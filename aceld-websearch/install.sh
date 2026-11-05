#!/usr/bin/env bash
# aceld-websearch 一键安装（macOS / Linux / Git Bash）
# 用法：
#   bash install.sh                 # 装到 ~/.workbuddy-ai/skills/aceld-websearch
#   bash install.sh --claude        # 装到 ~/.claude/skills/aceld-websearch
#   bash install.sh --dest <路径>   # 装到指定目录

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skill"
NAME="aceld-websearch"
DEST="$HOME/.workbuddy-ai/skills/$NAME"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --claude) DEST="$HOME/.claude/skills/$NAME"; shift ;;
    --dest)   DEST="$2"; shift 2 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "未知参数：$1"; exit 1 ;;
  esac
done

echo "==> 源目录：$SRC"
[[ -f "$SRC/SKILL.md" ]] || { echo "!! 找不到 skill/SKILL.md，请在 aceld-websearch 目录运行 install.sh"; exit 1; }

if [[ -d "$DEST" ]]; then
  # ★备份必须放在 skills/ 外面：加载器按子目录扫技能，
  #   备份留在 skills/ 里会被当成「同名技能」，列表里出现两三个分不清哪个是真的。
  BACKUP_ROOT="$(dirname "$DEST")/skills-backup"
  mkdir -p "$BACKUP_ROOT"
  BACKUP="$BACKUP_ROOT/$NAME.bak.$(date +%Y%m%d%H%M%S)"
  echo "==> 已存在同名技能，备份到：$BACKUP"
  mv "$DEST" "$BACKUP"
fi

mkdir -p "$(dirname "$DEST")"
cp -R "$SRC" "$DEST"

echo "==> 已安装到：$DEST"
echo
echo "内容："
find "$DEST" -maxdepth 2 -type f | sed "s|$DEST|  |" | sort
echo
echo "下一步："
echo "  1) 重启会话，让 Agent 重新加载技能列表"
echo "  2) 自测：python $DEST/scripts/window.py --json"
echo "  3) 完整链路：python $DEST/scripts/rank.py -i $DEST/assets/candidates.example.json -o ./research/demo/pack"
echo "  4) 交付校验：python $DEST/scripts/verify.py ./research/demo/pack/pack.json"
