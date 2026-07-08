#!/bin/sh
set -e

cd /app

APP_MODE="${APP_MODE:-api}"
echo "[Entrypoint] Document QA Bot starting (APP_MODE=${APP_MODE})"

case "${APP_MODE}" in
  api)
    export API_HOST="${API_HOST:-0.0.0.0}"
    export API_PORT="${API_PORT:-8000}"
    echo "[Entrypoint] FastAPI → ${API_HOST}:${API_PORT}"
    exec python api_server.py
    ;;
  gradio)
    export GRADIO_HOST="${GRADIO_HOST:-0.0.0.0}"
    export GRADIO_PORT="${GRADIO_PORT:-7860}"
    echo "[Entrypoint] Gradio → ${GRADIO_HOST}:${GRADIO_PORT}"
    exec python main.py
    ;;
  *)
    echo "[Entrypoint] Unknown APP_MODE: ${APP_MODE} (use 'api' or 'gradio')"
    exit 1
    ;;
esac
