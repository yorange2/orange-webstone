"""卡面文字数据源：orange-stone 的官方卡库 `cards/cards.json`。

引擎的手写经典卡用自定义 id（`CLASSIC_001`、`NEUTRAL_*`），官方库用
Blizzard id（`CS2_172` 等）——orange-stone 自己的对拍测试
`generated_cards_match_handwritten` 就是**按名字**配对的，这里沿用同一
口径：先按 card_id 查，查不到按卡名回退。没有效果文本的白板卡返回空串
（前端不渲染）。文本是官方英文（HearthstoneJSON 无本地化字段）。

路径可用环境变量 `ORANGE_STONE_CARDS_JSON` 覆盖；默认按工作区布局解析
（本文件在 `<workspace>/orange-webstone/server/app/`，`parents[3]` 即工作区根）。
"""

import json
import os
import re
from functools import lru_cache
from pathlib import Path

__all__ = ["text_for"]

#: 官方文本带 HTML 标记（`<b>Taunt</b>`），前端纯文本渲染，剥掉标签。
_TAG_RE = re.compile(r"<[^>]+>")


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


@lru_cache(maxsize=1)
def _text_maps() -> tuple[dict[str, str], dict[str, str]]:
    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for card in json.loads(_cards_json_path().read_text()):
        text = card.get("text", "")
        if not text:
            continue
        by_id[card["id"]] = text
        by_name[card["name"]] = text
    return by_id, by_name


def text_for(card_id: str, name: str) -> str:
    """卡面效果文本（去 HTML 标记）；查不到返回空串。"""
    by_id, by_name = _text_maps()
    raw = by_id.get(card_id) or by_name.get(name, "")
    return _TAG_RE.sub("", raw)
