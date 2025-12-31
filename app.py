from flask import Flask, render_template, request, send_file, jsonify
import os, shutil, subprocess, sys, platform
import yt_dlp

app = Flask(__name__)
last_files = {}
progress_data = {"percent": 0, "status": "idle", "title": None, "thumb": None}

# ✅ yt-dlp auto update
def auto_update_ytdlp():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        import yt_dlp.version
        print(f"✅ yt-dlp updated to version: {yt_dlp.version.__version__}")
    except Exception as e:
        print(f"⚠️ yt-dlp auto-update failed: {e}")

# ✅ progress hook: updates percent in real time
def progress_hook(d):
    if d.get('status') == 'downloading':
        # Prefer numeric calculation if available
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        downloaded = d.get('downloaded_bytes') or 0
        if total and downloaded:
            pct = (downloaded / total) * 100
        else:
            # Fallback to string percent
            pct_str = d.get('_percent_str', '0.0%').replace('%', '').strip()
            try:
                pct = float(pct_str)
            except:
                pct = 0.0
        progress_data["percent"] = round(pct, 2)
        progress_data["status"] = "downloading"
    elif d.get('status') == 'finished':
        progress_data["percent"] = 100.0
        progress_data["status"] = "finished"

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/prepare', methods=['POST'])
def prepare():
    # reset progress for a new request
    progress_data.update({"percent": 0, "status": "starting", "title": None, "thumb": None})

    data = request.get_json() or {}
    url = data.get("url")
    if not url:
        return jsonify({"ready": False, "error": "No URL provided"}), 400

    os.makedirs("downloads", exist_ok=True)

    # Detect ffmpeg availability
    has_ffmpeg = shutil.which("ffmpeg") is not None
    if has_ffmpeg:
        format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        format_str = 'best[ext=mp4]/best'

    outtmpl = 'downloads/%(id)s - %(title)s.%(ext)s'

    try:
        ydl_opts = {
            'format': format_str,
            'outtmpl': outtmpl,
            'quiet': True,
            'noplaylist': True,
            'progress_hooks': [progress_hook],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as e:
                # Safe fallback if merge/ffmpeg issues
                msg = str(e).lower()
                needs_simple = (
                    'ffmpeg is not installed' in msg or
                    'requested merging' in msg or
                    'merging of multiple formats' in msg or
                    '--abort-on-error' in msg
                )
                if needs_simple:
                    safe_opts = dict(ydl_opts)
                    safe_opts['format'] = 'best[ext=mp4]/best'
                    with yt_dlp.YoutubeDL(safe_opts) as ydl2:
                        info = ydl2.extract_info(url, download=True)
                else:
                    raise

            downloaded_file = ydl.prepare_filename(info)
            # Save the downloaded filename (mp4/webm/m4a etc.)
            last_files['mp4'] = downloaded_file

            # If ffmpeg is present, create an MP3 from the downloaded file.
            last_files['mp3'] = None
            if has_ffmpeg:
                try:
                    mp3_file = os.path.splitext(downloaded_file)[0] + ".mp3"
                    subprocess.run([
                        "ffmpeg", "-i", downloaded_file,
                        "-vn", "-ab", "192k", mp3_file,
                        "-y"
                    ], check=False)
                    if os.path.exists(mp3_file):
                        last_files['mp3'] = mp3_file
                except Exception:
                    last_files['mp3'] = None

        # Store metadata for UI
        title = info.get('title') if isinstance(info, dict) else None
        thumbnail = info.get('thumbnail') if isinstance(info, dict) else None
        progress_data["title"] = title
        progress_data["thumb"] = thumbnail

        mp4_exists = os.path.exists(last_files.get('mp4', ''))
        mp3_exists = os.path.exists(last_files.get('mp3', ''))

        response = {
            "ready": True,
            "title": title,
            "thumbnail": thumbnail,
            "mp4": mp4_exists,
            "mp3": mp3_exists,
            "mp4_url": "/download?type=mp4",
            "mp3_url": "/download?type=mp3"
        }
        return jsonify(response)
    except Exception as e:
        print("❌ Error:", e)
        progress_data["status"] = "error"
        return jsonify({"ready": False, "error": str(e)}), 500

@app.route('/progress')
def progress():
    return jsonify(progress_data)

@app.route('/download')
def download():
    file_type = request.args.get("type")

    if file_type == "mp4":
        mp4 = last_files.get("mp4")
        if not mp4 or not os.path.exists(mp4):
            return "❌ MP4 file not ready", 404
        return send_file(mp4, as_attachment=True,
                         download_name="video.mp4",
                         mimetype="video/mp4")

    elif file_type == "mp3":
        mp3 = last_files.get("mp3")
        if not mp3 or not os.path.exists(mp3):
            return "❌ MP3 file not ready", 404
        return send_file(mp3, as_attachment=True,
                         download_name="audio.mp3",
                         mimetype="audio/mpeg")

    elif file_type == "both":
        mp4 = last_files.get("mp4")
        mp3 = last_files.get("mp3")

        if not mp4 or not os.path.exists(mp4):
            return "❌ MP4 file missing", 404
        if not mp3 or not os.path.exists(mp3):
            return "❌ MP3 file missing", 404

        return jsonify({
            "mp4": "/download?type=mp4",
            "mp3": "/download?type=mp3"
        })

    return "Invalid type", 400

if __name__ == "__main__":
    auto_update_ytdlp()
    print("✅ Flask server running at: http://127.0.0.1:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
