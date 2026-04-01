from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
import threading
import time

app = Flask(__name__)
CORS(app)

downloads = {}
DOWNLOAD_DIR = '/tmp/downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_video(download_id, url, dtype):
    try:
        downloads[download_id]['status'] = 'downloading'
        downloads[download_id]['progress'] = 0
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    percent = float(d['_percent_str'].replace('%', '').strip())
                    downloads[download_id]['progress'] = percent
                except:
                    pass
        
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_DIR, f'{download_id}.%(ext)s'),
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
        }
        
        if dtype == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            ydl_opts['format'] = 'best[ext=mp4]/best'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloads[download_id]['filename'] = ydl.prepare_filename(info)
            downloads[download_id]['title'] = info.get('title', 'video')
        
        downloads[download_id]['status'] = 'completed'
        downloads[download_id]['progress'] = 100
        
    except Exception as e:
        downloads[download_id]['status'] = 'failed'
        downloads[download_id]['error'] = str(e)

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url')
    dtype = data.get('type', 'video')
    
    if not url:
        return jsonify({'success': False, 'message': 'URL required'})
    
    download_id = str(uuid.uuid4())
    downloads[download_id] = {
        'status': 'starting',
        'progress': 0,
        'url': url,
        'type': dtype
    }
    
    thread = threading.Thread(target=download_video, args=(download_id, url, dtype))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'download_id': download_id})

@app.route('/status/<download_id>')
def get_status(download_id):
    if download_id in downloads:
        return jsonify(downloads[download_id])
    return jsonify({'status': 'not_found'})

@app.route('/download/<download_id>')
def download_file(download_id):
    if download_id in downloads and downloads[download_id]['status'] == 'completed':
        filename = downloads[download_id]['filename']
        if os.path.exists(filename):
            return send_file(filename, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

@app.route('/cancel/<download_id>', methods=['POST'])
def cancel_download(download_id):
    if download_id in downloads:
        downloads[download_id]['status'] = 'cancelled'
    return jsonify({'success': True})

@app.route('/')
def home():
    return jsonify({'status': 'running', 'message': 'YT Downloader API'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
