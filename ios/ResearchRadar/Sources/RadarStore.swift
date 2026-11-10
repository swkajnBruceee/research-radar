import SwiftUI
import Security
import CryptoKit
import Network

@MainActor final class RadarStore: ObservableObject {
    @Published var snapshot: RadarSnapshot
    @Published var pending: [PendingChange] = []
    @Published var connected = false
    @Published var busy = false
    @Published var configuring = false
    @Published var message: String?
    @Published var lastConnected: Date?
    @Published var serverAddress: String
    @Published var serverSyncRunning = false
    @Published var connectionNotice: String?
    @Published var invitation: ConnectionInvitation?
    @Published var contentNotice: String?
    @Published var contentCacheManifest: Record = [:]
    @Published var contentReceipt: Record = [:]
    private let contentDeviceID:String = {
        if let saved=UserDefaults.standard.string(forKey:"radar.content-device"),UUID(uuidString:saved) != nil { return saved }
        let value=UUID().uuidString;UserDefaults.standard.set(value,forKey:"radar.content-device");return value
    }()
    private let monitor = NWPathMonitor()
    private var reconnectTask: Task<Void,Never>?
    private var foreground = false
    private let session: URLSession
    private let root: URL
    private var confirmed: RadarSnapshot
    private let bundledTechnologies: [Entry]
    private let bundledSignals: [Entry]
    private let publicReadings:Record
    var signals: [Entry] {
        let rows = snapshot.frontier_meta?.flag("publication_required") == true ? (snapshot.signals ?? []) : bundledSignals
        return rows.filter { $0.data.flag("publication_ready") }
    }
    func canDisplayPaper(_ item:Entry)->Bool { !item.isPaper || item.data.flag("curated") || signals.contains { $0.id==item.id } }
    var technologies: [Entry] { snapshot.technology_briefs ?? bundledTechnologies }
    var offlineReadingCount:Int { signals.filter { !cachedReading($0.id).isEmpty }.count }
    var contentSummary:String { "\(offlineReadingCount) / \(signals.count) 项精读可离线阅读" }
    private var generation = UUID()
    var conflicts: [PendingChange] { pending.filter { $0.conflict != nil } }
    var notion: Record { snapshot.integrations["notion"]?.object ?? [:] }
    var baseURL: URL? { try? ConnectionAddress.normalized(serverAddress) }
    var scope: String { SHA256.hash(data:Data((baseURL?.absoluteString ?? "unconfigured").utf8)).map { String(format:"%02x",$0) }.joined() }
    var partition: URL { root.appendingPathComponent(scope, isDirectory: true) }
    init() {
        serverAddress = UserDefaults.standard.string(forKey: "radar.server") ?? ""
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10; config.timeoutIntervalForResource = 35
        session = URLSession(configuration: config)
        root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("ResearchRadar", isDirectory: true)
        let raw = (try? Data(contentsOf: Bundle.main.url(forResource: "ReadingShelf", withExtension: "json")!)) ?? Data("{}".utf8)
        let publicSeed=(try? JSONDecoder().decode(Record.self,from:raw)) ?? [:]
        publicReadings=publicSeed["public_readings"]?.object ?? [:]
        let seed=RadarSnapshot(raw:publicSeed)
        bundledTechnologies = seed.technology_briefs ?? []
        bundledSignals = seed.signals ?? []
        snapshot = seed; confirmed = seed
        restore(fallback: seed)
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor [weak self] in
                guard let self else { return }
                if path.status == .satisfied { self.beginReconnect() }
                else { self.connected = false; self.connectionNotice = "网络不可用，正在使用本机缓存。" }
            }
        }
        monitor.start(queue:DispatchQueue(label:"ResearchRadar.network"))
    }
    func setForeground(_ active: Bool) {
        foreground = active
        if active { beginReconnect() } else { reconnectTask?.cancel(); reconnectTask = nil }
    }
    private func beginReconnect() {
        guard foreground, !configuring, baseURL != nil, reconnectTask == nil else { return }
        reconnectTask = Task { [weak self] in
            defer { self?.reconnectTask = nil }
            for seconds in [0,3,8,20,45] {
                if seconds > 0 { do { try await Task.sleep(for:.seconds(seconds)) } catch { return } }
                guard let self, !Task.isCancelled, self.foreground else { return }
                await self.refresh(silent:true)
                if self.connected { return }
            }
        }
    }
    func restore(fallback: RadarSnapshot) {
        if let data = try? Data(contentsOf: partition.appendingPathComponent("offline.json")), let saved = try? JSONDecoder().decode(OfflineState.self, from: data) {
            confirmed = saved.snapshot; pending = saved.pending; lastConnected = saved.lastConnected
        } else { confirmed = fallback; pending = []; lastConnected = nil }
        if baseURL == nil { confirmed.refreshBundledContent(from:fallback) }
        applyPending()
        contentCacheManifest=(try? Data(contentsOf:partition.appendingPathComponent("Reading/manifest.json"))).flatMap { try? JSONDecoder().decode(Record.self,from:$0) } ?? [:]
        contentReceipt=(try? Data(contentsOf:partition.appendingPathComponent("Reading/receipt.json"))).flatMap { try? JSONDecoder().decode(Record.self,from:$0) } ?? [:]
        contentNotice=nil
    }
    func persist() {
        do {
            try FileManager.default.createDirectory(at: partition, withIntermediateDirectories: true)
            let data = try JSONEncoder().encode(OfflineState(snapshot: confirmed, pending: pending, lastConnected: lastConnected))
            try data.write(to: partition.appendingPathComponent("offline.json"), options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        } catch { message = "本机保存失败：\(error.localizedDescription)" }
    }
    func keychain(_ code: String? = nil) -> String {
        let query: [String:Any] = [kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:"ResearchRadar.access",kSecAttrAccount as String:scope]
        if let code {
            SecItemDelete(query as CFDictionary)
            if !code.isEmpty {
                var q = query; q[kSecValueData as String] = Data(code.utf8); q[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
                if SecItemAdd(q as CFDictionary,nil) != errSecSuccess { message = "访问码未能保存到钥匙串，请重新输入。" }
            }
            return code
        }
        var q = query; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary,&result) == errSecSuccess, let data = result as? Data else { return "" }
        return String(data:data,encoding:.utf8) ?? ""
    }
    func configure(address: String, code: String, expectedID: String? = nil) async {
        do {
            let url = try ConnectionAddress.normalized(address)
            guard !busy && !configuring else { throw RadarError.message("正在同步，请完成后再切换服务器。") }
            configuring = true;defer { configuring = false }
            let firstConnectionDrafts = baseURL == nil ? pending : []
            persist(); generation = UUID(); serverAddress = url.absoluteString; UserDefaults.standard.set(serverAddress, forKey:"radar.server")
            let raw = try Data(contentsOf: Bundle.main.url(forResource:"ReadingShelf",withExtension:"json")!)
            restore(fallback: RadarSnapshot(raw: try JSONDecoder().decode(Record.self,from:raw)))
            for draft in firstConnectionDrafts where !pending.contains(where:{$0.id == draft.id}) { pending.append(draft) }
            applyPending();persist()
            connected = false
            if let expectedID {
                let server = try await object("api/discovery")
                guard server.text("id").lowercased() == expectedID.lowercased() else { throw RadarError.message("服务器身份与配对码不一致，请重新扫描 Mac 上的二维码。") }
            }
            _ = keychain(code)
            await refresh()
        } catch { message = error.localizedDescription }
    }
    func request(_ path: String, method: String = "GET", body: Record? = nil, retry: Bool = true) async throws -> Data {
        guard let baseURL, let url = URL(string:path, relativeTo:baseURL)?.absoluteURL, url.host == baseURL.host, url.port == baseURL.port else { throw RadarError.message("请先在连接设置中填写研究台地址。") }
        let active = generation
        var req = URLRequest(url:url); req.httpMethod = method
        if let body { req.httpBody = try JSONEncoder().encode(body); req.setValue("application/json", forHTTPHeaderField:"Content-Type") }
        do {
            let (data,response) = try await session.data(for:req)
            guard active == generation else { throw RadarError.message("服务器已切换，本次请求已取消。") }
            guard let http = response as? HTTPURLResponse else { throw RadarError.message("服务器响应无效") }
            if http.statusCode == 401, retry, path != "api/login", !keychain().isEmpty {
                _ = try await request("api/login",method:"POST",body:["code":JSONValue(keychain())],retry:false)
                return try await request(path,method:method,body:body,retry:false)
            }
            let object = (try? JSONDecoder().decode(Record.self,from:data)) ?? [:]
            if http.statusCode == 409 { throw RadarError.conflict(object["current"]?.object ?? [:]) }
            if http.statusCode == 401 { throw RadarError.message("请输入正确的访问码。服务重启后可能需要重新登录。") }
            guard (200..<300).contains(http.statusCode) else { throw RadarError.message(object.text("error").isEmpty ? "服务器返回 HTTP \(http.statusCode)" : object.text("error")) }
            return data
        } catch let error as URLError {
            connected = false
            throw RadarError.message(error.code == .timedOut ? "连接超时。请确认手机与 Mac 可以互通；缓存和本机草稿仍可使用。" : "未连接研究台：\(error.localizedDescription)。请检查地址、本地网络权限与 Mac 服务。")
        }
    }
    func object(_ path:String,method:String = "GET",body:Record? = nil) async throws -> Record {
        try JSONDecoder().decode(Record.self,from:try await request(path,method:method,body:body))
    }
    func refresh(silent: Bool = false) async {
        guard !busy else { return }; busy = true; defer { busy = false }
        do {
            let raw = try await object("api/state");confirmed = RadarSnapshot(raw:raw);serverSyncRunning = (raw["sync"]?.object ?? [:]).flag("running");connected = true; lastConnected = Date()
            applyPending(); persist()
            connectionNotice = nil
            await flush(silent:silent)
            await syncReadingContent()
        } catch {
            connected = false; connectionNotice = error.localizedDescription
            if !silent { message = error.localizedDescription }
            applyPending()
        }
    }
    func applyPending() {
        snapshot = confirmed
        for command in pending {
            switch command.kind {
            case "item":
                if let i = snapshot.items.firstIndex(where:{$0.id==command.target}) { snapshot.items[i].data.merge(command.changes) { _,new in new } }
            case "idea":
                if let i = snapshot.ideas.firstIndex(where:{$0.id==command.target}) { snapshot.ideas[i].data.merge(command.changes) { _,new in new } }
                else { snapshot.ideas.insert(Entry(data:command.changes.merging(["id":JSONValue(command.target)]) { _,new in new }),at:0) }
            case "idea-delete": snapshot.ideas.removeAll { $0.id==command.target }
            case "frontier":
                if snapshot.signals == nil { snapshot.signals = bundledSignals }
                if let i=snapshot.signals?.firstIndex(where:{$0.id==command.target}) {
                    let current=snapshot.signals?[i].data.text("version_signature") ?? "",base=command.base.text("version_signature")
                    if !current.isEmpty && !base.isEmpty && current != base { continue }
                    snapshot.signals?[i].data.merge(command.changes) { _,new in new }
                }
            default: break
            }
        }
    }
    func entry(_ id:String) -> Entry? { snapshot.items.first {$0.id==id} }
    func stageSignal(_ id:String,status:String) async {
        guard let original=(confirmed.signals ?? bundledSignals).first(where:{$0.id==id}) else { return }
        stage(kind:"frontier",id:id,base:original.data.filter{["status","version_signature"].contains($0.key)},changes:["status":JSONValue(status)])
        await sendIfPossible()
    }
    func stageItem(_ id:String,changes:Record) async {
        guard let original = confirmed.items.first(where:{$0.id==id}) else { return }
        stage(kind:"item",id:id,base:original.data,changes:changes)
        await sendIfPossible()
    }
    func stageIdea(id:String,changes:Record) async {
        let original = confirmed.ideas.first {$0.id==id}
        stage(kind:"idea",id:id,base:original?.data ?? ["exists":JSONValue(false)],changes:changes)
        await sendIfPossible()
    }
    func deleteIdea(_ id:String) async {
        if confirmed.ideas.contains(where:{$0.id==id}) {
            pending.removeAll {$0.target==id && $0.kind=="idea"}
            stage(kind:"idea-delete",id:id,base:confirmed.ideas.first{$0.id==id}!.data,changes:[:])
        } else { pending.removeAll {$0.target==id}; applyPending(); persist() }
        await sendIfPossible()
    }
    private func stage(kind:String,id:String,base:Record,changes:Record) {
        // Keep the original baseline; editing a draft must not erase an unresolved conflict.
        if let index = pending.firstIndex(where:{$0.kind==kind && $0.target==id}) {
            pending[index].id = UUID().uuidString
            for key in changes.keys where pending[index].base[key] == nil { pending[index].base[key] = base[key] }
            pending[index].changes.merge(changes) { _,new in new }
        } else { pending.append(PendingChange(kind:kind,target:id,base:kind == "item" ? base.filter { changes[$0.key] != nil } : base,changes:changes)) }
        applyPending(); persist()
    }
    private func sendIfPossible() async { if connected && !busy { busy = true; await flush(); busy = false } }
    func flush(silent: Bool = false) async {
        for id in pending.map(\.id) {
            guard let command = pending.first(where:{$0.id==id}), command.conflict == nil else { continue }
            do {
                let body:Record = ["id":JSONValue(command.id),"kind":JSONValue(command.kind),"target":JSONValue(command.target),"base":JSONValue(command.base),"changes":JSONValue(command.changes)]
                let receipt = try await object("api/mobile/commit",method:"POST",body:body)
                let record = receipt["record"]?.object ?? [:]
                if command.kind == "item", let i = confirmed.items.firstIndex(where:{$0.id==command.target}) { confirmed.items[i].data = record }
                else if command.kind == "idea" { confirmed.ideas.removeAll {$0.id==command.target}; confirmed.ideas.insert(Entry(data:record),at:0) }
                else if command.kind == "idea-delete" { confirmed.ideas.removeAll {$0.id==command.target} }
                else if command.kind == "frontier" {
                    if confirmed.signals == nil { confirmed.signals = bundledSignals }
                    if let i=confirmed.signals?.firstIndex(where:{$0.id==command.target}) { confirmed.signals?[i].data.merge(record) { _,new in new } }
                }
                pending.removeAll {$0.id==id}
                // A receipt proves the write; fetch a fresh baseline before clearing the visible draft.
                persist()
            } catch RadarError.conflict(let current) {
                if let index = pending.firstIndex(where:{$0.id==id}) { pending[index].conflict = current }
                message = "有同步冲突，本机修改已保留。"
            } catch { connectionNotice = error.localizedDescription; if !silent { message = error.localizedDescription }; break }
        }
        do { let raw = try await object("api/state");confirmed = RadarSnapshot(raw:raw);serverSyncRunning = (raw["sync"]?.object ?? [:]).flag("running");connected = true; lastConnected = Date() }
        catch { connected = false }
        applyPending(); persist()
    }
    func resolve(_ change:PendingChange,useLocal:Bool) async {
        guard let i = pending.firstIndex(where:{$0.id==change.id}) else { return }
        if useLocal {
            pending[i].base = change.kind == "item" ? (change.conflict ?? [:]).filter { change.changes[$0.key] != nil } : (change.kind == "idea" && (change.conflict ?? [:]).isEmpty ? ["exists":JSONValue(false)] : (change.conflict ?? [:])); pending[i].conflict = nil; pending[i].id = UUID().uuidString
        } else { pending.remove(at:i) }
        applyPending(); persist(); await refresh()
    }
    func details(_ id:String) async throws -> Record {
        let path = "api/items/" + id.addingPercentEncoding(withAllowedCharacters:.urlPathAllowed)!
        let value = try await object(path)
        if let i = confirmed.items.firstIndex(where:{$0.id==id}) { confirmed.items[i].data = value; applyPending(); persist() }
        return value
    }
    func run(_ path:String,body:Record? = nil) async {
        guard !busy else { return }; busy = true
        do {
            _ = try await object(path,method:"POST",body:body)
            if path == "api/sync" {
                serverSyncRunning = true
                defer { serverSyncRunning = false }
                for _ in 0..<90 {
                    try await Task.sleep(for:.seconds(1))
                    if !(try await object("api/sync")).flag("running") { break }
                }
                let current = try await object("api/sync")
                if current.flag("running") { connectionNotice = "采集仍在 Mac 后台运行，稍后下拉刷新。" }
            } else { message = "操作已提交" }
        }
        catch { message = error.localizedDescription }
        busy = false; await refresh()
    }
    func download(_ path:String,name:String) async throws -> URL {
        let data = try await request(path)
        let folder = root.appendingPathComponent("Exports");try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        let file = folder.appendingPathComponent(UUID().uuidString+"-"+name)
        try data.write(to:file,options:[.atomic,.completeFileProtectionUntilFirstUserAuthentication]);return file
    }
    func pdfFile(_ item:Entry) -> URL { partition.appendingPathComponent("PDFs").appendingPathComponent(item.id.replacingOccurrences(of:"/",with:"_").replacingOccurrences(of:":",with:"-")+".pdf") }
    func cachePDF(_ item:Entry) async throws -> URL {
        guard let url = URL(string:item.data.text("pdf_url")), url.scheme == "https" else { throw RadarError.message("没有可下载的 HTTPS PDF 链接") }
        let (temp,response) = try await URLSession.shared.download(from:url)
        guard let response = response as? HTTPURLResponse, response.statusCode == 200 else { throw RadarError.message("PDF 下载未完成") }
        let size = (try FileManager.default.attributesOfItem(atPath:temp.path)[.size] as? NSNumber)?.intValue ?? 0
        guard size < 80*1024*1024 else { throw RadarError.message("PDF 超过 80 MB，请通过浏览器阅读") }
        let prefix = try FileHandle(forReadingFrom:temp); defer { try? prefix.close() }
        guard try prefix.read(upToCount:5) == Data("%PDF-".utf8) else { throw RadarError.message("来源没有返回 PDF 文件") }
        let file = pdfFile(item);try FileManager.default.createDirectory(at:file.deletingLastPathComponent(),withIntermediateDirectories:true)
        if FileManager.default.fileExists(atPath:file.path) { try FileManager.default.removeItem(at:file) }
        try FileManager.default.moveItem(at:temp,to:file);return file
    }
    func topicName(_ id:String) -> String { snapshot.topics.first{$0.id==id}?.data.text("short") ?? id }
}

extension RadarStore {
    func syncReadingContent() async {
        let active=generation
        contentReceipt["current"]=JSONValue(false)
        do {
            let manifest=try await object("api/content/manifest")
            if manifest.text("version")==contentCacheManifest.text("version") && offlineReadingCount==signals.count { contentNotice=nil;await acknowledgeContent(manifest,generation:active);return }
            let readings:Record
            let versions=manifest["reading_versions"]?.object ?? [:]
            if versions.isEmpty {
                let payload=try await object("api/content")
                readings=try ReadingPackage.validate(payload,manifest:manifest)
            } else {
                var changed:Record=[:]
                let previous=contentCacheManifest["reading_versions"]?.object ?? [:]
                for id in versions.keys.sorted() {
                    if versions[id]==previous[id] && !cachedReading(id).isEmpty { continue }
                    var path=URLComponents(string:"api/content/reading")!
                    path.queryItems=[URLQueryItem(name:"item_id",value:id),URLQueryItem(name:"version",value:manifest.text("version"))]
                    let payload=try await object(path.string!)
                    changed[id]=JSONValue(try ReadingPackage.validateReading(payload,id:id,manifest:manifest))
                }
                readings=changed
            }
            guard active==generation else { return }
            for (id,raw) in readings {
                let file=readingCache(id)
                try FileManager.default.createDirectory(at:file.deletingLastPathComponent(),withIntermediateDirectories:true)
                try JSONEncoder().encode(raw).write(to:file,options:[.atomic,.completeFileProtectionUntilFirstUserAuthentication])
            }
            var saved=manifest;saved["synced_at"]=JSONValue(ISO8601DateFormatter().string(from:Date()))
            let file=partition.appendingPathComponent("Reading/manifest.json")
            try FileManager.default.createDirectory(at:file.deletingLastPathComponent(),withIntermediateDirectories:true)
            try JSONEncoder().encode(saved).write(to:file,options:[.atomic,.completeFileProtectionUntilFirstUserAuthentication])
            contentCacheManifest=saved;contentNotice=nil
            await acknowledgeContent(manifest,generation:active)
        } catch {
            if active==generation { contentNotice="手记已更新，部分全文缓存待重试：\(error.localizedDescription)" }
        }
    }
    private func acknowledgeContent(_ manifest:Record,generation active:UUID) async {
        do {
            let receipt=try await object("api/content/receipt",method:"POST",body:["device_id":JSONValue(contentDeviceID),"version":JSONValue(manifest.text("version")),"documents":manifest["documents"] ?? JSONValue([:])])
            guard active==generation else { return }
            let file=partition.appendingPathComponent("Reading/receipt.json")
            try JSONEncoder().encode(receipt).write(to:file,options:[.atomic,.completeFileProtectionUntilFirstUserAuthentication])
            contentReceipt=receipt
            if !receipt.flag("current") { contentNotice="本机内容已保存；研究台已有新内容，请再次更新。" }
        } catch { if active==generation { contentNotice="全文已缓存；保存确认待联网重试。" } }
    }
    func refreshReadingQueue() async throws {
        let result = try await object("api/reading-queue")
        guard result != confirmed.reading_queue else { return }
        confirmed.reading_queue=result;applyPending();persist()
    }
    func enqueueReading(_ id:String) async throws {
        let result = try await object("api/reading-queue",method:"POST",body:["item_id":JSONValue(id)])
        confirmed.reading_queue=result["queue"]?.object;applyPending();persist()
    }
    func readingQueueAction(_ task:Record,action:String) async throws {
        let result = try await object("api/reading-queue/"+task.text("id"),method:"POST",body:["action":JSONValue(action),"revision":task["revision"] ?? JSONValue(value:.number(0))])
        confirmed.reading_queue=result["queue"]?.object;applyPending();persist()
    }
    func readingCache(_ id:String) -> URL {
        partition.appendingPathComponent("Reading").appendingPathComponent(SHA256.hash(data:Data(id.utf8)).map{String(format:"%02x",$0)}.joined()+".json")
    }
    func cachedReading(_ id:String) -> Record {
        let digest=signals.first(where:{$0.id==id})?.data.text("reading_document_id")
        if let raw=try? Data(contentsOf:readingCache(id)),let cached=try? JSONDecoder().decode(Record.self,from:raw),
           digest == nil || cached["document"]?.object.text("id")==digest { return cached }
        if let bundled=publicReadings[id]?.object,let digest,bundled["document"]?.object.text("id")==digest { return bundled }
        return [:]
    }
    func readingState(_ id:String) async throws -> Record {
        let result = try await object("api/reading/"+id.addingPercentEncoding(withAllowedCharacters:.urlPathAllowed)!)
        let file = readingCache(id)
        try FileManager.default.createDirectory(at:file.deletingLastPathComponent(),withIntermediateDirectories:true)
        try JSONEncoder().encode(result).write(to:file,options:[.atomic,.completeFileProtectionUntilFirstUserAuthentication])
        return result
    }
}
