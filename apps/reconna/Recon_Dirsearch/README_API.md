# DirectoryScannerAPI - Documentation

## Overview
`DirectoryScannerAPI` là một class Python để quét thư mục và file trên website với khả năng real-time monitoring và control.

## Installation
```bash
pip install requests colorama
```

## Basic Usage

### 1. Import và Khởi tạo
```python
from main import DirectoryScannerAPI

# Khởi tạo scanner
scanner = DirectoryScannerAPI(
    base_url="http://example.com/",
    threads=50,
    timeout=10,
    callback=my_callback_function  # Optional
)
```

### 2. Callback Function (Optional)
```python
def my_callback(result):
    """Callback function được gọi mỗi khi có kết quả mới"""
    if result['found']:
        print(f"Found: {result['url']} (Status: {result['status_code']})")
    elif result['error']:
        print(f"Error: {result['path']} - {result['error']}")

# Sử dụng callback
scanner = DirectoryScannerAPI(
    base_url="http://example.com/",
    callback=my_callback
)
```

## API Methods

### Control Methods

#### `start_scan() -> bool`
Bắt đầu quét trong thread riêng
```python
success = scanner.start_scan()
if success:
    print("Scan started successfully")
```

#### `stop()`
Dừng quét
```python
scanner.stop()
```

#### `is_stopped() -> bool`
Kiểm tra trạng thái dừng
```python
if scanner.is_stopped():
    print("Scan has been stopped")
```

#### `wait_for_completion(timeout=None) -> bool`
Chờ quét hoàn thành
```python
# Chờ vô thời hạn
scanner.wait_for_completion()

# Chờ tối đa 30 giây
completed = scanner.wait_for_completion(timeout=30)
```

### Status Methods

#### `get_status() -> dict`
Lấy trạng thái hiện tại
```python
status = scanner.get_status()
print(f"Progress: {status['scanned_count']}/{status['total_paths']}")
print(f"Found URLs: {status['found_urls_count']}")
print(f"Progress: {status.get('progress_percent', 0)}%")
print(f"Rate: {status.get('rate', 0)} requests/second")
```

**Response format:**
```json
{
    "is_scanning": true,
    "stop_requested": false,
    "scanned_count": 150,
    "total_paths": 1000,
    "found_urls_count": 5,
    "results_count": 150,
    "elapsed_time": 3.45,
    "rate": 43.5,
    "progress_percent": 15.0
}
```

### Results Methods

#### `get_results(found_only=False) -> list`
Lấy kết quả quét
```python
# Lấy tất cả kết quả
all_results = scanner.get_results(found_only=False)

# Chỉ lấy URLs tìm thấy
found_results = scanner.get_results(found_only=True)
```

#### `get_found_urls() -> list`
Lấy chỉ URLs tìm thấy (shortcut)
```python
found_urls = scanner.get_found_urls()
for url in found_urls:
    print(f"Found: {url['url']} (Status: {url['status_code']})")
```

#### `get_summary() -> dict`
Lấy summary của scan
```python
summary = scanner.get_summary()
print(f"Target: {summary['target']}")
print(f"Total scanned: {summary['total_scanned']}")
print(f"Found URLs: {summary['found_urls']}")
print(f"Elapsed time: {summary['elapsed_time']}s")
print(f"Average rate: {summary['average_rate']} req/s")
```

### File Operations

#### `save_results(filename=None, found_only=True) -> str`
Lưu kết quả vào file
```python
# Lưu chỉ found URLs với tên file tự động
filename = scanner.save_results()

# Lưu tất cả kết quả với tên file tùy chỉnh
filename = scanner.save_results(
    filename="my_results.txt",
    found_only=False
)
```

## Complete Example

```python
from main import DirectoryScannerAPI
import time

def result_callback(result):
    """Callback function cho real-time updates"""
    if result['found']:
        print(f"✅ Found: {result['path']} (Status: {result['status_code']})")
    elif result['error']:
        print(f"❌ Error: {result['path']} - {result['error']}")

def main():
    # Khởi tạo scanner
    scanner = DirectoryScannerAPI(
        base_url="http://testphp.vulnweb.com/",
        threads=30,
        timeout=10,
        callback=result_callback
    )
    
    # Bắt đầu quét
    print("🚀 Starting directory scan...")
    scanner.start_scan()
    
    # Monitor progress real-time
    while scanner.is_scanning:
        status = scanner.get_status()
        print(f"\r📊 Progress: {status['scanned_count']}/{status['total_paths']} "
              f"({status.get('progress_percent', 0):.1f}%) - "
              f"Found: {status['found_urls_count']}", end='', flush=True)
        time.sleep(1)
    
    # Lấy kết quả
    found_urls = scanner.get_found_urls()
    print(f"\n🎉 Scan completed! Found {len(found_urls)} URLs")
    
    # Hiển thị kết quả
    for url in found_urls:
        print(f"  🔗 {url['url']} (Status: {url['status_code']})")
    
    # Lưu kết quả
    filename = scanner.save_results()
    print(f"💾 Results saved to: {filename}")
    
    # Lấy summary
    summary = scanner.get_summary()
    print(f"📈 Summary: {summary['total_scanned']} scanned, "
          f"{summary['elapsed_time']}s elapsed, "
          f"{summary['average_rate']} req/s")

if __name__ == "__main__":
    main()
```

## Web Integration Example

### JavaScript/HTML Integration
```html
<!DOCTYPE html>
<html>
<head>
    <title>Directory Scanner</title>
</head>
<body>
    <div id="scanner">
        <input type="text" id="url" placeholder="Enter target URL">
        <button onclick="startScan()">Start Scan</button>
        <div id="status"></div>
        <div id="results"></div>
    </div>

    <script>
        let scanId = null;
        
        async function startScan() {
            const url = document.getElementById('url').value;
            
            // Start scan via your backend API
            const response = await fetch('/api/scan/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url})
            });
            
            const data = await response.json();
            scanId = data.scan_id;
            
            // Monitor progress
            monitorProgress();
        }
        
        async function monitorProgress() {
            if (!scanId) return;
            
            const response = await fetch(`/api/scan/${scanId}/status`);
            const data = await response.json();
            
            const status = data.status;
            document.getElementById('status').innerHTML = 
                `Progress: ${status.scanned_count}/${status.total_paths} (${status.progress_percent}%)`;
            
            if (status.is_scanning) {
                setTimeout(monitorProgress, 1000);
            } else {
                // Get final results
                getResults();
            }
        }
        
        async function getResults() {
            const response = await fetch(`/api/scan/${scanId}/found`);
            const data = await response.json();
            
            let html = '<h3>Found URLs:</h3>';
            data.found_urls.forEach(url => {
                html += `<div>${url.url} (Status: ${url.status_code})</div>`;
            });
            
            document.getElementById('results').innerHTML = html;
        }
    </script>
</body>
</html>
```

### Python Backend Integration
```python
from flask import Flask, request, jsonify
from main import DirectoryScannerAPI
import threading
import uuid

app = Flask(__name__)

# Store active scans
active_scans = {}

@app.route('/api/scan/start', methods=['POST'])
def start_scan():
    data = request.get_json()
    url = data['url']
    
    # Generate scan ID
    scan_id = str(uuid.uuid4())
    
    # Create scanner
    scanner = DirectoryScannerAPI(base_url=url)
    active_scans[scan_id] = scanner
    
    # Start scan in background
    scanner.start_scan()
    
    return jsonify({
        'success': True,
        'scan_id': scan_id
    })

@app.route('/api/scan/<scan_id>/status')
def get_status(scan_id):
    scanner = active_scans.get(scan_id)
    if not scanner:
        return jsonify({'error': 'Scan not found'}), 404
    
    return jsonify({
        'success': True,
        'status': scanner.get_status()
    })

@app.route('/api/scan/<scan_id>/results')
def get_results(scan_id):
    scanner = active_scans.get(scan_id)
    if not scanner:
        return jsonify({'error': 'Scan not found'}), 404
    
    return jsonify({
        'success': True,
        'found_urls': scanner.get_found_urls()
    })

if __name__ == '__main__':
    app.run(debug=True)
```

## Error Handling

```python
try:
    scanner = DirectoryScannerAPI(base_url="invalid-url")
    scanner.start_scan()
except ValueError as e:
    print(f"Invalid URL: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Performance Tips

1. **Thread Count**: Tăng `threads` để quét nhanh hơn (50-100 threads)
2. **Timeout**: Giảm `timeout` để tránh chờ quá lâu (5-10 seconds)
3. **Callback**: Sử dụng callback để xử lý kết quả real-time
4. **Memory**: Monitor memory usage với large wordlists

## Supported URL Formats

- `http://example.com/`
- `https://example.com/`
- `example.com` (auto-adds http://)
- `192.168.1.1`
- `example.com:8080`
- `example.com/admin` 