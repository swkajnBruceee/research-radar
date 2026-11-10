import SwiftUI

struct TechnologyCardView: View {
    let brief: Entry
    var b:Record { brief.data }
    var body: some View {
        VStack(alignment:.leading,spacing:15) {
            HStack {
                Text(b.text("category")).font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text(b.text("update_label")).font(.caption).foregroundStyle(.tint)
            }
            Text(brief.title).font(.title3.bold()).fixedSize(horizontal:false,vertical:true)
            Text(b.text("tagline")).font(.body).lineSpacing(4).fixedSize(horizontal:false,vertical:true)
            VStack(alignment:.leading,spacing:6) {
                Text("为什么重要").font(.caption.bold()).foregroundStyle(.secondary)
                Text(b.text("why")).font(.subheadline).lineSpacing(3)
            }
            VStack(alignment:.leading,spacing:8) {
                HStack {
                    Text(b.text("update_label")).font(.caption.bold())
                    Spacer()
                    Text(b.text("update_date")).font(.caption2).foregroundStyle(.secondary)
                }
                Text(b.text("update")).font(.subheadline).lineSpacing(3).fixedSize(horizontal:false,vertical:true)
            }.padding(13).background(.tint.opacity(0.06),in:RoundedRectangle(cornerRadius:10))
            NavigationLink { TechnologyDetailView(brief:brief) } label: {
                HStack { Text("了解原理与进展").font(.subheadline.weight(.medium));Spacer();Image(systemName:"arrow.right") }.frame(minHeight:44)
            }.buttonStyle(.plain).foregroundStyle(.tint)
        }.padding(.vertical,10)
    }
}
struct TechnologyDetailView: View {
    @EnvironmentObject var store: RadarStore
    let brief:Entry
    var b:Record { brief.data }
    var candidates:[Entry] { b.strings("related_ids").compactMap(store.entry) }
    var body: some View {
        List {
            Section {
                Text(brief.title).font(.title2.bold()).textSelection(.enabled)
                Text(b.text("tagline")).font(.body).lineSpacing(5).textSelection(.enabled)
            }
            Section("为什么重要") { Text(b.text("why")).lineSpacing(4).textSelection(.enabled) }
            Section("它如何工作") {
                ForEach(Array(b.records("mechanism").enumerated()),id:\.offset) { index,step in
                    HStack(alignment:.top,spacing:14) {
                        Text("\(index+1)").font(.title3).foregroundStyle(.tint).frame(minWidth:20)
                        VStack(alignment:.leading,spacing:7) {
                            Text(step.text("title")).font(.headline)
                            Text(step.text("text")).font(.subheadline).foregroundStyle(.secondary).lineSpacing(4)
                        }
                    }.padding(.vertical,7)
                }
            }
            Section("放到具体任务中") { Text(b.text("example")).lineSpacing(5).textSelection(.enabled) }
            Section(b.text("update_label")+" · "+b.text("update_date")) { Text(b.text("update")).lineSpacing(5).textSelection(.enabled) }
            Section("理解它时，还要知道") { Text(b.text("boundary")).font(.subheadline).lineSpacing(4) }
            Section("值得进一步研究的问题") { Text(b.text("question")).lineSpacing(4).textSelection(.enabled) }
            Section("继续深入（可选）") {
                ForEach(Array(b.records("sources").enumerated()),id:\.offset) { _,source in
                    VStack(alignment:.leading,spacing:10) {
                        Text(source.text("role")).font(.caption).foregroundStyle(.tint)
                        Text(source.text("title")).font(.headline)
                        Text(source.text("published")+" · "+source.text("evidence_level")).font(.caption).foregroundStyle(.secondary)
                        if let item=store.entry(source.text("item_id")) {
                            NavigationLink("打开论文与笔记") { PaperDetailView(id:item.id) }
                            NavigationLink("全文证据精读") { DeepReadingView(id:item.id) }
                        }
                        SafeExternalLink("核对原始来源",value:source.text("url"),symbol:"arrow.up.right.square")
                    }.padding(.vertical,10)
                }
            }
            if !candidates.isEmpty {
                Section {
                    DisclosureGroup("更多可能相关的新资料 · \(candidates.count) 篇") {
                        Text("按关键词关联，尚未纳入上面的解读。").font(.caption).foregroundStyle(.secondary)
                        ForEach(candidates) { item in NavigationLink { PaperDetailView(id:item.id) } label: { Text(item.title).font(.subheadline) } }
                    }
                }
            }
            Section {
                Text("核对日期 \(b.text("checked_at"))。导读依据已链接的原始摘要整理，价值判断与例子用于帮助理解；论文结论仍需结合全文与实验核查。").font(.caption).foregroundStyle(.secondary)
            }
        }.navigationTitle("技术导读").navigationBarTitleDisplayMode(.inline)
    }
}
struct ReadingPlanView: View {
    @AppStorage("radar.plan.day") private var planDay = ""
    @AppStorage("radar.plan.step") private var planStep = 0
    var body: some View {
        List {
            Section { Text("先看懂技术，再挑感兴趣的内容深入。需要安排时间时，可以使用这份可选计划。").foregroundStyle(.secondary) }
            Section("今天的 30 分钟") {
                ForEach(Array(["浏览重要技术 · 5 分钟","精读一个方法与实验 · 20 分钟","记下一个问题 · 5 分钟"].enumerated()),id:\.offset) { index,label in
                    Button { planStep = planStep > index ? index : index+1 } label: {
                        Label(label,systemImage:planStep > index ? "checkmark.circle.fill" : "circle").foregroundStyle(.primary).padding(.vertical,4)
                    }.accessibilityValue(planStep > index ? "已完成" : "未完成")
                }
            }
        }.navigationTitle("阅读计划").navigationBarTitleDisplayMode(.inline)
        .task { let day = Date().formatted(.iso8601.year().month().day().dateSeparator(.dash));if planDay != day { planDay=day;planStep=0 } }
    }
}
