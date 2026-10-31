#!/usr/bin/env bash
# aceld-skill-rollout 一键安装（macOS / Linux）
# 用法：
#   bash install.sh                 # 装到 ~/.workbuddy-ai/skills/aceld-skill-rollout
#   bash install.sh --claude        # 装到 ~/.claude/skills/aceld-skill-rollout
#   bash install.sh --dest <路径>   # 装到指定目录

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skill"
NAME="aceld-skill-rollout"
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
[[ -f "$SRC/SKILL.md" ]] || { echo "!! 找不到 skill/SKILL.md，请在 aceld-skill-rollout 目录运行 install.sh"; exit 1; }

if [[ -d "$DEST" ]]; then
  BACKUP="$DEST.bak.$(date +%Y%m%d%H%M%S)"
  echo "==> 已存在同名技能，备份到：$BACKUP"
  mv "$DEST" "$BACKUP"
fi

mkdir -p "$(dirname "$DEST")"
cp -R "$SRC" "$DEST"

# cp -R 会把开发时的 __pycache__ 一起搬过去，装完清掉
find "$DEST" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$DEST" -type f -name "*.pyc" -delete 2>/dev/null || true

echo "==> 已安装到：$DEST"

# 登记来源，供 preflight.py --check-updates 查上游更新（找不到 register_source.py 就跳过）
PYBIN="$(command -v python3 || command -v python || true)"
REG="$HOME/.workbuddy-ai/skills/aceld-findskill/scripts/register_source.py"
if [[ -n "$PYBIN" && -f "$REG" ]]; then
  "$PYBIN" "$REG" "$NAME" "aceld/aceld-skill" || true
fi

echo
echo "内容："
find "$DEST" -maxdepth 2 -type f | sed "s|$DEST/|  |" | sort
echo
echo "下一步："
echo "  1) 重启会话，让 Agent 重新加载技能列表"
echo "  2) 先体检现有技能库（在仓库根跑，自动定位 aceld-skill）："
echo "       python $DEST/scripts/audit.py"
echo "  3) 要铺新能力时：先写 block.md，再 dry-run 注入，最后 --apply"
echo "       python $DEST/scripts/inject.py --block block.md --marker \"能力名\""
echo "  4) 发布前必过：python $DEST/scripts/audit.py --verify"
