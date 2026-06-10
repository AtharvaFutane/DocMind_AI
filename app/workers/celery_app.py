"""
Celery application configuration.
"""
from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "documind",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,    # One task at a time per worker for heavy tasks
)

# Scheduled task: re-crawl all completed jobs every Sunday at 2am
celery_app.conf.beat_schedule = {
    "weekly-recrawl": {
        "task": "app.workers.tasks.recrawl_all_jobs",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),
    }
}
