"""
Celery Application — Configuration with task routing.
"""
from celery import Celery
from api.core.config import settings

celery_app = Celery(
    "nexus_worker",
    broker=settings.REDIS_URI,
    backend=settings.REDIS_URI,
    include=[
        "api.worker.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minute hard limit
    task_soft_time_limit=540,  # 9 minute soft limit
    worker_prefetch_multiplier=1,  # One task at a time for VRAM management
    task_routes={
        "process_document": {"queue": "documents"},
        "generate_embeddings": {"queue": "embeddings"},
        "run_workflow_step": {"queue": "workflows"},
    },
)
