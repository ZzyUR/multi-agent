#!/bin/bash
# 一键启动开发环境：后端 API + 前端 Vite
# 用法：bash start_dev.sh [--mock]
#   默认使用真实模式（读取 backend/.env：真实大模型 + 真实搜索）
#   --mock 使用假数据（离线测试，无需 API key）

set -e
cd "$(dirname "$0")"

USE_MOCK=false
if [[ "$1" == "--mock" ]]; then
  USE_MOCK=true
  echo ">>> Mock 模式：使用假数据（离线测试，无需 API key）"
else
  echo ">>> 真实模式：读取 backend/.env（真实大模型 + 真实搜索）"
fi

# 启动后端
echo ""
echo "[1/2] 启动 FastAPI 后端 (port 8000)..."
cd backend
if $USE_MOCK; then
  USE_MOCK_MODEL=true USE_MOCK_SEARCH=true PYTHONPATH=. python3.12 api_server.py &
else
  PYTHONPATH=. python3.12 api_server.py &
fi
BACKEND_PID=$!
cd ..

# 等待后端就绪
echo "     等待后端启动..."
for i in $(seq 1 10); do
  if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "     ✓ 后端就绪 http://localhost:8000"
    break
  fi
  sleep 1
done

# 启动前端
echo ""
echo "[2/2] 启动 Vite 前端 (port 5173)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "======================================="
echo "  DeepResearch 开发环境已启动"
echo "  前端: http://localhost:5173"
echo "  API:  http://localhost:8000/docs"
echo "======================================="
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待 Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
