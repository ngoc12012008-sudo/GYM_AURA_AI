"""Chấm điểm Churn Score, CLV, Priority Score và nhóm can thiệp (theo tài liệu Aura, mục IV-VI).

Mọi phép tính chỉ dùng dữ liệu TRƯỚC ngày `asof`, nên có thể chấm lại tại một ngày trong quá khứ để kiểm tra.
"""
import sqlite3

import numpy as np
import pandas as pd

from config import (DB, GROUP_PT, MEMBERSHIP_PLANS, RISK_ORDER, SCRIPTS, load_rules)

EMPTY = {
    "goi_pt": ["ma_hv", "loai_pt", "so_buoi", "gia", "ngay_mua", "chi_nhanh"],
    "danh_gia": ["ma_hv", "ngay", "so_sao", "khieu_nai", "da_xu_ly", "noi_dung", "chi_nhanh"],
    "thiet_bi": ["ten", "chi_nhanh", "so_luong", "nam_su_dung", "p_hong_thang", "chi_phi_tb", "chi_phi_max"],
}
DATES = {"hoi_vien": ["ngay_tham_gia", "ngay_sinh"], "goi_the": ["ngay_bat_dau", "ngay_het_han"],
         "checkin": ["thoi_gian"], "goi_pt": ["ngay_mua"], "danh_gia": ["ngay"]}


# ------------------------------------------------------------------ đọc dữ liệu
def data_version():
    """Chuỗi thay đổi khi dữ liệu thay đổi (dùng làm khóa cache)."""
    if not DB.exists():
        return "none"
    parts = []
    with sqlite3.connect(DB) as con:
        for t, c in [("hoi_vien", "ngay_tham_gia"), ("goi_the", "ngay_het_han"), ("checkin", "thoi_gian"),
                     ("goi_pt", "ngay_mua"), ("danh_gia", "ngay"), ("thiet_bi", "chi_phi_tb")]:
            try:
                parts.append(str(con.execute(f"SELECT count(*), max({c}) FROM {t}").fetchone()))
            except Exception:
                parts.append("-")
    return "|".join(parts)


def load_data():
    data = {}
    with sqlite3.connect(DB) as con:
        names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ["hoi_vien", "goi_the", "checkin", "goi_pt", "danh_gia", "thiet_bi"]:
            if t in names:
                df = pd.read_sql(f"SELECT * FROM {t}", con)
            else:
                df = pd.DataFrame(columns=EMPTY.get(t, []))
            for c in DATES.get(t, []):
                if c in df:
                    df[c] = pd.to_datetime(df[c], errors="coerce", format="mixed")
            data[t] = df
    ci = data["checkin"]
    if "hinh_thuc" not in ci:
        ci["hinh_thuc"] = "Tự do"
    hv = data["hoi_vien"]
    if "tap_cung_ban" not in hv:
        hv["tap_cung_ban"] = 0
    hv["tap_cung_ban"] = hv["tap_cung_ban"].fillna(0).astype(int)
    return data


def data_end(data):
    """Ngày 'hôm nay' của dữ liệu = ngày sau lượt check-in cuối cùng."""
    return data["checkin"]["thoi_gian"].max().normalize() + pd.Timedelta(days=1)


def filter_branch(data, branch):
    if not branch or branch == "Tất cả":
        return data
    return {k: (v[v["chi_nhanh"] == branch] if "chi_nhanh" in v.columns else v) for k, v in data.items()}


# ------------------------------------------------------------------ trạng thái hợp đồng
def _extend_chain(end, gt, tol_days):
    """Nối các gói liên tiếp (gói sau bắt đầu trong vòng tol_days sau khi gói trước hết hạn)."""
    end = end.copy()
    g = gt[["ma_hv", "ngay_bat_dau", "ngay_het_han"]]
    for _ in range(80):
        m = g.merge(end.rename("e"), left_on="ma_hv", right_index=True)
        m = m[(m["ngay_bat_dau"] <= m["e"] + pd.Timedelta(days=tol_days)) & (m["ngay_het_han"] > m["e"])]
        if m.empty:
            break
        new = m.groupby("ma_hv")["ngay_het_han"].max()
        end.loc[new.index] = new
    return end


def membership_state(asof, gt, grace=30, live=False):
    """Gói hiện tại của từng hội viên còn hạn hoặc vừa hết hạn (trong `grace` ngày) tại asof."""
    g = gt[gt["ngay_bat_dau"] <= asof]
    if g.empty:
        return pd.DataFrame()
    cur = g.loc[g.groupby("ma_hv")["ngay_het_han"].idxmax()].set_index("ma_hv")
    cur = cur[["loai_goi", "gia", "ngay_bat_dau", "ngay_het_han"]].copy()
    if live:   # dữ liệu thật: gói gia hạn trước (bắt đầu trong tương lai) cũng tính
        cur["ngay_het_han"] = _extend_chain(cur["ngay_het_han"], gt, 3)
    cur["con_lai"] = (cur["ngay_het_han"] - asof).dt.days
    cur = cur[cur["con_lai"] >= -grace]
    cur["trang_thai"] = np.where(cur["con_lai"] >= 0, "Còn hạn", "Vừa hết hạn")
    days = (cur["ngay_het_han"] - cur["ngay_bat_dau"]).dt.days.clip(lower=1) + 1
    cur["gia_thang"] = cur["gia"] / (days / 30).clip(lower=1)
    cur["so_goi"] = g.groupby("ma_hv").size().reindex(cur.index).fillna(1)
    return cur


def churn_label(asof, gt, end_of_data, horizon=90, grace=30):
    """Nhãn thật: 1 nếu hội viên rời bỏ (hết hạn và không gia hạn trong `grace` ngày) trong `horizon` ngày tới.
    NaN nếu chưa đủ dữ liệu để biết."""
    st = membership_state(asof, gt, grace)
    if st.empty:
        return pd.Series(dtype=float, name="da_bo")
    final = _extend_chain(st["ngay_het_han"], gt, grace)
    left = final < asof + pd.Timedelta(days=horizon)
    known = (~left) | (final + pd.Timedelta(days=grace) <= end_of_data)
    y = left.astype(float).where(known)
    return y.rename("da_bo")


# ------------------------------------------------------------------ đặc trưng
def features(asof, data, rules=None, live=False):
    r = rules or load_rules()
    asof = pd.Timestamp(asof).normalize()
    hv, gt, ci, pt, dg = data["hoi_vien"], data["goi_the"], data["checkin"], data["goi_pt"], data["danh_gia"]
    st = membership_state(asof, gt, r["an_han_ngay"], live)
    if st.empty:
        return pd.DataFrame()
    df = hv.set_index("ma_hv").join(st, how="inner")
    df = df[df["ngay_tham_gia"] <= asof]
    idx = df.index

    c = ci[(ci["thoi_gian"] < asof) & ci["ma_hv"].isin(idx)]
    ago = (asof - c["thoi_gian"]).dt.total_seconds() / 86400
    W = r["khong_tap_ngay"]

    def cnt(mask):
        return c[mask].groupby("ma_hv").size().reindex(idx, fill_value=0)

    df["buoi_14"] = cnt(ago <= W)
    df["buoi_14_truoc"] = cnt((ago > W) & (ago <= 2 * W))
    df["buoi_30"] = cnt(ago <= 30)
    df["buoi_90"] = cnt(ago <= 90)
    df["lop_nhom_30"] = cnt((ago <= 30) & (c["hinh_thuc"] == "Lớp nhóm"))
    last = c.groupby("ma_hv")["thoi_gian"].max().reindex(idx)
    df["lan_cuoi"] = last
    df["ngay_vang"] = (asof - last).dt.days.fillna((asof - df["ngay_tham_gia"]).dt.days).astype(int)
    df["tham_nien"] = (asof - df["ngay_tham_gia"]).dt.days
    prev = df["buoi_14_truoc"]
    df["xu_huong"] = ((df["buoi_14"] - prev) / prev.where(prev > 0)).fillna(0.0)

    # PT
    p = pt[(pt["ngay_mua"] <= asof) & pt["ma_hv"].isin(idx)] if len(pt) else pt
    pt_ci = c[c["hinh_thuc"] == "PT"]
    bought = p.groupby("ma_hv")["so_buoi"].sum().reindex(idx, fill_value=0) if len(p) else pd.Series(0, idx)
    used = pt_ci.groupby("ma_hv").size().reindex(idx, fill_value=0)
    last_buy = p.groupby("ma_hv")["ngay_mua"].max().reindex(idx) if len(p) else pd.Series(pd.NaT, idx)
    last_pt = pt_ci.groupby("ma_hv")["thoi_gian"].max().reindex(idx)
    df["pt_con_buoi"] = (bought - used).clip(lower=0).astype(int)
    df["co_pt"] = ((df["pt_con_buoi"] > 0) & ((asof - last_buy).dt.days <= 240)).astype(int)
    if "co_pt" in hv.columns and not len(pt):      # dữ liệu cũ chỉ có cột co_pt
        df["co_pt"] = hv.set_index("ma_hv")["co_pt"].reindex(idx).fillna(0).astype(int)
    last_act = pd.concat([last_pt, last_buy], axis=1).max(axis=1)
    df["pt_ngung"] = (asof - last_act).dt.days.fillna(0).astype(int).where(df["co_pt"] == 1, 0)
    latest_pt = p.sort_values("ngay_mua").groupby("ma_hv")["loai_pt"].last().reindex(idx) if len(p) else pd.Series(None, idx)
    df["pt_nhom"] = (latest_pt.isin(GROUP_PT) & (df["co_pt"] == 1)).astype(int)
    df["tong_pt"] = p.groupby("ma_hv")["gia"].sum().reindex(idx, fill_value=0) if len(p) else 0.0

    # Đánh giá / khiếu nại
    d = dg[(dg["ngay"] < asof) & dg["ma_hv"].isin(idx)] if len(dg) else dg
    if len(d):
        rec = d[(asof - d["ngay"]).dt.days <= r["danh_gia_ngay"]].sort_values("ngay")
        df["sao_gan_nhat"] = rec.groupby("ma_hv")["so_sao"].last().reindex(idx)
        df["sao_tb"] = d.groupby("ma_hv")["so_sao"].mean().reindex(idx)
        opn = d[(d["khieu_nai"] == 1) & (d["da_xu_ly"] == 0)]
        df["khieu_nai_mo"] = opn.groupby("ma_hv").size().reindex(idx, fill_value=0)
    else:
        df["sao_gan_nhat"], df["sao_tb"], df["khieu_nai_mo"] = np.nan, np.nan, 0
    df["tap_nhom"] = ((df["tap_cung_ban"] == 1) | (df["lop_nhom_30"] >= r["nhom_toi_thieu_buoi"])
                      | (df["pt_nhom"] == 1)).astype(int)

    # CLV (MVP): hợp đồng hiện tại + chi tiêu quá khứ + gói PT
    g = gt[(gt["ngay_bat_dau"] <= asof) & gt["ma_hv"].isin(idx)]
    df["tong_the"] = g.groupby("ma_hv")["gia"].sum().reindex(idx, fill_value=0)
    df["clv"] = df["tong_the"] + df["tong_pt"]
    return df


# ------------------------------------------------------------------ chấm điểm
def score(asof, data, rules=None, live=False, explain=True):
    r = rules or load_rules()
    df = features(asof, data, r, live)
    if df.empty:
        return df
    # 1. Tần suất
    drop = -df["xu_huong"]
    no_visit = df["buoi_14"] == 0
    df["d_tan_suat"] = np.select(
        [no_visit, (df["buoi_14_truoc"] > 0) & (drop > r["giam_manh_pct"]),
         (df["buoi_14_truoc"] > 0) & (drop >= r["giam_vua_pct"])],
        [r["diem_khong_tap"], r["diem_giam_manh"], r["diem_giam_vua"]], 0)
    # 2. Hợp đồng
    cl = df["con_lai"]
    df["d_hop_dong"] = np.select(
        [cl < r["hd_rat_gap_ngay"], cl < r["hd_gap_ngay"], cl <= r["hd_vang_ngay"]],
        [r["diem_hd_rat_gap"], r["diem_hd_gap"], r["diem_hd_vang"]], 0)
    # 3. Phản hồi
    sao = df["sao_gan_nhat"]
    df["d_phan_hoi"] = (np.select([sao <= 2, sao >= 4], [r["diem_sao_thap"], r["diem_sao_cao"]], 0)
                        + np.where(df["khieu_nai_mo"] > 0, r["diem_khieu_nai"], 0))
    # 4. PT & nhóm
    df["d_pt_nhom"] = (np.where((df["co_pt"] == 1) & (df["pt_ngung"] > r["pt_ngung_ngay"]), r["diem_pt_ngung"], 0)
                       + np.where(df["tap_nhom"] == 1, r["diem_tap_nhom"], 0))
    raw = df[["d_tan_suat", "d_hop_dong", "d_phan_hoi", "d_pt_nhom"]].sum(axis=1)
    df["churn_score"] = raw.clip(0, 100).astype(int)
    df["muc_rui_ro"] = np.select(
        [df["churn_score"] >= r["nguong_critical"], df["churn_score"] >= r["nguong_high"],
         df["churn_score"] >= r["nguong_medium"]], RISK_ORDER[:3], RISK_ORDER[3])
    df["hang_clv"] = np.select([df["clv"] > r["clv_vip"], df["clv"] >= r["clv_medium"]], ["VIP", "Medium"], "Low")
    df["priority"] = (df["churn_score"] * df["clv"] / 1e6).round(1)      # = Churn × CLV (triệu)
    high = df["churn_score"] >= r["nguong_high"]
    df["nhom_can_thiep"] = np.select(
        [high & (df["hang_clv"] == "VIP"), high & (df["hang_clv"] == "Medium"), high,
         df["churn_score"] >= r["nguong_medium"]],
        ["Nhóm 1 – Ưu tiên số 1", "Nhóm 2 – Ưu tiên số 2", "Nhóm 3 – Ưu tiên số 3", "Theo dõi sát"],
        "Nhóm 4 – Theo dõi")
    df["phu_trach"] = df["nhom_can_thiep"].map(lambda g: SCRIPTS[g][0])
    df["kich_ban"] = df["nhom_can_thiep"].map(lambda g: SCRIPTS[g][1])
    if explain:
        df["ly_do"] = [_reasons(x, r) for x in df.itertuples()]
    df = df.reset_index().rename(columns={"index": "ma_hv"})
    return df.sort_values(["priority", "churn_score"], ascending=False).reset_index(drop=True)


def _reasons(x, r):
    why = []
    if x.d_tan_suat == r["diem_khong_tap"]:
        why.append(f"không đi tập {x.ngay_vang} ngày")
    elif x.d_tan_suat > 0:
        why.append(f"số buổi 14 ngày giảm {abs(x.xu_huong):.0%} ({x.buoi_14_truoc}→{x.buoi_14})")
    if x.d_hop_dong > 0:
        why.append("thẻ đã hết hạn" if x.con_lai < 0 else f"thẻ còn {x.con_lai} ngày")
    if x.d_phan_hoi > 0 and not pd.isna(x.sao_gan_nhat) and x.sao_gan_nhat <= 2:
        why.append(f"đánh giá {int(x.sao_gan_nhat)} sao")
    if x.khieu_nai_mo > 0:
        why.append("khiếu nại chưa xử lý")
    if x.co_pt and x.pt_ngung > r["pt_ngung_ngay"]:
        why.append(f"ngưng PT {x.pt_ngung} ngày")
    good = []
    if not pd.isna(x.sao_gan_nhat) and x.sao_gan_nhat >= 4:
        good.append(f"đánh giá {int(x.sao_gan_nhat)} sao")
    if x.tap_nhom:
        good.append("tập nhóm/cùng bạn")
    s = ", ".join(why) if why else "tập đều, ổn định"
    return s[:1].upper() + s[1:] + (f"; điểm tốt: {', '.join(good)}" if good else "")


def breakdown(row, rules=None):
    """Bảng điểm từng nhóm chỉ số cho 1 hội viên."""
    return pd.DataFrame({
        "Nhóm chỉ số": ["Tần suất tập (45%)", "Thời hạn hợp đồng (30%)", "Phản hồi dịch vụ (15%)", "PT & tập nhóm (10%)"],
        "Điểm": [row["d_tan_suat"], row["d_hop_dong"], row["d_phan_hoi"], row["d_pt_nhom"]],
    })


# ------------------------------------------------------------------ tin nhắn mẫu
def message_for(x, branch_name="Aura Fitness"):
    ten = str(x["ho_ten"]).split()[-1]
    xung = "anh" if str(x.get("gioi_tinh", "")).startswith("Nam") else "chị" if str(x.get("gioi_tinh", "")).startswith("Nữ") else "bạn"
    g = x["nhom_can_thiep"]
    het = "đã hết hạn" if x["con_lai"] < 0 else f"còn {x['con_lai']} ngày"
    if g.startswith("Nhóm 1"):
        return (f"Chào {xung} {ten}, em là quản lý {branch_name}. Lâu rồi không thấy {xung} ghé phòng tập, "
                f"em muốn hỏi thăm xem {xung} có gặp vấn đề gì không ạ. Để cảm ơn {xung} đã đồng hành, "
                f"Aura xin tặng {xung} 1 buổi PT 1 kèm 1 miễn phí và voucher nâng cấp gói khi gia hạn. "
                f"Em gọi lại cho {xung} lúc nào tiện ạ?")
    if g.startswith("Nhóm 2"):
        return (f"Aura Fitness: Chào {xung} {ten}! Thẻ tập của {xung} {het}. Aura đã giữ sẵn lịch tập phù hợp cho {xung} "
                f"tuần này. Gia hạn trong 7 ngày để nhận ưu đãi GIẢM 15%. Trả lời tin nhắn này để được hỗ trợ nhé!")
    if g.startswith("Nhóm 3"):
        return (f"Aura Fitness: Chào {xung} {ten}, Aura rất muốn biết điều gì khiến {xung} chưa đến tập thường xuyên. "
                f"Mời {xung} trả lời khảo sát 1 phút: [link]. Nếu bận, {xung} có thể bảo lưu thẻ hoặc chuyển sang "
                f"gói Day Pass 50.000đ/buổi linh hoạt.")
    if g == "Theo dõi sát":
        return (f"Aura Fitness: Chào {xung} {ten}! Tuần này Aura có các lớp Yoga/GroupX mới khung giờ tối, "
                f"mời {xung} đăng ký tập thử cùng bạn bè. Hẹn gặp {xung} tại phòng tập!")
    return (f"Aura Fitness: Chúc mừng {xung} {ten} đã duy trì {x['buoi_30']} buổi tập trong 30 ngày qua! "
            f"Mời {xung} đo InBody miễn phí để theo dõi tiến bộ nhé.")


# ------------------------------------------------------------------ doanh thu & CLV dự báo
def recognized_revenue(data, months=3):
    """Doanh thu ghi nhận/tháng (chia đều giá gói theo ngày; PT chia đều 90 ngày) trong `months` tháng gần nhất."""
    end = data_end(data) if len(data["checkin"]) else pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=30 * months)

    def spread(price, s, e):
        days = (e - s).dt.days.clip(lower=1)
        ov = (e.clip(upper=end) - s.clip(lower=start)).dt.days.clip(lower=0)
        return float((price * ov / days).sum()) / months

    gt = data["goi_the"]
    mem = spread(gt["gia"], gt["ngay_bat_dau"], gt["ngay_het_han"] + pd.Timedelta(days=1)) if len(gt) else 0.0
    pt = data["goi_pt"]
    ptr = spread(pt["gia"], pt["ngay_mua"], pt["ngay_mua"] + pd.Timedelta(days=90)) if len(pt) else 0.0
    return {"the": mem, "pt": ptr, "tong": mem + ptr}


def monthly_churn_rate(data, rules=None, horizon=90):
    """Tỷ lệ rời bỏ hàng tháng, đo trên giai đoạn gần nhất đã biết kết quả."""
    r = rules or load_rules()
    end = data_end(data)
    asof = end - pd.Timedelta(days=horizon + r["an_han_ngay"])
    y = churn_label(asof, data["goi_the"], end, horizon, r["an_han_ngay"]).dropna()
    if len(y) < 10:
        return None
    rate_h = y.mean()
    return 1 - (1 - rate_h) ** (30 / horizon)


def predictive_clv(data, rules=None, margin=None):
    r = rules or load_rules()
    margin = r["bien_loi_nhuan"] if margin is None else margin
    rev = recognized_revenue(data)
    active = len(membership_state(data_end(data), data["goi_the"], 0, live=True))
    churn = monthly_churn_rate(data, r)
    arpu = rev["tong"] / active if active else 0
    life = 1 / churn if churn else None
    return {"arpu": arpu, "bien_loi_nhuan": margin, "churn_thang": churn, "tuoi_tho": life,
            "clv_du_bao": arpu * margin * life if life else None, "hoi_vien_hoat_dong": active,
            "doanh_thu_thang": rev["tong"]}
