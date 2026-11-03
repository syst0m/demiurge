#!/usr/bin/env bash
# Installs a pre-commit hook that works from Git Bash, WSL, Linux and macOS.
#
# `pre-commit install` bakes one absolute interpreter path into the hook, so a
# hook installed from WSL (/mnt/c/...) fails in Git Bash, and the reverse. This
# hook looks for an interpreter that has pre_commit at run time instead.
#
# Usage: bash scripts/install-git-hook.sh
set -euo pipefail

hook="$(git rev-parse --git-path hooks)/pre-commit"
mkdir -p "$(dirname "$hook")"

cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
# Portable pre-commit shim. Installed by scripts/install-git-hook.sh.
HERE="$(cd "$(dirname "$0")" && pwd)"
ARGS=(hook-impl --config=.pre-commit-config.yaml --hook-type=pre-commit --hook-dir "$HERE" -- "$@")

# python.exe and py.exe cover WSL calling the Windows interpreter.
for py in python3 python py python.exe py.exe; do
    if command -v "$py" > /dev/null && "$py" -c 'import pre_commit' 2> /dev/null; then
        exec "$py" -m pre_commit "${ARGS[@]}"
    fi
done
if command -v pre-commit > /dev/null; then
    exec pre-commit "${ARGS[@]}"
fi
echo 'pre-commit not found: run "python -m pip install pre-commit" in this shell.' 1>&2
exit 1
HOOK

chmod +x "$hook"
echo "Installed $hook"
