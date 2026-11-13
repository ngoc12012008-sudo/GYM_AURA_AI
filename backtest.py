"""Kiểm tra ngược: chấm điểm tại một ngày trong quá khứ, so với việc khách có thật sự rời bỏ trong 90 ngày sau.

Chạy: python backtest.py [YYYY-MM-DD]
Quy tắc tốt khi tỷ lệ bỏ thật tăng dần: An toàn < Trung bình < Cao < Cực kỳ nguy hiểm.
"""
import sys

import pandas as pd

from churn import churn_label, data_end, load_data, score
from config import RISK_ORDER, load_rules

r = load_rules()
data = load_data()
end = data_end(data)
asof = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else end - pd.Timedelta(days=90 + r["an_han_ngay"])

s = score(asof, data, r, explain=False).set_index("ma_hv")
y = churn_label(asof, data["goi_the"], end, 90, r["an_han_ngay"])
m = s.join(y, how="inner").dropna(subset=["da_bo"])
print(f"Ngày kiểm tra: {asof.date()} | {len(m)} hội viên có kết quả | tỷ lệ rời bỏ 90 ngày chung: {m['da_bo'].mean():.0%}\n")
t = m.groupby("muc_rui_ro")["da_bo"].agg(so_khach="size", ty_le_bo="mean").reindex(RISK_ORDER).dropna()
print(t.to_string(formatters={"ty_le_bo": "{:.0%}".format}))
print()
print(m.groupby("chi_nhanh")["da_bo"].agg(so_khach="size", ty_le_bo="mean").to_string(formatters={"ty_le_bo": "{:.0%}".format}))
