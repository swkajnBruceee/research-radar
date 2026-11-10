import SwiftUI

@main struct ResearchRadarApp: App {
    @StateObject private var store = RadarStore()
    var body: some Scene {
        WindowGroup { RadarTabs().environmentObject(store).tint(Color("AccentColor")) }
    }
}
struct RadarTabs: View {
    @EnvironmentObject var store: RadarStore
    @Environment(\.scenePhase) private var phase
    @State private var settings = false
    @AppStorage("radar.onboarded") private var onboarded = false
    var body: some View {
        TabView {
            NavigationStack { TodayView() }.tabItem { Label("前沿",systemImage:"sparkles") }
            NavigationStack { LibraryView(mode:.papers) }.tabItem { Label("论文",systemImage:"books.vertical") }
            NavigationStack { IdeasView() }.tabItem { Label("选题",systemImage:"lightbulb") }
            NavigationStack { MoreView() }.tabItem { Label("更多",systemImage:"ellipsis.circle") }
        }
        .sheet(isPresented:$settings,onDismiss:{ onboarded = true; store.invitation = nil }) { NavigationStack { ConnectionView(invitation:store.invitation,firstRun:!onboarded) } }
        .alert("研究台",isPresented:Binding(get:{store.message != nil},set:{if !$0 { store.message = nil }})) { Button("知道了") { store.message = nil } } message: { Text(store.message ?? "") }
        .task { store.setForeground(true) }
        .onChange(of:phase) { _,value in store.setForeground(value == .active) }
        .onOpenURL { url in do { store.invitation = try ConnectionInvitation.parse(url); settings = true } catch { store.message = error.localizedDescription } }
    }
}
