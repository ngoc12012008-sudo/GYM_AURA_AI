"""Aura Gym AI – web nội bộ (Flask). Mở bằng run.py hoặc: python web.py

Một web duy nhất: cập nhật dữ liệu ở trang "Cập nhật dữ liệu", hệ thống tự tính lại điểm và AI,
không cần chạy lại chương trình.
"""
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import io
import json
import sqlite3
import threading
import time
import uuid
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd
from flask import Flask, abort, jsonify, render_template, request, send_file

import ai_model
import backup
import churn
import etl
from config import (BRANCHES, CLV_COLORS, CLV_ORDER, CONTACT_CHANNELS, CONTACT_RESULTS, DB, DEFAULT_RULES,
                    GROUP_ORDER, MEMBERSHIP_PLANS, PT_PACKAGES, RISK_COLORS, RISK_ORDER, RULE_LABELS,
                    SCRIPTS, load_rules, reset_rules, save_rules)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
ALL = "Tất cả chi nhánh"
GROUP_COLORS = {"Nhóm 1 – Ưu tiên số 1": "#8e2f25", "Nhóm 2 – Ưu tiên số 2": "#b8662e",
                "Nhóm 3 – Ưu tiên số 3": "#c39a3e", "Theo dõi sát": "#b9b8c0", "Nhóm 4 – Theo dõi": "#8e82be"}
RISK_COLORS_UI = RISK_COLORS
CLV_COLORS_UI = CLV_COLORS
RISK_KEY = {"Cực kỳ nguy hiểm": "critical", "Rủi ro cao": "high", "Rủi ro trung bình": "medium", "An toàn": "low"}
NAV = [
    ("overview", "/", "bi-house", "Trang chủ"),
    ("action", "/can-thiep", "bi-telephone", "Cần gọi"),
    ("member", "/hoi-vien", "bi-people", "Hội viên"),
    ("ai", "/ai", "bi-graph-up", "Dự báo AI"),
    ("clv", "/clv", "bi-wallet2", "Doanh thu & CLV"),
    ("reserve", "/du-phong", "bi-wrench", "Quỹ sửa chữa"),
    ("_admin", None, None, "Dữ liệu"),
    ("data", "/cap-nhat", "bi-arrow-repeat", "Cập nhật dữ liệu"),
    ("rules", "/quy-tac", "bi-sliders", "Quy tắc chấm điểm"),
]


# ====================================================================== bộ nhớ dữ liệu
class Store:
    """Giữ dữ liệu + điểm trong bộ nhớ; tự tính lại khi dữ liệu hoặc quy tắc thay đổi."""

    def __init__(self):
        self.lock = threading.RLock()
        self.key = None
        self.state = None

    def get(self, force=False):
        with self.lock:
            if not etl.schema_ok():
                return None
            rules = load_rules()
            key = (churn.data_version(), json.dumps(rules, sort_keys=True))
            if force or key != self.key:
                t = time.time()
                data = churn.load_data()
                end = churn.data_end(data)
                # mỗi chi nhánh chấm theo ngày dữ liệu mới nhất của chính chi nhánh đó
                parts = []
                for br in sorted(data["hoi_vien"]["chi_nhanh"].dropna().unique()):
                    db = churn.filter_branch(data, br)
                    if len(db["checkin"]) and len(db["goi_the"]):
                        parts.append(churn.score(churn.data_end(db), db, rules, live=True))
                s = pd.concat([p for p in parts if not p.empty], ignore_index=True) if parts else churn.score(end, data, rules, live=True)
                s = s.sort_values(["priority", "churn_score"], ascending=False).reset_index(drop=True)
                bundle, err = None, None
                if ai_model.sklearn_ok():
                    try:
                        bundle = ai_model.get_bundle()
                    except Exception as e:  # noqa: BLE001
                        err = str(e)
                else:
                    err = "Chưa cài scikit-learn – chạy lại run.py để tự cài."
                s = ai_model.predict(bundle, s)
                self.state = dict(data=data, end=end, scores=s, bundle=bundle, ai_error=err, rules=rules,
                                  branches=sorted(data["hoi_vien"]["chi_nhanh"].dropna().unique(),
                                                  key=lambda b: (b not in BRANCHES, b)),
                                  computed_at=datetime.now(), seconds=time.time() - t)
                self.key = key
            return self.state


STORE = Store()
PENDING = {}   # token -> dict(clean, branch, append, t)


# ====================================================================== tiện ích
def vn_num(x, d=0):
    s = f"{x:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


AVATAR_COLORS = ["var(--brand-soft)"]


@app.template_filter("avc")
def f_avatar_color(name):
    return AVATAR_COLORS[sum(map(ord, str(name))) % len(AVATAR_COLORS)]


@app.template_filter("ini")
def f_initials(name):
    p = str(name or "?").split()
    return (p[-2][0] + p[-1][0]).upper() if len(p) > 1 else p[0][:2].upper()


@app.template_filter("tr")
def f_tr(x):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{vn_num(x / 1e6, 1)} tr"


@app.template_filter("vnd")
def f_vnd(x):
    return "–" if x is None or pd.isna(x) else f"{vn_num(x)} đ"


@app.template_filter("pct")
def f_pct(x, d=0):
    return "–" if x is None or pd.isna(x) else f"{vn_num(x * 100, d)}%"


@app.template_filter("num")
def f_num(x, d=0):
    return "–" if x is None or pd.isna(x) else vn_num(x, d)


@app.template_filter("ddmm")
def f_ddmm(x):
    return "–" if x is None or pd.isna(x) else pd.Timestamp(x).strftime("%d/%m/%Y")


def records(df, cols=None):
    df = df if cols is None else df[[c for c in cols if c in df.columns]]
    return json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))


def current_branch(st):
    from urllib.parse import unquote
    import unicodedata
    raw = request.args.get("cn") or unquote(request.cookies.get("cn") or "") or ALL
    nf = lambda x: unicodedata.normalize("NFC", str(x)).strip()
    return next((x for x in st["branches"] if nf(x) == nf(raw)), ALL)


def scoped(st, branch):
    s = st["scores"]
    if branch != ALL:
        s = s[s["chi_nhanh"] == branch]
    return s, churn.filter_branch(st["data"], None if branch == ALL else branch)


def contacts():
    if not DB.exists():
        return pd.DataFrame(columns=["ma_hv", "thoi_gian", "nhan_vien", "ket_qua", "ghi_chu", "kenh"])
    with sqlite3.connect(DB) as con:
        etl.ensure_contact_table(con)
        lh = pd.read_sql("SELECT * FROM lien_he", con)
    lh["thoi_gian"] = pd.to_datetime(lh["thoi_gian"], errors="coerce")
    return lh


def last_contacts():
    lh = contacts()
    if lh.empty:
        return {}
    last = lh.sort_values("thoi_gian").groupby("ma_hv").last()
    return {ma: {"t": r.thoi_gian.strftime("%d/%m %H:%M"), "kq": r.ket_qua, "ts": r.thoi_gian.isoformat()}
            for ma, r in last.iterrows()}


def page(template, active, **kw):
    st = STORE.get()
    snaps = backup.list_snapshots()
    last_action = snaps[0] if snaps else None
    if st is None and active not in ("data",):
        return render_template("empty.html", nav=NAV, active=active, st=None, branch=ALL, page_title="Chưa có dữ liệu",
                               last_action=last_action)
    branch = current_branch(st) if st else ALL
    ctx = dict(nav=NAV, active=active, st=st, branch=branch, ALL=ALL, RISK_ORDER=RISK_ORDER,
               RISK_COLORS=RISK_COLORS_UI, CLV_COLORS=CLV_COLORS_UI, GROUP_COLORS=GROUP_COLORS,
               GROUP_ORDER=GROUP_ORDER, CLV_ORDER=CLV_ORDER, RISK_KEY=RISK_KEY, rules=load_rules(),
               branch_info=BRANCHES.get(branch), last_action=last_action, history=snaps)
    ctx.update(kw)
    if st:
        s, d = scoped(st, branch)
        r = ctx["rules"]
        end_b = churn.data_end(d) if len(d["checkin"]) else st["end"]
        ctx.update(S=s, D=d, end=end_b, data_date=f_ddmm(end_b - pd.Timedelta(days=1)),
                   n_urgent=int((s["churn_score"] >= r["nguong_high"]).sum()),
                   ai_ok=st["bundle"] is not None, ai_time=st["bundle"]["trained_at"] if st["bundle"] else None)
        for k, fn in kw.items():
            if callable(fn):
                ctx[k] = fn(st, s, d, branch)
    return render_template(template, **ctx)


# ====================================================================== trang
@app.route("/")
def overview():
    def build(st, S, D, branch):
        r = load_rules()
        high = S["churn_score"] >= r["nguong_high"]
        pc = churn.predictive_clv(D, r)
        ci = D["checkin"]
        wk_end = churn.data_end(D).to_period("W").start_time   # bỏ tuần hiện tại chưa trọn
        ci = ci[(ci["thoi_gian"] >= wk_end - pd.Timedelta(weeks=26)) & (ci["thoi_gian"] < wk_end)]
        wk = ci.assign(t=ci["thoi_gian"].dt.to_period("W").dt.start_time).groupby("t").agg(
            luot=("ma_hv", "size"), khach=("ma_hv", "nunique")).reset_index()
        mat = pd.crosstab(S["hang_clv"], S["muc_rui_ro"]).reindex(index=CLV_ORDER, columns=RISK_ORDER, fill_value=0)
        by_branch = (S.groupby(["chi_nhanh", "muc_rui_ro"]).size().unstack(fill_value=0)
                     .reindex(columns=RISK_ORDER, fill_value=0))
        lh = contacts()
        lh = lh[lh["ma_hv"].isin(S["ma_hv"])].sort_values("thoi_gian", ascending=False)
        names = S.set_index("ma_hv")["ho_ten"]
        feed = [dict(ma=x.ma_hv, ten=names.get(x.ma_hv, x.ma_hv), kq=x.ket_qua, nv=x.nhan_vien, kenh=x.kenh or "",
                     t=x.thoi_gian.strftime("%d/%m %H:%M"), note=x.ghi_chu or "") for x in lh.head(8).itertuples()]
        recent = lh[lh["thoi_gian"] >= pd.Timestamp.now() - pd.Timedelta(days=30)]
        called7 = set(lh.loc[lh["thoi_gian"] >= pd.Timestamp.now() - pd.Timedelta(days=7), "ma_hv"])
        todo = S[high & ~S["ma_hv"].isin(called7)]
        now = datetime.now()
        thu = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"][now.weekday()]
        ok = recent["ket_qua"].isin(CONTACT_RESULTS[:4]).mean() if len(recent) else None
        return dict(
            k_total=len(S), k_expired=int((S["trang_thai"] == "Vừa hết hạn").sum()), k_high=int(high.sum()),
            k_high_pct=high.mean() if len(S) else 0, k_risk_rev=S.loc[high, "gia"].sum(), k_clv=S["clv"].mean(),
            k_vip=int((S["hang_clv"] == "VIP").sum()), pc=pc,
            top=records(S[high].head(8), ["ma_hv", "ho_ten", "so_dien_thoai", "chi_nhanh", "churn_score", "muc_rui_ro",
                                          "hang_clv", "clv", "priority", "ly_do", "phu_trach", "p_ai"]),
            charts=dict(
                risk=[int((S["muc_rui_ro"] == k).sum()) for k in RISK_ORDER],
                weeks=[t.strftime("%d/%m") for t in wk["t"]], visits=wk["luot"].tolist(), people=wk["khach"].tolist(),
                groups=[int((S["nhom_can_thiep"] == g).sum()) for g in GROUP_ORDER],
                branches=list(by_branch.index), by_branch={k: by_branch[k].astype(int).tolist() for k in RISK_ORDER},
            ),
            matrix=mat, mat_max=max(1, int(mat.values.max())), feed=feed, n_recent=len(recent), ok_rate=ok,
            queue=records(todo.head(8), ["ma_hv", "ho_ten", "so_dien_thoai", "chi_nhanh", "churn_score", "muc_rui_ro",
                                         "hang_clv", "clv", "ly_do", "phu_trach", "con_lai"]),
            n_todo=len(todo), n_called7=len(called7 & set(S["ma_hv"])), today=f"{thu}, {now:%d/%m/%Y}",
            dots=S[["ma_hv", "ho_ten", "churn_score", "muc_rui_ro", "hang_clv", "chi_nhanh"]].assign(
                goi=S["ma_hv"].isin(called7).astype(int)).values.tolist())
    return page("overview.html", "overview", ov=build)


@app.route("/can-thiep")
def action():
    def build(st, S, D, branch):
        cols = ["ma_hv", "ho_ten", "so_dien_thoai", "gioi_tinh", "chi_nhanh", "churn_score", "muc_rui_ro", "p_ai",
                "ai_canh_bao", "clv", "hang_clv", "priority", "nhom_can_thiep", "phu_trach", "kich_ban", "ly_do",
                "con_lai", "loai_goi", "ngay_het_han", "buoi_30", "trang_thai"]
        rows = records(S, cols)
        for r in rows:
            r["msg"] = churn.message_for({**r, "con_lai": r["con_lai"], "buoi_30": r["buoi_30"]}, f"Aura {r['chi_nhanh']}")
        return dict(rows=rows, last=last_contacts())
    return page("action.html", "action", act=build, results=CONTACT_RESULTS, channels=CONTACT_CHANNELS)


@app.route("/hoi-vien")
@app.route("/hoi-vien/<ma>")
def member(ma=None):
    def build(st, S, D, branch):
        lst = records(S, ["ma_hv", "ho_ten", "so_dien_thoai", "chi_nhanh", "churn_score", "muc_rui_ro"])
        if ma is None or ma not in set(st["scores"]["ma_hv"]):
            return dict(members=lst, x=None, missing=ma)
        x = st["scores"].set_index("ma_hv").loc[ma]
        data = st["data"]
        ci = data["checkin"]
        end_m = churn.data_end(churn.filter_branch(data, x.chi_nhanh))
        ci = ci[(ci["ma_hv"] == ma) & (ci["thoi_gian"] >= end_m - pd.Timedelta(weeks=26))]
        weeks = pd.date_range((end_m - pd.Timedelta(weeks=26)).to_period("W").start_time, end_m, freq="W-MON")
        wk = (ci.assign(t=ci["thoi_gian"].dt.to_period("W").dt.start_time).groupby(["t", "hinh_thuc"]).size()
              .unstack(fill_value=0).reindex(weeks, fill_value=0))
        series = {k: (wk[k].astype(int).tolist() if k in wk else [0] * len(weeks)) for k in ["Tự do", "Lớp nhóm", "PT"]}
        gt = data["goi_the"][data["goi_the"]["ma_hv"] == ma].sort_values("ngay_bat_dau", ascending=False)
        pt = data["goi_pt"][data["goi_pt"]["ma_hv"] == ma].sort_values("ngay_mua", ascending=False)
        dg = data["danh_gia"][data["danh_gia"]["ma_hv"] == ma].sort_values("ngay", ascending=False)
        lh = contacts()
        lh = lh[lh["ma_hv"] == ma].sort_values("thoi_gian", ascending=False)
        xd = x.to_dict()
        xd["ma_hv"] = ma
        return dict(members=lst, x=x, ma=ma, weeks=[w.strftime("%d/%m") for w in weeks], series=series,
                    gt=gt, pt=pt, dg=dg, lh=lh, bd=[int(x.d_tan_suat), int(x.d_hop_dong), int(x.d_phan_hoi), int(x.d_pt_nhom)],
                    msg=churn.message_for(xd, f"Aura {x.chi_nhanh}"))
    return page("member.html", "member", m=build, results=CONTACT_RESULTS, channels=CONTACT_CHANNELS)


@app.route("/ai")
def ai_page():
    def build(st, S, D, branch):
        b = st["bundle"]
        hidden = S[S["ai_canh_bao"] == "Rủi ro ẩn"].sort_values("p_ai", ascending=False)
        pts = {k: records(S[S["muc_rui_ro"] == k], ["churn_score", "p_ai", "ho_ten", "ma_hv"]) for k in RISK_ORDER}
        imp = b["importance"].head(10) if b and b.get("importance") is not None else pd.Series(dtype=float)
        return dict(b=b, m=b["metrics"] if b else {}, hidden=hidden, pts=pts,
                    imp_labels=list(imp.index), imp_values=[round(float(v), 4) for v in imp.values])
    return page("ai.html", "ai", a=build)


@app.route("/clv")
def clv_page():
    def build(st, S, D, branch):
        bins = np.arange(0, max(S["clv"].max() / 1e6 + 2, 12), 1.0) if len(S) else np.arange(0, 12)
        hist = {t: np.histogram(S.loc[S["hang_clv"] == t, "clv"] / 1e6, bins=bins)[0].tolist() for t in CLV_ORDER}
        act = S[S["trang_thai"] == "Còn hạn"]
        plans = act["loai_goi"].value_counts()
        order = [p for p in MEMBERSHIP_PLANS if p in plans.index] + [p for p in plans.index if p not in MEMBERSHIP_PLANS]
        tiers = S.groupby("hang_clv").agg(so=("ma_hv", "size"), clv=("clv", "mean"), rui_ro=("churn_score", "mean"),
                                          can=("churn_score", lambda v: int((v >= load_rules()["nguong_high"]).sum())))
        return dict(bins=[f"{int(b)}" for b in bins[:-1]], hist=hist, plan_labels=order,
                    plan_values=[int(plans[p]) for p in order], tiers=tiers.reindex(CLV_ORDER).fillna(0),
                    rev=churn.recognized_revenue(D),
                    matrix=pd.crosstab(S["hang_clv"], S["muc_rui_ro"]).reindex(index=CLV_ORDER, columns=RISK_ORDER, fill_value=0))
    return page("clv.html", "clv", c=build)


@app.route("/du-phong")
def reserve_page():
    import monte_carlo as mc

    def build(st, S, D, branch):
        eq = mc.load_equipment(None if branch == ALL else branch)
        return dict(eq=records(eq), rev=churn.recognized_revenue(D)["tong"] or 300e6)
    return page("reserve.html", "reserve", r=build)


@app.route("/cap-nhat")
def data_page():
    return page("data.html", "data", summary=lambda st, S, D, b: data_summary(st),
                tables=etl.SCHEMA, desc=etl.DESCRIPTIONS, plans=MEMBERSHIP_PLANS, pts=PT_PACKAGES)


@app.route("/quy-tac")
def rules_page():
    groups = [
        ("Tần suất tập luyện", "45%", "bi-activity", ["khong_tap_ngay", "diem_khong_tap", "giam_manh_pct", "diem_giam_manh", "giam_vua_pct", "diem_giam_vua"]),
        ("Thời hạn hợp đồng", "30%", "bi-calendar2-week", ["hd_rat_gap_ngay", "diem_hd_rat_gap", "hd_gap_ngay", "diem_hd_gap", "hd_vang_ngay", "diem_hd_vang"]),
        ("Phản hồi dịch vụ", "15%", "bi-chat-square-text", ["danh_gia_ngay", "diem_sao_thap", "diem_sao_cao", "diem_khieu_nai"]),
        ("PT & tập nhóm", "10%", "bi-people", ["pt_ngung_ngay", "diem_pt_ngung", "diem_tap_nhom", "nhom_toi_thieu_buoi"]),
        ("Phân loại & CLV", "", "bi-diagram-3", ["nguong_critical", "nguong_high", "nguong_medium", "clv_vip", "clv_medium", "bien_loi_nhuan", "an_han_ngay"]),
    ]
    return page("rules.html", "rules", groups=groups, labels=RULE_LABELS, defaults=DEFAULT_RULES,
                bt=lambda st, S, D, b: backtest(st["data"], load_rules()))


def data_summary(st):
    if not st:
        return []
    d = st["data"]
    out = []
    for b in st["branches"]:
        row = {"cn": b, "hv": int((d["hoi_vien"]["chi_nhanh"] == b).sum())}
        for t in ["goi_the", "checkin", "goi_pt", "danh_gia", "thiet_bi"]:
            row[t] = int((d[t]["chi_nhanh"] == b).sum()) if "chi_nhanh" in d[t] else 0
        ci = d["checkin"][d["checkin"]["chi_nhanh"] == b]["thoi_gian"]
        row["tu"] = f_ddmm(ci.min()) if len(ci) else "–"
        row["den"] = f_ddmm(ci.max()) if len(ci) else "–"
        row["active"] = int(((st["scores"]["chi_nhanh"] == b) & (st["scores"]["trang_thai"] == "Còn hạn")).sum())
        out.append(row)
    return out


def backtest(data, rules):
    end = churn.data_end(data)
    asof = end - pd.Timedelta(days=90 + rules["an_han_ngay"])
    s = churn.score(asof, data, rules, explain=False).set_index("ma_hv")
    y = churn.churn_label(asof, data["goi_the"], end, 90, rules["an_han_ngay"])
    m = s.join(y, how="inner").dropna(subset=["da_bo"])
    t = m.groupby("muc_rui_ro")["da_bo"].agg(["size", "mean"]).reindex(RISK_ORDER)
    return {"asof": f_ddmm(asof), "labels": RISK_ORDER, "n": t["size"].fillna(0).astype(int).tolist(),
            "rate": [None if pd.isna(v) else round(float(v), 4) for v in t["mean"]]}


# ====================================================================== API
@app.post("/api/contact")
def api_contact():
    j = request.get_json(force=True)
    if not j.get("ma_hv") or j.get("ket_qua") not in CONTACT_RESULTS:
        abort(400)
    now = datetime.now()
    with sqlite3.connect(DB) as con:
        etl.ensure_contact_table(con)
        con.execute("INSERT INTO lien_he (ma_hv, thoi_gian, nhan_vien, ket_qua, ghi_chu, kenh) VALUES (?,?,?,?,?,?)",
                    (j["ma_hv"], now.isoformat(timespec="minutes"), (j.get("nhan_vien") or "Lễ tân")[:60],
                     j["ket_qua"], (j.get("ghi_chu") or "")[:500], j.get("kenh") or ""))
    return jsonify(ok=True, t=now.strftime("%d/%m %H:%M"), ts=now.isoformat(), kq=j["ket_qua"])


@app.get("/api/contacts/<ma>")
def api_contacts(ma):
    lh = contacts()
    lh = lh[lh["ma_hv"] == ma].sort_values("thoi_gian", ascending=False)
    return jsonify([dict(t=r.thoi_gian.strftime("%d/%m/%Y %H:%M"), nv=r.nhan_vien, kq=r.ket_qua, note=r.ghi_chu or "",
                         kenh=r.kenh or "") for r in lh.itertuples()])


@app.get("/api/search")
def api_search():
    st = STORE.get()
    q = (request.args.get("q") or "").strip().lower()
    if not st or len(q) < 2:
        return jsonify([])
    s, _ = scoped(st, current_branch(st))
    key = (s["ma_hv"] + " " + s["ho_ten"] + " " + s["so_dien_thoai"]).str.lower()
    hit = s[key.str.contains(q, regex=False)].head(8)
    return jsonify(records(hit, ["ma_hv", "ho_ten", "so_dien_thoai", "muc_rui_ro", "chi_nhanh"]))


@app.post("/api/upload/check")
def api_upload_check():
    branch = (request.form.get("branch") or "").strip()
    append = request.form.get("mode", "append") == "append"
    if not branch:
        return jsonify(ok=False, report=[["error", "Chưa chọn chi nhánh"]])
    dfs, files = {}, []
    for f in request.files.getlist("files"):
        name = f.filename or "file"
        raw = io.BytesIO(f.read())
        try:
            if name.lower().endswith((".xlsx", ".xls")):
                book = etl.read_workbook(raw)
                if len(book) > 1 or (book and etl.detect_kind(name) is None):
                    dfs.update(book)
                    files.append({"name": name, "sheets": {k: len(v) for k, v in book.items()}})
                    continue
                raw.seek(0)
            df = etl.read_any(raw, name)
            kind = request.form.get(f"kind::{name}") or etl.detect_kind(name, df)
            if kind not in etl.TABLES:
                files.append({"name": name, "error": "Không nhận ra loại dữ liệu (đặt tên file chứa hoi_vien, goi_the, checkin...)"})
                continue
            dfs[kind] = df
            files.append({"name": name, "sheets": {kind: len(df)}})
        except Exception as e:  # noqa: BLE001
            files.append({"name": name, "error": f"Không đọc được file: {e}"})
    if not dfs:
        return jsonify(ok=False, files=files, report=[["error", "Không có dữ liệu hợp lệ trong file đã chọn"]])
    st = STORE.get()
    existing = set(st["data"]["hoi_vien"].query("chi_nhanh == @branch")["ma_hv"]) if st else set()
    clean, rep = etl.clean(dfs, branch, existing, append=append)
    token = uuid.uuid4().hex
    for k in [k for k, v in PENDING.items() if time.time() - v["t"] > 1800]:
        PENDING.pop(k, None)
    PENDING[token] = dict(clean=clean, branch=branch, append=append, t=time.time())
    preview = {}
    for t, df in clean.items():
        cols = [c for c in df.columns if c != "chi_nhanh"][:7]
        d = df[cols].head(5).copy()
        for c in d.columns:
            if pd.api.types.is_datetime64_any_dtype(d[c]):
                d[c] = d[c].dt.strftime("%d/%m/%Y %H:%M").str.replace(" 00:00", "")
        new_range = None
        dc = {"goi_the": "ngay_bat_dau", "checkin": "thoi_gian", "danh_gia": "ngay", "goi_pt": "ngay_mua", "hoi_vien": "ngay_tham_gia"}.get(t)
        if dc and dc in df and len(df):
            new_range = [f_ddmm(df[dc].min()), f_ddmm(df[dc].max())]
        preview[t] = {"cols": cols, "rows": d.astype(str).replace("nan", "").values.tolist(), "n": len(df), "range": new_range}
    errors = [m for lvl, m in rep if lvl == "error"]
    return jsonify(ok=not errors, token=token, files=files, report=rep, preview=preview)


@app.post("/api/upload/commit")
def api_upload_commit():
    token = (request.get_json(force=True) or {}).get("token")
    p = PENDING.pop(token, None)
    if not p:
        return jsonify(ok=False, error="Phiên kiểm tra đã hết hạn, hãy chọn lại file."), 400
    t0 = time.time()
    n = {k: len(v) for k, v in p["clean"].items()}
    backup.snapshot(f"{'Thêm dữ liệu' if p['append'] else 'Thay toàn bộ dữ liệu'} chi nhánh {p['branch']} "
                    f"({', '.join(f'{k} {v:,}'.replace(',', '.') for k, v in n.items())})")
    etl.write(p["clean"], append=p["append"])
    st = STORE.get(force=True)
    b = p["branch"]
    info = next((r for r in data_summary(st) if r["cn"] == b), None)
    return jsonify(ok=True, seconds=round(time.time() - t0, 1), branch=b, info=info, summary=data_summary(st),
                   data_date=f_ddmm(st["end"] - pd.Timedelta(days=1)),
                   ai=(st["bundle"]["trained_at"] if st["bundle"] else None))


@app.get("/api/summary")
def api_summary():
    st = STORE.get()
    return jsonify(summary=data_summary(st), data_date=f_ddmm(st["end"] - pd.Timedelta(days=1)) if st else None)


@app.post("/api/reload-raw")
def api_reload_raw():
    backup.snapshot("Nạp lại dữ liệu từ thư mục raw/")
    ok = etl.load_all(verbose=False)
    STORE.get(force=True)
    return jsonify(ok=ok)


@app.post("/api/sample")
def api_sample():
    import generate_data
    backup.snapshot("Tạo dữ liệu mẫu 3 chi nhánh")
    generate_data.main(300, 0)
    etl.load_all(verbose=False)
    STORE.get(force=True)
    return jsonify(ok=True)


@app.get("/tai/mau.xlsx")
def dl_template():
    xb = io.BytesIO()
    with pd.ExcelWriter(xb, engine="openpyxl") as w:
        for k, v in etl.template_csvs().items():
            pd.read_csv(io.StringIO(v)).to_excel(w, sheet_name=k, index=False)
    xb.seek(0)
    return send_file(xb, as_attachment=True, download_name="aura_mau_chi_nhanh.xlsx")


@app.get("/tai/mau-csv.zip")
def dl_template_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in etl.template_csvs().items():
            z.writestr(f"{k}.csv", "﻿" + v)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="aura_file_mau_csv.zip")


@app.get("/tai/chi-nhanh/<b>.xlsx")
def dl_branch(b):
    if not DB.exists():
        abort(404)
    path = DB.parent / "raw" / f".tmp_{uuid.uuid4().hex}.xlsx"
    with sqlite3.connect(DB) as con:
        etl.export_branch_excel(con, b, path)
    data = path.read_bytes()
    path.unlink(missing_ok=True)
    return send_file(io.BytesIO(data), as_attachment=True, download_name=f"{b}.xlsx")


@app.post("/tai/danh-sach.xlsx")
def dl_list():
    ids = json.loads(request.form.get("ids", "[]"))
    st = STORE.get()
    s = st["scores"].set_index("ma_hv").loc[[i for i in ids if i in set(st["scores"]["ma_hv"])]].reset_index()
    out = pd.DataFrame({"Priority": s["priority"], "Mã": s["ma_hv"], "Họ tên": s["ho_ten"], "SĐT": s["so_dien_thoai"],
                        "Chi nhánh": s["chi_nhanh"], "Churn Score": s["churn_score"], "Mức rủi ro": s["muc_rui_ro"],
                        "AI dự báo (%)": (s["p_ai"] * 100).round(), "CLV (đ)": s["clv"], "Hạng CLV": s["hang_clv"],
                        "Kịch bản": s["nhom_can_thiep"], "Phụ trách": s["phu_trach"], "Lý do": s["ly_do"],
                        "Thẻ còn (ngày)": s["con_lai"]})
    xb = io.BytesIO()
    with pd.ExcelWriter(xb, engine="openpyxl") as w:
        out.to_excel(w, index=False, sheet_name="Can thiep")
        ws = w.sheets["Can thiep"]
        for col, width in zip("ABCDEFGHIJKLMN", [9, 9, 22, 13, 11, 11, 18, 13, 13, 10, 22, 18, 60, 13]):
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A2"
    xb.seek(0)
    return send_file(xb, as_attachment=True, download_name=f"danh_sach_can_thiep_{datetime.now():%Y%m%d}.xlsx")


@app.post("/api/reserve")
def api_reserve():
    import monte_carlo as mc
    j = request.get_json(force=True)
    eq = pd.DataFrame(j.get("eq") or [])
    if eq.empty:
        return jsonify(ok=False, error="Chưa có thiết bị")
    for c in ["so_luong", "nam_su_dung", "p_hong_thang", "chi_phi_tb", "chi_phi_max"]:
        eq[c] = pd.to_numeric(eq.get(c), errors="coerce")
    months, rev = int(j.get("months", 12)), float(j.get("rev", 0)) * 1e6
    rate, start, target = float(j.get("rate", 0.06)), float(j.get("start", 0)) * 1e6, float(j.get("target", 0.05))
    costs, by_item = mc.simulate(eq, months, 10_000)
    sm = mc.summary(costs, rev, rate, start, target)
    path = mc.fund_path(costs, rev, rate, start) / 1e6
    hist, edges = np.histogram(costs.ravel() / 1e6, bins=40)
    return jsonify(ok=True, thang={k: float(v) for k, v in sm["thang"].items()}, ky={k: float(v) for k, v in sm["ky"].items()},
                   p_thieu_quy=sm["p_thieu_quy"], ty_le_can_thiet=sm["ty_le_can_thiet"], quy_ban_dau_can=sm["quy_ban_dau_can"],
                   vuot={k: v for k, v in sm["xac_suat_thang_vuot"].items()}, rev=rev,
                   hist=hist.tolist(), edges=[round(float(e), 1) for e in edges[:-1]],
                   months=list(range(1, months + 1)), median=np.median(path, 0).round(2).tolist(),
                   q05=np.quantile(path, 0.05, 0).round(2).tolist(), q01=np.quantile(path, 0.01, 0).round(2).tolist(),
                   items=list(by_item.index), item_values=(by_item.values / 1e6).round(2).tolist())


@app.get("/api/clv")
def api_clv():
    st = STORE.get()
    margin = float(request.args.get("margin", load_rules()["bien_loi_nhuan"]))
    branch = current_branch(st)
    rows = []
    for b in ([branch] if branch != ALL else st["branches"]):
        p = churn.predictive_clv(churn.filter_branch(st["data"], b), load_rules(), margin)
        rows.append(dict(cn=b, active=p["hoi_vien_hoat_dong"], rev=p["doanh_thu_thang"], arpu=p["arpu"],
                         churn=p["churn_thang"], life=p["tuoi_tho"], clv=p["clv_du_bao"]))
    tot = churn.predictive_clv(churn.filter_branch(st["data"], None if branch == ALL else branch), load_rules(), margin)
    return jsonify(rows=rows, total=dict(rev=tot["doanh_thu_thang"], arpu=tot["arpu"], churn=tot["churn_thang"],
                                         life=tot["tuoi_tho"], clv=tot["clv_du_bao"]))


def _parse_rules(j):
    new = dict(load_rules())
    for k, v in (j or {}).items():
        if k in DEFAULT_RULES:
            try:
                new[k] = type(DEFAULT_RULES[k])(float(v))
            except (TypeError, ValueError):
                pass
    return new


@app.post("/api/rules/test")
def api_rules_test():
    st = STORE.get()
    return jsonify(backtest(st["data"], _parse_rules(request.get_json(force=True))))


@app.post("/api/rules/save")
def api_rules_save():
    backup.snapshot("Lưu quy tắc Churn Score mới")
    save_rules(_parse_rules(request.get_json(force=True)))
    STORE.get(force=True)
    return jsonify(ok=True)


@app.post("/api/rules/reset")
def api_rules_reset():
    backup.snapshot("Khôi phục quy tắc mặc định")
    reset_rules()
    STORE.get(force=True)
    return jsonify(ok=True)


@app.get("/api/history")
def api_history():
    return jsonify(backup.list_snapshots())


@app.post("/api/undo")
def api_undo():
    sid = (request.get_json(silent=True) or {}).get("id")
    with STORE.lock:
        try:
            meta = backup.restore(sid)
        except ValueError as e:
            return jsonify(ok=False, error=str(e)), 400
        STORE.key = None
        st = STORE.get(force=True)
    return jsonify(ok=True, undone=meta["label"], time=meta["time"], has_data=st is not None,
                   summary=data_summary(st) if st else [],
                   data_date=f_ddmm(st["end"] - pd.Timedelta(days=1)) if st else None, history=backup.list_snapshots())


@app.post("/api/reset")
def api_reset():
    j = request.get_json(silent=True) or {}
    if (j.get("confirm") or "").strip().upper() not in ("XÓA", "XOA"):
        return jsonify(ok=False, error="Gõ chữ XÓA để xác nhận."), 400
    with STORE.lock:
        sid = backup.snapshot("Xóa toàn bộ dữ liệu" + (" (kèm lịch sử liên hệ)" if j.get("contacts") else ""))
        try:
            backup.reset_all(delete_contacts=bool(j.get("contacts")))
        except ValueError as e:
            import shutil
            shutil.rmtree(backup.BK / sid, ignore_errors=True)     # chưa xóa gì nên bỏ bản sao lưu vừa tạo
            return jsonify(ok=False, error=str(e)), 400
        STORE.key, STORE.state = None, None
    return jsonify(ok=True, history=backup.list_snapshots())


@app.post("/api/retrain")
def api_retrain():
    ai_model.train()
    st = STORE.get(force=True)
    return jsonify(ok=True, trained_at=st["bundle"]["trained_at"] if st["bundle"] else None)


@app.errorhandler(500)
def err500(e):
    if request.path.startswith("/api/"):
        return jsonify(ok=False, error="Lỗi máy chủ: " + str(getattr(e, "original_exception", e))), 500
    return f"<h3>Có lỗi xảy ra</h3><pre>{getattr(e, 'original_exception', e)}</pre><a href='/'>Về trang chủ</a>", 500


def run(port=8501, open_browser=True):
    import webbrowser
    print("--> Đang chuẩn bị dữ liệu và AI...")
    STORE.get()
    url = f"http://localhost:{port}"
    print(f"--> Web đã sẵn sàng: {url}   (KHÔNG đóng cửa sổ này trong lúc dùng)")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    run()
