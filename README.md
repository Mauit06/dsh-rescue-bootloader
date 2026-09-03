# dsh-rescue-bootloader

> DSH 救砖模块 — 类似 Windows 安全模式 / Magisk 救砖。
> 当 DSH 因插件崩溃无法启动时，自动进入安全模式，通过救砖管理台选择性恢复插件。

**v1.0.0** · MIT · Windows

---

## 功能特性

| 功能 | 说明 |
|------|------|
| **崩溃检测** | 监控 `dsh web` 启动；进程异常退出或端口 30 秒内无响应时触发救砖 |
| **安全模式** | 自动禁用所有非官方插件（保留 `@deepseek-ai/*` 和白名单插件） |
| **救砖管理台** | Web 界面 `http://127.0.0.1:8105`，可选择性重新启用插件 |
| **白名单** | 标记可信插件，安全模式下始终保留 |
| **崩溃日志** | 自动捕获崩溃时的 stdout/stderr；可查看、导出、清除 |
| **自启动** | DSH 启动时自动拉起救砖管理台 |

## 工作原理

1. 运行 `dsh web`（已被本插件拦截）
2. 启动器（`dsh-rescue.ps1`）启动 DSH 并监控启动过程
3. DSH 崩溃 → 自动进入安全模式，打开救砖管理台
4. 在管理台中逐个重新启用插件 → 应用并重启
5. 找到问题插件后，移除或修复即可

## 安装

### 方式一：官方插件命令（推荐）

```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
```

> 该插件带 `postinstall` 构建脚本，pnpm 10+ 首次安装时会默认阻止运行，需要授权。
> **必须在 profile 的 `pnpm-workspace.yaml` 中授权**（新版 pnpm 已不再读取 `package.json` 里的 `pnpm` 字段）：
>
> ```yaml
> allowBuilds:
>   dsh-rescue-bootloader: true
> ```
>
> 授权后重新运行安装：
>
> ```powershell
> dsh plugin --profile web install
> ```

安装完成后运行：

```powershell
dsh web
```

### 方式二：Release 包（无需授权）

1. 从 [Releases](https://github.com/Mauit06/dsh-rescue-bootloader/releases) 下载 `dsh-rescue-bootloader-1.0.0.tgz`
2. 用本地 tarball 方式安装（视为已发布产物，`postinstall` 默认直接运行，无需 allowBuilds）：

```powershell
dsh plugin --profile web add file:./dsh-rescue-bootloader-1.0.0.tgz
```

### 方式三：手动安装（ZIP / 解压）

1. 下载并解压 ZIP / tarball
2. 在解压目录中打开 PowerShell，运行：
   ```powershell
   .\install.ps1
   ```
3. 运行 `dsh web`

## 使用

| 命令 / 操作 | 说明 |
|------------|------|
| `dsh web` | 启动 DSH 并开启崩溃检测（崩溃时自动进入安全模式） |
| `http://127.0.0.1:8105` | 救砖管理台 — 安全模式下管理插件 |
| `http://127.0.0.1:3080` | DSH Web 界面 |

**救砖管理台操作：**

- ★（星标）— 切换插件白名单（安全模式下始终启用）
- ☐ 勾选框 — 选择要启用的插件
- **启用插件 / 禁用插件** — 仅标记该插件的待应用状态（不立即生效）
- **应用选中并重启 DSH** — 让所有标记为“启用”的插件生效并重启 DSH
- **导出 / 清除** — 导出或清除崩溃日志

## ⚠️ 注意事项 / 已知限制

- **仅 Windows**：拦截依赖 `dsh.cmd` / `dsh.ps1`（`%APPDATA%\npm`）。
- **仅拦截 `dsh web`**：如果改用 `dsh --profile web` 启动，则绕过本插件的崩溃检测。
- **需在前台控制台启动**：崩溃检测通过“包装启动 + 前台等待”实现，`dsh web` 窗口关闭时 DSH 也会退出。
- **安全模式只保留 `@deepseek-ai/*`**：若崩溃元凶本身是某个 `@deepseek-ai/*` 插件，安全模式不会禁用它（可能仍需手动移除）。
- **“应用/重启”会结束所有 DSH 进程**：救砖管理台点“应用/重启”会杀掉命令行含 `bin.js`/DSh 的 node 进程（含当前 DSH 会话），随后重新启动。
- **修改可逆**：进入安全模式前会备份 `package.json` 到 `package.json.rescue-backup`，可随时用管理台“恢复全部插件”还原。

## 卸载

### 官方方式

```powershell
dsh plugin --profile web remove dsh-rescue-bootloader
```

然后运行 `uninstall.ps1` 恢复 `dsh.cmd`/`dsh.ps1`：

```powershell
cd "$env:USERPROFILE\.dsh\profiles\web\node_modules\dsh-rescue-bootloader"
.\uninstall.ps1
```

### 手动卸载

```powershell
.\uninstall.ps1
```

## 文件结构

```
dsh-rescue-bootloader/
├── package.json          # 插件元数据（含 postinstall 脚本）
├── cordis.patch.yml      # DSH bundle 补丁
├── lib/
│   └── index.js          # 插件入口 — 自动启动救援服务器
├── scripts/
│   └── setup.js          # 安装后自动配置 dsh.cmd/dsh.ps1 拦截
├── dsh-rescue.ps1        # 启动器 — 崩溃检测与安全模式
├── rescue-server.mjs     # 救砖管理台后端（HTTP API）
├── rescue-ui.html        # 救砖管理台前端
├── install.ps1           # 手动安装脚本
├── uninstall.ps1         # 卸载脚本
├── CHANGELOG.md          # 变更日志
├── LICENSE               # MIT 协议
└── data/                 # 运行时数据（自动创建，已 gitignore）
    ├── .crash-flag       # 崩溃标记
    ├── state.json        # 安全模式状态
    ├── whitelist.json    # 白名单插件
    ├── last-boot.log     # 启动日志
    └── crash-logs/       # 崩溃历史
```

## 许可证

MIT
