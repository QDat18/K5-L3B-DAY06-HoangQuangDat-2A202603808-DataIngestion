# Tiêu chí chọn chiến lược

Chốt ngày 2026-11-14, **trước khi chạy đánh giá và trước khi đọc kết quả test**. Ba chiến lược: **A** (cắt cố định 500 ký tự, chồng 50), **B** (theo đoạn, tối đa 800 ký tự), **C** (= B + lọc `section`, chỉ áp dụng cho câu có filter; câu không có filter chạy B không lọc).

## Định nghĩa một "hit"

Một chunk là hit cho một câu khi **cả hai** điều kiện sau đúng:
- `chunk.page` thuộc `gold_page` của câu;
- văn bản chunk, sau `normalize_text`, chứa trọn `evidence_quote`.

Ngoại lệ ghi rõ khi báo cáo:
- Evidence bị tách qua nhiều chunk hoặc chunk A bắt đầu ở đơn vị trước đơn vị gold: tính là **không hit** theo cách chấm tự động, ghi thành lỗi chunking, và người chấm thủ công có thể xác nhận bằng chứng tương đương.
- q17 có hai trang hợp lệ (45, 46); trang 46 cần xác nhận thủ công vì trích dẫn tự động chỉ khớp ở trang 45.

Hit@1 = số câu có hit ở top-1 / số câu. Evidence Hit@3 = số câu có ít nhất một hit trong top-3 / số câu. Luôn báo số tử/mẫu.

## Thứ tự ưu tiên (từ điển)

1. **Evidence Hit@3 trên 15 câu dev.** Chênh lệch từ 1 câu trở xuống coi là hòa (mẫu nhỏ).
2. **Hit@1 trên dev**, nếu còn hòa.
3. **Grounding thủ công trên 5 câu test** (thang 0-2 theo GUIDE.md), nếu còn hòa.
4. **Tài nguyên**: số chunk, thời gian embed, dung lượng lưu trữ; chiến lược ít tốn hơn thắng.

Các tiêu chí còn lại (coherence trên 10 vị trí, tính hữu dụng của metadata) vẫn được báo cáo nhưng **không** dùng để chọn, trừ khi hai chiến lược hòa ở cả bốn bước trên.

## Quy tắc riêng cho C so với B

- C và B giống hệt nhau trên câu không có filter, nên so sánh B-C chỉ có ý nghĩa trên **4 câu filter** (q04, q08, q09, q20). Báo số tử/mẫu trên tập con này.
- Chọn C thay B chỉ khi trên các câu filter C có Hit@3 **không thấp hơn** B và tỷ lệ tuân thủ filter trong top-3 là 4/4.
- C đòi hỏi giá trị `section` do người dùng hoặc ngữ cảnh cung cấp trước khi truy xuất. Chi phí này được ghi vào phần đánh đổi.

## Ràng buộc để giữ công bằng

- Cùng một embedding model (`BAAI/bge-m3`), cùng cosine, cùng corpus, cùng câu hỏi cho cả ba chiến lược.
- Không sửa tham số chunking sau khi xem kết quả test. Nếu buộc phải sửa, ghi rõ trong báo cáo và tạo câu test mới.
- Không tự điền nhãn thủ công (coherence, grounding): nhãn do tác giả chấm.
