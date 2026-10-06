# Run from any directory. Creates the three PNG wireframes beside this script.
Add-Type -AssemblyName System.Drawing
$outputDir = $PSScriptRoot
if (-not $outputDir) { $outputDir = Join-Path (Get-Location) 'docs/wireframes' }
$font = New-Object System.Drawing.Font('Segoe UI', 13)
$heading = New-Object System.Drawing.Font('Segoe UI', 23, ([System.Drawing.FontStyle]::Bold))
$small = New-Object System.Drawing.Font('Segoe UI', 11)
$ink = [System.Drawing.Brushes]::Black
$gray = [System.Drawing.Brushes]::DimGray
$line = New-Object System.Drawing.Pen([System.Drawing.Color]::LightGray, 1)
function TextAt($text, $x, $y, $width = 1040, $height = 50, $style = $font) {
    $g.DrawString($text, $style, $ink, (New-Object System.Drawing.RectangleF($x,$y,$width,$height)))
}
function Box($text, $x, $y, $width, $height) {
    $g.FillRectangle([System.Drawing.Brushes]::WhiteSmoke,$x,$y,$width,$height)
    $g.DrawRectangle($line,$x,$y,$width,$height)
    TextAt $text ($x+16) ($y+12) ($width-32) ($height-20)
}
$tabs = @('Hỏi đáp','Lộ trình','Phân tích đề cương')
for ($screen=0; $screen -lt 3; $screen++) {
    $bitmap = New-Object System.Drawing.Bitmap(1200,940)
    $g = [System.Drawing.Graphics]::FromImage($bitmap)
    $g.Clear([System.Drawing.Color]::White)
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    TextAt 'SYLLABUS / SGU' 48 28 700 48 $heading
    TextAt 'Phác thảo TV4 · 07/10/2026 · Dữ liệu minh họa, chưa xác minh' 48 82 1100 30 $small
    for ($i=0; $i -lt 3; $i++) {
        $x=48+$i*368
        Box $tabs[$i] $x 132 352 52
        if ($i -eq $screen) { $g.FillRectangle([System.Drawing.Brushes]::Black,$x,181,352,4) }
    }
    if ($screen -eq 0) {
        TextAt 'Hỏi về đề cương môn học' 48 216 1000 46 $heading
        TextAt 'Môn học (không bắt buộc)' 48 282 500 30
        Box 'Tất cả môn / chọn một môn' 48 316 400 54
        TextAt 'Câu hỏi của bạn' 48 396 700 30
        Box 'Môn này được đánh giá theo những hình thức nào?' 48 432 760 96
        Box 'Gửi câu hỏi' 844 432 308 56
        TextAt 'Câu trả lời' 48 560 720 32
        Box 'Kết quả trả lời xuất hiện ở đây, kèm số nguồn [1].' 48 598 760 114
        Box "Nguồn [1]`nTên môn · Mục 9 · Trang n" 844 598 308 114
        Box 'Xem các đoạn được truy xuất  >  Nội dung gốc + nguồn' 48 740 1104 58
        TextAt 'Trạng thái: chưa gửi / đang tìm / có kết quả / lỗi kết nối. Khi dịch vụ lỗi, vẫn hiện đoạn trích nếu có.' 48 832 1104 62 $small
        $name='01-hoi-dap.png'
    } elseif ($screen -eq 1) {
        TextAt 'Lập lộ trình học' 48 216 1000 46 $heading
        TextAt 'Môn muốn học' 48 286 340 30
        Box 'Chọn môn đích' 48 322 336 54
        TextAt 'Các môn đã hoàn thành' 48 402 336 30
        Box "Chọn nhiều môn`n[ ] Môn A`n[ ] Môn B" 48 440 336 128
        TextAt 'Tín chỉ tối đa mỗi kỳ' 48 594 336 30
        Box '20' 48 632 336 52
        Box 'Tạo lộ trình' 48 714 336 56
        TextAt 'Kế hoạch đề xuất' 428 286 724 34
        Box "Học kỳ 1 · Tổng tín chỉ`nDanh sách môn + tín chỉ" 428 334 724 102
        Box "Học kỳ 2 · Tổng tín chỉ`nDanh sách môn + tín chỉ" 428 458 724 102
        Box 'Vùng đồ thị tiên quyết (phát triển ở tuần sau)' 428 584 724 96
        Box "Cảnh báo và gợi ý nên học trước`nTách biệt tiên quyết bắt buộc với gợi ý." 428 704 724 96
        TextAt 'Nếu không có lộ trình: hiển thị lý do từ API. Đây là bố cục dự kiến, chưa có kết quả học vụ thật.' 48 846 1104 52 $small
        $name='02-lo-trinh.png'
    } else {
        TextAt 'Phân tích đề cương' 48 216 1000 46 $heading
        Box 'Kéo thả hoặc chọn tệp PDF' 48 282 790 80
        Box 'Phân tích' 868 294 284 56
        Box 'Tên môn · Mã môn | Cảnh báo các mục còn thiếu' 48 386 1104 58
        TextAt 'Cấu trúc đề cương' 48 472 480 32
        Box "01  Thông tin tổng quát`n02  Mô tả học phần`n03  Mục tiêu học phần`n04  Chuẩn đầu ra`n05  Nội dung chi tiết`n06  Học liệu`n07  Hướng dẫn tổ chức dạy học`n08  Quy định`n09  Phương pháp đánh giá`n10  Phụ trách học phần" 48 514 470 300
        TextAt 'Chuẩn đầu ra (CLO)' 558 472 594 32
        Box "CLO | Nội dung | Bloom | Độ tin cậy`nG1   | Văn bản từ đề cương | Chưa có`nG2   | Văn bản từ đề cương | Chưa có" 558 514 594 130
        Box "Vùng biểu đồ phân bố Bloom`nHiện khi có kết quả phân loại.`nChưa phân loại khác với lớp 0." 558 670 594 144
        TextAt 'Mỗi mục có trạng thái Có / Thiếu và xem nội dung. PDF lỗi: thông báo chọn lại; giữ thông tin tệp.' 48 850 1104 52 $small
        $name='03-phan-tich.png'
    }
    $bitmap.Save((Join-Path $outputDir $name),[System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bitmap.Dispose()
}
$font.Dispose(); $heading.Dispose(); $small.Dispose(); $line.Dispose()
