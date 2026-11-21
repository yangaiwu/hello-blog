# Plan — Issue #21 实现方案

## 结构

```
app/
  __init__.py        create_app() 工厂：配置、DB 初始化、路由/WS 注册
  config.py          Settings.from_env()，demo 模式判定
  db.py              SQLite 连接与房间/弹幕 CRUD
  routes.py          HTTP 路由（页面 + JSON API）
  ws.py              WebSocket 弹幕端点（flask-sock）
  danmaku.py         弹幕校验 + 频率限制（纯函数/小类，可单测）
  hub.py             房间在线连接表 + 广播（传输无关，可单测）
  services/live.py   腾讯云 CSS 地址签名与生成（纯函数，可单测）
  templates/         base/index/broadcast/room
  static/            css + room.js/broadcast.js
tests/               pytest
docs/issue-21/       spec/plan/task
```

## 关键设计

| 决策 | 选择 | 理由 |
|------|------|------|
| 框架 | Flask 3 + flask-sock | 依赖最少，HTTP/WS 同端口 |
| 推拉流地址 | 本地签名（md5(key+stream+txTime)） | 不依赖云 API，只要域名+推流 Key；demo 模式返回占位地址 |
| 播放 | HLS 优先，FLV 回退（CDN 加载 hls.js/flv.js） | 兼容性与延迟平衡 |
| 弹幕通道 | WebSocket 房间广播 | 满足实时验收；广播逻辑抽到 RoomHub，可脱离传输单测 |
| 存储 | SQLite（WAL，每次调用独立连接） | 无运维依赖；连接短生命周期避免多线程共享问题 |
| 在线人数 | RoomHub 实时连接数 | 无需额外表，结束房间返回 0 |

## 测试 seam

1. `LiveService` 公开方法（签名/地址格式/demo）——纯函数断言固定值。
2. HTTP API 经 Flask test client（`create_app(environ=...)`），断言状态码与 JSON 契约。
3. 弹幕逻辑（`validate_content`/`validate_nickname`/`RateLimiter`）与 `RoomHub` 广播——直接调用，用假连接对象验证双端 fan-out。
4. WS 端到端（真实服务 + 两个 simple_websocket 客户端）作为集成测试；若运行环境不支持 WS 升级则跳过并显式标记（`pytest.mark.skipif`），不伪装成通过。

## 风险

- 腾讯云域名/Key 未提供 → demo 模式 + README 说明，凭据注入后零代码改动联调。
- 控制台 CNAME 未配置 → 拉流失败，页面给出播放错误提示。
- 单进程广播不适用多实例 → 首期单实例，后续换 Redis pub/sub。