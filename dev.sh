#!/bin/bash

# Torch-Markup 开发环境启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    Torch-Markup 开发环境${NC}"
echo -e "${BLUE}========================================${NC}"

# 生成新的 SECRET_KEY
generate_secret_key() {
    if command -v openssl &> /dev/null; then
        openssl rand -hex 32
    else
        # 如果没有 openssl，使用 Python
        python3 -c "import secrets; print(secrets.token_hex(32))"
    fi
}

# 更新 .env 文件中的 SECRET_KEY
update_secret_key() {
    local env_file="$BACKEND_DIR/.env"
    if [ -f "$env_file" ]; then
        local new_key=$(generate_secret_key)
        if grep -q "^SECRET_KEY=" "$env_file"; then
            # macOS 和 Linux 兼容的 sed
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s/^SECRET_KEY=.*/SECRET_KEY=$new_key/" "$env_file"
            else
                sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$new_key/" "$env_file"
            fi
        else
            echo "SECRET_KEY=$new_key" >> "$env_file"
        fi
        echo -e "${GREEN}✓ JWT SECRET_KEY 已更新，所有旧 token 已失效${NC}"
    fi
}

# 检查Python
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo -e "${RED}错误: 未找到Python，请先安装Python 3.10+${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Python: $($PYTHON_CMD --version)${NC}"
}

# 检查Node.js
check_node() {
    if ! command -v node &> /dev/null; then
        echo -e "${RED}错误: 未找到Node.js，请先安装Node.js${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Node.js: $(node --version)${NC}"
}

# 检查npm
check_npm() {
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}错误: 未找到npm${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ npm: $(npm --version)${NC}"
}

# 设置后端
setup_backend() {
    echo -e "\n${YELLOW}[1/4] 设置后端环境...${NC}"
    cd "$BACKEND_DIR"

    # 创建虚拟环境（如果不存在）
    if [ ! -d "venv" ]; then
        echo "创建Python虚拟环境..."
        $PYTHON_CMD -m venv venv
    fi

    # 激活虚拟环境
    source venv/bin/activate

    # 安装依赖
    echo "安装Python依赖..."
    pip install -r requirements.txt -q

    # 创建.env文件（如果不存在）
    if [ ! -f ".env" ]; then
        cp .env.example .env
        echo -e "${YELLOW}已创建 .env 文件，请根据需要修改数据库配置${NC}"
    fi

    echo -e "${GREEN}✓ 后端环境准备完成${NC}"
}

# 设置前端
setup_frontend() {
    echo -e "\n${YELLOW}[2/4] 设置前端环境...${NC}"
    cd "$FRONTEND_DIR"

    # 安装依赖（如果node_modules不存在或package.json更新）
    if [ ! -d "node_modules" ]; then
        echo "安装前端依赖..."
        npm install
    fi

    echo -e "${GREEN}✓ 前端环境准备完成${NC}"
}

# 启动后端
start_backend() {
    echo -e "\n${YELLOW}[3/4] 启动后端服务...${NC}"
    cd "$BACKEND_DIR"
    source venv/bin/activate

    # 后台启动uvicorn
    nohup uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 > "$ROOT_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$ROOT_DIR/.backend.pid"

    echo -e "${GREEN}✓ 后端已启动 (PID: $BACKEND_PID)${NC}"
    echo -e "  API地址: ${BLUE}http://localhost:8000${NC}"
    echo -e "  API文档: ${BLUE}http://localhost:8000/docs${NC}"
}

# 启动前端
start_frontend() {
    echo -e "\n${YELLOW}[4/4] 启动前端服务...${NC}"
    cd "$FRONTEND_DIR"

    # 后台启动vite
    nohup npm run dev > "$ROOT_DIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$ROOT_DIR/.frontend.pid"

    # 等待前端启动
    sleep 3

    echo -e "${GREEN}✓ 前端已启动 (PID: $FRONTEND_PID)${NC}"
    echo -e "  前端地址: ${BLUE}http://localhost:5173${NC}"
}

# 停止服务
stop_services() {
    echo -e "\n${YELLOW}停止服务...${NC}"

    if [ -f "$ROOT_DIR/.backend.pid" ]; then
        BACKEND_PID=$(cat "$ROOT_DIR/.backend.pid")
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID 2>/dev/null || true
            echo -e "${GREEN}✓ 后端已停止${NC}"
        fi
        rm -f "$ROOT_DIR/.backend.pid"
    fi

    if [ -f "$ROOT_DIR/.frontend.pid" ]; then
        FRONTEND_PID=$(cat "$ROOT_DIR/.frontend.pid")
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill $FRONTEND_PID 2>/dev/null || true
            echo -e "${GREEN}✓ 前端已停止${NC}"
        fi
        rm -f "$ROOT_DIR/.frontend.pid"
    fi

    # 清理可能残留的进程
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true

    # 清除所有 JWT token (更新 SECRET_KEY)
    update_secret_key
}

# 信号处理 - Ctrl+C
cleanup_on_exit() {
    echo -e "\n${YELLOW}收到退出信号，正在清理...${NC}"
    stop_services
    echo -e "${GREEN}所有服务已停止，JWT token 已清除${NC}"
    exit 0
}

# 注册信号处理
trap cleanup_on_exit SIGINT SIGTERM

# 显示状态
show_status() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${GREEN}Torch-Markup 已启动!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e ""
    echo -e "前端地址: ${BLUE}http://localhost:5173${NC}"
    echo -e "后端API:  ${BLUE}http://localhost:8000${NC}"
    echo -e "API文档:  ${BLUE}http://localhost:8000/docs${NC}"
    echo -e ""
    echo -e "默认管理员账户: ${YELLOW}admin / 123456${NC}"
    echo -e ""
    echo -e "日志文件:"
    echo -e "  后端: $ROOT_DIR/backend.log"
    echo -e "  前端: $ROOT_DIR/frontend.log"
    echo -e ""
    echo -e "停止服务: ${YELLOW}$0 stop${NC} 或 ${YELLOW}Ctrl+C${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# 前台运行模式 - 等待用户 Ctrl+C
run_foreground() {
    show_status
    echo -e "\n${YELLOW}服务运行中，按 Ctrl+C 停止...${NC}"
    # 等待信号
    while true; do
        sleep 1
    done
}

# 后台运行模式 - 启动后立即返回
run_background() {
    show_status
    echo -e "\n${GREEN}服务已在后台启动${NC}"
    echo -e "使用 ${YELLOW}$0 stop${NC} 停止服务"
    echo -e "使用 ${YELLOW}$0 logs${NC} 查看日志"
}

# 主函数
main() {
    case "${1:-}" in
        ""|fg|foreground)
            # 默认或 fg：前台运行
            check_python
            check_node
            check_npm
            setup_backend
            setup_frontend
            start_backend
            start_frontend
            run_foreground
            ;;
        start|bg|background)
            # start/bg：后台运行
            check_python
            check_node
            check_npm
            setup_backend
            setup_frontend
            start_backend
            start_frontend
            run_background
            ;;
        stop)
            stop_services
            echo -e "${GREEN}所有服务已停止${NC}"
            ;;
        restart)
            stop_services
            sleep 2
            check_python
            check_node
            check_npm
            setup_backend
            setup_frontend
            start_backend
            start_frontend
            run_foreground
            ;;
        status)
            echo -e "${YELLOW}检查服务状态...${NC}"
            if [ -f "$ROOT_DIR/.backend.pid" ] && kill -0 $(cat "$ROOT_DIR/.backend.pid") 2>/dev/null; then
                echo -e "${GREEN}✓ 后端运行中 (PID: $(cat "$ROOT_DIR/.backend.pid"))${NC}"
            else
                echo -e "${RED}✗ 后端未运行${NC}"
            fi
            if [ -f "$ROOT_DIR/.frontend.pid" ] && kill -0 $(cat "$ROOT_DIR/.frontend.pid") 2>/dev/null; then
                echo -e "${GREEN}✓ 前端运行中 (PID: $(cat "$ROOT_DIR/.frontend.pid"))${NC}"
            else
                echo -e "${RED}✗ 前端未运行${NC}"
            fi
            ;;
        logs)
            echo -e "${YELLOW}=== 后端日志 (最后20行) ===${NC}"
            tail -20 "$ROOT_DIR/backend.log" 2>/dev/null || echo "无日志"
            echo -e "\n${YELLOW}=== 前端日志 (最后20行) ===${NC}"
            tail -20 "$ROOT_DIR/frontend.log" 2>/dev/null || echo "无日志"
            ;;
        *)
            echo "用法: $0 [命令]"
            echo ""
            echo "命令:"
            echo "  (无参数) - 启动所有服务（前台运行，Ctrl+C 停止）"
            echo "  start   - 启动所有服务（后台运行）"
            echo "  stop    - 停止所有服务并清除 JWT token"
            echo "  restart - 重启所有服务（前台运行）"
            echo "  status  - 查看服务状态"
            echo "  logs    - 查看日志"
            echo ""
            echo "别名:"
            echo "  fg      - 同 (无参数)，前台运行"
            echo "  bg      - 同 start，后台运行"
            echo ""
            echo "提示: 前台运行时使用 Ctrl+C 可以停止服务并自动清除所有 JWT token"
            exit 1
            ;;
    esac
}

main "$@"
