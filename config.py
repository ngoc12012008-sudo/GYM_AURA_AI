"""Cấu hình chung: chi nhánh, bảng giá, quy tắc chấm điểm (theo tài liệu Aura Fitness & Yoga Center).

Muốn đổi ngưỡng/điểm: sửa trên giao diện (trang "Cài đặt quy tắc") hoặc sửa DEFAULT_RULES dưới đây.
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW = BASE / "raw"
DB = BASE / "gym.db"
MODEL_DIR = BASE / "models"
RULES_FILE = BASE / "rules.json"

# ---------------------------------------------------------------- Chi nhánh
BRANCHES = {
    "Quận 1": {"folder": "Quan_1", "code": "Q1", "ten": "Chi nhánh 1 (Flagship)",
               "dia_chi": "123 Nguyễn Huệ, P. Bến Nghé, Quận 1, TP.HCM", "dien_tich": 1200,
               "dac_diem": "Trụ sở trung tâm, máy nhập khẩu"},
    "Quận 7": {"folder": "Quan_7", "code": "Q7", "ten": "Chi nhánh 2",
               "dia_chi": "456 Nguyễn Thị Thập, P. Tân Quy, Quận 7, TP.HCM", "dien_tich": 800,
               "dac_diem": "Khu Cardio và GroupX rộng"},
    "Biên Hòa": {"folder": "Bien_Hoa", "code": "BH", "ten": "Chi nhánh 3",
                 "dia_chi": "789 Phạm Văn Thuận, P. Tân Mai, TP. Biên Hòa, Đồng Nai", "dien_tich": 900,
                 "dac_diem": "Khu Free Weights, phòng xông hơi cao cấp"},
}

# ---------------------------------------------------------------- Bảng giá
# tên gói: (số ngày hiệu lực, giá VNĐ)
MEMBERSHIP_PLANS = {
    "Day Pass": (1, 50_000),
    "Student Pass": (30, 299_000),
    "Off Peak": (30, 450_000),
    "Classic 6 tháng": (180, 2_400_000),
    "Classic 12 tháng": (360, 3_990_000),
    "All Access VIP 12 tháng": (360, 6_990_000),
}
# tên gói PT: (số buổi, giá VNĐ/người)
PT_PACKAGES = {
    "Starter PT": (10, 2_500_000),
    "Transformation PT": (30, 6_000_000),
    "Master PT": (50, 9_000_000),
    "Duo PT": (20, 3_500_000),
    "Small Group PT": (20, 2_500_000),
}
GROUP_PT = {"Duo PT", "Small Group PT"}

# ---------------------------------------------------------------- Quy tắc Churn Score (mục V tài liệu)
DEFAULT_RULES = {
    # 1. Tần suất tập (trọng số 45%)
    "khong_tap_ngay": 14, "diem_khong_tap": 40,          # không đi tập trong 14 ngày
    "giam_manh_pct": 0.50, "diem_giam_manh": 30,         # 14 ngày gần nhất giảm > 50% so với 14 ngày trước
    "giam_vua_pct": 0.25, "diem_giam_vua": 15,           # giảm 25% - 50%
    # 2. Thời hạn hợp đồng còn lại (trọng số 30%)
    "hd_rat_gap_ngay": 15, "diem_hd_rat_gap": 35,        # còn dưới 15 ngày (kể cả vừa hết hạn)
    "hd_gap_ngay": 30, "diem_hd_gap": 30,                # 15-29 ngày: tài liệu bỏ trống, mặc định 30 điểm
    "hd_vang_ngay": 60, "diem_hd_vang": 25,              # 30-60 ngày: "khung thời gian vàng"
    # 3. Phản hồi dịch vụ (trọng số 15%)
    "danh_gia_ngay": 30, "diem_sao_thap": 20, "diem_sao_cao": -10,
    "diem_khieu_nai": 15,                                # khiếu nại chưa xử lý triệt để
    # 4. PT và tập nhóm (trọng số 10%)
    "pt_ngung_ngay": 10, "diem_pt_ngung": 20,
    "diem_tap_nhom": -10, "nhom_toi_thieu_buoi": 2,      # >= 2 buổi lớp nhóm/30 ngày, hoặc tập cùng bạn
    # Phân loại mức rủi ro
    "nguong_critical": 75, "nguong_high": 50, "nguong_medium": 25,
    # CLV
    "clv_vip": 10_000_000, "clv_medium": 3_000_000,
    "bien_loi_nhuan": 0.65,
    # Số ngày ân hạn: hết hạn quá số ngày này mà không gia hạn = đã rời bỏ
    "an_han_ngay": 30,
}

RULE_LABELS = {
    "khong_tap_ngay": "Số ngày không đi tập để bị cộng điểm", "diem_khong_tap": "Điểm: không đi tập",
    "giam_manh_pct": "Mức giảm mạnh (tỷ lệ)", "diem_giam_manh": "Điểm: giảm mạnh",
    "giam_vua_pct": "Mức giảm vừa (tỷ lệ)", "diem_giam_vua": "Điểm: giảm vừa",
    "hd_rat_gap_ngay": "Hợp đồng còn dưới (ngày) – rất gấp", "diem_hd_rat_gap": "Điểm: rất gấp",
    "hd_gap_ngay": "Hợp đồng còn dưới (ngày) – gấp", "diem_hd_gap": "Điểm: gấp",
    "hd_vang_ngay": "Hợp đồng còn tối đa (ngày) – khung vàng", "diem_hd_vang": "Điểm: khung vàng",
    "danh_gia_ngay": "Xét đánh giá trong (ngày)", "diem_sao_thap": "Điểm: đánh giá 1-2 sao",
    "diem_sao_cao": "Điểm: đánh giá 4-5 sao", "diem_khieu_nai": "Điểm: khiếu nại chưa xử lý",
    "pt_ngung_ngay": "PT ngưng đặt lịch quá (ngày)", "diem_pt_ngung": "Điểm: PT ngưng",
    "diem_tap_nhom": "Điểm: tập nhóm / cùng bạn", "nhom_toi_thieu_buoi": "Số buổi lớp nhóm tối thiểu/30 ngày",
    "nguong_critical": "Ngưỡng Cực kỳ nguy hiểm", "nguong_high": "Ngưỡng Rủi ro cao",
    "nguong_medium": "Ngưỡng Rủi ro trung bình",
    "clv_vip": "CLV VIP từ (VNĐ)", "clv_medium": "CLV Medium từ (VNĐ)",
    "bien_loi_nhuan": "Biên lợi nhuận gộp", "an_han_ngay": "Số ngày ân hạn gia hạn",
}

RISK_ORDER = ["Cực kỳ nguy hiểm", "Rủi ro cao", "Rủi ro trung bình", "An toàn"]
RISK_COLORS = {"Cực kỳ nguy hiểm": "#8e2f25", "Rủi ro cao": "#b8662e",
               "Rủi ro trung bình": "#c39a3e", "An toàn": "#8e82be"}
CLV_ORDER = ["VIP", "Medium", "Low"]
CLV_COLORS = {"VIP": "#4a3428", "Medium": "#8e82be", "Low": "#b9b8c0"}
GROUP_ORDER = ["Nhóm 1 – Ưu tiên số 1", "Nhóm 2 – Ưu tiên số 2", "Nhóm 3 – Ưu tiên số 3",
               "Theo dõi sát", "Nhóm 4 – Theo dõi"]

# Kịch bản can thiệp (mục VI tài liệu)
SCRIPTS = {
    "Nhóm 1 – Ưu tiên số 1": ("Quản lý chi nhánh", "Gọi điện tham vấn 1 kèm 1, tặng 1 buổi PT hoặc voucher nâng cấp gói khi gia hạn."),
    "Nhóm 2 – Ưu tiên số 2": ("Zalo/SMS tự động", "Nhắn nhắc lịch tập cá nhân hóa, kèm voucher giảm 15% nếu gia hạn trong tuần."),
    "Nhóm 3 – Ưu tiên số 3": ("Khảo sát tự động", "Gửi khảo sát lý do không đi tập; đề xuất chuyển gói theo ngày hoặc bảo lưu thẻ."),
    "Theo dõi sát": ("Lễ tân", "Nhắn hỏi thăm nhẹ nhàng, mời tham gia lớp nhóm phù hợp lịch."),
    "Nhóm 4 – Theo dõi": ("Tự động", "Không can thiệp. Gửi lời chúc mừng khi đạt mốc buổi tập hoặc InBody tiến bộ."),
}

CONTACT_RESULTS = ["Đồng ý gia hạn", "Khách sẽ quay lại tập", "Muốn bảo lưu thẻ", "Chuyển gói phù hợp hơn",
                   "Hẹn gọi lại", "Không nghe máy", "Khách sẽ nghỉ"]
CONTACT_CHANNELS = ["Gọi điện", "Zalo", "SMS", "Gặp trực tiếp"]


def load_rules():
    rules = dict(DEFAULT_RULES)
    if RULES_FILE.exists():
        try:
            saved = json.loads(RULES_FILE.read_text(encoding="utf-8"))
            rules.update({k: type(DEFAULT_RULES[k])(v) for k, v in saved.items() if k in DEFAULT_RULES})
        except Exception:
            pass
    return rules


def save_rules(rules):
    RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_rules():
    if RULES_FILE.exists():
        RULES_FILE.unlink()


def branch_folder(name):
    if name in BRANCHES:
        return BRANCHES[name]["folder"]
    import unicodedata
    s = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode()
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_") or "Chi_nhanh"
