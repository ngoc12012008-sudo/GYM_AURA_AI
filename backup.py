"""Sao lưu tự động trước mỗi thao tác thay đổi dữ liệu, để có thể hoàn tác.

Mỗi bản sao lưu nằm trong backups/<thời_gian>/ gồm: gym.db, thư mục raw/, rules.json và meta.json (mô tả thao tác).
Khi khôi phục, lịch sử liên hệ (bảng lien_he) được GỘP giữa hiện tại và bản sao lưu, nên các cuộc gọi
đã ghi sau thời điểm sao lưu không bị mất.
"""
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime

import pandas as pd

from config import BASE, DB, RAW, RULES_FILE

BK = BASE / "backups"
KEEP = 10


def _copy_db(src_path, dst_path):
    """Sao chép CSDL bằng API backup của SQLite và ĐÓNG hẳn kết nối (Windows khóa file nếu còn mở)."""
    with closing(sqlite3.connect(src_path)) as src, closing(sqlite3.connect(dst_path)) as dst:
        src.backup(dst)


def _rmtree_raw():
    try:
        if RAW.exists():
            shutil.rmtree(RAW)
    except PermissionError as e:
        raise ValueError(f"Không xóa được thư mục raw/ – hãy đóng file {getattr(e, 'filename', '')} đang mở trong Excel rồi thử lại.") from e


def _counts():
    out = {}
    if not DB.exists():
        return out
    with closing(sqlite3.connect(DB)) as con:
        for t in ["hoi_vien", "goi_the", "checkin", "lien_he"]:
            try:
                out[t] = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            except sqlite3.Error:
                out[t] = 0
    return out


def snapshot(label):
    """Lưu trạng thái hiện tại TRƯỚC khi làm thao tác `label`. Trả về id bản sao lưu."""
    BK.mkdir(exist_ok=True)
    sid = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    d = BK / sid
    d.mkdir()
    if DB.exists():
        _copy_db(DB, d / "gym.db")               # sao chép an toàn kể cả khi web đang đọc
    if RAW.exists():
        shutil.copytree(RAW, d / "raw", ignore=shutil.ignore_patterns(".tmp_*", "~$*"))
    if RULES_FILE.exists():
        shutil.copy2(RULES_FILE, d / "rules.json")
    meta = {"id": sid, "label": label, "time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "counts": _counts()}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    for old in list_snapshots()[KEEP:]:
        shutil.rmtree(BK / old["id"], ignore_errors=True)
    return sid


def list_snapshots():
    if not BK.exists():
        return []
    out = []
    for d in BK.iterdir():
        m = d / "meta.json"
        if d.is_dir() and m.exists():
            try:
                out.append(json.loads(m.read_text(encoding="utf-8")))
            except Exception:
                pass
    return sorted(out, key=lambda x: x["id"], reverse=True)


def _contacts(path):
    try:
        with closing(sqlite3.connect(path)) as con:
            return pd.read_sql("SELECT * FROM lien_he", con)
    except Exception:
        return None


def restore(sid=None):
    """Khôi phục về trạng thái trước thao tác `sid` (mặc định: thao tác gần nhất).
    Bản sao lưu đó và các bản mới hơn bị xóa khỏi lịch sử. Trả về meta của bản đã khôi phục."""
    snaps = list_snapshots()
    if not snaps:
        raise ValueError("Không có thao tác nào để hoàn tác.")
    target = snaps[0] if sid is None else next((s for s in snaps if s["id"] == sid), None)
    if target is None:
        raise ValueError("Không tìm thấy bản sao lưu.")
    d = BK / target["id"]
    now_contacts = _contacts(DB) if DB.exists() else None

    # dữ liệu
    if (d / "gym.db").exists():
        _copy_db(d / "gym.db", DB)
    elif DB.exists():
        DB.unlink()
    _rmtree_raw()
    if (d / "raw").exists():
        shutil.copytree(d / "raw", RAW)
    else:
        RAW.mkdir(exist_ok=True)
    if (d / "rules.json").exists():
        shutil.copy2(d / "rules.json", RULES_FILE)
    elif RULES_FILE.exists():
        RULES_FILE.unlink()

    # gộp lịch sử liên hệ: không làm mất cuộc gọi đã ghi sau thời điểm sao lưu
    old_contacts = _contacts(DB)
    parts = [c for c in (old_contacts, now_contacts) if c is not None and len(c)]
    if parts:
        merged = pd.concat(parts, ignore_index=True).drop_duplicates()
        with closing(sqlite3.connect(DB)) as con:
            merged.to_sql("lien_he", con, if_exists="replace", index=False)
            con.commit()

    for s in snaps:
        if s["id"] >= target["id"]:
            shutil.rmtree(BK / s["id"], ignore_errors=True)
    return target


def reset_all(delete_contacts=False):
    """Xóa toàn bộ dữ liệu (đã sao lưu trước đó bằng snapshot)."""
    from etl import TABLES, ensure_contact_table
    _rmtree_raw()                                # làm trước: nếu file đang mở thì báo lỗi, chưa xóa gì
    if DB.exists():
        with closing(sqlite3.connect(DB)) as con:
            for t in TABLES:
                con.execute(f"DROP TABLE IF EXISTS {t}")
            if delete_contacts:
                con.execute("DROP TABLE IF EXISTS lien_he")
            ensure_contact_table(con)
            con.commit()
    RAW.mkdir(exist_ok=True)
    for f in (BASE / "models").glob("*.pkl"):
        f.unlink()
