from celery import current_task
from PIL import Image
import os
import subprocess
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.models import Post
from app.core.config import settings


def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


@celery_app.task(bind=True)
def process_uploaded_file(self, post_id: int, file_path: str, file_type: str):
    """Process uploaded file - compress, validate, etc."""
    
    try:
        db = SessionLocal()
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise Exception(f"Post {post_id} not found")
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'Processing file...'})
        
        if file_type == "image":
            # Process image
            processed_path = process_image(file_path)
            self.update_state(state='PROGRESS', meta={'progress': 50, 'status': 'Compressing image...'})
            
        elif file_type == "video":
            # Process video
            processed_path = process_video(file_path)
            self.update_state(state='PROGRESS', meta={'progress': 50, 'status': 'Processing video...'})
        
        # Update post status
        post.status = "processed"
        db.commit()
        
        self.update_state(state='SUCCESS', meta={'progress': 100, 'status': 'File processed successfully'})
        
        return {
            'post_id': post_id,
            'original_path': file_path,
            'processed_path': processed_path,
            'file_type': file_type
        }
        
    except Exception as e:
        db.rollback()
        post.status = "failed"
        db.commit()
        
        self.update_state(
            state='FAILURE',
            meta={'progress': 0, 'status': f'Processing failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True)
def generate_thumbnail(self, post_id: int, video_path: str):
    """Generate thumbnail for video file"""
    
    try:
        db = SessionLocal()
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise Exception(f"Post {post_id} not found")
        
        # Generate thumbnail using ffmpeg
        thumbnail_path = video_path.replace(os.path.splitext(video_path)[1], '_thumb.jpg')
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', '00:00:01.000',  # Take frame at 1 second
            '-vframes', '1',
            '-y',  # Overwrite output file
            thumbnail_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Update post with thumbnail path
            post.thumbnail_path = thumbnail_path
            db.commit()
            
            return {
                'post_id': post_id,
                'thumbnail_path': thumbnail_path,
                'status': 'success'
            }
        else:
            raise Exception(f"FFmpeg error: {result.stderr}")
            
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': f'Thumbnail generation failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


@celery_app.task
def cleanup_old_files():
    """Clean up old uploaded files"""
    
    try:
        db = SessionLocal()
        
        # Delete files older than 30 days that are not scheduled or posted
        cutoff_date = datetime.now() - timedelta(days=30)
        
        old_posts = db.query(Post).filter(
            Post.created_at < cutoff_date,
            Post.status.in_(["failed", "cancelled"])
        ).all()
        
        deleted_count = 0
        
        for post in old_posts:
            try:
                # Delete file from disk
                if post.file_path and os.path.exists(post.file_path):
                    os.remove(post.file_path)
                
                # Delete thumbnail if exists
                if post.thumbnail_path and os.path.exists(post.thumbnail_path):
                    os.remove(post.thumbnail_path)
                
                # Delete post record
                db.delete(post)
                deleted_count += 1
                
            except Exception as e:
                print(f"Error deleting post {post.id}: {e}")
                continue
        
        db.commit()
        
        return {
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date,
            'status': 'success'
        }
        
    except Exception as e:
        db.rollback()
        raise
    
    finally:
        db.close()


def process_image(file_path: str) -> str:
    """Process and compress image"""
    
    try:
        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large (max 1920x1080)
            max_size = (1920, 1080)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save with compression
            processed_path = file_path.replace(os.path.splitext(file_path)[1], '_processed.jpg')
            img.save(processed_path, 'JPEG', quality=85, optimize=True)
            
            return processed_path
            
    except Exception as e:
        raise Exception(f"Image processing failed: {str(e)}")


def process_video(file_path: str) -> str:
    """Process and compress video"""
    
    try:
        processed_path = file_path.replace(os.path.splitext(file_path)[1], '_processed.mp4')
        
        # Use ffmpeg to compress video
        cmd = [
            'ffmpeg',
            '-i', file_path,
            '-c:v', 'libx264',
            '-crf', '23',  # Constant Rate Factor for quality
            '-preset', 'medium',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',  # Optimize for web streaming
            '-y',  # Overwrite output file
            processed_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return processed_path
        else:
            raise Exception(f"Video processing failed: {result.stderr}")
            
    except Exception as e:
        raise Exception(f"Video processing failed: {str(e)}")


@celery_app.task(bind=True)
def batch_process_files(self, post_ids: list):
    """Process multiple files in batch"""
    
    total_files = len(post_ids)
    processed_files = []
    failed_files = []
    
    for i, post_id in enumerate(post_ids):
        try:
            db = SessionLocal()
            post = db.query(Post).filter(Post.id == post_id).first()
            
            if post:
                # Update progress
                progress = int((i / total_files) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'progress': progress,
                        'current': i + 1,
                        'total': total_files,
                        'status': f'Processing {post.title}...'
                    }
                )
                
                # Process file
                if post.file_type == "image":
                    processed_path = process_image(post.file_path)
                elif post.file_type == "video":
                    processed_path = process_video(post.file_path)
                    # Also generate thumbnail
                    generate_thumbnail.delay(post.id, post.file_path)
                
                post.status = "processed"
                db.commit()
                
                processed_files.append({
                    'post_id': post_id,
                    'title': post.title,
                    'processed_path': processed_path
                })
            
            db.close()
            
        except Exception as e:
            failed_files.append({
                'post_id': post_id,
                'error': str(e)
            })
    
    return {
        'total_files': total_files,
        'processed_files': processed_files,
        'failed_files': failed_files,
        'success_count': len(processed_files),
        'failure_count': len(failed_files)
    }