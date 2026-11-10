import SwiftUI
import UIKit

struct ShareFile: Identifiable { let id = UUID();let url:URL }
struct ShareSheet: UIViewControllerRepresentable {
    let url:URL
    func makeUIViewController(context:Context) -> UIActivityViewController { UIActivityViewController(activityItems:[url],applicationActivities:nil) }
    func updateUIViewController(_ controller:UIActivityViewController,context:Context) {}
}
struct ConnectionView: View {
    @EnvironmentObject var store: RadarStore
    @Environment(\.dismiss) private var dismiss
    let invitation: ConnectionInvitation?
    let firstRun: Bool
    init(invitation:ConnectionInvitation? = nil,firstRun:Bool = false) { self.invitation = invitation;self.firstRun = firstRun }
    @StateObject private var discovery = ServerDiscovery()
    @State private var scanning = false
    @State private var scannedValue: String?
    @State private var pairingNotice: String?
    @State private var pairingError: String?
    @State private var initialized = false
    @State private var pasted = ""
    @State private var expectedID: String?
    @State private var address=""
    @State private var code=""
    @FocusState private var activeField:String?
    var body: some View {
        Form {
            if firstRun {
                Section("开始你的研究工作流") {
                    Text("先了解重要技术，再按兴趣深入论文与证据。连接 Mac 可更新资料，内置技术导读可直接离线阅读。")
                    Button("先离线阅读") { dismiss() }
                }
            }
            Section("发现与配对") {
                if let notice = pairingNotice {
                    Label(notice,systemImage:"checkmark.circle.fill").foregroundStyle(.green).accessibilityIdentifier("pairing-result")
                    Text(address).font(.caption).textSelection(.enabled)
                    Button(code.isEmpty ? "下一步：输入访问码" : "下一步：连接研究台") { activeField=code.isEmpty ? "code" : nil; if !code.isEmpty { connect() } }.disabled(store.busy || store.configuring)
                }
                Button { discovery.start() } label: { Label("查找同网研究台",systemImage:"dot.radiowaves.left.and.right") }
                Text(discovery.status).font(.caption).foregroundStyle(.secondary)
                ForEach(discovery.servers) { server in
                    Button { address = server.address; expectedID = server.id } label: { VStack(alignment:.leading) { Text(server.name);Text(server.address).font(.caption) } }
                }
                Button { scanning = true } label: { Label("扫描 Mac 上的配对二维码",systemImage:"qrcode.viewfinder") }
                TextField("或粘贴配对链接 / HTTPS 地址",text:$pasted).textInputAutocapitalization(.never).autocorrectionDisabled()
                Button("使用配对链接") { accept(pasted) }.disabled(pasted.isEmpty)
                Text("Mac 浏览器打开 http://127.0.0.1:8765/pair。二维码不含访问码，配对时会核对服务器身份。自动发现需要本地网络权限与设备互通。 ").font(.caption).foregroundStyle(.secondary)
            }
            Section("研究台地址") {
                TextField("http://Mac 名称.local:8765",text:$address).focused($activeField,equals:"address").keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled().accessibilityLabel("服务器地址")
                Text("跨网络请使用 Mac 配对页的 HTTPS 地址；同网可使用 .local 地址或当前 IP。手机上的 127.0.0.1 指向手机自身。临时 HTTPS 通道重建后，需更新连接地址。").font(.caption).foregroundStyle(.secondary)
            }
            Section("访问码") {
                SecureField("xxxx-xxxx-xxxx",text:$code).focused($activeField,equals:"code").textContentType(.password).textInputAutocapitalization(.never).autocorrectionDisabled().privacySensitive()
                Text("二维码已填入地址，访问码需从 Mac 配对页查看并填写。填写后点击“保存并连接”；访问码只保存在本机钥匙串。").font(.caption).foregroundStyle(.secondary)
            }
            Section {
                Button { connect() } label: { HStack { Text((store.busy || store.configuring) ? "正在连接…" : "保存并连接");Spacer();if store.busy || store.configuring { ProgressView() } } }.disabled(store.busy || store.configuring || address.trimmingCharacters(in:.whitespaces).isEmpty)
                LabeledContent("状态",value:store.connected && (try? ConnectionAddress.normalized(address)) == store.baseURL ? "已连接" : pairingNotice != nil ? "地址已识别 · 等待连接" : "离线 · 使用缓存")
                if let notice = store.connectionNotice { Text(notice).font(.caption).foregroundStyle(.secondary) }
                if let date=store.lastConnected { LabeledContent("上次连接") { Text(date,format:.dateTime.month().day().hour().minute()) } }
                LabeledContent("离线精读",value:store.contentSummary)
                LabeledContent("内容保存确认",value:store.contentReceipt.flag("current") ? "研究台已收到本机确认" : store.contentCacheManifest.isEmpty ? "内置离线快照" : "等待确认或有新内容")
                if let date=ISO8601DateFormatter().date(from:store.contentCacheManifest.text("synced_at")) { LabeledContent("全文更新") { Text(date,format:.dateTime.month().day().hour().minute()) } }
                if let notice=store.contentNotice { Text(notice).font(.caption).foregroundStyle(.orange) }
                if !store.pending.isEmpty { Text("当前服务器有 \(store.pending.count) 项本机修改待同步。切换地址后会保留在原服务器分区，切回可继续处理。").font(.caption).foregroundStyle(.secondary) }
            }
            Section("连接排查") {
                Text("1. Mac 保持在线，研究台与公网通道运行。\n2. 跨网络使用 Mac 配对页的 HTTPS 地址。\n3. 同网连接需要本地网络权限与设备互通。\n4. 同一校园网账号不保证设备之间可互通。")
                Button("打开系统中的 App 设置") { if let url=URL(string:UIApplication.openSettingsURLString) { UIApplication.shared.open(url) } }
            }
            Section("离线使用") {
                Text("内置基础论文可直接阅读。连接后缓存文献、笔记和选题；PDF 需在精读页单独保存。离线修改会排队，联网时先检查服务器内容是否变化。").font(.subheadline)
            }
        }.scrollDismissesKeyboard(.interactively).navigationTitle("连接设置").navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItemGroup(placement:.keyboard) { Spacer();Button("收起键盘") { activeField=nil } } }
        .onAppear {
            guard !initialized else { return };initialized=true
            address=invitation?.address.absoluteString ?? store.serverAddress;expectedID=invitation?.id;code=store.keychain()
            if invitation != nil { pairingNotice="已识别研究台，请输入访问码后连接。" }
        }
        .onDisappear { discovery.stop() }
        .sheet(isPresented:$scanning,onDismiss:{
            guard let value=scannedValue else { return };scannedValue=nil;accept(value)
        }) { ScannerView { scannedValue=$0 } }
        .alert("连接未完成",isPresented:Binding(get:{pairingError != nil},set:{if !$0 { pairingError=nil }})) { Button("知道了") { pairingError=nil } } message: { Text(pairingError ?? "") }
    }
    func accept(_ value:String) {
        do {
            let target=try ConnectionTarget.parse(value)
            address=target.address.absoluteString;expectedID=target.expectedID;pairingError=nil
            pairingNotice=code.isEmpty ? "已识别研究台。下一步输入访问码，然后连接。" : "已识别研究台。点击下方按钮开始连接。"
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        } catch { pairingNotice=nil;pairingError=error.localizedDescription }
    }
    func connect() {
        guard !store.busy && !store.configuring else { return }
        activeField=nil
        guard !code.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty else {
            pairingError="请先填写 Mac 配对页显示的访问码。二维码不包含访问码。";return
        }
        Task {
            store.message=nil
            await store.configure(address:address,code:code,expectedID:expectedID)
            if store.connected {
                pairingNotice="已连接研究台，正在使用最新内容。"
                if firstRun { dismiss() }
            } else {
                pairingError=store.message ?? store.connectionNotice ?? "连接未完成，请检查地址与访问码。"
                store.message=nil
            }
        }
    }
}
struct ConflictsView: View {
    @EnvironmentObject var store: RadarStore
    var body: some View {
        List {
            if store.conflicts.isEmpty { ContentUnavailableView("暂无同步冲突",systemImage:"checkmark.shield",description:Text("本机修改与服务器同时变化时，会在这里等待你确认。")) }
            ForEach(store.conflicts) { change in
                Section(store.entry(change.target)?.title ?? "选题修改") {
                    Text("本机修改").font(.headline)
                    ForEach(change.changes.keys.sorted(),id:\.self) { key in VStack(alignment:.leading,spacing:5) { Text(key).font(.caption).foregroundStyle(.secondary);Text(display(change.changes[key])).textSelection(.enabled) } }
                    Text("服务器当前内容").font(.headline)
                    ForEach(change.changes.keys.sorted(),id:\.self) { key in VStack(alignment:.leading,spacing:5) { Text(key).font(.caption).foregroundStyle(.secondary);Text(display(change.conflict?[key])).textSelection(.enabled) } }
                    Button("以本机修改覆盖（再次核查后提交）") { Task { await store.resolve(change,useLocal:true) } }.disabled(store.busy)
                    Button("保留服务器版本，放弃本机这次修改",role:.destructive) { Task { await store.resolve(change,useLocal:false) } }.disabled(store.busy)
                }
            }
        }.navigationTitle("同步冲突").navigationBarTitleDisplayMode(.inline)
    }
    func display(_ value:JSONValue?) -> String {
        guard let value else { return "记录不存在" }
        if case .bool(let b)=value.value { return b ? "是" : "否" }
        return value.string.isEmpty ? "（空）" : value.string
    }
}
struct SourcesView: View {
    @EnvironmentObject var store: RadarStore
    @State private var saving=false
    var body: some View {
        List {
            Section("我的关注方向") {
                ForEach(store.snapshot.topics) { topic in
                    Toggle(topic.data.text("name"),isOn:Binding(get:{store.snapshot.settings.strings("focus").contains(topic.id)},set:{ selected in
                        var focus=Set(store.snapshot.settings.strings("focus"));if selected { focus.insert(topic.id) } else { focus.remove(topic.id) }
                        Task { await updateSettings(["focus":JSONValue(value:.array(focus.sorted().map { JSONValue($0) }))]) }
                    })).disabled(!store.connected || saving)
                }
            }
            Section("检查更新") {
                Toggle("Mac 服务运行期间自动检查",isOn:Binding(get:{store.snapshot.settings.flag("auto_sync")},set:{ value in Task { await updateSettings(["auto_sync":JSONValue(value)]) } })).disabled(!store.connected || saving)
                Picker("检查间隔",selection:Binding(get:{store.snapshot.settings["interval_minutes"] ?? JSONValue("180")},set:{ value in Task { await updateSettings(["interval_minutes":value]) } })) {
                    ForEach([60,180,360,1440],id:\.self) { value in Text(value==1440 ? "每天" : "每 \(value/60) 小时").tag(JSONValue(value:.number(Double(value)))) }
                }.disabled(!store.connected || saving)
                Button("立即检查信息源") { Task { await store.run("api/sync") } }.disabled(!store.connected || store.busy)
                Text("采集在 Mac 服务执行；iPhone 不承诺后台定时采集。离线时可继续阅读缓存。").font(.caption).foregroundStyle(.secondary)
            }
            ForEach(store.snapshot.sources) { source in
                Section(source.data.text("name")) {
                    Text(source.data.text("description")).font(.subheadline)
                    if source.data.text("collector") != "manual" {
                        Toggle("自动采集",isOn:Binding(get:{source.data.flag("enabled")},set:{ value in Task { await toggleSource(source.id,value:value) } })).disabled(!store.connected || saving)
                        Text("最近成功：\(source.data.text("last_success").isEmpty ? "尚未检查" : source.data.text("last_success"))").font(.caption).foregroundStyle(.secondary)
                        if !source.data.text("error").isEmpty { Text(source.data.text("error")).font(.caption).foregroundStyle(.orange) }
                    }
                    SafeExternalLink("原始来源",value:source.data.text("url"),symbol:"arrow.up.right.square")
                }
            }
        }.navigationTitle("信息源与偏好").navigationBarTitleDisplayMode(.inline)
    }
    func updateSettings(_ body:Record) async {
        saving=true;defer { saving=false }
        do { _ = try await store.object("api/settings",method:"PATCH",body:body);await store.refresh() } catch { store.message=error.localizedDescription }
    }
    func toggleSource(_ id:String,value:Bool) async {
        saving=true;defer { saving=false }
        do { _ = try await store.object("api/sources/"+id,method:"PATCH",body:["enabled":JSONValue(value)]);await store.refresh() } catch { store.message=error.localizedDescription }
    }
}
struct IntegrationsView: View {
    @EnvironmentObject var store: RadarStore
    @State private var all=false
    @State private var shared:ShareFile?
    @State private var downloading=false
    @State private var preview:AnnotationPreview?
    var body: some View {
        List {
            Section("Notion 精选与选题") {
                SafeExternalLink("打开科研资料库",value:store.notion.text("target"),symbol:"arrow.up.right.square")
                Text(store.notion.flag("runtime_configured") ? "服务器已配置 Notion 写入权限" : "网页后台尚未配置 Notion 凭证，可通过对话执行同步。").font(.caption).foregroundStyle(.secondary)
                Button("同步精选与选题到 Notion") { Task { await store.run("api/integrations/notion/sync") } }.disabled(!store.connected || store.busy || !store.notion.flag("runtime_configured"))
            }
            Section("Zotero 阅读证据") {
                Text("从 Mac 上运行的 Zotero 读取与现有论文匹配的批注。先预览，再导入；不会覆盖精读笔记。").font(.subheadline).foregroundStyle(.secondary)
                Button("检查并预览批注") { Task { await previewZotero() } }.disabled(!store.connected || downloading)
            }
            Section("文件交换") {
                Toggle("导出全部内容",isOn:$all)
                Text(all ? "包含服务器上的全部内容与选题。" : "包含服务器上的收藏、笔记及已开始阅读内容，另附全部选题。本机未同步的草稿可先通过精读页分享。").font(.caption).foregroundStyle(.secondary)
                exportButton("Zotero RIS",target:"zotero",suffix:"ris")
                exportButton("Notion CSV / Markdown",target:"notion",suffix:"zip")
                exportButton("Obsidian 笔记库",target:"obsidian",suffix:"zip")
                Button { Task { await download("api/export",name:"research-backup.zip") } } label: { Label("导出研究台备份",systemImage:"externaldrive") }.disabled(!store.connected || downloading)
            }
            Section("同步记录") {
                let runs=store.snapshot.integrations.records("runs")
                if runs.isEmpty { Text("暂无同步记录").foregroundStyle(.secondary) }
                ForEach(Array(runs.enumerated()),id:\.offset) { _,row in VStack(alignment:.leading,spacing:5) { Text("\(row.text("provider")) · \(row.text("status"))").font(.subheadline.weight(.medium));Text(row.text("detail")).font(.caption);Text(row.text("at")).font(.caption2).foregroundStyle(.secondary) } }
            }
        }.navigationTitle("产品联动").navigationBarTitleDisplayMode(.inline)
        .sheet(item:$shared) { ShareSheet(url:$0.url) }
        .sheet(item:$preview) { value in NavigationStack { AnnotationPreviewView(result:value.value) } }
    }
    func exportButton(_ title:String,target:String,suffix:String) -> some View {
        Button { Task { await download("api/integrations/export?target=\(target)&scope=\(all ? "all" : "selected")",name:"research-\(target).\(suffix)") } } label: { Label(title,systemImage:"square.and.arrow.up") }.disabled(!store.connected || downloading)
    }
    func download(_ path:String,name:String) async { downloading=true;defer { downloading=false };do { shared=ShareFile(url:try await store.download(path,name:name)) } catch { store.message=error.localizedDescription } }
    func previewZotero() async { downloading=true;defer { downloading=false };do { preview=AnnotationPreview(value:try await store.object("api/integrations/zotero/preview",method:"POST")) } catch { store.message=error.localizedDescription } }
}
struct AnnotationPreview: Identifiable { let id=UUID();let value:Record }
struct AnnotationPreviewView: View {
    @EnvironmentObject var store: RadarStore
    @Environment(\.dismiss) private var dismiss
    let result:Record
    @State private var selected=Set<String>()
    @State private var saving=false
    var rows:[Record] { result.records("annotations") }
    var body: some View {
        List {
            if rows.isEmpty { ContentUnavailableView("没有匹配的批注",systemImage:"text.magnifyingglass",description:Text("请确认 Zotero 中的文献含有与研究台一致的 arXiv 标识，并已添加 PDF 批注。")) }
            ForEach(Array(rows.enumerated()),id:\.offset) { _,row in
                Section {
                    Toggle("第 \(row.text("page")) 页",isOn:Binding(get:{selected.contains(row.text("id"))},set:{if $0 { selected.insert(row.text("id")) } else { selected.remove(row.text("id")) }}))
                    Text(row.text("quote")).textSelection(.enabled);Text(row.text("comment")).foregroundStyle(.secondary)
                }
            }
        }.navigationTitle("批注预览").navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement:.cancellationAction) { Button("关闭") { dismiss() } }
            ToolbarItem(placement:.confirmationAction) { Button("导入") { Task { saving=true;do { _ = try await store.object("api/integrations/zotero/import",method:"POST",body:["ids":JSONValue(value:.array(selected.map { JSONValue($0) }))]);await store.refresh();dismiss() } catch { store.message=error.localizedDescription };saving=false } }.disabled(selected.isEmpty || saving) }
        }.onAppear { selected=Set(rows.map{$0.text("id")}) }
    }
}
