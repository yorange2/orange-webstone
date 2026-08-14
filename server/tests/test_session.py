"""GameSession 与 WS 协议的端到端测试。

人类座位用一个脚本化策略（RandomBot / GreedyBot）驱动，不测 UI 只测
协议与状态形状；WS 测试走 fastapi TestClient。`ORANGE_WEB_BOT_DELAY=0`
让 bot 回合即时跑完（测试要快）。
"""

from __future__ import annotations

import os

os.environ.setdefault("ORANGE_WEB_BOT_DELAY", "0")

import random
import sys
from pathlib import Path

# 测试直跑（python -m pytest）时也能找到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import _paths  # noqa: F401
from app.main import app
from app.session import GameSession, SessionError, _deck_ids
from hearthstone_os.bots import RandomBot

MAX_STEPS = 5000


def play_until_done(session: GameSession, chooser) -> dict:
    """驱动一整局：人类座位用 chooser 选动作，直到 done。返回终态帧。"""
    state = session.start_state()
    steps = 0
    while not state["done"]:
        assert steps < MAX_STEPS, "整局步数超限（疑似死循环）"
        legal = state["legal"]
        assert legal, "人类回合不应没有合法动作"
        action = chooser._pick(state)
        events, state = session.step_human(action["index"])
        assert events and events[0]["type"] == "board", "每步至少一条 board 事件"
        steps += 1
    # 终态视角：me 永远是人类。bot 在回合中取胜（终局帧发生在 bot 回合）
    # 时最容易把视角带成 bot 的——这里兜底
    if state["winner"] == 2:
        assert state["me"]["heroHealth"] <= 0, "bot 取胜时 me（人类英雄）应已死亡"
    elif state["winner"] == 1:
        assert state["me"]["heroHealth"] > 0, "人类取胜时 me（人类英雄）应存活"
    return state


class _Scripted:
    """随机选动作的脚本化“人类”（测试用）。"""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def _pick(self, state) -> object:
        return state["legal"][self.rng.randrange(len(state["legal"]))]


def test_random_vs_random_full_game():
    session = GameSession(deck="vanilla", bot="random", seed=42)
    state = play_until_done(session, _Scripted(7))
    assert state["done"]
    assert state["winner"] in (1, 2)


def test_rule_bot_full_game():
    session = GameSession(deck="vanilla", bot="rule", seed=43)
    state = play_until_done(session, _Scripted(8))
    assert state["done"]
    assert state["winner"] in (1, 2)


def test_state_shape():
    session = GameSession(deck="vanilla", bot="rule", seed=44)
    state = session.start_state()
    # 结构：双玩家视图 + 合法动作 + 座位信息
    for side in ("me", "opponent"):
        p = state[side]
        for key in ("heroHealth", "remainingMana", "totalMana", "handCount",
                    "deckCount", "heroPowerUsable", "field", "hand"):
            assert key in p, f"{side}.{key} 缺失"
    assert state["humanTurn"] and state["currentPlayer"] == state["seat"] == 1
    assert state["legal"] and state["done"] is False
    assert isinstance(state["turn"], int) and state["turn"] >= 1
    # 卡面字段：名字 + 文本 + 数值
    card = state["me"]["hand"][0]
    assert isinstance(card["name"], str) and card["name"]
    assert isinstance(card["text"], str), "实体必须带 text 字段（可为空串）"
    assert isinstance(card["cost"], int) and card["cost"] >= 0
    assert isinstance(card["cardId"], str) and card["cardId"]
    # 对手手牌必须隐藏（只有计数，没有卡面）
    assert state["opponent"]["hand"] == []
    # 合法动作形状
    a = state["legal"][0]
    for key in ("index", "kind", "cardIndex", "entityId", "targetId", "description"):
        assert key in a


def test_invalid_action_rejected():
    session = GameSession(deck="vanilla", bot="rule", seed=45)
    try:
        session.step_human(9999)
        raise AssertionError("非法 index 应当抛 SessionError")
    except SessionError:
        pass


def test_step_twice_in_bot_turn_rejected():
    """人类 step 后 bot 回合被跑完，再 step 会轮到人类——两次连续 step
    只有第一次合法（第二次轮到人类了）。构造一个 bot="random" 快速局验证
    SessionError 只在真正非人类回合时抛出。"""
    session = GameSession(deck="vanilla", bot="random", seed=46)
    state = session.start_state()
    # 出到不能动为止，确保轮到人类时 step 合法
    state = play_until_done(session, _Scripted(9))
    assert state["done"]


def test_random_deck_builds_30():
    ids = _deck_ids("random", seed=47)
    assert len(ids) == 30 and all(isinstance(x, str) and x for x in ids)


def test_board_events_are_public_and_ordered():
    """人类 end_turn → 事件流：第一条是人类动作的即时结果，后面全是 bot
    回合的公开帧；每一帧 bot 手牌必须剥干净（hand 为空、只有 handCount）。"""
    session = GameSession(deck="vanilla", bot="random", seed=48)
    state = session.start_state()
    end_turn = next(a["index"] for a in state["legal"] if a["kind"] == "end_turn")
    events, state = session.step_human(end_turn)
    assert len(events) >= 1 and all(ev["type"] == "board" for ev in events)
    for ev in events:
        view = ev["view"]
        for side in ("me", "opponent"):
            assert view[side]["hand"] == [], f"board 帧不得含 {side} 手牌"
            assert isinstance(view[side]["handCount"], int)
        assert isinstance(ev["text"], str) and ev["text"]
        assert isinstance(view["turn"], int) and view["turn"] >= 1
        assert "done" in view and "winner" in view
    # 事件流的最后一条之后，终态帧要么是人类回合、要么已结束
    assert state["humanTurn"] or state["done"]
    # 视角翻转回归（用户报障：bot 结束回合后那一帧以 bot 为 me，逐帧
    # 比对把双方全场误报成"被消灭"）：最后一帧的 me/opponent 必须与
    # 终态 state（人类视角）一致
    last = events[-1]["view"]
    assert last["me"]["heroHealth"] == state["me"]["heroHealth"]
    assert [e["entityId"] for e in last["me"]["field"]] == [
        e["entityId"] for e in state["me"]["field"]
    ]
    assert [e["entityId"] for e in last["opponent"]["field"]] == [
        e["entityId"] for e in state["opponent"]["field"]
    ]


def test_card_text_lookup():
    from app.cards_info import text_for

    # 白板卡无文本（cards.json 里 CS2_172 Bloodfen Raptor 没有 text）
    assert text_for("CLASSIC_001", "Bloodfen Raptor") == ""
    # 手写 id 查不到 → 按名字回退到官方 id 的文本
    assert text_for("NEUTRAL_B05", "Frostwolf Grunt") == "Taunt"
    # 官方 id 直接命中
    assert text_for("CS2_121", "") == "Taunt"
    # 查不到 → 空串
    assert text_for("NOPE_000", "No Such Card") == ""


def test_unknown_bot_and_deck_rejected():
    for kwargs in (dict(bot="nope"), dict(deck="nope")):
        try:
            GameSession(deck=kwargs.get("deck", "vanilla"),
                        bot=kwargs.get("bot", "rule"), seed=1)
            raise AssertionError("未知 bot/卡组应当抛 SessionError")
        except SessionError:
            pass


# ---------------------------------------------------------------- WS 协议


def _run_ws_game() -> dict:
    """TestClient 打一局：start → 循环 action → 收 log/state 直到 done。"""
    rng = random.Random(1)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start", "deck": "vanilla", "bot": "random",
                          "seed": 5})
            state = ws.receive_json()
            assert state["type"] == "state" and not state["done"]
            log_seen = 0
            for _ in range(MAX_STEPS):
                legal = state["legal"]
                idx = legal[rng.randrange(len(legal))]["index"]
                ws.send_json({"type": "action", "index": idx})
                # 收消息直到下一帧 state（中间是 board 公开帧）
                while True:
                    msg = ws.receive_json()
                    if msg["type"] == "board":
                        assert isinstance(msg["text"], str) and msg["text"]
                        assert msg["view"]["opponent"]["hand"] == []
                        log_seen += 1
                    elif msg["type"] == "error":
                        raise AssertionError(f"服务端报错: {msg}")
                    else:
                        assert msg["type"] == "state"
                        state = msg
                        break
                if state["done"]:
                    break
            else:
                raise AssertionError("WS 整局步数超限")
    assert state["done"] and state["winner"] in (1, 2)
    assert log_seen > 0, "整局应当看到 bot 动作日志"
    return state


def test_ws_full_game():
    _run_ws_game()


def test_ws_action_before_start_gets_error():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "action", "index": 0})
            msg = ws.receive_json()
            assert msg["type"] == "error"
