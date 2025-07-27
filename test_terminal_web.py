#!/usr/bin/env python3
"""
Script test để kiểm tra terminal web hoạt động
"""
import requests
import json
import time
import subprocess
import threading

def test_create_shell():
    """Test tạo shell mẫu"""
    print("[TEST] Tạo shell mẫu...")
    
    url = "http://localhost:5000/api/shells/create-sample"
    response = requests.post(url)
    
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            shell_id = data['shell_id']
            print(f"[SUCCESS] Tạo shell thành công: {shell_id}")
            return shell_id
        else:
            print(f"[ERROR] Tạo shell thất bại: {data['msg']}")
            return None
    else:
        print(f"[ERROR] HTTP {response.status_code}: {response.text}")
        return None

def test_start_shell(shell_id):
    """Test khởi động shell"""
    print(f"[TEST] Khởi động shell {shell_id}...")
    
    url = f"http://localhost:5000/api/shells/{shell_id}/start"
    response = requests.post(url)
    
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            print(f"[SUCCESS] Khởi động shell thành công")
            return True
        else:
            print(f"[ERROR] Khởi động shell thất bại: {data['msg']}")
            return False
    else:
        print(f"[ERROR] HTTP {response.status_code}: {response.text}")
        return False

def test_send_command(shell_id, command):
    """Test gửi lệnh"""
    print(f"[TEST] Gửi lệnh: {command}")
    
    url = f"http://localhost:5000/api/shells/{shell_id}/command"
    data = {"command": command}
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            print(f"[SUCCESS] Gửi lệnh thành công")
            return True
        else:
            print(f"[ERROR] Gửi lệnh thất bại: {data['msg']}")
            return False
    else:
        print(f"[ERROR] HTTP {response.status_code}: {response.text}")
        return False

def test_get_shell_status(shell_id):
    """Test lấy trạng thái shell"""
    print(f"[TEST] Lấy trạng thái shell {shell_id}...")
    
    url = f"http://localhost:5000/api/shells/{shell_id}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'success':
            shell_data = data['data']
            print(f"[SUCCESS] Trạng thái shell: {shell_data['status']}")
            return shell_data['status']
        else:
            print(f"[ERROR] Lấy trạng thái thất bại: {data['msg']}")
            return None
    else:
        print(f"[ERROR] HTTP {response.status_code}: {response.text}")
        return None

def test_web_interface():
    """Test giao diện web"""
    print("[TEST] Kiểm tra giao diện web...")
    
    # Test trang chính
    url = "http://localhost:5000/shells"
    response = requests.get(url)
    
    if response.status_code == 200:
        print("[SUCCESS] Trang chính shell hoạt động")
    else:
        print(f"[ERROR] Trang chính shell không hoạt động: HTTP {response.status_code}")
        return False
    
    return True

def main():
    """Hàm chính test"""
    print("=== TEST TERMINAL WEB ===")
    
    # Test 1: Kiểm tra web interface
    if not test_web_interface():
        print("[ERROR] Web interface không hoạt động, dừng test")
        return
    
    # Test 2: Tạo shell mẫu
    shell_id = test_create_shell()
    if not shell_id:
        print("[ERROR] Không thể tạo shell, dừng test")
        return
    
    # Test 3: Lấy trạng thái shell ban đầu
    status = test_get_shell_status(shell_id)
    print(f"[INFO] Trạng thái shell ban đầu: {status}")
    
    # Test 4: Khởi động shell
    if test_start_shell(shell_id):
        # Đợi một chút để shell khởi động
        time.sleep(2)
        
        # Test 5: Lấy trạng thái sau khi khởi động
        status = test_get_shell_status(shell_id)
        print(f"[INFO] Trạng thái shell sau khởi động: {status}")
        
        # Test 6: Gửi lệnh test (nếu shell đã connected)
        if status and 'connected' in status.lower():
            test_send_command(shell_id, "whoami")
            test_send_command(shell_id, "pwd")
            test_send_command(shell_id, "ls -la")
    
    print("\n=== TEST HOÀN THÀNH ===")
    print("Để test terminal thật, hãy:")
    print("1. Mở trình duyệt và truy cập: http://localhost:5000/shells")
    print("2. Tạo shell mới hoặc chọn shell có sẵn")
    print("3. Nhấn 'Bật Shell' để khởi động")
    print("4. Sử dụng terminal để tương tác")

if __name__ == "__main__":
    main() 