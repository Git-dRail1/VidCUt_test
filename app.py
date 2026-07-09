from flask import Flask, request, jsonify, render_template_string
import yt_dlp
import os

app = Flask(__name__)

# Simple HTML UI embedded for easy single-file deployment or reference
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web Media Extractor</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background-color: #f9f9f9; color: #333; }
        .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { margin-top: 0; color: #111; }
        input[type="text"] { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        button { background-color: #0070f3; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; width: 100%; }
        button:hover { background-color: #0051a8; }
        .result-box { margin-top: 20px; display: none; }
        .stream-item { background: #f0f0f0; padding: 12px; margin: 8px 0; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }
        .stream-link { background: #0070f3; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 14px; }
        #loading { display: none; color: #666; font-style: italic; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Media Stream Extractor</h1>
        <p>Enter a video page URL to extract direct download links or HLS (.m3u8) playlists.</p>
        <input type="text" id="videoUrl" placeholder="https://example.com/video-page">
        <button onclick="extractMedia()">Extract Links</button>
        <div id="loading">Analyzing page and extracting streams...</div>
        
        <div id="resultBox" class="result-box">
            <h3>Available Streams Found:</h3>
            <div id="linksContainer"></div>
        </div>
    </div>

    <script>
        async function extractMedia() {
            const urlInput = document.getElementById('videoUrl').value;
            const loading = document.getElementById('loading');
            const resultBox = document.getElementById('resultBox');
            const container = document.getElementById('linksContainer');
            
            if (!urlInput) return alert('Please enter a URL');
            
            loading.style.display = 'block';
            resultBox.style.display = 'none';
            container.innerHTML = '';

            try {
                const response = await fetch('/extract', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: urlInput })
                });
                const data = await response.json();
                
                loading.style.display = 'none';
                
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }
                
                if (data.formats.length === 0) {
                    container.innerHTML = '<p>No direct media formats detected.</p>';
                } else {
                    data.formats.forEach(format => {
                        const div = document.createElement('div');
                        div.className = 'stream-item';
                        div.innerHTML = `
                            <div>
                                <strong>[${format.ext.toUpperCase()}]</strong> - ${format.resolution || 'Audio/Unknown'} (${format.note || 'Direct Link'})
                            </div>
                            <a href="${format.url}" target="_blank" rel="noopener noreferrer" class="stream-link">Open / Download</a>
                        `;
                        container.appendChild(div);
                    });
                }
                resultBox.style.display = 'block';
            } catch (err) {
                loading.style.display = 'none';
                alert('Failed to connect to backend extractor.');
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/extract', methods=['POST'])
def extract():
    data = request.get_json()
    target_url = data.get('url')
    
    if not target_url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = {
        'extract_flat': False,
        'skip_download': True,  # We only want the links, not to store the gigabytes of video on your server
    }

    try {
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            
            formats_found = []
            if 'formats' in info:
                for f in info['formats']:
                    # Filter for typical web layouts or manifest streams
                    formats_found.append({
                        'url': f.get('url'),
                        'ext': f.get('ext', 'unknown'),
                        'resolution': f.get('format_note') or f.get('resolution'),
                        'note': 'HLS/Manifest' if 'm3u8' in f.get('url', '') else 'Direct File'
                    })
            
            return jsonify({
                'title': info.get('title', 'Unknown Title'),
                'formats': formats_found[:20]  # Cap at top 20 variants to keep UI clean
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)