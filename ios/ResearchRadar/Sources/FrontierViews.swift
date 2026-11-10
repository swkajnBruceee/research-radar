import SwiftUI

struct TodayView: View {
    @EnvironmentObject var store: RadarStore
    @SceneStorage("frontier.view") private var mode="reviewed"
    @SceneStorage("frontier.days") private var days=0
    @SceneStorage("frontier.topic") private var topic="all"
    @SceneStorage("frontier.unread") private var unread=false
    @State private var search=""
    @State private var searching=false
    @State private var showingFilters=false
    @FocusState private var searchFocused:Bool
    @Environment(\.dynamicTypeSize) private var typeSize
    var rows:[Entry] {
        let result=store.signals.filter { FrontierFilter.matches($0.data,mode:mode,days:days,topic:topic,focus:store.snapshot.settings.strings("focus"),unread:unread,search:search) }
        return ["reviewed","all"].contains(mode) ? result.sorted { FrontierPriority.precedes($0.data,$1.data) } : result.sorted { $0.data.text("published") > $1.data.text("published") }
    }
    var showsCurrentScope:Bool { ["reviewed","all"].contains(mode) }
    var highlights:[Entry] { FrontierPriority.featured(rows.map(\.data)).map { Entry(data:$0) } }
    var filterCount:Int { (showsCurrentScope && days>0 ? 1 : 0)+(topic != "all" ? 1 : 0)+(showsCurrentScope && unread ? 1 : 0) }
    var scopeSummary:String {
        var parts=[String]()
        if showsCurrentScope && days>0 { parts.append("近 \(days) 天") }
        if topic != "all" { parts.append(topic=="focus" ? "我的关注" : store.topicName(topic)) }
        if showsCurrentScope && unread { parts.append("未处理") }
        if !search.isEmpty { parts.append("搜索结果") }
        parts.append("\(rows.count) 项")
        return parts.joined(separator:" · ")
    }
    var body: some View {
        List {
            if rows.isEmpty {
                Section {
                    ContentUnavailableView(mode=="seen" ? "了解过的方法会留在这里" : mode=="later" ? "稍后读里还没有内容" : "当前范围没有进展",systemImage:"tray",description:Text(mode=="seen" ? "阅读手记后标记“已了解”，下次可从这里回看证据和实验。" : "可以显示已处理内容，或调整时间与方向。"))
                    Button("显示全部进展") { mode="reviewed";resetFilters();search="" }
                }
            }
            if mode=="reviewed" && !rows.isEmpty {
                Section("先看这些") {
                    if highlights.isEmpty { Text("当前范围没有新的重点。可以回看已了解，或浏览全部更新。").foregroundStyle(.secondary) }
                    ForEach(highlights) { signal in FrontierRow(signal:signal,compact:true).swipeActions(edge:.trailing,allowsFullSwipe:false) { Button { Task { await store.stageSignal(signal.id,status:"later") } } label: { Label("稍后读",systemImage:"bookmark") }.tint(.blue) } }
                }
                Section("继续浏览") {
                    ForEach(Array(rows.filter { row in !highlights.contains(where:{$0.id==row.id}) }.prefix(4))) { signal in
                        NavigationLink { FrontierDetailView(id:signal.id) } label: {
                            VStack(alignment:.leading,spacing:6) { Text(signal.title).font(.subheadline.weight(.medium));Text(signal.data.text("published")).font(.caption).foregroundStyle(.secondary) }.padding(.vertical,5)
                        }
                    }
                    Button("查看全部 \(rows.count) 项进展") { mode="all" }
                }
            } else { ForEach(rows) { signal in
                Section {
                    FrontierRow(signal:signal)
                }.swipeActions(edge:.trailing,allowsFullSwipe:false) {
                    Button { Task { await store.stageSignal(signal.id,status:"later") } } label: { Label("稍后读",systemImage:"bookmark") }.tint(.blue)
                    Button { Task { await store.stageSignal(signal.id,status:"dismissed") } } label: { Label("略过",systemImage:"minus.circle") }.tint(.gray)
                }
            } }
        }.contentMargins(.top,8,for:.scrollContent)
        .navigationTitle("前沿手记").navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge:.top,spacing:0) { feedControls }
        .refreshable { if store.baseURL != nil { await store.refresh(silent:true) } }
        .toolbar {
            ToolbarItem(placement:.topBarTrailing) {
                Button {
                    withAnimation { searching.toggle() }
                    searchFocused=searching
                    if !searching { search="" }
                } label: { Image(systemName:searching ? "xmark" : "magnifyingglass") }
                .accessibilityLabel(searching ? "关闭搜索" : "搜索前沿方法")
                .accessibilityIdentifier("frontier-search")
            }
            ToolbarItem(placement:.topBarTrailing) {
                Menu {
                    NavigationLink { MethodComparisonView(initialID:nil) } label: { Label("方法对照",systemImage:"rectangle.split.2x1") }.disabled(store.signals.count<2)
                    if store.baseURL == nil {
                        NavigationLink { ConnectionView() } label: { Label("连接研究台",systemImage:"network") }
                    } else {
                        Button { Task { await store.refresh(silent:true) } } label: { Label(store.busy ? "正在更新…" : "更新资料",systemImage:"arrow.clockwise") }.disabled(store.busy)
                    }
                } label: { Image(systemName:"ellipsis") }.accessibilityLabel("更多阅读操作")
            }
        }
        .sheet(isPresented:$showingFilters) { filterSheet }
    }
    var feedControls:some View {
        VStack(alignment:.leading,spacing:4) {
            if searching {
                HStack(spacing:8) {
                    Image(systemName:"magnifyingglass").foregroundStyle(.secondary)
                    TextField("搜索方法、论文或问题",text:$search).focused($searchFocused).submitLabel(.search).autocorrectionDisabled()
                        .onSubmit { searchFocused=false }
                    if !search.isEmpty { Button { search="" } label: { Image(systemName:"xmark.circle.fill").foregroundStyle(.secondary) }.accessibilityLabel("清除搜索").frame(minWidth:44,minHeight:44) }
                }.padding(.horizontal,12).frame(minHeight:44).background(.quaternary,in:RoundedRectangle(cornerRadius:12))
            }
            HStack(spacing:10) {
                if typeSize.isAccessibilitySize {
                    Menu { modeOptions } label: { Label(modeName,systemImage:"chevron.down").frame(minHeight:44) }
                    Spacer()
                } else {
                    Picker("阅读分组",selection:$mode) {
                        Text("重点").tag("reviewed");Text("全部").tag("all");Text("稍后").tag("later");Text("已了解").tag("seen");Text("略过").tag("dismissed")
                    }.pickerStyle(.segmented).frame(minHeight:44)
                }
                Button { searchFocused=false;showingFilters=true } label: {
                    HStack(spacing:3) {
                        Image(systemName:filterCount==0 ? "line.3.horizontal.decrease" : "line.3.horizontal.decrease.circle.fill")
                        if filterCount>0 { Text("\(filterCount)").font(.caption.monospacedDigit()) }
                    }.frame(minWidth:44,minHeight:44)
                }.accessibilityLabel(filterCount==0 ? "筛选进展" : "筛选进展，已启用 \(filterCount) 项")
                .accessibilityIdentifier("frontier-filter")
            }
            HStack(alignment:.firstTextBaseline) {
                Text(showsCurrentScope ? "重要优先 · "+scopeSummary : scopeSummary)
                Spacer(minLength:8)
                if store.busy { Text("正在更新…") }
                else if !store.connected { Text("离线快照") }
                else if let latest=store.snapshot.frontier_meta?.text("reviewed_at"),!latest.isEmpty { Text("精读至 "+latest) }
                else { Text("离线快照") }
            }.font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true)
        }.padding(.horizontal,20).padding(.top,4).padding(.bottom,10).background(.bar)
    }
    var modeName:String { ["reviewed":"重点进展","all":"全部更新","later":"稍后读","seen":"已了解","dismissed":"已略过"][mode] ?? "重点进展" }
    var modeOptions:some View {
        Picker("阅读分组",selection:$mode) {
            Text("重点进展").tag("reviewed");Text("全部更新").tag("all");Text("稍后读").tag("later");Text("已了解").tag("seen");Text("已略过").tag("dismissed")
        }
    }
    var filterSheet:some View {
        NavigationStack {
            Form {
                if showsCurrentScope {
                    Section("发布时间") {
                        Picker("时间范围",selection:$days) { Text("全部时间").tag(0);Text("近 7 天").tag(7);Text("近 30 天").tag(30) }
                    }
                }
                Section("研究方向") {
                    Picker("方向",selection:$topic) {
                        Text("全部方向").tag("all");Text("我的关注").tag("focus")
                        ForEach(store.snapshot.topics) { Text($0.data.text("short")).tag($0.id) }
                    }
                }
                if showsCurrentScope {
                    Section("阅读状态") { Toggle("只看未处理",isOn:$unread) }
                }
                Section { Button("重置筛选") { resetFilters() }.disabled(filterCount==0) }
            }.navigationTitle("筛选进展").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement:.confirmationAction) { Button("完成") { showingFilters=false } } }
        }.presentationDetents([.medium,.large]).presentationDragIndicator(.visible)
    }
    func resetFilters() { days=0;topic="all";unread=false }
}
struct FrontierRow: View {
    @EnvironmentObject var store: RadarStore
    let signal:Entry
    var compact=false
    var b:Record { signal.data }
    var body: some View {
        VStack(alignment:.leading,spacing:12) {
            if !compact && FrontierPriority.rank(b)>0 {
                VStack(alignment:.leading,spacing:5) {
                    Label(FrontierPriority.rank(b)==2 ? "优先看" : "值得跟进",systemImage:"sparkle").font(.caption.weight(.semibold)).foregroundStyle(.tint)
                    Text((b["attention"]?.object ?? [:]).text("reason")).font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
                }
            }
            HStack {
                Text(b.text("published"));Text(b.text("change_type"));Spacer();Text(FrontierDetailView.statusName(b.text("status")))
            }.font(.caption2).foregroundStyle(.secondary)
            NavigationLink { FrontierDetailView(id:signal.id) } label: {
                VStack(alignment:.leading,spacing:9) {
                    Text(signal.title).font(compact ? .headline:.title3.bold()).fixedSize(horizontal:false,vertical:true)
                    Text((b["attention"]?.object ?? [:]).text("summary").isEmpty ? b.text("delta") : (b["attention"]?.object ?? [:]).text("summary")).font(.subheadline).foregroundStyle(.secondary).lineSpacing(3).lineLimit(compact ? 2:nil)
                }
            }
            if let evidence=b.records("evidence").first {
                Text(evidence.text("value")+"  ·  "+evidence.text("label")).font(.subheadline.weight(.medium)).foregroundStyle(.tint)
            }
            if !compact { Button { Task { await store.stageSignal(signal.id,status:b.text("status")=="later" ? "new" : "later") } } label: {
                Label(b.text("status")=="later" ? "移出稍后读" : "稍后读",systemImage:"bookmark").frame(minHeight:44)
            }.buttonStyle(.borderless) }
        }.padding(.vertical,7)
    }
}
struct FrontierDetailView: View {
    @EnvironmentObject var store: RadarStore
    let id:String
    @State private var editingExperiment=false
    var signal:Entry? { store.signals.first{$0.id==id} }
    var linkedIdeas:[Entry] { store.snapshot.ideas.filter{$0.data.text("item_id")==id}.sorted{$0.data.text("updated")>$1.data.text("updated")} }
    static func statusName(_ value:String)->String { ["new":"未处理","seen":"已了解","later":"稍后读","dismissed":"已略过"][value] ?? "未处理" }
    var body: some View {
        Group {
            if let signal {
                List {
                    Section {
                        Text(signal.data.text("published")+" · "+signal.data.text("change_type")+" · "+signal.data.text("source_name")).font(.caption).foregroundStyle(.secondary)
                        Text(signal.title).font(.title2.bold()).textSelection(.enabled)
                        if !signal.data.text("paper_title").isEmpty { Text(signal.data.text("paper_title")).font(.caption).foregroundStyle(.secondary).textSelection(.enabled) }
                    }
                    if signal.data.flag("reviewed") { reviewed(signal.data) }
                    else {
                        Section("新资料，尚未解读") {
                            Text("目前保留来源摘要或发布说明。核对方法、对照和实验后，再形成增量解读。").font(.caption).foregroundStyle(.secondary)
                            Text(signal.data.text("abstract")).lineSpacing(5).textSelection(.enabled)
                        }
                    }
                    Section("继续深入") {
                        NavigationLink("与其他方法对照") { MethodComparisonView(initialID:id) }
                        if store.entry(id) != nil {
                            NavigationLink("论文与研究笔记") { PaperDetailView(id:id) }
                            if signal.data.text("kind")=="paper" {
                                NavigationLink("全文证据") { DeepReadingView(id:id) }
                            }
                        }
                        SafeExternalLink("原始来源",value:signal.data.text("source_url"),symbol:"arrow.up.right.square")
                        SafeExternalLink("作者代码",value:signal.data.text("code_url"),symbol:"chevron.left.forwardslash.chevron.right")
                    }
                    Section("处理这条进展") {
                        LabeledContent("状态",value:Self.statusName(signal.data.text("status")))
                        Button("已了解") { update("seen") }
                        Button(signal.data.text("status")=="later" ? "移出稍后读" : "稍后读") { update(signal.data.text("status")=="later" ? "new" : "later") }
                        Button("略过") { update("dismissed") }
                        if signal.data.text("status") != "new" { Button("恢复未处理") { update("new") } }
                        if store.pending.contains(where:{$0.kind=="frontier" && $0.target==id}) { Text("处理状态已保存在本机，待连接后同步。").font(.caption).foregroundStyle(.secondary) }
                    }
                }
            } else { ContentUnavailableView("这条资料尚未缓存",systemImage:"wifi.slash") }
        }.navigationTitle("方法手记").navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented:$editingExperiment) { if let signal,let item=store.entry(id) { NavigationStack { IdeaEditor(existing:nil,source:item,signal:signal.data) } } }
    }
    @ViewBuilder func reviewed(_ b:Record)->some View {
        Section("这次新在哪里") { Text(b.text("delta")).font(.body).lineSpacing(5).textSelection(.enabled) }
        if !b.records("related_sources").isEmpty {
            Section("同一研究的其他发布") {
                ForEach(Array(b.records("related_sources").enumerated()),id:\.offset) { _,source in NavigationLink(source.text("title")) { FrontierDetailView(id:source.text("id")) } }
            }
        }

        Section("目前证据 · 作者报告") {
            Text(b.text("evidence_level")).font(.caption).foregroundStyle(.secondary)
            ForEach(Array(b.records("evidence").enumerated()),id:\.offset) { _,evidence in
                VStack(alignment:.leading,spacing:8) {
                    Text(evidence.text("value")).font(.title3.weight(.semibold)).foregroundStyle(.tint)
                    Text(evidence.text("label")).font(.subheadline.weight(.medium))
                    Text(evidence.text("context")).font(.caption).foregroundStyle(.secondary).lineSpacing(3)
                }.padding(.vertical,7)
            }
            Text(b.text("caveat")).font(.caption).foregroundStyle(.secondary).lineSpacing(4)
        }
        Section("值得试的问题") {
            Text(b.text("question")).font(.headline);Text(b.text("relevance")).lineSpacing(4)
            ForEach(linkedIdeas) { idea in
                NavigationLink { IdeaEditor(existing:idea,source:nil) } label: {
                    VStack(alignment:.leading,spacing:6) {
                        Text(idea.data.text("status")+" · 继续完善实验").font(.caption).foregroundStyle(.secondary)
                        Text(idea.title).font(.headline)
                    }
                }
            }
            if store.entry(id) != nil { Button(linkedIdeas.isEmpty ? "起草验证实验" : "另起草一个实验") { editingExperiment=true } }
            if b.text("status")=="seen" { Label("已了解",systemImage:"checkmark.circle").foregroundStyle(.secondary) }
            else { Button("已了解，留待回看") { update("seen") } }
        }
        Section {
            DisclosureGroup("怎样用于我的研究") {
                let reuse=b["reuse"]?.object ?? [:]
                Text(reuse.text("notice")).font(.caption).foregroundStyle(.secondary)
                Text("开始前需要什么").font(.headline)
                ForEach(Array(reuse.records("requirements").enumerated()),id:\.offset) { _,row in
                    VStack(alignment:.leading,spacing:6) {
                        Text(row.text("label")+" · "+(row.text("status")=="known" ? "原文条件":"待核对")).font(.subheadline.weight(.semibold))
                        Text(row.text("text")).font(.subheadline)
                        if let evidence=row.strings("evidence_ids").first { NavigationLink("定位这项条件") { DeepReadingView(id:id,initialEvidence:evidence) } }
                    }.padding(.vertical,5)
                }
                Text("需要改变的步骤").font(.headline)
                ForEach(Array(reuse.records("changes").enumerated()),id:\.offset) { _,row in
                    DisclosureGroup(row.text("title")) { Text(row.text("text")).textSelection(.enabled) }
                }
                Text("采纳前先核对").font(.headline)
                ForEach(Array(reuse.records("checks").enumerated()),id:\.offset) { _,row in
                    DisclosureGroup(row.text("title")) { Text(row.text("text")).textSelection(.enabled) }
                }
                NavigationLink("核对精读报告与出处") { DeepReadingView(id:id) }
                if !reuse.text("experiment").isEmpty { Text("最小验证实验建议").font(.headline);Text(reuse.text("experiment")).font(.subheadline).textSelection(.enabled) }
                ForEach(Array(reuse.records("resources").enumerated()),id:\.offset) { _,resource in SafeExternalLink("原文资源（未运行验证）",value:resource.text("url"),symbol:"arrow.up.right") }
                SafeExternalLink("作者代码",value:b.text("code_url"),symbol:"chevron.left.forwardslash.chevron.right")
                Text("未提供代码链接或未披露条件，仍需回原文核查。验证实验需由你选择起草。").font(.caption).foregroundStyle(.secondary)
            }
        }
        Section {
            DisclosureGroup("方法改动与步骤") {
                Text(b.text("before"));Text(b.text("after"))
                ForEach(Array(b.records("mechanism").enumerated()),id:\.offset) { index,step in
                    VStack(alignment:.leading,spacing:6) { Text("\(index+1). "+step.text("title")).font(.headline);Text(step.text("text")).font(.subheadline).foregroundStyle(.secondary) }.padding(.vertical,6)
                }

            }
            Text("解读核对 \(b.text("checked_at"))。研究关联属于阅读判断，实验结论归作者。").font(.caption).foregroundStyle(.secondary)
        }
    }
    func update(_ status:String) { Task { await store.stageSignal(id,status:status) } }
}

struct MethodComparisonView: View {
    @EnvironmentObject var store:RadarStore
    @State private var selected:Set<String>
    @State private var choosing=false
    init(initialID:String?) { _selected=State(initialValue:initialID.map{Set([$0])} ?? []) }
    var rows:[Entry] { store.signals.filter{selected.contains($0.id)} }
    var body:some View {
        List {
            Section("对照方法") {
                Text("比较技术选择，不做性能排名。不同任务、数据和指标不直接横比；同主题不代表方法继承。").font(.caption).foregroundStyle(.secondary)
                Button("选择两至三项 · 已选 \(selected.count) 项") { choosing=true }
                ForEach(rows) { signal in Text(signal.title).font(.subheadline) }
            }
            if rows.count>=2 {
                compare("具体改动",key:"delta")
                compare("原先做法",key:"before")
                Section("数据、硬件与接口") {
                    ForEach(rows) { signal in
                        VStack(alignment:.leading,spacing:8) {
                            Text(signal.title).font(.headline)
                            ForEach(Array((signal.data["reuse"]?.object ?? [:]).records("requirements").enumerated()),id:\.offset) { _,condition in Text(condition.text("label")+" · "+condition.text("text")).font(.subheadline) }
                        }.padding(.vertical,7)
                    }
                }
                Section("作者证据与评测条件") {
                    ForEach(rows) { signal in
                        VStack(alignment:.leading,spacing:8) {
                            Text(signal.title).font(.headline)
                            ForEach(Array(signal.data.records("evidence").enumerated()),id:\.offset) { _,row in
                                Text(row.text("value")).font(.subheadline.bold());Text(row.text("context")).font(.subheadline)
                            }
                            NavigationLink("核对全文证据") { DeepReadingView(id:signal.id) }
                        }.padding(.vertical,8)
                    }
                }
                compare("适用边界",key:"caveat")
                compare("研究用途",key:"relevance")
            } else { Section { Text("再选一篇，逐项查看改动、证据条件与边界。").foregroundStyle(.secondary) } }
        }.navigationTitle("方法对照").navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented:$choosing) {
            NavigationStack {
                List(store.signals) { signal in
                    Button {
                        if selected.contains(signal.id) { selected.remove(signal.id) }
                        else if selected.count<3 { selected.insert(signal.id) }
                    } label: {
                        HStack { Text(signal.title).foregroundStyle(.primary);Spacer();Image(systemName:selected.contains(signal.id) ? "checkmark.circle.fill":"circle") }.frame(minHeight:44)
                    }.accessibilityAddTraits(selected.contains(signal.id) ? .isSelected:[]).disabled(selected.count>=3 && !selected.contains(signal.id))
                }.navigationTitle("选择对照方法").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement:.confirmationAction) { Button("完成") { choosing=false } } }
            }
        }
        .onChange(of:store.signals.map(\.id)) { _,ids in selected.formIntersection(Set(ids)) }
    }
    func compare(_ title:String,key:String)->some View {
        Section(title) { ForEach(rows) { signal in
            VStack(alignment:.leading,spacing:8) { Text(signal.title).font(.headline);Text(signal.data.text(key)).textSelection(.enabled) }.padding(.vertical,7)
        } }
    }
}
