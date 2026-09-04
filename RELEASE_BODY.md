## dsh-rescue-bootloader v1.1.3

修复 **“WebUI 任何操作闪出 cmd/pwsh 黑窗”** —— 根因是拦截补丁宽匹配：`dsh plugin --profile web …` 等子命令被误劫持拉起救援启动器。

### 本版本修复
- 拦截改**严格位置判定**：仅 `dsh web` / `dsh --profile web` 进入崩溃检测；其余子命令直通。已装机旧补丁加载时自动幂等升级。
- 全链路子进程**无窗化**：Node `windowsHide` / Python `CREATE_NO_WINDOW`（taskkill、管理台拉起、守护重载）。
- 管理台**单实例守卫**：第二实例检测到端口占用即退出（Windows SO_REUSEADDR 抢绑问题），并清理历史僵尸实例。
- 行为级回归入库：shim 四形态实跑断言、JS↔Python 配对还原、安全模式状态仿真。

### 功能保持
- 一条命令安装/卸载、两级安全模式、退出安全模式按钮、60 秒检测超时、依赖表兜底恢复列表。

### 安装 / 卸载
```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
dsh plugin --profile web remove dsh-rescue-bootloader
```

**Release asset:** `dsh-rescue-bootloader-1.1.3.tgz`。