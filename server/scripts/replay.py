"""按终端日志里的 `repro:` 行原地重放一局，用于复现玩家报的 bug。

日志里每次动作被拒、断开或服务端异常都会打印一行 repro 参数，直接抄进来：

    .venv/bin/python server/scripts/replay.py --seed 3141592653 --deck vanilla \\
        --bot rule --lang zh --actions 2,0,5,1

重放走的是和 WS 服务端**完全同一条路径**（`GameSession.step_human`），
所以引擎、bot、随机数、日志行都一致。默认开 debug 日志——逐动作轨迹与
每帧局面摘要会打到终端。动作放完之后打印当下这帧的合法动作表（人类
下一步可选什么），便于接着往下试；`--actions -` 表示只开局不走动作。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ORANGE_WEB_LOG", "debug")
os.environ.setdefault("ORANGE_WEB_BOT_DELAY", "0")  # 重放不需要动画节奏

from app import _paths  # noqa: F401,E402
from app.debuglog import log, setup, summarize  # noqa: E402
from app.session import GameSession, SessionError  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="重放一局 orange-webstone 对局")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--deck", default="vanilla", choices=["vanilla", "random"])
    ap.add_argument("--bot", default="rule", choices=["rule", "greedy", "random"])
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--actions", default="-", help="人类动作下标，逗号分隔；- 表示只开局")
    args = ap.parse_args(argv)

    setup()
    session = GameSession(
        deck=args.deck, bot=args.bot, seed=args.seed, lang=args.lang, sid="replay"
    )
    state = session.start_state()
    log.info("[replay] 开局 %s", session.repro())
    log.info("[replay]   · %s", summarize(state))

    indices = [] if args.actions.strip() == "-" else [
        int(x) for x in args.actions.split(",") if x.strip()
    ]
    for n, index in enumerate(indices, 1):
        try:
            _events, state = session.step_human(index)
        except SessionError as e:
            # 复现成功：报错停在第几步、当时的合法动作表长什么样
            log.error("[replay] 第 %d 步 idx=%d 被拒: %s", n, index, e)
            _dump_legal(session, state)
            return 1
        if state["done"]:
            log.info("[replay] 第 %d 步后对局结束 winner=%s", n, state["winner"])
            return 0

    log.info("[replay] %d 步放完 | %s", len(indices), summarize(state))
    _dump_legal(session, state)
    return 0


def _dump_legal(session: GameSession, state: dict) -> None:
    """打印人类当前可选的合法动作（下标 = 前端点击发过来的 index）。

    描述走 `session._describe`，和对局日志/界面同一套人话措辞——
    `state["legal"]` 里的 `description` 是引擎的 Rust Debug 串，不好读。
    """
    if state["done"] or not state["humanTurn"]:
        return
    obs = session.env.observe()
    log.info("[replay] 当前合法动作：")
    for a in session.env.legal_actions():
        log.info("[replay]   %2d  %-9s %s", a.index, a.kind, session._describe(a, obs))


if __name__ == "__main__":
    raise SystemExit(main())
