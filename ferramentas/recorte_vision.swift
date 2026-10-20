// A máscara da pessoa quadro a quadro com o Vision do macOS (VNGeneratePersonSegmentationRequest, .accurate): o
// recorte.py compila e roda este arquivo. Sai no stdout em cinza 8 bits, quadro a quadro, no tamanho do vídeo.
import AVFoundation
import CoreImage
import Vision

let url = URL(fileURLWithPath: CommandLine.arguments[1])
let asset = AVURLAsset(url: url)
let track = asset.tracks(withMediaType: .video)[0]
let reader = try! AVAssetReader(asset: asset)
let out = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
reader.add(out)
reader.startReading()
let size = track.naturalSize
let W = Int(size.width), H = Int(size.height)
let ctx = CIContext()
let req = VNGeneratePersonSegmentationRequest()
req.qualityLevel = .accurate
req.outputPixelFormat = kCVPixelFormatType_OneComponent8
var buf = [UInt8](repeating: 0, count: W * H)
var n = 0
while let sample = out.copyNextSampleBuffer(), let px = CMSampleBufferGetImageBuffer(sample) {
    let h = VNImageRequestHandler(cvPixelBuffer: px, options: [:])
    try! h.perform([req])
    let mask = req.results!.first!.pixelBuffer
    let img = CIImage(cvPixelBuffer: mask).transformed(by: CGAffineTransform(scaleX: CGFloat(W) / CGFloat(CVPixelBufferGetWidth(mask)),
                                                                            y: CGFloat(H) / CGFloat(CVPixelBufferGetHeight(mask))))
    ctx.render(img, toBitmap: &buf, rowBytes: W, bounds: CGRect(x: 0, y: 0, width: W, height: H), format: .L8, colorSpace: nil)
    FileHandle.standardOutput.write(Data(buf))
    n += 1
    if n % 240 == 0 { FileHandle.standardError.write("\(n) quadros\n".data(using: .utf8)!) }
}
FileHandle.standardError.write("pronto: \(n) quadros \(W)x\(H)\n".data(using: .utf8)!)
