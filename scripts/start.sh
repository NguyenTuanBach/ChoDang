#!/usr/bin/env bash
# Chạy VIN-15 cùng lúc, gom log về một terminal: BE (FastAPI, cổng 8000), agent-api (cổng 8100) và FE (Next.js, cổng 3000) chạy thẳng trên máy.
# Không cần Docker (DB là Supabase qua DATABASE_URL trong .env). Ctrl+C dừng tất cả. BE hoặc FE chết thì dừng tất cả; agent chết thì BE vẫn chạy.
set -Eeuo pipefail

SKIP_BE=0
SKIP_AGENT=0
SKIP_FE=0

usage() {
    cat <<'EOF'
Usage: scripts/start.sh [--skip-be] [--skip-agent] [--skip-fe]
  --skip-be       Không chạy backend (cổng 8000).
  --skip-agent    Không chạy agent-api (cổng 8100). BE vẫn chạy, chỉ là không gọi được agent.
  --skip-fe       Không chạy frontend Next.js (cổng 3000).
  -h, --help      In hướng dẫn này.

Biến môi trường (đọc từ .env ở gốc repo, mẫu .env.example):
  APP_PORT (8000), NEXT_PORT (3000), AGENT_API_PORT (8100), AGENT_API_SERVICE_TOKEN (BE và agent dùng chung), DATABASE_URL, OPENAI_API_KEY
Cần cài uv và Node.js/npm. Lần đầu (hoặc khi lock đổi) script tự cài dependency cho be/, agent/ (uv sync) và fe/ (npm ci).
EOF
}

for arg in "$@"; do
    case "$arg" in
        --skip-be) SKIP_BE=1 ;;
        --skip-agent) SKIP_AGENT=1 ;;
        --skip-fe) SKIP_FE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$arg" >&2; usage >&2; exit 2 ;;
    esac
done

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BE_DIR="$ROOT_DIR/be"
AGENT_DIR="$ROOT_DIR/agent"
FE_DIR="$ROOT_DIR/fe"
LOG_DIR="${TMPDIR:-/tmp}/vin15-start-$$"
mkdir -p "$LOG_DIR"
BG_PIDS=()
BG_NAMES=()
BG_CRITICAL=()
TAIL_PIDS=()
TEARDOWN_DONE=0

step() { printf '\n\033[36m>>> %s\033[0m\n' "$1"; }
ok() { printf '\033[32m  [OK] %s\033[0m\n' "$1"; }
warn() { printf '\033[33m  [WARN] %s\033[0m\n' "$1"; }
fail() { printf '\033[31m  [ERROR] %s\033[0m\n' "$1" >&2; }
info() { printf '\033[90m    %s\033[0m\n' "$1"; }

require_command() {
    command -v "$1" >/dev/null 2>&1 && return
    fail "Chưa cài $1 hoặc không có trong PATH. ${2:-Cài rồi chạy lại.}"
    exit 1
}

trim() {
    local value="$1"
    value="${value%$'\r'}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf '%s' "$value"
}

load_env() {
    # Đọc .env từng dòng thay vì `source` để giá trị có dấu cách hay ký tự lạ không bị shell diễn giải.
    local env_file="$ROOT_DIR/.env"
    [[ -f "$env_file" ]] || { warn "Không thấy .env; dùng giá trị mặc định (cp .env.example .env để cấu hình)."; return; }
    info "Đọc .env"
    local line key value
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# || "$line" != *=* ]] && continue
        key="$(trim "${line%%=*}")"
        value="$(trim "${line#*=}")"
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || { warn "Bỏ qua khoá không hợp lệ: $key"; continue; }
        [[ "$value" == \"*\" && "$value" == *\" && ${#value} -ge 2 ]] && value="${value:1:${#value}-2}"
        [[ "$value" == \'*\' && "$value" == *\' && ${#value} -ge 2 ]] && value="${value:1:${#value}-2}"
        export "$key=$value"
    done < "$env_file"
}

configure() {
    APP_PORT="${APP_PORT:-8000}"
    NEXT_PORT="${NEXT_PORT:-3000}"
    AGENT_API_PORT="${AGENT_API_PORT:-8100}"
    export APP_PORT NEXT_PORT AGENT_API_PORT
    BE_URL="http://localhost:$APP_PORT"
    FE_URL="http://localhost:$NEXT_PORT"
    # FE (Next) chuyển tiếp /api/* sang BE_URL (xem fe/next.config.ts).
    export BE_URL
    AGENT_URL="http://127.0.0.1:$AGENT_API_PORT"
    # Hai bên phải dùng cùng token; BE chỉ gọi agent khi có AGENT_API_URL. Giá trị đã đặt trong .env thì giữ.
    export AGENT_API_SERVICE_TOKEN="${AGENT_API_SERVICE_TOKEN:-agent-api-local-only}"
    [[ "$SKIP_AGENT" -eq 0 ]] && export AGENT_API_URL="${AGENT_API_URL:-$AGENT_URL}"
    # agent-api chỉ nghe loopback khi chạy local.
    export AGENT_API_HOST="127.0.0.1"
    # Chưa có đăng nhập: ngoài production, BE coi mọi request là SV A (dữ liệu từ `make seed-dev`). Đã đặt trong .env thì giữ.
    if [[ "${APP_ENV:-development}" != "production" ]]; then
        export AGENT_DEV_DEFAULT_USER_EMAIL="${AGENT_DEV_DEFAULT_USER_EMAIL:-sv.a@example.test}"
    fi
}

# ---------- Cổng ----------

port_lines() { ss -ltnpH 2>/dev/null | awk -v port=":$1" '$4 ~ port "$" { print }'; }
port_in_use() { [[ -n "$(port_lines "$1")" ]]; }
port_pids() { port_lines "$1" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | sort -u; }

port_process_info() {
    local pid
    local pids=()
    mapfile -t pids < <(port_pids "$1")
    if [[ ${#pids[@]} -eq 0 ]]; then port_lines "$1"; return; fi
    for pid in "${pids[@]}"; do
        ps -p "$pid" -o pid=,args= 2>/dev/null || printf 'PID %s (không lấy được thông tin)\n' "$pid"
    done
}

confirm_kill_port() {
    local port="$1" name="$2" answer pid
    local pids=()
    mapfile -t pids < <(port_pids "$port")
    [[ ${#pids[@]} -gt 0 && -t 0 ]] || return 1
    printf '\n'
    warn "Cổng $port ($name) đang bị chiếm bởi:"
    port_process_info "$port" | sed 's/^/      /'
    read -r -p "  Kill tiến trình trên để giải phóng cổng $port? [y/N] " answer
    [[ "$answer" =~ ^[Yy]([Ee][Ss])?$ ]] || return 1
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null && ok "Đã gửi SIGTERM tới PID $pid" || warn "Không dừng được PID $pid"
    done
    sleep 1
    if port_in_use "$port"; then
        for pid in "${pids[@]}"; do kill -KILL "$pid" 2>/dev/null || true; done
        sleep 1
    fi
    ! port_in_use "$port"
}

check_ports() {
    step "Kiểm tra cổng"
    require_command ss "Ubuntu/Debian: sudo apt install iproute2"
    local errors=()
    if [[ "$SKIP_BE" -eq 0 ]] && port_in_use "$APP_PORT" && ! confirm_kill_port "$APP_PORT" "Backend"; then
        errors+=("$APP_PORT (Backend): $(port_process_info "$APP_PORT" | tr '\n' '; ')")
    fi
    if [[ "$SKIP_FE" -eq 0 ]] && port_in_use "$NEXT_PORT" && ! confirm_kill_port "$NEXT_PORT" "Frontend"; then
        errors+=("$NEXT_PORT (Frontend): $(port_process_info "$NEXT_PORT" | tr '\n' '; ')")
    fi
    if [[ "$SKIP_AGENT" -eq 0 ]] && port_in_use "$AGENT_API_PORT" && ! confirm_kill_port "$AGENT_API_PORT" "Agent API"; then
        errors+=("$AGENT_API_PORT (Agent API): $(port_process_info "$AGENT_API_PORT" | tr '\n' '; ')")
    fi
    if [[ ${#errors[@]} -gt 0 ]]; then
        fail "Cổng đang bị chiếm:"
        printf '  %s\n' "${errors[@]}" >&2
        exit 1
    fi
    ok "Cổng trống"
}

# ---------- Tiến trình nền ----------

tail_with_prefix() {
    tail -n +1 -F "$2" 2>/dev/null | while IFS= read -r line; do printf '  [%s] %s\n' "$1" "$line"; done &
    TAIL_PIDS+=("$!")
}

# Chạy lệnh trong session riêng (setsid) để khi dừng thì kill được cả cây tiến trình con (uvicorn, uv...).
spawn() {
    local name="$1" tag="$2" critical="$3" dir="$4"; shift 4
    local log_file="$LOG_DIR/$tag.log"
    : > "$log_file"
    setsid bash -c 'cd "$1" && shift && exec "$@"' _ "$dir" "$@" >>"$log_file" 2>&1 &
    BG_PIDS+=("$!"); BG_NAMES+=("$name"); BG_CRITICAL+=("$critical")
    tail_with_prefix "$tag" "$log_file"
}

cleanup() {
    [[ "$TEARDOWN_DONE" -eq 1 ]] && return
    TEARDOWN_DONE=1
    local pid
    # Dừng agent trước (đứng sau BE trong danh sách) để BE không gọi vào agent đã tắt giữa chừng.
    for (( i=${#BG_PIDS[@]}-1; i>=0; i-- )); do
        pid="${BG_PIDS[$i]}"
        kill -0 "$pid" 2>/dev/null && kill -- "-$pid" 2>/dev/null || true
    done
    for _ in 1 2 3 4 5; do
        local alive=0
        for pid in "${BG_PIDS[@]:-}"; do [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && alive=1; done
        [[ "$alive" -eq 0 ]] && break
        sleep 1
    done
    for pid in "${BG_PIDS[@]:-}"; do [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && kill -KILL -- "-$pid" 2>/dev/null || true; done
    for pid in "${TAIL_PIDS[@]:-}"; do [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true; done
}

stop_all() { printf '\n\033[33m  %s\033[0m\n' "${1:-Đang dừng ...}"; cleanup; ok "Đã dừng tất cả."; exit "${2:-1}"; }
trap 'stop_all "Đã nhận Ctrl+C" 0' INT TERM
trap cleanup EXIT

wait_for_url() {
    local url="$1" label="$2" timeout_seconds="$3" started
    info "Chờ $label ($url) ..."
    started="$(date +%s)"
    while ! curl -fsS --max-time 3 -o /dev/null "$url" 2>/dev/null; do
        (( $(date +%s) - started >= timeout_seconds )) && return 1
        sleep 2
    done
    ok "$label đã sẵn sàng"
}

# ---------- Môi trường uv ----------

# Chỉ sync khi uv.lock hoặc pyproject.toml đổi (dấu vết ở .venv/.vin15-synced).
sync_module() {
    local dir="$1" name="$2" stamp wanted
    stamp="$dir/.venv/.vin15-synced"
    wanted="$(sha256sum "$dir/uv.lock" "$dir/pyproject.toml" | cut -d' ' -f1 | sha256sum | cut -d' ' -f1)"
    [[ "$(cat "$stamp" 2>/dev/null)" == "$wanted" ]] && return
    info "Cài dependency của $name bằng uv (lần đầu hoặc uv.lock đổi) ..."
    (cd "$dir" && uv sync --extra dev) || { fail "uv sync $name thất bại."; exit 1; }
    mkdir -p "$(dirname "$stamp")"
    printf '%s\n' "$wanted" > "$stamp"
}

prepare() {
    step "Chuẩn bị môi trường (uv)"
    require_command uv "Cài uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    [[ "$SKIP_BE" -eq 0 ]] && sync_module "$BE_DIR" "be"
    [[ "$SKIP_AGENT" -eq 0 ]] && sync_module "$AGENT_DIR" "agent"
    if [[ "$SKIP_FE" -eq 0 ]]; then
        require_command npm "Cài Node.js/npm hoặc chạy với --skip-fe."
        # Cài lại khi package-lock.json đổi (dấu vết ở node_modules/.vin15-synced).
        local stamp="$FE_DIR/node_modules/.vin15-synced" wanted
        wanted="$(sha256sum "$FE_DIR/package-lock.json" | cut -d' ' -f1)"
        if [[ "$(cat "$stamp" 2>/dev/null)" != "$wanted" ]]; then
            info "Cài dependency của fe bằng npm ci (lần đầu hoặc package-lock.json đổi) ..."
            npm --prefix "$FE_DIR" ci || { fail "npm ci thất bại."; exit 1; }
            printf '%s\n' "$wanted" > "$stamp"
        fi
    fi
    ok "Môi trường sẵn sàng"
}

# ---------- Dịch vụ ----------

start_agent() {
    [[ "$SKIP_AGENT" -eq 1 ]] && return
    step "Chạy Agent API (cổng $AGENT_API_PORT)"
    # Không bắt buộc: chết thì BE vẫn chạy, monitor chỉ cảnh báo.
    spawn "Agent API" AG 0 "$AGENT_DIR" uv run --no-sync vin15-agent-api
    wait_for_url "$AGENT_URL/healthz" "Agent API" 60 || { warn "Agent API không lên. Log: $LOG_DIR/AG.log"; return; }
    AGENT_API_STARTED=1
}

start_backend() {
    [[ "$SKIP_BE" -eq 1 ]] && return
    step "Chạy Backend - FastAPI (cổng $APP_PORT)"
    [[ -n "${DATABASE_URL:-}" ]] || warn "Chưa có DATABASE_URL: BE chạy không database (chỉ health)."
    spawn "Backend" BE 1 "$BE_DIR" uv run --no-sync python -m vin15
    wait_for_url "$BE_URL/api/health" "Backend" 60 || { fail "Backend không lên. Log: $LOG_DIR/BE.log"; stop_all "Backend lỗi"; }
    info "Swagger: $BE_URL/docs"
}

start_frontend() {
    [[ "$SKIP_FE" -eq 1 ]] && return
    step "Chạy Frontend - Next.js dev (cổng $NEXT_PORT)"
    spawn "Frontend" FE 1 "$FE_DIR" npm run dev -- --port "$NEXT_PORT"
    wait_for_url "$FE_URL" "Frontend" 120 || { fail "Frontend không lên. Log: $LOG_DIR/FE.log"; stop_all "Frontend lỗi"; }
}

monitor_processes() {
    info "Log: $LOG_DIR"
    local reported=()
    while true; do
        sleep 3
        local index pid name code
        for index in "${!BG_PIDS[@]}"; do
            pid="${BG_PIDS[$index]}"; name="${BG_NAMES[$index]}"
            kill -0 "$pid" 2>/dev/null && continue
            [[ " ${reported[*]:-} " == *" $index "* ]] && continue
            set +e; wait "$pid"; code=$?; set -e
            if [[ "${BG_CRITICAL[$index]}" -eq 1 ]]; then
                fail "$name đã dừng (mã $code)."
                stop_all "$name dừng"
            fi
            reported+=("$index")
            warn "$name đã dừng (mã $code); BE/FE vẫn chạy."
        done
    done
}

AGENT_API_STARTED=0

main() {
    require_command curl "Ubuntu/Debian: sudo apt install curl"
    require_command setsid "Cài util-linux."
    [[ "$SKIP_BE" -eq 1 && "$SKIP_AGENT" -eq 1 && "$SKIP_FE" -eq 1 ]] && { fail "Đã bỏ qua tất cả, không có gì để chạy."; exit 2; }
    load_env
    configure
    check_ports
    prepare
    start_agent
    start_backend
    start_frontend
    printf '\n\033[32m========================================================\033[0m\n'
    printf '\033[32m  VIN-15 đang chạy\033[0m\n'
    printf '\033[32m========================================================\033[0m\n'
    [[ "$SKIP_BE" -eq 0 ]] && printf '  Backend:   %s  (Swagger: %s/docs)\n' "$BE_URL" "$BE_URL"
    [[ "$SKIP_FE" -eq 0 ]] && printf '  Frontend:  %s\n' "$FE_URL"
    [[ "$AGENT_API_STARTED" -eq 1 ]] && printf '  Agent API: %s/healthz\n' "$AGENT_URL"
    printf '\n\033[33m  Ctrl+C dừng tất cả.\033[0m\n\n'
    monitor_processes
}

main
