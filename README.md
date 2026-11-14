# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Bài làm của Hoàng Quang Đạt (2A202603808): cách setup và chạy

Đề tài: đái tháo đường típ 2, QĐ 5481/QĐ-BYT (tiếng Việt). Báo cáo: [report/individual/2A202603808_HoangQuangDat.md](report/individual/2A202603808_HoangQuangDat.md). Code ở `starter/src/`, benchmark ở `starter/benchmark/`, kết quả ở `starter/results/`, manifest ở `starter/data/manifest.json`, nhật ký thí nghiệm ở `artifacts/experiment_log.csv`.

**Dữ liệu.** File gốc không nằm trong repo (quyền tái phân phối chưa xác minh). Tải về từ URL trong `starter/data/manifest.json`, lưu thành `starter/data/raw/5481_QD-BYT_460925.docx` và đối chiếu sha256 trong manifest.

**Cài đặt** (Python 3.11-3.14, Docker; chạy từ `starter/`, trên Windows PowerShell):

```bash
cd starter
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

**Chạy** (lần đầu tải model `BAAI/bge-m3`, vài GB; CPU mất khoảng 2-4 phút mỗi lần nạp):

```bash
python -m pytest -m "not slow"        # test nhanh (cần Docker cho tests/test_store.py)
python -m pytest                      # thêm test embedding (tải model)
python -m src.run --split dev         # nạp A và B, chạy A/B/C trên 15 câu dev
python -m src.run --split test        # đúng MỘT lần; lần hai bị chặn trừ khi dùng --force-test
python -m src.run --split test2       # tập giữ riêng 10 câu, cũng chỉ chạy một lần
python -m src.audit                   # sinh lại mẫu audit (sẽ ghi đè nhãn đã chấm trong results/audit_*.csv)
```

Lưu ý: `python -m src.audit` ghi đè các file `audit_*.csv`; sao lưu nhãn trước khi chạy lại. Nhãn audit hiện có do Claude chấm (xem `starter/results/audit_method.md`).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.
