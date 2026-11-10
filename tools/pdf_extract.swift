import Foundation
import PDFKit
import Vision
let input=CommandLine.arguments.dropFirst().first ?? ""
guard let document=PDFDocument(url:URL(fileURLWithPath:input)),document.pageCount<=250 else { fputs("PDF 无法读取或超过 250 页\n",stderr);exit(1) }
var pages:[[String:Any]]=[]
var unreadable:[Int]=[]
var ocrPages:[Int]=[]
let useOCR=CommandLine.arguments.contains("--ocr")
for index in 0..<document.pageCount {
    guard let page=document.page(at:index) else { unreadable.append(index+1);continue }
    var text=page.string ?? ""
    if useOCR && text.trimmingCharacters(in:.whitespacesAndNewlines).count<20 {
        let bounds=page.bounds(for:.mediaBox)
        let scale=min(2,2000/max(bounds.width,bounds.height))
        if let context=CGContext(data:nil,width:max(1,Int(bounds.width*scale)),height:max(1,Int(bounds.height*scale)),bitsPerComponent:8,bytesPerRow:0,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.noneSkipLast.rawValue) {
            context.setFillColor(CGColor(gray:1,alpha:1));context.fill(CGRect(x:0,y:0,width:bounds.width*scale,height:bounds.height*scale))
            context.scaleBy(x:scale,y:scale);context.translateBy(x:-bounds.minX,y:-bounds.minY);page.draw(with:.mediaBox,to:context)
            if let image=context.makeImage() {
                let request=VNRecognizeTextRequest();request.recognitionLevel = .accurate
                request.recognitionLanguages=["en-US","zh-Hans"];request.usesLanguageCorrection=true
                do {
                    try VNImageRequestHandler(cgImage:image).perform([request])
                    text=(request.results ?? []).compactMap{$0.topCandidates(1).first?.string}.joined(separator:"\n")
                    ocrPages.append(index+1)
                } catch { }
            }
        }
    }
    if useOCR && text.trimmingCharacters(in:.whitespacesAndNewlines).count<20 { unreadable.append(index+1) }
    pages.append(["page":index+1,"text":text,"ocr":ocrPages.contains(index+1)])
}
let output=try JSONSerialization.data(withJSONObject:["pages":pages,"total":document.pageCount,"ocr_pages":ocrPages,"unreadable_pages":unreadable])
FileHandle.standardOutput.write(output)
