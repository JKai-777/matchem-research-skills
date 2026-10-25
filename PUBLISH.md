# 推送与订阅

本机没有 winget 可用的安装通道（`winget install` 报 `0x80073cfc`），也没有管理员权限，所以走的是**便携版 Git**（已装好并验证）：

| 项 | 值 |
|---|---|
| git 二进制 | `C:\Users\23848\git\cmd\git.exe` |
| 版本 | `git version 2.56.0.windows.3` |
| 安装包 | PortableGit-2.56.0.3-64-bit.7z.exe，解压即用，不写注册表 |
| 签名 | `Status=Valid`，`Signer=CN=Johannes Schindelin, O=Johannes Schindelin, L=Bruehl, C=DE` |
| SHA256 | `4FC27B779829A36DF77911E3F4DEA09C66C790DD6C5F7DFA3B6A5479F1FE354F` |
| PATH | 已把 `C:\Users\23848\git\cmd` 追加到**用户** PATH（HKCU），新开的终端里直接可用的 `git` |
| 凭据助手 | `credential.helper = wincred`（Windows 凭据管理器） |

推送脚本：[tools/push_github.ps1](tools/push_github.ps1)

> 脚本文件必须保持 **UTF-8 带 BOM**。PowerShell 5.1 没有 BOM 时按 GBK 解码，中文注释会让脚本语法报错（`The '<' operator is reserved for future use`）。某些编辑器/自动化工具保存时会吃掉 BOM，改完脚本跑一次 `[IO.File]::ReadAllBytes($p)[0..2]` 确认前三个字节是 `239,187,191`。

## 第一步：在 GitHub 上建一个空仓库

打开（把用户名换成你自己的）：

```
https://github.com/new?name=matchem-research-skills&visibility=public
```

**必须是 public**——插件的 GitHub 订阅没有鉴权逻辑，私有库装不了。
**不要勾** "Add a README"、"Add .gitignore"、"Choose a license"，远端非空会导致 push 被拒。

## 第二步：跑推送脚本

在**你自己的终端**里执行（不要用管理员）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "G:\DSH work place\matchem-research-skills\tools\push_github.ps1" -User 你的GitHub账号
```

脚本会依次做：

1. 找到 git（新开的终端里 `git` 已在 PATH；老终端里没有就查 `%USERPROFILE%\git\cmd\git.exe`，即便携版位置）
2. `git init -b main` → `git add -A` → `git commit`（提交作者名/邮箱没配过会现场问你，建议邮箱用 GitHub 的 noreply 地址）
3. 调 GitHub API 检查远端是否存在、是否 public、是否非空
4. `git remote add origin` → `git push -u origin main`

只想检查不推送，加 `-DryRun`：它**不写配置、不提交、不推送**，只报告 git 位置、待提交文件数和远端状态。仓库现状已确认 `-DryRun` 跑完 `rev-list --all --count` 仍是 0。

本地已经准备好的部分：`.git` 已初始化（分支 `main`）、12 个文件已全部暂存（`## No commits yet on main`）、`core.autocrlf=false` 固定用 LF。所以脚本第一次跑起来就是从"待提交"直接进 commit。

如果忘了账号名，脚本会直接告诉你去哪个地址建库。

## 关于认证

GitHub 从 2021 年 8 月起不接受账号密码，推送时必须用 **Personal Access Token**：

1. GitHub → Settings → Developer settings → Personal access tokens → 勾 `repo` 权限
2. 推送时终端会问 `Username` 和 `Password`：用户名填 GitHub 账号，**密码位置粘贴 token**

凭据由 Windows 凭据管理器保存（`wincred`），第一次输过之后不用再输，也不进任何脚本、不进这个仓库。

> 为什么不走浏览器授权：便携版自带的 Git Credential Manager 在本机跑不起来，`git-credential-manager.exe --version` 直接崩（输出 `由于 Exception.ToString() 失败，因此无法打印异常字符串。`，退出码 `-532462766`），所以已把 helper 换成 `wincred`。换回去的办法是 `git config --global credential.helper manager`，但那需要先解决 GCM 崩溃。

## 第三步：在 DSH 里订阅

1. 侧边栏「插件」→ Skills Manager → 打开 `sidebarEntry`（或走「设置 → 技能」）
2. 进「发现」页 → GitHub 仓库订阅
3. 粘贴 `你的账号/matchem-research-skills`
4. 点「添加」——只登记记录，不下载、不扫描、不生效
5. 点「刷新」——下载 codeload 归档、解压、扫描 `SKILL.md`
6. 勾选目标根，点「安装」——安装时自动启用

安装目标只有三个：

| 目标 | 路径 | 适用 |
|---|---|---|
| 全局（DSH） | `C:\Users\23848\.dsh\skills` | 所有会话可用 |
| 公共 Agent | `%DSH_AGENTS_HOME%\skills` | 跨 agent 共享 |
| 项目 | `<工作区>\.dsh\skills` | 仅该工作区 |

如果远端默认分支不是 `main`，订阅地址要写成 `账号/matchem-research-skills/tree/分支名/skills`。

## 第四步：核验

```powershell
Get-ChildItem "C:\Users\23848\.dsh\skills" -Directory | Select-Object Name
Get-Content "C:\Users\23848\.dsh\skills-manager\repositories.json" -Raw
```

前者应出现三个新目录；后者记录里 `commit` 和 `refreshedAt` 应为非 null。

技能目录是「durable projection」，成员变化时宿主会追加一份完整的替换清单，**不需要重启 DSH**。

## 更新流程

1. 本地改内容 → `git commit` → `git push`
2. 插件里点「刷新」
3. 若技能本地被改过，插件会检测到并要求确认覆盖

历史备份在 `C:\Users\23848\.dsh\skills-manager\trash`，**不会自动清理**。

## 手工命令（脚本之外想自己来）

```powershell
$git = "C:\Users\23848\git\cmd\git.exe"
$repo = "G:\DSH work place\matchem-research-skills"
& $git -C $repo init -b main
& $git -C $repo config user.name "你的名字"
& $git -C $repo config user.email "you@example.com"
& $git -C $repo add -A
& $git -C $repo commit -m "feat: 材料化学研究流水线技能（文献 / 思路 / PPT）"
& $git -C $repo remote add origin https://github.com/你的账号/matchem-research-skills.git
& $git -C $repo push -u origin main
```
