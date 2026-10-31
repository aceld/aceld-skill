# Course Studio 一键安装（Windows / PowerShell）
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Claude
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Dest "D:\skills\course-studio"

param(
    [switch]$Claude,
    [string]$Dest = ""
)

$ErrorActionPreference = "Stop"

$Name = "course-studio"
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
    Write-Host "!! 找不到 skill\SKILL.md，请在仓库根目录运行" -ForegroundColor Red
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
Write-Host ""
Write-Host "内容：" -ForegroundColor Cyan
Get-ChildItem -Path $Dest -Recurse -File -Depth 1 |
    ForEach-Object { "  " + $_.FullName.Substring($Dest.Length + 1) } | Sort-Object

Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "  1) 重启会话，让 Agent 重新加载技能列表"
Write-Host "  2) 在课程工作目录放一份 course.yaml（模板见 $Dest\assets\course.example.yaml）"
Write-Host "  3) 说一句：帮我做一节讲 XXX 的课"
