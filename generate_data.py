"""Sinh dữ liệu mẫu cho 3 chi nhánh (~300 hội viên/chi nhánh), đúng định dạng hệ thống đọc.

Kết quả: mỗi chi nhánh 1 file Excel raw/<Chi_nhanh>.xlsx gồm 6 sheet
  hoi_vien.csv : ma_hv, ho_ten, so_dien_thoai, gioi_tinh, ngay_sinh, ngay_tham_gia, chi_nhanh, tap_cung_ban
  goi_the.csv  : ma_hv, loai_goi, gia, ngay_bat_dau, ngay_het_han
  goi_pt.csv   : ma_hv, loai_pt, so_buoi, gia, ngay_mua
  checkin.csv  : ma_hv, thoi_gian, hinh_thuc   (Tự do / Lớp nhóm / PT)
  danh_gia.csv : ma_hv, ngay, so_sao, khieu_nai, da_xu_ly, noi_dung
  thiet_bi.csv : ten, chi_nhanh, so_luong, nam_su_dung, p_hong_thang, chi_phi_tb, chi_phi_max

Khi có dữ liệu thật: không cần chạy file này, nhập file thật trên giao diện (trang "Nhập dữ liệu").
Chạy: python generate_data.py [số_hội_viên_mỗi_chi_nhánh] [số_tháng_thời_gian_tới]
Ngoài raw/, sinh thêm thư mục du_lieu_thoi_gian_toi/: dữ liệu MỚI phát sinh sau ngày TODAY
(khách cũ tiếp tục tập/gia hạn/bỏ + khách mới) để nhập bằng chế độ "Thêm dữ liệu mới".
"""
import random
import sys
from datetime import date, datetime, timedelta

import pandas as pd

from config import BASE as BASE_DIR, BRANCHES, MEMBERSHIP_PLANS, PT_PACKAGES, RAW

SEED = 2026
TODAY = date(2026, 11, 7)            # dữ liệu tính đến hết ngày này
START = TODAY - timedelta(days=640)  # lịch sử ~21 tháng
MONTHS_AHEAD = 0                     # sinh thêm dữ liệu "thời gian tới" (tháng); 0 = chỉ dữ liệu đến TODAY

HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
DEM_NAM = ["Văn", "Minh", "Quốc", "Đức", "Hoàng", "Gia", "Thanh", "Hữu", "Anh", "Nhật"]
DEM_NU = ["Thị", "Ngọc", "Thu", "Minh", "Phương", "Khánh", "Bảo", "Thanh", "Mai", "Diệu"]
TEN_NAM = ["An", "Bảo", "Cường", "Dũng", "Duy", "Hải", "Hiếu", "Huy", "Khang", "Khoa", "Long", "Minh", "Nam",
           "Phát", "Phúc", "Quân", "Sơn", "Tài", "Thắng", "Thịnh", "Trí", "Tuấn", "Việt", "Vinh"]
TEN_NU = ["Anh", "Châu", "Chi", "Diệp", "Giang", "Hà", "Hân", "Hương", "Lan", "Linh", "Mai", "My", "Ngân",
          "Nhi", "Oanh", "Phương", "Quyên", "Tâm", "Thảo", "Trang", "Trâm", "Uyên", "Vy", "Yến"]
DAU_SO = ["090", "093", "089", "070", "079", "077", "091", "094", "088", "086", "096", "097", "098", "032", "035", "038"]

# Kiểu hành vi: (tỷ lệ, buổi/tuần, xác suất "rời bỏ" mỗi tháng)
PERSONAS = {
    "cham_chi": (0.27, (3.5, 5.0), 0.015),
    "deu_vua": (0.35, (2.0, 3.2), 0.04),
    "giam_dan": (0.24, (2.0, 3.5), 0.10),
    "bo_som": (0.14, (1.5, 2.8), 0.28),
}
# Cơ cấu phân khúc theo chi nhánh: student, offpeak, classic, vip
SEGMENT_MIX = {
    "Quận 1": (0.12, 0.10, 0.43, 0.35),
    "Quận 7": (0.18, 0.12, 0.50, 0.20),
    "Biên Hòa": (0.28, 0.14, 0.48, 0.10),
}
PT_BUY_PROB = {"student": 0.05, "offpeak": 0.10, "classic": 0.22, "vip": 0.45}
GOOD_COMMENTS = ["HLV nhiệt tình", "Phòng sạch sẽ", "Máy móc tốt", "Lớp yoga rất hay", "Nhân viên thân thiện",
                 "Không gian thoáng", "Rất hài lòng"]
MID_COMMENTS = ["Bình thường", "Giờ cao điểm hơi đông", "Ổn", "Cần thêm lớp buổi tối"]
BAD_COMMENTS = ["Máy chạy bộ hỏng lâu chưa sửa", "Phòng tắm không sạch", "Điều hòa yếu", "Quá đông giờ cao điểm",
                "HLV hay đổi lịch", "Tủ đồ bị hỏng khóa", "Nhân viên thái độ chưa tốt", "Nhạc quá to"]

EQUIPMENT = [
    # ten, so_luong theo CN (Q1, Q7, BH), p_hong_thang, chi_phi_tb, chi_phi_max
    ("Máy chạy bộ", (12, 10, 8), 0.025, 2_500_000, 20_000_000),
    ("Xe đạp tập / Elliptical", (8, 10, 6), 0.015, 1_200_000, 8_000_000),
    ("Máy tập đa năng (cáp)", (10, 6, 8), 0.015, 1_500_000, 12_000_000),
    ("Ghế, tạ, giàn tạ (Free Weights)", (30, 20, 40), 0.005, 400_000, 3_000_000),
    ("Điều hòa", (8, 6, 6), 0.015, 3_000_000, 30_000_000),
    ("Phòng tắm, đường nước", (1, 1, 1), 0.10, 1_500_000, 40_000_000),
    ("Hệ thống điện, chiếu sáng", (1, 1, 1), 0.06, 1_500_000, 35_000_000),
    ("Âm thanh phòng GroupX", (2, 3, 1), 0.02, 1_500_000, 15_000_000),
    ("Máy check-in, camera", (4, 3, 3), 0.02, 1_000_000, 8_000_000),
    ("Máy đo InBody", (1, 1, 1), 0.01, 2_500_000, 30_000_000),
    ("Phòng xông hơi", (1, 0, 1), 0.04, 3_000_000, 60_000_000),
    ("Sàn cao su, gương, nội thất", (1, 1, 1), 0.05, 2_000_000, 50_000_000),
]
EQUIP_AGE = {"Quận 1": 4, "Quận 7": 2, "Biên Hòa": 1}


def rand_name(rng):
    if rng.random() < 0.5:
        return "Nam", f"{rng.choice(HO)} {rng.choice(DEM_NAM)} {rng.choice(TEN_NAM)}"
    return "Nữ", f"{rng.choice(HO)} {rng.choice(DEM_NU)} {rng.choice(TEN_NU)}"


def pick_plan(rng, segment, months_in):
    if segment == "student":
        return "Classic 6 tháng" if months_in >= 6 and rng.random() < 0.15 else "Student Pass"
    if segment == "offpeak":
        return "Classic 6 tháng" if rng.random() < 0.08 else "Off Peak"
    if segment == "classic":
        return rng.choices(["Classic 6 tháng", "Classic 12 tháng", "All Access VIP 12 tháng"], [0.55, 0.40, 0.05])[0]
    return rng.choices(["All Access VIP 12 tháng", "Classic 12 tháng"], [0.9, 0.1])[0]


def hour_for(rng, plan):
    if plan == "Student Pass":
        return rng.choice([8, 9, 10, 13, 14, 15])
    if plan == "Off Peak":
        return rng.choice([8, 9, 10, 11, 13, 14])
    return rng.choice([6, 6, 7, 7, 11, 12, 17, 18, 18, 19, 19, 20, 20, 21])


def make_branch(branch, n, rng, end_sim=TODAY):
    code = BRANCHES[branch]["code"]
    members, plans, pts, checkins, ratings = [], [], [], [], []
    phones = set()
    n_new = round(n * (end_sim - TODAY).days / (TODAY - START).days)   # khách mới trong thời gian tới
    for i in range(1, n + n_new + 1):
        ma = f"{code}-{i:04d}"
        segment = rng.choices(["student", "offpeak", "classic", "vip"], SEGMENT_MIX[branch])[0]
        weights = [p[0] for p in PERSONAS.values()]
        if segment == "vip":
            weights = [0.40, 0.35, 0.17, 0.08]
        persona = rng.choices(list(PERSONAS), weights)[0]
        _, (fmin, fmax), hazard = PERSONAS[persona]
        loyal = persona in ("cham_chi", "deu_vua")
        friend = int(rng.random() < (0.28 if loyal else 0.08))
        group_pref = rng.random() < (0.35 if loyal else 0.15)
        if friend:
            hazard *= 0.7

        if i <= n:
            joined = START + timedelta(days=rng.randint(0, (TODAY - START).days - 3))
        else:
            joined = TODAY + timedelta(days=rng.randint(1, max(1, (end_sim - TODAY).days - 3)))
        gender, name = rand_name(rng)
        age = rng.randint(18, 23) if segment == "student" else rng.randint(23, 58)
        dob = date(TODAY.year - age, rng.randint(1, 12), rng.randint(1, 28))
        while True:
            phone = rng.choice(DAU_SO) + f"{rng.randint(0, 9_999_999):07d}"
            if phone not in phones:
                phones.add(phone)
                break
        members.append(dict(ma_hv=ma, ho_ten=name, so_dien_thoai=phone, gioi_tinh=gender, ngay_sinh=dob,
                            ngay_tham_gia=joined, chi_nhanh=branch, tap_cung_ban=friend))

        # Thời điểm "nản" (disengage): sau số tháng ngẫu nhiên theo phân phối hình học
        life_m = 1
        while rng.random() > hazard and life_m < 60:
            life_m += 1
        disengage = joined + timedelta(days=30 * life_m - rng.randint(0, 25))
        signal = rng.random() < 0.8                        # 20% bỏ "im lặng", không có dấu hiệu trước
        ramp = rng.randint(21, 70)

        # Chuỗi gói thẻ
        d, months_in, my_plans = joined, 0, []
        while d <= end_sim:
            plan = pick_plan(rng, segment, months_in)
            days, price = MEMBERSHIP_PLANS[plan]
            end = d + timedelta(days=days - 1)
            my_plans.append(dict(ma_hv=ma, loai_goi=plan, gia=price, ngay_bat_dau=d, ngay_het_han=end))
            months_in += days // 30
            if end >= disengage or end >= end_sim:
                break
            gap = 0 if rng.random() < 0.8 else rng.randint(1, 12)
            d = end + timedelta(days=1 + gap)
        plans += my_plans
        last_day = min(end_sim, my_plans[-1]["ngay_het_han"])

        # Gói PT
        pt_sessions = []   # (ngày, buổi/tuần, số buổi, ngày kết thúc dự kiến)
        active_days = (min(last_day, disengage) - joined).days
        if active_days > 20 and rng.random() < PT_BUY_PROB[segment]:
            k = 0
            buy = joined + timedelta(days=rng.randint(0, max(1, int(active_days * 0.6))))
            while buy < min(last_day, disengage) and k < 3:
                pt_name = rng.choices(list(PT_PACKAGES), [0.35, 0.25, 0.10, 0.15, 0.15])[0]
                sessions, price = PT_PACKAGES[pt_name]
                pts.append(dict(ma_hv=ma, loai_pt=pt_name, so_buoi=sessions, gia=price, ngay_mua=buy))
                per_week = rng.choice([2, 2, 3])
                pt_sessions.append((buy, per_week, sessions))
                weeks = sessions / per_week
                buy = buy + timedelta(days=int(weeks * 7) + rng.randint(7, 60))
                k += 1
                if not loyal and rng.random() < 0.7:
                    break
                if rng.random() < 0.5:
                    break

        # Check-in theo tuần
        def rate_at(day):
            if day >= disengage:
                return 0.05 if rng.random() < 0.3 else 0.0
            if signal and (disengage - day).days < ramp:
                return max(0.0, (disengage - day).days / ramp) * base
            return base

        base = rng.uniform(fmin, fmax)
        day, pause = joined, 0
        while day <= last_day:
            if pause > 0:
                pause -= 1
            elif rng.random() < 0.035:
                pause = rng.randint(0, 2)          # nghỉ 1-3 tuần (đi công tác, ốm...) -> nhiễu
            else:
                r = rate_at(day) * rng.uniform(0.7, 1.25)
                plan_now = next((p["loai_goi"] for p in my_plans if p["ngay_bat_dau"] <= day <= p["ngay_het_han"]),
                                my_plans[-1]["loai_goi"])
                k = min(7, int(r) + (rng.random() < r % 1))
                for off in sorted(rng.sample(range(7), k)):
                    cday = day + timedelta(days=off)
                    if cday <= last_day:
                        kind = "Lớp nhóm" if group_pref and rng.random() < 0.5 else "Tự do"
                        checkins.append(dict(ma_hv=ma, thoi_gian=datetime(cday.year, cday.month, cday.day,
                                                                          hour_for(rng, plan_now), rng.randint(0, 59)),
                                             hinh_thuc=kind))
            day += timedelta(days=7)

        # Buổi PT
        for buy, per_week, sessions in pt_sessions:
            done, day = 0, buy
            stop = disengage - timedelta(days=ramp // 2 if signal else 0)
            while done < sessions and day <= last_day and day < stop:
                for off in sorted(rng.sample(range(7), per_week)):
                    cday = day + timedelta(days=off)
                    if done < sessions and cday <= last_day and cday < stop:
                        checkins.append(dict(ma_hv=ma, thoi_gian=datetime(cday.year, cday.month, cday.day,
                                                                          rng.choice([6, 7, 17, 18, 19]), rng.randint(0, 59)),
                                             hinh_thuc="PT"))
                        done += 1
                day += timedelta(days=7)

        # Đánh giá dịch vụ
        n_ratings = max(0, int(active_days / 110 + rng.random()))
        for _ in range(n_ratings):
            rd = joined + timedelta(days=rng.randint(3, max(4, (last_day - joined).days)))
            near_quit = (disengage - rd).days < 75
            if near_quit and rng.random() < 0.45:
                stars = rng.choice([1, 2, 2, 3])
            elif loyal:
                stars = rng.choices([3, 4, 5], [0.15, 0.4, 0.45])[0]
            else:
                stars = rng.choices([2, 3, 4, 5], [0.12, 0.3, 0.35, 0.23])[0]
            complaint = int(stars <= 2 and rng.random() < 0.65)
            resolved = int(not complaint or rng.random() < (0.85 if loyal else 0.45))
            text = rng.choice(BAD_COMMENTS if stars <= 2 else MID_COMMENTS if stars == 3 else GOOD_COMMENTS)
            ratings.append(dict(ma_hv=ma, ngay=rd, so_sao=stars, khieu_nai=complaint, da_xu_ly=resolved, noi_dung=text))
        # Một số khách bỏ có phàn nàn ngay trước khi nản
        if signal and disengage <= end_sim + timedelta(days=40) and rng.random() < 0.3:
            rd = disengage - timedelta(days=rng.randint(5, 30))
            if joined < rd <= end_sim:
                ratings.append(dict(ma_hv=ma, ngay=rd, so_sao=rng.choice([1, 2]), khieu_nai=1,
                                    da_xu_ly=int(rng.random() < 0.3), noi_dung=rng.choice(BAD_COMMENTS)))

    ci = pd.DataFrame(checkins).sort_values(["ma_hv", "thoi_gian"])
    idx = list(BRANCHES).index(branch)
    eq = pd.DataFrame([dict(ten=t, chi_nhanh=branch, so_luong=q[idx], nam_su_dung=EQUIP_AGE[branch],
                            p_hong_thang=p, chi_phi_tb=c, chi_phi_max=m)
                       for t, q, p, c, m in EQUIPMENT if q[idx] > 0])
    return {
        "hoi_vien": pd.DataFrame(members),
        "goi_the": pd.DataFrame(plans),
        "goi_pt": pd.DataFrame(pts, columns=["ma_hv", "loai_pt", "so_buoi", "gia", "ngay_mua"]),
        "checkin": ci,
        "danh_gia": pd.DataFrame(ratings, columns=["ma_hv", "ngay", "so_sao", "khieu_nai", "da_xu_ly", "noi_dung"]).sort_values(["ma_hv", "ngay"]),
        "thiet_bi": eq,
    }


def _write_book(path, dfs):
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for name, df in dfs.items():
            df.to_excel(w, sheet_name=name, index=False)
            ws = w.sheets[name]
            for i, col in enumerate(df.columns):
                ws.column_dimensions[chr(65 + i)].width = max(12, min(40, len(col) + 4))
            ws.freeze_panes = "A2"


DATE_OF = {"hoi_vien": "ngay_tham_gia", "goi_the": "ngay_bat_dau", "goi_pt": "ngay_mua",
           "checkin": "thoi_gian", "danh_gia": "ngay"}


def split(dfs, cutoff):
    """Tách dữ liệu: đến hết ngày cutoff (hiện tại) và sau cutoff (thời gian tới)."""
    now, later = {}, {}
    for name, df in dfs.items():
        if name not in DATE_OF:
            now[name] = df
            continue
        d = pd.to_datetime(df[DATE_OF[name]])
        mask = d < pd.Timestamp(cutoff) + pd.Timedelta(days=1)
        now[name], later[name] = df[mask], df[~mask]
    return now, later


def main(n=300, months_ahead=MONTHS_AHEAD):
    rng = random.Random(SEED)
    end_sim = TODAY + timedelta(days=30 * months_ahead)
    future_dir = BASE_DIR / "du_lieu_thoi_gian_toi"
    for branch, info in BRANCHES.items():
        dfs = make_branch(branch, n, rng, end_sim)
        now, later = split(dfs, TODAY)
        _write_book(RAW / f"{info['folder']}.xlsx", now)
        print(f"{branch}: đến {TODAY:%d/%m/%Y}: {len(now['hoi_vien'])} hội viên, {len(now['goi_the'])} gói thẻ, "
              f"{len(now['checkin'])} check-in -> raw/{info['folder']}.xlsx")
        if months_ahead:
            _write_book(future_dir / f"{info['folder']}_them_{TODAY + timedelta(days=1):%d-%m-%Y}_den_{end_sim:%d-%m-%Y}.xlsx", later)
            print(f"   + thời gian tới đến {end_sim:%d/%m/%Y}: {len(later['hoi_vien'])} khách mới, {len(later['goi_the'])} gói thẻ, "
                  f"{len(later['goi_pt'])} gói PT, {len(later['checkin'])} check-in, {len(later['danh_gia'])} đánh giá")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300,
         int(sys.argv[2]) if len(sys.argv) > 2 else MONTHS_AHEAD)
