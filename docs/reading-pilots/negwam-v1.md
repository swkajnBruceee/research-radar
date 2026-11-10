# NegWAM v1 自动精读记录

执行日期：2026-11-08（Asia/Shanghai）；报告生成时间：2026-11-08T14:22:14.015121+08:00。

论文：[Reinforcing End-to-End Autonomous Driving Safety via Negative-Aware Planning in a Unified World-Action Model](https://arxiv.org/abs/2611.08111v1)。

本轮读取agent-run、PRODUCT.md和前台展示检查逻辑，阅读shortlist全部24篇候选标题/摘要；从最新日期组2026-11-06选择本篇，以近专家负轨迹可能改变WAM后训练监督为由记录level 2初筛，再默认claim自动领取，未指定覆盖队列排序。领取后续租，完整精读后原子提交；已确认提交清除本任务租约，不重复release已提交任务。

全文覆盖128/128固定HTML证据片段，含附录实现、额外结果、失败案例及监督范围。固定PDF14页、9,347,639字节，SHA-256为`103de0db9f371f9a2cdf66b244921e31a7ca40643afcbaa7782b76090bde652d`。目视物理页4、5、6、7、8、9、12、13、14，核算法1、注意力掩码与损失、表I–VIII、图3–11；额外读取PDF算法与参数文字，未冒称所有页目视。

新增公开产物：

- `content/reading-pilots/negwam-v1.json`：12条有出处判断、技术增量卡片、attention与1个未执行实验草案。
- `content/reading-pilots/negwam-v1-evidence.json`：公开原文文档，不含本机任务租约凭据。

可复用改动：GTRS16K词表取ADE[0.3,1.0)m且离线EPDMS=0的轨迹，每次最多16个，85.8%训练样本有负例。排斥损失使用[0.9a−d]+乘(1−t)，重用训练单步动作解码；rider用专家/负轨迹分组、单向读取当前观察及自身，原流不能看rider，也不允许未来目标进入rider keys。兼容性排序通过共享DiT权重回传，部署删除rider和标量头，仍保留原WAM生成路径。不是免评估器训练，负标签继承NAVSIM规则。

关键消融：同一100K预训练起点后10K后训练，继续FM38.2，锚点39.1，rider38.8，组合40.4，相对同预算继续训练+2.2分；未后训练37.7。BeyondDrive为完整方法移植到同WAM且用其原负例，不是纯loss替换对照。图4兼容性矩阵仅三个例子，不能替代泛化统计。

边界：navhard40.4对BeyondDrive38.8的4.1%是相对提升、仅作者比较的无scorer WAM范围；PDM-Closed56.6及带scorer DriveFuture55.5更高。navtest综合EPDMS92.2→93.3，但NC98.4→98.1、DAC96.7→98.4；不能宣称碰撞率下降或所有子项改善。统一使用修正NAVSIM v2.2，有跨阶段/专家同失败豁免等口径。

HUGSIM零样本总体RC43.6→45.1、HD27.2→30.6，Easy大涨；Medium/Hard/Extreme的RC和HD全部下降，Hard具体33.9→31.2与16.1→14.2，Extreme30.2→26.1与12.6→10.8。按表保留这些退化，不照正文“Hard几乎不变”概括。附录图11还展示本法错过超车而撞停驶前车、以及转弯间距不足碰撞的反例；没有真车或形式安全证明。

资源：4×H100预训练22h/88GPUh，后训练2h/8GPUh，未单列负缓存采矿成本。推理模型6241.81MB、峰值GPU内存14029.08MB相同，延迟871.35→877.86ms（+6.51ms/+0.75%），1.15→1.14FPS；无新增推理模块不等于实测严格零开销。视觉3/动作10是Euler积分步数，不当总骨干调用数。完整推理硬件、重复/热身与尾延迟口径不足。

验证缺口：NAVSIM无独立validation split，作者在navhard做checkpoint/单变量敏感性比较，透明但非独立留出选模证据。曲线仅NegWAM三seed±1std，baseline单run；主表消融未给同等误差区间。navhard5K时NegWAM均值低于baseline，10K最高后回落；不写成训练越久越好。有限词表、统一零分标签及ADE几何代理不能覆盖所有危险时序。未运行作者代码、独立复现实验或审计缓存/评测/计时原始日志。

全文后attention为notable，依据training_change / controlled_comparison / negative_result，关联已核方法/实验。待验证草案匹配ADE、负例数、覆盖和训练预算，比较均匀池与违规/交互多标签分层采样，并在内部开发集冻结后报告所有难度与子项；仅写入报告，未执行或创建选题。

提交后调用`frontier.build(storage.all_items())`，本篇`publication_ready=true`、文档ID/来源匹配、覆盖128/128、attention=notable均断言通过。任务`needs_review`，lease_until=0且令牌已清除；检查时前台18篇可展示，analyzing=0。无需用户先人工确认，保留模型解读、引文匹配通过、作者实验未复现状态。

未修改产品代码、个人笔记、论文阅读状态或选题；未调用另行付费API、创建其他自动化或向他人发送消息。
