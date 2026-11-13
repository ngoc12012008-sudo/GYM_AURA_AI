"""BẤM RUN FILE NÀY. Tự cài thư viện còn thiếu, tạo dữ liệu mẫu nếu chưa có, nạp dữ liệu, cho AI học rồi mở web.

Chỉ cần chạy MỘT lần và để cửa sổ này mở. Khi có dữ liệu mới: vào trang "Cập nhật dữ liệu" trên web,
không cần chạy lại file này. Muốn tạo lại dữ liệu từ đầu: xóa thư mục raw/ và file gym.db rồi chạy lại.
"""
import importlib.util
import os
import socket
import subprocess
import sys
from pathlib import Path

try:   # Windows: cho phép in tiếng Việt có dấu
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
BASE = Path(__file__).resolve().parent
RAW = BASE / "raw"
DB = BASE / "gym.db"
# module: (tên pip, phiên bản tối thiểu)
PACKAGES = {"pandas": ("pandas", "2.0"), "numpy": ("numpy", "1.24"), "flask": ("flask", "2.3"),
            "sklearn": ("scikit-learn", "1.2"), "openpyxl": ("openpyxl", "3.0")}


def _ver(v):
    return tuple(int("".join(ch for ch in p if ch.isdigit()) or 0) for p in v.split(".")[:2])


def ensure_packages():
    from importlib.metadata import PackageNotFoundError, version
    need = []
    for mod, (pip, minv) in PACKAGES.items():
        if importlib.util.find_spec(mod) is None:
            need.append(pip)
            continue
        try:
            if _ver(version(pip)) < _ver(minv):
                need.append(f"{pip}>={minv}")
        except PackageNotFoundError:
            pass
    if need:
        print(f"--> Đang cài/cập nhật thư viện: {', '.join(need)} (lần đầu mất 1-3 phút)")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", *need], check=True, env=ENV)


def has_raw():
    return RAW.exists() and (any(RAW.glob("*.xlsx")) or
                             any((p / "hoi_vien.csv").exists() for p in RAW.iterdir() if p.is_dir()))


def raw_newer_than_db():
    if not DB.exists():
        return True
    files = list(RAW.glob("*/*.csv")) + [f for f in RAW.glob("*.xlsx") if not f.name.startswith("~$")]
    return max((f.stat().st_mtime for f in files), default=0) > DB.stat().st_mtime


def free_port(start=8501):
    for port in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


if __name__ == "__main__":
    ensure_packages()
    sys.path.insert(0, str(BASE))
    os.chdir(BASE)
    import etl  # noqa: E402  (cần pandas đã cài)
    if not has_raw() and not DB.exists():
        print("--> Lần chạy đầu: tạo dữ liệu mẫu 3 chi nhánh × 300 khách")
        import generate_data
        generate_data.main(300, 0)
    if has_raw() and (not etl.schema_ok() or raw_newer_than_db()):
        print("--> Nạp dữ liệu từ thư mục raw/")
        etl.load_all()
    import web  # noqa: E402
    web.run(port=free_port())
