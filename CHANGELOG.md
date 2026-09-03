# Changelog

## 1.0.0 (first release)

### Fix
- **Null-safe launcher**: `dsh-rescue.ps1` no longer fails with
  `Cannot bind argument to parameter 'Path' because it is null` when
  `$env:APPDATA` is unset — it now resolves the DSH `bin.js` via a
  `Resolve-BinJs` fallback across `APPDATA` / `USERPROFILE` / profile paths.

### 新增功能
- **两级安全模式**：第 1 次崩溃禁用除白名单外插件；第 2 次(升级)连白名单也禁用，只留 `@deepseek-ai/*`。
- **DSH 版本检测**：记录 DSH 主体版本(dsh-web-app)到 `state.json`，管理台展示。
- 对齐 DSH 官方插件规范：补充 `keywords`(deepseek-harness/dsh-plugin/cordis)、`repository`/`homepage`/`bugs`、`engines`。

### Improvements
- `scripts/setup.js` writes the `dsh.ps1` patch as UTF-8 **with BOM** so
  non-ASCII comments survive on zh-CN Windows PowerShell (5.1 reads BOM-less
  `.ps1` as ANSI/GBK).
- Removed leftover `[DEBUG]* ` logging from the boot launcher.
- `README.md` install guide updated to the pnpm 10+ flow: authorize
  `postinstall` in the profile's `pnpm-workspace.yaml` via `allowBuilds`
  (pnpm no longer reads `package.json`'s `pnpm` field).
- Added `.gitignore` (excludes runtime `data/`, `node_modules/`, `*.tgz`).