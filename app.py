from flask import Flask, request, jsonify, render_template_string, send_from_directory
import os
import subprocess
import json
import shutil

app = Flask(__name__)

# Configure a dedicated local download directory
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authenticated Media Processor & Cutter</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; background-color: #f4f7f6; color: #333; }
        .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px; }
        h2 { margin-top: 0; color: #111; }
        p { color: #666; font-size: 14px; margin-bottom: 20px; }
        label { font-weight: bold; display: block; margin-top: 15px; margin-bottom: 5px; }
        input[type="text"], select, textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; font-size: 14px; background-color: #fff; font-family: inherit; }
        textarea { height: 80px; resize: vertical; }
        
        /* Time Split Grid */
        .time-group { display: flex; gap: 15px; margin-top: 5px; }
        .time-field { flex: 1; }
        
        .btn-group { display: flex; gap: 10px; margin-top: 25px; }
        button { color: white; padding: 14px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold; transition: background 0.2s; }
        .btn-process { background-color: #10b981; flex: 2; }
        .btn-process:hover { background-color: #059669; }
        .btn-clear { background-color: #ef4444; flex: 1; font-size: 14px; }
        .btn-clear:hover { background-color: #dc2626; }
        .status-box { margin-top: 20px; padding: 15px; border-radius: 6px; display: none; background: #f0fdf4; border: 1px solid #bbf7d0; font-size: 14px; line-height: 1.5; word-break: break-all; }
        #errorBox { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
        
        .download-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; margin-top: 15px; border-radius: 8px; }
        .download-link-btn { display: inline-block; background-color: #0284c7; color: white; padding: 8px 16px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 5px; margin-right: 10px; font-size: 13px; }
        .download-link-btn:hover { background-color: #0369a1; }
        .download-link-btn.cut-btn { background-color: #7c3aed; }
        .download-link-btn.cut-btn:hover { background-color: #6d28d9; }
        
        /* Saved Files Section Styling */
        .library-box { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        .library-box h3 { margin-top: 0; color: #222; border-bottom: 2px solid #f0fdf4; padding-bottom: 8px; }
        .file-list { list-style: none; padding: 0; margin: 0; }
        .file-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #eee; font-size: 14px; }
        .file-item:last-child { border-bottom: none; }
        .file-link { color: #0284c7; font-weight: bold; text-decoration: none; }
        .file-link:hover { text-decoration: underline; }
        .no-files { color: #888; font-style: italic; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Direct Media Downloader & Cutter</h2>
        <p>Paste the link grabbed by FetchV, configure your resolution, and optionally specify timestamps below to cut a segment from the video.</p>
        
        <label for="streamUrl">FetchV Direct Link:</label>
        <input type="text" id="streamUrl" placeholder="https://.../stream.vid or .mp4">

        <label for="customFilename">Save File As (Custom Name):</label>
        <input type="text" id="customFilename" placeholder="my_awesome_video (Do not include .mp4)">
        
        <label for="targetRes">Target Resolution Selection:</label>
        <select id="targetRes">
            <option value="1080">1080p (Full HD)</option>
            <option value="720">720p (HD)</option>
            <option value="480" selected>480p (Standard)</option>
        </select>

        <!-- Video Trimming Segment -->
        <div class="time-group">
            <div class="time-field">
                <label for="startTime">Start Time (Optional):</label>
                <input type="text" id="startTime" placeholder="hh:mm:ss" value="00:00:00">
            </div>
            <div class="time-field">
                <label for="endTime">End Time (Optional):</label>
                <input type="text" id="endTime" placeholder="hh:mm:ss"value="00:00:01">
            </div>
        </div>

        <label for="customHeaders">Custom Headers / Cookie (Optional - fix for 404):</label>
        <textarea id="customHeaders" placeholder="User-Agent: Mozilla/5.0...&#10;Cookie: session_id=abc..."></textarea>
        
        <div class="btn-group">
            <button class="btn-process" onclick="processMedia()">Process & Download</button>
            <button class="btn-clear" onclick="clearDownloads()">Erase Directory</button>
        </div>
        
        <div id="statusBox" class="status-box">Processing...</div>
        <div id="errorBox" class="status-box"></div>
    </div>

    <!-- Persistent Saved Files Display -->
    <div class="library-box">
        <h3>Saved Video Files On Server</h3>
        <ul id="fileList" class="file-list">
            <!-- Files loaded via JavaScript dynamically -->
        </ul>
    </div>

    <script>
        window.addEventListener('DOMContentLoaded', refreshFileList);

        async function refreshFileList() {
            const listContainer = document.getElementById('fileList');
            try {
                const response = await fetch('/list-files');
                const files = await response.json();
                
                if (files.length === 0) {
                    listContainer.innerHTML = '<li class="no-files">No media files currently stored on the server.</li>';
                    return;
                }
                
                listContainer.innerHTML = files.map(file => `
                    <li class="file-item">
                        <span>📄 ${file.name} <small style="color:#888;">(${file.size})</small></span>
                        <a href="${file.url}" class="file-link" target="_blank">Download</a>
                    </li>
                `).join('');
            } catch(e) {
                listContainer.innerHTML = '<li class="no-files" style="color:#ef4444;">Failed to read download folder index.</li>';
            }
        }

        async function processMedia() {
            const url = document.getElementById('streamUrl').value;
            const res = document.getElementById('targetRes').value;
            const filename = document.getElementById('customFilename').value;
            const startTime = document.getElementById('startTime').value;
            const endTime = document.getElementById('endTime').value;
            const headersText = document.getElementById('customHeaders').value;
            const status = document.getElementById('statusBox');
            const errorBox = document.getElementById('errorBox');
            
            if(!url) return alert('Please enter a stream link.');
            
            status.style.display = 'block';
            status.innerText = "Processing video assets on your server. This will take a few minutes if re-encoding or clipping...";
            errorBox.style.display = 'none';
            
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        url: url, 
                        resolution: res, 
                        filename: filename, 
                        start_time: startTime, 
                        end_time: endTime, 
                        headers: headersText 
                    })
                });
                const data = await response.json();
                
                status.style.display = 'none';
                if(data.error) {
                    errorBox.innerText = data.error;
                    errorBox.style.display = 'block';
                } else {
                    let htmlResponse = `<strong>Success!</strong><br>${data.message}<br><div class="download-box">`;
                    htmlResponse += `<a href="${data.download_url}" class="download-link-btn" target="_blank">📥 Full Video (.mp4)</a>`;
                    
                    if(data.cut_url) {
                        htmlResponse += `<a href="${data.cut_url}" class="download-link-btn cut-btn" target="_blank">✂️ Cut Clip (.mp4)</a>`;
                    }
                    htmlResponse += `</div>`;
                    
                    status.innerHTML = htmlResponse;
                    status.style.display = 'block';
                    refreshFileList();
                }
            } catch(e) {
                status.style.display = 'none';
                errorBox.innerText = "Communication error with server.";
                errorBox.style.display = 'block';
            }
        }

        async function clearDownloads() {
            if(!confirm("Are you sure you want to completely erase all files inside your downloads folder?")) return;
            try {
                const response = await fetch('/clear-storage', { method: 'POST' });
                const data = await response.json();
                alert(data.message || data.error);
                refreshFileList();
            } catch(e) {
                alert("Failed to communicate clear command to server.");
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/list-files', methods=['GET'])
def list_files():
    files_info = []
    try:
        if os.path.exists(DOWNLOAD_FOLDER):
            for filename in os.listdir(DOWNLOAD_FOLDER):
                file_path = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(file_path) and filename.endswith('.mp4'):
                    bytes_size = os.path.getsize(file_path)
                    size_mb = bytes_size / (1024 * 1024)
                    files_info.append({
                        'name': filename,
                        'size': f"{size_mb:.1f} MB",
                        'url': f'/get-file/{filename}'
                    })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(files_info)

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    stream_url = data.get('url')
    target_res = int(data.get('resolution', 1080))
    user_filename = data.get('filename', '').strip()
    start_time = data.get('start_time', '').strip()
    end_time = data.get('end_time', '').strip()
    raw_headers = data.get('headers', '')
    
    if not stream_url:
        return jsonify({'error': 'Missing link URL'}), 400

    # Sanitize custom filenames
    if user_filename:
        user_filename = os.path.splitext(user_filename)[0]
        user_filename = "".join([c for c in user_filename if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).strip()
        base_name = user_filename
    else:
        base_name = "processed_video"
        
    full_filename = f"{base_name}.mp4"
    cut_filename = f"Cut_{base_name}.mp4"
    
    full_output_path = os.path.join(DOWNLOAD_FOLDER, full_filename)
    cut_output_path = os.path.join(DOWNLOAD_FOLDER, cut_filename)
    
    # Remove older files if they exist to protect memory footprint
    for path in [full_output_path, cut_output_path]:
        if os.path.exists(path):
            os.remove(path)

    # Validate timestamp format configuration (hh:mm:ss)
    time_regex = r'^\d{2}:\d{2}:\d{2}$'
    run_cutting = False
    if start_time or end_time:
        if (start_time and not json.dumps(start_time).match(time_regex)) or (end_time and not json.dumps(end_time).match(time_regex)):
            # Fallback text check logic
            import re
            if (start_time and not re.match(time_regex, start_time)) or (end_time and not re.match(time_regex, end_time)):
                return jsonify({'error': 'Timestamps must use strict HH:MM:SS layout configurations.'}), 400
        run_cutting = True

    # Compile custom browser headers to feed into FFmpeg
    header_lines = []
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    cookie_str = ""

    if raw_headers.strip():
        for line in raw_headers.split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                k, v = k.strip(), v.strip()
                if k.lower() == 'user-agent':
                    user_agent = v
                elif k.lower() == 'cookie':
                    cookie_str = v
                else:
                    header_lines.append(f"{k}: {v}")

    header_lines.append(f"User-Agent: {user_agent}")
    if cookie_str:
        header_lines.append(f"Cookie: {cookie_str}")
    
    ffmpeg_headers = "\r\n".join(header_lines) + "\r\n"
        
    try:
        # Step 1: Probe dimensions via ffprobe
        probe_cmd = [
            'ffprobe', '-v', 'error', 
            '-headers', ffmpeg_headers,
            '-select_streams', 'v:0', '-show_entries', 'stream=height', 
            '-of', 'json', stream_url
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        
        source_res = 0
        if probe_result.returncode == 0 and probe_result.stdout.strip():
            try:
                probe_data = json.loads(probe_result.stdout)
                source_res = int(probe_data['streams'][0].get('height', 0))
            except:
                pass

        # Step 2: Download complete stream base file
        if source_res == target_res or source_res == 0:
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-headers', ffmpeg_headers, '-i', stream_url, 
                '-c', 'copy', '-bsf:a', 'aac_adtstoasc', full_output_path
            ]
        else:
            scale_filter = f"scale=-2:{target_res}"
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-headers', ffmpeg_headers, '-i', stream_url,
                '-vf', scale_filter, '-c:v', 'libx264', '-crf', '23', 
                '-c:a', 'aac', '-b:a', '128k', full_output_path
            ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({'error': f"Full download stage failed:\n{result.stderr[-400:]}"}), 500

        # Step 3: Run sub-cutting phase if user supplied timestamps
        cut_url_route = None
        msg = f"Full video processed and saved as '{full_filename}'."
        
        if run_cutting:
            # We cut from the local saved file to make the extraction super accurate and lightning fast
            cut_cmd = ['ffmpeg', '-y', '-i', full_output_path]
            if start_time:
                cut_cmd.extend(['-ss', start_time])
            if end_time:
                cut_cmd.extend(['-to', end_time])
                
            # Copy codecs instantly without re-encoding since resolution scaling is already handled
            cut_cmd.extend(['-c', 'copy', cut_output_path])
            
            cut_result = subprocess.run(cut_cmd, capture_output=True, text=True)
            if cut_result.returncode == 0:
                cut_url_route = f"/get-file/{cut_filename}"
                msg += f" Extracted sub-clip and saved as '{cut_filename}'."
            else:
                msg += " (Trimming execution stage threw an error, check formatting parameters)."

        return jsonify({
            'message': msg,
            'filename': full_filename,
            'download_url': f'/get-file/{full_filename}',
            'cut_url': cut_url_route
        })

    except Exception as e:
        return jsonify({'error': f"Runtime pipeline error: {str(e)}"}), 500

@app.route('/get-file/<filename>')
def get_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

@app.route('/clear-storage', methods=['POST'])
def clear_storage():
    try:
        if os.path.exists(DOWNLOAD_FOLDER):
            shutil.rmtree(DOWNLOAD_FOLDER)
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
        return jsonify({'message': 'Downloads directory safely erased.'})
    except Exception as e:
        return jsonify({'error': f'Wipe execution failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)