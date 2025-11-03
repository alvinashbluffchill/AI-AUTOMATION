from celery import current_task
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from celery.schedules import crontab

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.models import Schedule, Post
from app.tasks.posting_tasks import execute_schedule


@celery_app.task(bind=True)
def schedule_post_task(self, post_id: int, platform_ids: list, scheduled_time: datetime):
    """Schedule a post for future posting"""
    
    try:
        db = SessionLocal()
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise Exception("Post not found")
        
        # Calculate delay until scheduled time
        now = datetime.now()
        if scheduled_time <= now:
            # Post immediately if scheduled time is in the past
            from app.tasks.posting_tasks import post_to_multiple_platforms
            post_to_multiple_platforms.delay(post_id, platform_ids)
            
            return {
                'post_id': post_id,
                'status': 'posted_immediately',
                'scheduled_time': scheduled_time
            }
        
        # Schedule for future posting
        delay_seconds = (scheduled_time - now).total_seconds()
        
        # Use Celery's eta (estimated time of arrival) to schedule the task
        from app.tasks.posting_tasks import post_to_multiple_platforms
        post_to_multiple_platforms.apply_async(
            args=[post_id, platform_ids],
            eta=scheduled_time
        )
        
        # Update post status
        post.status = "scheduled"
        post.scheduled_time = scheduled_time
        db.commit()
        
        return {
            'post_id': post_id,
            'status': 'scheduled',
            'scheduled_time': scheduled_time,
            'delay_seconds': delay_seconds
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': f'Scheduling failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True)
def create_recurring_schedule(self, schedule_id: int):
    """Set up recurring schedule using Celery Beat"""
    
    try:
        db = SessionLocal()
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        
        if not schedule:
            raise Exception("Schedule not found")
        
        # Create dynamic periodic task
        task_name = f"schedule_{schedule_id}"
        
        if schedule.schedule_type == "daily":
            time_str = schedule.schedule_data.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            
            celery_app.conf.beat_schedule[task_name] = {
                'task': 'app.tasks.posting_tasks.execute_schedule',
                'schedule': crontab(hour=hour, minute=minute),
                'args': (schedule_id,)
            }
            
        elif schedule.schedule_type == "weekly":
            day_of_week = schedule.schedule_data.get("day_of_week", 1)
            time_str = schedule.schedule_data.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            
            celery_app.conf.beat_schedule[task_name] = {
                'task': 'app.tasks.posting_tasks.execute_schedule',
                'schedule': crontab(hour=hour, minute=minute, day_of_week=day_of_week),
                'args': (schedule_id,)
            }
            
        elif schedule.schedule_type == "monthly":
            day_of_month = schedule.schedule_data.get("day_of_month", 1)
            time_str = schedule.schedule_data.get("time", "09:00")
            hour, minute = map(int, time_str.split(":"))
            
            celery_app.conf.beat_schedule[task_name] = {
                'task': 'app.tasks.posting_tasks.execute_schedule',
                'schedule': crontab(hour=hour, minute=minute, day_of_month=day_of_month),
                'args': (schedule_id,)
            }
        
        # Update Celery configuration
        celery_app.control.add_consumer(task_name)
        
        return {
            'schedule_id': schedule_id,
            'task_name': task_name,
            'schedule_type': schedule.schedule_type,
            'status': 'created'
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': f'Recurring schedule creation failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


@celery_app.task
def check_and_execute_schedules():
    """Check for schedules that need to be executed"""
    
    try:
        db = SessionLocal()
        
        # Get schedules that are due for execution
        now = datetime.now()
        due_schedules = db.query(Schedule).filter(
            Schedule.is_active == True,
            Schedule.next_execution <= now
        ).all()
        
        executed_count = 0
        
        for schedule in due_schedules:
            try:
                # Execute the schedule
                execute_schedule.delay(schedule.id)
                executed_count += 1
                
            except Exception as e:
                print(f"Error executing schedule {schedule.id}: {e}")
        
        return {
            'executed_count': executed_count,
            'total_due': len(due_schedules),
            'timestamp': now
        }
        
    except Exception as e:
        print(f"Error in check_and_execute_schedules: {e}")
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True)
def bulk_schedule_posts(self, post_ids: list, schedule_config: dict):
    """Schedule multiple posts with different timing"""
    
    try:
        db = SessionLocal()
        
        scheduled_posts = []
        failed_posts = []
        
        base_time = datetime.fromisoformat(schedule_config.get('start_time'))
        interval_minutes = schedule_config.get('interval_minutes', 60)
        platforms = schedule_config.get('platforms', [])
        
        for i, post_id in enumerate(post_ids):
            try:
                # Calculate scheduled time for this post
                scheduled_time = base_time + timedelta(minutes=i * interval_minutes)
                
                # Update progress
                progress = int((i / len(post_ids)) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'progress': progress,
                        'current': i + 1,
                        'total': len(post_ids),
                        'status': f'Scheduling post {post_id}...'
                    }
                )
                
                # Schedule the post
                schedule_post_task.delay(post_id, platforms, scheduled_time)
                
                scheduled_posts.append({
                    'post_id': post_id,
                    'scheduled_time': scheduled_time,
                    'platforms': platforms
                })
                
            except Exception as e:
                failed_posts.append({
                    'post_id': post_id,
                    'error': str(e)
                })
        
        return {
            'scheduled_posts': scheduled_posts,
            'failed_posts': failed_posts,
            'success_count': len(scheduled_posts),
            'failure_count': len(failed_posts)
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': f'Bulk scheduling failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


@celery_app.task
def update_schedule_queue(schedule_id: int, new_content: list):
    """Update the content queue for a schedule"""
    
    try:
        db = SessionLocal()
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        
        if not schedule:
            raise Exception("Schedule not found")
        
        # Update content queue
        schedule.content_queue = new_content
        
        # Reset current index if needed
        if schedule.current_index >= len(new_content):
            schedule.current_index = 0
        
        db.commit()
        
        return {
            'schedule_id': schedule_id,
            'content_count': len(new_content),
            'current_index': schedule.current_index,
            'status': 'updated'
        }
        
    except Exception as e:
        db.rollback()
        raise
    
    finally:
        db.close()


@celery_app.task
def pause_schedule(schedule_id: int):
    """Pause a recurring schedule"""
    
    try:
        db = SessionLocal()
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        
        if not schedule:
            raise Exception("Schedule not found")
        
        # Deactivate schedule
        schedule.is_active = False
        db.commit()
        
        # Remove from Celery Beat schedule
        task_name = f"schedule_{schedule_id}"
        if task_name in celery_app.conf.beat_schedule:
            del celery_app.conf.beat_schedule[task_name]
        
        return {
            'schedule_id': schedule_id,
            'status': 'paused'
        }
        
    except Exception as e:
        db.rollback()
        raise
    
    finally:
        db.close()


@celery_app.task
def resume_schedule(schedule_id: int):
    """Resume a paused schedule"""
    
    try:
        db = SessionLocal()
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        
        if not schedule:
            raise Exception("Schedule not found")
        
        # Reactivate schedule
        schedule.is_active = True
        
        # Recalculate next execution time
        from app.tasks.posting_tasks import calculate_next_execution_time
        schedule.next_execution = calculate_next_execution_time(schedule)
        
        db.commit()
        
        # Re-add to Celery Beat schedule
        create_recurring_schedule.delay(schedule_id)
        
        return {
            'schedule_id': schedule_id,
            'next_execution': schedule.next_execution,
            'status': 'resumed'
        }
        
    except Exception as e:
        db.rollback()
        raise
    
    finally:
        db.close()


@celery_app.task
def cleanup_completed_schedules():
    """Clean up completed one-time schedules"""
    
    try:
        db = SessionLocal()
        
        # Find completed one-time schedules
        now = datetime.now()
        completed_schedules = db.query(Schedule).filter(
            Schedule.schedule_type == "once",
            Schedule.next_execution < now - timedelta(hours=1),  # 1 hour buffer
            Schedule.last_executed.isnot(None)
        ).all()
        
        deleted_count = 0
        
        for schedule in completed_schedules:
            # Remove from Celery Beat schedule
            task_name = f"schedule_{schedule.id}"
            if task_name in celery_app.conf.beat_schedule:
                del celery_app.conf.beat_schedule[task_name]
            
            # Delete schedule
            db.delete(schedule)
            deleted_count += 1
        
        db.commit()
        
        return {
            'deleted_count': deleted_count,
            'timestamp': now
        }
        
    except Exception as e:
        db.rollback()
        raise
    
    finally:
        db.close()