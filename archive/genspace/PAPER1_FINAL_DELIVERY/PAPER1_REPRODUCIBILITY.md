# 论文 1 复现与断点恢复

下列命令均从项目根目录使用 PowerShell。写入范围为本交付目录。Windows 上使用冻结研究运行时做只读检查，图表另用已安装的 Anaconda 解释器。依赖路径来自实际命令探针。 [启动检查](work/startup_audit.json)

```powershell
$py = 'C:/Users/16043/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$plot = 'D:/Anaconda3/python.exe'
$delivery = 'PAPER1_FINAL_DELIVERY'
& $py -B "$delivery/automation/AUTO_PAPER_72H.py" status
& $py -B "$delivery/automation/audit_startup.py"
& $plot -B "$delivery/work/build_evaluation_figures.py"
& $plot -B "$delivery/automation/make_csods_diagram.py"
```

图表复现环境为 CPython 3.13.9、Matplotlib 3.10.6 和 NumPy 2.3.5。冻结待审批方法的执行环境另为 CPython 3.12.14、NumPy 2.3.5，运行时、源码、资产及配置的逐文件摘要均在原正式冻结候选。图表脚本复用已封存的 4,800 个检查点和证明归档，直接重建图与数据表。 [数值附录](work/stats-appendix.md) · [冻结清单](../METHOD_FINAL_FREEZE_MANIFEST.json)

## 文稿与导出

正文工作版本依次保存在 work 下的初稿、三轮修订稿和最终源稿中。最后一份为带 Pandoc 引用与公式的可编辑源。转换采用 Pandoc 3.8 与 IEEE CSL，Word 格式保留原生 OMML 方程。PDF 使用本地 Chromium 与 MathML。图的位图版便于 Word 内嵌，另存矢量 PDF 供论文编辑。 [文献库](PAPER1_REFERENCES.bib)

```powershell
& $py -B "$delivery/automation/build_manuscript.py"
& $py -B "$delivery/automation/verify_delivery.py"
& $py -B "$delivery/automation/render_word_quality.py"
```

最终 Word 用经官方发布摘要核对、在本机独立解包的 LibreOffice 26.8.3.1 和文档渲染工具逐页检查。该检查使用独立临时 Writer 配置和进程局部路径。发行 PDF 由本地 Chromium 输出，Word 版的校对 PDF 保存于工作子目录。 [渲染器实测](work/renderer_probe/RESULT.md) · [机械核验](work/mechanical_qa.json)

## 中断、恢复及结束

状态文件按 Asia/Shanghai 保存启动和截止时点、任务、进程身份、源快照摘要、失败及输出路径。阶段检查点按工件 SHA-256 记录。恢复命令验证已有状态和可验证工件，在最终正文签入后可执行导出与机械核验。文稿工件漂移触发重新校验，源快照漂移触发停止并保留证据。 [持久状态](AUTO_72H_STATE.json)

```powershell
& $py -B "$delivery/automation/AUTO_PAPER_72H.py" resume
```

本地 Windows 续作进程已在后台启动，Job 子进程用于有界构建及检查。当前主机的 Codex CLI 版本为 0.169.0-alpha.11.1，登录状态有效，实际传输探针在用户级 default.rules 解析出 NUL 字节后退出。规则及权限保留原状，自动新作者会话处于不可用状态。恢复人工写作与评审时，在现有 Codex 工作区读取续作文档和待办后继续。待配置由其维护方审核修复后，可重新验证低权限 CLI 探针。后台进程在看到交接检查点或到达截止时退出。 [续作提示](work/continuation_prompt.md) · [当前待办](AUTO_72H_NEXT_ACTIONS.md)

独立确认由专门准备态入口、封存持出发布和单独授权管理。论文构建工具的恢复范围是文稿与开发证据。 [正式执行计划](../METHOD_FINAL_EXECUTION_PLAN.md) · [人工审批模板](../METHOD_CONFIRMATION_AUTHORIZATION_TEMPLATE.md)
