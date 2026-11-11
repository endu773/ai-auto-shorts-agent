
const form = document.getElementById('form');
const file = document.getElementById('video');

file.addEventListener('change', () => {
  document.getElementById('fileLabel').textContent =
    file.files[0]?.name || 'Choose video file';
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  if (!file.files.length) return;

  const btn = document.getElementById('submit');
  btn.disabled = true;
  btn.textContent = 'Uploading...';

  const panel = document.getElementById('progress');
  panel.classList.remove('hidden');

  document.getElementById('status').textContent =
    'Uploading video and starting automatic editing...';

  const data = new FormData(form);

  try {
    const response = await fetch('/api/jobs', {
      method: 'POST',
      body: data
    });

    const job = await response.json();

    if (!response.ok) {
      throw new Error(job.detail || 'Upload failed');
    }

    poll(job.id);

  } catch (error) {
    document.getElementById('status').textContent =
      'Error: ' + error.message;

    btn.disabled = false;
    btn.textContent = 'Try again';
  }
});

async function poll(id) {
  const status = document.getElementById('status');
  const bar = document.getElementById('bar');

  try {
    const response = await fetch('/api/jobs/' + id);
    const job = await response.json();

    if (job.status === 'queued' ||
        job.status === 'processing') {

      status.textContent =
        job.status === 'queued'
        ? 'Waiting to process...'
        : 'AI is analysing and cutting your video...';

      bar.style.width =
        job.status === 'queued' ? '15%' : '55%';

      setTimeout(() => poll(id), 3000);
      return;
    }

    if (job.status === 'failed') {
      status.textContent = 'Processing failed: ' + job.error;
      return;
    }

    bar.style.width = '100%';

    status.textContent =
      `Done! ${job.clips.length} Shorts created. ${job.note || ''}`;

    document.getElementById('results').innerHTML =
      job.clips.map(clip => `
        <div class="clip">
          <b>${clip.name}</b>
          <p>${clip.start}s - ${clip.end}s</p>
          <a href="/api/jobs/${id}/clips/${clip.name}">
            Download Short
          </a>
        </div>
      `).join('');

  } catch (error) {
    status.textContent = 'Connection error. Please refresh and check.';
  }
}
  
