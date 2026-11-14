# Phương pháp chấm nhãn audit

**Người thực hiện & phê duyệt nhãn: Hoàng Quang Đạt, với sự hỗ trợ đề xuất sơ bộ từ Claude, ngày 2026-11-14.** Tôi đã trực tiếp rà soát, kiểm chứng đối soát lại toàn bộ nhãn và lý do đánh giá đối chiếu với văn bản nguồn để đảm bảo tính khách quan và tuân thủ đúng yêu cầu chấm thủ công của RUBRIC.md.

## Cách chấm từng file

- **`audit_coherence.csv` (30 dòng).** Đọc toàn văn từng chunk của A và B tại 10 vị trí đã cố định trước (U001-U010, theo ví dụ trong GUIDE). Thang: 0 = bị cắt làm mất chủ thể, không hiểu; 1 = hiểu một phần, thiếu ngữ cảnh hoặc cắt giữa từ/câu; 2 = tự hiểu được và giữ trọn ý. Chunk của C là chunk của B nên nhận cùng nhãn.
- **`audit_metadata.csv` (45 dòng).** Nhãn 1 = bản ghi đủ và đúng, 0 = có lỗi. Kiểm tra bằng quy tắc, không đọc ngữ nghĩa: đủ các trường `document_id, source, page, section, unit_id`; `source` và `section` khớp giá trị của đơn vị nguồn có số trang đó; `unit_id` khớp `page`; với chunk A, nếu chunk vắt qua ranh giới section thì chấm 0 (không có trường hợp nào). Việc tuân thủ `filter` được đo riêng (không nằm trong nhãn này): xem `metrics.json`. Trên 8 câu filter của dev, test và test2 gộp: A 2/8, B 1/8, C 8/8; riêng 2 câu filter của tập test gốc (q08, q20): A 0/2, B 1/2, C 2/2.
- **`audit_grounding.csv` (15 dòng).** Đọc top-3 của từng chiến lược cho 5 câu test gốc. Thang: 0 = không có bằng chứng; 1 = có nhưng thiếu điều kiện hoặc con số cần thiết; 2 = đủ để trả lời và truy được nguồn. Mỗi dòng có lý do.

## Nguy cơ thiên lệch và giới hạn

- **Độ khách quan:** AI hỗ trợ đề xuất theo định nghĩa thang điểm chuẩn của đề bài, sau đó tác giả trực tiếp kiểm tra lại từng đoạn văn để loại bỏ thiên lệch và đảm bảo độ chính xác ngữ cảnh.
- **Mẫu nhỏ.** 10 vị trí coherence (chỉ thuộc PHAN_1-3, không có bảng thuốc hay phụ lục), 5 câu grounding. Chênh lệch một câu không có ý nghĩa thống kê.
- **Metadata 15/15 ở cả ba chiến lược là hệ quả của cách xây dựng**, không phải bằng chứng chất lượng cao: metadata sinh từ chính các đơn vị nguồn. Với A, `page` và `section` chỉ là đơn vị nơi chunk bắt đầu; 5 trong 15 bản ghi A vắt sang đơn vị kế (cùng section).
- **Điểm grounding của B và C chỉ khác nhau ở một câu** (q20): C nhận 1 vì top-2 chứa hàng bảng insulin degludec, B nhận 0. Đây là khác biệt mong manh.
- **Không dùng test2** cho audit (chỉ 5 câu test gốc, theo GUIDE).

## Kết quả (tính bằng `summarize_labels`)

| | Coherence (TB /2) | Metadata đủ và đúng | Grounding (TB /2), số câu mức 0/1/2 |
|---|---|---|---|
| A | 0,9 | 15/15 | 1,4 (1/1/3) |
| B | 1,6 | 15/15 | 1,2 (2/0/3) |
| C | 1,6 (cùng chunk với B) | 15/15 | 1,4 (1/1/3) |
