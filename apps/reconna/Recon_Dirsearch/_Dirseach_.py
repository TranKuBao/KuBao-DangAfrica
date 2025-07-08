import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import Fore, Style, init
import os
import time
from datetime import datetime
import threading
from queue import Queue
import signal
import sys
import re
from urllib.parse import urlparse, urljoin
import json
from typing import Dict, List, Optional, Callable
from multiprocessing import Process, Queue as MPQueue

# Khởi tạo colorama để hiển thị màu sắc trên tất cả các hệ điều hành
init(autoreset=True)

class Recon_Directory:
    """
    Lớp API để quét thư mục và file trên website
    Hỗ trợ quét đa luồng, callback real-time, và lưu kết quả
    """
    
    def __init__(self, base_url: str, wordlist_file: Optional[str] = None, 
                 threads: int = 50, timeout: int = 10, 
                 callback: Optional[Callable] = None):
        """
        Khởi tạo Directory Scanner API
        
        Args:
            base_url (str): URL cơ sở để quét
            wordlist_file (str, optional): Đường dẫn đến file wordlist chứa các path cần quét
            threads (int): Số lượng thread đồng thời (mặc định: 50)
            timeout (int): Thời gian timeout cho mỗi request (giây)
            callback (callable, optional): Hàm callback để cập nhật real-time
        """
        # Chuẩn hóa và xác thực URL đầu vào
        self.base_url = self._normalize_url(base_url)
        self.wordlist_file = wordlist_file
        self.threads = threads
        self.timeout = timeout
        self.callback = callback
        
        # Lưu trữ kết quả quét
        self.results = []  # Tất cả kết quả (cả thành công và thất bại)
        self.found_urls = []  # Chỉ các URL được tìm thấy
        self.scanned_count = 0  # Số lượng path đã quét
        self.total_paths = 0  # Tổng số path cần quét
        self.start_time = None  # Thời điểm bắt đầu quét
        
        # Cờ điều khiển trạng thái
        self.is_scanning = False  # Đang quét hay không
        self.stop_requested = False  # Có yêu cầu dừng không
        self.stop_event = threading.Event()  # Event để dừng các thread
        
        # Xử lý đa luồng
        self.lock = threading.Lock()  # Lock để đồng bộ hóa
        self.result_queue = Queue()  # Queue để lưu kết quả
        self.scan_thread = None  # Thread chính thực hiện quét
        
        # Các mã trạng thái HTTP được coi là thành công
        self.success_codes = ['2', '3']  # 2xx và 3xx status codes
        
        # Tự động tìm file wordlist nếu không được cung cấp
        if not self.wordlist_file:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.wordlist_file = os.path.join(current_dir, "Dictionary", "dicc.txt")
        
        # Thiết lập signal handlers để dừng an toàn
        self._setup_signal_handlers()
    
    def _normalize_url(self, url_input: str) -> str:
        """
        Chuẩn hóa và xác thực URL đầu vào
        
        Args:
            url_input (str): URL thô từ người dùng
            
        Returns:
            str: URL đã được chuẩn hóa
            
        Raises:
            ValueError: Nếu URL không hợp lệ
        """
        # Loại bỏ khoảng trắng đầu cuối
        url_input = url_input.strip()
        
        # Kiểm tra nếu chỉ là hostname (không có protocol)
        if not url_input.startswith(('http://', 'https://')):
            # Kiểm tra nếu có chứa đường dẫn (có /)
            if '/' in url_input:
                # Giả sử http nếu không có protocol
                url_input = 'http://' + url_input
            else:
                # Chỉ là hostname, giả sử http
                url_input = 'http://' + url_input
        
        # Parse URL để xác thực
        try:
            parsed = urlparse(url_input)
            
            # Kiểm tra nếu có ít nhất scheme và netloc
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
            
            # Chuẩn hóa URL (loại bỏ dấu / cuối, đảm bảo format đúng)
            normalized_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # Thêm path nếu có (nhưng không có dấu / cuối)
            if parsed.path and parsed.path != '/':
                normalized_url += parsed.path.rstrip('/')
            
            return normalized_url
            
        except Exception as e:
            raise ValueError(f"Invalid URL '{url_input}': {str(e)}")
    
    def _test_connection(self) -> bool:
        """
        Kiểm tra kết nối đến URL đích
        
        Returns:
            bool: True nếu kết nối thành công, False nếu thất bại
        """
        try:
            # Thực hiện request GET để kiểm tra kết nối
            response = requests.get(self.base_url, timeout=self.timeout, allow_redirects=False)
            
            # Nếu nhận được status code hợp lệ thì coi như thành công
            if response.status_code in [200, 301, 302, 403, 401]:
                return True
            else:
                return True  # Vẫn tiếp tục, có thể là cố ý
                
        except requests.ConnectionError:
            # Lỗi kết nối
            return False
        except requests.Timeout:
            # Lỗi timeout
            return False
        except Exception:
            # Các lỗi khác
            return False
    
    def _setup_signal_handlers(self):
        """
        Thiết lập signal handlers để dừng an toàn khi nhận signal
        """
        def signal_handler(signum, frame):
            """
            Handler xử lý signal để dừng quét
            """
            self.stop()
        
        # Đăng ký signal handlers
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Signal kết thúc
    
    def _load_wordlist(self) -> List[str]:
        """
        Tải danh sách các path từ file wordlist
        
        Returns:
            list: Danh sách các path cần quét
            
        Raises:
            ValueError: Nếu không có file wordlist
            FileNotFoundError: Nếu file wordlist không tồn tại
            Exception: Nếu có lỗi khi đọc file
        """
        if self.wordlist_file is None:
            raise ValueError("Wordlist file path is not set")
            
        if not os.path.exists(self.wordlist_file):
            raise FileNotFoundError(f"Wordlist file '{self.wordlist_file}' not found.")
        
        try:
            # Đọc file wordlist và loại bỏ các dòng trống
            with open(self.wordlist_file, "r", encoding='utf-8') as f:
                paths = [line.strip() for line in f if line.strip()]
            return paths
            
        except Exception as e:
            raise Exception(f"Error reading wordlist file: {e}")
    
    def _check_url(self, path: str) -> Optional[Dict]:
        """
        Kiểm tra xem một path cụ thể có tồn tại trên đích không
        
        Args:
            path (str): Path cần kiểm tra
            
        Returns:
            dict: Thông tin kết quả hoặc None nếu đã dừng
        """
        # Kiểm tra nếu có yêu cầu dừng
        if self.is_stopped():
            return None
        
        # Tạo URL đầy đủ
        url = f"{self.base_url}/{path}"
        
        # Khởi tạo kết quả
        result = {
            'url': url,
            'path': path,
            'status_code': None,
            'response_time': None,
            'error': None,
            'found': False,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Đo thời gian response
            start_time = time.time()
            response = requests.get(url, timeout=self.timeout, allow_redirects=False)
            response_time = time.time() - start_time
            
            # Cập nhật thông tin kết quả
            result['status_code'] = response.status_code
            result['response_time'] = round(response_time, 3)
            
            # Kiểm tra nếu status code cho thấy thành công
            if str(response.status_code)[0] in self.success_codes:
                result['found'] = True
            
        except requests.RequestException as e:
            # Ghi lại lỗi nếu có
            result['error'] = str(e)
        
        # Cập nhật bộ đếm
        with self.lock:
            self.scanned_count += 1
        
        # Gọi callback nếu có
        if self.callback:
            try:
                self.callback(result)
            except Exception:
                pass  # Không để lỗi callback làm gián đoạn quét
        
        return result
    
    def _scan_worker(self):
        """
        Worker method để quét trong thread riêng biệt
        Đây là hàm chính thực hiện việc quét
        """
        try:
            # Kiểm tra kết nối trước
            if not self._test_connection():
                return
            
            # Tải wordlist
            paths = self._load_wordlist()
            self.total_paths = len(paths)
            self.start_time = time.time()
            
            # Bắt đầu quét với ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                # Gửi tất cả các task
                future_to_path = {executor.submit(self._check_url, path): path for path in paths}
                
                # Xử lý các task hoàn thành theo thời gian thực
                for future in as_completed(future_to_path):
                    # Kiểm tra nếu có yêu cầu dừng
                    if self.is_stopped():
                        break
                    
                    # Lấy kết quả
                    result = future.result()
                    if result is not None:
                        # Phân loại kết quả
                        if result['found']:
                            self.found_urls.append(result)
                        self.results.append(result)
            
        except Exception as e:
            print(f"Scan error: {e}")
        finally:
            # Đánh dấu kết thúc quét
            self.is_scanning = False
    
    def start_scan(self) -> bool:
        """
        Bắt đầu quá trình quét trong thread riêng biệt
        
        Returns:
            bool: True nếu bắt đầu quét thành công, False nếu đang quét
        """
        if self.is_scanning:
            return False
        
        # Khởi tạo lại các biến trạng thái
        self.is_scanning = True
        self.stop_requested = False
        self.stop_event.clear()
        self.scanned_count = 0
        self.results = []
        self.found_urls = []
        
        # Tạo và bắt đầu thread quét
        self.scan_thread = threading.Thread(target=self._scan_worker, daemon=True)
        self.scan_thread.start()
        return True
    
    def stop(self):
        """
        Dừng quá trình quét một cách an toàn
        """
        self.stop_requested = True
        self.stop_event.set()
    
    def is_stopped(self) -> bool:
        """
        Kiểm tra xem có yêu cầu dừng không
        
        Returns:
            bool: True nếu đã yêu cầu dừng
        """
        return self.stop_requested or self.stop_event.is_set()
    
    def get_status(self) -> Dict:
        """
        Lấy trạng thái quét hiện tại
        
        Returns:
            dict: Thông tin trạng thái hiện tại bao gồm:
                - is_scanning: Đang quét hay không
                - stop_requested: Có yêu cầu dừng không
                - scanned_count: Số path đã quét
                - total_paths: Tổng số path cần quét
                - found_urls_count: Số URL tìm thấy
                - results_count: Tổng số kết quả
                - elapsed_time: Thời gian đã trôi qua
                - rate: Tốc độ quét (path/giây)
                - progress_percent: Phần trăm hoàn thành
        """
        status = {
            'is_scanning': self.is_scanning,
            'stop_requested': self.stop_requested,
            'scanned_count': self.scanned_count,
            'total_paths': self.total_paths,
            'found_urls_count': len(self.found_urls),
            'results_count': len(self.results)
        }
        
        # Tính toán thời gian và tốc độ
        if self.start_time:
            elapsed_time = time.time() - self.start_time
            status['elapsed_time'] = round(elapsed_time, 2)
            if elapsed_time > 0:
                status['rate'] = round(self.scanned_count / elapsed_time, 1)
            
            # Tính phần trăm hoàn thành
            if self.total_paths > 0:
                status['progress_percent'] = round((self.scanned_count / self.total_paths) * 100, 1)
        
        return status
    
    def get_results(self, found_only: bool = False) -> List[Dict]:
        """
        Lấy kết quả quét
        
        Args:
            found_only (bool): Chỉ trả về các URL tìm thấy nếu True
            
        Returns:
            list: Danh sách kết quả
        """
        if found_only:
            return self.found_urls.copy()
        return self.results.copy()
    
    def get_found_urls(self) -> List[Dict]:
        """
        Lấy chỉ các URL được tìm thấy
        
        Returns:
            list: Danh sách các URL tìm thấy
        """
        return self.found_urls.copy()
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Chờ quét hoàn thành
        
        Args:
            timeout (float, optional): Thời gian tối đa chờ (giây)
            
        Returns:
            bool: True nếu quét hoàn thành, False nếu timeout hoặc dừng
        """
        if not self.is_scanning or self.scan_thread is None:
            return True
        
        # Chờ thread kết thúc
        if timeout:
            self.scan_thread.join(timeout=timeout)
            return not self.scan_thread.is_alive()
        else:
            self.scan_thread.join()
            return True
    
    def save_results(self, filename: Optional[str] = None, found_only: bool = True) -> str:
        """
        Lưu kết quả quét vào file
        
        Args:
            filename (str, optional): Tên file output (tự động tạo nếu không có)
            found_only (bool): Chỉ lưu các URL tìm thấy nếu True
            
        Returns:
            str: Tên file đã lưu kết quả
            
        Raises:
            Exception: Nếu có lỗi khi lưu file
        """
        # Tạo tên file tự động nếu không có
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scan_results_{timestamp}.txt"
        
        try:
            # Ghi kết quả vào file
            with open(filename, 'w', encoding='utf-8') as f:
                # Ghi header
                f.write(f"Directory Scan Results\n")
                f.write(f"Target: {self.base_url}\n")
                f.write(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Scanned: {self.scanned_count}\n")
                f.write(f"Found URLs: {len(self.found_urls)}\n")
                f.write("-" * 50 + "\n\n")
                
                # Ghi từng kết quả
                results_to_save = self.found_urls if found_only else self.results
                for result in results_to_save:
                    f.write(f"{result['url']} (Status: {result['status_code']})\n")
            
            return filename
            
        except Exception as e:
            raise Exception(f"Error saving results: {e}")
    
    def get_summary(self) -> Dict:
        """
        Lấy tóm tắt kết quả quét
        
        Returns:
            dict: Thông tin tóm tắt bao gồm:
                - target: URL đích
                - total_scanned: Tổng số đã quét
                - found_urls: Số URL tìm thấy
                - total_results: Tổng số kết quả
                - is_completed: Đã hoàn thành chưa
                - was_interrupted: Có bị gián đoạn không
                - elapsed_time: Thời gian thực hiện
                - average_rate: Tốc độ trung bình
        """
        summary = {
            'target': self.base_url,
            'total_scanned': self.scanned_count,
            'found_urls': len(self.found_urls),
            'total_results': len(self.results),
            'is_completed': not self.is_scanning,
            'was_interrupted': self.stop_requested
        }
        
        # Tính toán thời gian và tốc độ trung bình
        if self.start_time:
            elapsed_time = time.time() - self.start_time
            summary['elapsed_time'] = round(elapsed_time, 2)
            if elapsed_time > 0:
                summary['average_rate'] = round(self.scanned_count / elapsed_time, 1)
        
        return summary


# Hàm callback mẫu để cập nhật real-time
def print_result_callback(result: Dict):
    """
    Hàm callback mẫu để in kết quả theo thời gian thực
    Sử dụng màu sắc để phân biệt các loại kết quả
    
    Args:
        result (dict): Kết quả quét từ _check_url
    """
    if result['found']:
        # URL tìm thấy: màu xanh cho 200, vàng cho redirect
        status_color = Fore.GREEN if result['status_code'] == 200 else Fore.YELLOW
        print(f"{status_color}[+] Found: {result['path']} (Status: {result['status_code']}, Time: {result['response_time']}s){Style.RESET_ALL}")
    elif result['error']:
        # Có lỗi: màu đỏ
        print(f"{Fore.RED}[!] Error: {result['path']} - {result['error']}{Style.RESET_ALL}")


class DirsearchManager:
    _process = None
    _queue = None
    _result = []
    _is_running = False
    _wordlist_map = {
        'normal': os.path.join(os.path.dirname(__file__), 'Dictionary', 'normal.txt'),
        'deep': os.path.join(os.path.dirname(__file__), 'Dictionary', 'deep.txt'),
        'fast': os.path.join(os.path.dirname(__file__), 'Dictionary', 'fast.txt'),
        'default': os.path.join(os.path.dirname(__file__), 'Dictionary', 'default.txt'),
    }

    @staticmethod
    def _scan_worker(url, wordlist_file, queue):
        def callback(result):
            queue.put(result)
        scanner = Recon_Directory(url, wordlist_file=wordlist_file, callback=callback)
        scanner.start_scan()
        scanner.wait_for_completion()
        queue.put('DONE')

    @staticmethod
    def start_scan(url, mode):
        if DirsearchManager._process is not None and DirsearchManager._process.is_alive():
            return False, 'A scan is already running'
        wordlist_file = DirsearchManager._wordlist_map.get(mode, DirsearchManager._wordlist_map['default'])
        print(f"[DirsearchManager] Start scan: url={url}, mode={mode}, wordlist={wordlist_file}")
        DirsearchManager._queue = MPQueue()
        DirsearchManager._result = []
        DirsearchManager._process = Process(target=DirsearchManager._scan_worker, args=(url, wordlist_file, DirsearchManager._queue))
        DirsearchManager._process.start()
        DirsearchManager._is_running = True
        return True, 'Scan started'

    @staticmethod
    def get_scan_result():
        results = []
        if DirsearchManager._queue is not None:
            while not DirsearchManager._queue.empty():
                item = DirsearchManager._queue.get()
                if item == 'DONE':
                    DirsearchManager._is_running = False
                    break
                results.append(item)
        DirsearchManager._result.extend(results)
        return DirsearchManager._result

    @staticmethod
    def stop_scan():
        if DirsearchManager._process is not None and DirsearchManager._process.is_alive():
            DirsearchManager._process.terminate()
            DirsearchManager._process = None
            DirsearchManager._is_running = False
            return True, 'Scan stopped'
        else:
            return False, 'No scan is running'



