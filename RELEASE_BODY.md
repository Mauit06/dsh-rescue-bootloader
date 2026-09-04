## dsh-rescue-bootloader v1.1.2

纯 Python 救砖模块。本版本聚焦救砖管理台的可用性与正确性。

### 修复
- 第二次崩溃（升级禁用白名单）后，管理台不再丢失第三方插件列表：插件全集按 `当前 ∪ state ∪ 备份 ∪ 白名单 ∪ 依赖表` 合并计算；`rescue-backup` 始终携带全集清单，不会被二次崩溃覆盖缩水。

### 新增
- 救砖管理台 **“🚪 退出安全模式（恢复全部）”** 按钮：一键恢复崩溃前记录的全部插件并重启 DSH；备份缺失时按全集自动重建。

### 调整
- 启动/安全模式重启的检测超时统一延长至 **60 秒**（`--timeout` 可覆盖）。

### 安装 / 卸载（各一条命令）
```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
dsh plugin --profile web remove dsh-rescue-bootloader
```

**Release asset:** `dsh-rescue-bootloader-1.1.2.tgz`（备用：解压后 `python install.py`）。