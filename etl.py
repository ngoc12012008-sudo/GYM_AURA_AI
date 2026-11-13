"""Đọc, kiểm tra, làm sạch dữ liệu và lưu vào gym.db (SQLite).

- Mỗi chi nhánh một file Excel trong raw/ (vd raw/Quan_1.xlsx, mỗi sheet một loại dữ liệu). Chạy: python etl.py
  (vẫn đọc được kiểu cũ: thư mục raw/Quan_1/ chứa các file CSV)
- Hoặc nhập trực tiếp trên giao diện (trang "Nhập dữ liệu"): chỉ thay dữ liệu của chi nhánh đó.
- Bảng lịch sử liên hệ (lien_he) luôn được giữ nguyên.
"""
import io
import os
import sqlite3
import unicodedata

import pandas as pd

from config import BRANCHES, DB, GROUP_PT, MEMBERSHIP_PLANS, PT_PACKAGES, RAW, branch_folder

# Cột bắt buộc / tùy chọn của từng file
SCHEMA = {
    "hoi_vien": {"req": ["ma_hv", "ho_ten", "so_dien_thoai", "ngay_tham_gia"],
                 "opt": ["chi_nhanh", "gioi_tinh", "ngay_sinh", "tap_cung_ban", "co_pt"]},
    "goi_the": {"req": ["ma_hv", "loai_goi", "gia", "ngay_bat_dau", "ngay_het_han"], "opt": []},
    "checkin": {"req": ["ma_hv", "thoi_gian"], "opt": ["hinh_thuc"]},
    "goi_pt": {"req": ["ma_hv", "loai_pt", "gia", "ngay_mua"], "opt": ["so_buoi"]},
    "danh_gia": {"req": ["ma_hv", "ngay", "so_sao"], "opt": ["khieu_nai", "da_xu_ly", "noi_dung"]},
    "thiet_bi": {"req": ["ten", "so_luong", "p_hong_thang", "chi_phi_tb", "chi_phi_max"],
                 "opt": ["chi_nhanh", "nam_su_dung"]},
}
TABLES = list(SCHEMA)
DESCRIPTIONS = {
    "hoi_vien": "Danh sách hội viên (bắt buộc khi nhập chi nhánh mới)",
    "goi_the": "Gói thẻ membership – mỗi lần mua/gia hạn là 1 dòng",
    "checkin": "Lượt quẹt thẻ; cột hinh_thuc: Tự do / Lớp nhóm / PT",
    "goi_pt": "Gói huấn luyện viên cá nhân đã mua (tùy chọn)",
    "danh_gia": "Đánh giá sao và khiếu nại (tùy chọn)",
    "thiet_bi": "Thiết bị để mô phỏng chi phí sửa chữa (tùy chọn)",
}
DATE_COLS = {"hoi_vien": ["ngay_tham_gia", "ngay_sinh"], "goi_the": ["ngay_bat_dau", "ngay_het_han"],
             "checkin": ["thoi_gian"], "goi_pt": ["ngay_mua"], "danh_gia": ["ngay"]}

# Tên cột hay gặp khi xuất từ phần mềm khác -> tên chuẩn
ALIASES = {
    "ma_hoi_vien": "ma_hv", "ma_khach_hang": "ma_hv", "ma_kh": "ma_hv", "member_id": "ma_hv", "id": "ma_hv",
    "ho_va_ten": "ho_ten", "ten_khach_hang": "ho_ten", "name": "ho_ten",
    "sdt": "so_dien_thoai", "dien_thoai": "so_dien_thoai", "phone": "so_dien_thoai",
    "ngay_dang_ky": "ngay_tham_gia", "join_date": "ngay_tham_gia",
    "goi": "loai_goi", "ten_goi": "loai_goi", "gia_ban": "gia", "so_tien": "gia",
    "ngay_bd": "ngay_bat_dau", "ngay_kt": "ngay_het_han", "ngay_ket_thuc": "ngay_het_han",
    "thoi_gian_checkin": "thoi_gian", "checkin_time": "thoi_gian", "ngay_gio": "thoi_gian",
    "goi_pt": "loai_pt", "ten_goi_pt": "loai_pt", "sao": "so_sao", "diem_danh_gia": "so_sao",
    "ngay_danh_gia": "ngay", "chinhanh": "chi_nhanh", "co_so": "chi_nhanh",
}


def norm_col(c):
    s = str(c).replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower().strip()
    s = "".join(ch if ch.isalnum() else "_" for ch in s)
    while "__" in s:
        s = s.replace("__", "_")
    s = s.strip("_")
    return ALIASES.get(s, s)


def read_any(file, name=None):
    """Đọc CSV/Excel từ đường dẫn hoặc file tải lên. Tự nhận dạng mã hóa và dấu phân cách."""
    name = (name or getattr(file, "name", str(file))).lower()
    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file, dtype=str)
    else:
        raw = file.read() if hasattr(file, "read") else open(file, "rb").read()
        for enc in ("utf-8-sig", "cp1258", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sep = ";" if text.split("\n", 1)[0].count(";") > text.split("\n", 1)[0].count(",") else ","
        df = pd.read_csv(io.StringIO(text), dtype=str, sep=sep)
    df.columns = [norm_col(c) for c in df.columns]
    return df


def read_workbook(file, name=None):
    """Đọc file Excel nhiều sheet (mỗi sheet một loại dữ liệu). Trả về {loại: DataFrame}."""
    sheets = pd.read_excel(file, sheet_name=None, dtype=str)
    out = {}
    for sh, df in sheets.items():
        df.columns = [norm_col(c) for c in df.columns]
        kind = detect_kind(sh, df)
        if kind and not df.empty:
            out[kind] = df
    return out


def detect_kind(filename, df=None):
    n = norm_col(filename.rsplit(".", 1)[0])
    for t in TABLES:
        if t in n:
            return t
    keys = {"thiet_bi": ["thiet", "equip"], "danh_gia": ["danh_gia", "review", "feedback"],
            "goi_pt": ["pt"], "checkin": ["check", "quet"], "goi_the": ["the", "membership", "hop_dong"],
            "hoi_vien": ["hoi_vien", "member", "khach"]}
    for t, ks in keys.items():
        if any(k in n for k in ks):
            return t
    if df is not None:   # đoán theo cột
        cols = set(df.columns)
        for t in ["checkin", "goi_the", "goi_pt", "danh_gia", "thiet_bi", "hoi_vien"]:
            if set(SCHEMA[t]["req"]) <= cols:
                return t
    return None


def _to_date(s):
    s = s.astype(str).str.strip()
    out = pd.to_datetime(s, errors="coerce", format="ISO8601")
    bad = out.isna() & s.ne("") & s.ne("nan")
    if bad.any():   # thử kiểu Việt Nam dd/mm/yyyy
        out.loc[bad] = pd.to_datetime(s[bad], errors="coerce", dayfirst=True)
    return out


def _to_num(s, money=False):
    s = s.astype(str).str.replace(r"[^\d\-.,]", "", regex=True)
    if money:   # 1.500.000 hoặc 1,500,000 -> 1500000
        s = s.str.replace(r"[.,](?=\d{3}(\D|$))", "", regex=True)
    return pd.to_numeric(s.str.replace(",", "."), errors="coerce")


def _to_flag(s):
    v = s.astype(str).str.strip().str.lower()
    return v.isin(["1", "1.0", "true", "co", "có", "x", "yes", "y"]).astype(int)


KEYS = {"hoi_vien": ["ma_hv"], "goi_the": ["ma_hv", "ngay_bat_dau", "loai_goi"], "checkin": ["ma_hv", "thoi_gian", "hinh_thuc"],
        "goi_pt": ["ma_hv", "ngay_mua", "loai_pt"], "danh_gia": ["ma_hv", "ngay", "so_sao"], "thiet_bi": ["ten", "chi_nhanh"]}


def clean(dfs, branch=None, existing_members=None, append=False):
    """Kiểm tra và làm sạch. Trả về (dfs_sạch, báo_cáo[list (mức, nội dung)])."""
    rep, out = [], {}
    for t, df in dfs.items():
        if df is None:
            continue
        df = df.copy()
        df.columns = [norm_col(c) for c in df.columns]
        miss = [c for c in SCHEMA[t]["req"] if c not in df.columns]
        if miss:
            rep.append(("error", f"{t}: thiếu cột bắt buộc {', '.join(miss)}"))
            continue
        keep = SCHEMA[t]["req"] + [c for c in SCHEMA[t]["opt"] if c in df.columns]
        df = df[keep]
        n0 = len(df)
        if "ma_hv" in df:
            df["ma_hv"] = df["ma_hv"].astype(str).str.strip()
            df = df[df["ma_hv"].ne("") & df["ma_hv"].ne("nan")]
        for c in DATE_COLS.get(t, []):
            if c in df:
                df[c] = _to_date(df[c])
        if t == "hoi_vien":
            df["so_dien_thoai"] = df["so_dien_thoai"].astype(str).str.replace(r"\D", "", regex=True)
            df.loc[df["so_dien_thoai"].str.len().eq(9), "so_dien_thoai"] = "0" + df["so_dien_thoai"]
            df = df.dropna(subset=["ngay_tham_gia"])
            dup = df["ma_hv"].duplicated().sum()
            if dup:
                rep.append(("warning", f"hoi_vien: bỏ {dup} mã hội viên trùng"))
            df = df.drop_duplicates("ma_hv", keep="last")
            n0 -= dup
            for c in ["tap_cung_ban", "co_pt"]:
                if c in df:
                    df[c] = _to_flag(df[c])
            if "tap_cung_ban" not in df:
                df["tap_cung_ban"] = 0
            if branch:
                df["chi_nhanh"] = branch
            elif "chi_nhanh" not in df:
                rep.append(("error", "hoi_vien: chưa chọn chi nhánh và file không có cột chi_nhanh"))
                continue
            df["chi_nhanh"] = df["chi_nhanh"].astype(str).str.strip()
        elif t == "goi_the":
            df["gia"] = _to_num(df["gia"], money=True)
            df["loai_goi"] = df["loai_goi"].astype(str).str.strip()
            df = df.dropna(subset=["ngay_bat_dau", "ngay_het_han", "gia"])
            swap = df["ngay_het_han"] < df["ngay_bat_dau"]
            if swap.any():
                rep.append(("warning", f"goi_the: bỏ {swap.sum()} dòng có ngày hết hạn trước ngày bắt đầu"))
                df = df[~swap]
            unknown = sorted(set(df["loai_goi"]) - set(MEMBERSHIP_PLANS))
            if unknown:
                rep.append(("info", f"goi_the: gói ngoài bảng giá chuẩn (vẫn dùng bình thường): {', '.join(unknown[:5])}"))
            df = df.drop_duplicates(["ma_hv", "ngay_bat_dau", "loai_goi"])
        elif t == "checkin":
            df = df.dropna(subset=["thoi_gian"])
            if "hinh_thuc" not in df:
                df["hinh_thuc"] = "Tự do"
            h = df["hinh_thuc"].fillna("").astype(str).str.strip().str.lower()
            df["hinh_thuc"] = "Tự do"
            df.loc[h.str.contains("pt|hlv|personal"), "hinh_thuc"] = "PT"
            df.loc[h.str.contains("nhom|nhóm|group|lop|lớp|yoga|class"), "hinh_thuc"] = "Lớp nhóm"
            df = df.sort_values(["ma_hv", "thoi_gian"])
            # bỏ quẹt trùng: cùng người, cùng hình thức, cách nhau dưới 2 giờ
            gap = df.groupby(["ma_hv", "hinh_thuc"])["thoi_gian"].diff()
            dup = ~(gap.isna() | (gap > pd.Timedelta(hours=2)))
            if dup.any():
                rep.append(("info", f"checkin: bỏ {dup.sum()} lượt quẹt trùng (cách nhau < 2 giờ)"))
            df = df[~dup]
        elif t == "goi_pt":
            df["gia"] = _to_num(df["gia"], money=True)
            if "so_buoi" in df:
                df["so_buoi"] = _to_num(df["so_buoi"])
            else:
                df["so_buoi"] = float("nan")
            known = df["loai_pt"].map(lambda x: PT_PACKAGES.get(str(x).strip(), (None, None))[0])
            df["so_buoi"] = df["so_buoi"].fillna(known).fillna(10).astype(int)
            df = df.dropna(subset=["ngay_mua", "gia"])
        elif t == "danh_gia":
            df["so_sao"] = _to_num(df["so_sao"]).clip(1, 5)
            df = df.dropna(subset=["ngay", "so_sao"])
            for c in ["khieu_nai", "da_xu_ly"]:
                df[c] = _to_flag(df[c]) if c in df else (0 if c == "khieu_nai" else 1)
            if "noi_dung" not in df:
                df["noi_dung"] = ""
        elif t == "thiet_bi":
            for c in ["so_luong", "p_hong_thang", "chi_phi_tb", "chi_phi_max", "nam_su_dung"]:
                if c in df:
                    df[c] = _to_num(df[c], money=c.startswith("chi_phi"))
            if "nam_su_dung" not in df:
                df["nam_su_dung"] = 0
            df = df.dropna(subset=["so_luong", "p_hong_thang", "chi_phi_tb", "chi_phi_max"])
            if branch:
                df["chi_nhanh"] = branch
            elif "chi_nhanh" not in df:
                rep.append(("error", "thiet_bi: chưa chọn chi nhánh và file không có cột chi_nhanh"))
                continue
        dropped = n0 - len(df)
        if dropped and t not in ("checkin",):
            rep.append(("warning", f"{t}: bỏ {dropped} dòng lỗi/thiếu dữ liệu"))
        out[t] = df.reset_index(drop=True)

    # Đối chiếu mã hội viên
    members = set(out["hoi_vien"]["ma_hv"]) if "hoi_vien" in out else set()
    if append or "hoi_vien" not in out:
        members |= set(existing_members or [])
    if members:
        for t in ["goi_the", "checkin", "goi_pt", "danh_gia"]:
            if t in out:
                bad = ~out[t]["ma_hv"].isin(members)
                if bad.any():
                    rep.append(("warning", f"{t}: bỏ {bad.sum()} dòng có mã hội viên không có trong danh sách"))
                    out[t] = out[t][~bad].reset_index(drop=True)
    elif any(t in out for t in ["goi_the", "checkin", "goi_pt", "danh_gia"]):
        rep.append(("error", "Chưa có danh sách hội viên (hoi_vien) của chi nhánh này"))
    if "hoi_vien" in out and "goi_the" not in out and not existing_members:
        rep.append(("error", "Chi nhánh mới cần có cả file goi_the"))
    for t, df in out.items():
        rep.append(("ok", f"{t}: {len(df):,} dòng hợp lệ"))
    return out, rep


def _read_table(con, t):
    try:
        return pd.read_sql(f"SELECT * FROM {t}", con)
    except Exception:
        return None


def ensure_contact_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS lien_he (
        ma_hv TEXT, thoi_gian TEXT, nhan_vien TEXT, ket_qua TEXT, ghi_chu TEXT, kenh TEXT)""")
    cols = [r[1] for r in con.execute("PRAGMA table_info(lien_he)")]
    if "kenh" not in cols:
        con.execute("ALTER TABLE lien_he ADD COLUMN kenh TEXT")


def write(dfs, save_raw=True, append=False):
    """Ghi dữ liệu đã làm sạch.
    append=False: thay các bảng có trong dfs của chi nhánh đó.
    append=True : thêm dòng mới vào dữ liệu cũ (bỏ dòng trùng), không xóa gì."""
    saved = set()
    with sqlite3.connect(DB) as con:
        ensure_contact_table(con)
        hv_db = _read_table(con, "hoi_vien")
        if "hoi_vien" in dfs:
            branches = set(dfs["hoi_vien"]["chi_nhanh"])
            mapping = dfs["hoi_vien"].set_index("ma_hv")["chi_nhanh"]
            if append and hv_db is not None:
                mapping = pd.concat([hv_db.set_index("ma_hv")["chi_nhanh"], mapping])
                mapping = mapping[~mapping.index.duplicated(keep="last")]
        else:
            mapping = hv_db.set_index("ma_hv")["chi_nhanh"] if hv_db is not None else pd.Series(dtype=str)
            branches = None
        for t, df in dfs.items():
            df = df.copy()
            if t not in ("hoi_vien", "thiet_bi"):
                df["chi_nhanh"] = df["ma_hv"].map(mapping)
                df = df.dropna(subset=["chi_nhanh"])
            br = set(df["chi_nhanh"]) if branches is None or t == "thiet_bi" else branches
            old = _read_table(con, t)
            if old is not None and "chi_nhanh" in old.columns:
                if not append:
                    old = old[~old["chi_nhanh"].isin(br)]
                for c in DATE_COLS.get(t, []):
                    if c in old:
                        old[c] = pd.to_datetime(old[c], errors="coerce")
                df = pd.concat([old, df], ignore_index=True)
                if append:
                    k = [c for c in KEYS[t] if c in df.columns]
                    df = df.drop_duplicates(k, keep="last")
            df.to_sql(t, con, if_exists="replace", index=False)
            if save_raw:
                saved.update(df.loc[df["chi_nhanh"].isin(br), "chi_nhanh"])
        for b in saved:
            export_branch_excel(con, b)
    if saved:
        os.utime(DB)   # để run.py không nạp lại vô ích
        con.execute("CREATE INDEX IF NOT EXISTS ix_ci ON checkin(ma_hv)")


def export_branch_excel(con, branch, path=None):
    """Ghi toàn bộ dữ liệu 1 chi nhánh ra 1 file Excel, mỗi loại dữ liệu 1 sheet."""
    path = path or RAW / f"{branch_folder(branch)}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for t in TABLES:
            df = _read_table(con, t)
            if df is None or "chi_nhanh" not in df:
                continue
            df = df[df["chi_nhanh"] == branch]
            if t not in ("hoi_vien", "thiet_bi"):
                df = df.drop(columns="chi_nhanh")
            for c in DATE_COLS.get(t, []):
                if c in df:
                    d = pd.to_datetime(df[c], errors="coerce", format="mixed")
                    df[c] = d if t == "checkin" else d.dt.date
            df.to_excel(w, sheet_name=t, index=False)
            ws = w.sheets[t]
            for i, col in enumerate(df.columns):
                ws.column_dimensions[chr(65 + i)].width = max(12, min(40, len(col) + 4))
            ws.freeze_panes = "A2"
    return path


def import_folder(folder, branch=None):
    if folder.suffix.lower() in (".xlsx", ".xls"):
        return clean(read_workbook(folder), branch)
    dfs = {t: read_any(folder / f"{t}.csv") for t in TABLES if (folder / f"{t}.csv").exists()}
    return clean(dfs, branch)


def load_all(raw_dir=RAW, verbose=True):
    """Nạp lại toàn bộ chi nhánh từ thư mục raw/. Ưu tiên thư mục con; file phẳng chỉ dùng khi không có thư mục con."""
    folders = sorted(p for p in raw_dir.iterdir() if p.is_dir() and (p / "hoi_vien.csv").exists()) if raw_dir.exists() else []
    books = sorted(p for p in raw_dir.glob("*.xls*") if not p.name.startswith("~$")) if raw_dir.exists() else []
    folders = [f for f in folders if f.name not in {b.stem for b in books}] + books   # ưu tiên file Excel
    if not folders and (raw_dir / "hoi_vien.csv").exists():
        folders = [raw_dir]
    if not folders:
        raise SystemExit("Không tìm thấy dữ liệu trong raw/. Chạy generate_data.py hoặc nhập trên giao diện.")
    if DB.exists():   # dựng lại sạch nhưng giữ lịch sử liên hệ
        with sqlite3.connect(DB) as con:
            for t in TABLES:
                con.execute(f"DROP TABLE IF EXISTS {t}")
    ok = True
    for f in folders:
        branch = next((b for b, i in BRANCHES.items() if i["folder"] == f.stem), None)
        dfs, rep = import_folder(f, branch)
        errors = [m for lvl, m in rep if lvl == "error"]
        if verbose:
            print(f"[{f.name}]")
            for lvl, m in rep:
                print(f"   {'✗' if lvl == 'error' else '!' if lvl == 'warning' else '·'} {m}")
        if errors:
            ok = False
        if "hoi_vien" in dfs and "goi_the" in dfs:
            write(dfs, save_raw=False)
    if verbose:
        print(f"Đã lưu vào {DB}")
    return ok


def schema_ok():
    """DB có đúng cấu trúc mới không (để run.py biết có cần dựng lại)."""
    if not DB.exists():
        return False
    try:
        with sqlite3.connect(DB) as con:
            cols = [r[1] for r in con.execute("PRAGMA table_info(goi_the)")]
            n = con.execute("SELECT count(*) FROM hoi_vien").fetchone()[0]
        return "chi_nhanh" in cols and n > 0
    except Exception:
        return False


def template_csvs():
    """File mẫu (vài dòng) để người dùng điền dữ liệu thật."""
    return {
        "hoi_vien": "ma_hv,ho_ten,so_dien_thoai,gioi_tinh,ngay_sinh,ngay_tham_gia,tap_cung_ban\n"
                    "Q1-0001,Nguyễn Văn An,0901234567,Nam,1995-04-12,2026-01-15,0\n",
        "goi_the": "ma_hv,loai_goi,gia,ngay_bat_dau,ngay_het_han\n"
                   "Q1-0001,Classic 6 tháng,2400000,2026-01-15,2026-07-13\n"
                   "Q1-0001,Classic 12 tháng,3990000,2026-07-14,2027-07-08\n",
        "checkin": "ma_hv,thoi_gian,hinh_thuc\nQ1-0001,2026-11-01 18:30,Tự do\nQ1-0001,2026-11-03 19:00,Lớp nhóm\n",
        "goi_pt": "ma_hv,loai_pt,so_buoi,gia,ngay_mua\nQ1-0001,Starter PT,10,2500000,2026-10-01\n",
        "danh_gia": "ma_hv,ngay,so_sao,khieu_nai,da_xu_ly,noi_dung\nQ1-0001,2026-10-20,2,1,0,Máy chạy bộ hỏng\n",
        "thiet_bi": "ten,so_luong,nam_su_dung,p_hong_thang,chi_phi_tb,chi_phi_max\nMáy chạy bộ,12,2,0.05,4000000,25000000\n",
    }


if __name__ == "__main__":
    load_all()
