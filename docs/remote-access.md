# 手机跨网络访问

2026-11-07 起可使用带访问码保护的临时 HTTPS 通道。无需服务器、域名或新账号。

1. 在 Mac 打开 http://127.0.0.1:8765/pair，选择“跨网络 · HTTPS”。
2. 原生 App 使用默认的“App 配对码”，在 App 的连接设置中扫码，再输入访问码并点击“保存并连接”。如需网页，切换“Safari 网页码”，用手机相机扫描；也可直接复制 HTTPS 地址。
3. 在 Mac 的配对页点击“在这台 Mac 查看”，将访问码输入手机。链接与二维码不含访问码。

当前 HTTPS 地址以配对页为准。手机可以使用蜂窝网络或其他 Wi-Fi，但 Mac 仍需在线、未睡眠，研究台与通道进程保持运行。临时域名在通道重建后会变化，需要更新手机书签或 App 连接地址。此方案没有实现固定域名和独立云端运行。[Cloudflare Quick Tunnel 官方说明](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)将其定位为开发与测试用途，无可用性保证。

## 服务管理

安装依赖与登录常驻服务：

```sh
brew install cloudflared
python3 scripts/manage_remote_access.py install
python3 scripts/manage_remote_access.py status
```

它独立于采集和精读服务，不会重复启动采集器或精读工作线程。已有数据仍位于 `~/Library/Application Support/ResearchRadar/Data`。卸载公网入口可执行：

```sh
python3 scripts/manage_remote_access.py remove
```

卸载仅停止公网通道，保留本机服务、论文、笔记和阅读进度。日志位于 `data/logs/remote-access.log` 和 `remote-access-error.log`，状态位于 `data/remote-access.json`，不包含访问码或会话令牌。

## 访问边界

- 公网入口单独监听 `127.0.0.1:8768`，关闭本机免登录；不会把 `8765` 的本机免登录入口直接暴露出去。
- HTTPS 由 Cloudflare 终止，再通过加密隧道到本机；Cloudflare 作为中转服务处理流量。不是浏览器到本机进程的端到端 TLS。
- 除登录页资源和最小服务发现信息，所有数据接口都需要访问码登录。会话 Cookie 带 Secure、HttpOnly 和 SameSite=Strict。
- 公网不提供访问码读取接口；写入请求仅接受精确匹配的 HTTPS Origin，原生 App 可不发送 Origin。任意转发头不能开启本机免登录。
- 隧道连通检查每 30 秒执行；状态超过 90 秒不再展示为可用，连续失败后重新建立。网络限制可能影响通道，尤其是 Tunnel 的出站连接端口。
- 改用其他地址后，原生 App 保留原地址分区的离线草稿，需要切回原地址处理；当前不会自动合并不同地址的未同步草稿。

## 下一阶段

固定地址需要具备可持续托管的身份与路由配置，例如带域名的命名隧道；脱离 Mac 则需要将后端、数据存储和采集迁移到常在线服务。当前未创建云端数据库、域名账户或付费资源。公网链路已通过 HTTPS 请求与浏览器验证；真实 iPhone 的蜂窝网络、Safari 和原生 App 安装仍需真机验收。
