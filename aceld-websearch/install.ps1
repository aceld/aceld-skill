# aceld-websearch 一键安装（Windows / PowerShell）
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Claude
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Dest "D:\skills\aceld-websearch"

param(
    [switch]$Claude,
    [string]$Dest = ""
)

$ErrorActionPreference = "Stop"

$Name = "aceld-websearch"
$Src  = Join-Path $PSScriptRoot "skill"

if (-not $Dest) {
    if ($Claude) {
        $Dest = Join-Path $HOME ".claude\skills\$Name"
    } else {
        $Dest = Join-Path $HOME ".workbuddy-ai\skills\$Name"
    }
}

Write-Host "==> 源目录：$Src" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $Src "SKILL.md"))) {
    Write-Host "!! 找不到 skill\SKILL.md，请在 aceld-websearch 目录运行 install.ps1" -ForegroundColor Red
    exit 1
}

if (Test-Path $Dest) {
    # ★备份必须放在 skills/ 外面，否则加载器会把备份目录也当成同名技能扫出来
    $BackupRoot = Join-Path (Split-Path $Dest -Parent) "skills-backup"
    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
    $Backup = Join-Path $BackupRoot ($Name + ".bak." + (Get-Date -Format "yyyyMMddHHmmss"))
    Write-Host "==> 已存在同名技能，备份到：$Backup" -ForegroundColor Yellow
    Move-Item -Path $Dest -Destination $Backup
}

New-Item -ItemType Directory -Force -Path (Split-Path $Dest -Parent) | Out-Null
Copy-Item -Path $Src -Destination $Dest -Recurse -Force

Write-Host "==> 已安装到：$Dest" -ForegroundColor Green

Write-Host ""
Write-Host "内容：" -ForegroundColor Cyan
Get-ChildItem -Path $Dest -Recurse -File -Depth 1 |
    ForEach-Object { "  " + $_.FullName.Substring($Dest.Length + 1) } | Sort-Object

Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "  1) 重启会话，让 Agent 重新加载技能列表"
Write-Host "  2) 自测：python $Dest\scripts\window.py --json"
Write-Host "  3) 完整链路：python $Dest\scripts\rank.py -i $Dest\assets\candidates.example.json -o .\research\demo\pack"
Write-Host "  4) 交付校验：python $Dest\scripts\verify.py .\research\demo\pack\pack.json"
