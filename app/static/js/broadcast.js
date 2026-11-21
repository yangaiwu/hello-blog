/* Broadcast page: create a room, show push/play URLs, copy them, stop the stream. */
(() => {
  const form = document.getElementById('create-room');
  if (!form) return;

  const info = document.getElementById('stream-info');
  const errorEl = form.querySelector('[data-role="error"]');
  const statusEl = document.querySelector('[data-role="status"]');
  const watchLink = document.querySelector('[data-role="watch-link"]');
  const stopBtn = document.querySelector('[data-role="stop"]');
  const recent = document.getElementById('recent');

  let currentRoomId = null;

  const fields = {
    'obs-server': 'obs-server',
    'obs-key': 'obs-key',
    'push-url': 'push-url',
    'hls-url': 'hls-url',
    'flv-url': 'flv-url',
  };

  function field(role) {
    return document.querySelector(`[data-role="${role}"]`);
  }

  function showError(text) {
    errorEl.textContent = text;
    errorEl.hidden = false;
  }

  function fill(room, live) {
    field('obs-server').textContent = live.obs.server;
    field('obs-key').textContent = live.obs.stream_key;
    field('push-url').textContent = live.push_url;
    field('hls-url').textContent = live.play_urls.hls;
    field('flv-url').textContent = live.play_urls.flv;
    watchLink.href = room.url;
    currentRoomId = room.id;
    info.hidden = false;
    statusEl.textContent = '进行中';
    statusEl.className = 'badge live';
    recent.hidden = true;

    if (live.demo) {
      const hint = document.querySelector('[data-role="demo-hint"]');
      if (hint) hint.hidden = false;
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    const data = new FormData(form);
    const payload = {
      title: String(data.get('title') || '').trim(),
      anchor_name: String(data.get('anchor_name') || '').trim(),
    };
    try {
      const resp = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const body = await resp.json();
      if (!resp.ok) {
        showError(body.error ? body.error.message : '创建失败，请重试。');
        return;
      }
      fill(body.room, body.live);
    } catch (err) {
      showError('网络异常，创建失败。');
    }
  });

  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
      const target = field(button.dataset.copy);
      if (!target) return;
      try {
        await navigator.clipboard.writeText(target.textContent);
        button.textContent = '已复制';
        setTimeout(() => { button.textContent = '复制'; }, 1500);
      } catch (err) {
        button.textContent = '请手动复制';
      }
    });
  });

  stopBtn.addEventListener('click', async () => {
    if (!currentRoomId) return;
    const resp = await fetch(`/api/rooms/${currentRoomId}/stop`, { method: 'POST' });
    const body = await resp.json();
    if (!resp.ok) {
      showError(body.error ? body.error.message : '结束失败。');
      return;
    }
    statusEl.textContent = '已结束';
    statusEl.className = 'badge ended';
    stopBtn.disabled = true;
    stopBtn.textContent = '已结束';
  });
})();