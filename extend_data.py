"""Sinh TIẾP dữ liệu cho một chi nhánh từ dữ liệu đang có (không thay đổi dữ liệu cũ).

Đọc tình trạng từng hội viên ở cuối dữ liệu hiện có (tần suất tập gần đây, xu hướng, hạn thẻ, PT,
khiếu nại...), rồi mô phỏng N tháng tiếp theo: khách tập đều thì gia hạn, khách đang nản thì bỏ, có thêm khách mới.

Chạy: python extend_data.py "Quận 1" 3 [file_dữ_liệu_1.xlsx file_dữ_liệu_2.xlsx ...]
  - Không truyền file: đọc dữ liệu của chi nhánh trong gym.db
  - Kết quả: du_lieu_thoi_gian_toi/<Chi_nhanh>_them_<từ>_den_<đến>.xlsx -> nhập bằng chế độ "Thêm dữ liệu mới"
"""
import random
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import generate_data as gd
from config import BASE, BRANCHES, PT_PACKAGES

SHEETS = ["hoi_vien", "goi_the", "goi_pt", "checkin", "danh_gia"]


def load_current(branch, files=None):
    if files:
        import etl
        parts = [etl.read_workbook(f) for f in files]
        dfs = {t: pd.concat([p[t] for p in parts if t in p], ignore_index=True) for t in SHEETS}
    else:
        import churn
        data = churn.filter_branch(churn.load_data(), branch)
        dfs = {t: data[t].drop(columns=["chi_nhanh"], errors="ignore") if t != "hoi_vien" else data[t] for t in SHEETS}
    conv = {"hoi_vien": ["ngay_tham_gia", "ngay_sinh"], "goi_the": ["ngay_bat_dau", "ngay_het_han"],
            "goi_pt": ["ngay_mua"], "checkin": ["thoi_gian"], "danh_gia": ["ngay"]}
    for t, cols in conv.items():
        for c in cols:
            dfs[t][c] = pd.to_datetime(dfs[t][c], errors="coerce", format="mixed")
    for t, c in [("goi_the", "gia"), ("goi_pt", "gia"), ("goi_pt", "so_buoi"), ("danh_gia", "so_sao"),
                 ("danh_gia", "khieu_nai"), ("danh_gia", "da_xu_ly"), ("hoi_vien", "tap_cung_ban")]:
        dfs[t][c] = pd.to_numeric(dfs[t][c], errors="coerce").fillna(0).astype(int)
    return dfs


def extend(branch, months=3, files=None, seed=None):
    dfs = load_current(branch, files)
    hv, gt, pt, ci, dg = (dfs[t] for t in SHEETS)
    end = ci["thoi_gian"].max().normalize()                  # ngày cuối của dữ liệu hiện có
    w0, w1 = end + pd.Timedelta(days=1), end + pd.Timedelta(days=30 * months)
    rng = random.Random(seed if seed is not None else int(end.strftime("%Y%m%d")) + sum(map(ord, branch)))
    plans, pts, checkins, ratings = [], [], [], []

    ci_by = dict(tuple(ci.groupby("ma_hv")))
    gt_by = dict(tuple(gt.sort_values("ngay_het_han").groupby("ma_hv")))
    pt_by = dict(tuple(pt.groupby("ma_hv")))
    dg_by = dict(tuple(dg.groupby("ma_hv")))
    for _, m in hv.iterrows():
        ma = m["ma_hv"]
        g = gt_by.get(ma)
        if g is None or g.empty:
            continue
        last = g.iloc[-1]
        chain_end = last["ngay_het_han"]
        c = ci_by.get(ma, ci.iloc[0:0])
        if chain_end < end - pd.Timedelta(days=30):        # đã rời bỏ từ trước: 3% quay lại
            if rng.random() > 0.03:
                continue
            chain_end = w0 + pd.Timedelta(days=rng.randint(0, 60))
            base = rng.uniform(1.5, 2.5)
            declining, hazard, gone = False, 0.08, False
        else:
            ago = (end + pd.Timedelta(days=1) - c["thoi_gian"]).dt.days
            r4, r4p, w8 = (ago <= 28).sum(), ((ago > 28) & (ago <= 56)).sum(), (ago <= 56).sum() / 8
            declining = r4 == 0 or (r4p > 0 and r4 < 0.5 * r4p)
            hazard = 0.6 if r4 == 0 else 0.35 if declining else 0.02 if w8 >= 3 else 0.05 if w8 >= 1.5 else 0.12
            d = dg_by.get(ma)
            if d is not None and ((d["khieu_nai"] == 1) & (d["da_xu_ly"] == 0)).any():
                hazard += 0.1
            if m.get("tap_cung_ban", 0) == 1 or (c["hinh_thuc"] == "Lớp nhóm").mean() > 0.3:
                hazard *= 0.7
            base = r4 / 4 if r4 else w8
            gone = r4 == 0
            if not declining and base < 0.5:
                base = rng.uniform(1.0, 2.0)
        months_left = 0
        while rng.random() > min(0.95, hazard) and months_left < 24:
            months_left += 1
        disengage = end + pd.Timedelta(days=max(1, 30 * months_left + rng.randint(-10, 15)))
        signal = rng.random() < 0.8
        ramp = rng.randint(21, 60)

        # gia hạn
        plan_name, my_plans = last["loai_goi"], []
        d = chain_end + pd.Timedelta(days=1)
        in_grace = chain_end < w0
        if in_grace and (months_left == 0 or (gone and rng.random() > 0.05)):   # hết hạn + đã bỏ tập: hầu như không quay lại
            d = w1 + pd.Timedelta(days=1)
        while chain_end < w1 and (chain_end < disengage or in_grace) and d <= w1:
            in_grace = False
            if rng.random() < 0.1:
                plan_name = gd.pick_plan(rng, "classic", 12)
            days, price = gd.MEMBERSHIP_PLANS.get(plan_name, (30, int(last["gia"])))
            gap = 0 if rng.random() < 0.8 else rng.randint(1, 12)
            s = max(d + pd.Timedelta(days=gap), w0 + pd.Timedelta(days=rng.randint(0, 7)) if d < w0 else d)
            if s > w1:
                break
            e = s + pd.Timedelta(days=days - 1)
            my_plans.append(dict(ma_hv=ma, loai_goi=plan_name, gia=price, ngay_bat_dau=s.date(), ngay_het_han=e.date()))
            chain_end, d = e, e + pd.Timedelta(days=1)
        plans += my_plans
        last_day = min(w1, chain_end)

        # check-in theo tuần
        hours = list(c["thoi_gian"].dt.hour) or [18]
        p_group = (c["hinh_thuc"] == "Lớp nhóm").mean() if len(c) else 0.1
        day = w0
        while day <= last_day:
            if day >= disengage:
                r = 0.05 if rng.random() < 0.3 else 0.0
            elif signal and (disengage - day).days < ramp:
                r = base * (disengage - day).days / ramp
            else:
                r = base
            if rng.random() > 0.035:
                r *= rng.uniform(0.75, 1.25)
                k = min(7, int(r) + (rng.random() < r % 1))
                for off in sorted(rng.sample(range(7), k)):
                    cd = day + pd.Timedelta(days=off)
                    if cd <= last_day:
                        checkins.append(dict(ma_hv=ma, thoi_gian=datetime(cd.year, cd.month, cd.day, rng.choice(hours),
                                                                          rng.randint(0, 59)),
                                             hinh_thuc="Lớp nhóm" if rng.random() < p_group else "Tự do"))
            day += pd.Timedelta(days=7)

        # PT: tập nốt buổi còn lại, thỉnh thoảng mua gói mới
        p = pt_by.get(ma)
        left = int(p["so_buoi"].sum()) - int((c["hinh_thuc"] == "PT").sum()) if p is not None else 0
        if (left <= 0 and not declining and disengage > w0 + pd.Timedelta(days=30)
                and rng.random() < (0.12 if p is not None else 0.04)):
            name = rng.choices(list(PT_PACKAGES), [0.35, 0.25, 0.10, 0.15, 0.15])[0]
            buy = w0 + pd.Timedelta(days=rng.randint(0, 45))
            pts.append(dict(ma_hv=ma, loai_pt=name, so_buoi=PT_PACKAGES[name][0], gia=PT_PACKAGES[name][1], ngay_mua=buy.date()))
            left = PT_PACKAGES[name][0]
        if left > 0:
            day, stop = w0, disengage - pd.Timedelta(days=ramp // 2 if signal else 0)
            while left > 0 and day <= last_day and day < stop:
                for off in sorted(rng.sample(range(7), 2)):
                    cd = day + pd.Timedelta(days=off)
                    if left > 0 and cd <= last_day and cd < stop:
                        checkins.append(dict(ma_hv=ma, thoi_gian=datetime(cd.year, cd.month, cd.day,
                                                                          rng.choice([6, 7, 17, 18, 19]), rng.randint(0, 59)),
                                             hinh_thuc="PT"))
                        left -= 1
                day += pd.Timedelta(days=7)

        # đánh giá
        active = (last_day - w0).days
        for _ in range(max(0, int(active / 110 + rng.random()))):
            rd = w0 + pd.Timedelta(days=rng.randint(0, max(1, active)))
            near = (disengage - rd).days < 75
            stars = (rng.choice([1, 2, 2, 3]) if near and rng.random() < 0.45
                     else rng.choices([3, 4, 5], [0.2, 0.4, 0.4])[0] if not declining
                     else rng.choices([2, 3, 4], [0.3, 0.4, 0.3])[0])
            comp = int(stars <= 2 and rng.random() < 0.65)
            ratings.append(dict(ma_hv=ma, ngay=rd.date(), so_sao=stars, khieu_nai=comp,
                                da_xu_ly=int(not comp or rng.random() < 0.6),
                                noi_dung=rng.choice(gd.BAD_COMMENTS if stars <= 2 else gd.MID_COMMENTS if stars == 3 else gd.GOOD_COMMENTS)))

    # Khách mới: dùng bộ sinh gốc cho cửa sổ thời gian mới, rồi đánh số tiếp theo mã hiện có
    n_new = round(300 * (w1 - w0).days / 640)
    saved = gd.START, gd.TODAY
    gd.TODAY, gd.START = w0.date() - timedelta(days=1), w0.date() - timedelta(days=1) - (w1 - w0).to_pytimedelta()
    try:
        new = gd.make_branch(branch, n_new, rng, w1.date())
    finally:
        gd.START, gd.TODAY = saved
    code = BRANCHES.get(branch, {}).get("code", "CN")
    joined = pd.to_datetime(new["hoi_vien"]["ngay_tham_gia"])
    new_ids = list(new["hoi_vien"].loc[joined >= w0, "ma_hv"])
    start_no = max(int(str(x).split("-")[-1]) for x in hv["ma_hv"]) + 1
    remap = {old: f"{code}-{start_no + i:04d}" for i, old in enumerate(new_ids)}
    out_new = {}
    for t in SHEETS:
        df = new[t]
        df = df[df["ma_hv"].isin(new_ids)].copy()
        df["ma_hv"] = df["ma_hv"].map(remap)
        out_new[t] = df

    out = {
        "hoi_vien": out_new["hoi_vien"],
        "goi_the": pd.concat([pd.DataFrame(plans), out_new["goi_the"]], ignore_index=True),
        "goi_pt": pd.concat([pd.DataFrame(pts, columns=["ma_hv", "loai_pt", "so_buoi", "gia", "ngay_mua"]), out_new["goi_pt"]], ignore_index=True),
        "checkin": pd.concat([pd.DataFrame(checkins), out_new["checkin"]], ignore_index=True).sort_values(["ma_hv", "thoi_gian"]),
        "danh_gia": pd.concat([pd.DataFrame(ratings), out_new["danh_gia"]], ignore_index=True).sort_values(["ma_hv", "ngay"]),
    }
    folder = BRANCHES.get(branch, {}).get("folder", branch)
    path = BASE / "du_lieu_thoi_gian_toi" / f"{folder}_them_{w0:%d-%m-%Y}_den_{w1:%d-%m-%Y}.xlsx"
    gd._write_book(path, out)
    print(f"{branch}: {w0:%d/%m/%Y} → {w1:%d/%m/%Y}: {len(out['hoi_vien'])} khách mới, {len(out['goi_the'])} gói thẻ, "
          f"{len(out['goi_pt'])} gói PT, {len(out['checkin'])} check-in, {len(out['danh_gia'])} đánh giá -> {path.name}")
    return path


if __name__ == "__main__":
    b = sys.argv[1] if len(sys.argv) > 1 else "Quận 1"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    extend(b, n, sys.argv[3:] or None)
