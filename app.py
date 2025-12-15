from flask import Flask, render_template, request, send_file, jsonify
import os, shutil, subprocess
import yt_dlp

app = Flask(__name__)
last_files = {}

# ✅ yt-dlp auto update
def auto_update_ytdlp():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        import yt_dlp.version
        print(f"✅ yt-dlp updated to version: {yt_dlp.version.__version__}")
    except Exception as e:
        print(f"⚠️ yt-dlp auto-update failed: {e}")

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
        ydl_opts = {
            'format': format_str,
            'outtmpl': outtmpl,
            'quiet': True,
            'noplaylist': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            mp4_file = ydl.prepare_filename(info)
            last_files['mp4'] = mp4_file

            # ✅ Convert to MP3
            mp3_file = mp4_file.replace(".mp4", ".mp3")
            if shutil.which("ffmpeg"):
                subprocess.run([
                    "ffmpeg", "-i", mp4_file,
                    "-vn", "-ab", "192k", mp3_file,
                    "-y"
                ])
                last_files['mp3'] = mp3_file

        return jsonify({"ready": True})
    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"ready": False})

@app.route('/download')
def download():
    file_type = request.args.get("type")

    # ✅ MP4
    if file_type == "mp4":
        mp4 = last_files.get("mp4")
        if not mp4 or not os.path.exists(mp4):
            return "❌ MP4 file not ready", 404
        return send_file(mp4, as_attachment=True,
                         download_name="video.mp4",
                         mimetype="video/mp4")

    # ✅ MP3
    elif file_type == "mp3":
        mp3 = last_files.get("mp3")
        if not mp3 or not os.path.exists(mp3):
            return "❌ MP3 file not ready", 404
        return send_file(mp3, as_attachment=True,
                         download_name="audio.mp3",
                         mimetype="audio/mpeg")

    # ✅ BOTH → ZIP নয় → দুইটা আলাদা ডাউনলোড
    elif file_type == "both":
        mp4 = last_files.get("mp4")
        mp3 = last_files.get("mp3")

        if not mp4 or not os.path.exists(mp4):
            return "❌ MP4 file missing", 404
        if not mp3 or not os.path.exists(mp3):
            return "❌ MP3 file missing", 404

        # ✅ প্রথমে MP4 পাঠাও
        # ✅ তারপর JS দিয়ে MP3 auto-download করাও
        return jsonify({
            "mp4": "/download?type=mp4",
            "mp3": "/download?type=mp3"
        })

    return "Invalid type", 400

if __name__ == "__main__":
    auto_update_ytdlp()
    print("✅ Flask server running at: http://127.0.0.1:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
