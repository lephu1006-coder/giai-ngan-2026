#!/usr/bin/env python3
"""Tải số liệu (bản CSV công bố lên web) và ghi tệp JSON để dựng trang.

SHEET_CSV_URL  -> tonghop.json  : tab 'Tổng hợp' của bảng theo dõi thanh toán (Trung tâm Cung ứng DVSNC)
SHEET2_CSV_URL -> cds_mtqg.json : tab 'TỔNG QUAN' của bảng số liệu vốn chuyển đổi số và các dự án
Link lấy trong Google Sheet: Tệp > Chia sẻ > Công bố lên web > chọn đúng tab > CSV.
Thiếu link nào thì giữ nguyên số liệu hiện có của tệp đó.
"""
import csv, io, json, os, sys, datetime, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent


def get(url):
    if url.startswith(("http://", "https://")):
        req = urllib.request.Request(url, headers={"User-Agent": "tanlap-giai-ngan"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8-sig")
    return pathlib.Path(url).read_text(encoding="utf-8-sig")


def save(url, out_name, must_have, label):
    if not url:
        print(f"Chưa có link {label}: giữ nguyên {out_name}")
        return
    rows = [[c.strip() for c in row] for row in csv.reader(io.StringIO(get(url)))]
    while rows and not any(rows[-1]):
        rows.pop()
    values = [r[: max([i + 1 for i, c in enumerate(r) if c] or [0])] for r in rows]
    text = " ".join(" ".join(r) for r in values).upper()
    if not all(k in text for k in must_have):
        sys.exit(f"Link {label} không đúng tab cần lấy (thiếu: {', '.join(must_have)})")
    out = {"fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "range": label, "values": values}
    (ROOT / out_name).write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Đã tải {label}: {len(values)} dòng")


save(os.environ.get("SHEET_CSV_URL", "").strip() or (sys.argv[1] if len(sys.argv) > 1 else ""), "tonghop.json", ["TỔNG CỘNG"], "Tổng hợp")
save(os.environ.get("SHEET2_CSV_URL", "").strip() or (sys.argv[2] if len(sys.argv) > 2 else ""), "cds_mtqg.json", ["CHUYỂN ĐỔI SỐ"], "TỔNG QUAN vốn chuyển đổi số, MTQG")
