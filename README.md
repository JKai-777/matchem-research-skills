# matchem-research-skills

面向材料化学研究的 DSH 技能仓库：**文献 → 思路 → PPT** 三段流水线，一环一个技能。

由 DSH「技能管理」插件的 **发现 → GitHub 仓库订阅** 扫描安装。仓库里每个 `SKILL.md` 就是一个技能。

## 技能清单

| 技能名 | 负责环节 | 产出 |
|---|---|---|
| `matchem-literature-review` | 文献环 | 检索记录 + 筛选清单 + 关键数据表 + gap 陈述 |
| `matchem-research-design` | 思路环 | 可证伪假设 + ≥2 条互斥路线 + 风险清单 + 对照组设计 |
| `matchem-report-deck` | PPT 环 | 一页一论点大纲 + 12 页上下成稿 + 可溯源参考文献 |

三段是串联的：上一环的交付物是下一环的输入。gap 不落在数据表的空缺处，就退回文献环重做。

## 目录结构

```
matchem-research-skills/
├── README.md
├── PUBLISH.md                          # 推送与订阅步骤
├── LICENSE
├── skills/
│   ├── matchem-literature-review/
│   │   ├── SKILL.md
│   │   └── references/search-record-template.md
│   ├── matchem-research-design/
│   │   ├── SKILL.md
│   │   └── references/control-group-checklist.md
│   └── matchem-report-deck/
│       ├── SKILL.md
│       └── references/deck-outline-template.md
└── tools/
    ├── verify_repo.py                  # 本地校验，复刻插件扫描规则
    └── push_github.ps1                 # 初始化 + 检查远端 + 推送
```

## 安装

在 DSH 技能管理插件的「发现」页 → GitHub 仓库订阅 → 粘贴：

```
<你的账号>/matchem-research-skills
```

地址也可以写成 `https://github.com/<账号>/matchem-research-skills/tree/main/skills`，带上 `skills` 子目录可以只扫这一层（但归档仍会整库下载）。

**添加不会下载也不会生效**，必须接着点「刷新」扫描、再点「安装」。安装时会自动启用技能，不需要重启 DSH。

## 硬限制（来自插件，超了直接报错）

| 项 | 上限 |
|---|---|
| 单仓库归档 | 32 MiB |
| 解压总量 / 条目数 | 64 MiB / 10000 |
| 仓库数 | 30 |
| 每仓库技能数 | 500 |
| 单个 `SKILL.md` | 256 KiB |
| 技能正文合计 | 4 MiB |
| 单技能文件数 | 1000 |

另外：只支持**公开仓库**，插件没有鉴权逻辑。

## 写自己的技能时注意

插件的有效性判定（`repositories.js:653`）要求同时满足：

1. `SKILL.md` 首行是 `---`，且能找到闭合的 `---`
2. frontmatter 里有 `name`，且严格匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$`（小写字母、数字、单连字符）
3. `name` 不是 Windows 保留名（`con`/`prn`/`aux`/`nul`/`com1-9`/`lpt1-9`）
4. `name` 长度 ≤ 100
5. `description` 非空

任何一条不满足，技能会显示为无效，装不了。frontmatter 解析器只认 `key: value` 单行标量，也支持 `|` 和 `>` 块标量——写嵌套 YAML 结构它读不到。

## 校验

改完内容先跑本地校验，别等推到 GitHub 才发现装不上：

```powershell
& "C:\Users\23848\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" tools/verify_repo.py .
```

脚本逐项复刻插件规则，输出每个技能的有效性和各项尺寸占用。

## 许可

MIT，见 [LICENSE](LICENSE)。
