from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from datetime import datetime
import uuid
from PIL import Image

from app.core.database import get_db
from app.core.config import settings
from app.models.models import Post, User, SocialAccount
from app.tasks.file_tasks import process_uploaded_file, generate_thumbnail

router = APIRouter()


def validate_file(file: UploadFile) -> bool:
    """Validate uploaded file"""
    if not file.filename:
        return False
    
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in settings.ALLOWED_EXTENSIONS:
        return False
    
    return True


def save_uploaded_file(file: UploadFile, user_id: int) -> str:
    """Save uploaded file to disk"""
    if not validate_file(file):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Create user-specific directory
    user_dir = os.path.join(settings.UPLOAD_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(user_dir, unique_filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return file_path


@router.post("/file")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    platforms: str = Form(...),  # JSON string of platform IDs
    schedule_time: Optional[str] = Form(None),
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Upload a file for social media posting"""
    
    try:
        # Validate file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Save file
        file_path = save_uploaded_file(file, user_id)
        
        # Determine file type
        file_extension = os.path.splitext(file.filename)[1].lower()
        file_type = "video" if file_extension in [".mp4", ".avi", ".mov"] else "image"
        
        # Parse schedule time
        scheduled_time = None
        if schedule_time:
            try:
                scheduled_time = datetime.fromisoformat(schedule_time.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid schedule time format")
        
        # Create post record
        post = Post(
            user_id=user_id,
            title=title,
            description=description,
            file_path=file_path,
            file_type=file_type,
            scheduled_time=scheduled_time or datetime.now(),
            status="uploaded"
        )
        
        db.add(post)
        db.commit()
        db.refresh(post)
        
        # Process file in background
        background_tasks.add_task(process_uploaded_file, post.id, file_path, file_type)
        
        # Generate thumbnail for videos
        if file_type == "video":
            background_tasks.add_task(generate_thumbnail, post.id, file_path)
        
        return {
            "message": "File uploaded successfully",
            "post_id": post.id,
            "file_path": file_path,
            "file_type": file_type,
            "scheduled_time": scheduled_time
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/multiple")
async def upload_multiple_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    titles: str = Form(...),  # JSON string of titles
    descriptions: Optional[str] = Form(None),  # JSON string of descriptions
    platforms: str = Form(...),  # JSON string of platform IDs
    schedule_times: Optional[str] = Form(None),  # JSON string of schedule times
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Upload multiple files for batch processing"""
    
    import json
    
    try:
        titles_list = json.loads(titles)
        descriptions_list = json.loads(descriptions) if descriptions else []
        schedule_times_list = json.loads(schedule_times) if schedule_times else []
        
        if len(files) != len(titles_list):
            raise HTTPException(status_code=400, detail="Number of files and titles must match")
        
        uploaded_posts = []
        
        for i, file in enumerate(files):
            # Get corresponding metadata
            title = titles_list[i]
            description = descriptions_list[i] if i < len(descriptions_list) else None
            schedule_time = schedule_times_list[i] if i < len(schedule_times_list) else None
            
            # Save file
            file_path = save_uploaded_file(file, user_id)
            
            # Determine file type
            file_extension = os.path.splitext(file.filename)[1].lower()
            file_type = "video" if file_extension in [".mp4", ".avi", ".mov"] else "image"
            
            # Parse schedule time
            scheduled_time = None
            if schedule_time:
                try:
                    scheduled_time = datetime.fromisoformat(schedule_time.replace('Z', '+00:00'))
                except ValueError:
                    scheduled_time = datetime.now()
            
            # Create post record
            post = Post(
                user_id=user_id,
                title=title,
                description=description,
                file_path=file_path,
                file_type=file_type,
                scheduled_time=scheduled_time or datetime.now(),
                status="uploaded"
            )
            
            db.add(post)
            db.commit()
            db.refresh(post)
            
            # Process file in background
            background_tasks.add_task(process_uploaded_file, post.id, file_path, file_type)
            
            uploaded_posts.append({
                "post_id": post.id,
                "filename": file.filename,
                "file_type": file_type,
                "scheduled_time": scheduled_time
            })
        
        return {
            "message": f"Successfully uploaded {len(files)} files",
            "posts": uploaded_posts
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")


@router.get("/posts")
async def get_user_posts(
    user_id: int = 1,  # TODO: Get from authentication
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get user's uploaded posts"""
    
    query = db.query(Post).filter(Post.user_id == user_id)
    
    if status:
        query = query.filter(Post.status == status)
    
    posts = query.order_by(Post.created_at.desc()).all()
    
    return {
        "posts": [
            {
                "id": post.id,
                "title": post.title,
                "description": post.description,
                "file_path": post.file_path,
                "file_type": post.file_type,
                "thumbnail_path": post.thumbnail_path,
                "scheduled_time": post.scheduled_time,
                "posted_at": post.posted_at,
                "status": post.status,
                "created_at": post.created_at
            }
            for post in posts
        ]
    }


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: int,
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Delete a post and its associated file"""
    
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == user_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Delete file from disk
    if os.path.exists(post.file_path):
        os.remove(post.file_path)
    
    # Delete thumbnail if exists
    if post.thumbnail_path and os.path.exists(post.thumbnail_path):
        os.remove(post.thumbnail_path)
    
    # Delete from database
    db.delete(post)
    db.commit()
    
    return {"message": "Post deleted successfully"}