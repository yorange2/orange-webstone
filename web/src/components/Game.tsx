// 对局主界面：战场 + 手牌 + 目标选择状态机 + 日志 + 结算。
//
// 交互模型（与真实炉石一致的两段式）：
//   1. 点一个来源（手牌 / 己方随从 / 己方英雄 / 英雄技能）→ 选中；
//   2. 若该来源只剩唯一合法动作 → 直接打出；否则进入瞄准，合法目标
//      （对方随从 / 对方英雄）高亮，点击目标打出。
// 再点选中来源、点空白处或按 Esc 取消瞄准。
//
// 引擎的 ActionView 语义：play/hero_power 的 targetId=-1 表示无需目标，
// attack 的 targetId=-1 表示打脸；attack 的 entityId 不在己方场上 = 英雄攻击。
//
// bot 回合动画：`api.board` 是服务端逐动作推送的公开局面帧（bot 手牌已
// 剥掉）。棋盘渲染取 `board ?? state`——人类动作的即时结果与 bot 的每一步
// 都逐帧上屏；新随从有入场 pop 动画，掉血的实体（双方随从/英雄）红闪。
// 完整 state 只用于合法动作/手牌（board 帧里双方手牌都是空的）。

import { useEffect, useMemo, useRef, useState } from "react";
import type { ActionView, BoardView, EntityView, GameState } from "../types";
import type { GameApi } from "../useGame";
import { ChoiceModal } from "./ChoiceModal";
import { FieldRow } from "./FieldRow";
import { Hand } from "./Hand";
import { HeroPanel } from "./HeroPanel";

const HERO_ENTITY = -1; // 英雄攻击的占位"来源 id"（不在任何一方场上）

type Selection =
  | { kind: "play"; cardIndex: number }
  | { kind: "attack"; entityId: number }
  | { kind: "heroPower" }
  | null;

interface Flash {
  ids: Set<number>; // 掉血的实体（随从）
  meHero: boolean;
  oppHero: boolean;
}

const NO_FLASH: Flash = { ids: new Set(), meHero: false, oppHero: false };

export function Game({ api }: { api: GameApi }) {
  const state = api.state;
  const [sel, setSel] = useState<Selection>(null);
  const [boardView, setBoardView] = useState(false);
  const [flash, setFlash] = useState<Flash>(NO_FLASH);
  const prevBoardRef = useRef<BoardView | null>(null);

  // 每收到新一帧局面，旧的选择/结算覆盖必然过期，清掉；同时把完整
  // state 的公开部分设为下一帧 board 的比对基准——人类动作的即时结果帧
  // 要和动作前的局面比（伤害/消灭行才有出处），重开一局也不会误报
  useEffect(() => {
    setSel(null);
    setBoardView(false);
    prevBoardRef.current = state
      ? {
          turn: state.turn,
          done: state.done,
          winner: state.winner,
          me: state.me,
          opponent: state.opponent,
        }
      : null;
  }, [state]);

  // board 帧之间的效果比对：掉血闪烁 + 派生日志（伤害/消灭行）。
  // 战吼、法术这类效果不体现在动作日志里（日志只有"出 X"），逐帧比对
  // 把它们变成玩家看得见的行——"对方 X 受到 6 点伤害 / 被消灭"。
  useEffect(() => {
    const prev = prevBoardRef.current;
    const next = api.board;
    prevBoardRef.current = next;
    if (!prev || !next) return;

    // 派生日志：随从消灭与受伤（双方），英雄受伤（护甲也算）
    const lines: string[] = [];
    const effects = (aPrev: EntityView[], aNext: EntityView[], prefix: string) => {
      for (const p of aPrev) {
        const n = aNext.find((x) => x.entityId === p.entityId);
        if (!n) {
          lines.push(`${prefix}${p.name} 被消灭`);
        } else if (n.health < p.health) {
          lines.push(`${prefix}${n.name} 受到 ${p.health - n.health} 点伤害`);
        }
      }
    };
    effects(prev.opponent.field, next.opponent.field, "对方 ");
    effects(prev.me.field, next.me.field, "");
    const total = (p: { heroHealth: number; heroArmor: number }) =>
      p.heroHealth + p.heroArmor;
    const myLoss = total(prev.me) - total(next.me);
    if (myLoss > 0) lines.push(`你受到 ${myLoss} 点伤害`);
    const oppLoss = total(prev.opponent) - total(next.opponent);
    if (oppLoss > 0) lines.push(`对方英雄受到 ${oppLoss} 点伤害`);
    for (const line of lines) api.addLog(line);

    // 掉血闪烁（红闪 750ms）
    const ids = new Set<number>();
    const lostHealth = (a?: EntityView, b?: EntityView) =>
      !!a && !!b && a.entityId === b.entityId && b.health < a.health;
    const diffSide = (a: EntityView[], b: EntityView[]) => {
      for (const pa of a) for (const pb of b) if (lostHealth(pa, pb)) ids.add(pb.entityId);
    };
    diffSide(prev.me.field, next.me.field);
    diffSide(prev.opponent.field, next.opponent.field);
    if (ids.size || prev.me.heroHealth !== next.me.heroHealth ||
        prev.opponent.heroHealth !== next.opponent.heroHealth) {
      setFlash({
        ids,
        meHero: next.me.heroHealth < prev.me.heroHealth,
        oppHero: next.opponent.heroHealth < prev.opponent.heroHealth,
      });
      const t = setTimeout(() => setFlash(NO_FLASH), 750);
      return () => clearTimeout(t);
    }
  }, [api.board, api.addLog]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSel(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const derived = useMemo(() => computeDerived(state), [state]);

  if (!state) return <div className="board-wait">等待对局开始…</div>;

  // 棋盘渲染源：bot 回合的实时公开帧优先，否则完整 state
  const view = api.board ?? state;
  const me = view.me;
  const opponent = view.opponent;

  const choose = state.legal.filter((a) => a.kind === "choose");
  const endTurn = state.legal.find((a) => a.kind === "end_turn");
  const botActing = !state.humanTurn && !state.done;
  // 已发动作、下一帧 state 还没回来：bot 回合进行中，锁交互但不遮棋盘
  const acting = api.awaiting || botActing;

  // 选中来源的候选动作与可点目标
  let candidates: ActionView[] = [];
  if (sel && state.humanTurn && !state.awaitingChoice && !acting) {
    candidates = candidatesFor(sel, state, derived.myFieldIds);
  }
  const targetIds = new Set(
    candidates.filter((c) => c.targetId !== -1).map((c) => c.targetId),
  );
  // 打脸判定：引擎的"攻击英雄"目标是一个**正数实体 id**（英雄实体占全局
  // 实体槽，不在任何一方 field 里；field 只含随从）。targetId=-1 只表示
  // "无需目标"（play/技能直接打出）。所以脸 = 非 -1 且不在双方场上的目标。
  // （与 describe_action 的兜底口径一致：查不到场上匹配就渲染"对方英雄"；
  // 副作用是地点等非随从目标也会落到这里——引擎描述口径如此，MVP 接受。）
  const allFieldIds = useMemo(
    () => new Set([...me.field, ...opponent.field].map((e) => e.entityId)),
    [me.field, opponent.field],
  );
  const isFaceTarget = (c: ActionView) =>
    c.targetId >= 0 && !allFieldIds.has(c.targetId);
  const faceTargetable = candidates.some(isFaceTarget);

  const clickSource = (next: NonNullable<Selection>) => {
    if (!state.humanTurn || state.awaitingChoice || acting) return;
    if (sel && sameSelection(sel, next)) {
      setSel(null); // 再点一次取消
      return;
    }
    const cands = candidatesFor(next, state, derived.myFieldIds);
    if (cands.length === 0) {
      setSel(null); // 不可选的来源：清掉旧选择
      return;
    }
    // 攻击永远进入瞄准：选中 ≠ 出手（嘲讽逼出唯一目标时也不能点一下就
    // 打出去——真实炉石里选攻击者后必须再点目标）；出牌/英雄技能在只剩
    // 唯一合法动作时才直接打出
    if (cands.length === 1 && next.kind !== "attack") {
      api.sendAction(cands[0].index);
      return;
    }
    setSel(next); // 进入瞄准（含单目标的攻击）
  };

  const clickTarget = (targetId: number) => {
    if (!sel || !state.humanTurn) return;
    const cands = candidatesFor(sel, state, derived.myFieldIds);
    const hit = cands.find((c) => c.targetId === targetId);
    if (hit) {
      api.sendAction(hit.index);
      setSel(null);
    }
  };

  /** 点对方英雄（打脸）：命中目标是英雄实体 id 的候选动作。 */
  const clickFace = () => {
    if (!sel || !state.humanTurn) return;
    const cands = candidatesFor(sel, state, derived.myFieldIds);
    const hit = cands.find(isFaceTarget);
    if (hit) {
      api.sendAction(hit.index);
      setSel(null);
    }
  };

  const clickMinion = (side: "me" | "opponent") => (e: EntityView) => {
    if (sel) {
      if (targetIds.has(e.entityId)) clickTarget(e.entityId);
      return;
    }
    if (side === "me" && derived.attackableIds.has(e.entityId)) {
      clickSource({ kind: "attack", entityId: e.entityId });
    }
  };

  const damaged = (e: EntityView) => flash.ids.has(e.entityId) ? "is-damaged" : "";

  return (
    <div className="game-screen">
      <div className="board" data-live={api.board ? "1" : "0"}>
        {/* 对方：英雄面板 + 战场 */}
        <HeroPanel
          player={opponent}
          side="opponent"
          heroTargetable={faceTargetable}
          heroFlash={flash.oppHero}
          onHeroClick={() => faceTargetable && clickFace()}
        />
        <FieldRow
          side="opponent"
          minions={opponent.field}
          selectableIds={new Set()}
          selectedId={null}
          targetableIds={targetIds}
          dimmed={acting}
          damageClass={damaged}
          onMinionClick={clickMinion("opponent")}
        />

        {/* 中栏：回合信息 + 结束回合 */}
        <div className="mid-bar">
          <span className="turn-badge">
            第 {view.turn} 回合 {acting ? "· 对手回合…" : state.humanTurn ? "· 你的回合" : ""}
          </span>
          {state.humanTurn && !state.awaitingChoice && endTurn && (
            <button
              className="end-turn-btn"
              disabled={acting}
              onClick={() => api.sendAction(endTurn.index)}
            >
              结束回合
            </button>
          )}
        </div>

        {/* 己方：战场 + 英雄面板 */}
        <FieldRow
          side="me"
          minions={me.field}
          selectableIds={derived.attackableIds}
          selectedId={sel?.kind === "attack" ? sel.entityId : null}
          targetableIds={targetIds}
          dimmed={acting}
          damageClass={damaged}
          onMinionClick={clickMinion("me")}
        />
        <HeroPanel
          player={me}
          side="me"
          heroSelectable={derived.heroAttackable}
          heroSelected={sel?.kind === "attack" && sel.entityId === HERO_ENTITY}
          heroFlash={flash.meHero}
          onHeroClick={() => clickSource({ kind: "attack", entityId: HERO_ENTITY })}
          heroPowerSelectable={me.heroPowerUsable}
          heroPowerSelected={sel?.kind === "heroPower"}
          onHeroPowerClick={() => clickSource({ kind: "heroPower" })}
        />

        {/* 手牌：board 帧里没有，永远取完整 state */}
        <Hand
          hand={state.me.hand}
          selectableIndexes={derived.playableIndexes}
          selectedIndex={sel?.kind === "play" ? sel.cardIndex : null}
          disabled={!state.humanTurn || state.awaitingChoice || acting}
          onCardClick={(i) => clickSource({ kind: "play", cardIndex: i })}
        />
      </div>

      {/* 对手行动中横幅（发动作后 → 下一帧 state 之间） */}
      {acting && !state.done && <div className="board-awaiting">对方行动中…</div>}

      {/* 瞄准提示：选中来源后告诉玩家可以打脸 */}
      {sel && !acting && (
        <div className="targeting-hint">
          {faceTargetable
            ? "选择目标：点对方随从，或点对方英雄直接打脸（Esc 取消）"
            : "选择目标（Esc 取消）"}
        </div>
      )}

      {/* 日志栏 */}
      <aside className="log-panel">
        <h4>对局日志</h4>
        <ul>
          {api.log.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </aside>

      {/* 抉择弹窗 */}
      {state.awaitingChoice && choose.length > 0 && (
        <ChoiceModal choices={choose} onPick={(i) => api.sendAction(i)} />
      )}

      {/* 结算覆盖层 */}
      {state.done && !boardView && (
        <div className="modal-backdrop">
          <div className="modal result-modal">
            <h2>
              {state.winner === state.seat
                ? "🏆 胜利！"
                : state.winner === 0
                  ? "🤝 平局"
                  : "💀 失败"}
            </h2>
            <p className="result-meta">
              seed={state.seed} · 对手 {state.bot} · 共 {state.turn} 回合
            </p>
            <div className="result-actions">
              <button className="start-btn" onClick={api.restart}>
                再来一局
              </button>
              <button className="ghost-btn" onClick={() => setBoardView(true)}>
                查看场面
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------ 派生数据

interface Derived {
  myFieldIds: Set<number>;
  playableIndexes: Set<number>;
  attackableIds: Set<number>;
  heroAttackable: boolean;
}

function computeDerived(state: GameState | null): Derived {
  if (!state) {
    return {
      myFieldIds: new Set(),
      playableIndexes: new Set(),
      attackableIds: new Set(),
      heroAttackable: false,
    };
  }
  const legal = state.legal;
  const myFieldIds = new Set(state.me.field.map((e) => e.entityId));
  const playableIndexes = new Set(
    state.me.hand
      .filter((c) => c.playable)
      .map((_, i) => i)
      .filter((i) => legal.some((a) => a.kind === "play" && a.cardIndex === i)),
  );
  const attackableIds = new Set(
    state.me.field
      .filter((m) => m.canAttack)
      .map((m) => m.entityId)
      .filter((id) => legal.some((a) => a.kind === "attack" && a.entityId === id)),
  );
  const heroAttackable = legal.some(
    (a) => a.kind === "attack" && !myFieldIds.has(a.entityId),
  );
  return { myFieldIds, playableIndexes, attackableIds, heroAttackable };
}

function candidatesFor(
  sel: NonNullable<Selection>,
  state: GameState,
  myFieldIds: Set<number>,
): ActionView[] {
  const legal = state.legal;
  switch (sel.kind) {
    case "play":
      return legal.filter((a) => a.kind === "play" && a.cardIndex === sel.cardIndex);
    case "attack":
      return sel.entityId === HERO_ENTITY
        ? legal.filter((a) => a.kind === "attack" && !myFieldIds.has(a.entityId))
        : legal.filter((a) => a.kind === "attack" && a.entityId === sel.entityId);
    case "heroPower":
      return legal.filter((a) => a.kind === "hero_power");
  }
}

function sameSelection(a: Selection, b: Selection): boolean {
  if (!a || !b) return false;
  if (a.kind !== b.kind) return false;
  if (a.kind === "play" && b.kind === "play") return a.cardIndex === b.cardIndex;
  if (a.kind === "attack" && b.kind === "attack") return a.entityId === b.entityId;
  return true;
}
