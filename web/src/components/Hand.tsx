// 手牌区：重叠扇形排列，可出的卡高亮，选中上浮。

import type { EntityView, Lang } from "../types";
import { CardView } from "./CardView";

interface Props {
  hand: EntityView[];
  lang: Lang;
  selectableIndexes: Set<number>;
  selectedIndex: number | null;
  disabled?: boolean;
  onCardClick: (index: number) => void;
}

export function Hand({
  hand,
  lang,
  selectableIndexes,
  selectedIndex,
  disabled,
  onCardClick,
}: Props) {
  return (
    <div className={`hand ${disabled ? "is-disabled" : ""}`}>
      {hand.map((card, i) => (
        <CardView
          key={`${card.cardId}-${i}`}
          entity={card}
          size="hand"
          lang={lang}
          selectable={!disabled && selectableIndexes.has(i)}
          selected={selectedIndex === i}
          dimmed={disabled}
          onClick={() => !disabled && onCardClick(i)}
        />
      ))}
    </div>
  );
}
