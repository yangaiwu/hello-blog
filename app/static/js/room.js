/* Watch page: HLS-first player with FLV fallback, plus realtime danmaku. */
(() => {
  const root = document.getElementById('room');
  if (!root) return;

  const demo = root.dataset.demo === 'true';
  const isRunning = root.dataset.status === 'running';
  const video = document.getElementById('player');
  const playerError = root.querySelector('[data-role="player-error"]');

  function showPlayerError(text) {
    if (!playerError) return;
    playerError.textContent = text;
    playerError.hidden = false;
  }

  function attachPlayer() {
    if (demo) return; // placeholder explains demo mode
    const hlsUrl = root.dataset.hls;
    const flvUrl = root.dataset.flv;

    if (window.Hls && window.Hls.isSupported()) {
      const hls = new window.Hls({ lowLatencyMode: true });
      hls.on(window.Hls.Events.ERROR, (_event, data) => {
        if (data && data.fatal) showPlayerError('HLS 播放失败：请确认推流已开始且播放域名 CNAME 已生效。');
      });
      hls.loadSource(hlsUrl);
      hls.attachMedia(video);
    } else if (window.flvjs && window.flvjs.isSupported()) {
      const player = window.flvjs.createPlayer({ type: 'flv', url: flvUrl, isLive: true });
      player.attachMediaElement(video);
      player.on(window.flvjs.Events.ERROR, () => showPlayerError('FLV 播放失败：请确认推流已开始且播放域名可访问。'));
      player.load();
      player.play();
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = hlsUrl;
    } else {
      showPlayerError('当前浏览器不支持 HLS/FLV 播放，请更换浏览器。');
    }
  }

  /* ---------------- danmaku ---------------- */
  const listEl = root.querySelector('[data-role="messages"]');
  const statusEl = root.querySelector('[data-role="chat-status"]');
  const form = root.querySelector('[data-role="chat-form"]');
  const nickInput = root.querySelector('[data-role="nickname"]');
  const contentInput = root.querySelector('[data-role="content"]');
  const errorEl = root.querySelector('[data-role="chat-error"]');
  const viewersEl = root.querySelector('[data-role="viewers"]');

  let socket = null;
  let retry = 0;
  let errorTimer = null;

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function showChatError(text) {
    if (!errorEl) return;
    errorEl.textContent = text;
    errorEl.hidden = false;
    clearTimeout(errorTimer);
    errorTimer = setTimeout(() => { errorEl.hidden = true; }, 4000);
  }

  function appendMessage(nickname, content) {
    if (!listEl) return;
    const li = document.createElement('li');
    const nick = document.createElement('span');
    nick.className = 'nick';
    nick.textContent = nickname;
    const text = document.createElement('span');
    text.className = 'text';
    text.textContent = content;
    li.append(nick, text);
    listEl.append(li);
    listEl.scrollTop = listEl.scrollHeight;
  }

  function handleFrame(frame) {
    if (frame.type === 'viewers') {
      if (viewersEl) viewersEl.textContent = `在线 ${frame.count} 人`;
      return;
    }
    if (frame.type === 'message') {
      appendMessage(frame.nickname, frame.content);
      return;
    }
    if (frame.type === 'error') {
      showChatError(frame.message || frame.code);
      if (frame.code === 'room_ended' || frame.code === 'room_not_found') {
        setStatus('直播已结束，无法发送弹幕。');
        if (form) form.hidden = true;
      }
    }
  }

  function nickname() {
    const value = (nickInput && nickInput.value.trim()) || '';
    return value || '游客';
  }

  function connect() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}${root.dataset.wsPath}?nickname=${encodeURIComponent(nickname())}`;
    socket = new WebSocket(url);

    socket.addEventListener('open', () => {
      retry = 0;
      setStatus('已连接，房间内消息实时同步。');
    });
    socket.addEventListener('message', (event) => {
      try {
        handleFrame(JSON.parse(event.data));
      } catch (err) {
        /* ignore malformed frames */
      }
    });
    socket.addEventListener('close', () => {
      setStatus('连接已断开。');
      socket = null;
      if (!isRunning) return;
      retry = Math.min(retry + 1, 5);
      setTimeout(() => {
        setStatus('正在重新连接…');
        connect();
      }, retry * 1000);
    });
  }

  if (form) {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const content = contentInput ? contentInput.value.trim() : '';
      if (!content) return;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        showChatError('弹幕连接尚未就绪，请稍后重试。');
        return;
      }
      socket.send(JSON.stringify({ content }));
      contentInput.value = '';
    });
  }

  attachPlayer();
  if (isRunning) {
    setStatus('正在连接…');
    connect();
  }
})();