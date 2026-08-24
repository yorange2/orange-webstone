"""orange-webstone 服务端：FastAPI + WebSocket。

一个 WS 连接 = 一局对局（内存里一个 GameSession，不落库、不做多进程
共享——部署用单 worker，多副本需要粘性会话/外置存储，超出 MVP 范围）。

协议（camelCase，字段形状见 `view.py` / `web/src/types.ts`）：

    客户端 → 服务端
      {"type":"start","deck":"vanilla"|"random","bot":"rule"|"greedy"|"random","seed":int|null,"lang":"zh"|"en"}
      {"type":"action","index":int}
      {"type":"clientlog","level":"error","text":"...","stack":"..."}
                                                   # 浏览器侧报错转发（开发模式）
      {"type":"lang","lang":"zh"|"en"}             # 对局中切语言（影响后续
                                                   # 日志行；卡面每帧双语言，
                                                   # 客户端切换即时生效）

    服务端 → 客户端
      {"type":"state", ...view.state_dict()...}    # 人类回合的完整一帧
      {"type":"board","text":"...","view":{...}}   # 公开局面帧：人类动作的
                                                   # 即时结果 + bot 回合每一步
      {"type":"log","text":"出 血沼迅猛龙(2费)"}    # 兼容保留（暂未使用）
      {"type":"error","message":"..."}             # 非法动作等

`board.view` 是 bot 视角剥掉手牌的公开快照（`view.public_snapshot`），
浏览器逐帧渲染——对手的每一步都看得见，且不泄漏 bot 手牌。节奏：
人类动作的结果**即时**发送，之后每个 bot 动作间隔 `ORANGE_WEB_BOT_DELAY`
（默认 0.7s）；bot 回合结束（或对局结束）发一帧完整终态 state。
"""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from . import _paths  # noqa: F401  先接 orange-reinforcement 再导入 session
from .debuglog import log, next_session_id, setup as setup_logging, summarize
from .session import LANG_VALUES, GameSession, SessionError

__all__ = ["app"]

BOT_STEP_DELAY = float(os.environ.get("ORANGE_WEB_BOT_DELAY", "0.7"))
STATIC_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"

setup_logging()

app = FastAPI(title="orange-webstone")


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.websocket("/ws")
async def game_socket(ws: WebSocket) -> None:
    await ws.accept()
    sid = next_session_id()
    log.info("[%s] 连接建立", sid)
    session: GameSession | None = None
    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")
            if mtype == "start":
                seed = int(msg["seed"]) if msg.get("seed") is not None else _random_seed()
                try:
                    session = GameSession(
                        deck=msg.get("deck", "vanilla"),
                        bot=msg.get("bot", "rule"),
                        seed=seed,
                        lang=msg.get("lang", "zh"),
                        sid=sid,
                    )
                except SessionError as e:
                    log.warning("[%s] 开局被拒: %s | 请求=%s", sid, e, msg)
                    await ws.send_json({"type": "error", "message": str(e)})
                    continue
                state = session.start_state()
                log.info(
                    "[%s] 开局 deck=%s bot=%s seed=%s lang=%s",
                    sid, session.deck, session.bot, session.seed, session.lang,
                )
                log.debug("[%s]   · %s", sid, summarize(state))
                await ws.send_json({"type": "state", **state})
            elif mtype == "lang":
                if session is None:
                    await _reject(ws, sid, "还没开局（先发 start）", msg)
                    continue
                lang = msg.get("lang")
                if lang not in LANG_VALUES:
                    await _reject(ws, sid, f"未知语言: {lang}", msg)
                    continue
                log.debug("[%s] 切语言 %s → %s", sid, session.lang, lang)
                session.lang = lang  # 影响后续日志行；卡面双语言、前端即时切换
            elif mtype == "action":
                if session is None:
                    await _reject(ws, sid, "还没开局（先发 start）", msg)
                    continue
                index = msg.get("index")
                if not isinstance(index, int):
                    await _reject(ws, sid, "action 需要整数 index", msg)
                    continue
                try:
                    events, state = session.step_human(index)
                except SessionError as e:
                    # 动作被引擎/会话拒掉：连 repro 一起打，贴日志即可复现
                    log.warning("[%s] 动作被拒: %s | repro: %s", sid, e, session.repro())
                    await ws.send_json({"type": "error", "message": str(e)})
                    continue
                # 人类动作结果即时；bot 动作逐帧、每帧间隔 BOT_STEP_DELAY；
                # 最后一帧之后立即发终态 state（不留尾巴延迟）。
                for i, event in enumerate(events):
                    await ws.send_json(event)
                    if i < len(events) - 1:
                        await asyncio.sleep(BOT_STEP_DELAY)
                log.debug("[%s] > state %s", sid, summarize(state))
                await ws.send_json({"type": "state", **state})
            elif mtype == "clientlog":
                # 浏览器侧的报错转发到同一条终端流里——UI 崩了在服务端也看得见
                log.warning(
                    "[%s] [web] %s: %s%s",
                    sid,
                    msg.get("level", "error"),
                    msg.get("text", ""),
                    f"\n{msg['stack']}" if msg.get("stack") else "",
                )
            else:
                await _reject(ws, sid, f"未知消息类型: {mtype}", msg)
    except WebSocketDisconnect:
        log.info(
            "[%s] 断开%s", sid,
            f" | repro: {session.repro()}" if session is not None else "",
        )  # 玩家关页面，对局直接丢弃
    except Exception:
        # 服务端 bug：完整栈 + repro 落到终端，同时告知客户端（否则页面只会静默卡住）
        log.exception(
            "[%s] 服务端异常%s", sid,
            f" | repro: {session.repro()}" if session is not None else "",
        )
        with suppress(Exception):
            await ws.send_json({"type": "error", "message": "服务端异常，详见终端日志"})
        raise


async def _reject(ws: WebSocket, sid: str, message: str, msg: dict) -> None:
    """协议层拒绝：日志里带上原始消息（客户端只收到人话）。"""
    log.warning("[%s] 拒绝: %s | 消息=%s", sid, message, msg)
    await ws.send_json({"type": "error", "message": message})


def _random_seed() -> int:
    import secrets

    return secrets.randbits(32)


# 生产模式：vite build 产物存在就托管（挂最后，不遮 /ws 和 /healthz）
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
