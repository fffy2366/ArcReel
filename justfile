set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

run_dir := ".run"
backend_pid := run_dir + "/arcreel-backend.pid"
frontend_pid := run_dir + "/arcreel-frontend.pid"
backend_log := run_dir + "/arcreel-backend.log"
frontend_log := run_dir + "/arcreel-frontend.log"

default:
	@just --list

_local-prepare:
	@mkdir -p {{run_dir}}
	@test -f .env || cp .env.example .env
	@command -v uv >/dev/null
	@command -v pnpm >/dev/null
	@uv sync --locked
	@cd frontend && pnpm install --frozen-lockfile

docker-start:
	docker compose -f docker-compose.dev.yml up -d --wait
	curl --noproxy localhost --silent --fail --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:1241/health >/dev/null
	curl --noproxy localhost --silent --fail --head --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:3001 >/dev/null

docker-stop:
	docker compose -f docker-compose.dev.yml down

docker-restart: docker-stop docker-start

local-start: _local-prepare
	@if [ -f {{backend_pid}} ] && kill -0 "$(cat {{backend_pid}})" 2>/dev/null; then \
		echo "backend already running (pgid=$(cat {{backend_pid}}))"; \
	elif lsof -nP -iTCP:1241 -sTCP:LISTEN >/dev/null 2>&1; then \
		echo "backend port 1241 is already in use; stop the existing process first"; \
		exit 1; \
	else \
		rm -f {{backend_pid}}; \
		OPENAI_API_KEY= \
		nohup bash -lc 'exec uv run uvicorn server.app:app --reload --reload-dir server --reload-dir lib --port 1241' >{{backend_log}} 2>&1 & \
		pid=$!; \
		echo $pid >{{backend_pid}}; \
		if curl --noproxy localhost --silent --fail --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:1241/health >/dev/null; then \
			echo "started backend (pid=$(cat {{backend_pid}}))"; \
		else \
			rm -f {{backend_pid}}; \
			echo "backend failed to start; see {{backend_log}}"; \
			exit 1; \
		fi; \
	fi
	@if [ -f {{frontend_pid}} ] && kill -0 "$(cat {{frontend_pid}})" 2>/dev/null; then \
		echo "frontend already running (pgid=$(cat {{frontend_pid}}))"; \
	elif lsof -nP -iTCP:3001 -sTCP:LISTEN >/dev/null 2>&1; then \
		echo "frontend port 3001 is already in use; stop the existing process first"; \
		exit 1; \
	else \
		rm -f {{frontend_pid}}; \
		nohup bash -lc 'cd frontend && exec pnpm exec vite --host 0.0.0.0 --port 3001 --strictPort' >{{frontend_log}} 2>&1 & \
		pid=$!; \
		echo $pid >{{frontend_pid}}; \
		if curl --noproxy localhost --silent --fail --head --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:3001 >/dev/null; then \
			echo "started frontend (pid=$(cat {{frontend_pid}}))"; \
		else \
			rm -f {{frontend_pid}}; \
			echo "frontend failed to start; see {{frontend_log}}"; \
			exit 1; \
		fi; \
	fi

local-stop:
	@if [ -f {{frontend_pid}} ]; then \
		pid="$(cat {{frontend_pid}})"; \
		if kill -0 "$pid" 2>/dev/null; then \
			for child in $(pgrep -P "$pid" || true); do kill "$child" 2>/dev/null || true; done; \
			kill "$pid" 2>/dev/null || true; \
			echo "stopped frontend (pid=$(cat {{frontend_pid}}))"; \
		else \
			echo "frontend pid file was stale; removed {{frontend_pid}}"; \
		fi; \
		rm -f {{frontend_pid}}; \
	else \
		echo "frontend not running"; \
	fi
	@if [ -f {{backend_pid}} ]; then \
		pid="$(cat {{backend_pid}})"; \
		if kill -0 "$pid" 2>/dev/null; then \
			for child in $(pgrep -P "$pid" || true); do kill "$child" 2>/dev/null || true; done; \
			kill "$pid" 2>/dev/null || true; \
			echo "stopped backend (pid=$(cat {{backend_pid}}))"; \
		else \
			echo "backend pid file was stale; removed {{backend_pid}}"; \
		fi; \
		rm -f {{backend_pid}}; \
	else \
		echo "backend not running"; \
	fi

local-restart: local-stop local-start