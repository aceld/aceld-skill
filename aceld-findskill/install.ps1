# aceld-findskill 一键安装（Windows / PowerShell）
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Claude
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Dest "D:\skills\aceld-findskill"

param(
    [switch]$Claude,
    [string]$Dest = ""
)

$ErrorActionPreference = "Stop"

$Name = "aceld-findskill"
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
    Write-Host "!! 找不到 skill\SKILL.md，请在 aceld-findskill 目录运行 install.ps1" -ForegroundColor Red
    exit 1
}

if (Test-Path $Dest) {
    $Backup = "$Dest.bak." + (Get-Date -Format "yyyyMMddHHmmss")
    Write-Host "==> 已存在同名技能，备份到：$Backup" -ForegroundColor Yellow
    Move-Item -Path $Dest -Destination $Backup
}

New-Item -ItemType Directory -Force -Path (Split-Path $Dest -Parent) | Out-Null
Copy-Item -Path $Src -Destination $Dest -Recurse -Force

Write-Host "==> 已安装到：$Dest" -ForegroundColor Green

# 登记来源，供 preflight.py --check-updates 查上游更新
$Py = Get-Command python -ErrorAction SilentlyContinue
if ($Py) {
    & python (Join-Path $Dest "scripts\register_source.py") $Name "aceld/aceld-skill"
}

Write-Host ""
Write-Host "内容：" -ForegroundColor Cyan
Get-ChildItem -Path $Dest -Recurse -File -Depth 1 |
    ForEach-Object { "  " + $_.FullName.Substring($Dest.Length + 1) } | Sort-Object

Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "  1) 重启会话，让 Agent 重新加载技能列表"
Write-Host "  2) 国内先设代理：`$env:HTTPS_PROXY='http://127.0.0.1:7890'"
Write-Host "  3) 试一句：python $Dest\scripts\find.py 'pdf form filling'"
Write-Host "  4) 可选：`$env:GITHUB_TOKEN='xxx' 提高 API 配额（60 → 5000 次/小时）"
