from flask import Flask, render_template, request, send_file, jsonify
import os, shutil, socket, sys, subprocess
import yt_dlp

# ✅ yt-dlp অটো আপডেট
def auto_update_ytdlp():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        import yt_dlp.version
        print(f"✅ yt-dlp updated to version: {yt_dlp.version.__version__}")
    except Exception as e:
        print(f"⚠️ yt-dlp auto-update failed: {e}")

app = Flask(__name__)
last_files = {}

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

@app.route('/prepare', methods=['POST'])
def prepare():
    data = request.get_json()
    url = data.get("url")
    os.makedirs("downloads", exist_ok=True)

    format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    outtmpl = 'downloads/temp.%(ext)s'

    try:
        with yt_dlp.YoutubeDL({'format': format_str, 'outtmpl': outtmpl, 'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=True)
            mp4_file = ydl.prepare_filename(info)
            last_files['mp4'] = mp4_file

            # MP3 extract
            mp3_file = mp4_file.replace(".mp4", ".mp3")
            if shutil.which("ffmpeg"):
                os.system(f"ffmpeg -i \"{mp4_file}\" -vn -ab 192k \"{mp3_file}\"")
                last_files['mp3'] = mp3_file

        return jsonify({"ready": True})
    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"ready": False})

@app.route('/download')
def download():
    file_type = request.args.get("type")
    if file_type == "mp4":
        return send_file(last_files.get("mp4"), as_attachment=True)
    elif file_type == "mp3":
        return send_file(last_files.get("mp3"), as_attachment=True)
    elif file_type == "both":
        return "📦 MP4-MP3 combo download not implemented yet", 501
    return "Invalid type", 400

if __name__ == "__main__":
    auto_update_ytdlp()
    ip = get_ip()
    print(f"✅ Flask server running at: http://{ip}:5000")
    try:
        with open("/sdcard/flask_ip.txt", "w") as f:
            f.write(ip)
    except Exception as e:
        print(f"⚠️ Could not write IP to file: {e}")
    app.run(debug=True, host="0.0.0.0", port=5000)
