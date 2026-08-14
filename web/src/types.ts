// 与 server/app/view.py 一一对应的协议类型。
// 改一边必须同步另一边。

/** 场上/手牌实体（引擎 EntityView 的 JSON 形态）。 */
export interface EntityView {
  entityId: number;
  cardId: string;
  name: string;
  /** 卡面效果文本（官方英文，白板卡为空串）。 */
  text: string;
  cost: number;
  attack: number;
  health: number;
  canAttack: boolean;
  taunt: boolean;
  divineShield: boolean;
  stealth: boolean;
  elusive: boolean;
  windfury: boolean;
  charge: boolean;
  frozen: boolean;
  race: number;
  playable: boolean;
  /** 0=随从 1=法术 2=武器 3=英雄 */
  cardType: number;
}

/** 一方玩家视图（当前行动方视角：me 带手牌，opponent 手牌为空）。 */
export interface PlayerView {
  heroHealth: number;
  heroArmor: number;
  fatigue: number;
  heroAttack: number;
  remainingMana: number;
  totalMana: number;
  handCount: number;
  deckCount: number;
  weaponAttack: number;
  weaponDurability: number;
  heroPowerUsable: boolean;
  heroPowerCost: number;
  questProgress: number;
  questTarget: number;
  imbueCount: number;
  corpses: number;
  locationDurability: number;
  field: EntityView[];
  hand: EntityView[];
}

/** 合法动作（引擎 ActionView 的 JSON 形态）。 */
export interface ActionView {
  index: number;
  kind: "end_turn" | "play" | "attack" | "hero_power" | "choose";
  cardIndex: number;
  entityId: number;
  targetId: number;
  description: string;
}

/** 一帧局面（state 消息的载荷）。 */
export interface GameState {
  turn: number;
  done: boolean;
  /** 0=未结束/平局，1=P1，2=P2 */
  winner: number;
  awaitingChoice: boolean;
  me: PlayerView;
  opponent: PlayerView;
  legal: ActionView[];
  seat: number;
  currentPlayer: number;
  humanTurn: boolean;
  seed: number;
  bot: string;
}

/** bot 回合的公开局面帧（board 消息载荷）：双方手牌都剥掉（只有计数），
 *  客户端沿用自己上一帧完整 state 里的手牌渲染。 */
export interface BoardView {
  turn: number;
  done: boolean;
  winner: number;
  me: PlayerView;
  opponent: PlayerView;
}

export type ServerMessage =
  | ({ type: "state" } & GameState)
  | { type: "board"; text: string; view: BoardView }
  | { type: "log"; text: string }
  | { type: "error"; message: string };

export interface GameConfig {
  deck: "vanilla" | "random";
  bot: "rule" | "greedy" | "random";
  seed: number | null;
}

export const DECK_LABELS: Record<GameConfig["deck"], string> = {
  vanilla: "白板卡组（15 张 ×2）",
  random: "随机卡组（全池 30 张）",
};

export const BOT_LABELS: Record<GameConfig["bot"], string> = {
  rule: "规则对手（有斩杀与交换）",
  greedy: "贪婪对手（无脑打脸）",
  random: "随机对手",
};
