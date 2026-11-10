import SwiftUI

struct ReadingCitation: Identifiable { let id = UUID();let text:String }
struct DeepReadingView: View {
    @EnvironmentObject var store: RadarStore
    let id:String
    var initialEvidence:String? = nil
    @State private var value: Record = [:]
    @State private var search = ""
    @State private var waiting = false
    @State private var notice: String?
    @State private var job: Task<Void,Never>?
    @State private var citation: ReadingCitation?
    var document: Record { value["document"]?.object ?? [:] }
    var analysis: Record { value["analysis"]?.object ?? [:] }
    var passages: [Record] { document.records("passages") }
    var results: [Record] { passages.filter { search.isEmpty || ($0.text("section")+" "+$0.text("text")).localizedCaseInsensitiveContains(search) } }
    var status:Record { value["status"]?.object ?? [:] }
    var body: some View {
        List {
            if let evidence=initialEvidence,let row=passages.first(where:{$0.text("id")==evidence}) {
                Section("定位的原文条件") {
                    NavigationLink { EvidenceView(passage:row) { citation=ReadingCitation(text:quoteMarkdown(row)) } } label: {
                        VStack(alignment:.leading,spacing:8) { Text(row.text("location")).font(.caption).foregroundStyle(.tint);Text(row.text("text")).font(.subheadline).lineLimit(6);Text("查看此段全文").font(.caption).foregroundStyle(.tint) }
                    }
                }
            }
            if !analysis.isEmpty { interpretation }
            Section("全文阅读") {
                Text(store.entry(id)?.title ?? "论文").font(.headline)
                Text("原文保留来源语言。按章节或 PDF 页码定位，准备后可在本机离线检索。图表提取文字不完整时，请打开原文核对。").font(.caption).foregroundStyle(.secondary)
                if !document.isEmpty {
                    Text("\(passages.count) 个原文片段 · \(document.text("format").uppercased())").font(.caption)
                    if !document.text("fetched").isEmpty { Text("保存于 \(document.text("fetched"))").font(.caption2).foregroundStyle(.secondary) }
                    SafeExternalLink("查看原始全文",value:document.text("url"),symbol:"arrow.up.right.square")
                }
                Button { launch(model:false) } label: { Label(waiting ? "正在准备，可返回其他页面…" : passages.isEmpty ? "准备全文证据" : "检查全文状态",systemImage:waiting ? "hourglass" : "doc.text.magnifyingglass") }.disabled(waiting || !store.connected)
                if let notice { Text(notice).font(.caption).foregroundStyle(.secondary) }
                else if !status.text("message").isEmpty { Text(status.text("message")).font(.caption).foregroundStyle(status.text("status")=="error" ? .orange : .secondary) }
                if !store.connected { Text("正在使用本机全文缓存。连接研究台后可准备新论文。").font(.caption).foregroundStyle(.secondary) }
            }
            if analysis.isEmpty { interpretation }
            Section("原文检索 · \(results.count) / \(passages.count)") {
                if passages.isEmpty { ContentUnavailableView("全文尚未准备",systemImage:"doc.text",description:Text("连接研究台，点“准备全文证据”。支持论文和已配置的官方发布材料。")) }
                else if results.isEmpty { Text("没有匹配段落，可尝试原文英文关键词。").foregroundStyle(.secondary) }
                ForEach(results,id:\.self) { row in
                    NavigationLink { EvidenceView(passage:row) { citation = ReadingCitation(text:quoteMarkdown(row)) } } label: {
                        VStack(alignment:.leading,spacing:7) {
                            Text(row.text("location")).font(.caption).foregroundStyle(.tint)
                            Text(row.text("text")).font(.subheadline).lineLimit(5)
                        }.padding(.vertical,5)
                    }
                }
            }
        }.navigationTitle("全文证据").navigationBarTitleDisplayMode(.inline)
        .searchable(text:$search,prompt:"检索原文，如 ablation、failure、data")
        .task { value = store.cachedReading(id);await load();if status.text("status")=="running" { launchPoll() } }
        .onDisappear { job?.cancel();job=nil;waiting=false }
        .sheet(item:$citation) { quote in
            if let item = store.entry(id) { NavigationStack { NoteEditor(item:item,appendix:quote.text) } }
        }
    }
    @ViewBuilder var interpretation: some View {
        Section("精读解读与原文依据") {
            if analysis.isEmpty {
                Text("这篇尚未完成全文解读。后台完成后会自动展示，原文可先检索。").font(.caption).foregroundStyle(.secondary)
                if value.flag("model_configured") {
                    Button { launch(model:true) } label: { Label("生成有出处的解读",systemImage:"doc.text.magnifyingglass") }.disabled(waiting || !store.connected)
                }
            }
            if !analysis.isEmpty {
                Text(analysis.text("overview")).textSelection(.enabled)
                let coverage = analysis["coverage"]?.object ?? [:]
                DisclosureGroup("阅读范围与核查说明") {
                    Text(analysis.text("model")).font(.caption).foregroundStyle(.secondary)
                    if let read = coverage["read"], let total = coverage["total"] { Text("提取文字覆盖：\(number(read)) / \(number(total)) 个片段").font(.caption) }
                    Text(analysis.text("notice")).font(.caption).foregroundStyle(.secondary)
                }
                ForEach(Array(analysis.records("findings").enumerated()),id:\.offset) { _,row in claim(row,hypothesis:false) }
                ForEach(Array(analysis.records("hypotheses").enumerated()),id:\.offset) { _,row in claim(row,hypothesis:true) }
            }
        }
    }
    func number(_ value:JSONValue)->String { if case .number(let n)=value.value { return String(Int(n)) };return "—" }
    func claim(_ row:Record,hypothesis:Bool) -> some View {
        DisclosureGroup(row.text("title").isEmpty ? (hypothesis ? "待验证假设" : "查看研究判断") : row.text("title")) {
        VStack(alignment:.leading,spacing:9) {
            Text(hypothesis ? "待验证假设" : ["problem":"研究问题","method":"方法机制","evidence":"实验证据","limitation":"适用边界"][row.text("kind")] ?? "模型解读").font(.caption.bold()).foregroundStyle(.tint)
            Text(row.text("text")).textSelection(.enabled)
            Text("“\(row.text("quote"))”").font(.subheadline).foregroundStyle(.secondary).textSelection(.enabled)
            ForEach(row.strings("evidence_ids"),id:\.self) { evidenceID in
                if let source = passages.first(where:{$0.text("id")==evidenceID}) {
                    NavigationLink("核对原文 · "+source.text("location")) { EvidenceView(passage:source) { citation = ReadingCitation(text:quoteMarkdown(source)) } }
                }
            }
            if hypothesis { Button("加入选题笔记") { citation = ReadingCitation(text:"\n\n## 待验证假设 · 模型建议\n\n"+row.text("text")+"\n\n"+row.strings("evidence_ids").compactMap { key in passages.first{$0.text("id")==key}.map(quoteMarkdown) }.joined(separator:"\n")) } }
        }.padding(.vertical,7)
        }
    }
    func quoteMarkdown(_ row:Record)->String { "\n\n### 原文证据 · \(row.text("location"))\n\n> \(row.text("text"))\n\n[原文出处](\(row.text("url"))) · 证据 \(row.text("id"))\n\n我的理解：\n" }
    func load() async {
        guard store.connected else { return }
        do { value = try await store.readingState(id);notice = nil } catch { notice = error.localizedDescription }
    }
    func launch(model:Bool) {
        job?.cancel();waiting = true
        job = Task {
            defer { waiting=false }
            do {
                _ = try await store.object("api/reading/"+id.addingPercentEncoding(withAllowedCharacters:.urlPathAllowed)!,method:"POST",body:["model":JSONValue(model)])
                try await poll()
            } catch { if !Task.isCancelled { notice=error.localizedDescription } }
        }
    }
    func launchPoll() {
        waiting=true;job=Task { defer { waiting=false };do { try await poll() } catch { if !Task.isCancelled { notice=error.localizedDescription } } }
    }
    func poll() async throws {
        for _ in 0..<120 {
            try Task.checkCancellation()
            value=try await store.readingState(id);notice=nil
            if status.text("status") != "running" { return }
            try await Task.sleep(for:.seconds(2))
        }
        notice="读取仍在 Mac 后台进行。稍后回来检查状态即可。"
    }
}
struct EvidenceView: View {
    let passage:Record
    let save:()->Void
    var body: some View {
        List {
            Section(passage.text("location")) { Text(passage.text("text")).textSelection(.enabled).lineSpacing(6) }
            Section {
                SafeExternalLink("回到原文位置",value:passage.text("url"),symbol:"arrow.up.right.square")
                Button("引用到精读笔记",action:save)
                ShareLink(item:passage.text("text")+"\n\n"+passage.text("url")) { Label("分享这段证据",systemImage:"square.and.arrow.up") }
                Text("证据编号：\(passage.text("id"))").font(.caption).foregroundStyle(.secondary)
            }
        }.navigationTitle("原文证据").navigationBarTitleDisplayMode(.inline)
    }
}
