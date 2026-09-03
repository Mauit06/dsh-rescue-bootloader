## dsh-rescue-bootloader v1.1.0 (Python)

救砖模块整体重构为**纯 Python**，彻底去掉 PowerShell。

### 变更
- 启动器 `dsh_rescue.py`：崩溃检测 + 两级安全模式 + DSH 版本检测。
- 救砖管理台 `rescue_server.py`：HTTP API（纯标准库，零三方依赖）。
- `scripts/setup.py` / `install.py` / `uninstall.py` / `release.py`：全部 Python。
- `lib/index.js` 保持 JS（cordis 契约），仅用于拉起 Python 的 `rescue_server.py`。
- 需求：Python 3.9+；纯标准库，无需 `pip install`。

### 安装
```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
```
（git 安装后需在 profile 的 `pnpm-workspace.yaml` 加 `allowBuilds: dsh-rescue-bootloader: true`；或使用本 Release 的 .tgz，`postinstall` 自动运行 `python scripts/setup.py`。）

**Release asset:** `dsh-rescue-bootloader-1.1.0.tgz`。