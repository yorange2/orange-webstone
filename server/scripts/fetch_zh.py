#!/usr/bin/env python3
"""抓取 hearthstonejson 的 zhCN 本地化 dump，生成 `server/data/cards_zh.json`
（webstone 的中文卡名/卡面文本数据源）。

覆盖口径 = **引擎的全部 id**（orange-stone wheel 的 `GameEnv.all_card_ids()`）
∪ orange-stone `cards/cards.json` 的全部 id：

- 官方 id（CORE_*/EDR_* 等）直接命中 zhCN dump；
- 引擎手写 id（`CLASSIC_001`、`NEUTRAL_R26` 等）在 dump 里没有——用一张
  只含该卡的小对局（`GameEnv(seed, deck=[id])`）向引擎要英文名，再经
  enUS 全量 dump 的 name→id 命中 zhCN 条目（与 orange-stone 自己的对拍
  `generated_cards_match_handwritten` 同口径：按名字配对）。

产物 `cards_zh.json`：`{引擎/官方 id: {name, text}}`（text 非空才带），
按 id 排序。运行时（`app/cards_info.py`）按引擎 id 直接查，无需再做名字
配对。需要 orange-webstone 的 .venv（装好 orange-stone wheel）。

Sources（同版本同源的 `latest`，id 天然对齐）:
    https://api.hearthstonejson.com/v1/latest/zhCN/cards.json   （全量：含
        附魔/英雄技能/英雄等；collectible-only 会漏 426 个引擎 id）
    https://api.hearthstonejson.com/v1/latest/enUS/cards.json   （名字配对用）

Usage:
    python3 server/scripts/fetch_zh.py                # 下载 + 生成
    python3 server/scripts/fetch_zh.py --zh F --en E  # 用已有 dump（不联网）

orange-stone 卡库路径可用环境变量 `ORANGE_STONE_CARDS_JSON` 覆盖（与
`app/cards_info.py` 同口径）。
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ZH_URL = "https://api.hearthstonejson.com/v1/latest/zhCN/cards.json"
SOURCE_EN_URL = "https://api.hearthstonejson.com/v1/latest/enUS/cards.json"
USER_AGENT = "orange-webstone fetch_zh.py (card data refresh)"

#: 引擎自造 id 的衍生物（hearthstonejson 里没有对应条目），人工给中文名。
#: 名字沿用官方同义卡的简体翻译（如 Onyxian Whelp → 奥妮克希亚雏龙）。
MANUAL_ZH: dict[str, dict] = {
    "CORE_SW_429t": {"name": "乌龟"},
    "EDR_233t1": {"name": "森林狼"},
    "EDR_263t": {"name": "巨狼"},
    "EDR_813t": {"name": "蚂蚁"},
    "EDR_820t": {"name": "恐惧之种"},
    "END_002t": {"name": "匕首"},
    "EX1_170t": {"name": "奥妮克希亚雏龙"},
    "LEGENDARY_004t": {"name": "芬克尔·恩霍恩"},
    "TIME_017t": {"name": "坦克"},
}

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"  # server/data/


def en_cards_json_path() -> Path:
    import os

    env = os.environ.get("ORANGE_STONE_CARDS_JSON")
    if env:
        return Path(env)
    # server/scripts/fetch_zh.py → parents[2] = 工作区根（与 cards_info.py 一致）
    return SCRIPT_DIR.parents[2] / "orange-stone" / "cards" / "cards.json"


def _download(url: str, local: str | None) -> tuple[bytes, str]:
    """下载 dump 或读本地文件；返回 (raw, sha256)。"""
    if local:
        raw = Path(local).read_bytes()
    else:
        import urllib.request

        print(f"downloading {url} ...")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
    return raw, hashlib.sha256(raw).hexdigest()


def _engine_id_names(ids: list[str]) -> dict[str, str]:
    """引擎 id → 英文名：用只含该卡的小对局向引擎要名字（没有名字注册表）。"""
    import orange_stone

    names: dict[str, str] = {}
    for cid in ids:
        env = orange_stone.GameEnv(seed=1, deck=[cid])
        hand = env.structured_observation().me.hand
        if hand:
            names[cid] = hand[0].name
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zh", help="本地 zhCN cards.json dump（跳过下载）")
    parser.add_argument("--en", help="本地 enUS cards.json dump（跳过下载）")
    args = parser.parse_args()

    zh_raw, zh_sha = _download(SOURCE_ZH_URL, args.zh)
    en_raw, en_sha = _download(SOURCE_EN_URL, args.en)
    zh_dump = json.loads(zh_raw)
    en_dump = json.loads(en_raw)
    print(f"zhCN dump: {len(zh_dump)} cards, sha256={zh_sha}")
    print(f"enUS dump: {len(en_dump)} cards, sha256={en_sha}")

    zh_by_id = {c["id"]: c for c in zh_dump}
    en_name_to_id: dict[str, str] = {}
    for c in en_dump:
        en_name_to_id.setdefault(c["name"], c["id"])

    def zh_entry(card: dict) -> dict:
        entry = {"name": card["name"]}
        if card.get("text"):
            entry["text"] = card["text"]
        return entry

    entries: dict[str, dict] = {}

    # 1) orange-stone 卡库的官方 id（含引擎不直接出场的衍生物/附魔等）
    en_path = en_cards_json_path()
    en_ids = {c["id"] for c in json.loads(en_path.read_text())}
    for cid in sorted(en_ids):
        if cid in zh_by_id:
            entries[cid] = zh_entry(zh_by_id[cid])

    # 2) 引擎的全部 id：官方 id 直接命中；手写 id 按英文名配对
    import orange_stone

    engine_ids = sorted(orange_stone.GameEnv.all_card_ids())
    engine_names = _engine_id_names(engine_ids)
    matched = missed = 0
    for eid in engine_ids:
        if eid in zh_by_id:
            entries[eid] = zh_entry(zh_by_id[eid])
            matched += 1
            continue
        if eid in MANUAL_ZH:
            entries[eid] = MANUAL_ZH[eid]
            matched += 1
            continue
        name = engine_names.get(eid)
        real_id = en_name_to_id.get(name or "")
        if real_id and real_id in zh_by_id:
            entries[eid] = zh_entry(zh_by_id[real_id])
            matched += 1
        else:
            missed += 1
            print(f"WARN: {eid} ({name!r}) 无法配对中文，运行时回落英文")
    print(f"engine ids: {len(engine_ids)} 命中 {matched}，未命中 {missed}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / "cards_zh.json"
    out.write_text(
        json.dumps(
            {k: entries[k] for k in sorted(entries)},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (DATA_DIR / "SOURCE_ZH.md").write_text(
        f"# Chinese card text data (zhCN)\n\n"
        f"- Source URLs: `{SOURCE_ZH_URL}` (zhCN), `{SOURCE_EN_URL}` (enUS, 名字配对)\n"
        f"- Fetched: {fetched}\n"
        f"- zhCN sha256: `{zh_sha}`\n"
        f"- enUS sha256: `{en_sha}`\n"
        f"- Entries: {len(entries)} = engine `all_card_ids()` ({len(engine_ids)})"
        f" ∪ orange-stone cards.json ({len(en_ids)})\n\n"
        f"Re-fetch: `python3 server/scripts/fetch_zh.py`\n",
        encoding="utf-8",
    )
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(entries)} entries) + SOURCE_ZH.md")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
