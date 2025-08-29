# -*- encoding: utf-8 -*-
"""
Cron Scheduler for Weevely Cron Jobs
Tự động chạy các cron jobs theo thời gian đã hẹn
"""

import os
import sys
import time
import threading
import schedule
import datetime as dt
from croniter import croniter
from typing import Dict, List, Optional
import logging

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configure logging
def setup_logging():
    """Setup logging with proper directory creation"""
    try:
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(project_root, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, 'cron_scheduler.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    except Exception as e:
        # Fallback to console only if file logging fails
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger(__name__)

logger = setup_logging()

class WeevelyCronScheduler:
    """Scheduler để tự động chạy các cron jobs"""
    
    def __init__(self):
        self.running = False
        self.scheduler_thread = None
        self.jobs = {}
        self.last_check = None
        self.check_interval = 60  # Kiểm tra mỗi 60 giây
        self.app = None  # Store Flask app instance for context
        
    def set_app(self, app):
        """Set Flask app instance for context management"""
        self.app = app
        logger.info("Flask app instance set for cron scheduler")
        
    def start(self):
        """Bắt đầu scheduler"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
            
        if not self.app:
            logger.error("Cannot start scheduler: Flask app not set. Call set_app() first.")
            return
            
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("Cron scheduler started with Flask app context")
        
    def stop(self):
        """Dừng scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Cron scheduler stopped")
        
    def _run_scheduler(self):
        """Main scheduler loop"""
        logger.info("Starting cron scheduler loop...")
        
        while self.running:
            try:
                # Sử dụng app instance đã được set để tạo context
                if self.app:
                    with self.app.app_context():
                        self._check_and_run_jobs()
                else:
                    logger.warning("No Flask app instance available")
                    
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(10)  # Wait a bit before retrying
                
    def _check_and_run_jobs(self):
        """Kiểm tra và chạy các cron jobs cần thiết"""
        try:
            current_time = dt.datetime.utcnow()
            
            # Import models trong app context
            from apps.models import CronJob
            
            # Lấy tất cả cron jobs đang active
            active_jobs = CronJob.get_active_jobs()
            
            for job in active_jobs:
                try:
                    # Kiểm tra xem job có cần chạy không
                    if self._should_run_job(job, current_time):
                        logger.info(f"Executing cron job: {job.name} (ID: {job.id})")
                        
                        # Chạy job trong thread riêng để không block scheduler
                        job_thread = threading.Thread(
                            target=self._execute_job_safe,
                            args=(job.id,),
                            daemon=True
                        )
                        job_thread.start()
                        
                        # Update job statistics
                        job.last_run = current_time
                        job.run_count += 1
                        job.save()
                        
                        logger.info(f"Cron job {job.name} executed successfully")
                        
                except Exception as e:
                    logger.error(f"Error processing cron job {job.name}: {str(e)}")
                    # Update failure count
                    job.failure_count += 1
                    job.save()
                    
            self.last_check = current_time
            
        except Exception as e:
            logger.error(f"Error checking cron jobs: {str(e)}")
            
    def _should_run_job(self, job, current_time: dt.datetime) -> bool:
        """Kiểm tra xem job có cần chạy không dựa trên cron expression"""
        try:
            # Parse cron expression
            cron = croniter(job.cron_expression, job.last_run or current_time)
            next_run = cron.get_next(dt.datetime)
            
            # Job cần chạy nếu:
            # 1. Chưa chạy lần nào (last_run = None)
            # 2. Hoặc đã đến thời gian chạy tiếp theo
            if not job.last_run:
                return True
            
            if current_time >= next_run:
                return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error parsing cron expression for job {job.name}: {str(e)}")
            return False
            
    def _execute_job_safe(self, job_id: int):
        """Chạy job một cách an toàn với error handling"""
        try:
            # Sử dụng app instance để tạo context cho job execution
            if self.app:
                with self.app.app_context():
                    from apps.weevely.module_executor import CronWeevelyRunner
                    from apps.models import CronJob
                    
                    result = CronWeevelyRunner.run_cron_job(job_id)
                    
                    # Update job statistics
                    job = CronJob.find_by_id(job_id)
                    if job:
                        if result.get('success'):
                            job.success_count += 1
                        else:
                            job.failure_count += 1
                        job.save()
            else:
                logger.error("No Flask app instance available for job execution")
                
        except Exception as e:
            logger.error(f"Error executing cron job {job_id}: {str(e)}")
            
    def get_scheduler_status(self) -> Dict:
        """Lấy trạng thái của scheduler"""
        try:
            if self.app:
                with self.app.app_context():
                    from apps.models import CronJob
                    active_jobs = CronJob.get_active_jobs()
                    
                    return {
                        'running': self.running,
                        'last_check': self.last_check.isoformat() if self.last_check else None,
                        'active_jobs_count': len(active_jobs),
                        'total_jobs_count': CronJob.query.count(),
                        'check_interval_seconds': self.check_interval,
                        'app_context': 'Available'
                    }
            else:
                return {
                    'running': self.running,
                    'last_check': self.last_check.isoformat() if self.last_check else None,
                    'active_jobs_count': 0,
                    'total_jobs_count': 0,
                    'check_interval_seconds': self.check_interval,
                    'app_context': 'Not Available'
                }
        except Exception as e:
            logger.error(f"Error getting scheduler status: {str(e)}")
            return {
                'running': self.running,
                'error': str(e)
            }
        
    def force_run_job(self, job_id: int) -> Dict:
        """Chạy job ngay lập tức (manual execution)"""
        try:
            if not self.app:
                return {'success': False, 'error': 'No Flask app instance available'}
                
            with self.app.app_context():
                from apps.models import CronJob
                from apps.weevely.module_executor import CronWeevelyRunner
                
                job = CronJob.find_by_id(job_id)
                if not job:
                    return {'success': False, 'error': 'Job not found'}
                    
                if not job.is_active:
                    return {'success': False, 'error': 'Job is inactive'}
                    
                logger.info(f"Force running cron job: {job.name} (ID: {job.id})")
                
                # Execute job
                result = CronWeevelyRunner.run_cron_job(job_id)
                
                # Update statistics
                job.run_count += 1
                job.last_run = dt.datetime.utcnow()
                if result.get('success'):
                    job.success_count += 1
                else:
                    job.failure_count += 1
                job.save()
                
                return {
                    'success': True,
                    'job_name': job.name,
                    'result': result,
                    'message': 'Job executed successfully'
                }
                
        except Exception as e:
            logger.error(f"Error force running job {job_id}: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _download_folder() -> str:
        from flask import current_app
        import os
        # Use singular 'download' folder per requirement
        path = os.path.join(current_app.root_path, '..', 'dataserver', 'download')
        os.makedirs(path, exist_ok=True)
        return path

# Global scheduler instance
cron_scheduler = WeevelyCronScheduler()

def init_scheduler_with_app(app):
    """Initialize scheduler with Flask app instance"""
    try:
        cron_scheduler.set_app(app)
        logger.info("Cron scheduler initialized with Flask app")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize cron scheduler with app: {str(e)}")
        return False

def start_cron_scheduler():
    """Start cron scheduler (called from main app)"""
    try:
        cron_scheduler.start()
        return True
    except Exception as e:
        logger.error(f"Failed to start cron scheduler: {str(e)}")
        return False
        
def stop_cron_scheduler():
    """Stop cron scheduler"""
    try:
        cron_scheduler.stop()
        return True
    except Exception as e:
        logger.error(f"Failed to stop cron scheduler: {str(e)}")
        return False
        
def get_scheduler_status():
    """Get scheduler status"""
    return cron_scheduler.get_scheduler_status()
    
def force_run_job(job_id: int):
    """Force run a specific cron job"""
    return cron_scheduler.force_run_job(job_id)

if __name__ == "__main__":
    # Test scheduler
    print("Starting Weevely Cron Scheduler...")
    start_cron_scheduler()
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        stop_cron_scheduler()
        print("Scheduler stopped")
