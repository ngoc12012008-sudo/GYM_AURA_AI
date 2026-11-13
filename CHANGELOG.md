# Những thay đổi so với code cũ

## 0f. Sửa nút chọn chi nhánh (mới nhất)
- Số khách cần gọi ở thanh bên bị thành ô đỏ đặc khi đang mở trang Cần gọi: đã sửa màu.
- Bấm Biên Hòa / Quận 1 / Quận 7 không có tác dụng: trình duyệt lưu tên có dấu ở dạng mã hóa (Bi%C3%AAn...) nhưng
  máy chủ không giải mã nên luôn rơi về "Tất cả". Nay giải mã và chuẩn hóa Unicode trước khi so tên chi nhánh.

## 0e. Tên và chú thích
- Góc trái ghi "Aura Gym AI"; trang đầu đổi tên từ "Hôm nay" thành "Trang chủ".
- Bỏ các dòng chú thích giải thích: dưới vầng aura, dưới các lựa chọn cập nhật và công cụ, vùng xóa dữ liệu, hộp hoàn tác, nhãn "0–100" của Churn Score.

## 0d. Tông nâu – bạc – tím oải hương
- Bảng màu mới: nâu cà phê (#4A3428) cho chữ đậm và nút chính, nền bạc (#EFEFF1), tím oải hương (#8E82BE) làm điểm nhấn
  (mục đang chọn, quầng sáng vầng aura, mức An toàn); các mức rủi ro dùng tông nâu ấm (gạch, caramel, lúa mì). Có cả chế độ tối.
- Trang Hôm nay chỉ còn hai phần: danh sách "Gọi trước những người này" và vầng aura. Bỏ đoạn "… hội viên đang rời xa",
  dải số liệu, biểu đồ nhịp tập, cuộc gọi gần đây và bảng ba chi nhánh.
- Bỏ khối thừa ở trang khác: 4 bước giải thích và biểu đồ "Quy tắc so với AI" (Dự báo AI); biểu đồ gói và 3 thẻ chăm sóc
  theo hạng (Doanh thu & CLV); biểu đồ điểm trống khi khách không bị cộng điểm (Hội viên); dòng chân trang.

## 0c. Giao diện "không khối"
- Bỏ khung viền và nền của gần như mọi khối: nội dung đặt thẳng trên nền, phân tách bằng khoảng trắng và tiêu đề.
  Chỉ vùng thao tác (kéo thả file, chọn cách cập nhật, hộp thoại) còn khung. Thanh bên chuyển sang nền sáng.
- Trang Hôm nay: một câu lớn nói việc cần làm ("91 hội viên đang rời xa.") và hình **vầng aura** – mỗi chấm là một
  hội viên, càng xa tâm càng dễ rời bỏ, chấm to là khách VIP, chấm rỗng là đã gọi; chia góc theo chi nhánh;
  di chuột để xem tên, bấm để mở hồ sơ. Có hiệu ứng mở đầu một lần (tắt nếu máy bật giảm chuyển động).
- Bớt khối dữ liệu thừa: bỏ thẻ "Mức rủi ro" và ma trận khỏi trang Hôm nay (ma trận chuyển sang Doanh thu & CLV);
  hồ sơ hội viên lấy tên khách làm tiêu đề; phần "Cấu trúc file" thu gọn, bấm mới mở.

## 0b. Thiết kế lại giao diện
- Bộ nhận diện riêng: xanh khuynh diệp làm màu chính, thang rủi ro tông đất (gạch, gỉ, nghệ, rêu) chỉ dùng cho điểm Churn;
  tiêu đề và số lớn dùng Inter Display. Bỏ các dấu hiệu "giao diện mẫu": ô biểu tượng trên thẻ số liệu, nhãn IN HOA,
  viên nhãn tròn có chấm màu, ảnh đại diện nhiều màu, mũi tên "→", chuỗi nối bằng "·", thẻ mẹo trong menu.
- Menu và tiêu đề đặt theo việc người dùng làm: Hôm nay, Cần gọi, Hội viên, Dự báo AI, Doanh thu & CLV, Quỹ sửa chữa.
- Trang Hôm nay xoay quanh danh sách "Cần gọi hôm nay" (rủi ro cao, chưa gọi trong 7 ngày); số liệu gộp thành một dải.
- Chọn chi nhánh bằng nút liền nhau trên thanh trên (cả trên điện thoại).
- Trợ năng: dòng bảng dùng được bằng bàn phím (Tab, Enter), nhãn cho nút chỉ có biểu tượng, viền focus rõ, tôn trọng
  chế độ giảm chuyển động, thông báo đọc được bằng trình đọc màn hình, liên kết "Bỏ qua menu".

## 0a. Hoàn tác và xóa dữ liệu (mới nhất)
- **Nút Hoàn tác** (↺ ở thanh trên mọi trang, và trên trang Cập nhật dữ liệu): hủy thao tác vừa làm. Mục **Lịch sử thay đổi**
  cho phép quay về trước một mốc cũ hơn (hủy nhiều thao tác một lúc). Tự sao lưu trước mỗi thao tác, giữ 10 bản gần nhất.
- **Nút Xóa toàn bộ dữ liệu** (Vùng nguy hiểm, phải gõ XÓA để xác nhận; tùy chọn xóa cả lịch sử liên hệ) – cũng hoàn tác được.
- Hoàn tác không làm mất các cuộc gọi đã ghi sau thời điểm sao lưu. Nếu file trong raw/ đang mở bằng Excel, web báo rõ
  cần đóng file thay vì xóa dở dang. Sau khi xóa toàn bộ, run.py không tự tạo lại dữ liệu mẫu.

## 0. Bản web
- **Bỏ Streamlit, chuyển thành một web duy nhất (Flask + Bootstrap 5)**, giao diện theo Metis Bootstrap Admin Template:
  menu trái, thanh trên có tìm nhanh hội viên (Ctrl+K), chọn chi nhánh, chế độ sáng/tối; thẻ số liệu, biểu đồ Chart.js.
- **Cập nhật dữ liệu ngay trên web**: chọn chi nhánh → kéo thả file → xem kiểm tra & xem trước → bấm cập nhật.
  Hệ thống tự chấm điểm lại và cho AI học lại (~10 giây); mọi trang khác dùng dữ liệu mới, không cần chạy lại run.py.
- Ghi kết quả gọi khách, sao chép tin nhắn, chạy mô phỏng, thử quy tắc… đều không phải tải lại trang.
- Mỗi chi nhánh được chấm theo ngày dữ liệu mới nhất của chính nó (trước đây lấy chung một ngày, nên khi chỉ
  cập nhật 1 chi nhánh thì khách các chi nhánh khác bị coi như hết hạn).
- Thư viện giao diện đóng gói sẵn, chạy được khi không có Internet. Ít thư viện phải cài hơn (không còn streamlit, plotly).
- Dùng lại dữ liệu mẫu bản đầu (3 chi nhánh × 300 khách, đến 07/11/2026).
- Sửa: bản xem trước file lỗi với pandas mới (kiểu chuỗi mới); lỗi từ máy chủ nay được báo rõ trên giao diện.

## 1. Lỗi đã sửa

| File cũ | Lỗi | Đã sửa thế nào |
|---|---|---|
| run.py | Thiếu `import sqlite3`, nên từ lần chạy thứ 2 (khi đã có gym.db) bị dừng với lỗi `NameError` | Viết lại; kiểm tra DB bằng `etl.schema_ok()` |
| run.py | Thay file trong `raw/` thì DB không được nạp lại, vì chỉ kiểm tra bảng hoi_vien có tồn tại hay không | Tự nạp lại khi file trong `raw/` mới hơn `gym.db`, hoặc DB đang theo cấu trúc cũ |
| run.py | Cổng 8501 đang bận (do lần chạy trước chưa tắt) thì giao diện không lên | Tự tìm cổng trống từ 8501 trở đi |
| run.py | Chỉ cài thư viện khi thiếu, không kiểm tra phiên bản, nên Streamlit cũ có thể thiếu tính năng | Kiểm tra phiên bản tối thiểu; cài thêm scikit-learn và openpyxl |
| app.py | Dữ liệu được cache 10 phút, nên nạp dữ liệu mới không thấy thay đổi ngay | Cache theo "phiên bản dữ liệu" (số dòng, ngày mới nhất); đổi dữ liệu là tính lại ngay |
| app.py | Lưu kết quả gọi xong thì danh sách không cập nhật, vì lịch sử liên hệ được đọc trước khi lưu | Lưu xong tự tải lại trang và hiện thông báo |
| app.py | Ô "Ẩn khách đã liên hệ" ẩn vĩnh viễn khách từng được gọi, kể cả từ nhiều tháng trước | Chỉ ẩn khách liên hệ trong 3 / 7 / 14 / 30 ngày qua (tùy chọn) |
| app.py | Mỗi khách là một ô mở rộng, chỉ hiện 50 khách đầu, khó thao tác | Thay bằng bảng có thanh tiến độ, bấm vào dòng để mở bảng xử lý |
| app.py | Trang Dự phòng chi phí ghi đè biến `s` (bảng hội viên) và trùng tên biến `k` | Đặt tên riêng, tách thành hàm riêng cho từng trang |
| app.py | Lọc theo chi nhánh nhưng doanh thu mặc định ở trang Dự phòng vẫn là của cả hệ thống | Doanh thu tính theo chi nhánh đang chọn |
| app.py | Mỗi lần chọn khách đều gọi `set_index` cho cả bảng, chậm | Tạo bảng tra tên một lần |
| churn.py | Quy tắc chấm điểm khác hẳn tài liệu PDF: so 4 tuần thay vì 14 ngày, điểm số khác, chỉ 3 mức | Viết lại đúng mục V của tài liệu (xem phần 2) |
| churn.py | Không có CLV, Priority Score, kịch bản can thiệp | Đã bổ sung đủ (mục IV và VI tài liệu) |
| churn.py | Chấm điểm bằng vòng lặp `iterrows` cho từng khách, chậm | Tính bằng phép toán trên cả bảng, chấm 900 khách dưới 1 giây |
| churn.py / backtest.py | "Khách bỏ" chỉ xét người có thẻ hết hạn trong 60 ngày, vòng lặp chậm | Nhãn rời bỏ mới: hết hạn mà không gia hạn trong 30 ngày, xét trong 90 ngày tới; có xử lý trường hợp chưa đủ dữ liệu để biết |
| etl.py | `ngay_tham_gia` lỗi định dạng bị đổi thành rỗng mà không báo; không đọc được ngày kiểu 07/11/2026 | Đọc được cả `2026-11-07` và `07/11/2026`; báo số dòng bị bỏ |
| etl.py | Giá dạng `2.400.000` hoặc file Excel / dấu `;` không đọc được | Tự nhận dạng mã hóa, dấu phân cách, giá có dấu chấm, file .xlsx |
| etl.py | Tên cột phải đúng y hệt | Nhận tên cột tiếng Việt có dấu và tên phổ biến (vd "Mã hội viên", "SĐT") |
| etl.py | Mỗi lần chạy thay toàn bộ dữ liệu | Có thể nhập riêng từng chi nhánh, từng bảng; chi nhánh khác và lịch sử liên hệ giữ nguyên |
| etl.py | SĐT mất số 0 đầu khi qua Excel | Tự thêm lại số 0 cho số 9 chữ số |
| monte_carlo.py | Đọc thiết bị chỉ từ 1 file CSV; doanh thu lấy cả hệ thống | Đọc từ DB theo chi nhánh; doanh thu gồm cả PT, theo chi nhánh |
| monte_carlo.py | Thiết bị có số lượng 0 hoặc chi_phi_max < chi_phi_tb gây lỗi log | Bỏ qua hoặc tự chỉnh giá trị bất hợp lý |
| generate_data.py | Sinh nhiều lượt quẹt cùng ngày nên bị coi là trùng; chi nhánh "Thủ Đức" không khớp tài liệu | Mỗi ngày tối đa 1 lượt mỗi hình thức; 3 chi nhánh đúng tài liệu: Quận 1, Quận 7, Biên Hòa |

## 2. Mô hình tính mới (theo tài liệu Aura)

| | Code cũ | Code mới |
|---|---|---|
| Tần suất | Vắng >10 ngày +35; 4 tuần giảm >50% +30 | Không tập 14 ngày +40; 14 ngày giảm >50% +30; giảm 25-50% +15 |
| Hợp đồng | Còn <30 ngày +15 | <15 ngày +35; 15-29 ngày +30 (*tài liệu bỏ trống*); 30-60 ngày +25 |
| Phản hồi | Không có | 1-2 sao +20; khiếu nại chưa xử lý +15; 4-5 sao −10 |
| PT & nhóm | Có PT −15 | PT ngưng >10 ngày +20; tập nhóm / cùng bạn −10 |
| Khách mới | Khách mới đi ít +15 | Bỏ (tài liệu không có) |
| Mức rủi ro | 3 mức: Thấp / Trung bình / Cao (ngưỡng 30, 60) | 4 mức: An toàn / Trung bình / Cao / Cực kỳ nguy hiểm (ngưỡng 25, 50, 75) |
| CLV | Không có | Tổng gói thẻ + gói PT; VIP >10 tr, Medium 3-10 tr, Low <3 tr; CLV dự báo = ARPU × biên lợi nhuận × 1/churn tháng |
| Ưu tiên | Theo điểm | Priority Score = Churn × CLV |
| Kịch bản | 1 gợi ý ngắn | Nhóm 1-4 theo tài liệu + nhóm "Theo dõi sát" (*bổ sung*), kèm tin nhắn mẫu |
| Quy tắc | Sửa trong code | Sửa trên giao diện, thử trước khi lưu (rules.json) |

## 3. Tính năng mới

- **AI dự báo** (ai_model.py): mô hình Gradient Boosting học từ lịch sử, dự báo xác suất bỏ trong 90 ngày, có kiểm định AUC, nêu yếu tố ảnh hưởng, phát hiện "rủi ro ẩn"; tự học lại khi dữ liệu hoặc quy tắc đổi.
- **Dữ liệu mới**: thêm goi_pt, danh_gia, cột hinh_thuc trong checkin, tap_cung_ban trong hoi_vien; **mỗi chi nhánh gộp vào 1 file Excel** `raw/<Chi_nhanh>.xlsx` (6 sheet) thay vì nhiều file CSV; vẫn đọc được CSV; bảng giá đúng tài liệu.
- **Dữ liệu thời gian tới**: sinh thêm 3 tháng sau ngày 07/11/2026 (thư mục du_lieu_thoi_gian_toi/); trang Nhập dữ liệu có chế độ **Thêm dữ liệu mới** (giữ dữ liệu cũ, tự bỏ dòng trùng) bên cạnh chế độ Thay toàn bộ.
- **Sinh tiếp dữ liệu** (extend_data.py): mô phỏng thêm N tháng cho một chi nhánh dựa trên tình trạng hiện tại của từng khách, không làm thay đổi dữ liệu cũ. Đã sinh Quận 1: 06/02/2027 – 06/05/2027.
- **Giao diện**: 8 trang thay vì 4; giao diện mới (thẻ KPI, ma trận Rủi ro × CLV, đồng hồ điểm, biểu đồ theo tuần); trang Nhập dữ liệu kéo thả có kiểm tra lỗi; xuất CSV/Excel; ghi nhận kênh liên hệ (gọi / Zalo / SMS / trực tiếp).
- **File thêm**: config.py (cấu hình chung), ai_model.py, requirements.txt, .streamlit/config.toml (màu giao diện).
