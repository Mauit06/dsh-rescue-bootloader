# Changelog

## 1.0.0 (first release)

### Fix
- **Null-safe launcher**: `dsh-rescue.ps1` no longer fails with
  `Cannot bind argument to parameter 'Path' because it is null` when
  `$env:APPDATA` is unset — it now resolves the DSH `bin.js` via a
  `Resolve-BinJs` fallback across `APPDATA` / `USERPROFILE` / profile paths.

### Improvements
- `scripts/setup.js` writes the `dsh.ps1` patch as UTF-8 **with BOM** so
  non-ASCII comments survive on zh-CN Windows PowerShell (5.1 reads BOM-less
  `.ps1` as ANSI/GBK).
- Removed leftover `[DEBUG]* ` logging from the boot launcher.
- `README.md` install guide updated to the pnpm 10+ flow: authorize
  `postinstall` in the profile's `pnpm-workspace.yaml` via `allowBuilds`
  (pnpm no longer reads `package.json`'s `pnpm` field).
- Added `.gitignore` (excludes runtime `data/`, `node_modules/`, `*.tgz`).
