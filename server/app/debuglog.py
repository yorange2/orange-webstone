"""命令行调试日志：一局对局在终端里的完整可读轨迹。

设计目标是**日志本身就是 bug 报告**——玩家把终端这一段贴出来，读的人
不用追问就能知道：什么配置开的局（`deck/bot/seed`）、人类每一步选了哪个
下标、bot 回合逐步做了什么、每一帧双方的血量/手牌/场面、错误出在哪一步。
配上末尾的 `repro:` 行还能直接用 `scripts/replay.py` 原地复现。

级别由 `ORANGE_WEB_LOG` 控制（`debug` | `info` | `warning`，默认 `info`；
`scripts/dev.sh` 默认开 `debug`）：

  - info  : 连接/开局/错误/断开（每局十来行，生产也能开）
  - debug : 再加每个动作、每帧局面摘要（逐步轨迹）

日志走自己的 logger（`propagate=False`），不混进 uvicorn 的 access log。
"""

from __future__ import annotations

import itertools
import logging
import os
import sys

__all__ = ["log", "next_session_id", "setup", "summarize"]

log = logging.getLogger("webstone")

_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING}
_counter = itertools.count(1)


def next_session_id() -> str:
    """连接标识（`ws1`、`ws2`…）：多标签页同时开局时用它区分交错的行。"""
    return f"ws{next(_counter)}"


def setup() -> None:
    """按 `ORANGE_WEB_LOG` 配置 handler；重复调用只配置一次（--reload 会重跑）。"""
    if log.handlers:
        return
    level = _LEVELS.get(os.environ.get("ORANGE_WEB_LOG", "info").lower(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(message)s", "%H:%M:%S"))
    log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False


def summarize(frame: dict) -> str:
    """一帧局面压成一行：双方血量/护甲、手牌数、场面随从、法力、回合与终局。

    `frame` 是 `view.state_dict()` 或 `view.public_snapshot()` 的输出——
    board 帧没有 `legal`/`humanTurn`，缺字段就略过，两种帧共用这一个格式。
    """
    parts = [f"turn={frame['turn']}"]
    if "humanTurn" in frame:
        parts.append(f"human={'T' if frame['humanTurn'] else 'F'}")
    parts.append(_side("me", frame["me"]))
    parts.append(_side("opp", frame["opponent"]))
    if "legal" in frame:
        parts.append(f"legal={len(frame['legal'])}")
    if frame.get("done"):
        parts.append(f"DONE winner={frame.get('winner')}")
    return " ".join(parts)


def _side(tag: str, p: dict) -> str:
    """`me=30+2hp 5手 2场[3/2,2/1] 3/4法力`——场面带每只随从的攻/血。"""
    field = ",".join(f"{m['attack']}/{m['health']}" for m in p["field"])
    armor = f"+{p['heroArmor']}" if p["heroArmor"] else ""
    return (
        f"{tag}={p['heroHealth']}{armor}hp {p['handCount']}手 "
        f"{len(p['field'])}场[{field}] {p['remainingMana']}/{p['totalMana']}法力"
    )
