"""
Scheduler Service for running periodic background tasks
"""
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.orchestrator.message import Message, MessageType, MessagePriority
from app.database.firebase_client import firebase_client

logger = logging.getLogger(__name__)

class SchedulerService:
    """
    Service for scheduling and managing background tasks.
    Uses APScheduler for async task scheduling.
    """
    
    def __init__(self, orchestrator=None):
        """
        Initialize the scheduler service.
        
        Args:
            orchestrator: Reference to the orchestrator for sending messages
        """
        self.scheduler = AsyncIOScheduler()
        self.orchestrator = orchestrator
        self.jobs: Dict[str, str] = {}  # job_name -> job_id mapping
        
        # Configuration for synthesis intervals
        self.synthesis_interval_minutes = 15
        self.daily_summary_hour = 8  # 8 AM
        
        logger.info("Scheduler service initialized")
    
    def start(self):
        """Start the scheduler"""
        try:
            self.scheduler.start()
            self._setup_default_jobs()
            logger.info("Scheduler started with default jobs")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
    
    def stop(self):
        """Stop the scheduler"""
        try:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
    
    def _setup_default_jobs(self):
        """Setup default scheduled jobs"""
        # Schedule synthesis cycle every 15 minutes
        self.add_interval_job(
            job_id="synthesis_cycle",
            func=self._run_synthesis_cycle,
            minutes=self.synthesis_interval_minutes,
            name="Synthesis Cycle"
        )
        
        # Schedule daily summary at 8 AM
        self.add_cron_job(
            job_id="daily_summary",
            func=self._run_daily_summary,
            hour=self.daily_summary_hour,
            minute=0,
            name="Daily Summary"
        )
        
        logger.info("Default jobs scheduled")
    
    async def _run_synthesis_cycle(self):
        """
        Run the synthesis cycle for all active users.
        Sends a message to the ProactiveSynthesisAgent via orchestrator.
        """
        try:
            logger.info("Running scheduled synthesis cycle")
            
            # Get all active users
            active_users = await self._get_active_users()
            
            for user_id in active_users:
                if self.orchestrator:
                    # Send synthesis message to orchestrator
                    message = Message(
                        type=MessageType.COMMAND,
                        sender="SchedulerService",
                        recipient="ProactiveSynthesisAgent",
                        payload={
                            "action": "START_SYNTHESIS_CYCLE",
                            "user_id": user_id,
                            "triggered_by": "scheduler"
                        },
                        priority=MessagePriority.NORMAL
                    )
                    
                    self.orchestrator.send_message(message)
                    logger.info(f"Triggered synthesis cycle for user {user_id}")
                else:
                    logger.warning("No orchestrator available for synthesis cycle")
                    
        except Exception as e:
            logger.error(f"Synthesis cycle failed: {e}")
    
    async def _run_daily_summary(self):
        """
        Run daily summary generation for all users.
        This is a more comprehensive synthesis that runs once per day.
        """
        try:
            logger.info("Running scheduled daily summary")
            
            # Get all active users
            active_users = await self._get_active_users()
            
            for user_id in active_users:
                if self.orchestrator:
                    # Send daily summary message
                    message = Message(
                        type=MessageType.COMMAND,
                        sender="SchedulerService",
                        recipient="ProactiveSynthesisAgent",
                        payload={
                            "action": "GENERATE_DAILY_SUMMARY",
                            "user_id": user_id,
                            "triggered_by": "scheduler"
                        },
                        priority=MessagePriority.LOW
                    )
                    
                    self.orchestrator.send_message(message)
                    logger.info(f"Triggered daily summary for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Daily summary generation failed: {e}")
    
    async def _get_active_users(self) -> list:
        """
        Get list of active users from the database.
        
        Returns:
            List of user IDs that should receive scheduled updates
        """
        try:
            # Query users who have logged in within the last 7 days
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            
            users_ref = firebase_client.db.collection("users")
            query = users_ref.where("last_login", ">=", seven_days_ago.isoformat())
            
            active_users = []
            for doc in query.stream():
                user_data = doc.to_dict()
                # Only include users who have granted Gmail access
                if user_data.get("has_gmail_access", False):
                    active_users.append(doc.id)
            
            logger.info(f"Found {len(active_users)} active users for scheduled tasks")
            return active_users
            
        except Exception as e:
            logger.error(f"Failed to get active users: {e}")
            return []
    
    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        name: Optional[str] = None
    ) -> str:
        """
        Add an interval-based job to the scheduler.
        
        Args:
            job_id: Unique identifier for the job
            func: Function to execute
            seconds: Interval in seconds
            minutes: Interval in minutes
            hours: Interval in hours
            name: Human-readable name for the job
            
        Returns:
            Job ID
        """
        try:
            # Remove existing job if it exists
            if job_id in self.jobs:
                self.remove_job(job_id)
            
            # Create interval trigger with valid parameters
            kwargs = {}
            if seconds is not None:
                kwargs['seconds'] = seconds
            if minutes is not None:
                kwargs['minutes'] = minutes
            if hours is not None:
                kwargs['hours'] = hours
            
            trigger = IntervalTrigger(**kwargs)
            
            # Add job to scheduler
            job = self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name=name or job_id,
                replace_existing=True
            )
            
            self.jobs[job_id] = job.id
            logger.info(f"Added interval job: {job_id}")
            
            return job.id
            
        except Exception as e:
            logger.error(f"Failed to add interval job {job_id}: {e}")
            raise
    
    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        day_of_week: Optional[str] = None,
        name: Optional[str] = None
    ) -> str:
        """
        Add a cron-based job to the scheduler.
        
        Args:
            job_id: Unique identifier for the job
            func: Function to execute
            hour: Hour to run (0-23)
            minute: Minute to run (0-59)
            day_of_week: Day of week (mon-sun)
            name: Human-readable name for the job
            
        Returns:
            Job ID
        """
        try:
            # Remove existing job if it exists
            if job_id in self.jobs:
                self.remove_job(job_id)
            
            # Create cron trigger
            trigger = CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=day_of_week
            )
            
            # Add job to scheduler
            job = self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name=name or job_id,
                replace_existing=True
            )
            
            self.jobs[job_id] = job.id
            logger.info(f"Added cron job: {job_id}")
            
            return job.id
            
        except Exception as e:
            logger.error(f"Failed to add cron job {job_id}: {e}")
            raise
    
    def remove_job(self, job_id: str) -> bool:
        """
        Remove a job from the scheduler.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if removed, False otherwise
        """
        try:
            if job_id in self.jobs:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
                logger.info(f"Removed job: {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """
        Pause a scheduled job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if paused, False otherwise
        """
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """
        Resume a paused job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if resumed, False otherwise
        """
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False
    
    def get_jobs(self) -> list:
        """
        Get list of all scheduled jobs.
        
        Returns:
            List of job information
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        return jobs

# Global instance (will be initialized in main.py)
scheduler_service = None