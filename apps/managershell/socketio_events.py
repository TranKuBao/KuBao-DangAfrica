"""
Socket.IO events cho terminal shell thật
"""
from flask_socketio import emit, join_room, leave_room
from flask import request
import logging
import fcntl
import struct
import termios
from apps.models import ShellConnection, ShellStatus, ShellType

# Setup logging
logger = logging.getLogger(__name__)

def register_terminal_events(socketio):
    """Đăng ký các event Socket.IO cho terminal"""
    
    # Import shell_manager từ pwncat
    from apps.managershell.pwncat import shell_manager
    
    @socketio.on('connect')
    def handle_connect():
        """Khi client kết nối"""
        logger.info(f"Client connected: {request.sid}")
        emit('connected', {'status': 'connected'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Khi client ngắt kết nối"""
        logger.info(f"Client disconnected: {request.sid}")
        # Rời khỏi tất cả room
        for room in socketio.server.rooms(request.sid):
            if room != request.sid:
                leave_room(room)

    @socketio.on('join_shell')
    def handle_join_shell(data):
        """Tham gia room của shell cụ thể"""
        shell_id = data.get('shell_id')
        if shell_id:
            join_room(shell_id)
            logger.info(f"Client {request.sid} joined shell room: {shell_id}")
            emit('joined_shell', {'shell_id': shell_id, 'status': 'joined'})

    @socketio.on('leave_shell')
    def handle_leave_shell(data):
        """Rời khỏi room của shell"""
        shell_id = data.get('shell_id')
        if shell_id:
            leave_room(shell_id)
            logger.info(f"Client {request.sid} left shell room: {shell_id}")
            emit('left_shell', {'shell_id': shell_id, 'status': 'left'})

    @socketio.on('terminal_input')
    def handle_terminal_input(data):
        """Xử lý input từ terminal web"""
        shell_id = data.get('shell_id')
        input_data = data.get('input', '')
        
        if not shell_id or not input_data:
            emit('error', {'message': 'Missing shell_id or input data'})
            return
        
        logger.info(f"Terminal input for shell {shell_id}: {repr(input_data)}")
        
        # Gửi input tới shell thật
        success = shell_manager.send_input_to_shell(shell_id, input_data)
        
        if success:
            emit('input_sent', {'shell_id': shell_id, 'status': 'sent'})
        else:
            emit('error', {'message': f'Failed to send input to shell {shell_id}'})

    @socketio.on('shell_start')
    def handle_shell_start(data):
        """Khởi động shell"""
        shell_id = data.get('shell_id')
        if not shell_id:
            emit('error', {'message': 'Missing shell_id'})
            return
        
        logger.info(f"Starting shell: {shell_id}")
        
        # Lấy thông tin shell từ database
        shell = ShellConnection.get_by_id(shell_id)
        
        if not shell:
            emit('error', {'message': f'Shell {shell_id} not found'})
            return
        
        try:
            if shell.shell_type == ShellType.REVERSE:
                # Khởi động listener
                new_shell_id = shell_manager.start_listener(
                    shell.local_port, 
                    name=shell_id,
                    url=shell.url,
                    listen_ip=shell.local_ip or '0.0.0.0'
                )
            elif shell.shell_type == ShellType.BIND:
                # Kết nối bind shell
                new_shell_id = shell_manager.connect_shell(
                    shell.remote_ip,
                    shell.remote_port,
                    name=shell_id,
                    url=shell.url
                )
            else:
                emit('error', {'message': f'Unsupported shell type: {shell.shell_type}'})
                return
            
            if new_shell_id:
                emit('shell_started', {'shell_id': shell_id, 'status': 'started'})
            else:
                emit('error', {'message': f'Failed to start shell {shell_id}'})
                
        except Exception as e:
            logger.error(f"Error starting shell {shell_id}: {e}")
            emit('error', {'message': f'Error starting shell: {str(e)}'})

    @socketio.on('shell_stop')
    def handle_shell_stop(data):
        """Dừng shell"""
        shell_id = data.get('shell_id')
        if not shell_id:
            emit('error', {'message': 'Missing shell_id'})
            return
        
        logger.info(f"Stopping shell: {shell_id}")
        
        success = shell_manager.close_shell(shell_id)
        
        if success:
            emit('shell_stopped', {'shell_id': shell_id, 'status': 'stopped'})
        else:
            emit('error', {'message': f'Failed to stop shell {shell_id}'})

    @socketio.on('terminal_resize')
    def handle_terminal_resize(data):
        """Xử lý resize terminal"""
        shell_id = data.get('shell_id')
        cols = data.get('cols', 80)
        rows = data.get('rows', 24)
        
        if not shell_id:
            emit('error', {'message': 'Missing shell_id'})
            return
        
        logger.info(f"Terminal resize for shell {shell_id}: {cols}x{rows}")
        
        # Gửi lệnh resize tới shell (nếu cần)
        # Trong pwncat, có thể cần gửi escape sequence để resize
        resize_cmd = f"\x1b[8;{rows};{cols}t"
        shell_manager.send_input_to_shell(shell_id, resize_cmd)
        
        emit('resize_sent', {'shell_id': shell_id, 'cols': cols, 'rows': rows})