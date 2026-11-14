# Cách chia dev/test và nguy cơ rò rỉ

Ghi ngày 2026-11-14, **trước khi chạy bất kỳ truy xuất nào** trên bộ câu hỏi này. Corpus: QĐ 5481/QĐ-BYT (80 đơn vị, 13 section). File câu hỏi: `benchmark/questions.json` (20 câu).

## Kết quả chia

| Split | Số câu | ID |
|---|---|---|
| dev | 15 | q01-q07, q09, q10, q12, q13, q15, q16, q17, q19 |
| test | 5 | q08, q11, q14, q18, q20 |

Câu có filter (`section`): q04, q09 (dev), q08, q20 (test). Tổng 4 câu, trong đó 2 ở test.

## Quy tắc chia (chốt trước khi chạy)

Chia **thủ công**, không ngẫu nhiên, theo các quy tắc sau:

1. Dev đủ rộng để chọn và chỉnh chiến lược; test chỉ dùng để báo cáo, không dùng để chỉnh.
2. Test có ít nhất 1 câu filter (thực tế có 2: q08, q20).
3. Mỗi câu test nằm ở một section khác nhau: PHAN_9 (q08), PHAN_4 (q11), PHAN_2 (q14), PHU_LUC_01 (q18), PHU_LUC_02 (q20).
4. Test gồm các loại câu khác nhau: filter (2), bảng có đoạn gây nhiễu (q11, q14), diễn đạt lại không nêu tên thuốc (q18).
5. Các câu đa nguồn (q17) và câu đơn giản nhất (q01, q02) để ở dev, vì chúng giúp chẩn đoán lỗi.

Loại câu trong toàn bộ 20 câu: trực tiếp (q01, q02), diễn đạt lại (q03, q12, q13, q18), điều kiện/ngoại lệ (q05, q15), suy luận (q06, q07, q16, q19), phủ định (q10), bảng có đoạn gây nhiễu (q11, q14), cần filter (q04, q08, q09, q20), đa nguồn (q17).

## Nguy cơ rò rỉ và hạn chế

- **Cùng một người soạn dev và test.** Claude viết cả 20 câu khi đã đọc phần lớn corpus, và người dùng đã xem cả câu test lúc duyệt. Vì vậy tập test không "mù" với tác giả. Cam kết: không dùng kết quả của 5 câu test để chỉnh chunking, tham số hay tiêu chí chọn.
- **Tham số chunking chốt trước.** A: 500 ký tự, chồng 50. B: tối đa 800 ký tự. Các giá trị này do Claude chọn từ trước và chỉ được chỉnh dựa trên dev. Nếu có chỉnh sau khi xem test thì phải ghi rõ trong báo cáo và tạo thêm câu test mới.
- **Trùng chủ đề giữa dev và test.** q13 (dev, insulin NPH cách nhau 11-12 giờ) và q20 (test, degludec cách nhau tối thiểu 8 giờ) cùng chủ đề khoảng cách giữa các mũi tiêm; q06 (dev) và q08 (test) cùng chủ đề insulin. Đây là chủ ý để test có đoạn gây nhiễu thật, nhưng nghĩa là test không hoàn toàn tách biệt về chủ đề với dev. Không có câu hỏi hay `evidence_quote` nào dùng chung.
- **Mẫu rất nhỏ.** 5 câu test cho phép chênh 1 câu tương đương 20 điểm phần trăm. Báo cáo cần ghi số tử/mẫu và không kết luận mạnh từ chênh lệch 1 câu.
- **Evidence chỉ lấy từ văn bản.** Không có câu nào dựa vào 3 lưu đồ đã bị loại. Bảng nhiễm toan ketone/ALTT ở PHAN_7 cố ý không dùng vì nhãn mức độ bị mất khi làm phẳng bảng.
- **Phủ section chưa đều.** PHAN_1, PHAN_3 và PHU_LUC_03 không có câu hỏi nào; PHAN_4 có 7 câu. Kết quả không nên được suy rộng cho các section chưa có câu.
- **q17 có 2 nguồn hợp lệ** (`gold_page` = [45, 46]); trích dẫn tự động chỉ khớp ở trang 45, trang 46 cần xác nhận thủ công là bằng chứng tương đương.

## Bổ sung: tập `test2` (ghi ngày 2026-11-14, TRƯỚC khi chạy test2)

Sau khi chạy `test` lần đầu (A 2/5, B 3/5, C 3/5 Hit@3), mẫu 5 câu quá nhỏ để so sánh B với C, nên soạn thêm tập giữ riêng `test2` trong `benchmark/questions_test2.json`.

- **Số câu:** 10 (q21-q30), trong đó 4 câu filter (q21 `PHAN_4`, q26 `PHAN_8`, q28 `PHU_LUC_02`, q30 `PHAN_10`). Cộng với 4 câu filter cũ, tổng cộng 8 câu filter, 6 câu nằm ngoài dev.
- **Tình trạng:** `test` cũ **đã bị xem** (kết quả và các trace đã được đọc khi chọn chiến lược). `test2` được soạn và duyệt **trước khi chạy bất kỳ truy xuất nào trên nó**; cấu hình A (500/50), B (tối đa 800), C và embedding `bge-m3` giữ nguyên như đã chốt, không có chiến lược D.
- **Cách chạy:** `python -m src.run --split test2`, đúng một lần (chạy lần hai bị chặn trừ `--force-test` và phải ghi vào báo cáo). `--split all` chỉ gồm dev và test, không gồm test2.
- **Cách báo cáo:** báo riêng `test`, `test2`, và gộp (`held_out` = test + test2, 15 câu). Không chỉnh gì dựa trên test2.
- **Chủ đề mới:** dinh dưỡng, huyết áp, lipid, bàn chân, tác dụng phụ của thuốc, hiện tượng Somogyi, danh mục thuốc thiết yếu, CGM. Không có câu nào trùng câu hỏi hay `evidence_quote` với bộ 20 câu đầu (có test kiểm tra).
- **Hạn chế còn lại:** cùng một người soạn (Claude), người dùng đã duyệt từng câu; gộp 15 câu vẫn là mẫu nhỏ; q25 phản ánh một chỗ mâu thuẫn thật giữa Bảng 4 và mục lipid trong tài liệu gốc.
