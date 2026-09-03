## dsh-rescue-bootloader v1.0.1

DSH 救砖模块 — 崩溃检测、两级安全模式、救砖管理台一体化插件。类似 Windows 安全模式 / Magisk 救砖。

### 新增
- **两级安全模式**：第 1 次崩溃禁用除白名单外插件；第 2 次(升级)连白名单也禁用，只留 `@deepseek-ai/*`。
- **DSH 版本检测**：记录 DSH 主体版本(基于 dsh-web-app)到 state.json，救砖管理台顶部展示，便于判断破坏性更新兼容性。
- **对齐 DSH 官方插件规范**：keywords(deepseek-harness/dsh-plugin/cordis)、repository/homepage/bugs/engines。

### 修复
- `dsh web` 启动器不再报 `Cannot bind argument to parameter 'Path' because it is null`（`Resolve-BinJs` 跨 APPDATA/USERPROFILE/profile 回退）。
- JSON 读取显式 UTF-8，避免中文 description 导致 `ConvertFrom-Json` 失败。
- 安全模式/重启只精确清理 dsh 进程，不再误杀无关 node 应用。
- `setup.js` 以 UTF-8(BOM) 写入补丁，避免中文注释乱码。

### 安装
```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
```
（git 安装后需在 profile 的 pnpm-workspace.yaml 加 `allowBuilds: dsh-rescue-bootloader: true`；或使用本 Release 的 .tgz，`postinstall` 自动运行。）

**Release asset:** `dsh-rescue-bootloader-1.0.1.tgz`。