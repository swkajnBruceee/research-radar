# 具身研究台 · iPhone / iPad 客户端

这是独立的 SwiftUI App 工程，最低 iOS 17，无第三方依赖。App 自带页面和基础阅读数据，不需要先打开网页。现有 Python 服务继续提供最新资料和跨设备同步。

## 回来后安装到 iPhone

1. 用 Xcode 打开 ResearchRadar.xcodeproj。
2. 用数据线连接 iPhone，按设备提示信任电脑；在 Xcode 顶部选择这台手机。
3. 在 ResearchRadar target → Signing & Capabilities 中选择你的 Personal Team 或开发者团队。默认 Bundle ID 为 com.bruce.EmbodiedResearchRadar；如签名提示冲突，可以改为你自己的唯一 ID。
4. 如果设备提示开发者模式或签名信任，按 iPhone / Xcode 的提示完成。Apple 账号登录、协议和签名由你本人处理。
5. 按 Run 安装。免费 Personal Team 的签名有效期有限，过期后需要重新构建安装。
6. 首次打开直接显示具体研究增量的公开快照，无需先连接或填写配置。需要更新资料时，在连接设置查找同网研究台、扫描配对码或粘贴链接。Mac 打开 http://127.0.0.1:8765/pair 查看二维码和访问码。同网连接需允许“本地网络”权限；跨网络使用配对页的 HTTPS 地址。扫描时按需允许相机权限。

不要把未签名 .app 当成可直接安装的 IPA。真机版已可在无签名模式下构建，实际安装需要你的开发团队和连接的手机。

## 功能与移动适配

- 原生底部四栏：前沿、论文、选题、更多；方法背景、收藏、产业观察、联动、信息源与设置有独立页面。
- 默认首页显示具体新进展，直接给出改动与关键证据。可按近 7 天 / 30 天、方向和处理状态筛选；详情包含对照、改动、证据与可验证问题。基础方法移到“更多 → 方法背景”，首次启动不弹连接设置。
- 进展状态“已了解 / 稍后读 / 略过”独立于论文阅读进度；支持离线排队和原子冲突检查，稍后读不随 7 天窗口过期。
- 系统安全区域、动态字体、深浅色、横竖屏、iPad 布局、VoiceOver 控件标签，使用原生列表、表单、筛选和搜索。
- 精读：摘要、方法导读、独立笔记、PDF 下载与 Quick Look；新增全文证据页，按章节/PDF 页码检索原文、回源核对、引用到笔记，可选模型解读显示引文和输入覆盖。准备的全文缓存到本机，可离线阅读。
- 笔记与选题：支持离线新增/修改，修改队列持久化；联网后以操作 ID 去重，并原子核查服务器基线。双方修改会进入“更多 → 同步冲突”，由你选择，不静默覆盖。
- PDF 需要在精读页单独下载；下载后可离线打开。初始 App 内置七条具体进展、五条按需背景导读（均标明核对日期）和六篇历史基础论文；不包含个人笔记或账号信息。
- 联动：Notion 资料库、批注预览/选择导入、Zotero RIS 和 Notion/Obsidian 包下载，调用 iOS 分享菜单保存到文件或其他 App。
- 来源管理：关注方向、自动检查开关、采集间隔和来源状态。信息采集与 Notion/Zotero 处理仍在 Mac 服务执行。
- 研究增量快照首次打开即可离线阅读；前台网络恢复时有限重试，自动连接失败不反复弹窗。采集状态可在连接横幅中查看。
- 访问码按服务器分区保存在钥匙串。本机缓存与草稿也按地址分区，切换服务器不混用草稿。首次尚未连接时产生的草稿会带入第一次连接并检查冲突；更换已有服务器地址时需先处理旧地址的待同步修改，旧分区仍保留。

## 连接边界

App 包含独立界面、缓存与本机编辑能力，但安装 App 不会自动打通校园网。首次联网或更新最新资料仍需手机能访问服务；电脑睡眠、地址变化、校园网隔离都会影响连接。离线模式会明确显示。

公网服务器使用 HTTPS；局域网 HTTP 通过 NSAllowsLocalNetworking 放行，未全局关闭 ATS。App 不采集位置或通讯录；相机只在用户扫描配对码时使用，不保存或上传相机画面。

## 构建与检查

在项目根目录运行（无需切换全局 xcode-select）：

    DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -project ios/ResearchRadar.xcodeproj -scheme ResearchRadar -configuration Debug -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath ios/build CODE_SIGNING_ALLOWED=NO build

    DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -project ios/ResearchRadar.xcodeproj -scheme ResearchRadar -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath ios/device-build CODE_SIGNING_ALLOWED=NO build

    DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test --package-path ios

    python3 -m unittest discover -s tests -v

修改 Swift 文件清单后运行 python3 ios/create_project.py 重新生成工程。图标可用 ios/make_icon.swift 生成。

## 本次验证记录

- iOS Simulator Debug 构建通过。
- iPhone arm64 Release 无签名构建通过。
- Swift 核心测试 6 项通过：快照与草稿、地址、JSON、配对链接、旧缓存兼容，以及进展日期与处理状态筛选。
- Python 后端测试覆盖手机提交幂等、笔记冲突保护、选题增删改和重试。
- 当前未连接 iPhone，尚未完成真机签名、安装和交互验收。
- 本机 CoreSimulator 无法创建测试设备（stuck in creation state），因此未完成模拟器中的页面运行验收。适配已在代码中实现，键盘、系统权限和实际显示仍需真机检查。

## 文件

ResearchRadar/Sources：原生界面、网络、缓存与同步队列。
ResearchRadar/Resources：基础阅读快照、图标和隐私声明。
ResearchRadar.xcodeproj：直接打开的 Xcode 工程。
CoreTests：Swift 核心测试。

## 2026-11-06：全文内容更新与方法工具

- 更新资料时自动同步当前已发布的精读全文和报告，不再要求逐篇打开后才缓存；内容版本或覆盖校验失败保留旧缓存及草稿。连接处显示可离线阅读的数量及全文更新时间。PDF附件仍需单独保存。
- 当前内置包包含10篇已通过检查的精读；后续按发布文件生成，实际在线数量以研究台为准。更新内置包不等于用户设备已更新，需重新安装客户端。
- 前沿页和手记详情支持两至三篇方法对照；“怎样用于我的研究”汇集当前精读已有的改动步骤与采纳前检查，不编造缺失实现条件。
- 本轮模拟器Debug和iPhone Release无签名构建通过，核心测试8项通过；没有连接用户iPhone，仍需下述现场验收。

## 仍需完成的现场验收

- 连接用户 iPhone，选择签名团队并运行；验证相机/本地网络权限、Bonjour、二维码跳转、键盘、动态字体和离线恢复。
- 当前 Mac 服务已采用用户登录常驻。现已增加临时公网 HTTPS 通道，Mac 本机 /pair 页可查看与扫码；需保持 Mac 在线，通道重建后地址会变化。App 打包本身不解除校园网隔离。
- 当前未配置模型 API，方法自动解读未进行真实模型调用验收；原文准备、检索和引用可用。

## 2026-11-10：1.0（5）

首页“重点”最多展示三个不同研究/方向的变化，完整证据和使用条件在详情中展开。方法对照先展示已选方法，选择列表放入单独面板。联网更新按条目下载完整全文，校验通过并本机保存后才发送保存回执；旧服务器回退完整包。离线快照明确标识。软件升级时仅未配置连接的本地快照刷新公开内容，保留个人笔记和同版本处理状态。

公开离线包通过 `python3 scripts/build_frontier_content.py --from-server` 从本机公开内容接口导出，不读取个人笔记或私人状态接口。当前编译包内有34项，非固定数量。每次打包前重新导出，通过模拟器和iPhone编译后再安装；未签名构建不代表已安装手机。
