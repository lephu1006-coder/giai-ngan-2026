#!/usr/bin/env python3
"""Tải tab 'Tổng hợp' (bản CSV công bố lên web) và ghi tonghop.json.

Dùng: SHEET_CSV_URL=<link CSV> python fetch.py
Link lấy trong Google Sheet: Tệp > Chia sẻ > Công bố lên web > chọn tab Tổng hợp > CSV.
"""
import csv, io, json, os, sys, datetime, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
url = os.environ.get("SHEET_CSV_URL", "").strip() or (sys.argv[1] if len(sys.argv) > 1 else "")
if not url:
    print("Chưa có SHEET_CSV_URL: giữ nguyên số liệu hiện có")
    sys.exit(0)
if url.startswith(("http://", "https://")):
    req = urllib.request.Request(url, headers={"User-Agent": "tanlap-giai-ngan"})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8-sig")
else:
    text = pathlib.Path(url).read_text(encoding="utf-8-sig")
rows = [[c.strip() for c in row] for row in csv.reader(io.StringIO(text))]
while rows and not any(rows[-1]):
    rows.pop()
values = [r[: max([i + 1 for i, c in enumerate(r) if c] or [0])] for r in rows]
if not any("TỔNG CỘNG" in " ".join(r).upper() for r in values):
    sys.exit("Không thấy dòng TỔNG CỘNG: link có đúng tab Tổng hợp không?")
out = {"fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "range": "Tổng hợp (CSV)", "values": values}
(ROOT / "tonghop.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
print(f"Đã tải {len(values)} dòng")
