# RL 边界静默故障 v1 自动精读记录

执行时间：2026-11-07T23:19:11.648016+08:00

论文：Detecting Silent Faults at the Environment–Trainer Boundary in Reinforcement Learning，arXiv:2611.08144v1。

读取当前 agent-run、PRODUCT.md 和前台检查逻辑，阅读 shortlist 全部 24 篇标题/摘要。选择最新日期组 2026-11-06 的本篇，以受控故障注入可能改变分布式 RL 正确性验证方式为由作 level 2 初筛，引用公开候选标题短词；随后默认 claim 自动领取，未直接指定覆盖排序。

完整阅读 65/65 提取片段，包含正文、实验、限制与附录 A–G。固定版本 PDF 共 7 页、505,946 字节，SHA-256：`3a3a12783d62895130804675e4fa78587629e3eb6fc62c24a49f7223b2267af0`。目视检查物理页 1、2、3、4、6、7，核对图 1–6 与表 I–VI，尤其是账本分母、按剂量的检出差异、Hopper 未读字段、通信与训练时间的不同口径。领取后续租，再原子提交。

新增产物：

- `content/reading-pilots/silent-boundary-faults-v1.json`：12 条有依据判断、全文重要性判断、技术增量卡片与 1 个未执行实验草案。
- `content/reading-pilots/silent-boundary-faults-v1-evidence.json`：公开原文文档与证据，不含本机租约凭据。

核心：双侧逐step账本核环境实际经历与trainer所见；env侧episode记录补日志层盲区。过学习曲线检查的728次边界故障中，723个策略在干净评测中没有低于参考均值3std，但这不是等价检验。账本在Pendulum/Hopper/Pusher的189+207+189=585次所测注入中全部定位，HalfCheetah未测账本，不扩大为四环境全部900次验证。Hopper12次故障没改权重，因为SB3没读被改final observation，说明权重一致也非全部字段正确的证明。

边界：3%仅Pendulum有无账本的训练时间增量中位数，不是bridge总开销；实现为结束后对账，Hopper约150MB/run，在线digest未来工作。图6 step:fill低剂量episode record有检出、all剂量未检出，报告按图保留剂量差异。输入限状态、稠密奖励sim和SB3 PPO三seed，info未注入，未验证replay/image/sparse/long-horizon或持续运动真机；两个wrapper内共同错误也看不到。历史Gymnasium问题按原文版本记录，1.4已修复，未把其他外部issue视为本轮复核。pi0.5只做单步学习和随机权重前向计时，不当RL能力证据。未运行作者代码或审计公开原始日志/注册协议，作者实验未复现。

全文后attention维持priority，依据 controlled_comparison / negative_result / reusable_resource，关联已核方法与实验；是阅读优先级判断，不是普遍故障检测保证。实验草案仅写入报告，未执行或创建用户选题。

提交后调用 `frontier.build(storage.all_items())`，本篇 `publication_ready=true`、文档/来源匹配、覆盖65/65、attention=priority/rank2均断言通过；任务needs_review，自己的租约已清除。当前13篇可展示，analyzing为0。前台展示检查通过，保留模型解读/未复现状态，无需人工先点确认。

未修改产品代码、个人笔记、论文阅读状态或选题，未调用另行付费API、创建其他自动化或向他人发送消息。
