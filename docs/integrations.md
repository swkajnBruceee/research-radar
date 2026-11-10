# 研究工具联动设计

2026-11-05。面向科研选题与方法理解，每天约 30 分钟。

## 产品分工

研究台负责发现、去重、筛选、方法导航和问题记录。Zotero 承担论文、PDF 批注与引用；Notion 可承接研究项目和选题；Obsidian 是偏好本地 Markdown 时的替代选择。无需同时使用全部工具。

## 已交付的文件交换

- Zotero：精读页导出单篇 RIS；产品联动页导出所选论文集。保留原始标题、作者（来源完整时）、arXiv DOI、日期、主题和 PDF 链接。不把基础导读冒充论文摘要，不把 et al. 当成完整作者列表。RIS 不包含个人笔记。PDF 附件与不完整元数据需在 Zotero 核查。
- Notion：导出包含文献 CSV、选题 CSV 与 Markdown 正文的 ZIP。使用电脑端或网页端导入；CSV 数据库与 Markdown 页面不会自动建立关联。重复导入会新增记录，并非更新已有页面。
- Obsidian：导出可打开为仓库的 Markdown 文件夹，包含 Home、文献、八个主题和选题，通过相对链接关联。解压到新目录，避免覆盖在外部编辑过的笔记。
- 范围默认只包含收藏、有笔记或已开始阅读的内容；也可选择全部。Notion、Obsidian 包另附全部选题。笔记包包含个人内容，下载后由用户选择导入位置。

以上均为一次性快照。没有向外部账号写入内容，没有双向或自动同步。对话中的 Notion 连接与本地网页的运行时连接是两件事；当前网页未绑定 Notion 数据库。

## 后续设计顺序

1. Zotero：通过已授权的本地或云端接口读取文献与带页码的批注，以 arXiv ID / DOI 匹配研究台；保留批注来源，先预览再合并，不直接修改 Zotero 内部数据库。
2. Notion：在选定目标库后同步精读和选题。以稳定 ID 记录远端页面 ID、内容摘要、上次同步时间和错误。分别管理系统字段与人工笔记，重复操作不新增副本；双方同时修改时提示冲突。
3. Semantic Scholar：补充参考文献、引用与推荐论文。先评估新论文覆盖、匹配准确率和调用限制。引用不等于方法继承，仍需正文证据。
4. Readwise Reader：当手机阅读文章、访谈和博客成为高频行为时，再接入阅读高亮。其官方笔记导出为追加机制，不应视为任意修改都能双向同步。

## 官方依据

- Zotero 标准格式导入：https://www.zotero.org/support/kb/importing_standardized_formats
- Zotero PDF 与批注：https://www.zotero.org/support/pdf_reader
- Notion 导入范围：https://www.notion.com/help/import-data-into-notion
- Notion 数据源结构：https://developers.notion.com/guides/data-apis/working-with-databases
- Obsidian 文件夹仓库：https://help.obsidian.md/Files+and+folders/Manage+vaults
- Readwise 到 Notion 的追加导出：https://docs.readwise.io/highlights/docs/exporting-highlights/notion
- Semantic Scholar API：https://webflow.semanticscholar.org/product/api/tutorial

## 2026-11-05：在线同步与批注回流

已建立私有 Notion 资料库，保存于 data/notion-target.json；本次通过对话连接同步了在读的 PolicyIK。同步映射、源内容哈希、远端受管字段哈希、执行记录保存于 SQLite。个人补充字段和页面正文不属于覆盖范围。

网页“产品联动”新增：

- Zotero 批注检查与预览，选择后导入；精读页显示独立批注区，保留页码、摘录、评论和回跳链接。使用固定的 127.0.0.1:23119 官方本地 API，不转发 Zotero 端口，不写 Zotero 数据。仅匹配现有论文的 arXiv 标识。重复导入按实例/文库标识与批注 key 去重。来源更新只更新独立批注记录，个人笔记不变。上游删除不自动删除本地记录。
- Notion 资料库入口、已同步/待同步数量、执行日志。无服务器凭证时，网页按钮禁用；通过对话执行的同步会如实记录。
- 后台一键同步客户端：仅发送精选论文和选题，以稳定 ID 查询后创建，重试先查是否已存在。已同步条目更新前核对远端受管字段，发生人工修改则报告冲突，不静默覆盖。新遇到的同 ID 页面若内容不同，也保留并报告冲突。

### 使用前提

Zotero 需运行，且在“设置 → 高级”启用“允许此计算机上的其他应用程序与 Zotero 通讯”。此开关允许本机应用读取文献库，研究台仅发出读取请求。功能不需要 Zotero 写权限。

Notion 对话连接不会把账号凭证交给本地网页。若要从网页直接发起同步，需要自行在 Notion 建立 integration，将其授权到上述资料库，并在启动服务的环境中设置 NOTION_API_KEY。凭证只在服务器读取，不进入状态接口、导出包或前端。不要通过校园网网页表单或聊天粘贴凭证。当前为明确点击触发的一次同步，尚未启用定时自动推送。

API 路径：GET /api/integrations/status；POST /api/integrations/zotero/preview；POST /api/integrations/zotero/import（ids 列表）；POST /api/integrations/notion/sync。均受研究台原有访问控制保护。

验证覆盖：Notion 属性转换、重复同步、未知远端记录恢复、人工修改冲突；Zotero 匹配、页码、重复导入、笔记保留。接口关闭或未配置时显示原因，不标记同步成功。原生账号首次写入与 REST 持续同步分别记录验证程度。

真实连接验证：经用户确认，已在 Zotero 界面开启本机读取接口。当前文库与研究台没有 arXiv 标识重叠，预览返回 0 篇匹配、0 条批注，因此未向个人笔记添加任何导入内容。Notion 首次同步已回读核实。
