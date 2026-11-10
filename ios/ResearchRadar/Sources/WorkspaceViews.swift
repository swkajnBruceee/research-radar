import SwiftUI

struct TopicsView: View {
    @EnvironmentObject var store: RadarStore
    var body: some View {
        List(store.snapshot.topics) { topic in
            NavigationLink { TopicDetail(topic:topic) } label: {
                VStack(alignment:.leading,spacing:8) {
                    Text(topic.data.text("name")).font(.headline)
                    Text(topic.data.text("description")).font(.subheadline).foregroundStyle(.secondary)
                    Text("\(store.snapshot.items.filter{$0.topics.contains(topic.id) && store.canDisplayPaper($0)}.count) 条关联内容").font(.caption).foregroundStyle(.secondary)
                }.padding(.vertical,6)
            }
        }.navigationTitle("技术地图")
    }
}
struct TopicDetail: View {
    @EnvironmentObject var store: RadarStore
    let topic:Entry
    var body: some View {
        List {
            Section("带着问题阅读") { ForEach(topic.data.strings("questions"),id:\.self) { Text($0).textSelection(.enabled) } }
            Section("相关方向") { ForEach(topic.data.strings("related"),id:\.self) { id in
                if let linked=store.snapshot.topics.first(where:{$0.id==id}) { NavigationLink(linked.data.text("name")) { TopicDetail(topic:linked) } }
            } }
            Section("按发表时间排列") {
                ForEach(store.snapshot.items.filter{$0.topics.contains(topic.id) && store.canDisplayPaper($0)}.sorted{$0.data.text("published")<$1.data.text("published")}) { item in
                    NavigationLink { PaperDetailView(id:item.id) } label: { PaperRow(item:item) }
                }
            }
            Section { Text("主题关联用于阅读导航，不代表已核实的引用或方法继承关系。").font(.caption).foregroundStyle(.secondary) }
        }.navigationTitle(topic.data.text("short")).navigationBarTitleDisplayMode(.inline)
    }
}
struct IdeasView: View {
    @EnvironmentObject var store: RadarStore
    @State private var filter="全部"
    @State private var search=""
    @State private var add=false
    var ideas:[Entry] { store.snapshot.ideas.filter { (filter=="全部" || $0.data.text("status")==filter) && (search.isEmpty || [$0.title,$0.data.text("hypothesis"),$0.data.text("observation")].joined(separator:" ").localizedCaseInsensitiveContains(search)) } }
    var body: some View {
        List {
            Section { Picker("状态",selection:$filter) { ForEach(["全部","待调研","待验证","实验中","已归档"],id:\.self) { Text($0).tag($0) } } }
            if ideas.isEmpty { ContentUnavailableView("给问题留一个位置",systemImage:"lightbulb",description:Text("从论文精读页发起，或者记录一个新问题。")) }
            ForEach(ideas) { idea in
                NavigationLink { IdeaEditor(existing:idea,source:nil) } label: {
                    VStack(alignment:.leading,spacing:8) {
                        Text(idea.title).font(.headline)
                        Text(idea.data.text("hypothesis").isEmpty ? idea.data.text("observation") : idea.data.text("hypothesis")).lineLimit(3).foregroundStyle(.secondary)
                        Text("\(store.topicName(idea.data.text("topic"))) · \(idea.data.text("status"))").font(.caption).foregroundStyle(.secondary)
                    }.padding(.vertical,6)
                }
            }
        }.navigationTitle("选题池").searchable(text:$search,prompt:"搜索问题、假设和观察")
        .toolbar { ToolbarItem(placement:.topBarTrailing) { Button { add=true } label: { Image(systemName:"plus") }.accessibilityLabel("记录研究问题") } }
        .sheet(isPresented:$add) { NavigationStack { IdeaEditor(existing:nil,source:nil) } }
    }
}
struct IdeaEditor: View {
    @EnvironmentObject var store: RadarStore
    @Environment(\.dismiss) private var dismiss
    let existing:Entry?
    let source:Entry?
    @State private var title:String
    @State private var topic:String
    @State private var status:String
    @State private var observation:String
    @State private var evidence:String
    @State private var hypothesis:String
    @State private var experiment:String
    @State private var itemID:String
    @State private var discard=false
    @State private var delete=false
    @State private var saved=false
    @FocusState private var activeField:String?
    private let localID:String
    init(existing:Entry?,source:Entry?,signal:Record? = nil) {
        self.existing=existing;self.source=source;localID=existing?.id ?? UUID().uuidString
        _title=State(initialValue:existing?.title ?? signal?.text("question") ?? source?.data["analysis"]?.object.text("question") ?? "")
        _topic=State(initialValue:existing?.data.text("topic") ?? source?.topics.first ?? "vla")
        _status=State(initialValue:existing?.data.text("status") ?? "待调研")
        _observation=State(initialValue:existing?.data.text("observation") ?? signal?.text("delta") ?? "")
        let signalEvidence=signal.map { brief in (brief.records("evidence").map { $0.text("label")+" "+$0.text("value")+"。"+$0.text("context") }+[brief.text("source_url")]).joined(separator:"\n") }
        _evidence=State(initialValue:existing?.data.text("evidence") ?? signalEvidence ?? source.map{"起点文献：\($0.data.text("title"))\n\($0.data.text("url"))\n相关工作仍待核查。"} ?? "")
        _hypothesis=State(initialValue:existing?.data.text("hypothesis") ?? signal?.text("hypothesis_suggestion") ?? "")
        _experiment=State(initialValue:existing?.data.text("experiment") ?? signal?.text("experiment_suggestion") ?? "")
        _itemID=State(initialValue:existing?.data.text("item_id") ?? source?.id ?? "")
    }
    var changes:Record { ["title":JSONValue(title),"topic":JSONValue(topic),"status":JSONValue(status),"observation":JSONValue(observation),"evidence":JSONValue(evidence),"hypothesis":JSONValue(hypothesis),"experiment":JSONValue(experiment),"item_id":JSONValue(itemID)] }
    var dirty:Bool { if saved { return false };if let existing { return changes.contains { (existing.data[$0.key]?.string ?? "") != $0.value.string } };return !title.isEmpty || !observation.isEmpty || !hypothesis.isEmpty || !experiment.isEmpty }
    var valid:Bool { !title.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && title.count<=240 && [observation,evidence,hypothesis,experiment].allSatisfy{$0.count<=20000} }
    var body: some View {
        Form {
            Section("问题与方向") {
                TextField("问题标题（最多 240 字符）",text:$title,axis:.vertical).focused($activeField,equals:"title")
                Picker("研究方向",selection:$topic) { ForEach(store.snapshot.topics) { Text($0.data.text("name")).tag($0.id) } }
                Picker("状态",selection:$status) { ForEach(["待调研","待验证","实验中","已归档"],id:\.self) { Text($0).tag($0) } }
                Picker("起点文献",selection:$itemID) { Text("暂不关联").tag(""); ForEach(store.snapshot.items.filter { $0.id==itemID || ($0.isPaper && (store.canDisplayPaper($0) || $0.data.flag("saved") || !$0.data.text("notes").isEmpty)) }) { Text($0.title).tag($0.id) } }
            }
            editor("问题观察",text:$observation,hint:"从哪个现象、失败或矛盾中发现问题？")
            editor("证据与相关工作",text:$evidence,hint:"记录原文链接、章节与已知对照方法。")
            editor("待验证假设",text:$hypothesis,hint:"用可以被实验推翻的句子描述。")
            editor("最小验证实验",text:$experiment,hint:"对照组、数据预算、指标与判断条件。")
            Section { Text("每项最多 20000 字符。离线时保存在本机，连接成功后同步。").font(.caption).foregroundStyle(.secondary) }
            if existing != nil { Section { Button("删除选题",role:.destructive) { delete=true } } }
        }.scrollDismissesKeyboard(.interactively).navigationTitle(existing == nil ? "记录问题" : "编辑选题").navigationBarTitleDisplayMode(.inline).interactiveDismissDisabled(dirty)
        .toolbar {
            ToolbarItemGroup(placement:.keyboard) { Spacer();Button("收起键盘") { activeField=nil } }
            ToolbarItem(placement:.cancellationAction) { Button("取消") { if dirty { discard=true } else { dismiss() } } }
            ToolbarItem(placement:.confirmationAction) { Button("保存") { Task { await store.stageIdea(id:localID,changes:changes);saved=true;dismiss() } }.disabled(!valid) }
        }
        .confirmationDialog("放弃未保存的修改？",isPresented:$discard,titleVisibility:.visible) { Button("放弃修改",role:.destructive) { dismiss() } }
        .confirmationDialog("删除这个选题？",isPresented:$delete,titleVisibility:.visible) { Button("删除选题",role:.destructive) { Task { await store.deleteIdea(localID);saved=true;dismiss() } } }
    }
    func editor(_ label:String,text:Binding<String>,hint:String) -> some View { Section(label) { TextEditor(text:text).focused($activeField,equals:label).frame(minHeight:130).accessibilityLabel(label);Text(hint).font(.caption).foregroundStyle(.secondary) } }
}
struct MoreView: View {
    @EnvironmentObject var store: RadarStore
    var body: some View {
        List {
            Section("我的阅读") {
                NavigationLink { LibraryView(mode:.saved) } label: { Label("我的收藏",systemImage:"bookmark") }
                NavigationLink { ReadingPlanView() } label: { Label("阅读计划",systemImage:"clock") }
            }
            Section("探索与背景") {
                NavigationLink { TopicsView() } label: { Label("技术地图",systemImage:"map") }
                NavigationLink { TechnologyLibraryView() } label: { Label("方法背景",systemImage:"books.vertical") }
                NavigationLink { LibraryView(mode:.industry) } label: { Label("产业观察",systemImage:"globe.asia.australia") }
            }
            Section("内容设置") {
                NavigationLink { SourcesView() } label: { Label("信息源与关注方向",systemImage:"antenna.radiowaves.left.and.right") }
                NavigationLink { IntegrationsView() } label: { Label("产品联动与导出",systemImage:"square.stack.3d.up") }
                NavigationLink { ReadingQueueView() } label: { Label("内容更新与精读",systemImage:"text.badge.clock") }
            }
            Section {
                NavigationLink { ConnectionView() } label: {
                    Label {
                        VStack(alignment:.leading,spacing:4) {
                            Text("研究台连接")
                            Text(store.connected ? "已连接 · "+store.contentSummary : "离线 · "+store.contentSummary).font(.caption).foregroundStyle(.secondary)
                        }.padding(.vertical,3)
                    } icon: { Image(systemName:"network") }
                }.accessibilityIdentifier("research-connection")
                if !store.conflicts.isEmpty {
                    NavigationLink { ConflictsView() } label: { Label("同步冲突（\(store.conflicts.count)）",systemImage:"arrow.triangle.branch") }
                }
                if !store.pending.isEmpty { LabeledContent("本机待同步",value:"\(store.pending.count) 项") }
                if !store.pending.isEmpty { Button("重试同步本机修改") { Task { await store.refresh() } }.disabled(store.busy) }
                if let notice=store.contentNotice { Text(notice).font(.caption).foregroundStyle(.orange) }
            } header: { Text("设备与同步") } footer: {
                Text(store.connected ? "笔记、收藏和阅读进度通过研究台同步。" : "离线时保留本机修改，连接研究台后继续同步。")
            }
            Section("关于") {
                Text("具身研究台 · iPhone 客户端").font(.headline)
                Text("基础快照可直接阅读。最新内容、Notion 和 Zotero 回流需要连接研究台。Mac 上的信息采集只在服务运行期间执行。").font(.subheadline).foregroundStyle(.secondary)
                Text("版本 \(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")（\(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "3")） · iOS 17+").font(.caption).foregroundStyle(.secondary)
            }
        }.navigationTitle("更多").navigationBarTitleDisplayMode(.inline)
    }
}
