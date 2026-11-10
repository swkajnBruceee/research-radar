import XCTest
@testable import RadarCore
final class ModelsTests: XCTestCase {
    func testFeaturedOverviewComparesReachAndAvoidsDuplicateOrHandledResearch() {
        func row(_ id:String,_ reach:Int,_ area:String,_ date:String,_ group:String)->Record {
            ["id":JSONValue(id),"published":JSONValue(date),"status":JSONValue("new"),"publication_ready":JSONValue(true),"research_group":JSONValue(group),"attention":JSONValue(["level":JSONValue("priority"),"impact":JSONValue(["rank":JSONValue(value:.number(Double(reach))),"support_rank":JSONValue(value:.number(2)),"area":JSONValue(area)])])]
        }
        let route=row("route",3,"training","2026-10-20","project"),tool=row("tool",1,"evaluation","2026-11-09","tool")
        XCTAssertTrue(FrontierPriority.precedes(route,tool))
        let picked=FrontierPriority.featured([tool,route,row("release",1,"data","2026-11-09","project")])
        XCTAssertEqual(picked.filter{$0.text("research_group")=="project"}.count,1)
        var handled=route;handled["status"]=JSONValue("seen")
        XCTAssertFalse(FrontierPriority.featured([handled,tool]).contains{$0.text("id")=="route"})
    }
    func testOfflineAppUpdateAddsPublicContentWithoutReplacingNotesDraftSourcesOrMatchingTriage() {
        var original=RadarSnapshot(raw:[:]);original.items=[Entry(data:["id":JSONValue("paper"),"notes":JSONValue("My private notes"),"reading":JSONValue("read")])]
        original.signals=[Entry(data:["id":JSONValue("paper"),"version_signature":JSONValue("v1"),"status":JSONValue("seen")])]
        var update=RadarSnapshot(raw:[:]);update.items=[Entry(data:["id":JSONValue("paper"),"notes":JSONValue("")]),Entry(data:["id":JSONValue("new-paper")])]
        update.signals=[Entry(data:["id":JSONValue("paper"),"version_signature":JSONValue("v1"),"status":JSONValue("new")]),Entry(data:["id":JSONValue("new-paper"),"status":JSONValue("new")])]
        original.refreshBundledContent(from:update)
        XCTAssertEqual(original.items.first?.data.text("notes"),"My private notes")
        XCTAssertEqual(original.items.first?.data.text("reading"),"read")
        XCTAssertEqual(original.signals?.first?.data.text("status"),"seen")
        XCTAssertTrue(original.items.contains{$0.id=="new-paper"})
        update.signals?[0].data["version_signature"]=JSONValue("v2")
        original.refreshBundledContent(from:update);XCTAssertEqual(original.signals?.first?.data.text("status"),"new")
    }
    func testImportantOlderResearchPrecedesRoutineNewsAndRespectsTriageAndDateFilters() throws {
        var important:Record=["published":JSONValue("2026-10-20"),"status":JSONValue("new"),"attention":JSONValue(["level":JSONValue("priority")])]
        let routine:Record=["published":JSONValue("2026-11-07"),"status":JSONValue("new")]
        XCTAssertTrue(FrontierPriority.precedes(important,routine))
        important["status"]=JSONValue("seen");XCTAssertFalse(FrontierPriority.precedes(important,routine))
        important["status"]=JSONValue("dismissed");XCTAssertEqual(FrontierPriority.rank(important),0)
        important["status"]=JSONValue("new");important["publication_ready"]=JSONValue(true);important["reviewed"]=JSONValue(true)
        let date=ISO8601DateFormatter().date(from:"2026-11-07T00:00:00Z")!
        XCTAssertFalse(FrontierFilter.matches(important,mode:"reviewed",days:7,today:date,unread:false))
        XCTAssertTrue(FrontierFilter.matches(important,mode:"reviewed",days:0,today:date,unread:false))
    }
    func testScannerAcceptsBothAppAndWebCodesWithoutAcceptingSecretsOrArbitraryPaths() throws {
        let id="01234567-89AB-CDEF-0123-456789ABCDEF"
        let address="https://research.example.com/"
        let invitation="embodiedradar://connect?url=https%3A%2F%2Fresearch.example.com%2F&id="+id
        let app=try ConnectionTarget.parse(invitation)
        XCTAssertEqual(app.address.absoluteString,address);XCTAssertEqual(app.expectedID,id)
        let web=try ConnectionTarget.parse("  \n"+address+"\n")
        XCTAssertEqual(web.address,app.address);XCTAssertNil(web.expectedID)
        XCTAssertEqual(try ConnectionTarget.parse("http://research-mac.local:8765/").address.absoluteString,"http://research-mac.local:8765/")
        for bad in ["https://research.example.com/?code=secret","https://user:secret@research.example.com/","https://research.example.com/api/export","javascript:alert(1)","not a pairing code",invitation+"&code=secret"] {
            XCTAssertThrowsError(try ConnectionTarget.parse(bad))
        }
    }
    func testIncrementalReadingRejectsMixedPackageVersionsAndIncompleteEvidence() throws {
        let id="paper",digest="doc",version="package",readingVersion="reading"
        let document:Record=["id":JSONValue(digest),"passages":JSONValue(value:.array([JSONValue(["id":JSONValue("p")])]))]
        let analysis:Record=["document_id":JSONValue(digest),"item_id":JSONValue(id),"coverage":JSONValue(["read":JSONValue(value:.number(1)),"total":JSONValue(value:.number(1)),"evidence_ids":JSONValue(value:.array([JSONValue("p")]))])]
        let reading:Record=["document":JSONValue(document),"analysis":JSONValue(analysis)]
        let manifest:Record=["version":JSONValue(version),"documents":JSONValue([id:JSONValue(digest)]),"reading_versions":JSONValue([id:JSONValue(readingVersion)])]
        var payload:Record=["version":JSONValue(version),"item_id":JSONValue(id),"reading_version":JSONValue(readingVersion),"reading":JSONValue(reading)]
        XCTAssertEqual(try ReadingPackage.validateReading(payload,id:id,manifest:manifest),reading)
        payload["version"]=JSONValue("another-package");XCTAssertThrowsError(try ReadingPackage.validateReading(payload,id:id,manifest:manifest))
        payload["version"]=JSONValue(version);payload["reading_version"]=JSONValue("another-reading");XCTAssertThrowsError(try ReadingPackage.validateReading(payload,id:id,manifest:manifest))
    }
    func testDownloadedReadingsRejectMixedVersionsAndIncompleteCoverage() throws {
        let url=URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("ResearchRadar/Resources/ReadingShelf.json")
        let raw=try JSONDecoder().decode(Record.self,from:Data(contentsOf:url))
        var manifest=try XCTUnwrap(raw["content_manifest"]?.object)
        let readings=try XCTUnwrap(raw["public_readings"]?.object)
        var payload:Record=["version":JSONValue(manifest.text("version")),"readings":JSONValue(readings)]
        XCTAssertEqual(try ReadingPackage.validate(payload,manifest:manifest),readings)
        payload["version"]=JSONValue("other")
        XCTAssertThrowsError(try ReadingPackage.validate(payload,manifest:manifest))
        payload["version"]=manifest["version"]
        var documents=manifest["documents"]?.object ?? [:]
        let id=try XCTUnwrap(documents.keys.first)
        documents[id]=JSONValue("stale-document");manifest["documents"]=JSONValue(documents)
        XCTAssertThrowsError(try ReadingPackage.validate(payload,manifest:manifest))
        manifest=raw["content_manifest"]?.object ?? [:]
        var broken=readings,reading=broken[id]?.object ?? [:],analysis=reading["analysis"]?.object ?? [:]
        var coverage=analysis["coverage"]?.object ?? [:];coverage["read"]=JSONValue(value:.number(0));analysis["coverage"]=JSONValue(coverage)
        reading["analysis"]=JSONValue(analysis);broken[id]=JSONValue(reading);payload["readings"]=JSONValue(broken)
        XCTAssertThrowsError(try ReadingPackage.validate(payload,manifest:manifest))
    }
    func testFoundationSnapshotDecodesWithoutPrivateContent() throws {
        let url=URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("ResearchRadar/Resources/ReadingShelf.json")
        let raw=try JSONDecoder().decode(Record.self,from:Data(contentsOf:url))
        let snapshot=RadarSnapshot(raw:raw)
        XCTAssertGreaterThanOrEqual(snapshot.items.count,8);XCTAssertEqual(snapshot.topics.count,8)
        XCTAssertFalse(snapshot.signals?.isEmpty ?? true)
        XCTAssertTrue(snapshot.items.allSatisfy { $0.data.text("notes").isEmpty && !$0.data.flag("saved") })
        XCTAssertTrue(snapshot.integrations.isEmpty)
        let readings=raw["public_readings"]?.object ?? [:]
        let signal=try XCTUnwrap(snapshot.signals?.first)
        let reading=try XCTUnwrap(readings[signal.id]?.object)
        XCTAssertEqual(reading["document"]?.object.text("id"),signal.data.text("reading_document_id"))
        XCTAssertEqual(reading["analysis"]?.object["coverage"]?.object.strings("evidence_ids").count,reading["document"]?.object.records("passages").count)
        let saved=OfflineState(snapshot:snapshot,pending:[PendingChange(kind:"item",target:snapshot.items[0].id,base:snapshot.items[0].data,changes:["notes":JSONValue("离线笔记\nEvidence")])],lastConnected:nil)
        let restored=try JSONDecoder().decode(OfflineState.self,from:JSONEncoder().encode(saved))
        XCTAssertEqual(restored.pending[0].changes.text("notes"),"离线笔记\nEvidence")
        XCTAssertEqual(restored.pending[0].base,snapshot.items[0].data)
    }
    func testURLsSeparateLocalAndPublicTransport() throws {
        XCTAssertEqual(try ConnectionAddress.normalized("10.153.158.102:8765").absoluteString,"http://10.153.158.102:8765/")
        XCTAssertEqual(try ConnectionAddress.normalized("https://example.com").absoluteString,"https://example.com/")
        for bad in ["http://public.example.com","http://10.999.0.1","https://example.com?token=x","https://user:password@example.com","file:///etc/hosts","https://example.com/api/state"] { XCTAssertThrowsError(try ConnectionAddress.normalized(bad)) }
    }
    func testJSONValuesRemainTypedAcrossPersistence() throws {
        let raw=Data("{\"saved\":true,\"reading\":\"read\",\"count\":42,\"null\":null,\"topics\":[\"vla\"],\"nested\":{\"notes\":\"x\"}}".utf8)
        let value=try JSONDecoder().decode(Record.self,from:raw)
        XCTAssertTrue(value.flag("saved"));XCTAssertEqual(value.strings("topics"),["vla"])
        XCTAssertEqual(try JSONDecoder().decode(Record.self,from:JSONEncoder().encode(value)),value)
    }
    func testPairingInvitationRequiresValidIdentityAndSafeServerAddress() throws {
        let id = "01234567-89AB-CDEF-0123-456789ABCDEF"
        let value = try ConnectionInvitation.parse(URL(string:"embodiedradar://connect?url=http%3A%2F%2Fresearch-mac.local%3A8765%2F&id="+id)!)
        XCTAssertEqual(value.id,id);XCTAssertEqual(value.address.absoluteString,"http://research-mac.local:8765/")
        for bad in ["https://connect?url=https://example.com&id="+id,"embodiedradar://connect?url=http://public.example.com&id="+id,"embodiedradar://connect?url=https://example.com&id=broken","embodiedradar://connect?url=https://example.com&id="+id+"&id="+id,"embodiedradar://connect?url=https://example.com&id="+id+"&code=secret"] {
            XCTAssertThrowsError(try ConnectionInvitation.parse(URL(string:bad)!))
        }
    }

    func testTechnologyExplanationsLoadOfflineAndOlderDraftCachesStillDecode() throws {
        let url=URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("ResearchRadar/Resources/ReadingShelf.json")
        let raw=try JSONDecoder().decode(Record.self,from:Data(contentsOf:url))
        let snapshot=RadarSnapshot(raw:raw)
        XCTAssertEqual(snapshot.technology_briefs?.count,5)
        XCTAssertTrue(snapshot.technology_briefs?.allSatisfy{!$0.data.text("tagline").isEmpty && !$0.data.text("why").isEmpty} ?? false)
        let old=OfflineState(snapshot:snapshot,pending:[PendingChange(kind:"item",target:"arxiv:2406.09246",base:["notes":JSONValue("")],changes:["notes":JSONValue("Keep this offline draft")])],lastConnected:nil)
        var document=try JSONSerialization.jsonObject(with:JSONEncoder().encode(old)) as! [String:Any]
        var oldSnapshot=document["snapshot"] as! [String:Any];oldSnapshot.removeValue(forKey:"technology_briefs");oldSnapshot.removeValue(forKey:"signals");oldSnapshot.removeValue(forKey:"frontier_meta");document["snapshot"]=oldSnapshot
        let restored=try JSONDecoder().decode(OfflineState.self,from:JSONSerialization.data(withJSONObject:document))
        XCTAssertNil(restored.snapshot.technology_briefs);XCTAssertNil(restored.snapshot.signals);XCTAssertNil(restored.snapshot.frontier_meta)
        XCTAssertEqual(restored.pending[0].changes.text("notes"),"Keep this offline draft")
    }

    func testFrontierDateAndQueueFiltersKeepBackgroundOutOfCurrentUpdates() throws {
        let url=URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("ResearchRadar/Resources/ReadingShelf.json")
        let raw=try JSONDecoder().decode(Record.self,from:Data(contentsOf:url));let snapshot=RadarSnapshot(raw:raw)
        XCTAssertGreaterThanOrEqual(snapshot.signals?.count ?? 0,2)
        var row=snapshot.signals![0].data
        row["published"]=JSONValue("2026-11-03")
        let date=ISO8601DateFormatter().date(from:"2026-11-05T00:00:00Z")!
        XCTAssertTrue(FrontierFilter.matches(row,mode:"reviewed",days:7,today:date))
        row["published"]=JSONValue("2024-01-01")
        XCTAssertFalse(FrontierFilter.matches(row,mode:"reviewed",days:7,today:date))
        XCTAssertTrue(FrontierFilter.matches(row,mode:"reviewed",days:0,today:date))
        row["status"]=JSONValue("later")
        XCTAssertFalse(FrontierFilter.matches(row,mode:"reviewed",days:0,today:date))
        XCTAssertTrue(FrontierFilter.matches(row,mode:"later",days:7,today:date))
        row["status"]=JSONValue("seen")
        XCTAssertTrue(FrontierFilter.matches(row,mode:"seen",days:7,today:date))
        XCTAssertFalse(FrontierFilter.matches(row,mode:"later",days:0,today:date))
        row["status"]=JSONValue("dismissed")
        XCTAssertFalse(FrontierFilter.matches(row,mode:"all",days:0,today:date,unread:false))
        XCTAssertTrue(FrontierFilter.matches(row,mode:"dismissed",days:0,today:date))
        row["reviewed"]=JSONValue(false);row["status"]=JSONValue("new")
        XCTAssertFalse(FrontierFilter.matches(row,mode:"reviewed",days:0,today:date))
        XCTAssertTrue(FrontierFilter.matches(row,mode:"all",days:0,today:date))
        row["publication_ready"]=JSONValue(false)
        XCTAssertFalse(FrontierFilter.matches(row,mode:"all",days:0,today:date))
    }

    func testReadingQueueCachesWithDraftsAndOldSnapshotsRemainDecodable() throws {
        let url=URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("ResearchRadar/Resources/ReadingShelf.json")
        var raw=try JSONDecoder().decode(Record.self,from:Data(contentsOf:url))
        raw["reading_queue"]=JSONValue(["tasks":JSONValue(value:.array([JSONValue(["id":JSONValue("task"),"status":JSONValue("needs_review"),"revision":JSONValue(value:.number(3))])]))])
        let snapshot=RadarSnapshot(raw:raw)
        let state=OfflineState(snapshot:snapshot,pending:[PendingChange(kind:"item",target:"paper",base:[:],changes:["notes":JSONValue("Keep my draft")])],lastConnected:nil)
        let encoded=try JSONEncoder().encode(state)
        let restored=try JSONDecoder().decode(OfflineState.self,from:encoded)
        XCTAssertEqual(restored.snapshot.reading_queue?.records("tasks").first?.text("status"),"needs_review")
        var old=try JSONSerialization.jsonObject(with:encoded) as! [String:Any]
        var oldSnapshot=old["snapshot"] as! [String:Any];oldSnapshot.removeValue(forKey:"reading_queue");old["snapshot"]=oldSnapshot
        let legacy=try JSONDecoder().decode(OfflineState.self,from:JSONSerialization.data(withJSONObject:old))
        XCTAssertNil(legacy.snapshot.reading_queue)
        XCTAssertEqual(legacy.pending.first?.changes.text("notes"),"Keep my draft")
    }

}
