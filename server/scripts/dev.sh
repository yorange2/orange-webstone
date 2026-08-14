#!/bin/sh
# 一键起后端（开发模式，--reload）。前端另开终端：cd web && npm run dev
set -e
cd "$(dirname "$0")/../.."   # server/scripts/ → orange-webstone/
exec .venv/bin/uvicorn app.main:app --app-dir server --port 8000 --reload
