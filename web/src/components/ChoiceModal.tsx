// 抉择/发现弹窗：引擎把待选项列成 kind="choose" 的合法动作，逐条展示。

import type { ActionView } from "../types";

interface Props {
  choices: ActionView[];
  onPick: (index: number) => void;
}

export function ChoiceModal({ choices, onPick }: Props) {
  return (
    <div className="modal-backdrop">
      <div className="modal choice-modal">
        <h3>选择一个选项</h3>
        <div className="choice-list">
          {choices.map((c) => (
            <button key={c.index} className="choice-btn" onClick={() => onPick(c.index)}>
              {c.description}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
