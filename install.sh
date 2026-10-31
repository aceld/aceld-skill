#!/usr/bin/env bash
# Course Studio 一键安装（macOS / Linux）
# 用法：
#   bash install.sh                 # 装到 ~/.workbuddy-ai/skills/course-studio
#   bash install.sh --claude        # 装到 ~/.claude/skills/course-studio
#   bash install.sh --dest <路径>   # 装到指定目录

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skill"
NAME="course-studio"
DEST="$HOME/.workbuddy-ai/skills/$NAME"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --claude) DEST="$HOME/.claude/skills/$NAME"; shift ;;
    --dest)   DEST="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "未知参数：$1"; exit 1 ;;
  esac
done

echo "==> 源目录：$SRC"
[[ -f "$SRC/SKILL.md" ]] || { echo "!! 找不到 skill/SKILL.md，请在仓库根目录运行"; exit 1; }

if [[ -d "$DEST" ]]; then
  BACKUP="$DEST.bak.$(date +%Y%m%d%H%M%S)"
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
echo "  2) 在课程工作目录放一份 course.yaml（模板见 $DEST/assets/course.example.yaml）"
echo "  3) 说一句：帮我做一节讲 XXX 的课"
