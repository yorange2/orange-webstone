// 大厅：选卡组、选对手、填 seed，点开始。

import { useState } from "react";
import type { GameConfig } from "../types";
import { BOT_LABELS, DECK_LABELS } from "../types";
import type { ConnStatus } from "../useGame";

interface Props {
  status: ConnStatus;
  lastConfig: GameConfig | null;
  onStart: (cfg: GameConfig) => void;
}

export function Lobby({ status, lastConfig, onStart }: Props) {
  const [deck, setDeck] = useState<GameConfig["deck"]>(lastConfig?.deck ?? "vanilla");
  const [bot, setBot] = useState<GameConfig["bot"]>(lastConfig?.bot ?? "rule");
  const [seedText, setSeedText] = useState(
    lastConfig?.seed == null ? "" : String(lastConfig.seed),
  );
  const ready = status === "open";

  const submit = () => {
    if (!ready) return;
    const seed = seedText.trim() === "" ? null : Number(seedText);
    if (seed != null && (!Number.isInteger(seed) || seed < 0)) {
      setSeedText("");
      return;
    }
    onStart({ deck, bot, seed });
  };

  return (
    <div className="lobby">
      <h1>🪨 orange-webstone</h1>
      <p className="lobby-sub">网页版炉石模拟器 · 引擎：orange-stone</p>

      <label className="lobby-field">
        <span>你的卡组</span>
        <select value={deck} onChange={(e) => setDeck(e.target.value as GameConfig["deck"])}>
          {(Object.keys(DECK_LABELS) as GameConfig["deck"][]).map((d) => (
            <option key={d} value={d}>
              {DECK_LABELS[d]}
            </option>
          ))}
        </select>
      </label>

      <label className="lobby-field">
        <span>对手</span>
        <select value={bot} onChange={(e) => setBot(e.target.value as GameConfig["bot"])}>
          {(Object.keys(BOT_LABELS) as GameConfig["bot"][]).map((b) => (
            <option key={b} value={b}>
              {BOT_LABELS[b]}
            </option>
          ))}
        </select>
      </label>

      <label className="lobby-field">
        <span>随机种子（留空随机）</span>
        <input
          type="text"
          value={seedText}
          placeholder="如 42"
          onChange={(e) => setSeedText(e.target.value.trim())}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
      </label>

      <button className="start-btn" disabled={!ready} onClick={submit}>
        {ready ? "开始对局" : status === "connecting" ? "连接中…" : "服务器未连接"}
      </button>
      {!ready && <p className="lobby-hint">后端没起来？在 orange-webstone 下跑 server/scripts/dev.sh</p>}
    </div>
  );
}
