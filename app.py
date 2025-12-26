from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp
import os
import uuid
import tempfile
from pathlib import Path
import re

app = Flask(__name__)
CORS(app)

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    # Remove invalid characters for filenames
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
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
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_title = sanitize_filename(info.get('title', 'video'))
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_path = temp_file.name
        temp_file.close()
        
        # Options for the downloader - Force 1080p quality only
        ydl_opts = {
            'format': 'bestvideo[height=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]',
            'outtmpl': temp_path,
            'noplaylist': True,  # Single video only for this endpoint
            'merge_output_format': 'mp4',
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
        response.headers['Content-Disposition'] = f'attachment; filename="{video_title}.mp4"'
        return response
    
    except Exception as e:
        # Clean up temp file on error
        try:
            if 'temp_path' in locals():
                os.unlink(temp_path)
        except:
            pass
        return jsonify({'error': str(e)}), 500

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
        
        # Options for playlist download - Force 1080p quality
        ydl_opts = {
            'format': 'bestvideo[height=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]',
            'outtmpl': os.path.join(temp_dir, '%(playlist_index)s - %(title)s.%(ext)s'),
            'noplaylist': False,  # Enable playlist download
            'merge_output_format': 'mp4',
            'ignoreerrors': True,  # Continue on download errors
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
        response.headers['Content-Disposition'] = f'attachment; filename="{playlist_title}.zip"'
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
    app.run(debug=True, port=5000)
