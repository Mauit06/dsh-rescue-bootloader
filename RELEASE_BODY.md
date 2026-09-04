## dsh-rescue-bootloader v1.1.4

收尾修复：WebUI 操作仍闪 PowerShell 黑窗的根因（DETACHED 使 DSH 子进程各自新建可见控制台）→ 改为「自带隐藏控制台」方案：不再闪窗、关终端也不杀 DSH。

- 加固：两级安全模式不再裁剪救援插件自身（防救援链自断）
- 保持：严格拦截（仅 `dsh web` / `dsh --profile web`）、全链路无窗、单实例管理台、一条命令安装/卸载

```powershell
dsh plugin --profile web add github:Mauit06/dsh-rescue-bootloader
dsh plugin --profile web remove dsh-rescue-bootloader
```

**Release asset:** `dsh-rescue-bootloader-1.1.4.tgz`。