# Shell Mode Improvements

## Vấn đề ban đầu
- Lỗi `__init__() got an unexpected keyword argument 'status'` khi tạo ShellConnection
- Không có logic tự động lấy LHOST/LPORT từ shell đã có
- UX chưa tốt khi chọn target

## Các cải tiến đã thực hiện

### 1. Sửa lỗi ShellConnection Constructor
**File:** `apps/home/routes.py`
- Loại bỏ tham số `status` khỏi constructor vì không được định nghĩa trong `__init__`
- Sử dụng `ShellConnection.create_connection()` method thay vì tạo object trực tiếp
- Thêm error handling và logging chi tiết

### 2. Logic tự động lấy LHOST/LPORT
**File:** `apps/home/routes.py`
- Kiểm tra shell đã có với cùng LHOST/LPORT
- Nếu không có, tìm shell đang listening và sử dụng LHOST/LPORT của shell đó
- Chỉ tạo shell mới khi không có shell nào đang listening

### 3. Cải thiện UX cho Target Selection
**File:** `templates/poc/use-poc.html`
- Thêm loading state khi gọi API
- Cải thiện error handling và user feedback
- Thêm visual feedback khi chọn target
- Thêm keyboard navigation (ESC để đóng dropdown)
- Escape special characters để tránh lỗi JavaScript

### 4. Tự động điền LHOST/LPORT
**File:** `templates/poc/use-poc.html`
- Thêm function `getExistingShellInfo()` để lấy thông tin shell đã có
- Thêm function `autoFillShellInfo()` để tự động điền LHOST/LPORT
- Tự động điền khi modal mở
- Cập nhật LHOST/LPORT nếu server trả về giá trị khác

### 5. Cải thiện Error Handling
- Thêm try-catch cho việc start shell
- Thêm traceback logging cho debugging
- Cải thiện error messages cho user
- Thêm validation cho LHOST/LPORT

## Các tính năng mới

### Auto Shell Detection
- Tự động phát hiện shell đang listening
- Sử dụng LHOST/LPORT của shell đã có
- Tạo shell mới chỉ khi cần thiết

### Enhanced Target Selection
- Loading indicator khi gọi API
- Error handling chi tiết
- Visual feedback khi chọn target
- Keyboard navigation

### Improved Shell Mode
- Tự động điền LHOST/LPORT
- Validation input
- Better error messages
- Auto-update LHOST/LPORT từ server response

## Testing Checklist
- [ ] Test tạo shell mới
- [ ] Test sử dụng shell đã có
- [ ] Test target selection với nhiều target
- [ ] Test error handling khi API fail
- [ ] Test auto-fill LHOST/LPORT
- [ ] Test validation LHOST/LPORT
- [ ] Test keyboard navigation

## Notes
- Shell sẽ được tạo với status LISTENING mặc định
- LHOST/LPORT sẽ được tự động điền từ shell đã có
- Target selection đã được cải thiện với better UX
- Error handling đã được enhanced với detailed logging 