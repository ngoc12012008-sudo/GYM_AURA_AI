"""Mô hình AI dự báo xác suất rời bỏ trong 90 ngày tới (Gradient Boosting, học từ lịch sử của chính phòng tập).

Cách học: chụp "ảnh" dữ liệu mỗi 14 ngày trong quá khứ, tính đặc trưng tại thời điểm đó,
rồi đối chiếu với việc hội viên có thật sự rời bỏ trong 90 ngày sau hay không.
Kiểm định: học trên giai đoạn cũ, chấm trên giai đoạn mới nhất chưa từng thấy (đo AUC).

Chạy: python ai_model.py   -> huấn luyện và in kết quả đánh giá
"""
import pickle
from datetime import datetime

import numpy as np
import pandas as pd

from churn import churn_label, data_end, data_version, load_data, score
from config import MODEL_DIR, RISK_ORDER, load_rules

HORIZON = 90
STEP = 14
FEATURES = {
    "buoi_14": "Số buổi 14 ngày gần nhất", "buoi_14_truoc": "Số buổi 14 ngày trước đó",
    "buoi_30": "Số buổi 30 ngày", "buoi_90": "Số buổi 90 ngày", "ngay_vang": "Số ngày vắng",
    "xu_huong": "Xu hướng tần suất", "con_lai": "Số ngày thẻ còn lại", "tham_nien": "Thâm niên (ngày)",
    "so_goi": "Số lần mua/gia hạn", "gia_thang": "Giá gói quy đổi/tháng", "co_pt": "Đang có gói PT",
    "pt_ngung": "Số ngày ngưng PT", "sao_gan_nhat": "Đánh giá gần nhất", "sao_tb": "Đánh giá trung bình",
    "khieu_nai_mo": "Khiếu nại chưa xử lý", "tap_nhom": "Tập nhóm / cùng bạn", "lop_nhom_30": "Buổi lớp nhóm 30 ngày",
    "clv": "CLV tích lũy", "churn_score": "Churn Score (quy tắc)",
}
MODEL_FILE = MODEL_DIR / "churn_model.pkl"


def sklearn_ok():
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


def _X(df):
    X = df.reindex(columns=list(FEATURES)).astype(float)
    X["ngay_vang"] = X["ngay_vang"].clip(upper=365)
    X["con_lai"] = X["con_lai"].clip(-60, 400)
    return X


def build_dataset(data, rules):
    end = data_end(data)
    first = max(data["goi_the"]["ngay_bat_dau"].min(), data["checkin"]["thoi_gian"].min()) + pd.Timedelta(days=60)
    last = end - pd.Timedelta(days=HORIZON + rules["an_han_ngay"])
    rows = []
    for a in pd.date_range(first.normalize(), last, freq=f"{STEP}D"):
        s = score(a, data, rules, explain=False)
        if s.empty:
            continue
        y = churn_label(a, data["goi_the"], end, HORIZON, rules["an_han_ngay"])
        s = s.join(y, on="ma_hv").dropna(subset=["da_bo"])
        s["asof"] = a
        rows.append(s)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _model():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_depth=4, min_samples_leaf=30,
                                          l2_regularization=1.0, random_state=0)


def train(data=None, rules=None, save=True):
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import roc_auc_score

    rules = rules or load_rules()
    data = data or load_data()
    ds = build_dataset(data, rules)
    if len(ds) < 300 or ds["da_bo"].nunique() < 2:
        raise ValueError("Chưa đủ lịch sử để huấn luyện AI (cần khoảng 6 tháng dữ liệu trở lên).")
    asofs = np.sort(ds["asof"].unique())
    test_from = asofs[-1] - np.timedelta64(42, "D")            # 3 mốc gần nhất làm tập kiểm tra
    train_to = test_from - np.timedelta64(HORIZON + rules["an_han_ngay"], "D")   # tránh nhãn chồng lấn
    tr, te = ds[ds["asof"] <= train_to], ds[ds["asof"] >= test_from]
    metrics = {"so_mau": len(ds), "so_moc": len(asofs), "ty_le_bo": float(ds["da_bo"].mean())}
    importance = None
    if len(tr) > 200 and tr["da_bo"].nunique() == 2 and te["da_bo"].nunique() == 2:
        m = _model().fit(_X(tr), tr["da_bo"])
        p = m.predict_proba(_X(te))[:, 1]
        metrics.update(auc_ai=float(roc_auc_score(te["da_bo"], p)),
                       auc_rule=float(roc_auc_score(te["da_bo"], te["churn_score"])),
                       n_train=len(tr), n_test=len(te))
        te = te.assign(p_ai=p)
        metrics["theo_muc"] = (te.groupby("muc_rui_ro")["da_bo"].agg(["size", "mean"])
                               .reindex(RISK_ORDER).dropna().reset_index().values.tolist())
        te["nhom_ai"] = pd.cut(te["p_ai"], [-0.01, 0.1, 0.3, 0.6, 1.0], labels=["<10%", "10-30%", "30-60%", ">60%"])
        metrics["theo_ai"] = (te.groupby("nhom_ai", observed=True)["da_bo"].agg(["size", "mean"])
                              .reset_index().astype({"nhom_ai": str}).values.tolist())
        top = te.sort_values("p_ai", ascending=False).head(max(1, int(len(te) * 0.2)))
        metrics["bat_duoc_top20"] = float(top["da_bo"].sum() / max(1, te["da_bo"].sum()))
        pi = permutation_importance(m, _X(te), te["da_bo"], scoring="roc_auc", n_repeats=4, random_state=0)
        importance = pd.Series(pi.importances_mean, index=[FEATURES[c] for c in FEATURES]).sort_values(ascending=False)
    model = _model().fit(_X(ds), ds["da_bo"])
    bundle = {"model": model, "metrics": metrics, "importance": importance,
              "trained_at": datetime.now().strftime("%d/%m/%Y %H:%M"), "version": data_version(),
              "rules": dict(rules)}
    if save:
        MODEL_DIR.mkdir(exist_ok=True)
        with open(MODEL_FILE, "wb") as f:
            pickle.dump(bundle, f)
    return bundle


def load_bundle():
    if not MODEL_FILE.exists():
        return None
    try:
        with open(MODEL_FILE, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def get_bundle(retrain=False):
    """Lấy mô hình đã lưu; tự huấn luyện lại nếu dữ liệu hoặc quy tắc đã đổi."""
    if not sklearn_ok():
        return None
    b = None if retrain else load_bundle()
    if b is None or b.get("version") != data_version() or b.get("rules") != load_rules():
        b = train()
    return b


def predict(bundle, scored):
    """Thêm cột p_ai (xác suất rời bỏ 90 ngày), ai_canh_bao, clv_du_bao_cn vào bảng đã chấm điểm."""
    s = scored.copy()
    if bundle is None or s.empty:
        s["p_ai"] = np.nan
        s["ai_canh_bao"] = ""
        return s
    s["p_ai"] = bundle["model"].predict_proba(_X(s))[:, 1]
    r = bundle["rules"]
    hidden = (s["p_ai"] >= 0.5) & (s["churn_score"] < r["nguong_high"])
    over = (s["p_ai"] < 0.15) & (s["churn_score"] >= r["nguong_high"])
    s["ai_canh_bao"] = np.select([hidden, over], ["Rủi ro ẩn", "AI thấy ít rủi ro"], "")
    # CLV dự báo cá nhân = chi tiêu/tháng × biên lợi nhuận × tuổi thọ kỳ vọng (1 / churn tháng)
    p_month = (1 - (1 - s["p_ai"].clip(0, 0.999)) ** (30 / HORIZON)).clip(lower=0.025)
    monthly = s["gia_thang"] + s["tong_pt"] / (s["tham_nien"].clip(lower=90) / 30)
    s["tuoi_tho_thang"] = (1 / p_month).clip(upper=36)
    s["clv_du_bao_cn"] = monthly * r["bien_loi_nhuan"] * s["tuoi_tho_thang"]
    return s


if __name__ == "__main__":
    import time
    t = time.time()
    b = train()
    m = b["metrics"]
    print(f"Huấn luyện xong trong {time.time() - t:.1f}s trên {m['so_mau']:,} mẫu ({m['so_moc']} mốc thời gian)")
    if "auc_ai" in m:
        print(f"AUC kiểm định – AI: {m['auc_ai']:.3f} | Quy tắc PDF: {m['auc_rule']:.3f}")
        print(f"Top 20% khách AI xếp rủi ro nhất bắt được {m['bat_duoc_top20']:.0%} số khách thật sự rời bỏ")
        print("Tỷ lệ bỏ thật theo nhóm AI:", [(g, n, f"{v:.0%}") for g, n, v in m["theo_ai"]])
        print(b["importance"].head(8).round(4).to_string())
