import SwiftUI
import VisionKit
import AVFoundation

struct NearbyServer: Identifiable {
    let id: String
    let name: String
    let address: String
}
@MainActor final class ServerDiscovery: NSObject, ObservableObject, @preconcurrency NetServiceBrowserDelegate, @preconcurrency NetServiceDelegate {
    @Published var servers: [NearbyServer] = []
    @Published var status = "尚未搜索"
    private let browser = NetServiceBrowser()
    private var services: [NetService] = []
    override init() { super.init();browser.delegate = self }
    func start() {
        stop();servers = [];status = "正在查找同网研究台…"
        browser.searchForServices(ofType:"_embodiedradar._tcp.",inDomain:"local.")
    }
    func stop() { browser.stop();services.forEach{$0.stop()};services = [] }
    func netServiceBrowser(_ browser:NetServiceBrowser,didFind service:NetService,moreComing:Bool) {
        services.append(service);service.delegate = self;service.resolve(withTimeout:8)
    }
    func netServiceBrowser(_ browser:NetServiceBrowser,didRemove service:NetService,moreComing:Bool) {
        services.removeAll{$0 == service};servers.removeAll{$0.name == service.name}
    }
    func netServiceBrowser(_ browser:NetServiceBrowser,didNotSearch errorDict:[String:NSNumber]) { status = "搜索未完成，可扫描二维码或手动输入地址。" }
    func netServiceDidResolveAddress(_ sender:NetService) {
        guard let host = sender.hostName?.trimmingCharacters(in:CharacterSet(charactersIn:".")), sender.port > 0,
              let raw = sender.txtRecordData(), let data = NetService.dictionary(fromTXTRecord:raw)["id"], let id = String(data:data,encoding:.utf8), UUID(uuidString:id) != nil else { return }
        let server = NearbyServer(id:id,name:sender.name,address:"http://\(host):\(sender.port)/")
        servers.removeAll{$0.id==id};servers.append(server);status = "找到 \(servers.count) 台研究台，点选后输入访问码。"
    }
}
struct QRScanner: UIViewControllerRepresentable {
    let result: (String) -> Void
    let failure: (String) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(result:result,failure:failure) }
    func makeUIViewController(context:Context) -> DataScannerViewController {
        let controller = DataScannerViewController(recognizedDataTypes:[.barcode(symbologies:[.qr])],qualityLevel:.balanced,recognizesMultipleItems:false,isHighFrameRateTrackingEnabled:false,isPinchToZoomEnabled:true,isGuidanceEnabled:true,isHighlightingEnabled:true)
        controller.delegate = context.coordinator
        DispatchQueue.main.async {
            do { try controller.startScanning() }
            catch { context.coordinator.fail("相机扫描未能启动，请关闭后重试，或粘贴 Mac 配对页的链接。") }
        }
        return controller
    }
    func updateUIViewController(_ controller:DataScannerViewController,context:Context) {}
    static func dismantleUIViewController(_ controller:DataScannerViewController,coordinator:Coordinator) { controller.stopScanning() }
    class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let result: (String) -> Void
        let failure: (String) -> Void
        private var delivered = false
        init(result:@escaping (String)->Void,failure:@escaping (String)->Void) { self.result = result;self.failure = failure }
        func fail(_ message:String) { guard !delivered else { return };delivered=true;failure(message) }
        func dataScanner(_ dataScanner:DataScannerViewController,didAdd addedItems:[RecognizedItem],allItems:[RecognizedItem]) {
            deliver(allItems,from:dataScanner)
        }
        func dataScanner(_ dataScanner:DataScannerViewController,didUpdate updatedItems:[RecognizedItem],allItems:[RecognizedItem]) {
            deliver(allItems,from:dataScanner)
        }
        func dataScanner(_ dataScanner:DataScannerViewController,didTapOn item:RecognizedItem) {
            deliver([item],from:dataScanner)
        }
        func dataScanner(_ dataScanner:DataScannerViewController,becameUnavailableWithError error:DataScannerViewController.ScanningUnavailable) {
            fail("相机扫描已暂停，请关闭后重试，或粘贴 Mac 配对页的链接。")
        }
        func deliver(_ items:[RecognizedItem],from dataScanner:DataScannerViewController) {
            guard !delivered else { return }
            for item in items {
                if case .barcode(let code) = item, let value = code.payloadStringValue { delivered = true;dataScanner.stopScanning();result(value);break }
            }
        }
    }
}
struct ScannerView: View {
    @Environment(\.dismiss) private var dismiss
    let result: (String) -> Void
    @State private var cameraReady = false
    @State private var checked = false
    @State private var scanError: String?
    var body: some View {
        NavigationStack {
            Group {
                if let error=scanError { ContentUnavailableView("扫描未完成",systemImage:"qrcode",description:Text(error)) }
                else if !checked { ProgressView("正在准备相机…") }
                else if cameraReady && DataScannerViewController.isSupported && DataScannerViewController.isAvailable {
                    QRScanner(result:{ value in result(value);dismiss() },failure:{ scanError=$0 }).ignoresSafeArea(edges:.bottom)
                        .safeAreaInset(edge:.bottom) { Text("对准 Mac 配对页的二维码，识别后会回到连接设置。随后输入访问码并连接。").font(.callout).padding().frame(maxWidth:.infinity).background(.regularMaterial) }
                }
                else { ContentUnavailableView("相机扫描不可用",systemImage:"qrcode",description:Text("可用系统相机扫描 Mac 配对页，或复制配对链接到连接设置。请检查相机权限。")) }
            }.navigationTitle("扫描研究台配对码").navigationBarTitleDisplayMode(.inline)
            .task { cameraReady = await AVCaptureDevice.requestAccess(for:.video);checked = true }
            .toolbar { ToolbarItem(placement:.cancellationAction) { Button("关闭") { dismiss() } } }
        }
    }
}
