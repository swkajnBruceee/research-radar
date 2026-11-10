# 2026-11-07 手机跨网络访问验收

## 已实现并运行

- 公网入口采用 Cloudflare Quick Tunnel，当前无需新增账号、域名或付费资源。HTTPS 网关单独监听本机 8768 端口，强制访问码登录。
- 新增用户登录后自动启动的 `com.bruce.research-radar-remote` 服务，与原有采集/精读服务分别运行，不额外启动工作线程。
- Mac `/pair` 页面默认展示可用的 HTTPS 地址与网页二维码，也可切换同网地址、通过不含访问码的邀请链接打开原生 App。页面每 15 秒更新状态。
- 通道通过 `/api/discovery` 与实例 ID 验证连通性，状态过期不再标为可用，连续探测失败会重建。日志不记录请求路径、访问码、Cookie 或笔记。
- 原生 App 继续支持 HTTPS 地址，扫描器现可接受网页根地址二维码；连接说明已更新。

## 验证结果

- Python 完整测试 76 项通过；变更收尾再次运行访问边界相关测试 9 项通过。
- JavaScript 测试 26 项通过；Swift 核心测试 8 项通过。
- iOS 模拟器 Debug 与 iPhone arm64 Release 均构建成功；真机包未经签名、未安装。
- 实际通过公网 HTTPS 地址请求：匿名首页为登录页，服务发现仅返回 id/name/protocol；匿名 `/api/state`、`/api/content`、`/api/export` 均为 401，公网访问码读取始终为 403。
- 使用本机读取的访问码完成 HTTPS 登录，未在输出中打印凭据；会话 Cookie 带 Secure，登录后 health、state、content/manifest、pairing 均为 200，配对信息中的本机端口仍为 8765。
- 针对 Origin 冒用、localhost Host、转发头伪造、编码路径、通道尚未建立与状态过期做了独立测试，均通过。
- Chrome 已通过实际公网域名显示登录页；Mac 配对页可在 HTTPS/同网之间切换。390px 布局无横向溢出。使用 Apple Vision 从手机尺寸配对页截图解出二维码，内容精确对应当前 HTTPS 地址。
- 外部网页抓取工具无法访问临时域名，因此没有将该工具的失败作为外网连通证据；公网 HTTPS 请求与 Chrome 验证均由当前 Mac 发起。

截图：[配对页](pair-desktop.jpg)、[手机尺寸配对页](pair-mobile.jpg)、[公网登录页](public-login-mobile.jpg)。

## 明确未完成的边界

当前为临时公网通道，Mac 睡眠或关机后无法访问，通道重建后地址可能变化。尚未实现固定域名、独立常在线云端后端或跨地址的原生 App 离线草稿自动合并。真实 iPhone、蜂窝网络、Safari 与签名安装后的原生 App 未验收；需要用户在真实设备打开链接完成最终网络验证。后续路线见 [公网访问说明](../../remote-access.md)。
