// 英雄面板：血量/护甲/攻击、法力水晶、牌堆与手牌数、武器、英雄技能按钮。

import type { PlayerView } from "../types";

interface Props {
  player: PlayerView;
  side: "me" | "opponent";
  heroSelectable?: boolean;
  heroSelected?: boolean;
  heroTargetable?: boolean;
  /** 掉血闪烁。 */
  heroFlash?: boolean;
  onHeroClick?: () => void;
  heroPowerSelectable?: boolean;
  heroPowerSelected?: boolean;
  onHeroPowerClick?: () => void;
}

export function HeroPanel({
  player,
  side,
  heroSelectable,
  heroSelected,
  heroTargetable,
  heroFlash,
  onHeroClick,
  heroPowerSelectable,
  heroPowerSelected,
  onHeroPowerClick,
}: Props) {
  const total = player.heroHealth + player.heroArmor;
  return (
    <div className={`hero-panel hero-${side}`}>
      <div
        className={[
          "hero-portrait",
          heroSelectable ? "is-selectable" : "",
          heroSelected ? "is-selected" : "",
          heroTargetable ? "is-targetable" : "",
          heroFlash ? "is-damaged" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        onClick={onHeroClick}
        role={onHeroClick ? "button" : undefined}
        title={side === "me" ? "你的英雄" : "对方英雄"}
      >
        <span className="hero-health">{total}</span>
        {player.heroAttack > 0 && <span className="hero-atk">⚔{player.heroAttack}</span>}
        {heroTargetable && <span className="hero-target-mark">🎯</span>}
      </div>

      <div className="hero-side">
        {side === "me" && (
          <div className="mana-crystals" title={`法力水晶 ${player.remainingMana}/${player.totalMana}`}>
            {Array.from({ length: player.totalMana }, (_, i) => (
              <i key={i} className={i < player.remainingMana ? "filled" : ""} />
            ))}
            <span className="mana-text">
              {player.remainingMana}/{player.totalMana}
            </span>
          </div>
        )}
        {player.weaponDurability > 0 && (
          <span className="chip weapon-chip">
            🗡 {player.weaponAttack}/{player.weaponDurability}
          </span>
        )}
        {side === "me" && player.heroPowerUsable && (
          <button
            className={[
              "hero-power-btn",
              heroPowerSelectable ? "is-selectable" : "",
              heroPowerSelected ? "is-selected" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            onClick={onHeroPowerClick}
          >
            技能（{player.heroPowerCost}费）
          </button>
        )}
      </div>

      <div className="hero-counts">
        <span title="牌堆剩余">🂠{player.deckCount}</span>
        <span title="手牌数">🖐{player.handCount}</span>
      </div>
    </div>
  );
}
