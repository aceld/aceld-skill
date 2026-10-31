#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish.py —— 一条命令走完「提交 → 推送 → 同步本地 → 验证」

为什么需要它：
    用户的要求是「提交 GitHub 之后，本地技能也要跟着更新」。
    拆成两步手工做，一定会漏 —— 漏了本地就还是旧版，而你以为已经更新了。
    所以把四步绑成一个原子动作：任何一步失败，都会立刻告诉你。

用法：
    python publish.py -m "feat(xxx): 说明"       # 提交 + 推送 + 同步本地 + 验证
    python publish.py -m "..." --no-push         # 只提交（不推送、不同步）
    python publish.py -m "..." --no-sync         # 只提交 + 推送
    python publish.py --sync-only                # 只同步本地 + 验证
    python publish.py -m "..." --dry-run         # 只打印将执行什么

代理：
    本机直连 github.com:443 被 SNI 拦、沙箱代理返回 502，
    只有 Clash Party 的 127.0.0.1:7890 能通。默认自动设上，可用 --proxy 改。
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit import LOCAL_DEFAULT, find_repo

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROXY = "http://127.0.0.1:7890"


def run(cmd, cwd=None, env=None, check=True):
    print("  $ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = (r.stdout or "").strip()
    if out:
        for ln in out.splitlines()[-25:]:
            print("    " + ln)
    if check and r.returncode != 0:
        raise SystemExit("\n!! 失败：%s（exit %d）" % (" ".join(cmd), r.returncode))
    return r


def main():
    ap = argparse.ArgumentParser(description="提交 → 推送 → 同步本地 → 验证")
    ap.add_argument("-m", "--message", default=None, help="commit message（有改动时必填）")
    ap.add_argument("--paths", default="",
                    help="只提交这些路径（逗号分隔）。默认全部 —— 有人在同时改别的文件时用它，"
                         "别把别人写一半的代码一起提交")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--local", default=LOCAL_DEFAULT)
    ap.add_argument("--proxy", default=DEFAULT_PROXY, help="git push 用的 https 代理")
    ap.add_argument("--no-push", action="store_true", help="只提交，不推送也不同步")
    ap.add_argument("--no-sync", action="store_true", help="提交+推送，但不同步本地")
    ap.add_argument("--sync-only", action="store_true", help="只同步本地 + 验证")
    ap.add_argument("--dry-run", action="store_true", help="只打印将执行什么")
    a = ap.parse_args()

    repo = find_repo(a.repo)
    if not repo:
        print("!! 找不到 aceld-skill 仓库。用 --repo 指定，或设 ACELD_SKILL_REPO")
        return 2
    print("仓库：%s\n本地：%s\n" % (repo, a.local))

    py = sys.executable or "python"
    sync_cmd = [py, os.path.join(HERE, "sync.py"), "--mirror", "--apply",
                "--local", a.local, "--repo", repo]
    verify_cmd = [py, os.path.join(HERE, "audit.py"), "--verify",
                  "--local", a.local, "--repo", repo]

    if a.sync_only:
        if a.dry_run:
            print("[dry-run] 将执行：\n  " + " ".join(sync_cmd) + "\n  " + " ".join(verify_cmd))
            return 0
        print("== 同步本地（以仓库为准，逐个备份）==")
        run(sync_cmd, cwd=repo)
        print("\n== 验证 ==")
        return run(verify_cmd, cwd=repo, check=False).returncode

    # 1. 有没有改动
    st = run(["git", "status", "--porcelain"], cwd=repo).stdout.strip()
    dirty = bool(st)
    if dirty:
        print("改动 %d 个文件" % len(st.splitlines()))

    if a.dry_run:
        print("\n[dry-run] 将执行：")
        if dirty:
            print("  git add %s && git commit -m %r"
                  % (a.paths or "-A", a.message or "<缺 -m>"))
        if not a.no_push:
            print("  git push（https_proxy=%s）" % a.proxy)
        if not a.no_push and not a.no_sync:
            print("  " + " ".join(sync_cmd))
            print("  " + " ".join(verify_cmd))
        return 0

    # 2. 提交
    if dirty:
        if not a.message:
            print("!! 有改动但没给 -m。先想清楚「为什么改」再提交。")
            return 2
        print("\n== 提交 ==")
        if a.paths:
            run(["git", "add"] + [p.strip() for p in a.paths.split(",") if p.strip()], cwd=repo)
        else:
            run(["git", "add", "-A"], cwd=repo)
        run(["git", "commit", "-m", a.message], cwd=repo)
    else:
        print("\n== 提交 ==\n  工作区干净，跳过")

    if a.no_push:
        print("\n完成（--no-push：未推送、未同步本地）")
        return 0

    # 3. 推送
    print("\n== 推送 ==")
    env = dict(os.environ)
    env["https_proxy"] = a.proxy
    env["http_proxy"] = a.proxy
    env["GIT_TERMINAL_PROMPT"] = "0"      # 没凭据时立刻失败，不要挂住等输入
    push = run(["git", "push", "origin", "HEAD"], cwd=repo, env=env, check=False)
    if push.returncode != 0:
        print("\n!! 推送失败。提交已保留在本地，修好网络/凭据后重跑：")
        print("   python %s --sync-only" % os.path.join(HERE, "publish.py"))
        print("   或  git push origin HEAD")
        return 3

    if a.no_sync:
        print("\n完成（--no-sync：已推送，未同步本地）")
        return 0

    # 4. 同步本地
    print("\n== 同步本地（以仓库为准，逐个备份）==")
    run(sync_cmd, cwd=repo)

    # 5. 验证
    print("\n== 验证 ==")
    rc = run(verify_cmd, cwd=repo, check=False).returncode
    if rc == 0:
        print("\n完成：已推送，本地技能与线上一致 ✓")
        print("提示：重启会话才会加载新技能列表。")
    else:
        print("\n!! 同步完成但验证没过，看上面的问题清单")
    return rc


if __name__ == "__main__":
    sys.exit(main())
