import SwiftUI
import QuickLook

struct ConnectionBanner: View {
    @EnvironmentObject var store: RadarStore
    var body: some View {
        HStack(alignment:.top,spacing:12) {
            Image(systemName:store.connected ? "checkmark.circle.fill" : "wifi.slash").foregroundStyle(store.connected ? .green : .secondary)
            VStack(alignment:.leading,spacing:5) {
                Text(store.connected ? "已连接研究台" : "离线阅读模式").font(.subheadline.weight(.medium))
                Text(store.serverSyncRunning ? "正在检查公开信息源…" : store.connected ? "\(store.pending.count) 项本机修改待处理" : "可浏览已缓存内容；笔记和收藏会保存在本机。").font(.caption).foregroundStyle(.secondary)
                Text(store.contentSummary).font(.caption).foregroundStyle(.secondary)
                if let notice=store.contentNotice { Text(notice).font(.caption).foregroundStyle(.orange) }
            }
            Spacer(minLength:0)
            NavigationLink { ConnectionView() } label: { Image(systemName:"gearshape").frame(minWidth:44,minHeight:44) }.accessibilityLabel("连接设置")
        }.padding().background(.quaternary,in:RoundedRectangle(cornerRadius:16))
    }
}
struct PaperRow: View {
    @EnvironmentObject var store: RadarStore
    let item: Entry
    var body: some View {
        VStack(alignment:.leading,spacing:10) {
            HStack {
                Text(item.isPaper ? "论文" : item.data.text("kind") == "model" ? "模型" : item.data.text("kind") == "release" ? "代码发布" : "研究动态").font(.caption).foregroundStyle(.tint)
                if item.data.flag("curated") { Text("基础阅读").font(.caption).foregroundStyle(.secondary) }
                Spacer()
                Text(String(item.data.text("updated").prefix(10))).font(.caption).foregroundStyle(.secondary)
            }
            Text(store.signals.first(where:{$0.id==item.id})?.title ?? item.title).font(.headline).fixedSize(horizontal:false,vertical:true)
            Text(store.signals.first(where:{$0.id==item.id})?.data.text("delta") ?? item.data.text("summary")).font(.subheadline).foregroundStyle(.secondary).lineLimit(3)
            HStack {
                Text(item.topics.prefix(2).map(store.topicName).joined(separator:" · ")).font(.caption).foregroundStyle(.secondary)
                Spacer()
                if item.data.flag("saved") { Image(systemName:"bookmark.fill").foregroundStyle(.tint).accessibilityLabel("已收藏") }
                if item.data.text("reading") == "read" { Image(systemName:"checkmark.circle").foregroundStyle(.secondary).accessibilityLabel("已读") }
            }
        }.padding(.vertical,8)
    }
}
struct TechnologyLibraryView: View {
    @EnvironmentObject var store: RadarStore
    @State private var search = ""
    @State private var topic = "all"
    var briefs:[Entry] {
        store.technologies.filter { b in
            (topic == "all" || b.topics.contains(topic)) &&
            (search.isEmpty || [b.title,b.data.text("tagline"),b.data.text("why"),b.data.text("update")].joined(separator:" ").localizedCaseInsensitiveContains(search))
        }
    }
    var body: some View {
        List {
            Section {
                Text("先了解方法、价值与近期变化，再选择要深入的内容。").font(.subheadline).foregroundStyle(.secondary).lineSpacing(4)
                Menu {
                    Picker("方法方向",selection:$topic) {
                        Text("全部方法").tag("all");Text("语言与动作").tag("vla");Text("预测与规划").tag("world");Text("数据与迁移").tag("data");Text("控制与执行").tag("control")
                    }
                } label: { Label(topic == "all" ? "全部方法" : store.topicName(topic),systemImage:"line.3.horizontal.decrease.circle") }
            }
            if briefs.isEmpty { ContentUnavailableView("没有匹配的技术",systemImage:"sparkles",description:Text("试试 VLA、世界模型、数据或控制。")) }
            ForEach(briefs) { brief in Section { TechnologyCardView(brief:brief) } }
            Section {
                Text("按方法理解与科研价值组织。导读核对：\(store.technologies.map{$0.data.text("checked_at")}.max() ?? "尚未更新")。顺序属于编辑导读，新资料经核对后再形成进展解读。").font(.caption).foregroundStyle(.secondary)
                ConnectionBanner().listRowInsets(EdgeInsets())
            }
        }.listStyle(.insetGrouped).navigationTitle("重要技术")
        .searchable(text:$search,prompt:"搜索技术、原理或问题")
        .refreshable { if store.baseURL != nil { await store.refresh(silent:true) } }
        .toolbar {
            ToolbarItem(placement:.topBarTrailing) {
                if store.baseURL == nil { NavigationLink { ConnectionView() } label: { Image(systemName:"network") }.accessibilityLabel("连接研究台更新资料") }
                else { Button { Task { await store.refresh(silent:true) } } label: { Image(systemName:store.busy ? "hourglass" : "arrow.clockwise") }.disabled(store.busy).accessibilityLabel("更新资料") }
            }
        }
    }
}

enum LibraryMode { case papers, saved, industry }
struct LibraryView: View {
    @EnvironmentObject var store: RadarStore
    let mode: LibraryMode
    @State private var search = ""
    @State private var topic = "all"
    @State private var reading = "all"
    @State private var oldestFirst = false
    var title: String { mode == .papers ? "论文精读" : mode == .saved ? "我的收藏" : "产业观察" }
    var items: [Entry] {
        store.snapshot.items.filter { item in
            (mode == .saved || store.canDisplayPaper(item)) &&
            (mode == .papers ? (item.isPaper && !item.data.flag("curated")) : mode == .saved ? item.data.flag("saved") : !item.isPaper) &&
            (topic == "all" || item.topics.contains(topic)) &&
            (reading == "all" || item.data.text("reading") == reading) &&
            (search.isEmpty || [item.title,item.data.text("title"),item.data.text("summary"),item.data.text("notes"),item.data.text("authors")].joined(separator:" ").localizedCaseInsensitiveContains(search))
        }.sorted { oldestFirst ? $0.data.text("published") < $1.data.text("published") : $0.data.text("updated") > $1.data.text("updated") }
    }
    var body: some View {
        List {
            Section {
                Menu {
                    Picker("研究方向",selection:$topic) { Text("全部方向").tag("all"); ForEach(store.snapshot.topics) { Text($0.title.isEmpty ? $0.data.text("name") : $0.title).tag($0.id) } }
                    Picker("阅读状态",selection:$reading) { Text("全部阅读状态").tag("all"); Text("未读").tag("unread");Text("在读").tag("reading");Text("已读").tag("read") }
                    Toggle("按发表时间正序",isOn:$oldestFirst)
                } label: { Label("筛选 · \(items.count) 条",systemImage:"line.3.horizontal.decrease.circle") }
                if topic != "all" || reading != "all" { Button("清除筛选") { topic = "all"; reading = "all" } }
            }
            if items.isEmpty { ContentUnavailableView("没有匹配内容",systemImage:"books.vertical",description:Text("调整筛选，或在连接研究台后检查更新。")) }
            ForEach(items) { item in
                NavigationLink { PaperDetailView(id:item.id) } label: { PaperRow(item:item) }
                .swipeActions(edge:.trailing,allowsFullSwipe:false) { Button { Task { await store.stageItem(item.id,changes:["saved":JSONValue(!item.data.flag("saved"))]) } } label: { Label(item.data.flag("saved") ? "取消收藏" : "收藏",systemImage:"bookmark") }.tint(.green) }
            }
        }.searchable(text:$search,prompt:"论文、方法、作者、笔记").navigationTitle(title).refreshable { await store.refresh() }
    }
}
struct PaperDetailView: View {
    @EnvironmentObject var store: RadarStore
    let id: String
    @State private var editing = false
    @State private var idea = false
    @State private var preview: URL?
    @State private var loadingPDF = false
    @State private var exporting = false
    @State private var shared: ShareFile?
    var item: Entry? { store.entry(id) }
    var body: some View {
        Group {
            if let item {
                List {
                    Section {
                        Text(item.title).font(.title2.bold()).textSelection(.enabled)
                        if !item.data.text("title_zh").isEmpty { Text(item.data.text("title")).font(.subheadline).foregroundStyle(.secondary).textSelection(.enabled) }
                        Text(item.data.text("authors")).font(.caption).foregroundStyle(.secondary)
                        Text("发表：\(item.data.text("published")) · \(item.data.text("note_level"))").font(.caption).foregroundStyle(.secondary)
                        if item.data.flag("curated") { Label("历史基础导读，尚不代表全文分析或复现",systemImage:"info.circle").font(.caption).foregroundStyle(.secondary) }
                    }
                    Section("阅读") {
                        SafeExternalLink("打开原始来源",value:item.data.text("url"),symbol:"arrow.up.right.square")
                        if !item.data.text("code_url").isEmpty { SafeExternalLink("作者代码",value:item.data.text("code_url"),symbol:"chevron.left.forwardslash.chevron.right") }
                        if item.isPaper { NavigationLink { DeepReadingView(id:id) } label: { Label("全文证据与方法精读",systemImage:"text.magnifyingglass") } }
                        if !item.data.text("pdf_url").isEmpty {
                            Button { Task { await openPDF(item) } } label: { Label(loadingPDF ? "正在保存 PDF…" : FileManager.default.fileExists(atPath:store.pdfFile(item).path) ? "阅读已保存的 PDF" : "下载并离线保存 PDF",systemImage:"doc.richtext") }.disabled(loadingPDF)
                            Text("摘要和笔记已缓存在本机；PDF 需要单独下载。大文件建议在 Wi-Fi 下保存。").font(.caption).foregroundStyle(.secondary)
                        }
                        Picker("阅读状态",selection:Binding(get:{item.data.text("reading")},set:{ value in Task { await store.stageItem(id,changes:["reading":JSONValue(value)]) } })) {
                            Text("未读").tag("unread"); Text("在读").tag("reading");Text("已读").tag("read")
                        }
                    }
                    Section(item.data.flag("curated") ? "基础导读" : "原始摘要 / 发布说明") { Text(item.data.text("summary")).textSelection(.enabled).lineSpacing(5) }
                    let analysis = item.data["analysis"]?.object ?? [:]
                    ForEach([("problem","研究问题"),("method","方法机制"),("evidence","实验证据"),("limitations","适用边界"),("question","候选问题 · 待验证")],id:\.0) { key,label in
                        if !analysis.text(key).isEmpty { Section(label) { Text(analysis.text(key)).textSelection(.enabled).lineSpacing(4) } }
                    }
                    Section("我的精读笔记") {
                        if item.data.text("notes").isEmpty { Text("从问题、方法、证据和局限开始记录。").foregroundStyle(.secondary) }
                        else { Text(item.data.text("notes")).textSelection(.enabled).lineSpacing(4) }
                        Button { editing = true } label: { Label("编辑笔记",systemImage:"square.and.pencil") }
                        if store.pending.contains(where:{$0.target==id}) { Label("本机修改已保存，待同步",systemImage:"internaldrive").font(.caption).foregroundStyle(.secondary) }
                    }
                    if !item.data.records("zotero_annotations").isEmpty {
                        Section("Zotero 阅读证据") {
                            ForEach(Array(item.data.records("zotero_annotations").enumerated()),id:\.offset) { _,row in
                                VStack(alignment:.leading,spacing:8) {
                                    Text("第 \(row.text("page")) 页").font(.caption).foregroundStyle(.secondary)
                                    Text(row.text("quote")).textSelection(.enabled);Text(row.text("comment")).foregroundStyle(.secondary)
                                    SafeExternalLink("回到 Zotero",value:row.text("source"),symbol:"arrow.up.right.square")
                                }.padding(.vertical,5)
                            }
                        }
                    }
                    Section {
                        Button { idea = true } label: { Label("从这项工作记录一个问题",systemImage:"lightbulb") }
                        ShareLink(item:markdown(item)) { Label("分享精读笔记",systemImage:"square.and.arrow.up") }
                        if item.isPaper { Button { Task { await exportRIS(item) } } label: { Label(exporting ? "正在导出…" : "导出 Zotero RIS",systemImage:"doc.badge.arrow.up") }.disabled(exporting || !store.connected) }
                    }
                }.navigationTitle("精读").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement:.topBarTrailing) { Button { Task { await store.stageItem(id,changes:["saved":JSONValue(!item.data.flag("saved"))]) } } label: { Image(systemName:item.data.flag("saved") ? "bookmark.fill" : "bookmark") }.accessibilityLabel(item.data.flag("saved") ? "取消收藏" : "收藏") } }
                .sheet(isPresented:$editing) { NavigationStack { NoteEditor(item:item) } }
                .sheet(isPresented:$idea) { NavigationStack { IdeaEditor(existing:nil,source:item) } }
                .sheet(item:$shared) { ShareSheet(url:$0.url) }
            } else { ContentUnavailableView("内容尚未缓存",systemImage:"wifi.slash",description:Text("连接研究台后刷新内容。")) }
        }.quickLookPreview($preview)
        .task { if store.connected { do { _ = try await store.details(id) } catch { /* Cached reading remains available. */ } } }
    }
    func markdown(_ item:Entry) -> String { "# \(item.title)\n\n\(item.data.text("url"))\n\n## 摘要\n\n\(item.data.text("summary"))\n\n## 我的笔记\n\n\(item.data.text("notes"))" }
    func openPDF(_ item:Entry) async {
        if FileManager.default.fileExists(atPath:store.pdfFile(item).path) { preview = store.pdfFile(item);return }
        loadingPDF = true;defer { loadingPDF = false }
        do { preview = try await store.cachePDF(item) } catch { store.message = error.localizedDescription }
    }
    func exportRIS(_ item:Entry) async {
        exporting = true;defer { exporting = false }
        var c = URLComponents();c.path = "api/integrations/export";c.queryItems = [URLQueryItem(name:"target",value:"zotero"),URLQueryItem(name:"item_id",value:item.id)]
        do { shared = ShareFile(url:try await store.download(c.string!,name:"paper.ris")) } catch { store.message = error.localizedDescription }
    }
}
struct NoteEditor: View {
    @EnvironmentObject var store: RadarStore
    @Environment(\.dismiss) private var dismiss
    let item: Entry
    @State private var notes: String
    @State private var level: String
    @State private var discard = false
    @FocusState private var noteFocused:Bool
    init(item:Entry, appendix:String = "") { self.item = item;_notes = State(initialValue:item.data.text("notes")+appendix);_level = State(initialValue:item.data.text("note_level")) }
    var changed:Bool { notes != item.data.text("notes") || level != item.data.text("note_level") }
    var body: some View {
        Form {
            Section("已完成的分析程度") { Picker("程度",selection:$level) { ForEach(["摘要筛选","全文分析","代码核查"],id:\.self) { Text($0).tag($0) } } }
            Section("我的笔记") { TextEditor(text:$notes).focused($noteFocused).frame(minHeight:320).accessibilityLabel("精读笔记");Text("本机保存后待联网同步；可使用 Markdown。最多 60000 字符。").font(.caption).foregroundStyle(.secondary) }
            Section { Button("插入精读模板") { if notes.isEmpty { notes = "## 研究问题\n\n## 与已有方法的区别\n\n## 核心机制\n\n## 实验证据与原文位置\n\n## 局限\n\n## 待验证假设\n\n## 最小实验\n" } }.disabled(!notes.isEmpty) }
        }.scrollDismissesKeyboard(.interactively).navigationTitle("编辑笔记").navigationBarTitleDisplayMode(.inline).interactiveDismissDisabled(changed)
        .toolbar {
            ToolbarItemGroup(placement:.keyboard) { Spacer();Button("收起键盘") { noteFocused=false } }
            ToolbarItem(placement:.cancellationAction) { Button("取消") { if changed { discard = true } else { dismiss() } } }
            ToolbarItem(placement:.confirmationAction) { Button("保存") { Task { await store.stageItem(item.id,changes:["notes":JSONValue(notes),"note_level":JSONValue(level)]);dismiss() } }.disabled(notes.count>60000) }
        }.confirmationDialog("放弃未保存的修改？",isPresented:$discard,titleVisibility:.visible) { Button("放弃修改",role:.destructive) { dismiss() } }
    }
}
struct SafeExternalLink: View {
    let title:String;let value:String;let symbol:String
    init(_ title:String,value:String,symbol:String) { self.title=title;self.value=value;self.symbol=symbol }
    var body: some View {
        if let url=URL(string:value),["http","https","zotero"].contains(url.scheme?.lowercased() ?? ""),url.user==nil,url.password==nil { Link(destination:url) { Label(title,systemImage:symbol) } }
    }
}
