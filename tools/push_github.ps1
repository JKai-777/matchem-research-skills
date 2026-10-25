<#
push_github.ps1 — 把 matchem-research-skills 推到 GitHub 的最后一公里。

它做四件事：
  1. 找到 git（本机没有全局安装时，会去常见路径和便携版目录里找）
  2. 确保仓库已 init / add / commit（有 .git 且工作区干净就跳过）
  3. 检查远端仓库是否存在且为 public
  4. push -u origin main

用法（在你的终端里，不要用管理员）：
  powershell -NoProfile -ExecutionPolicy Bypass -File "G:\DSH work place\matchem-research-skills\tools\push_github.ps1" -User 你的GitHub账号

可选参数：
  -Name  "你的名字"      提交作者名（不填则读 git config，仍为空就现场问）
  -Email "you@x.com"     提交邮箱
  -Repo  matchem-research-skills
  -DryRun                只检查不推送
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$User,
  [string]$Name,
  [string]$Email,
  [string]$Repo = 'matchem-research-skills',
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

$RepoRoot = Split-Path -Parent $PSScriptRoot

function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Fail($msg, $hint) {
  Say "`n[失败] $msg" 'Red'
  if ($hint) { Say "       $hint" 'Yellow' }
  exit 1
}

# ---------- 1. 找 git ----------
function Find-Git {
  $cmd = Get-Command git -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $candidates = @(
    (Join-Path $env:USERPROFILE 'git\cmd\git.exe'),
    (Join-Path $env:USERPROFILE 'git\bin\git.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd\git.exe'),
    "$env:ProgramFiles\Git\cmd\git.exe",
    "${env:ProgramFiles(x86)}\Git\cmd\git.exe"
  )
  foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { return $c } }
  return $null
}

$git = Find-Git
if (-not $git) {
  Fail "找不到 git。" "先安装 Git for Windows，或用便携版解压后本脚本会自动发现 %USERPROFILE%\git\cmd\git.exe"
}
Say "git: $git"
Say (& $git --version)

# ---------- 2. 提交 ----------
Say "`n仓库目录: $RepoRoot"
if (-not (Test-Path (Join-Path $RepoRoot '.git'))) {
  Say "未初始化，执行 git init -b main"
  & $git -C $RepoRoot init -b main 2>&1 | Out-Null
} else {
  Say "已存在 .git，跳过 init"
}

# 身份
$cfgName = (& $git config user.name) 2>$null
$cfgEmail = (& $git config user.email) 2>$null
if ($Name) { $cfgName = $Name }
if ($Email) { $cfgEmail = $Email }
if ($DryRun) {
  # 演练模式不写配置、不提交，只报告将要发生什么
  $whoName = if ($cfgName) { $cfgName } else { '未设置' }
  $whoMail = if ($cfgEmail) { $cfgEmail } else { '未设置' }
  Say ("作者: " + $whoName + " / " + $whoMail)
  $wouldCommit = @(& $git -C $RepoRoot status --porcelain)
  Say ("待提交文件数: " + $wouldCommit.Count)
} else {
  if ($Name) { & $git -C $RepoRoot config user.name $Name }
  if ($Email) { & $git -C $RepoRoot config user.email $Email }
  if (-not $cfgName) {
    $input1 = Read-Host "提交作者名（会写进 commit，例如 Zhang San）"
    if (-not $input1) { Fail "提交必须有作者名" }
    & $git -C $RepoRoot config user.name $input1
    $cfgName = $input1
  }
  if (-not $cfgEmail) {
    $input2 = Read-Host "提交邮箱（建议用 GitHub 的 noreply 邮箱）"
    if (-not $input2) { Fail "提交必须有作者邮箱" }
    & $git -C $RepoRoot config user.email $input2
    $cfgEmail = $input2
  }
  Say "作者: $cfgName <$cfgEmail>"

  & $git -C $RepoRoot add -A
  $staged = & $git -C $RepoRoot diff --cached --name-only
  if ($staged) {
    Say "暂存文件数: $((($staged -split "`n") | Where-Object { $_.Trim() }).Count)"
    & $git -C $RepoRoot commit -m "feat: 材料化学研究流水线技能（文献 / 思路 / PPT）" 2>&1 | ForEach-Object { Say "  $_" }
  } else {
    Say "没有新的改动需要提交"
  }
}

# ---------- 3. 远端检查 ----------
$url = "https://github.com/$User/$Repo"
Say "`n远端: $url"
try {
  $api = Invoke-RestMethod -Uri "https://api.github.com/repos/$User/$Repo" `
    -Headers @{ 'User-Agent' = 'dsh-push-script'; 'Accept' = 'application/vnd.github+json' } -TimeoutSec 30
  if ($api.private) {
    Fail "远端仓库是 private，插件的 GitHub 订阅没有鉴权逻辑，装不了。" "把仓库改成 public：Settings -> General -> Danger Zone -> Change visibility"
  }
  Say "远端存在，public，默认分支: $($api.default_branch)"
  if ($api.default_branch -and $api.default_branch -ne 'main') {
    Say "提示：远端默认分支是 $($api.default_branch)，推送后记得在本插件里用 tree 形式指定分支。" 'Yellow'
  }
  if ($api.size -gt 0) {
    Say "提示：远端已有内容（size=$($api.size) KB）。若是网页上自动生成了 README/LICENSE，push 会被拒。" 'Yellow'
    Say "      解决：git pull --rebase origin $($api.default_branch) 之后再 push；或直接删掉远端重建为空库。" 'Yellow'
  }
} catch {
  $code = $null
  if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
  if ($code -eq 404) {
    Say "远端仓库还不存在。" 'Yellow'
    Say "先去网页建一个空仓库（不要勾 README / .gitignore / LICENSE）：" 'Yellow'
    Say "  https://github.com/new?name=$Repo&visibility=public" 'Cyan'
    Fail "建完再跑一次本脚本。"
  } else {
    Say "远端检查跳过（网络或限流：$code）" 'Yellow'
  }
}

if ($DryRun) {
  Say "`n-DryRun：只检查，不提交也不推送。正式运行的推送命令：" 'Cyan'
  Say "  `"$git`" -C `"$RepoRoot`" push -u origin main" 'Cyan'
  exit 0
}

& $git -C $RepoRoot remote remove origin 2>$null
& $git -C $RepoRoot remote add origin "$url.git"

# ---------- 4. 推送 ----------
Say "`n开始推送。如果需要认证，git 会弹出登录窗口或在终端里问你要凭据。"
Say "（GitHub 从 2021-08 起不接受账号密码，认证要用 Personal Access Token 或浏览器授权）" 'Yellow'
& $git -C $RepoRoot push -u origin main 2>&1 | ForEach-Object { Say "  $_" }
if ($LASTEXITCODE -ne 0) {
  Fail "推送失败。" "凭据问题请用 PAT（Settings -> Developer settings -> Personal access tokens，勾 repo 权限）"
}

Say "`n推送完成。" 'Green'
Say "仓库地址: $url"
Say "`n在 DSH 插件里的订阅写法："
Say "  $User/$Repo" 'Cyan'
Say "`n接着：添加 -> 刷新 -> 安装（只有安装会让技能生效）。" 'Green'
