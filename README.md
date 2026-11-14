# Tình hình giải ngân vốn đầu tư năm 2026, UBND phường Tân Lập

Trang công khai số liệu tổng hợp, tự cập nhật lúc 06:40 hằng ngày từ tab "Tổng hợp" của bảng theo dõi do Trung tâm Cung ứng dịch vụ sự nghiệp công cập nhật.

- `index.html`, `logo.png`: trang được đăng.
- `tonghop.json`: số liệu tab Tổng hợp lần tải gần nhất. `nq27.json`: Biểu 02 kèm Nghị quyết số 27/NQ-HĐND.
- `fetch.py`: tải số liệu (link CSV lưu trong secret `SHEET_CSV_URL`); `build.py`, `template.html`: dựng trang. Nếu tổng các nhóm không khớp dòng TỔNG CỘNG, lần cập nhật dừng lại và trang giữ số hôm trước.
- `.github/workflows/cap-nhat.yml`: lịch chạy hằng ngày.
