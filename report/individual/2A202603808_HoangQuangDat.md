# Báo cáo cá nhân — Day 6

**Họ tên: Hoàng Quang Đạt · MSSV: 2A202603808 · Lớp: L3B**

---

## 1. Dữ liệu và pipeline

* **Chủ đề & Nguồn:** Hướng dẫn chẩn đoán và điều trị đái tháo đường típ 2 theo Quyết định 5481/QĐ-BYT (30/12/2020) của Bộ Y tế. Văn bản tải từ thuvienphapluat.vn (URL và mã hash SHA256 lưu tại `starter/data/manifest.json`). File docx gốc không đưa vào repo nhằm tuân thủ quy định phân phối dữ liệu; người chấm có thể tải lại theo URL trong manifest.
* **Quy mô & Quy tắc tính trang:** File docx không có số trang in cố định =>  chia tài liệu thành các "đơn vị nguồn" (source unit) liên tiếp trong cùng section với độ dài tối thiểu 1.500 ký tự chuẩn hóa. Toàn bộ tài liệu gồm 80 đơn vị (137.094 ký tự), trong đó 79 đơn vị hợp lệ $\ge 1.500$ ký tự (vượt yêu cầu tối thiểu 30 trang), 1 đơn vị ngắn (Phụ lục 3: 1.335 ký tự).
* **Chuẩn hóa & Xử lý lỗi:** Chuẩn hóa Unicode NFC, loại bỏ khoảng trắng thừa/NBSP, làm phẳng bảng biểu thành các dòng text. Loại bỏ phần mở đầu hành chính (quyết định, danh sách ban soạn thảo) và phần tài liệu tham khảo cuối bài; 3 lưu đồ dạng ảnh không trích xuất được text. Chi tiết các đoạn rỗng/ảnh được ghi nhận tại `starter/results/errors.log`.
* **Embedding & Vector Store:**
  * Model: `BAAI/bge-m3` chạy local (CPU, `sentence-transformers`, 1024 chiều, chuẩn hóa L2). Chi phí: 0 USD.
  * Vector Store: PostgreSQL 16 + pgvector qua Docker, tìm kiếm chính xác Cosine distance (`score = 1 - distance`). Cơ chế upsert theo khóa `(strategy, chunk_id)` đảm bảo nạp lại không bị nhân đôi dữ liệu.
* **Metadata & Bộ lọc:** Mỗi chunk gồm `document_id`, `source`, `page` (thứ tự đơn vị nguồn), `unit_id` và trường lọc `section`. Trường `section` có 13 giá trị tự nhiên từ văn bản (`PHAN_1` đến `PHAN_10`, `PHU_LUC_01` đến `PHU_LUC_03`), giúp người dùng khoanh vùng tìm kiếm chính xác theo chuyên khoa/chủ đề.

---

## 2. Cấu hình và benchmark

* **Ba cấu hình thử nghiệm:**
  * **Strategy A (Fixed-size):** Cắt cố định 500 ký tự, overlap 50 ký tự trên toàn bộ văn bản. Tạo ra 305 chunk. Không dùng bộ lọc.
  * **Strategy B (By Paragraph):** Cắt theo đoạn văn tự nhiên, ngắt câu hợp lý, khống chế tối đa 800 ký tự. Tạo ra 234 chunk. Không dùng bộ lọc.
  * **Strategy C (Metadata Filter):** Dùng chung tập chunk và vector của Strategy B, chỉ kích hoạt thêm bộ lọc `section` khi câu hỏi có yêu cầu phạm vi.
* **Bộ Benchmark:** Gồm 20 câu hỏi gốc (`starter/benchmark/questions.json`) chia thành **15 câu dev / 5 câu test**, trong đó có **4 câu có filter** (2 dev, 2 test). Bổ sung 10 câu `test2` độc lập (`questions_test2.json`) để kiểm chứng thêm. Mỗi câu đều có đáp án, số trang nguồn (`gold_page`) và trích dẫn bằng chứng (`evidence_quote`) được hàm `verify_questions` kiểm chứng đối soát 100% với văn bản gốc.
* **Tiêu chí chọn cấu hình (đặt trước khi chạy test):** Ưu tiên Evidence Hit@3 trên tập dev; nếu hòa thì xét Hit@1 dev, tiếp đến điểm Grounding trên test và tối ưu tài nguyên. Strategy C được chọn nếu Hit không giảm và đạt tỷ lệ tuân thủ filter 100%.

---

## 3. Kết quả thực nghiệm

### Bảng 1: Hiệu năng truy xuất và tài nguyên
| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Số chunk | Thời gian ingest | Chi phí |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **A** | dev | 7/15 | 7/15 | 305 | ~130s | 0 USD |
| **A** | test | 1/5 | 2/5 | 305 | — | 0 USD |
| **A** | test2 (held-out) | 6/10 | 8/10 | 305 | — | 0 USD |
| **B** | dev | 9/15 | 13/15 | 234 | ~110s | 0 USD |
| **B** | test | 3/5 | 3/5 | 234 | — | 0 USD |
| **B** | test2 (held-out) | 6/10 | 9/10 | 234 | — | 0 USD |
| **C** | dev | 9/15 | 13/15 | 234 | Dùng chung B | 0 USD |
| **C** | test | 3/5 | 3/5 | 234 | Dùng chung B | 0 USD |
| **C** | test2 (held-out) | 6/10 | 9/10 | 234 | Dùng chung B | 0 USD |

### Bảng 2: Đánh giá chất lượng định tính thủ công
| Strategy | Coherence TB /2 (10 vị trí) | Metadata đủ & đúng (15 bản ghi) | Tuân thủ Filter (8 câu) | Grounding TB /2 (5 câu test) |
|---|:---:|:---:|:---:|:---:|
| **A** | 0.9 | 15/15 | 2/8 (25%) | 1.4 (1/1/3) |
| **B** | 1.6 | 15/15 | 1/8 (12.5%) | 1.2 (2/0/3) |
| **C** | 1.6 | 15/15 | **8/8 (100%)** | **1.4** (1/1/3) |

* **Đường dẫn minh chứng:** Log trace chi tiết tại `starter/results/traces_{A,B,C}_{dev,test,test2}.jsonl`. Bảng chấm nhãn thủ công tại `audit_coherence.csv`, `audit_metadata.csv`, `audit_grounding.csv` và phương pháp tại `audit_method.md`.

---

## 4. Phân tích và kết luận

* **So sánh Strategy A và Strategy B (Tác động của Chunking):**
  * *Retrieval:* B vượt trội hoàn toàn so với A trên tập dev (Hit@3 đạt 13/15 so với 7/15). Tính gộp 30 câu, B đạt Hit@3 là 25/30 trong khi A chỉ đạt 17/30.
  * *Coherence:* B đạt 1.6/2 điểm mạch lạc, trong khi A chỉ đạt 0.9/2. Các chunk của A bị cắt cơ học giữa từ (ví dụ `bị bện`), cắt giữa danh sách tiêu chuẩn chẩn đoán hoặc gãy hàng bảng biểu. B giữ trọn vẹn đoạn văn và tiêu đề nên ngữ cảnh rõ ràng.
  * *Tài nguyên:* B tiết kiệm hơn (234 chunk so với 305 chunk của A), giúp giảm thời gian nhúng và dung lượng lưu trữ vector.
* **So sánh Strategy B và Strategy C (Tác động của Metadata Filter):**
  * Về số lượng câu Hit, B và C hòa nhau (đều 13/15 dev, 3/5 test).
  * Tuy nhiên, C vượt trội hoàn toàn về **độ chính xác phạm vi**: ở các câu hỏi có điều kiện lọc, 100% top-3 chunk của C nằm đúng section yêu cầu (8/8 câu), trong khi B chỉ đạt 1/8 (7 câu còn lại bị lẫn chunk từ các phần khác do trùng lặp từ khóa). Điểm Grounding của C nhỉnh hơn B (1.4 so với 1.2) nhờ giữ đúng bảng tra cứu liều thuốc ở câu q20.
* **Hai ví dụ lỗi truy xuất điển hình:**
  1. *Câu q18 (test - liều dùng thuốc GLP-1 tiêm 1 lần/ngày):* Cả 3 chiến lược đều trượt. Lý do: câu hỏi không nêu đích danh hoạt chất Liraglutide, còn chunk chứa bảng liều lại không lặp lại cụm từ "GLP-1", dẫn đến vector search ưu tiên nhầm sang đoạn mô tả cơ chế chung của nhóm GLP-1.
  2. *Câu q20 (test - khoảng cách tiêm tối thiểu của insulin degludec):* Cả 3 chiến lược đều không đạt Hit@3. Với C, dù bộ lọc đã khoanh vùng đúng Phụ lục 2 nhưng đoạn chứa quy định "tối thiểu 8 giờ" (trang 75) có điểm tương đồng thấp hơn các đoạn mô tả thời gian bán thải 42 giờ.
* **Chiến lược được lựa chọn: Strategy C**
  * Đáp ứng trọn vẹn các tiêu chí đã đặt ra: Hit@3 cao ngang B, tính mạch lạc tốt (1.6/2), và đảm bảo 100% kết quả trả về đúng phạm vi chuyên môn khi người dùng chỉ định phần cần tra cứu.
* **Hạn chế & Hướng cải tiến:**
  * *Hạn chế:* Tập test nhỏ (5 câu) nên chênh lệch định lượng giữa B và C chưa lớn. Bộ lọc cứng của C phụ thuộc vào việc người dùng chỉ định đúng section; nếu người dùng chọn sai section thì sẽ bị lọc mất đáp án.
  * *Cải tiến:* Bổ sung tìm kiếm kết hợp từ khóa (Hybrid Search: BM25 + Vector) và Reranker để bắt chính xác các tên thuốc hiếm/chỉ số cụ thể (khắc phục lỗi q18); áp dụng phân loại mềm câu hỏi sang section thay vì lọc cứng.

---

## 5. Công cụ AI và cách kiểm tra

* **Công cụ sử dụng:** Sử dụng AI (Claude Code) hỗ trợ lập trình các module pipeline, xây dựng bộ unit test và gợi ý các câu hỏi benchmark từ văn bản nguồn.
* **Cách kiểm tra & xác thực:**
  * Kiểm thử tự động toàn bộ chức năng pipeline bằng 83 unit test (`pytest`, 100% pass).
  * Trực tiếp rà soát, đối soát thủ công từng câu hỏi và đoạn trích bằng chứng (`evidence_quote`) với văn bản gốc của Bộ Y tế thông qua hàm `verify_questions`.
  * Kiểm tra tính toàn vẹn của các file log trace thực tế (`.jsonl`) và trực tiếp duyệt lại các nhãn chấm audit trong các file CSV trước khi tổng hợp số liệu vào báo cáo.
