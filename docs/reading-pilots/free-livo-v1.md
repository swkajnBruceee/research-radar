# FREE-LIVO v1 自动精读记录

执行日期：2026-11-08（Asia/Shanghai）；报告生成时间：2026-11-08T08:21:33.204154+08:00。

论文：[FREE-LIVO: Physically Decoupled Yet Tightly Coupled LiDAR-Inertial-Visual Odometry](https://arxiv.org/abs/2611.07463v1)。

本轮读取agent-run、PRODUCT.md和前台展示检查逻辑，阅读shortlist全部24篇标题与摘要，从最新日期组2026-11-06选择本篇；以跨模态重投影可能解除共刚体与同步约束为由记录level 2初筛，随后默认claim自动领取，没有指定覆盖队列排序。领取后续租，完整精读后原子提交；已确认提交清除本任务租约，不对已提交任务重复release。

完整阅读62/62固定HTML证据片段，包括方法、全部实验、实现参数与结论；该版本无附录。固定PDF8页、18,394,345字节，SHA-256：`4092c997b0d3a564b36e6f49a67bfbbb12507d0d5fcef850d4e2258b0a4d0cfc`。目视物理页3、4、5、6、7，核对公式1–4、图2–9和表I/II，复算六序列均值，保留延迟表按序列组配对平均的口径。

新增公开产物：

- `content/reading-pilots/free-livo-v1.json`：10条有出处判断、技术增量卡片、attention与1个未执行实验草案。
- `content/reading-pilots/free-livo-v1-evidence.json`：公开原文证据文档，不含本机租约凭据。

技术增量：单帧LiDAR强度图经CRF补全后，用SuperPoint/LightGlue MINIMA匹配RGB；几何仍取实际LiDAR深度，只接受5像素内有深度的匹配。3D点到像素因子直接连接不同时间的两端位姿，不设固定LiDAR–camera外参或常量偏移状态。联合VGICP、视觉smart factor、双惯性链、Huber/DCS，在5秒固定滞后图用iSAM2优化。仍需已知相机内参、IMU链和足够关联，不等于无任何标定/同步条件。

证据：M3DGR六段平移ATE经SE(3)对齐，完整0.45m、GLIM约0.71m；并非逐段第一。松耦合平均2.10m、最近邻补全0.52m，支持紧耦合设计的差异大于生成补全在该集的0.07m平均改善；Dynamic02松耦合0.41m还好于完整0.56m，Dynamic04最近邻0.29m也好于CRF0.32m。不能把全部收益归给生成模型。CRF借助240万RGB图像预训练和80个内部LiDAR点云微调，不是无训练。

摘要边界：0→0.5秒延迟下，室内Dynamic01+02组ATE0.77→1.83m，不能写成所有场景轻微下降；两个室外组约0.29→0.29/0.31m。R3LIVE/FAST-LIVO2的ATE不呈单调退化，强LIO可能遮蔽视觉融合错位；图7着色为定性补充，不能代替双轨迹真值。FAST-LIVO2失败原因是作者可能解释，未独立验证标定/同步因果。

独立双手和轮式/足式机器人演示无真值，仅展示联合轨迹与着色点云；0.45m属于M3DGR，不贴到真正独立移动演示。作者在7940HS/RTX4080/32GB笔记本、TensorRT FP16下声明实时，没有FPS、分项/尾延迟、功耗或低算力对照。缺初始化、帧对搜索/重连、长期低共视、时钟漂移和随机抖动的充分定量验证；多会话和多机器人SLAM是未来工作。作者实验未复现，未运行代码、审计内部训练数据或实机日志。

全文后attention为notable（值得跟进），依据capability_change / controlled_comparison / real_robot，关联已核方法与实验。实验草案仅写报告，固定紧耦合与匹配器，比较CRF/最近邻/不补全，按共视和时间间隔分层，在公开含真值回放上同时测内点率、两轨迹误差与推理成本；明确刚性rig回放不能冒充独立运动真值实验。未执行或创建用户选题。

提交后调用`frontier.build(storage.all_items())`，本版本`publication_ready=true`、文档ID/来源匹配、覆盖62/62、attention=notable均断言通过。任务`needs_review`，lease_until=0且令牌已清除。检查时前台16篇可展示，analyzing=0。无需人工先点确认，保留模型解读、引文匹配通过、作者实验未复现状态。

未修改产品代码、个人笔记、论文已读状态或选题；未调用另行付费API、创建其他自动化或向他人发送消息。
