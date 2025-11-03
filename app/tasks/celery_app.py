from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "social_media_automation",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.file_tasks",
        "app.tasks.posting_tasks", 
        "app.tasks.analytics_tasks",
        "app.tasks.scheduling_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks schedule
celery_app.conf.beat_schedule = {
    # Sync analytics every hour
    'sync-analytics-hourly': {
        'task': 'app.tasks.analytics_tasks.sync_all_analytics',
        'schedule': crontab(minute=0),  # Every hour
    },
    # Process scheduled posts every minute
    'process-scheduled-posts': {
        'task': 'app.tasks.posting_tasks.process_scheduled_posts',
        'schedule': crontab(minute='*'),  # Every minute
    },
    # Clean up old files daily
    'cleanup-old-files': {
        'task': 'app.tasks.file_tasks.cleanup_old_files',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    # Generate daily analytics report
    'daily-analytics-report': {
        'task': 'app.tasks.analytics_tasks.generate_daily_report',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
}

celery_app.conf.timezone = 'UTC'