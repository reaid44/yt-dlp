const urlInput = document.getElementById("urlInput");
const downloadBtn = document.getElementById("downloadBtn");
const progressBar = document.getElementById("progressBar");
const progressPercent = document.getElementById("progressPercent");
const statusText = document.getElementById("statusText");
const titleEl = document.getElementById("title");
const thumbEl = document.getElementById("thumb");
const mp4Btn = document.getElementById("mp4Btn");
const mp3Btn = document.getElementById("mp3Btn");

function setProgress(pct) {
  const clamped = Math.max(0, Math.min(100, pct || 0));
  progressBar.style.width = clamped + "%";
  progressPercent.textContent = clamped.toFixed(0) + "%";
}

function showDownloads(mp4Url, mp3Url) {
  if (mp4Url) {
    mp4Btn.href = mp4Url;
    mp4Btn.style.display = "inline-block";
  }
  if (mp3Url) {
    mp3Btn.href = mp3Url;
    mp3Btn.style.display = "inline-block";
  }
}

async function pollProgress(stopSignal) {
  try {
    const res = await fetch("/progress");
    const data = await res.json();
    setProgress(data.percent || 0);
    statusText.textContent = "Status: " + (data.status || "idle");

    if (data.title) titleEl.textContent = data.title;
    if (data.thumb) {
      thumbEl.src = data.thumb;
      thumbEl.style.display = "block";
    }

    if (data.percent >= 100 || stopSignal.stopped) {
      stopSignal.stopped = true;
      return;
    }
  } catch (_) {
    // ignore errors
  }
  setTimeout(() => pollProgress(stopSignal), 600);
}

downloadBtn.addEventListener("click", async () => {
  const url = (urlInput.value || "").trim();
  if (!url) {
    alert("YouTube URL দিন।");
    return;
  }

  // Reset UI
  setProgress(0);
  statusText.textContent = "Status: starting";
  titleEl.textContent = "";
  thumbEl.removeAttribute("src");
  mp4Btn.style.display = "none";
  mp3Btn.style.display = "none";

  downloadBtn.disabled = true;

  const stopSignal = { stopped: false };
  pollProgress(stopSignal); // start polling

  try {
    const res = await fetch("/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    const data = await res.json();

    if (data.ready) {
      statusText.textContent = "Status: finished";
      setProgress(100);
      if (data.title) titleEl.textContent = data.title;
      if (data.thumbnail) {
        thumbEl.src = data.thumbnail;
        thumbEl.style.display = "block";
      }
      showDownloads(data.mp4 ? data.mp4_url : null, data.mp3 ? data.mp3_url : null);
    } else {
      statusText.textContent = "Status: error";
      alert(data.error || "Unknown error");
    }
  } catch (e) {
    statusText.textContent = "Status: error";
    alert("Prepare request failed: " + e);
  } finally {
    stopSignal.stopped = true;
    downloadBtn.disabled = false;
  }
});
