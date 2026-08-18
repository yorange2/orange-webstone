"""卡面文字数据源：orange-stone 的官方卡库 `cards/cards.json`（英文）+
本仓库 `data/cards_zh.json`（zhCN 切片，`scripts/fetch_zh.py` 生成）。

引擎的手写经典卡用自定义 id（`CLASSIC_001`、`NEUTRAL_*`），官方库用
Blizzard id（`CS2_172` 等）——orange-stone 自己的对拍测试
`generated_cards_match_handwritten` 就是**按名字**配对的，这里沿用同一
口径：先按 card_id 查，查不到按卡名回退。中文同理：zh 表按 id 命中；
自定义 id 走英文名 → 官方 id → 中文名/文本。没有效果文本的白板卡返回空串
（前端不渲染）。文本是官方英文/官方简体中文（HearthstoneJSON zhCN）。

HearthstoneJSON 的数值用 `$25`/`#8` 占位符标记（值的位置随语言变化），
渲染前剥掉。路径可用环境变量覆盖；en 默认按工作区布局解析（本文件在
`<workspace>/orange-webstone/server/app/`，`parents[3]` 即工作区根），
zh 默认在 `orange-webstone/server/data/`（独立仓库自带数据）。
"""

import json
import os
import re
from functools import lru_cache
from pathlib import Path

__all__ = ["text_for", "zh_for"]

#: 官方文本带 HTML 标记（`<b>Taunt</b>`），前端纯文本渲染，剥掉标签。
_TAG_RE = re.compile(r"<[^>]+>")
#: 数值占位符（`$25`、`#8` → `25`、`8`），en/zh 两路文本都有。
_PLACEHOLDER_RE = re.compile(r"[$#](?=\d)")


def _cards_json_path() -> Path:
    env = os.environ.get("ORANGE_STONE_CARDS_JSON")
    if env:
        return Path(env)
    return (
        Path(__file__).resolve().parents[3]
        / "orange-stone"
        / "cards"
        / "cards.json"
    )


def _cards_zh_json_path() -> Path:
    env = os.environ.get("WEBSTONE_CARDS_ZH_JSON")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / "data" / "cards_zh.json"


@lru_cache(maxsize=1)
def _en_maps() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """英文表：`(id → text, name → text, name → id)`。

    text 两张表只收录有文本的卡（白板卡查不到即空串）；name → id 收录
    全部卡（白板卡也要中文名）。同一卡名多个 id（如 Lord Jaraxxus 的
    本体/英雄/CORE 版）按文件顺序后者胜出。
    """
    by_id_text: dict[str, str] = {}
    by_name_text: dict[str, str] = {}
    by_name_id: dict[str, str] = {}
    for card in json.loads(_cards_json_path().read_text()):
        by_name_id[card["name"]] = card["id"]
        text = card.get("text", "")
        if not text:
            continue
        by_id_text[card["id"]] = text
        by_name_text[card["name"]] = text
    return by_id_text, by_name_text, by_name_id


@lru_cache(maxsize=1)
def _zh_maps() -> tuple[dict[str, str], dict[str, str]]:
    """中文表：`(id → name, id → text)`（白板卡无 text 条目）。

    数据文件形状是 `{id: {name, text}}`——id 键覆盖引擎 `all_card_ids()`
    与 orange-stone cards.json 的并集（见 fetch_zh.py）。
    """
    by_name: dict[str, str] = {}
    by_text: dict[str, str] = {}
    for cid, card in json.loads(_cards_zh_json_path().read_text()).items():
        by_name[cid] = card["name"]
        by_text[cid] = card.get("text", "")
    return by_name, by_text


def _clean(raw: str) -> str:
    """去 HTML 标记与数值占位符。"""
    return _PLACEHOLDER_RE.sub("", _TAG_RE.sub("", raw))


def text_for(card_id: str, name: str) -> str:
    """卡面效果文本（官方英文，去 HTML 标记与占位符）；查不到返回空串。"""
    by_id_text, by_name_text, _ = _en_maps()
    raw = by_id_text.get(card_id) or by_name_text.get(name, "")
    return _clean(raw)


def zh_for(card_id: str, name: str) -> tuple[str, str]:
    """中文卡名与卡面文本 `(name_zh, text_zh)`；查不到返回 `("", "")`。"""
    _, _, en_by_name_id = _en_maps()
    zh_name, zh_text = _zh_maps()
    official_id = card_id if card_id in zh_name else en_by_name_id.get(name, "")
    return (
        zh_name.get(official_id, ""),
        _clean(zh_text.get(official_id, "")),
    )
