// 卡面渲染：手牌与场上共用。卡图没有数据源，用卡牌类型配色 + 卡名（按
// 语言 zhCN/英文）+ 关键词角标表达。size="hand" 稍大（手牌可点），
// size="field" 稍小。

import type { EntityView, Lang } from "../types";

interface Props {
  entity: EntityView;
  size: "hand" | "field";
  lang: Lang;
  selectable?: boolean;
  selected?: boolean;
  targetable?: boolean;
  dimmed?: boolean;
  /** 附加状态类名（如掉血闪烁 is-damaged）。 */
  extraClass?: string;
  onClick?: () => void;
}

const KEYWORDS: [keyof EntityView, string][] = [
  ["taunt", "嘲讽"],
  ["divineShield", "圣盾"],
  ["stealth", "潜行"],
  ["elusive", "扰咒"],
  ["windfury", "风怒"],
  ["charge", "冲锋"],
];

const TYPE_CLASS = ["minion", "spell", "weapon", "hero"] as const;

export function CardView({
  entity,
  size,
  lang,
  selectable,
  selected,
  targetable,
  dimmed,
  extraClass,
  onClick,
}: Props) {
  const name = lang === "zh" ? entity.nameZh || entity.name : entity.name;
  const text = lang === "zh" ? entity.textZh || entity.text : entity.text;
  const type = TYPE_CLASS[entity.cardType] ?? "minion";
  const isMinion = entity.cardType === 0;
  const cls = [
    "card",
    `card-${size}`,
    `card-${type}`,
    entity.taunt ? "is-taunt" : "",
    entity.frozen ? "is-frozen" : "",
    entity.divineShield ? "is-shield" : "",
    entity.stealth ? "is-stealth" : "",
    selectable ? "is-selectable" : "",
    selected ? "is-selected" : "",
    targetable ? "is-targetable" : "",
    dimmed ? "is-dimmed" : "",
    !entity.playable && size === "hand" ? "is-unplayable" : "",
    entity.canAttack && size === "field" && !dimmed ? "is-ready" : "",
    extraClass ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  const tooltip = text ? `${name}\n${text}` : name;

  return (
    <div
      className={cls}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      title={tooltip}
    >
      <span className="card-cost">{entity.cost}</span>
      <span className="card-name">{name}</span>
      {size === "hand" && text && <span className="card-text">{text}</span>}
      {isMinion && (
        <>
          <span className="card-atk">{entity.attack}</span>
          <span className="card-hp">{entity.health}</span>
        </>
      )}
      <span className="card-keywords">
        {KEYWORDS.filter(([k]) => entity[k]).map(([k, label]) => (
          <i key={k}>{label}</i>
        ))}
      </span>
    </div>
  );
}
