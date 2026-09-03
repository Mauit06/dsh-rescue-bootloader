## dsh-rescue-bootloader v1.1.1

DSH 救砖模块 —— 纯 Python、**一条命令安装/卸载**。

### 这个版本解决什么
- 安装不再需要任何手工步骤：移除 postinstall/构建脚本，`allowBuilds` 授权正式成为历史。
- 卸载也只需一条 `dsh plugin remove`：拦截块由插件自动安装、自动还原（幂等、写前备份、损坏自愈）。
- `dsh web` 与 `dsh --profile web` 都会被拦截。
- DSH 不再随终端关闭退出（DETACHED_PROCESS），可选 `--daemon` 全程后台守护。
- 自动探测 Python 并缓存全路径，运行不依赖 PATH。
- 修复旧版 `dsh.cmd` 拦截损坏（`:rundsh` 标签丢失/粘连导致的静默失效）。

### 安装
```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
```
重启一次 DSH 即自动完成拦截配置。卸载：
```powershell
dsh plugin --profile web remove dsh-rescue-bootloader
```

**Release asset:** `dsh-rescue-bootloader-1.1.1.tgz`（备用：解压后 `python install.py`）。