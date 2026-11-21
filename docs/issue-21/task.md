# Task — Issue #21 任务拆解

| # | 任务 | 验收 |
|---|------|------|
| 1 | 配置层 `Settings.from_env`（demo 判定） | 缺任一 CSS 变量 → is_demo=True |
| 2 | `services/live.py` 签名与地址生成 | txTime 十六进制、txSecret=md5(key+stream+txTime)，push/play URL 格式固定断言通过 |
| 3 | `db.py` SQLite 表与 CRUD | 建库、房间创建/查询/结束、弹幕落库与回显 |
| 4 | `routes.py` 页面与 API | 列表/开播/观看/结束/历史弹幕，参数校验返回明确错误 |
| 5 | `danmaku.py` + `hub.py` | 长度/频率校验生效，RoomHub 双连接广播 |
| 6 | `ws.py` WebSocket 端点 | 双客户端实时互通、历史回显、越界回错误帧 |
| 7 | 模板与静态资源 | 三页可用，demo 模式占位提示，开播页地址一键复制 |
| 8 | README + requirements + .gitignore | 环境变量表、OBS 配置、demo 说明 |
| 9 | 测试与自检 | pytest 全绿；一次性启动自检 200 |

提交顺序（TDD 红/绿分离）：

1. `docs(#21)`: spec/plan/task + requirements/.gitignore
2. `test(#21)`: 失败测试（红）
3. `feat(#21)`: 最小实现使测试通过（绿）
4. `feat(#21)`: 模板/静态资源/README（页面级交付）