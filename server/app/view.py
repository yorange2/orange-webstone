"""结构化观测 / 动作 → JSON 字典（发给浏览器的唯一形状）。

字段名转 camelCase，与 `web/src/types.ts` 一一对应；这里加一个字段
前端就要同步一份。观测里的卡名是引擎卡表的官方英文名（如 "Bloodfen
Raptor"）；`text` 从官方卡库 cards.json 查（见 cards_info.py，先按
card_id 再按卡名回退）。中文名映射是后续项。
"""

from __future__ import annotations

from hearthstone_os.env import Action, Env

from .cards_info import text_for

__all__ = ["board_event", "public_snapshot", "state_dict"]


def entity(e) -> dict:
    return {
        "entityId": e.entity_id,
        "cardId": e.card_id,
        "name": e.name,
        "text": text_for(e.card_id, e.name),
        "cost": e.cost,
        "attack": e.attack,
        "health": e.health,
        "canAttack": e.can_attack,
        "taunt": e.taunt,
        "divineShield": e.divine_shield,
        "stealth": e.stealth,
        "elusive": e.elusive,
        "windfury": e.windfury,
        "charge": e.charge,
        "frozen": e.frozen,
        "race": e.race,
        "playable": e.playable,
        "cardType": e.card_type,
    }


def player(p) -> dict:
    return {
        "heroHealth": p.hero_health,
        "heroArmor": p.hero_armor,
        "fatigue": p.fatigue,
        "heroAttack": p.hero_attack,
        "remainingMana": p.remaining_mana,
        "totalMana": p.total_mana,
        "handCount": p.hand_count,
        "deckCount": p.deck_count,
        "weaponAttack": p.weapon_attack,
        "weaponDurability": p.weapon_durability,
        "heroPowerUsable": p.hero_power_usable,
        "heroPowerCost": p.hero_power_cost,
        "questProgress": p.quest_progress,
        "questTarget": p.quest_target,
        "imbueCount": p.imbue_count,
        "corpses": p.corpses,
        "locationDurability": p.location_durability,
        "field": [entity(x) for x in p.field],
        "hand": [entity(x) for x in p.hand],
    }


def action(a: Action) -> dict:
    return {
        "index": a.index,
        "kind": a.kind,
        "cardIndex": a.card_index,
        "entityId": a.entity_id,
        "targetId": a.target_id,
        "description": a.description,
    }


def state_dict(env: Env, seat: int, *, seed: int, bot: str) -> dict:
    """完整 state 帧 + 合法动作，**永远以 seat（人类）为 me**。

    `env.observe()` 给的是当前行动方视角：正常的人类回合帧就是这个视角；
    但对局若在 bot 回合中结束（bot 的最后一手杀了你），行动方仍是 bot，
    观测是 bot 视角——不翻转的话结算画面会把 bot 当 me 渲染。
    """
    obs = env.observe()
    if env.current_player == seat:
        me_raw, opp_raw = obs.me, obs.opponent
    else:
        me_raw, opp_raw = obs.opponent, obs.me
    return {
        "turn": obs.turn,
        "done": obs.done,
        "winner": obs.winner,
        "awaitingChoice": obs.awaiting_choice,
        "me": player(me_raw),
        "opponent": player(opp_raw),
        "legal": [action(a) for a in env.legal_actions()],
        "seat": seat,
        "currentPlayer": env.current_player,
        "humanTurn": env.current_player == seat,
        "seed": seed,
        "bot": bot,
    }


def public_snapshot(env: Env, seat: int) -> dict:
    """公开局面帧（board 消息的 view 载荷），**永远以 seat（人类）为 me**。

    `env.observe()` 给的是当前行动方视角：bot 行动时是 bot 视角（要翻转
    并剥掉 bot 手牌）；但 bot 回合的最后一手（结束回合）之后、以及人类
    动作直接终局时，行动方已是人类——观测本身就是人类视角。两种分支
    都剥掉双方手牌条目（只留 handCount）：board 帧只承载公开信息，
    客户端的手牌永远取完整 state。

    不分支会怎样：bot 结束回合后的那一帧以 bot 为 me，前端逐帧比对
    会把双方全场误报成"被消灭"（两侧互相消失）。
    """
    obs = env.observe()
    if env.current_player == seat:
        me_raw, opp_raw = obs.me, obs.opponent
    else:
        me_raw, opp_raw = obs.opponent, obs.me
    me = player(me_raw)
    me["hand"] = []
    opp = player(opp_raw)
    opp["hand"] = []
    return {
        "turn": obs.turn,
        "done": obs.done,
        "winner": obs.winner,
        "me": me,
        "opponent": opp,
    }


def board_event(env: Env, seat: int, text: str) -> dict:
    """bot 回合每一步（含人类动作的即时结果）的 board 消息。"""
    return {"type": "board", "text": text, "view": public_snapshot(env, seat)}
