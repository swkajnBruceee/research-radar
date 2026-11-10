import AppKit
import ImageIO
let size=1024
let bitmap=CGContext(data:nil,width:size,height:size,bitsPerComponent:8,bytesPerRow:size*4,space:CGColorSpaceCreateDeviceRGB(),bitmapInfo:CGImageAlphaInfo.noneSkipLast.rawValue)!
let context=NSGraphicsContext(cgContext:bitmap,flipped:false)
NSGraphicsContext.saveGraphicsState();NSGraphicsContext.current=context
NSColor(srgbRed:0.075,green:0.235,blue:0.195,alpha:1).setFill();NSBezierPath(rect:NSRect(x:0,y:0,width:size,height:size)).fill()
NSColor(srgbRed:0.76,green:0.91,blue:0.67,alpha:0.14).setFill()
let sweep=NSBezierPath();sweep.move(to:NSPoint(x:512,y:512));sweep.appendArc(withCenter:NSPoint(x:512,y:512),radius:330,startAngle:0,endAngle:65);sweep.close();sweep.fill()
NSColor(srgbRed:0.76,green:0.91,blue:0.67,alpha:1).setStroke()
for r in [330.0,216.0,105.0] { let circle=NSBezierPath(ovalIn:NSRect(x:512-r,y:512-r,width:r*2,height:r*2));circle.lineWidth=14;circle.stroke() }
let line=NSBezierPath();line.move(to:NSPoint(x:512,y:842));line.line(to:NSPoint(x:512,y:512));line.line(to:NSPoint(x:780,y:330));line.lineWidth=20;line.lineCapStyle = .round;line.stroke()
NSColor(srgbRed:0.76,green:0.91,blue:0.67,alpha:1).setFill()
NSBezierPath(ovalIn:NSRect(x:490,y:490,width:44,height:44)).fill();NSBezierPath(ovalIn:NSRect(x:680,y:660,width:40,height:40)).fill()
NSGraphicsContext.restoreGraphicsState()
let destination=CGImageDestinationCreateWithURL(URL(fileURLWithPath:CommandLine.arguments[1]) as CFURL,"public.png" as CFString,1,nil)!
CGImageDestinationAddImage(destination,bitmap.makeImage()!,nil)
assert(CGImageDestinationFinalize(destination))
