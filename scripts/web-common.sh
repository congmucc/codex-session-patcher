#!/bin/bash
# Shared helpers for Web UI launch scripts.

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
FRONTEND_DIR="${FRONTEND_DIR:-$PROJECT_DIR/web/frontend}"
FRONTEND_DIST_DIR="${FRONTEND_DIST_DIR:-$FRONTEND_DIR/dist}"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=8

web_list_python_candidates() {
    {
        if [ -n "${WEB_PYTHON_BIN:-}" ]; then
            printf '%s\n' "$WEB_PYTHON_BIN"
        fi

        for name in python3 python python3.13 python3.12 python3.11 python3.10 python3.9 python3.8; do
            if command -v "$name" >/dev/null 2>&1; then
                command -v "$name"
            fi
        done

        if command -v py >/dev/null 2>&1 && py -3 - <<'PY' >/dev/null 2>&1
import sys

raise SystemExit(0 if sys.version_info >= (3, 8) else 1)
PY
        then
            printf '%s\n' "$(web_py_launcher_path)"
        fi

        for path in \
            /opt/homebrew/bin/python3 \
            /usr/local/bin/python3 \
            /Library/Frameworks/Python.framework/Versions/Current/bin/python3
        do
            if [ -x "$path" ]; then
                printf '%s\n' "$path"
            fi
        done

    } | awk 'NF && !seen[$0]++'
}

web_py_launcher_path() {
    local state_dir wrapper_path

    state_dir="$(web_state_dir)"
    wrapper_path="$state_dir/python-launcher.sh"
    mkdir -p "$state_dir"

    if [ ! -f "$wrapper_path" ]; then
        cat > "$wrapper_path" <<'EOF'
#!/bin/sh
exec py -3 "$@"
EOF
        chmod +x "$wrapper_path"
    fi

    printf '%s\n' "$wrapper_path"
}

web_python_is_supported() {
    "$1" - <<'PY' >/dev/null 2>&1
import sys

raise SystemExit(0 if sys.version_info >= (3, 8) else 1)
PY
}

web_python_version_string() {
    "$1" - <<'PY'
import sys

print(".".join(map(str, sys.version_info[:3])))
PY
}

web_pick_python_bin() {
    local candidate

    while IFS= read -r candidate; do
        if web_python_is_supported "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done < <(web_list_python_candidates)

    return 1
}

web_ensure_pip_available() {
    local python_bin="$1"

    if "$python_bin" -m pip --version >/dev/null 2>&1; then
        return 0
    fi

    if "$python_bin" -m ensurepip --upgrade >/dev/null 2>&1 && "$python_bin" -m pip --version >/dev/null 2>&1; then
        return 0
    fi

    return 1
}

web_state_dir() {
    local git_dir

    if [ -n "${WEB_STATE_DIR:-}" ]; then
        printf '%s\n' "$WEB_STATE_DIR"
    elif [ -d "$PROJECT_DIR/.git" ]; then
        printf '%s\n' "$PROJECT_DIR/.git/web-runtime"
    elif [ -f "$PROJECT_DIR/.git" ]; then
        git_dir="$(sed -n 's/^gitdir: //p' "$PROJECT_DIR/.git" | head -n 1)"
        if [ -n "$git_dir" ]; then
            case "$git_dir" in
                /*) ;;
                *) git_dir="$PROJECT_DIR/$git_dir" ;;
            esac
            printf '%s\n' "$git_dir/web-runtime"
        elif [ -n "${XDG_STATE_HOME:-}" ]; then
            printf '%s\n' "$XDG_STATE_HOME/codex-session-patcher"
        else
            printf '%s\n' "$PROJECT_DIR/.codex-session-patcher-state"
        fi
    elif [ -n "${XDG_STATE_HOME:-}" ]; then
        printf '%s\n' "$XDG_STATE_HOME/codex-session-patcher"
    else
        printf '%s\n' "$PROJECT_DIR/.codex-session-patcher-state"
    fi
}

web_python_deps_stamp() {
    printf '%s\n' "$(web_state_dir)/python-web-deps.stamp"
}

web_frontend_deps_stamp() {
    printf '%s\n' "$(web_state_dir)/frontend-deps.stamp"
}

web_mark_python_deps_installed() {
    local state_dir

    state_dir="$(web_state_dir)"
    mkdir -p "$state_dir"
    : > "$(web_python_deps_stamp)"
}

web_mark_frontend_deps_installed() {
    local state_dir

    state_dir="$(web_state_dir)"
    mkdir -p "$state_dir"
    : > "$(web_frontend_deps_stamp)"
}

web_python_deps_ready() {
    local python_bin="$1"
    PROJECT_DIR="$PROJECT_DIR" WEB_PYTHON_IMPORT_CHECK="${WEB_PYTHON_IMPORT_CHECK:-}" "$python_bin" - <<'PY' >/dev/null 2>&1
import os
import sys

project_dir = os.environ["PROJECT_DIR"]
sys.path.insert(0, project_dir)

snippet = os.environ.get("WEB_PYTHON_IMPORT_CHECK")
if snippet:
    exec(snippet, {})
else:
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
    import pydantic  # noqa: F401
    import uvicorn  # noqa: F401
    import websockets  # noqa: F401
    import web.backend.main  # noqa: F401
PY
}

web_python_deps_need_install() {
    local python_bin="$1"
    local stamp_file

    stamp_file="$(web_python_deps_stamp)"

    if [ "${WEB_FORCE_PYTHON_DEPS_INSTALL:-0}" = "1" ]; then
        return 0
    fi

    if [ ! -f "$stamp_file" ]; then
        if web_python_deps_ready "$python_bin"; then
            web_mark_python_deps_installed
            return 1
        fi
        return 0
    fi

    if [ "$PROJECT_DIR/pyproject.toml" -nt "$stamp_file" ]; then
        return 0
    fi

    if ! web_python_deps_ready "$python_bin"; then
        return 0
    fi

    return 1
}

web_frontend_deps_need_install() {
    local stamp_file node_modules_mtime

    stamp_file="$(web_frontend_deps_stamp)"

    if [ "${WEB_FORCE_FRONTEND_DEPS_INSTALL:-0}" = "1" ]; then
        return 0
    fi

    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        return 0
    fi

    if [ ! -x "$FRONTEND_DIR/node_modules/.bin/vite" ]; then
        return 0
    fi

    if [ -f "$stamp_file" ]; then
        if [ "$FRONTEND_DIR/package.json" -nt "$stamp_file" ]; then
            return 0
        fi

        if [ -f "$FRONTEND_DIR/package-lock.json" ] && [ "$FRONTEND_DIR/package-lock.json" -nt "$stamp_file" ]; then
            return 0
        fi

        return 1
    fi

    if [ "$FRONTEND_DIR/package.json" -nt "$FRONTEND_DIR/node_modules" ]; then
        return 0
    fi

    if [ -f "$FRONTEND_DIR/package-lock.json" ] && [ "$FRONTEND_DIR/package-lock.json" -nt "$FRONTEND_DIR/node_modules" ]; then
        return 0
    fi

    web_mark_frontend_deps_installed
    return 1
}

web_frontend_sources_newer_than_dist() {
    local dist_entry="$FRONTEND_DIST_DIR/index.html"
    local source_dir
    local source_path

    for source_path in \
        "$FRONTEND_DIR/index.html" \
        "$FRONTEND_DIR/package.json" \
        "$FRONTEND_DIR/package-lock.json" \
        "$FRONTEND_DIR/vite.config.js"
    do
        if [ -f "$source_path" ] && [ "$source_path" -nt "$dist_entry" ]; then
            return 0
        fi
    done

    for source_dir in "$FRONTEND_DIR/src" "$FRONTEND_DIR/public"; do
        if [ -d "$source_dir" ] && find "$source_dir" -type f -newer "$dist_entry" -print -quit | grep -q .; then
            return 0
        fi
    done

    return 1
}

web_frontend_build_need_run() {
    if [ "${WEB_FORCE_FRONTEND_BUILD:-0}" = "1" ]; then
        return 0
    fi

    if [ ! -f "$FRONTEND_DIST_DIR/index.html" ]; then
        return 0
    fi

    if web_frontend_sources_newer_than_dist; then
        return 0
    fi

    return 1
}

web_port_in_use() {
    local port="$1"
    local host="$2"
    local python_bin="$3"

    "$python_bin" - "$host" "$port" <<'PY'
import errno
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
family = socket.AF_INET6 if ":" in host else socket.AF_INET
sock = socket.socket(family, socket.SOCK_STREAM)
try:
    sock.bind((host, port))
except OSError as exc:
    if exc.errno == errno.EADDRINUSE:
        raise SystemExit(0)

    message = exc.strerror or str(exc)
    print(f"Cannot bind to {host}:{port}: {message}", file=sys.stderr)
    raise SystemExit(2)
else:
    raise SystemExit(1)
finally:
    sock.close()
PY
}

web_find_available_port() {
    local port="$1"
    local host="$2"
    local python_bin="$3"
    local status

    while true; do
        if web_port_in_use "$port" "$host" "$python_bin"; then
            status=0
        else
            status=$?
        fi

        case "$status" in
            0)
                port=$((port + 1))
                ;;
            1)
                printf '%s\n' "$port"
                return 0
                ;;
            *)
                return "$status"
                ;;
        esac
    done
}
