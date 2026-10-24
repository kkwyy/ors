# Git 工作流与 CI 入门（本项目的实操版）

> 目标：读完你能独立完成「开分支 → 改代码 → 提 PR → 看 CI → 合并」，
> 并且知道这套东西为什么存在、出问题时去哪里看。

---

## 1. 先看全局地图

```
┌──────────────┐   commit    ┌──────────────┐   push    ┌────────────────┐
│  你的工作区   │ ─────────→ │  本地 Git     │ ───────→ │  GitHub 仓库    │
│  编辑器/终端  │             │  历史 + 分支  │          │  main + PR     │
└──────────────┘             └──────────────┘          └───────┬────────┘
       │                                                      │ 触发
       │  make check / pre-commit                             ↓
       └─────────────── 本地门禁                    ┌──────────────────┐
                                                    │ GitHub Actions   │
                                                    │ lint / test ×4   │
                                                    └────────┬─────────┘
                                                             │ 状态回写
                                                             ↓
                                                    PR 页面 ✅ / ❌
```

四个角色，各管一件事：

| 角色 | 管什么 | 不管什么 |
|---|---|---|
| 工作区 | 你正在编辑的文件 | 历史 |
| 本地 Git | 提交历史、分支、回滚 | 远端协作 |
| GitHub | 托管、PR、代码评审、权限 | 跑测试 |
| GitHub Actions | 在干净机器上装依赖、跑检查 | 存代码 |

**核心思想：本地越早发现的问题，修复成本越低。**
pre-commit（秒级）→ `make check`（十秒级）→ CI（分钟级）。

---

## 2. Git 分支模型

### 2.1 一条铁律

**`main` 永远是可发布状态。所有改动都走分支 + PR。**

不要在 `main` 上直接写代码。原因：`main` 是别人（以及未来的你）拉取、部署、打 tag 的基准；
它一旦坏了，所有下游都坏。

### 2.2 分支命名

| 前缀 | 用途 | 例子 |
|---|---|---|
| `feat/` | 新功能 | `feat/farkas-certificate` |
| `fix/` | 修 bug | `fix/iis-timeout` |
| `docs/` | 文档 | `docs/git-ci-guide` |
| `chore/` | 杂务 | `chore/bump-highspy` |
| `refactor/` | 重构 | `refactor/backend-interface` |

### 2.3 日常流程（背下来）

```bash
# 1. 从最新的 main 开分支
git switch main
git pull --ff-only
git switch -c feat/farkas-certificate

# 2. 改代码，随时提交
git add -A
git commit -m "feat: extract Farkas ray from dual simplex"

# 3. 推到远端（第一次带 -u，之后直接 git push）
git push -u origin HEAD

# 4. 在 GitHub 上开 Pull Request
#    仓库页面会出现 "Compare & pull request" 按钮

# 5. 等 CI 绿 → 评审 → Squash and merge

# 6. 回到 main，删掉本地分支
git switch main
git pull --ff-only
git branch -d feat/farkas-certificate
```

### 2.4 最常用的几条命令

| 命令 | 作用 |
|---|---|
| `git status` | 我现在改了哪些文件 |
| `git diff` | 具体改了什么 |
| `git log --oneline --graph --all` | 看分支和提交历史 |
| `git switch -c <name>` | 新建并切换分支 |
| `git switch main` | 切回主分支 |
| `git add -A && git commit -m "..."` | 提交全部改动 |
| `git push -u origin HEAD` | 推送当前分支 |
| `git pull --ff-only` | 拉取并快进（不产生 merge commit） |
| `git restore <file>` | 丢弃未暂存的改动 |
| `git reset --soft HEAD~1` | 撤销最后一次提交，保留改动 |

### 2.5 提交信息怎么写

```
<type>: <一句话说明>

可选正文：为什么改、改了什么、有什么副作用
```

`type` 用 `feat` / `fix` / `docs` / `test` / `refactor` / `chore` / `perf`。
不需要很长，但要能让半年后的你一眼看懂。

---

## 3. CI 是什么

### 3.1 一句话

**CI（Continuous Integration，持续集成）= 每次你推代码，机器自动在干净环境里装依赖、跑检查、跑测试。**

### 3.2 为什么需要

- 你的机器能跑，不代表别人的机器能跑（Python 3.10 vs 3.13、macOS vs Linux）。
- 改 A 模块可能悄悄弄坏 B 模块，靠人肉回归不现实。
- PR 需要一个客观的「能不能合并」的判据，而不是「我觉得没问题」。
- 出问题时，CI 日志是唯一可复现的证据。

### 3.3 术语表

| 术语 | 含义 | 本项目的值 |
|---|---|---|
| **Workflow** | 一个 YAML 文件，描述一套自动化 | `.github/workflows/ci.yml` |
| **Trigger** | 什么时候跑 | push 到 main、PR、手动 |
| **Job** | 一组步骤，跑在独立机器上 | `lint`、`test` |
| **Step** | 一条命令或一个 action | `ruff check .` |
| **Runner** | 执行 Job 的机器 | `ubuntu-latest` |
| **Matrix** | 参数组合，一次跑多份 | Python 3.10/3.11/3.12/3.13 |
| **Cache** | 缓存依赖，加速后续运行 | pip 缓存 |
| **Artifact** | 运行产物（日志、报告） | 暂未使用 |
| **Concurrency** | 同一分支只保留最新一次运行 | 已配置 |
| **Secrets** | 加密的密钥（token、密码） | 暂未使用 |

### 3.4 免费额度

- **公开仓库：Actions 免费，无时长限制**（有并发限制）。
- 私有仓库：每月 2000 分钟（Linux），超出按分钟计费。

本项目是 Public，所以随便跑。

---

## 4. 逐段读懂 `ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, master]   # 推到主分支时跑
  pull_request:                # 任何 PR 都跑
  workflow_dispatch:           # 允许在网页上手动触发

permissions:
  contents: read               # 最小权限：只读代码

concurrency:
  group: ci-${{ github.ref }}  # 同一个分支/PR 共用一个组
  cancel-in-progress: true     # 新提交来了，取消上一次没跑完的
```

三个 job 级概念：

```yaml
jobs:
  lint:                        # job 1：静态检查
    runs-on: ubuntu-latest     # 跑在 GitHub 提供的 Ubuntu 上
    steps:
      - uses: actions/checkout@v4          # 把代码拉到 runner
      - uses: actions/setup-python@v5      # 装指定 Python
        with:
          python-version: "3.13"
          cache: pip                       # 缓存 pip 下载
          cache-dependency-path: pyproject.toml
      - run: pip install -e ".[highs,dev]" # 和本地一样的安装方式
      - run: pip check                     # 依赖有没有冲突
      - run: ruff check .                  # 代码规范
      - run: ruff format --check .         # 格式是否统一（只检查不改）
      - run: mypy src/ors                  # 类型检查
```

```yaml
  test:                        # job 2：测试矩阵
    strategy:
      fail-fast: false         # 一个版本挂了，其他版本继续跑
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[highs,dev]"
      - run: python -m pytest -q
```

**为什么 lint 和 test 分开？**
- 并行跑，总时间更短。
- 失败时一眼看出是「代码不规范」还是「功能坏了」。
- lint 只跑一个 Python 版本，没必要矩阵。

**为什么 test 要跑 4 个版本？**
- `requires-python = ">=3.10"` 是对用户的承诺，CI 负责验证这个承诺。
- 不同版本的 `typing`、`dataclasses`、依赖 wheel 都可能有差异。

---

## 5. 一次 PR 的完整生命周期

```
开分支 → 写代码 → commit → push
                            │
                            ↓
                    GitHub 自动开 PR 页面
                            │
              ┌─────────────┴─────────────┐
              ↓                           ↓
        CI 跑 lint/test            你继续改代码
              │                     （push 会自动重跑）
              ↓
        全绿 → Review → Squash merge → 删分支
              │
              ↓
        main 更新，自动部署/发布（未来）
```

PR 页面上的几个关键区域：

- **Conversation**：描述、评论、CI 状态。
- **Commits**：这个 PR 包含哪些提交。
- **Checks**：CI 的每个 job 和 step。
- **Files changed**：逐行 diff，可以留评论。
- **Merge 按钮**：CI 没绿时通常是灰的（如果配了分支保护）。

---

## 6. CI 挂了怎么看

### 6.1 定位

1. 打开 **Actions** 标签页。
2. 点最新的红色 ❌ run。
3. 左侧选 job（`lint & types` 或 `test (py3.x)`）。
4. 展开红色的 step。
5. **从上往下找第一个 `Error` / `error:`**，后面的往往是连锁反应。

### 6.2 常见失败与修复

| 报错 | 原因 | 修复 |
|---|---|---|
| `ruff format --check` 失败 | 格式不统一 | 本地 `make format`，提交 |
| `ruff check` 失败 | 规范问题（未用导入、行太长） | `make lint`，按提示改 |
| `mypy` 失败 | 类型不匹配 | 看文件:行号，修注解 |
| `pytest` 某个版本失败 | 版本差异 / 真实 bug | 本地用该版本复现 |
| `pip install` 失败 | wheel 不兼容 / 网络 | 看是哪个包、哪个 Python |
| `Repository not found` | 权限/仓库名错 | 检查 remote URL |

### 6.3 重跑

- **Re-run all jobs**：全部重跑。
- **Re-run failed jobs**：只重跑失败的（省时间）。
- 注意：重跑用的是同一个 commit，不会包含你后来的修改。

### 6.4 本地复现

```bash
make check                 # ruff + mypy + pytest
make format                # 自动修格式
ruff format --check .      # 只检查，和 CI 一致
```

**原则：CI 失败时，先在本地复现，再修，再推。不要靠反复重跑碰运气。**

---

## 7. pre-commit、make、CI 三者什么关系

| | pre-commit | `make check` | CI |
|---|---|---|---|
| 位置 | 本地 | 本地 | 远端 |
| 触发 | `git commit` | 手动 | push / PR |
| 范围 | 本次暂存的文件 | 全部 | 全部 |
| 速度 | 秒级 | 十秒级 | 分钟级 |
| 能否跳过 | `--no-verify` | 不适用 | 不能 |
| 权威性 | 低（可绕过） | 中 | 高 |

- **pre-commit**：本地门卫，拦截明显问题（格式、尾随空格、debug 语句）。
- **make check**：提交前体检，跑完整的 lint + 类型 + 测试。
- **CI**：远端守门员，最终裁决，也是 PR 合并的依据。

三者跑的是同一套工具，所以结果应该一致。如果不一致，通常是环境差异（版本、依赖）。

---

## 8. 给 main 加分支保护（建议做）

仓库 → **Settings → Branches → Add branch protection rule**：

- Branch name pattern: `main`
- ✅ Require a pull request before merging
- ✅ Require status checks to pass before merging
  - 搜索并勾选：`lint & types`、`test (py3.10)`、`test (py3.11)`、`test (py3.12)`、`test (py3.13)`
  - 注意：这些 check 要**先跑过一次**才会出现在列表里
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings

效果：以后谁都不能直接 push `main`，必须 PR + 全绿。这是保护自己的最重要一步。

---

## 9. 本项目的全局结构

```
ors/
├── src/ors/
│   ├── model.py           # 建模层：Var / LinearExpr / Constraint / Model
│   ├── result.py          # Result / SolveOptions
│   ├── status.py          # 状态枚举
│   ├── diagnose.py        # IIS、体检、报告、Diagnosis
│   ├── backend/
│   │   └── highs_backend.py  # 把 Model 翻译成 HiGHS，读 MPS
│   ├── cli.py             # 命令行入口
│   └── __init__.py        # 公开 API
├── tests/                 # 与模块一一对应
├── docs/                  # 设计、路线图、本指南
├── examples/              # 可运行示例
└── .github/workflows/     # CI
```

### 数据流

```
用户代码
  │  m.add_var / add_constr
  ↓
Model（保留名字和原始表达式）
  │  m.optimize()
  ↓
highs_backend.solve()
  │  建 HighsLp → passModel → run
  ↓
Result（status / objective / x / dual）
  │  如果 infeasible
  ↓
diagnose()
  │  删除过滤 / 加性方法，反复调用 solve
  ↓
Diagnosis（IIS + findings + 报告）
```

### 扩展点（以后加功能看这里）

| 想加什么 | 改哪里 |
|---|---|
| 新求解器后端 | `backend/` 下新增模块，实现 `solve` / `read_model` |
| 新诊断方法 | `diagnose.py` 的 `_compute_iis` 加分支 |
| 新体检项 | `_check_model` 加规则 |
| 新证书类型 | 新增 `certificate.py` + `verify/` |
| 新报告格式 | `Diagnosis.report` 加分支 |
| 新命令行子命令 | `cli.py` |

### 测试与 CI 的对应

- `tests/test_model.py` → 建模层，不依赖求解器。
- `tests/test_solve.py` → 后端求解，依赖 highspy。
- `tests/test_diagnose.py` → IIS 与报告。
- CI 在 4 个 Python 版本上重复跑这些测试。

---

## 10. 发布流程（现在不用，先知道）

1. 版本号从 `0.0.1` 升到 `0.1.0`（`pyproject.toml`）。
2. 打 tag：`git tag v0.1.0 && git push origin v0.1.0`。
3. 未来在 CI 里加一个 `release` job：构建 wheel、上传 GitHub Release、发布到 PyPI。
4. 用户 `pip install ors` 即可。

在 1.0 之前，版本号 `0.x`，API 可以变，但每次破坏性变更要写 CHANGELOG。

---

## 11. 常见问题

**Q: CI 没触发？**
检查：推的是不是 `main`？YAML 缩进对不对（用 `check-yaml`）？Actions 是否被禁用（Settings → Actions）？

**Q: 一直 queued？**
并发组限制、免费额度、GitHub 状态页故障。先看 https://www.githubstatus.com。

**Q: 缓存没生效？**
`cache-dependency-path` 要指向会变化的依赖文件；本项目是 `pyproject.toml`。

**Q: 能不能跳过 CI？**
管理员可以 bypass，但**不要**。CI 是给你自己兜底的。

**Q: `--no-verify` 什么时候用？**
只在紧急修复、且你明确知道后果时。用过之后要补一次完整检查。

**Q: Dependabot 的 PR 要合并吗？**
看 CI 是否绿。绿了就合，尤其是 patch 版本；major 版本要读 changelog。

---

## 12. 你现在可以做的练习

1. 开一个分支 `docs/ci-practice`，改一行 README，提交、推送。
2. 在 GitHub 上开 PR，看 CI 跑。
3. 故意把某个测试改坏，推上去，看红色 ❌ 长什么样。
4. 修好，看变绿。
5. Squash merge，删分支。
6. 给 `main` 加分支保护。

做完这六步，Git + CI 的基本盘你就掌握了。
