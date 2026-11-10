# 重点发现、精读与手机更新验收

实施：2026-11-09至2026-11-10（Asia/Shanghai）。本轮是产品优化和既有精读的比较校准，不宣称重新独立复现论文。

## 已完成

1. **首屏先展示重要变化。** 网页和iOS默认进入“重点”，最多三个、跨研究决策方向且同一研究不重复占位。标题先讲方法变化，详情按需查看改动、作者实验、局限及原文。已了解/略过不继续占据重点。支持返回原浏览视图、版本绑定的阅读位置；不自动改变个人论文阅读状态。
2. **比较影响范围与证据。** route/method/task/tool与controlled/limited/insufficient共同决定展示顺序，日期只处理同级顺序。35份既有完整精读经过编辑比较，校准绑定原始文档版本，未覆盖原报告、个人笔记或选题。最高级不再被单项工具结果大量占用。当前重点为La-JEPA、RoboTryOn、SuperMimic；这不是统一科学质量排行榜。
3. **重要候选可以先读。** 已有完整初筛、逐字证据和影响范围的level2候选可通过优先通道领取，不等待无关批次完成。普通批次不被消费或跳过；最长等待也参与排序。新增plan不领取租约。新领取报告必须包含impact和adoption；旧活动租约兼容。失败继续走续租、释放与版本检查。
4. **具体使用条件与方法对照。** 已确认条件附原文位置，未知条件明确标注；提供固定基线、改动模块、指标和推翻条件的最小实验建议。重点三项补充了来源验证的条件。其他旧报告若尚未整理条件会如实提示。资源链接未运行，不宣称可直接复现。iOS对照选择列表移入独立面板，已选方法和比较结果先出现。
5. **官方发布也能完整处理。** 配置内的GitHub发布、固定SHA模型/数据集README、PI官方技术文章进入同一候选与完整正文发布门槛。未下载权重或运行仓库代码。明确论文出处才可归为同一研究。版本哈希区分发布正文改动与下载计数；相同README在不同提交保留独立文档。arXiv扩展相关类别并持续回扫，游标仅在本批全部入库后提交。
6. **手机按篇更新并确认保存。** 先比较清单，只下载变化项；逐项检查版本、文档ID、来源和完整覆盖，全部保存成功后才更新清单并发送回执。全局版本中途改变返回412并重试，旧服务器支持完整包回退。回执是客户端报告已保存，不等于用户阅读，也不能证明是物理手机。离线包明确标识；无连接的软件升级仅刷新公开快照，并保留个人记录和同版本处理状态。

## 实际验收

- 网页：从首页点击SuperMimic → 展开“怎样用于我的研究” → “定位这项条件” → 对应原文片段自动展开 → 返回重点浏览。没有写入个人稍后读、阅读状态、笔记和选题。
- [改版前首页](01-before-home.png)：先展开一篇详情，首屏难以比较重要内容。
- [移动宽度首页](03-web-overview.png)：三个重点标题均可见，SuperMimic不再埋在长列表中。
- [当前桌面首页](05-web-overview-current.png)：三个研究变化并列，可继续浏览全部34项。
- [原文条件定位](04-web-source-condition.png)：当前版本全文、报告与所引用片段一起呈现，避免误导为必须人工点确认才可展示。
- [iPhone模拟器首页](iphone-overview.png)：原生1.0（5）、离线快照34项，三个重点标题在首屏可见。仅检查此原生初始页面；未冒充完整真机点击、VoiceOver或全部动态字体验收。
- Python **105通过**、JavaScript **30通过**、Swift核心 **13通过**。覆盖版本变化、逐字引文、优先通道资格、校准不改原报告、个人记录保留、增量包与回执、同研究去重、旧服务器兼容。
- 模拟器Debug与iPhone Release（未签名）均BUILD SUCCEEDED。物理手机当时不可用，没有安装到用户手机；现有手机软件不会因服务更新自动获得新的原生布局。
- 六个自动来源最近一次实际采集均ok：arXiv301、LeRobot发布5、IsaacLab发布5、模型10、数据集10、PI文章12。见[source-sync.json](source-sync.json)。另有完整数据集卡10/10、PI全文12/12直接采集记录。
- 公网认证、公开内容清单一致性、按篇下载与过期版本412均通过，详见[deployment.json](deployment.json)。实际手机保存回执**未验证**，没有伪造真机回执。
- 同一自动任务已恢复ACTIVE，保留每3小时一次与专用会话，提示更新为每轮最多两项/40分钟并遵守新协议，没有创建第二个任务。Mac与Codex需保持运行。

## 当前边界与后续检验

当前通过展示检查34项。离线包也重新导出为34项。两篇既有精读（2611.09892、2611.09684）因未固定版本的来源元数据变动，暂不能证明与当前版本一致，正确留在后台，原报告未删除。未猜测版本或绕过检查。

候选仍有积压：验收时未初筛1867项、已有合格优先候选2项。优先通道改善调度，不代表已达成重要事件几小时内必达的覆盖率承诺；需要继续观察实际筛选吞吐、漏收样本与发布时间。任何来源抓取成功都不代表所有重要研究已被发现。

公网仍使用临时Cloudflare通道，Mac需在线，重建会改变地址。固定域名、脱离Mac的全天托管、物理手机安装/真实收件、运行代码复现及更全面无障碍检查均未完成。用户没有既有域名或托管账号，本轮没有购买服务、注册账号或接受新条款。

## 主要实现位置

app/attention.py、app/reading_queue.py、app/research_tools.py、app/research_material.py、app/collectors.py、app/public_content.py、app/content_delivery.py、app/server.py；public/frontier.js、frontier.css、reading.js；iOS Models、RadarStore、FrontierViews及DeepReadingView。执行协议见[agent-run.md](../../../reading-queue/agent-run.md)。

官方参考：[Cloudflare临时通道](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)、[arXiv API](https://info.arxiv.org/help/api/user-manual.html)、[GitHub Releases API](https://docs.github.com/en/rest/releases/releases)、[Hugging Face模型卡](https://huggingface.co/docs/hub/model-cards)、[Codex本地自动任务](https://learn.chatgpt.com/docs/automations?surface=app)。
