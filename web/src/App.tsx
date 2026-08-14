// 根组件：连接状态 → 大厅 → 对局。

import { Game } from "./components/Game";
import { Lobby } from "./components/Lobby";
import { useGame } from "./useGame";

export default function App() {
  const api = useGame();

  return (
    <div className="app">
      {api.status === "connecting" && (
        <div className="app-status">正在连接服务器…</div>
      )}
      {api.error && (
        <div className="toast" onClick={api.clearError} role="alert">
          ⚠ {api.error}（点击关闭）
        </div>
      )}
      {api.state ? <Game api={api} /> : <Lobby status={api.status} lastConfig={api.config} onStart={api.start} />}
    </div>
  );
}
