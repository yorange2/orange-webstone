"""把 orange-reinforcement 接到 sys.path（hearthstone_os 复用）。

orange-webstone 只依赖 orange-stone 的 wheel + orange-reinforcement 的
hearthstone_os 包（纯 Python，无 torch 依赖）。hearthstone_os 没有打包
成可安装发行版，这里按工作区布局解析路径；可用环境变量
`ORANGE_REINFORCEMENT_PATH` 覆盖（部署时指到 checkout 目录）。

默认解析：本文件在 `<workspace>/orange-webstone/server/app/` 下，
`parents[3]` 即工作区根，hearthstone_os 在 `<workspace>/orange-reinforcement/`。
"""

import os
import sys
from pathlib import Path


def ensure_orange_reinforcement_path() -> None:
    env = os.environ.get("ORANGE_REINFORCEMENT_PATH")
    if env:
        path = Path(env)
    else:
        path = Path(__file__).resolve().parents[3] / "orange-reinforcement"
    s = str(path)
    if s not in sys.path:
        sys.path.insert(0, s)


ensure_orange_reinforcement_path()
