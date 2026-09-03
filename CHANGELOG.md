# Changelog

## 1.0.1
- **两级安全模式**：第 1 次崩溃禁用除白名单外插件；第 2 次(升级)连白名单也禁用，只留 `@deepseek-ai/*`。
- **DSH 版本检测**：记录 DSH 主体版本(dsh-web-app)到 `state.json`，管理台展示。
- **对齐 DSH 官方插件规范**：补齐 `keywords`(deepseek-harness/dsh-plugin/cordis)、`repository`/`homepage`/`bugs`、`engines(node>=20.11)`。
- **Bug 修复**：空值安全启动器(Path-null)、UTF-8 JSON 读取(dsh-rescue/install/uninstall)、精确进程清理、BOM 补丁。

## 1.0.0 (first release)
- 空值安全启动器，修复 `dsh web` 的 `Path is null`。
- 安全模式、救砖管理台、白名单、崩溃日志、自启动。