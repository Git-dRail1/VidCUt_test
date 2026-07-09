from flask import Flask, request, jsonify, render_template_string, send_from_directory
import os
import subprocess
import json
import re

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authenticated Media Processor</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; background-color: #f4f7f6; color: #333; }
        .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        h2 { margin-top: 0; color: #111; }
        p { color: #666; font-size: 14px; margin-bottom: 20px; }
        label { font-weight: bold; display: block; margin-top: 15px; margin-bottom: 5px; }
        input[type="text"], select, textarea { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; font-size: 14px; background-color: #fff; font-family: inherit; }
        textarea { height: 80px; resize: vertical; }
        button { background-color: #10b981; color: white; padding: 14px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; width: 100%; margin-top: 25px; font-weight: bold; }
        button:hover { background-color: #059669; }
        .status-box { margin-top: 20px; padding: 15px; border-radius: 6px; display: none; background: #f0fdf4; border: 1px solid #bbf7d0; font-size: 14px; line-height: 1.5; word-break: break-all; }
        #errorBox { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
        .download-btn { display: inline-block; background-color: #0284c7; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Direct Media Downloader</h2>
        <p>Paste the direct stream link grabbed by FetchV. If you encounter a 404 error, supply your browser session headers below.</p>
        
        <label for="streamUrl">FetchV Direct Link:</label>
        <input type="text" id="streamUrl" placeholder="https://.../stream.vid or .mp4">
        
        <label for="targetRes">Target Resolution Selection:</label>
        <select id="targetRes">
            <option value="1080">1080p (Full HD)</option>
            <option value="720">720p (HD)</option>
            <option value="480">480p (Standard)</option>
        </select>

        <label for="customHeaders">Custom Headers / Cookie (Optional - fix for 404):</label>
        <textarea id="customHeaders" placeholder="User-Agent: Mozilla/5.0...&#10;Cookie: session_id=abc..."></textarea>
        
        <button onclick="processMedia()">Process & Download</button>
        
        <div id="statusBox" class="status-box">Processing...</div>
        <div id="errorBox" class="status-box"></div>
    </div>

    <script>
        async function processMedia() {
            const url = document.getElementById('streamUrl').value;
            const res = document.getElementById('targetRes').value;
            const headersText = document.getElementById('customHeaders').value;
            const status = document.getElementById('statusBox');
            const errorBox = document.getElementById('errorBox');
            
            if(!url) return alert('Please enter a stream link.');
            
            status.style.display = 'block';
            status.innerText = "Processing video on your server...";
            errorBox.style.display = 'none';
            
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url, resolution: res, headers: headersText })
                });
                const data = await response.json();
                
                status.style.display = 'none';
                if(data.error) {
                    errorBox.innerText = data.error;
                    errorBox.style.display = 'block';
                } else {
                    status.innerHTML = `<strong>Success!</strong><br>${data.message}<br><br><a href="${data.download_url}" class="download-btn" target="_blank">📥 Download .MP4 File</a>`;
                    status.style.display = 'block';
                }
            } catch(e) {
                status.style.display = 'none';
                errorBox.innerText = "Communication error with server.";
                errorBox.style.display = 'block';
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process', methods=['POST'])
def process():
    data = request.get_json()
    stream_url = data.get('url')
    target_res = int(data.get('resolution', 1080))
    raw_headers = data.get('headers', '')
    
    if not stream_url:
        return jsonify({'error': 'Missing link URL'}), 400
        
    output_filename = "processed_video.mp4"
    output_path = os.path.join(DOWNLOAD_FOLDER, output_filename)
    
    if os.path.exists(output_path):
        os.remove(output_path)

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

    # Add standard User-Agent and connection attributes
    header_lines.append(f"User-Agent: {user_agent}")
    if cookie_str:
        header_lines.append(f"Cookie: {cookie_str}")
    
    # Format headers for FFmpeg input parameters
    ffmpeg_headers = "\r\n".join(header_lines) + "\r\n"
        
    try:
        # Check source profile with custom validation headers
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
            
        print(f"Source height: {source_res}p. Target choice: {target_res}p.")

        # Build execution pipeline with authorization headers passed inline
        if source_res == target_res or source_res == 0:
            ffmpeg_cmd = [
                'ffmpeg', '-y', 
                '-headers', ffmpeg_headers,
                '-i', stream_url, 
                '-c', 'copy', '-bsf:a', 'aac_adtstoasc', output_path
            ]
            msg = "Downloaded file cleanly without re-encoding processing."
        else:
            scale_filter = f"scale=-2:{target_res}"
            ffmpeg_cmd = [
                'ffmpeg', '-y', 
                '-headers', ffmpeg_headers,
                '-i', stream_url,
                '-vf', scale_filter, '-c:v', 'libx264', '-crf', '23', 
                '-c:a', 'aac', '-b:a', '128k', output_path
            ]
            msg = f"Transcoded and scaled down directly to {target_res}p."

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            # Clean up the output string to return the precise error root
            err_output = result.stderr if result.stderr else "Unknown error encountered."
            return jsonify({'error': f"FFmpeg Error:\n{err_output[-500:]}"}), 500
            
        return jsonify({
            'message': msg,
            'download_url': f'/get-file/<filename>'
        })

    except Exception as e:
        return jsonify({'error': f"Runtime Error: {str(e)}"}), 500

@app.route('/get-file/<filename>')
def get_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)