from flask import Flask, render_template, request, send_file
import os
import shutil
import socket
import sys
import subprocess

# ✅ রানটাইমে yt-dlp অটো আপডেট
def auto_update_ytdlp():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        import yt_dlp
        print(f"✅ yt-dlp updated to version: {yt_dlp.__version__}")
    except Exception as e:
        print(f"⚠️ yt-dlp auto-update failed: {e}")

app = Flask(__name__)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/download', methods=['POST'])
def download_video():
    import yt_dlp   # ✅ আপডেটের পর নতুন ভার্সন ইমপোর্ট হবে
    url = request.form['url']
    format_type = request.form['format']  # 'mp4', 'm4a', 'mp3'

    format_map = {
        'mp4': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'm4a': 'bestaudio[ext=m4a]/bestaudio',
        'mp3': 'bestaudio[ext=webm]/bestaudio',
    }

    ydl_opts = {
        'format': format_map.get(format_type, 'best'),
        'outtmpl': f'downloads/%(title)s.{format_type}',
        'postprocessors': []
    }

    if format_type == 'mp3':
        if shutil.which("ffmpeg"):
            ydl_opts['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            })
        else:
            format_type = 'webm'
            ydl_opts['format'] = format_map['mp3']
            ydl_opts['outtmpl'] = f'downloads/%(title)s.webm'

    os.makedirs('downloads', exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        if format_type == 'mp3':
            temp_file = ydl.prepare_filename(info) + ".mp3"
            final_file = temp_file.replace(".mp3.mp3", ".mp3")
            if os.path.exists(temp_file):
                os.rename(temp_file, final_file)
                filename = final_file
            else:
                return f"Download failed: {temp_file} not found", 500
        else:
            filename = ydl.prepare_filename(info)

    if os.path.exists(filename):
        return send_file(filename, as_attachment=True)
    else:
        return f"Download failed: {filename} not found", 500

if __name__ == "__main__":
    # ✅ প্রথমেই yt-dlp আপডেট হবে
    auto_update_ytdlp()

    ip = get_ip()
    print(f"✅ Flask server running at: http://{ip}:5000")

    try:
        with open("/sdcard/flask_ip.txt", "w") as f:
            f.write(ip)
    except Exception as e:
        print(f"⚠️ Could not write IP to file: {e}")

    app.run(debug=True, host="0.0.0.0", port=5000)
