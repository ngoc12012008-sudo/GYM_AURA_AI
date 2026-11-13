"""Mô phỏng Monte Carlo chi phí sửa chữa / bảo trì và tính tỷ lệ quỹ dự phòng.

Chạy: python monte_carlo.py [số_tháng] [số_kịch_bản] [chi_nhánh]

Mô hình:
- Mỗi thiết bị, mỗi tháng có xác suất hỏng p = p_hong_thang × (1 + HE_SO_TUOI × tuổi), tuổi tăng dần theo tháng.
- Chi phí mỗi lần hỏng theo phân phối log-normal (trung bình = chi_phi_tb, phân vị 99% ≈ chi_phi_max),
  mô tả "đuôi dài" của sự cố lớn.
- Quỹ dự phòng: mỗi tháng trích TỶ_LỆ × doanh thu ghi nhận, trả chi phí phát sinh; theo dõi quỹ có bị âm không.
"""
import sqlite3
import sys

import numpy as np
import pandas as pd

from config import DB, RAW

HE_SO_TUOI = 0.15     # mỗi năm tuổi tăng 15% xác suất hỏng
COLS = ["ten", "chi_nhanh", "so_luong", "nam_su_dung", "p_hong_thang", "chi_phi_tb", "chi_phi_max"]


def load_equipment(branch=None):
    eq = None
    try:
        with sqlite3.connect(DB) as con:
            eq = pd.read_sql("SELECT * FROM thiet_bi", con)
    except Exception:
        files = list(RAW.glob("**/thiet_bi.csv"))
        if files:
            eq = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    if eq is None or eq.empty:
        return pd.DataFrame(columns=COLS)
    eq = eq.reindex(columns=COLS)
    if branch and branch != "Tất cả":
        eq = eq[eq["chi_nhanh"] == branch]
    return eq.reset_index(drop=True)


def monthly_revenue(branch=None):
    """Doanh thu ghi nhận trung bình/tháng của 3 tháng gần nhất (thẻ + PT)."""
    try:
        from churn import filter_branch, load_data, recognized_revenue
        return recognized_revenue(filter_branch(load_data(), branch))["tong"] or None
    except Exception:
        return None


def simulate(eq, months=12, n_sims=10_000, seed=0):
    """Trả về ma trận chi phí [n_sims, months] (VNĐ) và chi phí trung bình/năm theo hạng mục."""
    rng = np.random.default_rng(seed)
    costs = np.zeros((n_sims, months))
    by_item = {}
    eq = eq.dropna(subset=["so_luong", "p_hong_thang", "chi_phi_tb", "chi_phi_max"])
    for _, e in eq.iterrows():
        n = int(max(0, e.so_luong))
        if n == 0 or e.chi_phi_tb <= 0:
            continue
        cmax = max(float(e.chi_phi_max), float(e.chi_phi_tb) * 1.01)
        sigma = max(0.1, (np.log(cmax) - np.log(e.chi_phi_tb)) / 2.33 * 1.2)
        mu = np.log(e.chi_phi_tb) - sigma ** 2 / 2                 # để trung bình đúng bằng chi_phi_tb
        age0 = 0.0 if pd.isna(e.nam_su_dung) else float(e.nam_su_dung)
        item_total = np.zeros(n_sims)
        for m in range(months):
            p = min(0.95, max(0.0, e.p_hong_thang) * (1 + HE_SO_TUOI * (age0 + m / 12)))
            k = rng.binomial(n, p, n_sims)
            total_k = int(k.sum())
            if total_k:
                draws = np.minimum(rng.lognormal(mu, sigma, total_k), cmax * 1.5)
                c = np.bincount(np.repeat(np.arange(n_sims), k), weights=draws, minlength=n_sims)
                costs[:, m] += c
                item_total += c
        by_item[e.ten] = by_item.get(e.ten, 0) + item_total.mean() * 12 / months
    return costs, pd.Series(by_item, dtype=float).sort_values(ascending=False)


def fund_path(costs, revenue, rate, start_fund=0.0):
    """Số dư quỹ cuối mỗi tháng cho từng kịch bản."""
    return start_fund + np.cumsum(revenue * rate - costs, axis=1)


def p_shortfall(costs, revenue, rate, start_fund=0.0):
    """Xác suất quỹ bị âm ít nhất 1 lần trong kỳ."""
    return float((fund_path(costs, revenue, rate, start_fund).min(axis=1) < 0).mean())


def required_rate(costs, revenue, target=0.05, start_fund=0.0):
    """Tỷ lệ trích quỹ nhỏ nhất để xác suất thiếu quỹ <= target (tìm nhị phân)."""
    lo, hi = 0.0, 1.0
    if revenue <= 0:
        return float("nan")
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if p_shortfall(costs, revenue, mid, start_fund) <= target else (mid, hi)
    return hi


def required_start_fund(costs, revenue, rate, target=0.05):
    """Quỹ ban đầu cần có để xác suất thiếu quỹ <= target với tỷ lệ trích cho trước."""
    worst = -(np.cumsum(revenue * rate - costs, axis=1).min(axis=1))
    return float(max(0.0, np.quantile(worst, 1 - target)))


def summary(costs, revenue, rate, start_fund=0.0, target=0.05):
    m = costs.ravel()
    total = costs.sum(axis=1)
    mean_m = m.mean()
    return {
        "doanh_thu_thang": revenue,
        "thang": {"trung_binh": mean_m, "p50": np.quantile(m, .5), "p90": np.quantile(m, .9),
                  "p95": np.quantile(m, .95), "p99": np.quantile(m, .99), "max": m.max()},
        "ky": {"trung_binh": total.mean(), "p95": np.quantile(total, .95), "p99": np.quantile(total, .99)},
        "xac_suat_thang_vuot": {f"Tháng chi > {k}× trung bình": float((m > k * mean_m).mean()) for k in (2, 3, 5)},
        "ty_le_trich": rate,
        "p_thieu_quy": p_shortfall(costs, revenue, rate, start_fund),
        "ty_le_can_thiet": required_rate(costs, revenue, target, start_fund),
        "quy_ban_dau_can": required_start_fund(costs, revenue, rate, target),
        "muc_tieu": target,
    }


def fmt(x):
    return f"{x / 1e6:,.1f} tr"


if __name__ == "__main__":
    months = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10_000
    branch = sys.argv[3] if len(sys.argv) > 3 else None
    eq = load_equipment(branch)
    rev = monthly_revenue(branch) or 300_000_000
    costs, by_item = simulate(eq, months, n)
    rate = 0.06
    s = summary(costs, rev, rate)
    t = s["thang"]
    print(f"{branch or 'Toàn hệ thống'} | {n:,} kịch bản × {months} tháng | doanh thu ghi nhận ~{fmt(rev)}/tháng\n")
    print("CHI PHÍ SỬA CHỮA MỖI THÁNG")
    print(f"  Trung bình {fmt(t['trung_binh'])} | trung vị {fmt(t['p50'])}")
    print(f"  1/10 tháng tệ nhất vượt {fmt(t['p90'])} | 1/20 vượt {fmt(t['p95'])} | 1/100 vượt {fmt(t['p99'])}")
    print(f"  Tệ nhất trong mô phỏng: {fmt(t['max'])}")
    for k, v in s["xac_suat_thang_vuot"].items():
        print(f"  {k}: {v:.1%}")
    y = s["ky"]
    print(f"\nCẢ KỲ {months} THÁNG: trung bình {fmt(y['trung_binh'])} | 5% xấu nhất > {fmt(y['p95'])} | 1% > {fmt(y['p99'])}")
    print("\nHẠNG MỤC TỐN NHẤT (trung bình/năm)")
    for name, v in by_item.head(5).items():
        print(f"  {name:<34} {fmt(v)}")
    print("\nQUỸ DỰ PHÒNG")
    print(f"  Trích {rate:.0%} doanh thu, không có quỹ ban đầu: xác suất thiếu quỹ ít nhất 1 lần = {s['p_thieu_quy']:.1%}")
    print(f"  Để xác suất thiếu quỹ <= {s['muc_tieu']:.0%}: cần trích {s['ty_le_can_thiet']:.1%} doanh thu")
    print(f"  Hoặc giữ {rate:.0%} và để sẵn quỹ ban đầu {fmt(s['quy_ban_dau_can'])}")
