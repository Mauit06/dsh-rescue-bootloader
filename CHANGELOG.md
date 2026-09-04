# Changelog

## 1.1.4 (pwsh 闪窗根修 + 救援自保 + 装机恢复)
- **修复**：PowerShell 黑窗仍闪的根因——v1.1.3 用 DETACHED_PROCESS 让 DSH 脱离控制台，导致 DSH 每次 spawn 控制台子进程（工具调用的 pwsh/python）都新分配可见窗口。改为 `CREATE_NEW_CONSOLE + SW_HIDE`「自带隐藏控制台」：子进程继承隐藏控制台不再闪窗，且关终端仍不杀 DSH。
- **加固**：两级安全模式任何级别都不再裁剪 `dsh-rescue-bootloader` 自身（修复升级安全模式后救援链自断、无法自愈还原的问题）。
## 1.1.3 (WebUI 闪窗修复)
- **修复(根因)**：拦截触发从宽匹配改为**严格位置判定**——仅 `dsh web` / `dsh --profile web` 进入救援；`dsh plugin --profile web …`（WebUI/工具链高频形态）不再被劫持拉起救援链导致 cmd/pwsh 黑窗闪现。cmd/ps1/sh 三套拦截同规则，装机旧补丁自动幂等升级。
- **修复**：全部子进程 spawn 静默化——Node `windowsHide`、Python `CREATE_NO_WINDOW`（含 taskkill/管理台拉起/守护重载），消除黑窗闪烁。
- **修复**：管理台单实例守卫——Windows 下 `SO_REUSEADDR` 允许多个 rescue_server 抢绑 8105，现第二实例检测到占用即退出（实机已清理 4 个端口互踩僵尸进程）。
- **新增**：行为级回归入库——shim 四形态实跑断言（cmd.exe/powershell.exe）、JS↔Python 配对还原测试、安全模式状态仿真测试（tests/）。
## 1.1.2
- **修复**：第二次崩溃（升级禁用白名单）后管理台第三方插件列表消失的问题——插件全集改为 `当前 ∪ state ∪ 备份 ∪ 白名单 ∪ 依赖表` 合并计算；`rescue-backup` 改为始终携带全集清单，不再被二次崩溃覆盖缩水。
- **新增**：管理台 “🚪 退出安全模式（恢复全部）” 按钮（备份缺失时按全集自动重建 bundles）。
- **调整**：启动与安全模式重启的检测超时统一由 30/20 秒延长为 **60 秒**（`--timeout` 可覆盖）。

## 1.1.1
## 1.1.1 (一条命令安装/卸载)
- **去除 postinstall 等全部构建脚本**：安装只需 `dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader`，不再需要 `allowBuilds` 手工授权。
- 拦截配置迁入插件生命周期：加载时**自动安装**、卸载/退出时**自动还原** dsh 包装脚本（幂等、写前备份 `.dsh-rescue-bak`、损坏自愈）。
- 拦截同时覆盖 `dsh web` 与 `dsh --profile web`。
- DSH 以 `DETACHED_PROCESS` 启动（关终端不再带走 DSH）；新增 `--daemon` 全程后台守护监控。
- 自动探测 `python/python3/py` 并缓存全路径（`data/python.path`），运行不依赖 PATH。
- 自动生成独立还原脚本 `~/.dsh/dsh-rescue-uninstall.py`（离线兜底）。
- 修复历史损坏：`dsh.cmd` 的 `:rundsh` 标签丢失/粘连导致的静默失效。

## 1.1.0 (Python rewrite)
- 救砖模块整体改用**纯 Python**（去掉 PowerShell）。
- 启动器 `dsh_rescue.py`：崩溃检测 + 两级安全模式 + DSH 版本检测。
- 管理台 `rescue_server.py`：HTTP API（纯标准库）。
- 安装/卸载/发布：`install.py` / `uninstall.py` / `release.py`。
- `lib/index.js` 保持 JS 仅作 DSH 插件入口，spawn Python 服务器。
- 需求：Python 3.9+，纯标准库，零三方依赖。

## 1.0.1
- **两级安全模式**：第 1 次崩溃禁用除白名单外插件；第 2 次(升级)连白名单也禁用，只留 `@deepseek-ai/*`。
- **DSH 版本检测**：记录 DSH 主体版本(dsh-web-app)到 `state.json`，管理台展示。
- **对齐 DSH 官方插件规范**：补齐 `keywords`(deepseek-harness/dsh-plugin/cordis)、`repository`/`homepage`/`bugs`、`engines(node>=20.11)`。
- **Bug 修复**：空值安全启动器(Path-null)、UTF-8 JSON 读取(dsh-rescue/install/uninstall)、精确进程清理、BOM 补丁。

## 1.0.0 (first release)
- 空值安全启动器，修复 `dsh web` 的 `Path is null`。
- 安全模式、救砖管理台、白名单、崩溃日志、自启动。