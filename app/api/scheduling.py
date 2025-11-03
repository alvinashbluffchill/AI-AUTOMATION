from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import json

from app.core.database import get_db
from app.models.models import Schedule, Post, SocialAccount
from app.tasks.scheduling_tasks import schedule_post_task, create_recurring_schedule

router = APIRouter()


class ScheduleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    schedule_type: str  # once, daily, weekly, monthly, custom
    schedule_data: dict  # Contains timing information
    content_queue: List[dict]  # List of content items
    target_platforms: List[str]  # Platform IDs


class ScheduleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    schedule_type: str
    is_active: bool
    current_index: int
    next_execution: Optional[datetime]
    created_at: datetime


class PostScheduleRequest(BaseModel):
    post_id: int
    platform_ids: List[str]
    scheduled_time: datetime
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None


@router.post("/create", response_model=ScheduleResponse)
async def create_schedule(
    schedule_data: ScheduleCreate,
    background_tasks: BackgroundTasks,
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Create a new posting schedule"""
    
    # Calculate next execution time
    next_execution = calculate_next_execution(schedule_data.schedule_type, schedule_data.schedule_data)
    
    # Create schedule record
    schedule = Schedule(
        user_id=user_id,
        name=schedule_data.name,
        description=schedule_data.description,
        schedule_type=schedule_data.schedule_type,
        schedule_data=schedule_data.schedule_data,
        content_queue=schedule_data.content_queue,
        target_platforms=schedule_data.target_platforms,
        next_execution=next_execution
    )
    
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    # Set up recurring schedule in Celery
    if schedule_data.schedule_type != "once":
        background_tasks.add_task(create_recurring_schedule, schedule.id)
    
    return schedule


@router.get("/list")
async def list_schedules(
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Get user's schedules"""
    
    schedules = db.query(Schedule).filter(Schedule.user_id == user_id).all()
    
    return {
        "schedules": [
            {
                "id": schedule.id,
                "name": schedule.name,
                "description": schedule.description,
                "schedule_type": schedule.schedule_type,
                "is_active": schedule.is_active,
                "current_index": schedule.current_index,
                "next_execution": schedule.next_execution,
                "created_at": schedule.created_at,
                "content_count": len(schedule.content_queue) if schedule.content_queue else 0
            }
            for schedule in schedules
        ]
    }


@router.post("/post")
async def schedule_single_post(
    request: PostScheduleRequest,
    background_tasks: BackgroundTasks,
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Schedule a single post to multiple platforms"""
    
    # Get the post
    post = db.query(Post).filter(Post.id == request.post_id, Post.user_id == user_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Update post with scheduling info
    post.scheduled_time = request.scheduled_time
    post.status = "scheduled"
    
    # Add platform-specific data
    platform_data = {
        "caption": request.caption,
        "hashtags": request.hashtags,
        "platforms": request.platform_ids
    }
    post.platform_data = platform_data
    
    db.commit()
    
    # Schedule the posting task
    background_tasks.add_task(
        schedule_post_task,
        post.id,
        request.platform_ids,
        request.scheduled_time
    )
    
    return {
        "message": "Post scheduled successfully",
        "post_id": post.id,
        "scheduled_time": request.scheduled_time,
        "platforms": request.platform_ids
    }


@router.put("/{schedule_id}/toggle")
async def toggle_schedule(
    schedule_id: int,
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Toggle schedule active/inactive"""
    
    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id,
        Schedule.user_id == user_id
    ).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    schedule.is_active = not schedule.is_active
    db.commit()
    
    return {
        "message": f"Schedule {'activated' if schedule.is_active else 'deactivated'}",
        "is_active": schedule.is_active
    }


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Delete a schedule"""
    
    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id,
        Schedule.user_id == user_id
    ).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    db.delete(schedule)
    db.commit()
    
    return {"message": "Schedule deleted successfully"}


@router.get("/{schedule_id}/preview")
async def preview_schedule(
    schedule_id: int,
    days: int = 7,
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Preview upcoming posts for a schedule"""
    
    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id,
        Schedule.user_id == user_id
    ).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Generate preview of upcoming posts
    upcoming_posts = generate_schedule_preview(schedule, days)
    
    return {
        "schedule_name": schedule.name,
        "preview_days": days,
        "upcoming_posts": upcoming_posts
    }


def calculate_next_execution(schedule_type: str, schedule_data: dict) -> datetime:
    """Calculate the next execution time based on schedule type"""
    
    now = datetime.now()
    
    if schedule_type == "once":
        return datetime.fromisoformat(schedule_data.get("datetime"))
    
    elif schedule_type == "daily":
        time_str = schedule_data.get("time", "09:00")
        hour, minute = map(int, time_str.split(":"))
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run
    
    elif schedule_type == "weekly":
        day_of_week = schedule_data.get("day_of_week", 1)  # Monday = 1
        time_str = schedule_data.get("time", "09:00")
        hour, minute = map(int, time_str.split(":"))
        
        days_ahead = day_of_week - now.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        next_run = now + timedelta(days=days_ahead)
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return next_run
    
    elif schedule_type == "monthly":
        day_of_month = schedule_data.get("day_of_month", 1)
        time_str = schedule_data.get("time", "09:00")
        hour, minute = map(int, time_str.split(":"))
        
        next_run = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            # Move to next month
            if now.month == 12:
                next_run = next_run.replace(year=now.year + 1, month=1)
            else:
                next_run = next_run.replace(month=now.month + 1)
        
        return next_run
    
    else:  # custom - use cron expression
        # For now, return next hour as placeholder
        return now + timedelta(hours=1)


def generate_schedule_preview(schedule: Schedule, days: int) -> List[dict]:
    """Generate a preview of upcoming posts"""
    
    preview = []
    current_time = schedule.next_execution or datetime.now()
    content_queue = schedule.content_queue or []
    current_index = schedule.current_index
    
    for i in range(min(days, len(content_queue))):
        content_item = content_queue[(current_index + i) % len(content_queue)]
        
        preview.append({
            "scheduled_time": current_time,
            "content": content_item,
            "platforms": schedule.target_platforms
        })
        
        # Calculate next execution time
        if schedule.schedule_type == "daily":
            current_time += timedelta(days=1)
        elif schedule.schedule_type == "weekly":
            current_time += timedelta(weeks=1)
        elif schedule.schedule_type == "monthly":
            # Approximate monthly increment
            current_time += timedelta(days=30)
    
    return preview