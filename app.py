from flask import Flask, render_template, request, send_file, jsonify
import os, shutil, socket, sys, subprocess
import yt_dlp

# ==================== yt-dlp auto-update ====================
def auto_update_ytdlp():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])
        import yt_dlp.version
        print(f"yt-dlp updated to version: {yt_dlp.version.__version__}")
    except Exception as e:
        print(f"yt-dlp auto-update failed: {e}")

# ==================== Flask setup ====================
app = Flask(__name__)
last_files = {}  # {'mp4': path, 'mp3': path}
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==================== IP helper ====================
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

# ==================== routes ====================
@app.route("/")
def index():
    return render_template("index.html")

# Fetch title/channel/thumbnail/duration only (no download)
@app.route("/fetch_info", methods=["POST"])
def fetch_info():
    data = request.get_json(force=True) or {}
    url = data.get("url")
    if not url:
        return jsonify({"error": "URL required"}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            # reduce JS runtime warnings without installing Node
            "extractor_args": {"youtube": {"player_client": ["default"]}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "title": info.get("title", "Unknown Title"),
                "channel": info.get("uploader", "Unknown Channel"),
                "thumbnail": info.get("thumbnail") or "",
                "duration": info.get("duration", 0)
            })
    except Exception as e:
        return jsonify({"error": f"{e}"}), 400

# Prepare download (video/audio) with resolution/bitrate
@app.route("/prepare", methods=["POST"])
def prepare():
    data = request.get_json(force=True) or {}
    url = data.get("url")
    type_ = data.get("type", "mp4")        # "mp4" or "mp3"
    res = str(data.get("res", "")).strip() # e.g., "360","720","1080","2160"
    bitrate = str(data.get("bitrate", "192")).strip()  # e.g., "192","256","320","350"

    if not url:
        return jsonify({"ready": False, "error": "URL required"}), 400

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Build format string and postprocessors
    if type_.lower() == "mp3":
        format_str = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": bitrate,  # 192, 256, 320, 350
        }]
        merge_format = None
    else:
        # video mp4 with optional max height
        if res.isdigit():
            format_str = f"bestvideo[height<={res}]+bestaudio/best/best"
        else:
            format_str = "bestvideo+bestaudio/best"
        postprocessors = []
        merge_format = "mp4"

    ydl_opts = {
        "format": format_str,
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "merge_output_format": merge_format,
        "postprocessors": postprocessors,
        "ignoreerrors": True,
        "noplaylist": True,
        "quiet": True,
        # keep YouTube working without JS runtime
        "extractor_args": {"youtube": {"player_client": ["default"]}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            # finalize mp3 filename if audio mode
            if type_.lower() == "mp3":
                filename = filename.rsplit(".", 1)[0] + ".mp3"

            # store last files
            if type_.lower() == "mp4":
                last_files["mp4"] = filename
                # optional parallel mp3 generation from the same mp4 if requested via bitrate-only later
            elif type_.lower() == "mp3":
                last_files["mp3"] = filename

        return jsonify({"ready": True})
    except Exception as e:
        return jsonify({"ready": False, "error": f"{e}"}), 500

# Download prepared file
@app.route("/download")
def download():
    file_type = (request.args.get("type") or "").lower()
    path = last_files.get(file_type)
    if not path or not os.path.exists(path):
        return "File not ready", 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

# ==================== run ====================
if __name__ == "__main__":
    auto_update_ytdlp()
    ip = get_ip()
    print(f"Flask server running at: http://{ip}:5000")
    # optional: write IP for Android Termux convenience
    try:
        with open("/sdcard/flask_ip.txt", "w") as f:
            f.write(f"http://{ip}:5000")
        print("IP written to /sdcard/flask_ip.txt")
    except Exception as e:
        print(f"Could not write IP: {e}")
    app.run(debug=True, host="0.0.0.0", port=5000)
