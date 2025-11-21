import os
import sys
import socket
import subprocess

from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp


# ==================== yt-dlp auto-update ====================
def auto_update_ytdlp():
    """Update yt-dlp automatically when server starts."""
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"
        ])
        import yt_dlp.version
        print(f"yt-dlp updated to version: {yt_dlp.version.__version__}")
    except Exception as e:
        print(f"yt-dlp auto-update failed: {e}")


# ==================== Flask setup ====================
app = Flask(__name__)
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ==================== IP helper ====================
def get_ip():
    """Return local IP address for server info."""
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


@app.route("/favicon.ico")
def favicon():
    path = os.path.join(app.root_path, "static", "favicon.ico")
    if os.path.exists(path):
        return send_file(path, mimetype="image/vnd.microsoft.icon")
    return ("", 204)


@app.route("/fetch_info", methods=["POST"])
def fetch_info():
    """Fetch video info (title, channel, thumbnail, duration)."""
    data = request.get_json(force=True) or {}
    url = data.get("url")
    if not url:
        return jsonify({"error": "URL required"}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            # Reduce JS runtime warnings while keeping YouTube working
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
        return jsonify({"error": str(e)}), 400


@app.route("/download", methods=["POST"])
def download():
    """Download video or audio with resolution/bitrate options."""
    data = request.get_json(force=True) or {}
    url = data.get("url")
    type_ = (data.get("type", "mp4") or "mp4").lower()         # "mp4" or "mp3"
    res = str(data.get("res", "1080")).strip()                 # 144/240/360/480/720/1080/2160...
    bitrate = str(data.get("bitrate", "192")).strip()          # 128/192/256/320/350...

    if not url:
        return jsonify({"error": "URL required"}), 400

    if type_ == "mp3":
        format_str = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": bitrate,
        }]
        merge_format = None
    else:
        if res.isdigit():
            # limit max height to requested resolution
            format_str = f"bestvideo[height<={res}]+bestaudio/best"
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
        # Keep YouTube working without installing Node
        "extractor_args": {"youtube": {"player_client": ["default"]}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if type_ == "mp3":
                filename = filename.rsplit(".", 1)[0] + ".mp3"

        return send_file(
            filename,
            as_attachment=True,
            download_name=os.path.basename(filename)
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== run server ====================
if __name__ == "__main__":
    auto_update_ytdlp()
    ip = get_ip()
    print(f"Flask server running at: http://{ip}:5000")
    try:
        # Helpful for Android/Termux
        with open("/sdcard/flask_ip.txt", "w") as f:
            f.write(f"http://{ip}:5000")
        print("IP written to /sdcard/flask_ip.txt")
    except Exception as e:
        print(f"Could not write IP: {e}")
    app.run(debug=True, host="0.0.0.0", port=5000)
