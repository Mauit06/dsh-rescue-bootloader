## dsh-rescue-bootloader v1.0.0

DSH 救砖模块 — 崩溃检测、安全模式、救砖管理台一体化插件。类似 Windows 安全模式 / Magisk 救砖。

### 修复
- `dsh web` 启动器不再报 `Cannot bind argument to parameter 'Path' because it is null`（通过 `Resolve-BinJs` 跨 APPDATA/USERPROFILE/profile 回退解析 DSH bin.js）。
- `dsh-rescue.ps1` 读取 JSON 显式用 UTF-8，避免中文 description 导致 `ConvertFrom-Json` 失败。

### 改进
- `setup.js` 以 UTF-8 (BOM) 写入 dsh.ps1 拦截补丁，避免中文注释乱码。
- 移除启动器中的 `[DEBUG]` 输出。
- README 安装文档更新为 pnpm 10+ 的 `allowBuilds`（pnpm-workspace.yaml）授权流程。
- 新增 `.gitignore` 与 `CHANGELOG.md`。

### 安装
```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
```
（git 安装后需在 profile 的 pnpm-workspace.yaml 加 `allowBuilds: dsh-rescue-bootloader: true`；或使用本 Release 的 .tgz。）

**Release asset:** `dsh-rescue-bootloader-1.0.0.tgz`（12 个文件，含 CHANGELOG.md）。