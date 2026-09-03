## dsh-rescue-bootloader v1.2.0

DSH 救砖模块 —— 纯 Python、**一条命令安装/卸载**。

### 这个版本解决什么
- 安装不再需要任何手工步骤：移除了 postinstall/构建脚本，`allowBuilds` 授权正式成为历史。
- 卸载也只需一条 `dsh plugin remove`：拦截块由插件自动安装、自动还原。
- `dsh web` 与 `dsh --profile web` 都会被拦截。
- DSH 不再随终端窗口关闭而退出（`DETACHED_PROCESS`），可选 `--daemon` 全程后台守护。
- Python 自动探测并缓存全路径，运行不依赖 PATH。
- 附带损坏自愈：修复了旧版 dsh.cmd 拦截（标签丢失/粘连）静默失效问题。

### 安装
```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
```
重启 DSH 一次即自动完成拦截配置；卸载：
```powershell
dsh plugin --profile web remove dsh-rescue-bootloader
```

**Release asset:** `dsh-rescue-bootloader-1.2.0.tgz`（可 `python install.py` 手动安装）。