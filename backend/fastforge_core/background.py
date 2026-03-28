"""
FastForge Background Jobs
==============================
background job system.
Simple abstraction that works with FastAPI's BackgroundTasks
and can be swapped for Celery/ARQ in production.

Usage:
    from fastforge_core.background import BackgroundJobManager, BackgroundJob

    class SendWelcomeEmailJob(BackgroundJob):
        def execute(self, user_id: int, email: str):
            send_email(email, "Welcome!", "...")

    # In your service:
    job_manager.enqueue(SendWelcomeEmailJob, user_id=42, email="user@example.com")

    # Or with FastAPI's built-in BackgroundTasks:
    @router.post("/users")
    def create_user(background_tasks: BackgroundTasks):
        ...
        job_manager.enqueue_fastapi(background_tasks, SendWelcomeEmailJob, user_id=42)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Type
from datetime import datetime, timezone
import logging
import traceback

logger = logging.getLogger("fastforge.jobs")


class BackgroundJob(ABC):
    """
    Base class for background jobs.
    Override execute() with your job logic.
    """

    @abstractmethod
    def execute(self, **kwargs):
        """Implement your job logic here."""
        pass

    def on_error(self, error: Exception, **kwargs):
        """Called when execute() raises an exception. Override for custom error handling."""
        logger.error(f"Job {self.__class__.__name__} failed: {error}\n{traceback.format_exc()}")


class BackgroundJobManager:
    """
    Manages background job execution.

    Default mode: runs jobs synchronously (suitable for dev/testing).
    Production: swap the executor for Celery/ARQ integration.
    """

    def __init__(self):
        self._registry: dict[str, Type[BackgroundJob]] = {}
        self._history: list[dict] = []

    def register(self, job_class: Type[BackgroundJob]):
        """Register a job class."""
        self._registry[job_class.__name__] = job_class
        return job_class

    def enqueue(self, job_class: Type[BackgroundJob], **kwargs):
        """
        Execute a job. In default mode, runs synchronously.
        Override this method to integrate with Celery/ARQ.
        """
        job = job_class()
        job_name = job_class.__name__
        started_at = datetime.now(timezone.utc)

        try:
            logger.info(f"Executing job: {job_name}")
            job.execute(**kwargs)
            self._history.append({
                "job": job_name,
                "status": "completed",
                "started_at": started_at.isoformat(),
                "kwargs": {k: str(v)[:100] for k, v in kwargs.items()},
            })
        except Exception as e:
            job.on_error(e, **kwargs)
            self._history.append({
                "job": job_name,
                "status": "failed",
                "error": str(e),
                "started_at": started_at.isoformat(),
            })

    def enqueue_fastapi(self, background_tasks, job_class: Type[BackgroundJob], **kwargs):
        """
        Enqueue using FastAPI's BackgroundTasks (runs after response is sent).

        Usage:
            @router.post("/orders")
            def create_order(background_tasks: BackgroundTasks):
                order = service.create(data)
                job_manager.enqueue_fastapi(background_tasks, SendOrderConfirmation, order_id=order.id)
                return order
        """
        def _run():
            self.enqueue(job_class, **kwargs)
        background_tasks.add_task(_run)

    def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent job execution history."""
        return self._history[-limit:]


# Global instance
job_manager = BackgroundJobManager()
