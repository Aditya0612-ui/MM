from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp
import os
import uuid
import tempfile
from pathlib import Path
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

def sanitize_filename(filename):
    """Remove invalid characters from filename and ensure ASCII-safe"""
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u2013': '-',  # en dash
        '\u2014': '-',  # em dash
        '\u2018': "'",  # left single quote
        '\u2019': "'",  # right single quote
        '\u201C': '"',  # left double quote
        '\u201D': '"',  # right double quote
        '\u2026': '...',  # ellipsis
    }
    
    for unicode_char, ascii_char in replacements.items():
        filename = filename.replace(unicode_char, ascii_char)
    
    # Remove any remaining non-ASCII characters
    filename = filename.encode('ascii', 'ignore').decode('ascii')
    
    # Remove invalid characters for filenames
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Remove extra spaces
    filename = ' '.join(filename.split())
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    
    # Ensure filename is not empty
    if not filename:
        filename = 'video'
    
    return filename

@app.route('/api/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        video_url = data.get('url')
        download_type = data.get('type', 'single')  # 'single' or 'playlist'
        
        if not video_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # First, get video info to extract the title
        info_opts = {
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
        }
        
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_title = sanitize_filename(info.get('title', 'video'))
            duration = info.get('duration', 0)
        
        # Create a temporary file path (but don't create the file yet)
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f'ytdl_{uuid.uuid4().hex}.mp4')
        
        # Options for the downloader with multiple fallback formats
        # Supports very long videos (20+ hours) with audio
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            'outtmpl': temp_path,
            'noplaylist': True,
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'prefer_ffmpeg': True,
            'socket_timeout': 60,
            'retries': 15,
            'fragment_retries': 15,
            'http_chunk_size': 10485760,
            'extractor_retries': 5,
            'file_access_retries': 5,
            'ignoreerrors': False,
            'keepvideo': False,
            'no_warnings': False,
            'quiet': False,
            # YouTube bot detection bypass
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
        }
        
        # Download video to temp file
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        # Send the file directly to user
        def generate():
            try:
                with open(temp_path, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
            finally:
                # Clean up temp file after sending
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
        response = Response(generate(), mimetype='video/mp4')
        # Use ASCII-safe filename encoding for Content-Disposition
        safe_filename = video_title.encode('ascii', 'ignore').decode('ascii')
        if not safe_filename:
            safe_filename = 'video'
        response.headers['Content-Disposition'] = f'attachment; filename="{safe_filename}.mp4"'
        return response
    
    except Exception as e:
        # Clean up temp file on error
        try:
            if 'temp_path' in locals():
                os.unlink(temp_path)
        except:
            pass
        
        error_msg = str(e)
        # Provide user-friendly error messages
        if 'Sign in to confirm' in error_msg or 'not a bot' in error_msg:
            error_msg = 'YouTube bot detection triggered. Try again in a few minutes or try a different video.'
        elif 'HTTP Error 429' in error_msg:
            error_msg = 'YouTube rate limit reached. Please try again in a few minutes.'
        elif 'HTTP Error 403' in error_msg or 'Sign in to confirm your age' in error_msg:
            error_msg = 'This video is age-restricted or private and cannot be downloaded.'
        elif 'Video unavailable' in error_msg:
            error_msg = 'This video is unavailable or has been removed.'
        elif 'Requested format is not available' in error_msg:
            error_msg = 'The requested quality is not available for this video. Try a different video.'
        elif 'timeout' in error_msg.lower():
            error_msg = 'Download timeout. The video might be too long or connection is slow.'
        
        return jsonify({'error': error_msg}), 500

@app.route('/api/info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        video_url = data.get('url')
        info_type = data.get('type', 'single')  # 'single' or 'playlist'
        
        if not video_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist' if info_type == 'playlist' else False,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # Check if it's a playlist
            if info.get('_type') == 'playlist':
                entries = info.get('entries', [])
                return jsonify({
                    'type': 'playlist',
                    'title': info.get('title'),
                    'uploader': info.get('uploader'),
                    'video_count': len(entries),
                    'videos': [{
                        'title': entry.get('title'),
                        'url': entry.get('url'),
                        'id': entry.get('id'),
                    } for entry in entries[:10]]  # Return first 10 for preview
                })
            else:
                # Single video
                return jsonify({
                    'type': 'single',
                    'title': info.get('title'),
                    'thumbnail': info.get('thumbnail'),
                    'duration': info.get('duration'),
                    'uploader': info.get('uploader'),
                })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-playlist', methods=['POST'])
def download_playlist():
    try:
        data = request.get_json()
        playlist_url = data.get('url')
        
        if not playlist_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Create a temporary directory for playlist downloads
        temp_dir = tempfile.mkdtemp()
        
        # Options for playlist download with better error handling and audio support
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            'outtmpl': os.path.join(temp_dir, '%(playlist_index)s - %(title)s.%(ext)s'),
            'noplaylist': False,
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'prefer_ffmpeg': True,
            'ignoreerrors': True,
            'socket_timeout': 60,
            'retries': 15,
            'fragment_retries': 15,
            'http_chunk_size': 10485760,
            'extractor_retries': 5,
            'file_access_retries': 5,
            'max_downloads': 50,
            'keepvideo': False,
            # YouTube bot detection bypass
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'skip': ['hls', 'dash'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
        }
        
        # Download entire playlist
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=True)
            playlist_title = sanitize_filename(info.get('title', 'playlist'))
        
        # Create a zip file of all downloaded videos
        import zipfile
        zip_path = tempfile.NamedTemporaryFile(delete=False, suffix='.zip').name
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, arcname=file)
        
        # Clean up temp directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Send the zip file
        def generate():
            try:
                with open(zip_path, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
            finally:
                # Clean up zip file after sending
                try:
                    os.unlink(zip_path)
                except:
                    pass
        
        response = Response(generate(), mimetype='application/zip')
        # Use ASCII-safe filename encoding for Content-Disposition
        safe_filename = playlist_title.encode('ascii', 'ignore').decode('ascii')
        if not safe_filename:
            safe_filename = 'playlist'
        response.headers['Content-Disposition'] = f'attachment; filename="{safe_filename}.zip"'
        return response
    
    except Exception as e:
        # Clean up on error
        try:
            if 'temp_dir' in locals():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            if 'zip_path' in locals():
                os.unlink(zip_path)
        except:
            pass
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(debug=debug, port=port)
