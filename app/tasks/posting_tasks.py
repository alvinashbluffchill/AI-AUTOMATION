from celery import current_task
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.models import Post, SocialAccount, Schedule
from app.services.instagram_service import InstagramService
from app.services.facebook_service import FacebookService
from app.services.twitter_service import TwitterService
from app.services.youtube_service import YouTubeService
from app.services.tiktok_service import TikTokService


@celery_app.task(bind=True)
def post_to_platform(self, post_id: int, platform: str, social_account_id: int):
    """Post content to a specific social media platform"""
    
    try:
        db = SessionLocal()
        
        # Get post and social account
        post = db.query(Post).filter(Post.id == post_id).first()
        social_account = db.query(SocialAccount).filter(SocialAccount.id == social_account_id).first()
        
        if not post or not social_account:
            raise Exception("Post or social account not found")
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': f'Posting to {platform}...'})
        
        # Get appropriate service
        service = get_platform_service(platform, social_account)
        
        if not service:
            raise Exception(f"Service not available for platform: {platform}")
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 30, 'status': 'Uploading content...'})
        
        # Post content
        result = service.post_content(
            file_path=post.file_path,
            caption=post.description,
            title=post.title
        )
        
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'Finalizing post...'})
        
        # Update post record
        post.platform_post_id = result.get('post_id')
        post.posted_at = datetime.now()
        post.status = "posted"
        post.social_account_id = social_account_id
        
        # Store platform-specific data
        if post.platform_data:
            post.platform_data.update(result)
        else:
            post.platform_data = result
        
        db.commit()
        
        self.update_state(state='SUCCESS', meta={'progress': 100, 'status': 'Posted successfully'})
        
        return {
            'post_id': post_id,
            'platform': platform,
            'platform_post_id': result.get('post_id'),
            'posted_at': post.posted_at,
            'status': 'success'
        }
        
    except Exception as e:
        # Update post status to failed
        if 'post' in locals():
            post.status = "failed"
            db.commit()
        
        self.update_state(
            state='FAILURE',
            meta={'progress': 0, 'status': f'Posting failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True)
def post_to_multiple_platforms(self, post_id: int, platform_ids: List[str]):
    """Post content to multiple platforms"""
    
    try:
        db = SessionLocal()
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise Exception("Post not found")
        
        results = []
        total_platforms = len(platform_ids)
        
        for i, platform in enumerate(platform_ids):
            try:
                # Update progress
                progress = int((i / total_platforms) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'progress': progress,
                        'current_platform': platform,
                        'status': f'Posting to {platform}...'
                    }
                )
                
                # Get social account for this platform
                social_account = db.query(SocialAccount).filter(
                    SocialAccount.user_id == post.user_id,
                    SocialAccount.platform == platform,
                    SocialAccount.is_active == True
                ).first()
                
                if not social_account:
                    results.append({
                        'platform': platform,
                        'status': 'failed',
                        'error': 'No active social account found'
                    })
                    continue
                
                # Post to platform
                service = get_platform_service(platform, social_account)
                result = service.post_content(
                    file_path=post.file_path,
                    caption=post.description,
                    title=post.title
                )
                
                results.append({
                    'platform': platform,
                    'status': 'success',
                    'platform_post_id': result.get('post_id'),
                    'result': result
                })
                
            except Exception as e:
                results.append({
                    'platform': platform,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Update post status based on results
        success_count = sum(1 for r in results if r['status'] == 'success')
        if success_count > 0:
            post.status = "posted" if success_count == total_platforms else "partially_posted"
            post.posted_at = datetime.now()
        else:
            post.status = "failed"
        
        # Store results in platform_data
        post.platform_data = {'posting_results': results}
        db.commit()
        
        return {
            'post_id': post_id,
            'results': results,
            'success_count': success_count,
            'total_platforms': total_platforms
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': f'Multi-platform posting failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


@celery_app.task
def process_scheduled_posts():
    """Process posts that are scheduled to be posted now"""
    
    try:
        db = SessionLocal()
        
        # Get posts scheduled for now (with 1-minute buffer)
        now = datetime.now()
        buffer_time = now + timedelta(minutes=1)
        
        scheduled_posts = db.query(Post).filter(
            Post.status == "scheduled",
            Post.scheduled_time <= buffer_time,
            Post.scheduled_time >= now - timedelta(minutes=5)  # Don't process very old scheduled posts
        ).all()
        
        processed_count = 0
        
        for post in scheduled_posts:
            try:
                # Get platform data
                platform_data = post.platform_data or {}
                platforms = platform_data.get('platforms', [])
                
                if platforms:
                    # Post to multiple platforms
                    post_to_multiple_platforms.delay(post.id, platforms)
                else:
                    # Default to user's first active social account
                    social_account = db.query(SocialAccount).filter(
                        SocialAccount.user_id == post.user_id,
                        SocialAccount.is_active == True
                    ).first()
                    
                    if social_account:
                        post_to_platform.delay(post.id, social_account.platform, social_account.id)
                
                processed_count += 1
                
            except Exception as e:
                print(f"Error processing scheduled post {post.id}: {e}")
                post.status = "failed"
                db.commit()
        
        return {
            'processed_count': processed_count,
            'timestamp': now,
            'status': 'success'
        }
        
    except Exception as e:
        print(f"Error in process_scheduled_posts: {e}")
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True)
def execute_schedule(self, schedule_id: int):
    """Execute a recurring schedule"""
    
    try:
        db = SessionLocal()
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        
        if not schedule or not schedule.is_active:
            return {'status': 'skipped', 'reason': 'Schedule not found or inactive'}
        
        # Get current content from queue
        content_queue = schedule.content_queue or []
        if not content_queue:
            return {'status': 'skipped', 'reason': 'No content in queue'}
        
        current_index = schedule.current_index
        if current_index >= len(content_queue):
            current_index = 0  # Reset to beginning
        
        current_content = content_queue[current_index]
        
        # Create post from content
        post = Post(
            user_id=schedule.user_id,
            title=current_content.get('title', ''),
            description=current_content.get('description', ''),
            file_path=current_content.get('file_path', ''),
            file_type=current_content.get('file_type', 'image'),
            scheduled_time=datetime.now(),
            status="scheduled"
        )
        
        db.add(post)
        db.commit()
        db.refresh(post)
        
        # Post to target platforms
        target_platforms = schedule.target_platforms or []
        if target_platforms:
            post_to_multiple_platforms.delay(post.id, target_platforms)
        
        # Update schedule
        schedule.current_index = (current_index + 1) % len(content_queue)
        schedule.last_executed = datetime.now()
        
        # Calculate next execution time
        schedule.next_execution = calculate_next_execution_time(schedule)
        
        db.commit()
        
        return {
            'schedule_id': schedule_id,
            'post_id': post.id,
            'content_index': current_index,
            'next_execution': schedule.next_execution,
            'status': 'success'
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': f'Schedule execution failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


def get_platform_service(platform: str, social_account):
    """Get the appropriate service for a platform"""
    
    services = {
        'instagram': InstagramService,
        'facebook': FacebookService,
        'twitter': TwitterService,
        'youtube': YouTubeService,
        'tiktok': TikTokService
    }
    
    service_class = services.get(platform)
    if service_class:
        return service_class(social_account)
    
    return None


def calculate_next_execution_time(schedule: Schedule) -> datetime:
    """Calculate next execution time for a schedule"""
    
    now = datetime.now()
    schedule_data = schedule.schedule_data or {}
    
    if schedule.schedule_type == "daily":
        time_str = schedule_data.get("time", "09:00")
        hour, minute = map(int, time_str.split(":"))
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run
    
    elif schedule.schedule_type == "weekly":
        day_of_week = schedule_data.get("day_of_week", 1)
        time_str = schedule_data.get("time", "09:00")
        hour, minute = map(int, time_str.split(":"))
        
        days_ahead = day_of_week - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        
        next_run = now + timedelta(days=days_ahead)
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return next_run
    
    elif schedule.schedule_type == "monthly":
        day_of_month = schedule_data.get("day_of_month", 1)
        time_str = schedule_data.get("time", "09:00")
        hour, minute = map(int, time_str.split(":"))
        
        next_run = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            if now.month == 12:
                next_run = next_run.replace(year=now.year + 1, month=1)
            else:
                next_run = next_run.replace(month=now.month + 1)
        
        return next_run
    
    # Default: next hour
    return now + timedelta(hours=1)