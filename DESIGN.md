# 前沿动态设计

## 依据与取舍

- Anthropic frontend-design：以产品实际内容建立层级；用真实研究增量作为首屏主角。已读取官方 SKILL.md 并应用。
  https://github.com/anthropics/skills/tree/main/skills/frontend-design
- Folo：订阅时间线、阅读状态与稍后消费的思路。
  https://github.com/RSSNext/Folo
- Hugging Face Daily Papers：按日与周筛选具体论文，并保留研究来源。社区热度不被当作研究质量分数。
  https://huggingface.co/papers
- Impeccable：参考其 critique、distill、adapt 的审查方向；未安装或执行 CLI、hooks 或 engine。
  https://github.com/pbakaus/impeccable
- Product Design 已安装；本轮按 audit skill 做截图复核，记录见 docs/design-audit/2026-11-05/。

## 视觉与版式

色彩：纸面 #FAFAF8，墨色 #222326，结构线 #DFDFDB，证据与选中状态 #215B50。正文使用系统字体与连续阅读版式，强调方法、对照和边界。

字型：中文用系统无衬线（PingFang SC）以适应长技术标题，拉丁使用系统 UI 字体；标题 24/20，增量正文 16，证据说明 13，日期 12。无装饰性英文口号、虚构影响分或巨型概念卡。

桌面：左侧四项主导航，右侧830px宽连续手记。文章之前可切换论文，标题下直接解释增量与一项关键证据；更多实验和机制按需展开。

手机网页：同一手记纵向阅读，底部四项导航；iOS以原生列表进入详情。回看包含近期、稍后读、已了解、已略过。主要操作触点至少44px。已有实验显示继续编辑入口，编辑器标题栏保留保存。

## 审查

必须能在首屏回答“这几天有什么新变化”。默认不出现“VLA 是什么”与入门例子。日期、核对层级、当前证据与研究者判断清楚分开。新版本出现后旧版解读失效，资料仍能进入全部更新。无新进展时提供改变日期范围的操作。

本轮阅读动线改为前沿手记、论文、选题、更多四项导航。正文用连续阅读和渐进展开组织，优先呈现解释方法选择的消融以及适用边界。可编辑实验草稿带入原文证据与模型建议，保存后进入选题。手机采用底部导航，桌面采用侧栏。最新复核见docs/design-audit/reading-flow/report.md。

网页同篇地址与原文返回保留视图、展开状态及会话阅读位置；位置按论文版本区分。正式页面和隔离保存验证见docs/design-audit/revisit-flow/report.md。
