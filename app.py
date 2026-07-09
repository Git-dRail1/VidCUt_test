from flask import Flask, request, jsonify, render_template_string, send_from_directory
import os
import subprocess
import json

app = Flask(__name__)

# Configure a local download folder
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Media Processor</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; background-color: #f4f7f6; color: #333; }
        .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        h2 { margin-top: 0; }
        label { font-weight: bold; display: block; margin-top: 15px; margin-bottom: 5px; }
        input[type="text"], select { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; font-size: 14px; }
        button { background-color: #10b981; color: white; padding: 14px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; width: 100%; margin-top: 20px; font-weight: bold; }
        button:hover { background-color: #059669; }
        .status-box { margin-top: 20px; padding: 15px; border-radius: 6px; display: none; background: #f0fdf4; border: 1px solid #bbf7d0; }
        #errorBox { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Direct Media Downloader & Converter</h2>
        <p>Paste the direct stream link grabbed by FetchV below.</p>
        
        <label for="streamUrl">FetchV Direct Link:</label>
        <input type="text" id="streamUrl" placeholder="https://.../stream.mp4 or .m3u8">
        
        <label for="targetRes">Target Resolution:</label>
        <select id="targetRes">
            <option value="1080">1080p (Full HD)</option>
            <option value="720">720p (HD)</option>
            <option value="480">480p (Standard)</option>
        </select>
        
        <button onclick="processMedia()">Process & Download</button>
        
        <div id="statusBox" class="status-box">Processing... Please wait. This can take a few minutes for conversion.</div>
        <div id="errorBox" class="status-box"></div>
    </div>

    <script>
        async function processMedia() {
            const url = document.getElementById('streamUrl').value;
            const res = document.getElementById('targetRes').value;
            const status = document.getElementById('statusBox');
            const errorBox = document.getElementById('errorBox');
            
            if(!url) return alert('Please paste a media URL.');
            
            status.style.display = 'block';
            status.innerText = "Analyzing stream and processing file on your server...";
            errorBox.style.display = 'none';
            
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url, resolution: res })
                });
                const data = await response.json();
                
                status.style.display = 'none';
                if(data.error) {
                    errorBox.innerText = data.error;
                    errorBox.style.display = 'block';
                } else {
                    status.innerHTML = `<strong>Success!</strong> ${data.message}<br><br><a href="${data.download_url}" target="_blank" style="color:#059669; font-weight:bold;">👉 Click Here to Download .MP4</a>`;
                    status.style.display = 'block';
                }
            } catch(e) {
                status.style.display = 'none';
                errorBox.innerText = "Server communication error.";
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
    
    if not stream_url:
        return jsonify({'error': 'Missing URL'}), 400
        
    output_filename = "processed_video.mp4"
    output_path = os.path.join(DOWNLOAD_FOLDER, output_filename)
    
    # Clean up old file if it exists
    if os.path.exists(output_path):
        os.remove(output_path)
        
    try:
        # Step 1: Probe the link using ffprobe to detect the source height (resolution)
        probe_cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0', 
            '-show_entries', 'stream=height', '-of', 'json', stream_url
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        probe_data = json.loads(probe_result.stdout)
        
        source_res = 0
        if 'streams' in probe_data and len(probe_data['streams']) > 0:
            source_res = int(probe_data['streams'][0].get('height', 0))
            
        print(f"Detected Source Resolution Height: {source_res}p. Target: {target_res}p.")

        # Step 2: Build FFmpeg Command based on resolution matchup
        # If resolutions match or probing fails, we copy the stream without re-encoding to save time/CPU
        if source_res == target_res or source_res == 0:
            print("Resolutions match or source resolution undetected. Downloading stream directly...")
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-i', stream_url, 
                '-c', 'copy', '-bsf:a', 'aac_adtstoasc', output_path
            ]
            msg = f"Downloaded directly matching your source height ({source_res}p)."
        else:
            print(f"Resolution mismatch. Transcoding stream to {target_res}p...")
            # Scale video height while maintaining original aspect ratio automatically
            scale_filter = f"scale=-2:{target_res}"
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-i', stream_url,
                '-vf', scale_filter, '-c:v', 'libx264', '-crf', '23', 
                '-c:a', 'aac', '-b:a', '128k', output_path
            ]
            msg = f"Transcoded successfully from {source_res}p down to your requested {target_res}p configuration."

        # Run compilation
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return jsonify({'error': f"FFmpeg processing failed: {result.stderr}"}), 500
            
        return jsonify({
            'message': msg,
            'download_url': f'/get-file/{output_filename}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-file/<filename>')
def get_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)