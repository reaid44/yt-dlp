const startBtn = document.getElementById('startBtn');
const status = document.getElementById('status');
const preview = document.getElementById('preview');
const thumb = document.getElementById('thumb');
const videoTitle = document.getElementById('videoTitle');
const mp4Btn = document.getElementById('mp4Btn');
const mp3Btn = document.getElementById('mp3Btn');
const bothBtn = document.getElementById('bothBtn');
const progressBar = document.getElementById('progressBar');

// Update progress bar width
function updateProgress(percent) {
    progressBar.style.width = percent + '%';
}

startBtn.addEventListener('click', async () => {
    const url = document.getElementById('urlInput').value.trim();
    if (!url) { 
        alert('Please enter a link'); 
        return; 
    }

    startBtn.disabled = true;
    status.textContent = '⏳ Processing...';
    preview.classList.add('hidden');
    updateProgress(10);

    try {
        const res = await fetch('/prepare', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({url})
        });

        updateProgress(50);

        const data = await res.json();
        if (data.ready) {
            status.textContent = '✅ File ready!';
            videoTitle.textContent = data.title || 'Unknown title';
            if (data.thumbnail) thumb.src = data.thumbnail;
            mp4Btn.href = data.mp4_url || '/download?type=mp4';
            mp3Btn.href = data.mp3_url || '/download?type=mp3';
            bothBtn.href = '/download?type=both';
            preview.classList.remove('hidden');
            updateProgress(100);
        } else {
            status.textContent = '❌ Not ready — ' + (data.error || 'Error');
            updateProgress(0);
        }
    } catch (e) {
        status.textContent = '❌ Server error: ' + e.message;
        updateProgress(0);
    } finally {
        startBtn.disabled = false;
    }
});
