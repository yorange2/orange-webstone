"""一局对局的驱动核心（纯同步、无 IO，WS 层包在外面）。

结构照搬 `hearthstone_os/play.py` 的人机循环：`Env(deck, seed)` + 座位表
`{1: 人类, 2: bot}`。人类固定在 P1（先手），bot 在 P2（后手 + 幸运币）。

关键设计：bot 回合**逐动作**跑（而不是让引擎内置 bot 一个 step 打完），
每一步都产出一个 `board` 事件——一条动作日志 + 一帧**公开局面**（bot
视角剥掉手牌，见 `view.public_snapshot`）。浏览器据此逐动作渲染动画，
对手的每一步玩家都看得见，同时 bot 手牌永远不外泄。bot 回合结束回到
人类回合时再发一帧完整的人类视角 state。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from . import _paths  # noqa: F401  接 orange-reinforcement 到 sys.path
from hearthstone_os.bots import BOTS
from hearthstone_os.decks import random_deck, vanilla
from hearthstone_os.env import Env, describe_action

from .cards_info import text_for, zh_for
from .view import board_event, state_dict

__all__ = ["GameSession", "SessionError"]

#: 大厅可选对手（键 = WS start 消息里的 bot 字段）
BOTS_AVAILABLE: dict[str, str] = {"rule": "规则", "greedy": "贪婪", "random": "随机"}

#: 卡面/日志语言（键 = WS start / lang 消息里的 lang 字段）
LANG_VALUES: tuple[str, ...] = ("zh", "en")

MAX_GAME_STEPS = 5000  # 引擎自身的兜底（rl/env.rs），这里只是保险


class SessionError(Exception):
    """对局流程错误（发给客户端当 error 消息）。"""


def _deck_ids(deck: str, seed: int) -> list[str]:
    """卡组选择：vanilla = 15 张白板/关键词卡 ×2；random = 全池随机 30 张。"""
    if deck == "vanilla":
        return vanilla()
    if deck == "random":
        return random_deck(random.Random(seed))
    raise SessionError(f"未知卡组: {deck}（可选 vanilla | random）")


@dataclass
class GameSession:
    deck: str
    bot: str
    seed: int
    lang: str = "zh"  # 卡面/日志语言，默认中文；对局中可经 WS lang 消息切换
    seat: int = 1  # 人类固定 P1

    def __post_init__(self) -> None:
        if self.bot not in BOTS_AVAILABLE:
            raise SessionError(f"未知对手: {self.bot}")
        if self.lang not in LANG_VALUES:
            raise SessionError(f"未知语言: {self.lang}（可选 zh | en）")
        self.env = Env(deck=_deck_ids(self.deck, self.seed), seed=self.seed)
        self._bot = BOTS[self.bot](seed=self.seed)
        self._steps = 0

    # ------------------------------------------------------------ 查询

    @property
    def human_turn(self) -> bool:
        return self.env.current_player == self.seat

    def start_state(self) -> dict:
        """开局后的人类视角帧（人类 P1 先手，初始就是人类回合）。"""
        return state_dict(self.env, self.seat, seed=self.seed, bot=self.bot)

    # ------------------------------------------------------------ 驱动

    def step_human(self, index: int) -> tuple[list[dict], dict]:
        """执行人类动作，然后跑完整个 bot 回合。

        返回 `(事件流, 终态帧)`：事件流是 `board` 消息列表——第一条是
        人类这一步动作的**即时**结果（自己的随从立刻上场），后面是 bot
        回合逐动作的公开局面帧。终态帧永远是人类视角的完整 state
        （对局结束或轮回到人类回合时）。非法 index 抛 `SessionError`。

        动作与观测都**即时取数**：客户端可能带着旧一帧的 index 竞态重发，
        校验必须对着当下这帧的合法动作表做；描述动作也必须是 step 前的
        观测（出牌后手牌已经变了）。
        """
        if not self.human_turn:
            raise SessionError("现在不是你的回合")
        legal = self.env.legal_actions()
        if not (0 <= index < len(legal)):
            raise SessionError(f"非法动作下标: {index}")
        action = legal[index]
        line = self._describe(action, self.env.observe())  # step 前的观测
        self._step(index)
        events = [board_event(self.env, self.seat, line)]

        # bot 回合逐动作跑，每个动作一帧公开局面
        while not self.env.done and not self.human_turn:
            obs = self.env.observe()
            legal = self.env.legal_actions()
            bot_action = self._bot.choose(obs, legal)
            self._step(bot_action.index)
            events.append(board_event(self.env, self.seat, self._describe(bot_action, obs)))

        return events, state_dict(self.env, self.seat, seed=self.seed, bot=self.bot)

    def _describe(self, action, obs) -> str:
        """动作日志行；出牌附上卡面效果文本（否则战吼类效果完全不可见）。

        卡面文本是官方公开信息，不涉及 bot 手牌泄漏。lang=zh 时把行内
        嵌的英文卡名替换为中文名（describe_action 的模板本身已是中文），
        并附中文卡面文本。
        """
        line = describe_action(action, obs)
        if action.kind == "play" and 0 <= action.card_index < len(obs.me.hand):
            card = obs.me.hand[action.card_index]
            text = (zh_for(card.card_id, card.name)[1] or text_for(card.card_id, card.name)) \
                if self.lang == "zh" else text_for(card.card_id, card.name)
            text = text.replace("\n", " ").strip()
            if text:
                line += f"——{text}"
        if self.lang == "zh":
            line = self._localize_names(line, obs)
        return line

    @staticmethod
    def _localize_names(line: str, obs) -> str:
        """把行内嵌的英文卡名替换成中文名。

        只替换本动作可能涉及的实体（我方手牌 + 双方场上）的名字，
        长名先换避免子串误伤（如 Skeleton 是 Skeleton Knight 的前缀）。
        """
        names: set[tuple[str, str]] = set()
        for ent in obs.me.hand + obs.me.field + obs.opponent.field:
            name_zh, _ = zh_for(ent.card_id, ent.name)
            if name_zh and name_zh != ent.name:
                names.add((ent.name, name_zh))
        for en, zh in sorted(names, key=lambda p: -len(p[0])):
            line = line.replace(en, zh)
        return line

    def _step(self, index: int) -> None:
        self.env.step(index)
        self._steps += 1
        if self._steps > MAX_GAME_STEPS:
            raise SessionError("超过对局步数上限（5000），判为异常")
