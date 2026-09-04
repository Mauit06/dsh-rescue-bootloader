# dsh-rescue-bootloader

> DSH 救砖模块 — 崩溃检测、两级安全模式、救砖管理台一体化插件。类似 Windows 安全模式 / Magisk 救砖。
> 纯 Python 实现（零三方依赖）：当 DSH 因插件崩溃无法启动时自动进入安全模式，经救砖管理台选择性恢复插件。

**v1.1.4 (Python 版)** · MIT · 面向 Windows（拦截依赖 `dsh.cmd` / `dsh.ps1`）

---

## Python 运行要求

- **Python 3.9+**（实测 3.14.3）：`python` / `py` 需在 PATH。
- **Node.js**：DSH 本体需要（用于启动 `node .../dsh/lib/bin.js web`）。
- **DSH**：`@deepseek-ai/dsh` 全局安装。
- 本插件的 Python 部分**只用标准库**（`subprocess` / `http.server` / `json` / `socket`），无需 `pip install` 任何东西。

> 说明：DSH 插件入口 `lib/index.js` 保持 JS（cordis 插件契约要求），它只负责在 DSH 启动时拉起 Python 的 `rescue_server.py`；其余（启动器/管理台后端/安装卸载）全部为 Python。

## 功能特性

| 功能 | 说明 |
|------|------|
| **崩溃检测** | `dsh_rescue.py` 启动 DSH 并监控；进程异常退出或端口 **60 秒**内无响应即触发救砖（`--timeout` 可调） |
| **两级安全模式** | 第 1 次崩溃禁用除白名单外的所有插件；第 2 次（升级）连白名单也禁用，只留 `@deepseek-ai/*` |
| **版本检测** | 记录 DSH 主体版本（`dsh-web-app`）到 `state.json`，帮助判断破坏性更新兼容性 |
| **救砖管理台** | `rescue_server.py` 提供 HTTP 服务 `http://127.0.0.1:8105`，选择性重新启用插件 |
| **白名单** | 标记可信插件——第一次安全模式下保留；第二次崩溃时同样被禁用 |
| **崩溃日志** | 自动捕获崩溃时的 stdout/stderr；可查看、导出、清除 |
| **自启动** | DSH 启动时自动拉起救砖管理台（Python） |

## 工作原理

1. 运行 `dsh web`（已被本插件拦截）
2. 启动器 `dsh_rescue.py` 启动 DSH（`node .../bin.js web`）并监控启动，同时记录 DSH 主体版本
3. DSH 崩溃 → 第 1 次进入安全模式（保留官方 + 白名单），打开救砖管理台
4. 若安全模式下仍崩溃 → 第 2 次升级为仅保留官方（连白名单也禁用）
5. 在管理台中逐个重新启用插件 → 应用并重启；成功后自动复位崩溃计数

## 安装（一条命令）

```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
```

从 v1.1.1 起插件**不再包含任何构建脚本**（无 postinstall），因此**无需 pnpm 的 `allowBuilds` 授权**。
插件加载时会自动：

1. 在全局 dsh 包装脚本（`dsh.cmd` / `dsh.ps1` / `dsh`）中装入崩溃检测拦截——此后 `dsh web` 与 `dsh --profile web` 都经 `dsh_rescue.py` 守护；
2. 拉起救砖管理台 `http://127.0.0.1:8105`。

装完后**重启一次 DSH**（或新开终端跑 `dsh web`）即自动生效，之后无需任何手动配置。

> 备用（离线/手动）：下载 [Releases](https://github.com/Mauit06/dsh-rescue-bootloader/releases) 的 .tgz / ZIP 解压后运行 `python install.py`。
## 使用

| 命令 / 操作 | 说明 |
|------------|------|
| `dsh web` | 启动 DSH 并开启崩溃检测（崩溃时自动进入安全模式） |
| `http://127.0.0.1:8105` | 救砖管理台 — 安全模式下管理插件 |
| `http://127.0.0.1:3080` | DSH Web 界面 |

**救砖管理台操作：**

- ★（星标）— 切换插件白名单
- ☐ 勾选框 — 选择要启用的插件
- **启用插件 / 禁用插件** — 仅标记待应用状态（不立即生效）
- **应用选中并重启 DSH** — 让标记为“启用”的插件生效并重启 DSH
- **导出 / 清除** — 导出或清除崩溃日志
- **🚪 退出安全模式（恢复全部）** — 一键恢复崩溃前记录的全部插件并重启 DSH

## ⚠️ 注意事项 / 已知限制

- **Python 版**：启动器/管理台/安装脚本均为 Python（纯标准库，跨平台逻辑）；拦截依赖 `dsh.cmd`/`dsh.ps1`（Windows）/ `dsh` shell 包装（非 Windows）。
- **仅两种形态进入拦截**：`dsh web` 与 `dsh --profile web`；`dsh plugin --profile web …` 等子命令一律直通 DSH，不会被劫持（v1.1.3 修复 WebUI 操作闪窗的根因）。
- **自动安装/还原**：拦截块的写入与还原全部由插件自身完成（幂等、写前自动备份 `*.dsh-rescue-bak`、损坏可自愈）；Python 全路径缓存于 `data/python.path`，运行不依赖 PATH（加载时自动探测 `python`/`python3`/`py -3`）。
- **DSH 不随终端关闭而退出**：启动器用 `DETACHED_PROCESS` 启动 DSH；加 `--daemon` 则启动器本身也后台守护、全程监控崩溃。
- **安全模式只保留 `@deepseek-ai/*`**：profile 中仅 `@deepseek-ai/dsh-base`、`@deepseek-ai/dsh-web-app` 两个核心会保留，其余第三方一律禁用；若元凶是这两个核心则无法禁用。
- **“应用/重启”结束 DSH 进程**：通过 PID 文件精确清理，不误杀其它 node 应用。
- **修改可逆**：进入安全模式前备份 `package.json` 到 `package.json.rescue-backup`，可用管理台“恢复全部插件”还原。

## 卸载（一条命令）

```powershell
dsh plugin --profile web remove dsh-rescue-bootloader
```

插件被卸载（reload 或 DSH 退出）时，会**自动还原**全部 dsh 包装脚本；首次写入前已备份为同目录 `*.dsh-rescue-bak`。

若插件目录曾被手动/离线删除，运行安装时自动放置的独立还原脚本：

```powershell
python "$env:USERPROFILE\.dsh\dsh-rescue-uninstall.py"
```

## 文件结构

```
dsh-rescue-bootloader/
├── package.json          # 插件元数据（无构建脚本，拦截由插件自动安装）
├── cordis.patch.yml      # DSH bundle 补丁
├── lib/
│   └── index.js          # 插件入口(JS) — 拉起 Python 救援服务器
├── scripts/
│   └── setup.py          # 安装后拦截 dsh.cmd/dsh.ps1 → Python 启动器
├── dsh_rescue.py         # 启动器 — 崩溃检测 + 两级安全模式 + 版本检测
├── rescue_server.py      # 救砖管理台后端（HTTP API）
├── rescue-ui.html        # 救砖管理台前端
├── install.py            # 手动安装脚本
├── uninstall.py          # 卸载脚本
├── CHANGELOG.md          # 变更日志
├── LICENSE               # MIT 协议
└── data/                 # 运行时数据（自动创建，已 gitignore）
    ├── state.json        # 安全模式状态(含 crashCount/dshVersion)
    ├── whitelist.json    # 白名单插件
    ├── dsh.pid           # 记录 DSH 进程 PID
    ├── python.path       # 记录 Python 可执行路径
    ├── last-boot.log     # 启动日志
    └── crash-logs/       # 崩溃历史
```

## 许可证

MIT