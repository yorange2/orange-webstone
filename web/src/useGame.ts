// WS 连接与对局状态的 hook：一个连接一局对局。
// 断线重连策略：MVP 不自动重连（对局不可恢复），断线回大厅并提示。

import { useCallback, useEffect, useRef, useState } from "react";
import type { BoardView, GameConfig, GameState, ServerMessage } from "./types";

export type ConnStatus = "connecting" | "open" | "closed";

export interface GameApi {
  status: ConnStatus;
  state: GameState | null;
  /** bot 回合逐动作的公开局面帧；收到新 state 时清空。 */
  board: BoardView | null;
  log: string[];
  error: string | null;
  config: GameConfig | null;
  /** 已发动作、还没收到下一帧 state（bot 回合进行中）。 */
  awaiting: boolean;
  start: (cfg: GameConfig) => void;
  sendAction: (index: number) => void;
  restart: () => void;
  clearError: () => void;
  /** 追加一条客户端派生的日志（如逐帧比对出的伤害/消灭行）。 */
  addLog: (text: string) => void;
}

const MAX_LOG = 100;

export function useGame(): GameApi {
  const [status, setStatus] = useState<ConnStatus>("connecting");
  const [state, setState] = useState<GameState | null>(null);
  const [board, setBoard] = useState<BoardView | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<GameConfig | null>(null);
  const [awaiting, setAwaiting] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss://" : "ws://";
    const ws = new WebSocket(`${proto}${location.host}/ws`);
    wsRef.current = ws;
    ws.onopen = () => setStatus("open");
    ws.onclose = () => setStatus("closed");
    ws.onmessage = (ev) => {
      const msg: ServerMessage = JSON.parse(ev.data);
      if (msg.type === "state") {
        const { type: _t, ...rest } = msg;
        setState(rest);
        setBoard(null);
        setAwaiting(false);
      } else if (msg.type === "board") {
        setBoard(msg.view);
        setLog((prev) => [...prev.slice(-(MAX_LOG - 1)), msg.text]);
      } else if (msg.type === "log") {
        setLog((prev) => [...prev.slice(-(MAX_LOG - 1)), msg.text]);
      } else if (msg.type === "error") {
        setError(msg.message);
        setAwaiting(false); // 动作被拒：还是人类回合
        setBoard(null);
      }
    };
    return () => ws.close();
  }, []);

  const send = useCallback((obj: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(obj));
    }
  }, []);

  const start = useCallback(
    (cfg: GameConfig) => {
      setConfig(cfg);
      setState(null);
      setBoard(null);
      setLog([]);
      setError(null);
      send({ type: "start", ...cfg });
    },
    [send],
  );

  const sendAction = useCallback(
    (index: number) => {
      setAwaiting(true);
      send({ type: "action", index });
    },
    [send],
  );

  const restart = useCallback(() => {
    if (config) start(config);
  }, [config, start]);

  const addLog = useCallback(
    (text: string) => setLog((prev) => [...prev.slice(-(MAX_LOG - 1)), text]),
    [],
  );

  return {
    status,
    state,
    board,
    log,
    error,
    config,
    awaiting,
    start,
    sendAction,
    restart,
    clearError: () => setError(null),
    addLog,
  };
}
