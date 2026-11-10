import Foundation

struct JSONValue: Codable, Equatable, Hashable {
    var value: Value
    enum Value: Equatable, Hashable { case string(String), number(Double), bool(Bool), object([String:JSONValue]), array([JSONValue]), null }
    init(value: Value) { self.value = value }
    init(_ s: String) { value = .string(s) }
    init(_ b: Bool) { value = .bool(b) }
    init(_ object: [String:JSONValue]) { value = .object(object) }
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { value = .null }
        else if let v = try? c.decode(Bool.self) { value = .bool(v) }
        else if let v = try? c.decode(String.self) { value = .string(v) }
        else if let v = try? c.decode(Double.self) { value = .number(v) }
        else if let v = try? c.decode([String:JSONValue].self) { value = .object(v) }
        else { value = .array(try c.decode([JSONValue].self)) }
    }
    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch value {
        case .null: try c.encodeNil()
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        }
    }
    var string: String { if case .string(let v) = value { return v }; return "" }
    var bool: Bool { if case .bool(let v) = value { return v }; return false }
    var integer: Int { if case .number(let v) = value,v.isFinite,v>=Double(Int.min),v<Double(Int.max) { return Int(v) }; return 0 }
    var object: [String:JSONValue] { if case .object(let v) = value { return v }; return [:] }
    var array: [JSONValue] { if case .array(let v) = value { return v }; return [] }
}
typealias Record = [String:JSONValue]
extension Dictionary where Key == String, Value == JSONValue {
    func text(_ key: String) -> String { self[key]?.string ?? "" }
    func flag(_ key: String) -> Bool { self[key]?.bool ?? false }
    func records(_ key: String) -> [Record] { (self[key]?.array ?? []).map(\.object) }
    func strings(_ key: String) -> [String] { (self[key]?.array ?? []).map(\.string) }
}
struct Entry: Identifiable, Codable, Equatable {
    var data: Record
    var id: String { data.text("id") }
    var title: String { data.text("title_zh").isEmpty ? data.text("title") : data.text("title_zh") }
    var isPaper: Bool { data.text("kind") == "paper" }
    var topics: [String] { data.strings("topics") }
}
struct RadarSnapshot: Codable {
    var items: [Entry]
    var ideas: [Entry]
    var topics: [Entry]
    var sources: [Entry]
    var settings: Record
    var integrations: Record
    var recommended: [String]
    var server_time: String
    // Optional to keep previously saved snapshots and unsent drafts decodable.
    var technology_briefs: [Entry]?
    var signals: [Entry]?
    var frontier_meta: Record?
    var reading_queue: Record?
    init(raw: Record) {
        items = raw.records("items").map { Entry(data: $0) }
        ideas = raw.records("ideas").map { Entry(data: $0) }
        topics = raw.records("topics").map { Entry(data: $0) }
        sources = raw.records("sources").map { Entry(data: $0) }
        settings = raw["settings"]?.object ?? [:]
        integrations = raw["integrations"]?.object ?? [:]
        recommended = raw.strings("recommended")
        server_time = raw.text("server_time")
        technology_briefs = raw["technology_briefs"] == nil ? nil : raw.records("technology_briefs").map { Entry(data:$0) }
        signals = raw["signals"] == nil ? nil : raw.records("signals").map { Entry(data:$0) }
        frontier_meta = raw["frontier_meta"]?.object
        reading_queue = raw["reading_queue"]?.object
    }
    mutating func refreshBundledContent(from fallback:RadarSnapshot) {
        let existing=Dictionary((signals ?? []).map{($0.id,$0)},uniquingKeysWith:{$1})
        let incoming=fallback.signals ?? [],ids=Set(incoming.map(\.id))
        signals=incoming.map { row in
            var updated=row
            if let previous=existing[row.id] {
                let sameVersion = !row.data.text("version_signature").isEmpty && row.data.text("version_signature")==previous.data.text("version_signature")
                let sameDocument = !row.data.text("reading_document_id").isEmpty && row.data.text("reading_document_id")==previous.data.text("reading_document_id") && row.data.text("source_url")==previous.data.text("source_url")
                if (sameVersion || sameDocument) && ["new","seen","later","dismissed"].contains(previous.data.text("status")) { updated.data["status"]=previous.data["status"] }
            }
            return updated
        }+(signals ?? []).filter{!ids.contains($0.id)}
        let itemIDs=Set(items.map(\.id));items+=fallback.items.filter{!itemIDs.contains($0.id)}
        frontier_meta=fallback.frontier_meta
        frontier_meta?["published_count"]=JSONValue(value:.number(Double(signals?.count ?? 0)))
    }
}

enum FrontierFilter {
    static func matches(_ data:Record,mode:String,days:Int,today:Date = Date(),topic:String = "all",focus:[String] = [],unread:Bool = true,search:String = "") -> Bool {
        if !data.flag("publication_ready") { return false }
        if days > 0 && !["seen","later","dismissed"].contains(mode) {
            let format=DateFormatter();format.calendar=Calendar(identifier:.gregorian);format.locale=Locale(identifier:"en_US_POSIX");format.timeZone=TimeZone(secondsFromGMT:0);format.dateFormat="yyyy-MM-dd"
            let cutoff=format.string(from:today.addingTimeInterval(-Double(days-1)*86400))
            if data.text("published").isEmpty || data.text("published") < cutoff { return false }
        }
        let status=data.text("status")
        if mode=="seen" && status != "seen" { return false }
        if mode=="later" && status != "later" { return false }
        if mode=="dismissed" && status != "dismissed" { return false }
        if ["reviewed","all"].contains(mode) && status=="dismissed" { return false }
        if mode=="reviewed" && !data.flag("reviewed") { return false }
        if unread && ["reviewed","all"].contains(mode) && status != "new" { return false }
        if topic=="focus" && !data.strings("topics").contains(where:focus.contains) { return false }
        if !["all","focus"].contains(topic) && !data.strings("topics").contains(topic) { return false }
        let text=[data.text("title"),data.text("paper_title"),data.text("delta"),data.text("before"),data.text("after"),data.text("abstract")].joined(separator:" ")
        return search.isEmpty || text.localizedCaseInsensitiveContains(search)
    }
}

enum FrontierPriority {
    static func rank(_ row:Record)->Int {
        guard !["seen","dismissed"].contains(row.text("status")) else { return 0 }
        return ["priority":2,"notable":1][(row["attention"]?.object ?? [:]).text("level")] ?? 0
    }
    static func precedes(_ a:Record,_ b:Record)->Bool {
        let x=order(a),y=order(b)
        for index in x.indices where x[index] != y[index] { return x[index]>y[index] }
        if a.text("published") != b.text("published") { return a.text("published")>b.text("published") }
        return a.text("id")>b.text("id")
    }
    static func order(_ row:Record)->[Int] {
        let level=rank(row),impact=(row["attention"]?.object ?? [:])["impact"]?.object ?? [:]
        return [level>0 ? 1:0,level>0 ? (impact["rank"]?.integer ?? level):0,level>0 ? (impact["support_rank"]?.integer ?? 0):0,level]
    }
    static func featured(_ rows:[Record])->[Record] {
        var selected=[Record](),areas=Set<String>(),groups=Set<String>()
        for row in rows.sorted(by:precedes) where row.flag("publication_ready") && row.text("status")=="new" && rank(row)>0 {
            let area=((row["attention"]?.object ?? [:])["impact"]?.object ?? [:]).text("area")
            let group=row.text("research_group").isEmpty ? row.text("id"):row.text("research_group")
            if groups.contains(group) || (!area.isEmpty && areas.contains(area)) { continue }
            selected.append(row);areas.insert(area);groups.insert(group)
            if selected.count==3 { break }
        }
        return selected
    }
}
struct PendingChange: Identifiable, Codable, Equatable {
    var id = UUID().uuidString
    var kind: String
    var target: String
    var base: Record
    var changes: Record
    var conflict: Record? = nil
}
struct OfflineState: Codable {
    var snapshot: RadarSnapshot
    var pending: [PendingChange]
    var lastConnected: Date?
}
enum ReadingPackage {
    static func validateReading(_ payload:Record,id:String,manifest:Record) throws -> Record {
        let versions=manifest["reading_versions"]?.object ?? [:]
        guard let expected=versions[id],!expected.string.isEmpty,payload.text("item_id")==id,payload.text("version")==manifest.text("version"),payload["reading_version"]==expected,let reading=payload["reading"]?.object else { throw RadarError.message("单项全文版本已变化，请重新同步。") }
        let subset:Record=["version":manifest["version"] ?? JSONValue(""),"documents":JSONValue([id:(manifest["documents"]?.object ?? [:])[id] ?? JSONValue("")])]
        _ = try validate(["version":payload["version"] ?? JSONValue(""),"readings":JSONValue([id:JSONValue(reading)])],manifest:subset)
        return reading
    }
    static func validate(_ payload:Record,manifest:Record) throws -> Record {
        let documents=manifest["documents"]?.object ?? [:]
        let readings=payload["readings"]?.object ?? [:]
        guard !manifest.text("version").isEmpty, payload.text("version")==manifest.text("version"),
              Set(documents.keys)==Set(readings.keys) else { throw RadarError.message("内容版本已变化或下载不完整，请再次更新。") }
        for (id,digest) in documents {
            let reading=readings[id]?.object ?? [:],document=reading["document"]?.object ?? [:],analysis=reading["analysis"]?.object ?? [:]
            let passages=document.records("passages"),coverage=analysis["coverage"]?.object ?? [:]
            guard document.text("id")==digest.string, analysis.text("document_id")==digest.string,
                  analysis.text("item_id")==id, !passages.isEmpty,
                  coverage["read"]==JSONValue(value:.number(Double(passages.count))),
                  coverage["total"]==coverage["read"],
                  Set(coverage.strings("evidence_ids"))==Set(passages.map{$0.text("id")}),
                  coverage.strings("evidence_ids").count==passages.count else { throw RadarError.message("全文缓存未通过版本和覆盖检查，保留原缓存。") }
        }
        return readings
    }
}
enum ConnectionAddress {
    static func normalized(_ input: String) throws -> URL {
        var text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.contains("://") { text = "http://" + text }
        guard var c = URLComponents(string: text), let scheme = c.scheme?.lowercased(), ["http","https"].contains(scheme), let host = c.host, !host.isEmpty,
              c.user == nil, c.password == nil, c.query == nil, c.fragment == nil, c.path.isEmpty || c.path == "/" else { throw RadarError.message("请输入服务器根地址，例如 http://10.153.158.102:8765") }
        if scheme == "http" {
            let parts = host.split(separator: ".").compactMap { Int($0) }
            let privateIP = parts.count == 4 && parts.allSatisfy { (0...255).contains($0) } && (parts[0] == 10 || parts[0] == 127 || (parts[0] == 192 && parts[1] == 168) || (parts[0] == 172 && (16...31).contains(parts[1])))
            guard privateIP || host == "localhost" || host.hasSuffix(".local") else { throw RadarError.message("校园网地址可用 HTTP，公网服务器请使用 HTTPS。") }
        }
        c.scheme = scheme; c.host = host.lowercased(); c.path = "/"
        guard let url = c.url else { throw RadarError.message("服务器地址无效") }
        return url
    }
}
enum RadarError: LocalizedError {
    case message(String)
    case conflict(Record)
    var errorDescription: String? {
        switch self { case .message(let s): return s; case .conflict: return "服务器内容已变化。本机修改已保留，请在“同步冲突”中选择保留哪个版本。" }
    }
}

struct ConnectionInvitation: Identifiable, Equatable {
    let id: String
    let address: URL
    static func parse(_ url: URL) throws -> ConnectionInvitation {
        guard let c = URLComponents(url:url,resolvingAgainstBaseURL:false), c.scheme == "embodiedradar", c.host == "connect", c.path.isEmpty, c.user == nil, c.password == nil, c.fragment == nil,
              let items = c.queryItems, items.count == 2, Set(items.map(\.name)) == Set(["url","id"]),
              let raw = items.first(where:{$0.name=="url"})?.value, let id = items.first(where:{$0.name=="id"})?.value, UUID(uuidString:id) != nil else { throw RadarError.message("这不是有效的研究台配对码。") }
        return ConnectionInvitation(id:id,address:try ConnectionAddress.normalized(raw))
    }
}

/// Both the App invitation QR and the Safari root-address QR are accepted.
struct ConnectionTarget: Equatable {
    let address: URL
    let expectedID: String?
    static func parse(_ text: String) throws -> ConnectionTarget {
        let value = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string:value) else { throw RadarError.message("配对链接无效，请扫描 Mac 配对页的二维码。") }
        if ["http","https"].contains(url.scheme?.lowercased() ?? "") {
            return ConnectionTarget(address:try ConnectionAddress.normalized(value),expectedID:nil)
        }
        let invitation = try ConnectionInvitation.parse(url)
        return ConnectionTarget(address:invitation.address,expectedID:invitation.id)
    }
}
