// 一方战场（从左到右一排随从）。

import type { EntityView } from "../types";
import { CardView } from "./CardView";

interface Props {
  side: "me" | "opponent";
  minions: EntityView[];
  selectableIds: Set<number>;
  selectedId: number | null;
  targetableIds: Set<number>;
  dimmed?: boolean;
  /** 逐实体的附加状态类（掉血闪烁等）。 */
  damageClass?: (e: EntityView) => string;
  onMinionClick: (e: EntityView) => void;
}

export function FieldRow({
  side,
  minions,
  selectableIds,
  selectedId,
  targetableIds,
  dimmed,
  damageClass,
  onMinionClick,
}: Props) {
  return (
    <div className={`field-row field-${side}`}>
      {minions.length === 0 && (
        <span className="field-empty">{side === "me" ? "你的战场" : "对方战场"}</span>
      )}
      {minions.map((m) => (
        <CardView
          key={m.entityId}
          entity={m}
          size="field"
          selectable={selectableIds.has(m.entityId)}
          selected={selectedId === m.entityId}
          targetable={targetableIds.has(m.entityId)}
          dimmed={dimmed}
          extraClass={damageClass?.(m)}
          onClick={() => onMinionClick(m)}
        />
      ))}
    </div>
  );
}
