# RAFT v1：代理精读试跑

值得关注的是“推理适配 → 冻结适配器 → 动作微调”这一训练配方。正文消融支持它优于所测联合训练和可训练适配器；收益依任务和扰动差别很大。优先理解训练顺序和控制实验，再决定是否复现。

- 状态：待核查研究草稿；作者实验，未复现。
- 论文：[arXiv:2611.04368v1](https://arxiv.org/abs/2611.04368v1)，2026-11-03。
- 试跑日期：2026-11-05；未调用额外模型API，未创建定时任务。
- 阅读范围：已阅读提取出的91个文字片段（主文与附录），并目视核对PDF第6、7、10、15、19、20、21页关键图表；未逐一检查所有图片、公式、引用文献或执行代码。逐字引文匹配只验证出处，不证明语义判断正确；实验数值来自作者，未复现。
- 原文HTML SHA-256：`401105ec546c7a870f50ddce8b7bfb49586da605690324c502c49b2e3e136175`。
- PDF SHA-256：`1563bba4c84f32f3ee8184cc17f6fb45fcaa587697b16102849b29af63c1f96b`。
- 署名：Shresth Grover、Andrey Kolobov、Dhruv Shah；原文标示CC BY 4.0。本报告为中文解读，非作者原文。

## 关键判断与证据

### 关键增量：冻结推理适配器，再学习动作

RAFT 的增量是后训练的参数与顺序安排。先用任务相关推理训练视觉和语言 LoRA；动作训练阶段冻结它们，更新语言模型、动作专家与投影层。它不要求推理时先生成文字链再动作。作者的消融支持这一配方，但不能据此证明冻结对所有 VLA 都有效。

依据：[1 Introduction · f4354d417c517253](https://arxiv.org/html/2611.04368v1#S1.p2.1)；[3.1 Overview and Problem Setup · a939bc18dbcad3d4](https://arxiv.org/html/2611.04368v1#S3.SS1.p1.1)；[3.3 Stage II: Action Adaptation · f5b0aa0e8094647c](https://arxiv.org/html/2611.04368v1#S3.SS3.p1.2)

### 两阶段具体更新哪些参数？

第一阶段只更新 LoRA，预训练 SigLIP 与其余主干冻结；第二阶段 LoRA 与 SigLIP 仍冻结，语言主干、动作专家、投影层参与动作微调。仿真/DROID 配置的 LoRA rank=64、alpha=128，覆盖视觉和语言模块。YAM 使用 π0.5，不直接套用 MolmoBot 的全部配置。

依据：[3.1 Overview and Problem Setup · a939bc18dbcad3d4](https://arxiv.org/html/2611.04368v1#S3.SS1.p1.1)；[3.3 Stage II: Action Adaptation · f5b0aa0e8094647c](https://arxiv.org/html/2611.04368v1#S3.SS3.p1.2)；[6 Training and implementation details · 7563e80a4753adb8](https://arxiv.org/html/2611.04368v1#S6.p1.1)；[6 Training and implementation details · bf798dbc199b9625](https://arxiv.org/html/2611.04368v1#S6.T1.7)

### 新增数据：推理标注也有成本

作者用 Gemini 3.1 Pro 为观测和指令生成框、关键点、轨迹、空间描述或 VQA 标注。主实验抓放用 full reasoning，开抽屉用 bbox；同一任务内部固定模态。相同动作示范数不代表没有额外数据加工、模型标注和计算成本。

依据：[3.2 Stage I: Reasoning Alignment · e24e079d0e0f9fe1](https://arxiv.org/html/2611.04368v1#S3.SS2.p1.1)；[6.1 Annotation format · 8c04320d06002855](https://arxiv.org/html/2611.04368v1#S6.SS1.p1.1)；[Setup. · 35b310ba1931f337](https://arxiv.org/html/2611.04368v1#S8.SS1.SSS0.Px1.p1.1)

### DROID：75.0% 来自三类 OOD 的合并结果

MolmoBot 用50条抓放示范适配。作者报告 RAFT/Plain FT 的 OOD 成功率75.0%/27.9%：换物体颜色83%/33%（24次）、干扰物75%/25%（24次）、背景65%/25%（20次），共68次 OOD 试验。ID另有30次，约63%/60%。75%不等于图6含ID的 Mean，后者约71%。

依据：[Real-world: DROID · a1b88d3184fa0787](https://arxiv.org/html/2611.04368v1#S4.SS2.SSS0.Px3.p1.1)；[6.4 Evaluation protocol · 151431e02d09b411](https://arxiv.org/html/2611.04368v1#S6.SS4.p1.1)；[Real-world: DROID · 615770bc6459a3e9](https://arxiv.org/html/2611.04368v1#S4.F6)

### YAM：70% 是完整任务，且包括 ID

π0.5 用100条示范学习开箱、取物并放入箱内。70.0%是五个轴的整段任务合并成功率；DeLock36%、Plain FT约35%、RETAIN29%。它既不是仅开箱成功率，也不是仅OOD。附录明确每个OOD轴30次，但没有同样明确写出YAM的ID次数，因此本试跑不补写总样本数。

依据：[Real-world: YAM · 242f51b85cd1814d](https://arxiv.org/html/2611.04368v1#S4.SS2.SSS0.Px4.p1.1)；[6.4 Evaluation protocol · 151431e02d09b411](https://arxiv.org/html/2611.04368v1#S6.SS4.p1.1)

### 仿真：83.21% 对79.62%，需看分轴

MolmoBot/MolmoSpaces 每任务106条单布局成功示范；抓放五个评测划分各106次，方法间使用匹配初始条件。表4均值83.21%/79.62%，差约3.59个百分点；纹理与指令轴与普通微调打平。真机的大幅提升不能替代仿真结论，本报告也不据此断言跨训练随机种子的显著性。

依据：[Simulation · 4588b7807c9570f6](https://arxiv.org/html/2611.04368v1#S4.SS2.SSS0.Px1.p1.1)；[Setup. · e5c1e4ab3b1db09e](https://arxiv.org/html/2611.04368v1#S8.T4.6)

### 核心消融：冻结、继续更新与联合训练

仿真抓放中冻结适配器83.21%，动作阶段继续更新73.96%，仅推理阶段48.30%；推理与动作1:1联合训练63.21%，普通微调79.62%。这支持分阶段与冻结的重要性，但这一联合配方的失败不等于所有联合训练无效。

依据：[Setup. · 741cb2d5f30f3a42](https://arxiv.org/html/2611.04368v1#S8.T3.7)；[Setup. · 4dd11098c2bdf409](https://arxiv.org/html/2611.04368v1#S8.SS3.SSS0.Px1.p1.1)；[Setup. · e5c1e4ab3b1db09e](https://arxiv.org/html/2611.04368v1#S8.T4.6)

### 更强控制：冻结视觉已缩小部分差距

冻结视觉的Plain FT平均79.62%，但新物体成功率从35.85%升至40.57%；RAFT为43.40%，相对这个控制只高2.83个百分点。应同时看这个控制，避免把所有收益归因于推理内容。

依据：[Setup. · e5c1e4ab3b1db09e](https://arxiv.org/html/2611.04368v1#S8.T4.6)；[Results. · 774c12679077d1d5](https://arxiv.org/html/2611.04368v1#S8.SS3.SSS0.Px2.p1.1)

### 复现条件：额外1,000步训练与外部标注

表1的仿真/DROID配置：推理阶段1,000步、有效batch48、单张46GB L40；动作阶段5,000步、有效batch512、四张46GB L40。基线统一动作训练5,000步，但总训练预算并不完全相等。已读文字未提供足够的标注美元成本、端到端工时和所有训练重复信息，暂不估算费用。

依据：[Baselines · 7d9786fe12c942fa](https://arxiv.org/html/2611.04368v1#S4.SS1.SSS0.Px1.p1.1)；[6 Training and implementation details · bf798dbc199b9625](https://arxiv.org/html/2611.04368v1#S6.T1.7)；[3.2 Stage I: Reasoning Alignment · e24e079d0e0f9fe1](https://arxiv.org/html/2611.04368v1#S3.SS2.p1.1)

### 推理模态没有通吃的赢家

抓放新物体成功率：轨迹45.28%，VQA/full reasoning各43.40%，bbox/keypoint各34.91%，普通微调35.85%；开抽屉不同模态在ID和视觉扰动上各有优势。监督内容本身需要验证，不能认为任意推理标注都能改善结果。

依据：[Setup. · 35b310ba1931f337](https://arxiv.org/html/2611.04368v1#S8.SS1.SSS0.Px1.p1.1)；[Results. · f454f270f593cd38](https://arxiv.org/html/2611.04368v1#S8.SS1.SSS0.Px2.p1.1)

### 表示分析提供相关证据，尚非因果证明

线性探针414帧来自46个策略训练episode；按episode留出探针拟合，不代表这些轨迹未进入策略训练。所谓任务进度标签是时间四分位，并非人工标定的实际子任务完成度。注意力集中与PR相关性支持表示变化，不单凭这些测量证明因果或通用推理能力。

依据：[Real-world: YAM · 7b4ba4f8907f189c](https://arxiv.org/html/2611.04368v1#S4.F9)；[Model and captured frames. · dc33cb68e2bca442](https://arxiv.org/html/2611.04368v1#S10.SS0.SSS0.Px1.p1.1)；[Linear probes. · bc2909dc9a6d9674](https://arxiv.org/html/2611.04368v1#S10.SS0.SSS0.Px3.p1.1)；[Visual attention and region masks. · be03f9086948e567](https://arxiv.org/html/2611.04368v1#S10.SS0.SSS0.Px4.p1.1)；[Late-layer dimensionality correlates with downstream success · f93622eb6aab5813](https://arxiv.org/html/2611.04368v1#S4.SS3.SSS0.Px1.p1.2)

### 口径核查：39%和38.05%不是同一均值

图5开抽屉39%覆盖ID、灯光、纹理和指令；表5独立RAFT的38.05%只覆盖ID、灯光、纹理三轴，不能强行统一。表5组合RAFT为36.16%，低于独立RAFT的38.05%，所以可与RETAIN组合不等于组合更好。论文代码链接本次访问返回404，未核查实现或复现。

依据：[Setup. · 22a0470f2e71c483](https://arxiv.org/html/2611.04368v1#S8.T5.7)；[Results. · 5d196da1664cf491](https://arxiv.org/html/2611.04368v1#S8.SS4.SSS0.Px2.p1.1)；[Baselines · 8f79ccea6d5da580](https://arxiv.org/html/2611.04368v1#S4.F5)；[Setup. · a2ad0a3a4eb3c7b0](https://arxiv.org/html/2611.04368v1#S8.SS4.SSS0.Px1.p1.1)

### 最小实验：收益对标注噪声有多敏感？

待验证假设：冻结适配器保留的既可能是任务信号，也可能是错误标注。先只做一个仿真抓放任务，固定动作示范、初始化、数据顺序、动作训练步数与评测episode。四组为冻结视觉Plain FT、标准RAFT、10%记录加入可控对象/坐标错误的RAFT、30%同类错误的RAFT。RAFT各组固定推理训练量，单独记录额外GPU时与标注量。先小规模检查，再以至少3个训练种子评测ID/新物体/纹理成功率及配对差异区间；另加总GPU时匹配的动作训练控制。若噪声不影响结果，或预算匹配控制达到相同收益，就反对“精确任务推理信号是主要来源”的解释；只在单一扰动退化则缩小假设。实验尚未运行，也未全面排查相关工作，不能称为已发现研究空白。

依据：[3.2 Stage I: Reasoning Alignment · e24e079d0e0f9fe1](https://arxiv.org/html/2611.04368v1#S3.SS2.p1.1)；[4.5 Effect of unfrozen adapter · e51dfdb523a93f6c](https://arxiv.org/html/2611.04368v1#S4.SS5.p1.1)；[Results. · f454f270f593cd38](https://arxiv.org/html/2611.04368v1#S8.SS1.SSS0.Px2.p1.1)；[Setup. · 741cb2d5f30f3a42](https://arxiv.org/html/2611.04368v1#S8.T3.7)；[Setup. · e5c1e4ab3b1db09e](https://arxiv.org/html/2611.04368v1#S8.T4.6)

## 自动化试跑结论

已跑通：固定版本原文 → 章节提取 → 代理解读 → 关键图表目视核对 → 引文校验 → 待核查报告。结构化报告在 `content/reading-pilots/raft-v1.json`。导入命令：`python3 scripts/import_reading_pilot.py content/reading-pilots/raft-v1.json`。导入要求缓存中的原文内容哈希及版本一致，拒绝伪造引文、未读片段及覆盖其他解读。

本次没有创建独立精读队列、自动筛选规则或定时执行器；这些仍是后续工作。个人阅读状态、笔记和选题池未自动改写。
