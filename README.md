# Aura Retention AI – Web giữ chân hội viên (Aura Fitness & Yoga Center)

Web nội bộ tính **Churn Score**, **CLV**, **Priority Score** và kịch bản can thiệp đúng theo tài liệu Aura,
cộng thêm **AI học máy** dự báo xác suất rời bỏ trong 90 ngày.

## Cách chạy
1. Cài Python 3.12–3.14 (bản chính thức từ python.org, không dùng bản MSYS2).
2. Chạy `run.py` (VS Code/PyCharm bấm Run, hoặc gõ `py -V:3.14 run.py`).
3. Lần đầu tự cài thư viện, tạo dữ liệu mẫu, cho AI học (~1 phút) rồi mở trình duyệt tại `http://localhost:8501`.

**Chỉ cần chạy một lần và để cửa sổ đó mở.** Khi có dữ liệu mới, vào trang **Cập nhật dữ liệu** trên web –
không cần chạy lại `run.py`, không cần tải lại các trang khác bằng tay.

Toàn bộ thư viện giao diện (Bootstrap, biểu tượng, biểu đồ, font) đã đóng gói sẵn trong `static/vendor/`,
nên web chạy được cả khi máy không có Internet.

## Các trang
| Trang | Dùng để |
|---|---|
| Trang chủ | Danh sách khách nên gọi trước và vầng aura toàn bộ hội viên |
| Cần gọi | Lọc theo kịch bản / mức rủi ro / CLV, bấm vào khách để xem lý do, tin nhắn mẫu (sao chép 1 chạm), ghi kết quả gọi; xuất Excel/CSV |
| Hội viên | Đồng hồ Churn Score, điểm từng nhóm chỉ số, AI dự báo, CLV, biểu đồ tập theo tuần, gói thẻ, PT, đánh giá, lịch sử liên hệ |
| Dự báo AI | Độ chính xác AI so với quy tắc, kiểm chứng, yếu tố ảnh hưởng, danh sách "rủi ro ẩn" |
| Doanh thu & CLV | ARPU, churn tháng, tuổi thọ kỳ vọng, CLV dự báo theo chi nhánh (kéo thanh biên lợi nhuận) |
| Quỹ sửa chữa | Mô phỏng Monte Carlo chi phí sửa chữa và quỹ dự phòng |
| Cập nhật dữ liệu | Chọn chi nhánh → kéo thả file → kiểm tra → cập nhật. Chế độ **Thêm dữ liệu mới** hoặc **Thay toàn bộ** |
| Quy tắc chấm điểm | Sửa ngưỡng/điểm, thử trước bằng kiểm tra ngược rồi mới lưu |

**Hoàn tác & xóa dữ liệu:** trước mỗi thao tác thay đổi dữ liệu (cập nhật, xóa, nạp lại, tạo mẫu, đổi quy tắc),
hệ thống tự sao lưu vào thư mục `backups/` (giữ 10 bản gần nhất). Bấm nút **↺ Hoàn tác** ở thanh trên để hủy thao tác
vừa làm, hoặc vào mục **Lịch sử thay đổi** trên trang Cập nhật dữ liệu để quay về trước một mốc bất kỳ. Lịch sử gọi khách
ghi sau thời điểm sao lưu không bị mất khi hoàn tác. Nút **Xóa toàn bộ dữ liệu** (phải gõ chữ XÓA để xác nhận) nằm ở
"Vùng nguy hiểm" của trang Cập nhật dữ liệu – và cũng hoàn tác được.

Góc trên: chọn chi nhánh, tìm nhanh hội viên (Ctrl+K), chế độ sáng/tối, đổi tên nhân viên trực.

## Mô hình tính toán (theo tài liệu Aura)
**Churn Score (0-100)**: tần suất tập 14 ngày (45%), hạn hợp đồng (30%), phản hồi dịch vụ (15%), PT & tập nhóm (10%).
Mức: Cực kỳ nguy hiểm ≥75 · Cao 50-74 · Trung bình 25-49 · An toàn <25.
**CLV** = tổng gói thẻ + gói PT (VIP >10 tr · Medium 3-10 tr · Low <3 tr); **CLV dự báo** = ARPU × biên lợi nhuận × 1/churn tháng.
**Priority Score** = Churn Score × CLV. Kịch bản Nhóm 1-4 theo tài liệu + nhóm "Theo dõi sát" (bổ sung).
Mỗi chi nhánh được chấm theo ngày dữ liệu mới nhất của chính chi nhánh đó.

## Dữ liệu
Mỗi chi nhánh một file Excel trong `raw/` (`Quan_1.xlsx`, `Quan_7.xlsx`, `Bien_Hoa.xlsx` – dữ liệu mẫu bản đầu,
300 hội viên/chi nhánh, 05/02/2025 → 07/11/2026), mỗi sheet một loại dữ liệu:

| Sheet | Cột bắt buộc | Cột tùy chọn |
|---|---|---|
| hoi_vien | ma_hv, ho_ten, so_dien_thoai, ngay_tham_gia | chi_nhanh, gioi_tinh, ngay_sinh, tap_cung_ban (0/1) |
| goi_the | ma_hv, loai_goi, gia, ngay_bat_dau, ngay_het_han | |
| checkin | ma_hv, thoi_gian | hinh_thuc (Tự do / Lớp nhóm / PT) |
| goi_pt | ma_hv, loai_pt, gia, ngay_mua | so_buoi |
| danh_gia | ma_hv, ngay, so_sao | khieu_nai, da_xu_ly (0/1), noi_dung |
| thiet_bi | ten, so_luong, p_hong_thang, chi_phi_tb, chi_phi_max | chi_nhanh, nam_su_dung |

Vẫn nhận các file CSV riêng lẻ. Dữ liệu nhập trên web được lưu lại vào `raw/<Chi_nhanh>.xlsx`.

## Công cụ dòng lệnh (không bắt buộc)
```
python generate_data.py 300 0            # tạo lại dữ liệu mẫu bản đầu
python generate_data.py 300 3            # + 3 tháng "thời gian tới" vào du_lieu_thoi_gian_toi/
python extend_data.py "Quận 1" 3         # sinh tiếp 3 tháng cho 1 chi nhánh từ dữ liệu đang có
python backtest.py                       # kiểm tra ngược quy tắc
python ai_model.py                       # huấn luyện và đánh giá AI
python monte_carlo.py 12 10000 "Quận 1"  # mô phỏng chi phí sửa chữa
python web.py                            # chạy web không qua run.py
```

## Lưu ý
Chỉ chạy trong mạng nội bộ: dữ liệu có số điện thoại thật của khách. Web chỉ mở cho chính máy đang chạy (127.0.0.1).
Thư viện giao diện đi kèm đều là giấy phép mở – xem `static/vendor/LICENSES.txt`.
