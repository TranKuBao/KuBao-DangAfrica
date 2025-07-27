# Terminal Web với PTY Thật

Hệ thống terminal web tích hợp với pwncat sử dụng PTY (Pseudo Terminal) thật, cho phép tương tác với reverse shell như terminal thật trên Kali Linux.

## Tính năng

- ✅ **Terminal thật**: Sử dụng PTY thật thay vì xterm.js
- ✅ **Real-time**: Socket.IO cho tương tác real-time
- ✅ **Reverse Shell**: Hỗ trợ reverse shell với pwncat
- ✅ **Bind Shell**: Hỗ trợ bind shell với pwncat
- ✅ **Auto-reconnect**: Tự động reconnect khi mất kết nối
- ✅ **Command History**: Lưu lịch sử lệnh
- ✅ **Database**: Lưu trữ thông tin shell trong database

## Cách sử dụng

### 1. Khởi động server

```bash
python run.py
```

Server sẽ chạy trên `http://localhost:5000`

### 2. Truy cập web interface

Mở trình duyệt và truy cập: `http://localhost:5000/shells`

### 3. Tạo shell mới

1. Nhấn "Add Shell" để tạo shell mới
2. Chọn loại shell:
   - **Reverse Shell**: Lắng nghe kết nối từ victim
   - **Bind Shell**: Kết nối tới shell đang chạy trên target
3. Nhập thông tin cần thiết (IP, port, etc.)
4. Nhấn "Create"

### 4. Khởi động shell

1. Chọn shell từ danh sách
2. Nhấn "Bật Shell" để khởi động
3. Đợi shell kết nối (status sẽ chuyển thành "Connected")

### 5. Tương tác với terminal

1. Khi shell đã kết nối, terminal sẽ hiển thị
2. Nhập lệnh vào ô input và nhấn Enter
3. Output sẽ hiển thị real-time
4. Sử dụng arrow keys để duyệt lịch sử lệnh

## Cấu trúc code

### Core Components

- `apps/managershell/pwncat.py`: Quản lý shell với PTY thật
- `apps/managershell/socketio_events.py`: Xử lý Socket.IO events
- `apps/managershell/routes.py`: API routes cho web interface
- `templates/shells/view-shell.html`: Giao diện terminal

### Key Features

#### PTY Management
```python
# Tạo PTY cho shell
master_fd, slave_fd = pty.openpty()

# Khởi động pwncat với PTY
proc = subprocess.Popen(
    ["python", "-m", "pwncat", "-lp", str(port)],
    stdin=slave_fd,
    stdout=slave_fd,
    stderr=slave_fd,
    close_fds=True,
    preexec_fn=os.setsid
)
```

#### Real-time Communication
```python
# Gửi input tới shell
os.write(master_fd, data.encode('utf-8'))

# Đọc output từ shell
data = os.read(master_fd, 1024)
```

#### Socket.IO Integration
```javascript
// Gửi lệnh tới shell
socket.emit('terminal_input', {
    shell_id: shellId,
    input: command + '\n'
});

// Nhận output từ shell
socket.on('terminal_output', function(data) {
    printOutput(data.output);
});
```

## API Endpoints

### Shell Management
- `GET /api/shells` - Lấy danh sách shell
- `POST /api/shells` - Tạo shell mới
- `GET /api/shells/<id>` - Lấy thông tin shell
- `POST /api/shells/<id>/start` - Khởi động shell
- `POST /api/shells/<id>/close` - Đóng shell
- `DELETE /api/shells/<id>` - Xóa shell

### Terminal Interaction
- `POST /api/shells/<id>/command` - Gửi lệnh
- `GET /api/shells/<id>/history` - Lấy lịch sử lệnh

### Socket.IO Events
- `terminal_input` - Gửi input tới shell
- `terminal_output` - Nhận output từ shell
- `shell_status_update` - Cập nhật trạng thái shell
- `shell_start` - Khởi động shell
- `shell_stop` - Dừng shell

## Testing

### Test API
```bash
python test_terminal_web.py
```

### Test Manual
1. Khởi động server: `python run.py`
2. Mở browser: `http://localhost:5000/shells`
3. Tạo shell mẫu và test tương tác

## Troubleshooting

### Lỗi thường gặp

1. **Port đã được sử dụng**
   ```
   Error: [Errno 98] Address already in use
   ```
   Giải pháp: Đổi port hoặc kill process đang sử dụng port

2. **Permission denied**
   ```
   Error: [Errno 13] Permission denied
   ```
   Giải pháp: Chạy với quyền sudo hoặc kiểm tra firewall

3. **pwncat không tìm thấy**
   ```
   FileNotFoundError: [Errno 2] No such file or directory: 'python'
   ```
   Giải pháp: Cài đặt pwncat: `pip install pwncat-cs`

### Debug Mode

Bật debug logging:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Security Considerations

- ⚠️ **Chỉ sử dụng trong môi trường test**
- ⚠️ **Không expose ra internet**
- ⚠️ **Sử dụng firewall để bảo vệ**
- ⚠️ **Logging tất cả hoạt động**

## Dependencies

- Flask
- Flask-SocketIO
- pwncat-cs
- psutil
- SQLAlchemy

## License

MIT License - Chỉ sử dụng cho mục đích giáo dục và test. 