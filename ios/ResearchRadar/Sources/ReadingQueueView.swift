import SwiftUI

struct ReadingQueueEntry: View {
    @EnvironmentObject var store:RadarStore
    let itemID:String
    @State private var saving=false
    @State private var notice:String?
    var task:Record? { store.snapshot.reading_queue?.records("tasks").first { $0.text("item_id")==itemID && !$0.flag("stale") } }
    var body: some View {
        if let task {
            NavigationLink { ReadingQueueView(initialFilter:["completed","cancelled"].contains(task.text("status")) ? "all" : "active") } label: { Label("精读任务 · "+task.text("status_label"),systemImage:"text.badge.clock") }
        } else {
            Button {
                saving=true
                Task {
                    defer { saving=false }
                    do { try await store.enqueueReading(itemID);notice=nil }
                    catch { notice=error.localizedDescription }
                }
            } label: { Label(saving ? "正在加入…" : "交给精读",systemImage:"text.badge.plus") }.disabled(saving || !store.connected)
            if !store.connected { Text("连接研究台后可加入精读队列。").font(.caption).foregroundStyle(.secondary) }
        }
        if let notice { Text(notice).font(.caption).foregroundStyle(.orange) }
    }
}

struct ReadingQueueView: View {
    @EnvironmentObject var store:RadarStore
    @Environment(\.scenePhase) private var phase
    @State private var filter="active"
    @State private var saving=false
    @State private var notice:String?
    init(initialFilter:String="active") { _filter=State(initialValue:initialFilter) }
    var queue:Record { store.snapshot.reading_queue ?? [:] }
    var tasks:[Entry] {
        queue.records("tasks").filter { row in
            filter=="all" || (filter=="review" ? row.text("status")=="needs_review" : !["completed","cancelled"].contains(row.text("status")))
        }.map { Entry(data:$0) }
    }
    var body: some View {
        List {
            Section {
                Text("论文自动进入后台；完成精读与技术解读后才在前台展示。").font(.subheadline)
                Text(queue.text("notice").isEmpty ? "从前沿详情或全文证据页加入任务。" : queue.text("notice")).font(.caption).foregroundStyle(.secondary)
                if !store.connected { Text("离线 · 查看已缓存的队列，连接后可操作。").font(.caption).foregroundStyle(.secondary) }
                if let notice { Text(notice).font(.caption).foregroundStyle(.orange) }
                Picker("任务范围",selection:$filter) { Text("进行中").tag("active");Text("待核查").tag("review");Text("全部").tag("all") }.pickerStyle(.segmented)
            }
            if tasks.isEmpty { ContentUnavailableView("这个范围暂无任务",systemImage:"text.badge.clock",description:Text("从一篇论文开始，选择“交给精读”。")) }
            ForEach(tasks) { task in
                Section {
                    Text(task.data.text("status_label")).font(.caption.bold()).foregroundStyle(.tint)
                    Text(task.title).font(.headline).textSelection(.enabled)
                    if let priority=task.data["priority"]?.object { Text(priority.text("reason")).font(.caption).foregroundStyle(.secondary) }
                    Text(task.data.text("message")).font(.subheadline)
                    if task.data.flag("stale") {
                        Text("来源已有新版本，旧任务保留作历史记录。").font(.caption).foregroundStyle(.orange)
                        Button("为当前版本新建任务") { change { try await store.enqueueReading(task.data.text("item_id")) } }.disabled(saving || !store.connected)
                        if !["completed","cancelled"].contains(task.data.text("status")) { actionButton("取消旧版任务",task.data,"cancel") }
                    } else {
                        if !task.data.text("document_id").isEmpty {
                            NavigationLink(["needs_review","completed"].contains(task.data.text("status")) ? "查看解读与证据" : "查看原文证据") { DeepReadingView(id:task.data.text("item_id")) }
                        }
                        actions(task.data)
                    }
                    DisclosureGroup("执行记录") {
                        SafeExternalLink("任务来源版本",value:task.data.text("source_url"),symbol:"arrow.up.right.square")
                        ForEach(Array(task.data.records("events").enumerated()),id:\.offset) { _,event in
                            VStack(alignment:.leading,spacing:5) { Text(event.text("message"));Text(event.text("at")).font(.caption2).foregroundStyle(.secondary) }.padding(.vertical,4)
                        }
                    }
                }.buttonStyle(.borderless)
            }
        }.navigationTitle("后台处理").navigationBarTitleDisplayMode(.inline)
        .refreshable { await load() }
        .toolbar { Button("刷新") { Task { await load() } }.disabled(!store.connected || saving) }
        .task {
            while !Task.isCancelled {
                if phase == .active && store.connected && !saving { await load() }
                do { try await Task.sleep(for:.seconds(4)) } catch { return }
            }
        }
    }
    @ViewBuilder func actions(_ task:Record)->some View {
        let status=task.text("status")
        if status=="needs_review" { actionButton("我已核查",task,"complete") }
        if status=="completed" { actionButton("恢复待核查",task,"reopen") }
        if ["failed","cancelled"].contains(status) { actionButton("重新排队",task,"retry") }
        if !["completed","cancelled"].contains(status) { actionButton("取消任务",task,"cancel") }
    }
    func actionButton(_ label:String,_ task:Record,_ action:String)->some View {
        Button(label) { change { try await store.readingQueueAction(task,action:action) } }.disabled(saving || !store.connected)
    }
    func change(_ work:@escaping () async throws ->Void) {
        saving=true
        Task {
            defer { saving=false }
            do { try await work();notice=nil }
            catch { notice=error.localizedDescription;try? await store.refreshReadingQueue() }
        }
    }
    func load() async {
        guard store.connected else { return }
        do { try await store.refreshReadingQueue();notice=nil } catch { notice=error.localizedDescription }
    }
}
