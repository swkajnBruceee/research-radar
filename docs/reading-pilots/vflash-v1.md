# VFlash v1 自动精读记录

执行时间：2026-11-07T20:21:15.290338+08:00

论文：VFlash: Fast, Accurate Visual Planning via Flash Primitive Decoding，arXiv:2611.08449v1。

本轮读取最新 agent-run、PRODUCT.md 和展示逻辑。队列共 545+ 待处理任务；按新协议先读取 shortlist 的全部 24 篇公开标题/摘要，选择同属最新 2026-11-06 候选的 VFlash。以其改动坐标生成/验证步骤和潜在推理成本影响作 level 2 初筛，引用摘要短词 `autoregressive`，仅调整公开处理优先级。随后默认 claim 自动领取本篇，没有直接覆盖领取顺序。

完整阅读 139/139 原文片段，覆盖正文、实验与附录 A–F；另读取固定版 PDF 算法 1 和评测协议。下载原 PDF 28 页、1,779,619 字节，SHA-256：`dc70ae56a2b9a2741aa7c415b0ef7c1f4a280b530cc357b8f84ed74dea2b3749`。目视核对物理页 4、6、7、8、10、21、25、26 的图 2/3/4、表 2–7/11/12、算法和计时说明。租约已续租，提交成功后清除本篇租约。

新增产物：

- `content/reading-pilots/vflash-v1.json`：14 条有来源判断、全文后 attention、技术增量卡片及 1 个未执行的实验草案。
- `content/reading-pilots/vflash-v1-evidence.json`：公开原文文档与片段，不含领取凭据。

技术判断：值得优先理解“schema 对齐的整基元预测，替代逐坐标 target-token 一致性验证”的训练/推理选择。同 target 联合 2D+3D AgiBot ADE 为 0.105→0.041m，Thor Molmo 推理阶段均值和为 3552.7→703.3ms。全文 attention 保留 priority，引用已核对方法和对照实验，以 training_change / compute_shift / controlled_comparison 为依据；是阅读顺序判断，不是科学质量定论。

重要边界：额外 537M drafter 需训练，视觉接受不保证维持 AR 分布。Dense200 直接接受 mean F1 从 60.10 掉到 39.09，置信回退到 61.78 仍损高 IoU 指标；密集运动多项指标退化，25 倍计时仅单 H100 rollout。Molmo 70.2% 比原生 62.6% 还换了 encoder；更接近的 AR 计划对照为 61.0%，但动作模型各自从同初始检查点重训，仿真推理暂停，不能归为实时闭环改善。LIBERO-PRO 总 +6.8 点中仅比 subtask 配置多 1.7 点，Plus 加轨迹无平均收益。计时预给工具 JSON，total 为共享部分阶段均值加解码均值，排除部分输入输出；驾驶质量五步 DDIM、计时十步，不混为同配置。所有结果未复现，未运行源码、复建模型或开展真机实验；其余图像未逐张目视核查。

提交后调用 `frontier.build(storage.all_items())`，本篇 `publication_ready=true`、文档 ID/来源匹配、覆盖 139/139、attention=priority/rank2 均断言通过，任务 `needs_review`。当前展示信号 12，队列 analyzing 为 0。研究判断仍需研究者核查，前台不要求先点人工确认。

仅处理公开材料、公开候选排序和本篇报告/证据/记录；未修改产品代码、个人笔记、阅读状态或选题，未调用另行付费 API、创建自动化或向他人发送消息。
