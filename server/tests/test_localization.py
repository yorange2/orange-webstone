"""中文卡名/卡面文本（zhCN）与语言切换的测试。

数据：orange-webstone/server/data/cards_zh.json（scripts/fetch_zh.py 按
orange-stone cards.json 的 id 集合切片，2038 条全量覆盖）。
"""

from __future__ import annotations

import os

os.environ.setdefault("ORANGE_WEB_BOT_DELAY", "0")

import sys
from pathlib import Path

# 测试直跑（python -m pytest）时也能找到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import _paths  # noqa: F401
from app.cards_info import text_for, zh_for
from app.main import app
from app.session import GameSession, SessionError


# ------------------------------------------------------------ 中文数据查找


def test_zh_id_hit():
    # 官方 id 直接命中；白板卡无文本
    assert zh_for("CS2_172", "Bloodfen Raptor") == ("血沼迅猛龙", "")
    # HTML 标记剥掉（<b>嘲讽</b> → 嘲讽）
    assert zh_for("CS2_121", "Frostwolf Grunt") == ("霜狼步兵", "嘲讽")


def test_zh_name_fallback():
    # 引擎手写 id 查不到 → 英文名 → 官方 id → 中文
    assert zh_for("CLASSIC_001", "Bloodfen Raptor") == ("血沼迅猛龙", "")
    assert zh_for("NEUTRAL_B05", "Frostwolf Grunt") == ("霜狼步兵", "嘲讽")


def test_zh_missing_returns_empty():
    assert zh_for("NOPE_000", "No Such Card") == ("", "")


def test_placeholder_cleanup_en():
    # HearthstoneJSON 的数值占位符（$4 / #5）渲染前剥掉
    assert "$" not in text_for("BT_235", "") and "#" not in text_for("CORE_AT_055", "")


def test_placeholder_cleanup_zh():
    name, text = zh_for("CORE_AT_037", "")
    assert name == "活体根须"
    assert "造成2点伤害" in text and "$" not in text
    assert "恢复5点生命值" in zh_for("CORE_AT_055", "")[1]


def test_entity_view_has_both_languages():
    """entity 每帧带双语言：name/text（英文）+ nameZh/textZh（中文）。"""
    session = GameSession(deck="random", bot="random", seed=70)
    state = session.start_state()
    for side in ("me", "opponent"):
        for zone in ("hand", "field"):
            for card in state[side][zone]:
                assert isinstance(card["nameZh"], str)
                assert isinstance(card["textZh"], str)
    # 全池随机卡组的卡名应有中文（id 直接命中 zh 切片）
    assert all(card["nameZh"] for card in state["me"]["hand"])


# ------------------------------------------------------------ 日志行本地化


def _first_play_action(session: GameSession):
    """人类的第一个可出牌动作（同一 seed 对局完全确定）。

    起手可能没有 1 费卡，就空过几回合攒水晶——step_human 会一并跑完
    bot 回合，回到人类回合再看。"""
    for _ in range(20):
        obs = session.env.observe()
        legal = session.env.legal_actions()
        for a in legal:
            if a.kind == "play":
                return a, obs
        end_turn = next(a for a in legal if a.kind == "end_turn")
        _, state = session.step_human(end_turn.index)
        assert not state["done"], "攒水晶途中对局不应结束"
    raise AssertionError("20 回合内没有可出的牌")


def test_describe_uses_lang():
    """同一 seed 的两局起手相同：zh 局日志行用中文卡名，en 局用英文。"""
    zh_session = GameSession(deck="random", bot="random", seed=73, lang="zh")
    en_session = GameSession(deck="random", bot="random", seed=73, lang="en")
    a_zh, obs_zh = _first_play_action(zh_session)
    a_en, obs_en = _first_play_action(en_session)
    card_zh = obs_zh.me.hand[a_zh.card_index]
    card_en = obs_en.me.hand[a_en.card_index]
    assert card_zh.name == card_en.name
    name_zh, _ = zh_for(card_zh.card_id, card_zh.name)
    assert name_zh, "出牌卡应可映射中文"
    line_zh = zh_session._describe(a_zh, obs_zh)
    line_en = en_session._describe(a_en, obs_en)
    assert line_zh.startswith(f"出 {name_zh}({card_zh.cost}费)")
    assert line_en.startswith(f"出 {card_en.name}({card_en.cost}费)")


def test_describe_zh_appends_zh_text():
    """zh 日志行附中文卡面文本（战吼等效果不可见就全丢了）。"""
    session = GameSession(deck="random", bot="random", seed=73, lang="zh")
    a, obs = _first_play_action(session)
    card = obs.me.hand[a.card_index]
    _, text_zh = zh_for(card.card_id, card.name)
    line = session._describe(a, obs)
    if text_zh:
        assert f"——{text_zh.replace(chr(10), ' ').strip()}" in line


def test_lang_validation():
    try:
        GameSession(deck="vanilla", bot="random", seed=74, lang="fr")
        raise AssertionError("非法语言应当抛 SessionError")
    except SessionError:
        pass


# ------------------------------------------------------------ WS 协议


def test_ws_start_lang_and_switch():
    """start 带 lang；对局中 lang 消息切语言：非法值报错、合法值后对局照常。"""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            # start 的 lang 非法 → error
            ws.send_json({"type": "start", "deck": "vanilla", "bot": "random",
                          "seed": 75, "lang": "fr"})
            assert ws.receive_json()["type"] == "error"
            # 合法 start（默认 zh 也可以显式带）
            ws.send_json({"type": "start", "deck": "vanilla", "bot": "random",
                          "seed": 75, "lang": "zh"})
            state = ws.receive_json()
            assert state["type"] == "state" and not state["done"]
            # 对局中切语言：非法报错、合法继续
            ws.send_json({"type": "lang", "lang": "de"})
            assert ws.receive_json()["type"] == "error"
            ws.send_json({"type": "lang", "lang": "en"})
            ws.send_json({"type": "action", "index": state["legal"][0]["index"]})
            while True:
                msg = ws.receive_json()
                if msg["type"] == "error":
                    raise AssertionError(f"服务端报错: {msg}")
                if msg["type"] == "state":
                    assert isinstance(msg["turn"], int)
                    break
