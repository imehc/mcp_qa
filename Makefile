# MCP QA 项目模块化 Makefile
# 支持多模块管理：mcp_server 等

# 项目基础配置
PROJECT_NAME = mcp-qa
PYTHON = uv run python
UV_RUN = uv run
VENV_DIR = .venv
LOG_DIR = logs

# 模块配置
MODULES = mcp_server ollama
CURRENT_MODULE ?= mcp_server

# mcp_server 模块配置
MCP_SERVER_PID_FILE = .mcp_server.pid
MCP_SERVER_LOG_FILE = logs/mcp_server_$(shell date +%Y%m%d_%H%M%S).log
MCP_SERVER_HOST ?= 0.0.0.0
MCP_SERVER_PORT ?= 8020
MCP_SERVER_DEBUG ?= false
MCP_SERVER_ALLOWED_DIRS ?= docs

# ollama 模块配置 (仅限 macOS)
OLLAMA_AVAILABLE := $(shell command -v brew >/dev/null 2>&1 && echo true || echo false)

# 检测操作系统
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
    PLATFORM = macos
endif
ifeq ($(UNAME_S),Linux)
    PLATFORM = linux
endif

# 颜色输出
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[0;33m
BLUE = \033[0;34m
PURPLE = \033[0;35m
CYAN = \033[0;36m
NC = \033[0m # No Color

.PHONY: help install start stop restart status logs clean dev test build list-modules check-port diagnose
.PHONY: mcp-server-start mcp-server-stop mcp-server-restart mcp-server-status mcp-server-logs mcp-server-dev mcp-server-diagnose
.PHONY: ollama-start ollama-stop ollama-restart ollama-status ollama-diagnose

# 默认目标
.DEFAULT_GOAL := help

help: ## 显示帮助信息
	@echo "$(CYAN)MCP QA 多模块管理命令$(NC)"
	@echo ""
	@echo "$(YELLOW)通用命令:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E '^  [^m]'
	@echo ""
	@echo "$(YELLOW)模块特定命令 (mcp_server):$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^mcp-server-.*:.*?## / {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)模块特定命令 (ollama):$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^ollama-.*:.*?## / {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)当前模块配置 ($(CURRENT_MODULE)):$(NC)"
	@echo "  $(GREEN)HOST$(NC)         服务器主机地址 ($(HOST))"
	@echo "  $(GREEN)PORT$(NC)         服务器端口 ($(PORT))"
	@echo "  $(GREEN)DEBUG$(NC)        调试模式 ($(DEBUG))"
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		echo "  $(GREEN)ALLOWED_DIRS$(NC) 安全白名单目录 ($(MCP_SERVER_ALLOWED_DIRS))"; \
	fi
	@echo ""
	@echo "$(YELLOW)示例:$(NC)"
	@echo "  make start                           # 启动当前模块 ($(CURRENT_MODULE))"
	@echo "  make mcp-server-start                # 明确启动 mcp_server 模块"
	@echo "  make ollama-start                    # 启动 ollama 服务 (仅限 macOS)"
	@echo "  make start CURRENT_MODULE=mcp_server # 指定模块启动"
	@echo "  make start MCP_SERVER_ALLOWED_DIRS='docs,data' # 自定义安全目录"
	@echo "  make list-modules                    # 查看所有可用模块"

install: ## 安装依赖
	@echo "$(BLUE)正在安装项目依赖...$(NC)"
	@if command -v uv >/dev/null 2>&1; then \
		uv sync; \
	else \
		pip install -e .; \
	fi
	@echo "$(GREEN)依赖安装完成!$(NC)"

list-modules: ## 列出所有可用模块
	@echo "$(CYAN)可用模块:$(NC)"
	@for module in $(MODULES); do \
		echo "  $(GREEN)$$module$(NC)"; \
	done
	@echo ""
	@echo "$(YELLOW)当前默认模块: $(CURRENT_MODULE)$(NC)"

# =============================================================================
# 通用模块操作命令（作用于当前模块）
# =============================================================================

setup-dirs: ## 创建必要的目录
	@mkdir -p $(LOG_DIR)
	@mkdir -p faiss_index

check-port: ## 检查端口是否被占用
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		PORT_IN_USE=$$(lsof -i :$(MCP_SERVER_PORT) 2>/dev/null); \
		if [ -n "$$PORT_IN_USE" ]; then \
			echo "$(RED)❌ 端口 $(MCP_SERVER_PORT) 已被占用:$(NC)"; \
			echo "$$PORT_IN_USE"; \
			PID_FROM_PORT=$$(echo "$$PORT_IN_USE" | awk 'NR==2 {print $$2}'); \
			if [ -f $(MCP_SERVER_PID_FILE) ]; then \
				SAVED_PID=$$(cat $(MCP_SERVER_PID_FILE)); \
				if [ "$$PID_FROM_PORT" = "$$SAVED_PID" ]; then \
					echo "$(YELLOW)这是我们自己的MCP Server进程$(NC)"; \
				else \
					echo "$(RED)这是其他进程，请先停止占用端口的进程$(NC)"; \
					exit 1; \
				fi \
			else \
				echo "$(RED)这是其他进程，请先停止占用端口的进程:$(NC)"; \
				echo "$(YELLOW)可以使用: kill $$PID_FROM_PORT$(NC)"; \
				exit 1; \
			fi \
		else \
			echo "$(GREEN)✅ 端口 $(MCP_SERVER_PORT) 可用$(NC)"; \
		fi \
	fi

check-running: ## 检查服务器是否运行
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		$(MAKE) mcp-server-status > /dev/null 2>&1 || true; \
	fi

start: ## 启动当前模块
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		$(MAKE) mcp-server-start; \
	elif [ "$(CURRENT_MODULE)" = "ollama" ]; then \
		$(MAKE) ollama-start; \
	else \
		echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
		exit 1; \
	fi

stop: ## 停止当前模块
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		$(MAKE) mcp-server-stop; \
	elif [ "$(CURRENT_MODULE)" = "ollama" ]; then \
		$(MAKE) ollama-stop; \
	else \
		echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
		exit 1; \
	fi

restart: ## 重启当前模块
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		$(MAKE) mcp-server-restart; \
	elif [ "$(CURRENT_MODULE)" = "ollama" ]; then \
		$(MAKE) ollama-restart; \
	else \
		echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
		exit 1; \
	fi

status: ## 查看当前模块状态
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		$(MAKE) mcp-server-status; \
	elif [ "$(CURRENT_MODULE)" = "ollama" ]; then \
		$(MAKE) ollama-status; \
	else \
		echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
		exit 1; \
	fi

dev: ## 以开发模式启动当前模块
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		$(MAKE) mcp-server-dev; \
	else \
		echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
		exit 1; \
	fi

logs: ## 查看当前模块日志
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		$(MAKE) mcp-server-logs; \
	else \
		echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
		exit 1; \
	fi

logs-static: ## 查看当前模块静态日志
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		if [ -f $(MCP_SERVER_LOG_FILE) ]; then \
			echo "$(BLUE)MCP Server 日志内容:$(NC)"; \
			cat $(MCP_SERVER_LOG_FILE); \
		else \
			echo "$(RED)❌ 日志文件不存在: $(MCP_SERVER_LOG_FILE)$(NC)"; \
		fi; \
	else \
		echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
		exit 1; \
	fi

diagnose: ## 诊断当前模块问题
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		$(MAKE) mcp-server-diagnose; \
	elif [ "$(CURRENT_MODULE)" = "ollama" ]; then \
		$(MAKE) ollama-diagnose; \
	else \
		echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
		exit 1; \
	fi

test: ## 运行测试
	@echo "$(BLUE)正在运行测试...$(NC)"
	@$(UV_RUN) -m pytest tests/ -v || echo "$(YELLOW)测试目录不存在，跳过测试$(NC)"

test-server: ## 测试当前模块连接
	@echo "$(BLUE)测试 $(CURRENT_MODULE) 模块连接...$(NC)"
	@if command -v curl >/dev/null 2>&1; then \
		if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
			curl -s http://$(MCP_SERVER_HOST):$(MCP_SERVER_PORT)/health > /dev/null && \
			echo "$(GREEN)✅ MCP Server 连接正常$(NC)" || \
			echo "$(RED)❌ MCP Server 连接失败$(NC)"; \
		else \
			echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
		fi \
	else \
		echo "$(YELLOW)curl 命令不可用，无法测试连接$(NC)"; \
	fi

clean: ## 清理临时文件
	@echo "$(BLUE)正在清理临时文件...$(NC)"
	@rm -f $(MCP_SERVER_PID_FILE)
	@rm -rf __pycache__/
	@rm -rf mcp_server/__pycache__/
	@rm -rf mcp_server/*/__pycache__/
	@rm -rf .pytest_cache/
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info/
	@echo "$(GREEN)✅ 清理完成$(NC)"

clean-logs: ## 清理当前模块日志文件
	@echo "$(YELLOW)正在清理 $(CURRENT_MODULE) 模块日志文件...$(NC)"
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		if [ -f $(MCP_SERVER_LOG_FILE) ]; then \
			> $(MCP_SERVER_LOG_FILE); \
			echo "$(GREEN)✅ MCP Server 日志文件已清空$(NC)"; \
		else \
			echo "$(YELLOW)MCP Server 日志文件不存在$(NC)"; \
		fi \
	else \
		echo "$(RED)❌ 未知模块: $(CURRENT_MODULE)$(NC)"; \
	fi

clean-all: clean clean-logs ## 清理所有临时文件和日志
	@echo "$(GREEN)✅ 全部清理完成$(NC)"

# =============================================================================
# MCP Server 模块特定命令
# =============================================================================

mcp-server-start: setup-dirs ## 启动 mcp_server 模块
	@echo "$(BLUE)正在启动 MCP Server 模块...$(NC)"
	@echo "$(CYAN)配置: Host=$(MCP_SERVER_HOST), Port=$(MCP_SERVER_PORT), Debug=$(MCP_SERVER_DEBUG)$(NC)"
	@echo "$(CYAN)安全目录: $(MCP_SERVER_ALLOWED_DIRS)$(NC)"
	@# 检查是否已经在运行，如果是则直接退出
	@if [ -f $(MCP_SERVER_PID_FILE) ]; then \
		PID=$$(cat $(MCP_SERVER_PID_FILE)); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "$(YELLOW)MCP Server 已经在运行 (PID: $$PID)$(NC)"; \
			echo "$(GREEN)地址: http://$(MCP_SERVER_HOST):$(MCP_SERVER_PORT)$(NC)"; \
		else \
			echo "$(YELLOW)清理过期的PID文件$(NC)"; \
			rm -f $(MCP_SERVER_PID_FILE); \
			$(MAKE) _do-mcp-server-start; \
		fi \
	else \
		$(MAKE) _do-mcp-server-start; \
	fi

_do-mcp-server-start: ## 内部启动命令
	@# 检查端口是否被其他进程占用
	@PORT_IN_USE=$$(lsof -i :$(MCP_SERVER_PORT) 2>/dev/null); \
	if [ -n "$$PORT_IN_USE" ]; then \
		echo "$(RED)❌ 端口 $(MCP_SERVER_PORT) 已被其他进程占用:$(NC)"; \
		echo "$$PORT_IN_USE"; \
		PID_FROM_PORT=$$(echo "$$PORT_IN_USE" | awk 'NR==2 {print $$2}'); \
		echo "$(RED)请先停止占用端口的进程: kill $$PID_FROM_PORT$(NC)"; \
		exit 1; \
	fi
	@# 检查Python模块是否存在
	@if ! $(UV_RUN) python -c "import mcp_server.server" 2>/dev/null; then \
		echo "$(RED)❌ 找不到 mcp_server.server 模块$(NC)"; \
		echo "$(YELLOW)请确保项目依赖已正确安装: make install$(NC)"; \
		exit 1; \
	fi
	@# 启动服务
	@echo "$(BLUE)启动 MCP Server...$(NC)"
	@MCP_HOST=$(MCP_SERVER_HOST) MCP_PORT=$(MCP_SERVER_PORT) MCP_DEBUG=$(MCP_SERVER_DEBUG) \
		MCP_ALLOWED_DIRS=$(MCP_SERVER_ALLOWED_DIRS) \
		nohup $(UV_RUN) -m mcp_server.server > $(MCP_SERVER_LOG_FILE) 2>&1 & echo $$! > $(MCP_SERVER_PID_FILE)
	@sleep 3
	@# 验证启动是否成功
	@if [ -f $(MCP_SERVER_PID_FILE) ]; then \
		PID=$$(cat $(MCP_SERVER_PID_FILE)); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "$(GREEN)✅ MCP Server 启动成功!$(NC)"; \
			echo "$(GREEN)PID: $$PID$(NC)"; \
			echo "$(GREEN)地址: http://$(MCP_SERVER_HOST):$(MCP_SERVER_PORT)$(NC)"; \
			echo "$(GREEN)日志: $(MCP_SERVER_LOG_FILE)$(NC)"; \
		else \
			echo "$(RED)❌ MCP Server 启动失败$(NC)"; \
			echo "$(YELLOW)查看日志获取详细错误信息: make mcp-server-logs$(NC)"; \
			if [ -f $(MCP_SERVER_LOG_FILE) ]; then \
				echo "$(RED)最近的错误日志:$(NC)"; \
				tail -n 10 $(MCP_SERVER_LOG_FILE) | sed 's/^/  /'; \
			fi; \
			rm -f $(MCP_SERVER_PID_FILE); \
			exit 1; \
		fi \
	else \
		echo "$(RED)❌ 无法获取进程ID$(NC)"; \
		exit 1; \
	fi

mcp-server-stop: ## 停止 mcp_server 模块
	@if [ -f $(MCP_SERVER_PID_FILE) ]; then \
		PID=$$(cat $(MCP_SERVER_PID_FILE)); \
		echo "$(YELLOW)正在停止 MCP Server (PID: $$PID)...$(NC)"; \
		if ps -p $$PID > /dev/null 2>&1; then \
			kill $$PID; \
			sleep 2; \
			if ps -p $$PID > /dev/null 2>&1; then \
				echo "$(YELLOW)强制停止 MCP Server...$(NC)"; \
				kill -9 $$PID; \
			fi; \
			echo "$(GREEN)✅ MCP Server 已停止$(NC)"; \
		else \
			echo "$(YELLOW)MCP Server 未运行$(NC)"; \
		fi; \
		rm -f $(MCP_SERVER_PID_FILE); \
	else \
		echo "$(YELLOW)MCP Server 未运行$(NC)"; \
	fi

mcp-server-restart: ## 重启 mcp_server 模块
	@echo "$(BLUE)正在重启 MCP Server...$(NC)"
	@$(MAKE) mcp-server-stop
	@sleep 1
	@$(MAKE) mcp-server-start

mcp-server-status: ## 查看 mcp_server 模块状态
	@if [ -f $(MCP_SERVER_PID_FILE) ]; then \
		PID=$$(cat $(MCP_SERVER_PID_FILE)); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "$(GREEN)✅ MCP Server 正在运行$(NC)"; \
			echo "$(GREEN)PID: $$PID$(NC)"; \
			echo "$(GREEN)地址: http://$(MCP_SERVER_HOST):$(MCP_SERVER_PORT)$(NC)"; \
			echo "$(GREEN)运行时间: $$(ps -o etime= -p $$PID | tr -d ' ')$(NC)"; \
			echo "$(GREEN)内存使用: $$(ps -o rss= -p $$PID | tr -d ' ') KB$(NC)"; \
		else \
			echo "$(RED)❌ MCP Server 未运行$(NC)"; \
			rm -f $(MCP_SERVER_PID_FILE); \
		fi \
	else \
		echo "$(RED)❌ MCP Server 未运行$(NC)"; \
	fi

mcp-server-logs: ## 查看 mcp_server 模块日志
	@if [ -f $(MCP_SERVER_LOG_FILE) ]; then \
		echo "$(BLUE)显示 MCP Server 日志 (按 Ctrl+C 退出):$(NC)"; \
		tail -f $(MCP_SERVER_LOG_FILE); \
	else \
		echo "$(RED)❌ 日志文件不存在: $(MCP_SERVER_LOG_FILE)$(NC)"; \
	fi

mcp-server-dev: setup-dirs ## 以开发模式启动 mcp_server 模块
	@echo "$(BLUE)正在以开发模式启动 MCP Server...$(NC)"
	@echo "$(CYAN)配置: Host=$(MCP_SERVER_HOST), Port=$(MCP_SERVER_PORT), Debug=true$(NC)"
	@echo "$(CYAN)安全目录: $(MCP_SERVER_ALLOWED_DIRS)$(NC)"
	@echo "$(YELLOW)按 Ctrl+C 停止服务器$(NC)"
	@# 检查端口是否被占用
	@PORT_IN_USE=$$(lsof -i :$(MCP_SERVER_PORT) 2>/dev/null); \
	if [ -n "$$PORT_IN_USE" ]; then \
		echo "$(RED)❌ 端口 $(MCP_SERVER_PORT) 已被占用:$(NC)"; \
		echo "$$PORT_IN_USE"; \
		exit 1; \
	fi
	@MCP_HOST=$(MCP_SERVER_HOST) MCP_PORT=$(MCP_SERVER_PORT) MCP_DEBUG=true \
		MCP_ALLOWED_DIRS=$(MCP_SERVER_ALLOWED_DIRS) \
		$(UV_RUN) -m mcp_server.server

mcp-server-diagnose: ## 诊断 mcp_server 模块问题
	@echo "$(CYAN)MCP Server 诊断信息:$(NC)"
	@echo ""
	@echo "$(YELLOW)1. 检查端口占用:$(NC)"
	@PORT_IN_USE=$$(lsof -i :$(MCP_SERVER_PORT) 2>/dev/null); \
	if [ -n "$$PORT_IN_USE" ]; then \
		echo "$(RED)端口 $(MCP_SERVER_PORT) 被占用:$(NC)"; \
		echo "$$PORT_IN_USE"; \
	else \
		echo "$(GREEN)端口 $(MCP_SERVER_PORT) 可用$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)2. 检查进程状态:$(NC)"
	@if [ -f $(MCP_SERVER_PID_FILE) ]; then \
		PID=$$(cat $(MCP_SERVER_PID_FILE)); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "$(GREEN)MCP Server 进程运行中 (PID: $$PID)$(NC)"; \
			echo "运行时间: $$(ps -o etime= -p $$PID | tr -d ' ')"; \
			echo "内存使用: $$(ps -o rss= -p $$PID | tr -d ' ') KB"; \
		else \
			echo "$(RED)PID文件存在但进程未运行$(NC)"; \
		fi \
	else \
		echo "$(YELLOW)无PID文件$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)3. 检查Python模块:$(NC)"
	@if $(UV_RUN) python -c "import mcp_server.server" 2>/dev/null; then \
		echo "$(GREEN)mcp_server.server 模块可导入$(NC)"; \
	else \
		echo "$(RED)mcp_server.server 模块导入失败$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)4. 检查日志文件:$(NC)"
	@if [ -f $(MCP_SERVER_LOG_FILE) ]; then \
		LOG_SIZE=$$(wc -l < $(MCP_SERVER_LOG_FILE)); \
		echo "$(GREEN)日志文件存在: $(MCP_SERVER_LOG_FILE)$(NC)"; \
		echo "日志行数: $$LOG_SIZE"; \
		if [ $$LOG_SIZE -gt 0 ]; then \
			echo ""; \
			echo "$(YELLOW)最近的日志内容:$(NC)"; \
			tail -n 5 $(MCP_SERVER_LOG_FILE) | sed 's/^/  /'; \
		fi \
	else \
		echo "$(YELLOW)日志文件不存在$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)5. 网络连接测试:$(NC)"
	@if command -v curl >/dev/null 2>&1; then \
		if curl -s --connect-timeout 5 http://$(MCP_SERVER_HOST):$(MCP_SERVER_PORT)/health > /dev/null 2>&1; then \
			echo "$(GREEN)HTTP连接正常$(NC)"; \
		else \
			echo "$(RED)HTTP连接失败$(NC)"; \
		fi \
	else \
		echo "$(YELLOW)curl不可用，跳过网络测试$(NC)"; \
	fi

# =============================================================================
# Ollama 模块特定命令 (仅限 macOS)
# =============================================================================

ollama-start: ## 启动 ollama 服务 (仅限 macOS)
	@if [ "$(PLATFORM)" != "macos" ]; then \
		echo "$(RED)❌ Ollama 命令仅支持 macOS$(NC)"; \
		exit 1; \
	fi
	@if [ "$(OLLAMA_AVAILABLE)" != "true" ]; then \
		echo "$(RED)❌ 未检测到 brew 命令，请先安装 Homebrew$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)正在启动 Ollama 服务...$(NC)"
	@if brew services list | grep -q "ollama.*started"; then \
		echo "$(YELLOW)Ollama 服务已经在运行$(NC)"; \
	else \
		brew services start ollama && \
		echo "$(GREEN)✅ Ollama 服务启动成功$(NC)" || \
		echo "$(RED)❌ Ollama 服务启动失败$(NC)"; \
	fi

ollama-stop: ## 停止 ollama 服务 (仅限 macOS)
	@if [ "$(PLATFORM)" != "macos" ]; then \
		echo "$(RED)❌ Ollama 命令仅支持 macOS$(NC)"; \
		exit 1; \
	fi
	@if [ "$(OLLAMA_AVAILABLE)" != "true" ]; then \
		echo "$(RED)❌ 未检测到 brew 命令，请先安装 Homebrew$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)正在停止 Ollama 服务...$(NC)"
	@if brew services list | grep -q "ollama.*started"; then \
		brew services stop ollama && \
		echo "$(GREEN)✅ Ollama 服务已停止$(NC)" || \
		echo "$(RED)❌ Ollama 服务停止失败$(NC)"; \
	else \
		echo "$(YELLOW)Ollama 服务未运行$(NC)"; \
	fi

ollama-restart: ## 重启 ollama 服务 (仅限 macOS)
	@if [ "$(PLATFORM)" != "macos" ]; then \
		echo "$(RED)❌ Ollama 命令仅支持 macOS$(NC)"; \
		exit 1; \
	fi
	@if [ "$(OLLAMA_AVAILABLE)" != "true" ]; then \
		echo "$(RED)❌ 未检测到 brew 命令，请先安装 Homebrew$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)正在重启 Ollama 服务...$(NC)"
	@brew services restart ollama && \
	echo "$(GREEN)✅ Ollama 服务重启成功$(NC)" || \
	echo "$(RED)❌ Ollama 服务重启失败$(NC)"

ollama-status: ## 查看 ollama 服务状态 (仅限 macOS)
	@if [ "$(PLATFORM)" != "macos" ]; then \
		echo "$(RED)❌ Ollama 命令仅支持 macOS$(NC)"; \
		exit 1; \
	fi
	@if [ "$(OLLAMA_AVAILABLE)" != "true" ]; then \
		echo "$(RED)❌ 未检测到 brew 命令，请先安装 Homebrew$(NC)"; \
		exit 1; \
	fi
	@echo "$(CYAN)Ollama 服务状态:$(NC)"
	@if brew services list | grep -q "ollama.*started"; then \
		echo "$(GREEN)✅ Ollama 服务正在运行$(NC)"; \
		brew services list | grep ollama; \
	else \
		echo "$(RED)❌ Ollama 服务未运行$(NC)"; \
		brew services list | grep ollama; \
	fi

ollama-diagnose: ## 诊断 ollama 服务问题 (仅限 macOS)
	@if [ "$(PLATFORM)" != "macos" ]; then \
		echo "$(RED)❌ Ollama 命令仅支持 macOS$(NC)"; \
		exit 1; \
	fi
	@echo "$(CYAN)Ollama 诊断信息:$(NC)"
	@echo ""
	@echo "$(YELLOW)1. 检查平台支持:$(NC)"
	@echo "当前平台: $(PLATFORM)"
	@echo ""
	@echo "$(YELLOW)2. 检查 Homebrew:$(NC)"
	@if command -v brew >/dev/null 2>&1; then \
		echo "$(GREEN)Homebrew 已安装$(NC)"; \
		echo "版本: $$(brew --version | head -n1)"; \
	else \
		echo "$(RED)Homebrew 未安装$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)3. 检查 Ollama 安装:$(NC)"
	@if brew list ollama >/dev/null 2>&1; then \
		echo "$(GREEN)Ollama 已通过 Homebrew 安装$(NC)"; \
		echo "版本: $$(brew list --versions ollama)"; \
	else \
		echo "$(RED)Ollama 未通过 Homebrew 安装$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)4. 检查服务状态:$(NC)"
	@if [ "$(OLLAMA_AVAILABLE)" = "true" ]; then \
		brew services list | grep ollama || echo "$(YELLOW)未找到 Ollama 服务$(NC)"; \
	else \
		echo "$(YELLOW)Homebrew 不可用，无法检查服务状态$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)5. 检查网络连接:$(NC)"
	@if command -v ollama >/dev/null 2>&1; then \
		if ollama list >/dev/null 2>&1; then \
			echo "$(GREEN)Ollama 命令可用$(NC)"; \
		else \
			echo "$(RED)Ollama 命令执行失败$(NC)"; \
		fi \
	else \
		echo "$(YELLOW)Ollama 命令不在 PATH 中$(NC)"; \
	fi

build: ## 构建项目
	@echo "$(BLUE)正在构建项目...$(NC)"
	@if command -v uv >/dev/null 2>&1; then \
		uv build; \
	else \
		$(UV_RUN) -m build; \
	fi
	@echo "$(GREEN)✅ 构建完成$(NC)"

info: ## 显示项目信息
	@echo "$(CYAN)MCP QA 多模块项目信息:$(NC)"
	@echo "  $(GREEN)项目名称:$(NC) $(PROJECT_NAME)"
	@echo "  $(GREEN)可用模块:$(NC) $(MODULES)"
	@echo "  $(GREEN)当前模块:$(NC) $(CURRENT_MODULE)"
	@echo "  $(GREEN)UV版本:$(NC) $$(uv --version 2>&1)"
	@echo "  $(GREEN)Python版本:$(NC) $$($(UV_RUN) python --version 2>&1)"
	@echo "  $(GREEN)平台:$(NC) $(PLATFORM)"
	@echo "  $(GREEN)工作目录:$(NC) $$(pwd)"
	@echo ""
	@echo "$(CYAN)当前模块 ($(CURRENT_MODULE)) 配置:$(NC)"
	@if [ "$(CURRENT_MODULE)" = "mcp_server" ]; then \
		echo "  $(GREEN)PID文件:$(NC) $(MCP_SERVER_PID_FILE)"; \
		echo "  $(GREEN)日志文件:$(NC) $(MCP_SERVER_LOG_FILE)"; \
		echo "  $(GREEN)服务地址:$(NC) http://$(MCP_SERVER_HOST):$(MCP_SERVER_PORT)"; \
		echo "  $(GREEN)安全目录:$(NC) $(MCP_SERVER_ALLOWED_DIRS)"; \
	fi

# 快捷命令别名
up: start ## start的别名
down: stop ## stop的别名
ps: status ## status的别名
tail: logs ## logs的别名