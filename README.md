# hello-blog

A demo repository used by the Grape DevOps platform (dev environment) for
end-to-end pipeline verification: VOD -> Issue -> Coding -> QA -> SRE.

The feature work lives in the issue tracker. Issue #21 turned this repository
into a small 娱乐秀场 live-streaming site (开播 → 观看 → 弹幕).

## Layout

```
app/
  __init__.py        create_app() factory (config, DB, routes, WebSocket)
  config.py          Settings.from_env() + demo-mode detection
  db.py              SQLite (WAL) rooms / messages persistence
  routes.py          page routes and JSON API
  ws.py              /ws/room/<id> danmaku endpoint (flask-sock)
  danmaku.py         message validation + per-connection rate limiting
  hub.py             room presence and broadcast (transport independent)
  services/live.py   腾讯云 CSS push/play URL signing
  templates/         index / broadcast / room / 404
  static/            app.css, room.js, broadcast.js
tests/               pytest suite (unit + HTTP + real WebSocket)
docs/                per-issue spec / plan / task
```

## Quick start

```bash
pip install -r requirements.txt
DB_PATH=./live.db python -m flask --app app run --port 8080
# open http://127.0.0.1:8080/
```

Pages: `/` room list, `/broadcast` create a room and get push URLs,
`/room/<id>` watch page (player + danmaku).

## Configuration

All configuration is environment based; every variable is optional.

| Variable | Meaning | Default |
|----------|---------|---------|
| `CSS_PUSH_DOMAIN` | 腾讯云推流域名 | empty → demo mode |
| `CSS_PLAY_DOMAIN` | 腾讯云播放域名 | empty → demo mode |
| `CSS_PUSH_KEY` | 推流鉴权 Key（控制台「推流配置」里的鉴权 Key） | empty → demo mode |
| `CSS_PLAY_KEY` | 播放鉴权 Key（可选，配置后播放地址也签名） | empty → 播放地址不签名 |
| `CSS_BIZID` | 腾讯云直播 bizid（推拉流域名前缀，可选） | empty |
| `CSS_APP_NAME` | 直播 AppName | `live` |
| `CSS_PUSH_URL_TTL` | 推流地址有效期（秒） | `7200` |
| `DB_PATH` | SQLite 文件路径 | `live.db` |
| `SECRET_KEY` | Flask session 密钥 | `dev-secret-change-me` |

### Demo mode

If any of `CSS_PUSH_DOMAIN` / `CSS_PLAY_DOMAIN` / `CSS_PUSH_KEY` is missing the
service boots in **demo mode**: push/play URLs are placeholders
(`demo-push.css.example.com` / `demo-play.css.example.com`), the watch page
shows a notice instead of pulling a stream, and the full 开播 → 观看 → 弹幕
loop still works. Inject the credentials and restart to go live — no code
changes needed.

## Tencent Cloud CSS setup

1. 控制台开启「云直播 CSS」，添加**推流域名**与**播放域名**，按提示完成 CNAME。
2. 在「域名管理 → 推流配置」中记录 **推流鉴权 Key**（即 `CSS_PUSH_KEY`）；需要播放鉴权时同样配置 `CSS_PLAY_KEY`。
3. 记录 `bizid`（推流域名前缀），配合 `CSS_BIZID` 使用；AppName 默认 `live`。
4. 启动本站并设置上述环境变量，进入「我要开播」创建房间。

### OBS 推流

开播页会给出两组值：

- **服务器**：`rtmp://<bizid>.pushDomain/live`
- **串流密钥**：`stream_xxx?txSecret=...&txTime=...`（已含鉴权参数）

OBS → 设置 → 直播 → 服务选「自定义」，填入以上两项后点「开始推流」。
推流地址由本地按 `md5(pushKey + streamName + txTime)` 规则签名，无需调用云 API。

### 播放

观看页优先使用 hls.js 播放 `.m3u8`，不支持时回退 flv.js 播放 `.flv`。若拉流失败，页面会给出排查提示（通常是推流未开始或播放域名 CNAME 未生效）。

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/rooms` | 创建房间，返回房间信息 + 推流/播放地址 |
| GET | `/api/rooms` | 房间列表（含实时在线人数） |
| GET | `/api/rooms/<id>` | 房间详情 + 推流/播放地址 |
| POST | `/api/rooms/<id>/stop` | 结束直播（幂等） |
| GET | `/api/rooms/<id>/messages?limit=100` | 历史弹幕 |
| WS | `/ws/room/<id>?nickname=<name>` | 弹幕通道，客户端发送 `{"content": "..."}` |

Danmaku rules: nickname 1–30 chars, content 1–200 chars, at most 1 message per
second per connection. Violations return a `{"type":"error","code":...}` frame
without dropping the connection.

## Tests

```bash
python -m pytest          # 51 tests: signing, API, danmaku rules, real WS fan-out
```

## Notes / limitations

- Single-process broadcast (`RoomHub` in memory); multi-instance deployment
  needs a shared pub/sub (e.g. Redis).
- No auth/user system in this iteration (per the Issue scope).
- Room "cover" is a generated placeholder, not an uploaded image.