# apps/weevely/worker.py
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from session_manager import WeevelySessionManager

class WeevelyWorker:
    def __init__(self, max_workers=10):
        self.task_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = True
        
    def add_task(self, weevely_id, command, callback):
        """Thêm task vào queue"""
        task = {
            'weevely_id': weevely_id,
            'command': command,
            'callback': callback,
            'timestamp': time.time()
        }
        self.task_queue.put(task)
    
    def process_tasks(self):
        """Xử lý tasks trong background"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                future = self.executor.submit(self._execute_task, task)
                future.add_done_callback(self._task_completed)
            except queue.Empty:
                continue
    
    def _execute_task(self, task):
        """Thực thi task cụ thể"""
        session_manager = WeevelySessionManager()
        return session_manager.execute_command(
            task['weevely_id'], 
            task['command']
        )