from flask import Flask, render_template, request, send_file, jsonify
import os, shutil, subprocess, sys, platform
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

    # If ffmpeg is available we can request merging video+audio; otherwise
    # ask for a single-file format to avoid yt-dlp trying to run ffmpeg.
    has_ffmpeg = shutil.which("ffmpeg") is not None
    if has_ffmpeg:
        format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        # avoid merge formats that require ffmpeg
        format_str = 'best[ext=mp4]/best'

    outtmpl = 'downloads/%(id)s - %(title)s.%(ext)s'

    try:
        ydl_opts = {
            'format': format_str,
            'outtmpl': outtmpl,
            'quiet': True,
            'noplaylist': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as e:
                # If yt-dlp failed because ffmpeg is missing and merging was
                # requested, retry with a safe single-file format to avoid
                # requiring ffmpeg.
                msg = str(e).lower()
                if ('ffmpeg is not installed' in msg) or ('requested merging' in msg) or ('merging of multiple formats' in msg) or ('--abort-on-error' in msg):
                    safe_opts = dict(ydl_opts)
                    safe_opts['format'] = 'best[ext=mp4]/best'
                    with yt_dlp.YoutubeDL(safe_opts) as ydl2:
                        info = ydl2.extract_info(url, download=True)
                else:
                    raise

            downloaded_file = ydl.prepare_filename(info)
            # Save the downloaded filename (may be mp4, webm, m4a, etc.)
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
                except Exception as _:
                    last_files['mp3'] = None

        # Build a richer response for the UI: include title, thumbnail and available files
        title = info.get('title') if isinstance(info, dict) else None
        thumbnail = info.get('thumbnail') if isinstance(info, dict) else None

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
        return jsonify({"ready": False, "error": str(e)})

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


@app.route('/open-downloads', methods=['GET', 'POST'])
def open_downloads():
    """Attempt to open the downloads folder on the server host.

    Works on Windows, macOS, and common Linux desktops. This is a convenience
    for local development only; in production this endpoint should be removed
    or protected.
    """
    downloads_dir = os.path.abspath("downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    try:
        if platform.system() == "Windows":
            # Use explorer via subprocess instead of os.startfile to avoid
            # SystemExit or debugger-related exits when running under debugpy.
            try:
                subprocess.Popen(["explorer", downloads_dir])
            except Exception:
                # Fallback to os.startfile but protect against SystemExit
                try:
                    os.startfile(downloads_dir)
                except SystemExit:
                    return jsonify({"opened": False, "error": "SystemExit when opening folder"}), 500
                except Exception as e:
                    return jsonify({"opened": False, "error": str(e)}), 500
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", downloads_dir])
        else:
            # Linux / BSD
            subprocess.Popen(["xdg-open", downloads_dir])
        return jsonify({"opened": True})
    except Exception as e:
        print("Could not open downloads folder:", e)
        return jsonify({"opened": False, "error": str(e)}), 500

if __name__ == "__main__":
    auto_update_ytdlp()
    print("✅ Flask server running at: http://127.0.0.1:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
