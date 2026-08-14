# orange-webstone

网页版炉石传说：浏览器里玩 orange-stone 引擎驱动的炉石对局。当前 MVP 是
**人机对战**（你 vs 规则/贪婪/随机对手），架构预留了在线双人 PvP。

## 架构

```
浏览器（React + Vite + TS）          Python 服务端（FastAPI + WebSocket）
┌───────────────────────┐  WS   ┌──────────────────────────────────────┐
│ Lobby → Game 界面      │◄─────►│ app/main.py    WS 协议与静态托管      │
│ 手牌/战场/瞄准状态机    │ JSON  │ app/session.py GameSession 对局驱动  │
│ useGame hook          │       │ app/view.py    观测/动作 → JSON      │
└───────────────────────┘       │ hearthstone_os Env + bots（sys.path 复用）│
                                │ orange_stone PyO3 绑定（Rust 引擎）   │
                                └──────────────────────────────────────┘
```

- **服务端持有一局 `hearthstone_os.Env`**（双 GameEnv 锁步，任意一方视角的
  观测都能给），人类固定 P1，bot 在 P2。bot 回合**逐动作**跑（复用
  `play.py` 的模式），每一步产出一帧 **board 公开局面**发给浏览器——对手的
  每一步都看得见，前端逐帧渲染（新随从 pop-in、掉血红闪）。
- **board 帧不泄漏手牌**：取 bot 视角的观测、剥掉 bot 手牌条目（只留
  handCount）；人类手牌在这个视角里本来就隐藏。回到人类回合发一帧完整
  state（含手牌与合法动作）。客户端用 `awaiting` 标志锁交互并显示
  "对方行动中…"。
- **无卡图**：卡面用卡牌类型配色 + 引擎卡表的英文原名 + 官方效果文本渲染。
  文本来自 `orange-stone/cards/cards.json`（服务端启动时读一次，先按
  card_id 查、查不到按卡名回退——与 orange-stone 自己的对拍口径一致，
  白板卡无文本）。中文名映射是后续项。

## WS 协议

```
C→S  {"type":"start","deck":"vanilla"|"random","bot":"rule"|"greedy"|"random","seed":int|null}
C→S  {"type":"action","index":int}
S→C  {"type":"state", turn, done, winner, awaitingChoice, me, opponent, legal[], seat, humanTurn, seed, bot}
S→C  {"type":"board","text":"出 Sen'jin Shieldmasta(4费)","view":{turn, done, winner, me, opponent}}
       # 公开局面帧：人类动作的即时结果 + bot 回合每一步（双方手牌都剥掉）
S→C  {"type":"error","message":"..."}
```

节奏：人类动作的 board 帧即时发送；bot 动作每帧间隔 `ORANGE_WEB_BOT_DELAY`
（默认 0.7s）；bot 回合结束（或对局结束）发一帧完整终态 state。

字段形状见 `server/app/view.py` ↔ `web/src/types.ts`（改一边同步另一边）。
一局一个 WS 连接，对局在内存里，不落库。

## 开发

```bash
# 依赖（一次性）
python3.12 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r server/requirements.txt
.venv/bin/pip install ../orange-stone/target/wheels/orange_stone-*.whl
cd web && npm install && cd ..

# 开发模式（两个终端；vite 代理 /ws 到 8000）
.venv/bin/uvicorn app.main:app --app-dir server --port 8000 --reload
cd web && npm run dev            # http://localhost:5173

# 生产模式（构建后 uvicorn 直接托管 dist + WS，单端口）
cd web && npm run build
.venv/bin/uvicorn app.main:app --app-dir server --port 8000
# 打开 http://localhost:8000
```

服务端通过 `ORANGE_REINFORCEMENT_PATH`（默认工作区内的
`../orange-reinforcement`）复用 `hearthstone_os`；`ORANGE_WEB_BOT_DELAY`
控制 bot 每步日志的间隔（默认 0.7s，测试设 0）。

## 测试

```bash
.venv/bin/python -m pytest server/tests -q   # GameSession 整局 + WS 协议端到端
```

## 已知边界（MVP 有意为之）

- **英文卡名与卡面文本**：引擎卡表原名 + cards.json 官方文本（如
  "Bloodfen Raptor" / "Taunt"）；中文名/中文文本映射待做。
- **无卡图/无音效**：动画靠 board 逐帧渲染（入场 pop + 掉血红闪），
  没有攻击飞行动画。
- **无换牌（mulligan）**：引擎起手固定 hand_size，无需选择。
- **单进程内存对局**：断线即丢局；多副本部署需要粘性会话/外置存储。
- **人类固定 P1**：先手优势不做座位轮换（人机对战无所谓公平对拍）。

## 路线图

1. 中文卡名/卡面文本映射（cards.json 只有英文；经典卡中文表在
   `orange-stone/docs/finished/classic-cards-zh.md`，需按名字配对）
2. 在线双人 PvP（房间号 + 按座位分发视角，session.py 的驱动结构已支持）
3. 训练好的 RL 智能体当对手（`hearthstone_os/models/agent_full_s*.pt`，
   RuleBot 同接口可直接换）
4. 卡组编辑器（全池选卡，服务端校验合法）
5. 卡图（外部 API 或本地资源）、攻击/施法飞行动画
