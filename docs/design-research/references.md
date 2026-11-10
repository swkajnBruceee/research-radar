# 交互参考与选型 · 2026-11-05

| 来源 | 本项目采用的思路 | 没有据此作出的承诺 |
| --- | --- | --- |
| [Folo](https://github.com/RSSNext/Folo) | 持续时间线、阅读队列、跨设备状态；桌面并列阅读、移动逐项深入 | 未接入 Folo 账号，未迁移用户订阅 |
| [Hugging Face Daily Papers](https://huggingface.co/papers) | 以日期和具体研究为入口，支持日/周式筛选 | 社区热度不作为质量分数，也未编造投票数据 |
| [Anthropic frontend-design SKILL.md](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | 先明确专家用户、真实任务和信息层级；真实研究增量占首屏，审查内容密度和移动展示 | 已读取并应用写作/层级原则；未宣称安装了全局 skill |
| [Impeccable](https://github.com/pbakaus/impeccable) | 参考其 critique、distill、adapt 的审查方向 | 仅读取文档，未执行安装程序、CLI、hooks 或 engine |

插件目录中找到 Product Design（可审查流程、从已有网址做原型）和 Figma（可编辑设计与交接）。用户随后安装了 Product Design；本轮已读取 audit skill 并按其要求进行新截图复核，记录见 docs/design-audit/2026-11-05/。

没有把大型阅读器框架引入当前 Python + 原生 SwiftUI 项目；本轮借鉴阅读组织方式，保留已有笔记、文献和同步代码。

## 首轮审查结论

默认首页不应出现 VLA 定义、动作扩散入门例子或“先看懂技术”的教学提示。应先展示具体的新训练配方、结构变化、评测反证和数据构造方法。每项增量把“对照是什么、改了什么、有什么证据”放在原文入口之前。

用户能快速处理并继续：已了解、稍后读、略过均可恢复；原文阅读状态单独记录。未解读的新资料依然进入更新流，但不伪装成已核实结论。对旧日期与新论文版本作边界检查。

## 证据来源

所有具体研究增量保留带版本的 arXiv 原文链接，位于 `content/frontier.json`。初始包括 RAFT、Asynchronous Robot Policies、LoopQ、DreamX、梯度路由消融、HiLo-WAM、RoboTryOn。当前依据原始摘要核对，不声称复现或完成全文实验审查。
