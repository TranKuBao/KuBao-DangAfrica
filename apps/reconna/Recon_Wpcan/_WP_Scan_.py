from flask import Flask, request, Response
#from flask_cors import CORS
import subprocess
from urllib.parse import urlparse
import threading
import time
import queue
import json

class Recon_Wpscan:
    process = None
    is_running = False
    scan_data = []
    scan_queue = queue.Queue()
    scan_thread = None
    target = None
    clients = []  # Danh sách clients đang listen
    
    @classmethod
    def normalize_url(cls, target):
        parsed = urlparse(target)
        if not parsed.scheme:
            target = "http://" + target
        return target

    @classmethod
    def start_scan(cls, target):
        if cls.is_running:
            return False,"Error: Scan is running..."
        if not target:
            return False, "Error: Missing Url..."
            
        cls.target = cls.normalize_url(target)
        cls.scan_data = []
        cls.is_running = True
        
        cls.scan_thread = threading.Thread(target=cls._run_scan)
        cls.scan_thread.daemon = True
        cls.scan_thread.start()
        
        return True,f"Start scanning {cls.target}...."

    @classmethod
    def _run_scan(cls):
        try:
            if not cls.target:
                raise ValueError("Target is not set")
                
            cls.process = subprocess.Popen(
                ["wpscan", "--url", cls.target, "--random-user-agent"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            
            if cls.process.stdout:
                for line in cls.process.stdout:
                    if not cls.is_running:
                        break
                        
                    line = line.strip()
                    if line:
                        cls.scan_data.append(line)
                        # Gửi real-time cho tất cả clients
                        cls._broadcast_to_clients(line)
                        
                cls.process.stdout.close()
            cls.process.wait()
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            cls.scan_data.append(error_msg)
            cls._broadcast_to_clients(error_msg)
        finally:
            cls.is_running = False
            cls.process = None
            cls._broadcast_to_clients("SCAN_COMPLETED")

    @classmethod
    def _broadcast_to_clients(cls, message):
        """Gửi message tới tất cả clients đang listen"""
        for client_queue in cls.clients:
            try:
                client_queue.put({
                    'timestamp': time.time(),
                    'message': message,
                    'target': cls.target
                })
            except:
                pass  # Client đã disconnect

    @classmethod
    def stream_data(cls):
        """Tạo queue cho client mới và trả về generator"""
        client_queue = queue.Queue()
        cls.clients.append(client_queue)
        
        def generate():
            try:
                while cls.is_running or not client_queue.empty():
                    try:
                        data = client_queue.get(timeout=1)
                        yield f"data: {json.dumps(data)}\n\n"
                    except queue.Empty:
                        if not cls.is_running:
                            break
                        continue
            finally:
                # Remove client khi disconnect
                if client_queue in cls.clients:
                    cls.clients.remove(client_queue)
                    
        return Response(generate(), mimetype='text/event-stream')