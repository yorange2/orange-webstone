#!/bin/sh
# 一键起后端（开发模式，--reload + 调试日志）。前端另开终端：cd web && npm run dev
# 日志级别可覆盖：ORANGE_WEB_LOG=info sh server/scripts/dev.sh
set -e
cd "$(dirname "$0")/../.."   # server/scripts/ → orange-webstone/
export ORANGE_WEB_LOG="${ORANGE_WEB_LOG:-debug}"
exec .venv/bin/uvicorn app.main:app --app-dir server --port 8000 --reload
