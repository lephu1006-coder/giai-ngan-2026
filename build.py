#!/usr/bin/env python3
"""Dựng trang công khai tình hình giải ngân, UBND phường Tân Lập.

Đầu vào:  tonghop.json  (tab 'Tổng hợp' của bảng theo dõi, giữ nguyên các ô)
          nq27.json     (Biểu 02 kèm Nghị quyết số 27/NQ-HĐND)
          history.json  (giải ngân lũy kế theo ngày và nhóm nguồn vốn; tự ghi thêm mỗi lần chạy)
Đầu ra:   index.html, og.png (ảnh xem trước khi chia sẻ link), history.json
Dừng với mã lỗi khác 0 nếu số liệu không khớp (tổng nhóm, tổng cộng), để không đăng số sai.
"""
import json, sys, html, datetime as dt, pathlib, math, os, re, unicodedata

ROOT = pathlib.Path(__file__).resolve().parent
TZ = dt.timezone(dt.timedelta(hours=7))
SITE_URL = "https://lephu1006-coder.github.io/giai-ngan-2026/"
YEAR_START = dt.date(2026, 1, 1)
DUE_2026 = dt.date(2027, 1, 31)
e = html.escape


# ---------- số liệu ----------
def num(s):
    t = str(s or "").replace(".", "").replace(",", ".").strip()
    try:
        return float(t) if t else 0.0
    except ValueError:
        return 0.0


def parse(values):
    groups, rows, total, g = [], [], None, None
    for v in values:
        v = list(v) + [""] * 6
        tt, name = str(v[0]).strip(), str(v[1]).strip()
        if not tt and name.upper().startswith("TỔNG CỘNG"):
            total = (num(v[3]), num(v[4]))
            continue
        if tt and all(c in "IVXLC" for c in tt):
            g = {"nhom": tt, "nguon": name, "kh": num(v[3]), "gn": num(v[4]), "co_von": str(v[3]).strip() != ""}
            groups.append(g)
            continue
        if g and tt.isdigit() and name:
            rows.append({"nhom": g["nhom"], "stt": int(tt), "du_an": name, "kh": num(v[3]), "gn": num(v[4])})
    return groups, rows, total


def validate(groups, rows, total):
    errs = []
    for g in groups:
        if not g["co_von"]:
            continue
        rs = [r for r in rows if r["nhom"] == g["nhom"]]
        skh, sgn = sum(r["kh"] for r in rs), sum(r["gn"] for r in rs)
        if abs(skh - g["kh"]) > 1 or abs(sgn - g["gn"]) > 1:
            errs.append(f"Nhóm {g['nhom']}: cộng dự án {skh:,.0f}/{sgn:,.0f} khác dòng nhóm {g['kh']:,.0f}/{g['gn']:,.0f}")
    if total is None:
        errs.append("Không thấy dòng TỔNG CỘNG")
    else:
        gkh = sum(g["kh"] for g in groups if g["co_von"])
        ggn = sum(g["gn"] for g in groups if g["co_von"])
        if abs(gkh - total[0]) > 1 or abs(ggn - total[1]) > 1:
            errs.append(f"Tổng các nhóm {gkh:,.0f}/{ggn:,.0f} khác dòng TỔNG CỘNG {total[0]:,.0f}/{total[1]:,.0f}")
    if not rows:
        errs.append("Không đọc được dự án nào")
    return errs


# khóa, tên đầy đủ, tên ngắn, căn cứ, hạn giải ngân, khối (A: cấp trên giao, B: HĐND phường giao), ngày giao vốn
LABEL = [
    ("kéo dài", "Kế hoạch vốn năm 2025 kéo dài sang năm 2026", "Vốn 2025 kéo dài", "Quyết định số 1199/QĐ-UBND ngày 14/4/2026 của UBND tỉnh; thời hạn giải ngân đến hết ngày 31/12/2026 theo Quyết định số 3598/QĐ-UBND ngày 09/11/2026 của UBND tỉnh", dt.date(2026, 12, 31), "A", dt.date(2026, 4, 14)),
    ("02558", "Kế hoạch vốn năm 2026 giao mới", "KH 2026 giao mới", "Quyết định số 02558/QĐ-UBND ngày 31/12/2025", DUE_2026, "A", dt.date(2025, 12, 31)),
    ("1133", "Kế hoạch vốn đầu tư công năm 2026, ngân sách phường", "Ngân sách phường", "Quyết định số 1133/QĐ-UBND ngày 17/6/2026 và số 1474/QĐ-UBND ngày 26/8/2026", DUE_2026, "B", dt.date(2026, 6, 17)),
    ("2347", "Kế hoạch vốn chi đầu tư phát triển khác, ngân sách tỉnh bổ sung có mục tiêu", "Ngân sách tỉnh bổ sung", "Quyết định số 2347/QĐ-UBND ngày 24/7/2026 của UBND tỉnh; UBND phường giao đợt 1 tại Quyết định số 1385/QĐ-UBND ngày 18/8/2026", DUE_2026, "A", dt.date(2026, 8, 18)),
    ("CĐS", "Vốn chuyển đổi số, ngân sách tỉnh bổ sung có mục tiêu", "Chuyển đổi số", "Quyết định số 3164/QĐ-UBND ngày 30/9/2026 và số 3392/QĐ-UBND ngày 22/10/2026 của UBND tỉnh", DUE_2026, "A", dt.date(2026, 9, 30)),
    ("MTQG", "Vốn Chương trình mục tiêu quốc gia năm 2026 và vốn đối ứng ngân sách phường", "CT mục tiêu quốc gia", "Nghị quyết số 31/NQ-HĐND ngày 10/11/2026 của HĐND phường", DUE_2026, "A", dt.date(2026, 11, 10)),
    ("27/NQ", "Bổ sung kế hoạch vốn năm 2026 (tiền sử dụng đất)", "Bổ sung NQ 27", "Nghị quyết số 27/NQ-HĐND ngày 06/10/2026 của HĐND phường", dt.date(2027, 12, 31), "B", dt.date(2026, 10, 6)),
    ("31/NQ", "Phân bổ bổ sung kế hoạch vốn năm 2026, ngân sách phường (tiền sử dụng đất)", "Bổ sung NQ 31", "Nghị quyết số 31/NQ-HĐND ngày 10/11/2026 của HĐND phường", dt.date(2027, 12, 31), "B", dt.date(2026, 11, 10)),
]
KHOI = {"A": ("Vốn cấp trên giao", "Tính vào KPI, phải giải ngân hết kế hoạch năm 2026"),
        "B": ("Vốn HĐND phường giao", "Ngân sách phường do HĐND phường phân bổ")}
URGENT_DAYS = 60  # vốn cấp trên giao chưa đủ 60 ngày: cấp bách, chưa đánh giá chậm
CUT_B = dt.date(2026, 9, 30)  # tách vốn HĐND phường giao trước và bổ sung sau ngày 30/9/2026
SUB_B = {"truoc": "Giao trước ngày 30/9/2026", "sau": "Bổ sung sau ngày 30/9/2026"}


def label(nguon):
    for key, long, short, basis, due, khoi, giao in LABEL:
        if key in nguon:
            return long, short, basis, due, khoi, giao
    return nguon, nguon[:24], "", DUE_2026, "B", YEAR_START


# Tình hình thực hiện theo văn bản đã ban hành (thư mục Lưu trữ trình duyệt, báo cáo tuần của Phòng KT-HT&ĐT).
# (khóa nguồn vốn, cụm tên dự án, số vốn dư không còn nhu cầu giải ngân, ghi chú)
TIEN_DO = [
    ("kéo dài", "Mầm non Tân Hòa", 81_686_000,
     "Dự án hoàn thành, đã phê duyệt quyết toán tại Quyết định số 1348/QĐ-UBND ngày 07/8/2026 của UBND phường. "
     "Số vốn còn lại 81.686.000 đồng không còn nhu cầu giải ngân; UBND phường đã đề nghị điều chỉnh giảm tại "
     "Báo cáo số 663/BC-UBND ngày 27/10/2026 gửi Sở Tài chính, chờ UBND tỉnh quyết định."),
    ("kéo dài", "Cao Đạt", 0,
     "Đang vận động bàn giao phần mặt bằng còn lại, tháo gỡ vướng mắc đơn thư. Thời hạn giải ngân vốn năm 2025 kéo dài "
     "được điều chỉnh đến hết ngày 31/12/2026 tại Quyết định số 3598/QĐ-UBND ngày 09/11/2026 của UBND tỉnh."),
    ("02558", "Cao Đạt", 0, "Đang vận động bàn giao phần mặt bằng còn lại, tháo gỡ vướng mắc đơn thư."),
    ("1133", "Nguyễn Du", 0, "Đang thi công; Phòng KT-HT&ĐT đôn đốc, giám sát nhà thầu đẩy nhanh tiến độ."),
    ("1133", "Nguyễn Văn Cừ", 0, "Đang thi công; Phòng KT-HT&ĐT đôn đốc, giám sát nhà thầu đẩy nhanh tiến độ."),
    ("1133", "Trạm Y tế", 0, "Đang thi công; Phòng KT-HT&ĐT đôn đốc, giám sát nhà thầu đẩy nhanh tiến độ."),
    ("1133", "hội trường", 0, "Đang thi công; Phòng KT-HT&ĐT đôn đốc, giám sát nhà thầu đẩy nhanh tiến độ."),
]
DONE = "Đã quyết toán"


def date_in(text):
    m = re.search(r"ngày\s+(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def own_progress(today, giao, due):
    """Tiến độ thời gian riêng của một nguồn: từ ngày giao vốn đến hạn giải ngân."""
    if due <= giao:
        return 1.0
    return max(0.0, min(1.0, (today - giao).days / (due - giao).days))


def status(tl, khoi, giao, due, today, chua_giao, done=False):
    if done:
        return DONE
    if chua_giao:
        return "Chờ UBND giao chi tiết"
    if tl >= 0.9995:
        return "Đạt tiến độ"
    if khoi == "A" and (today - giao).days < URGENT_DAYS:
        return "Cấp bách"
    return "Đạt tiến độ" if tl >= own_progress(today, giao, due) else "Chậm tiến độ"


# Kế hoạch vốn năm 2026 của 02 dự án nhà văn hóa cộng đồng theo Biểu 02 kèm theo Nghị quyết số 31/NQ-HĐND
# ngày 10/11/2026 của HĐND phường (bảng theo dõi ghi tổng mức đầu tư ở cột số vốn giao). Tên dự án theo Nghị quyết.
NQ31_MTQG = [
    (("mliâo", "mlâo"), "Cải tạo, sửa chữa Nhà văn hóa cộng đồng buôn Kõ Mliâo", 1_127e6,
     "Quyết định số 1999/QĐ-UBND ngày 04/11/2026"),
    (("cuôr",), "Cải tạo, sửa chữa Nhà văn hóa cộng đồng buôn Ea Cuôr Kap", 672e6,
     "Quyết định số 2000/QĐ-UBND ngày 04/11/2026"),
]


# Biểu 02 kèm theo Nghị quyết số 31/NQ-HĐND: phần vốn ngân sách phường (tiền sử dụng đất), UBND phường giao chi tiết
# khi bảo đảm điều kiện. 61 triệu đồng vốn đối ứng của dự án nhà văn hóa buôn Ea Cuôr Kap đã tính trong nhóm MTQG.
NQ31_NSP = [
    ("Xây dựng cơ sở hạ tầng khu dân cư C5-C6-C7 thuộc Quy hoạch Km7, phường Tân Lập, tỉnh Đắk Lắk", 1_000e6),
    ("Trường tiểu học Nguyễn Du; Hạng mục: Nhà lớp học kết hợp nhà bộ môn và Hạ tầng kỹ thuật khác", 2_800e6),
    ("Trường THCS Nguyễn Văn Cừ; Hạng mục: Nhà lớp học 18 phòng và Hạ tầng kỹ thuật khác", 2_900e6),
    ("Cải tạo Trạm Y tế phường Tân Lập", 200e6),
    ("Cải tạo nhà hội trường, nhà làm việc Đảng ủy phường Tân Lập", 180e6),
    ("Cải tạo các đường hẻm Hùng Vương - Ama Khê", 1_500e6),
]


def apply_nq31(rs):
    errs = []
    for r in rs:
        key = unicodedata.normalize("NFC", r["du_an"]).lower()
        hit = [x for x in NQ31_MTQG if any(unicodedata.normalize("NFC", k) in key for k in x[0])]
        if len(hit) != 1:
            errs.append(f"{r['du_an']}: không đối chiếu được với Nghị quyết số 31/NQ-HĐND")
            continue
        _, ten, kh, qd = hit[0]
        if r["gn"] > kh + 1e3:
            errs.append(f"{ten}: số đã giải ngân lớn hơn kế hoạch vốn năm 2026")
        r.update(du_an=ten, kh=kh, basis=qd)
    return errs


def parse_cds(values):
    """Bảng số liệu vốn chuyển đổi số và các dự án (đơn vị triệu đồng): lấy các dự án đầu tư
    vốn chuyển đổi số và chương trình mục tiêu quốc gia; bỏ chi thường xuyên và nhiệm vụ khác."""
    out, errs = {"cds": [], "mtqg": []}, []
    for v in values:
        v = list(v) + [""] * 8
        tt, name = str(v[0]).strip(), " ".join(str(v[1]).split())
        if not name.lower().startswith("dự án") or (tt and not all(c in "IVXLC" for c in tt)):
            continue
        name = name.replace("Dự án: ", "Dự án ").strip()
        kind = "cds" if "chuyển đổi số" in name.lower() else "mtqg" if "nhà văn hóa cộng đồng" in name.lower() else None
        if not kind:
            continue
        kh, gn, cl = num(v[3]) * 1e6, num(v[4]) * 1e6, num(v[6]) * 1e6
        if str(v[6]).strip() and abs(kh - gn - cl) > 1e3:
            errs.append(f"{name}: vốn giao trừ đã giải ngân khác số còn lại")
        out[kind].append({"du_an": name, "kh": kh, "gn": gn, "basis": " ".join(str(v[2]).split()), "note": " ".join(str(v[7]).split())})
    errs += apply_nq31(out["mtqg"])
    return out, errs


def model(th, nq, cds=None, today=None):
    today = today or dt.datetime.now(TZ).date()
    groups, rows, total = parse(th["values"])
    errs = validate(groups, rows, total)
    if errs:
        print("SỐ LIỆU KHÔNG KHỚP, KHÔNG DỰNG TRANG:\n- " + "\n- ".join(errs), file=sys.stderr)
        sys.exit(2)
    empty = [g for g in groups if not g["co_von"]]
    keep = [dict(g, chua_giao=False) for g in groups if g["co_von"]]
    projects = [dict(r, chua_giao=False) for r in rows if any(g["nhom"] == r["nhom"] for g in keep)]
    sheet_has_nq = any(("27/NQ" in g["nguon"] or "10 dự án mới" in g["nguon"]) and g["co_von"] for g in groups)
    if not sheet_has_nq:
        nq_nhom = empty[0]["nhom"] if empty else "V"
        keep.append({"nhom": nq_nhom, "nguon": "27/NQ-HĐND", "kh": sum(float(x["ke_hoach"]) for x in nq),
                     "gn": sum(float(x["da_giai_ngan"]) for x in nq), "co_von": True, "chua_giao": True})
        for x in nq:
            projects.append({"nhom": nq_nhom, "stt": int(x["stt"]), "du_an": x["du_an"], "kh": float(x["ke_hoach"]),
                             "gn": float(x["da_giai_ngan"]), "chua_giao": True})
    if cds:
        extra, errs2 = parse_cds(cds["values"])
        if errs2:
            print("SỐ LIỆU VỐN CHUYỂN ĐỔI SỐ, MTQG KHÔNG KHỚP:\n- " + "\n- ".join(errs2), file=sys.stderr)
            sys.exit(2)
        used = {g["nhom"] for g in keep}
        romans = [r for r in "I II III IV V VI VII VIII IX X XI XII".split() if r not in used]
        for kind, nguon in (("cds", "CĐS"), ("mtqg", "MTQG")):
            rs = extra[kind]
            if not rs:
                continue
            nh = romans.pop(0)
            keep.append({"nhom": nh, "nguon": nguon, "kh": sum(r["kh"] for r in rs), "gn": sum(r["gn"] for r in rs),
                         "co_von": True, "chua_giao": False})
            for i, r in enumerate(rs, 1):
                projects.append({"nhom": nh, "stt": i, "du_an": r["du_an"], "kh": r["kh"], "gn": r["gn"], "chua_giao": False,
                                 "note": r["note"], "basis_p": r["basis"],
                                 "giao_p": date_in(r["basis"]) if kind == "cds" else None})
    if not any("31/NQ" in g["nguon"] and g["co_von"] for g in groups):
        used = {g["nhom"] for g in keep}
        nh = [r for r in "I II III IV V VI VII VIII IX X XI XII".split() if r not in used][0]
        keep.append({"nhom": nh, "nguon": "31/NQ-HĐND", "kh": sum(k for _, k in NQ31_NSP), "gn": 0.0, "co_von": True, "chua_giao": True})
        for i, (ten, k) in enumerate(NQ31_NSP, 1):
            projects.append({"nhom": nh, "stt": i, "du_an": ten, "kh": k, "gn": 0.0, "chua_giao": True})
    giao = [p for p in projects if not p["chua_giao"]]
    kh_g, gn_g = sum(p["kh"] for p in giao), sum(p["gn"] for p in giao)
    for g in keep:
        g["tl"] = g["gn"] / g["kh"] if g["kh"] else 0
        g["long"], g["short"], g["basis"], g["due"], g["khoi"], g["giao"] = label(g["nguon"])
    order = {"A": 0, "B": 1}
    keep.sort(key=lambda g: (order[g["khoi"]], g["chua_giao"]))
    seq = {"A": 0, "B": 0}
    for g in keep:
        seq[g["khoi"]] += 1
        g["ma"] = f'{g["khoi"]}{seq[g["khoi"]]}'
    gmap = {g["nhom"]: g for g in keep}
    for p in projects:
        g = gmap[p["nhom"]]
        p["khoi"], p["due"] = g["khoi"], g["due"]
        p["giao"] = p.get("giao_p") or g["giao"]
        p["tl"] = p["gn"] / p["kh"] if p["kh"] else 0
        p["du"], done = 0.0, False
        for key, ten, du, note in TIEN_DO:
            if key in g["nguon"] and ten.lower() in p["du_an"].lower():
                p["du"] = min(float(du), max(p["kh"] - p["gn"], 0))
                done = du > 0 and p["kh"] - p["gn"] - p["du"] <= 1e3
                if not p.get("note"):
                    p["note"] = note
        p["done"] = done
        tl_eff = p["gn"] / (p["kh"] - p["du"]) if p["kh"] - p["du"] > 0 else 1
        p["xl"] = status(tl_eff, p["khoi"], p["giao"], p["due"], today, p["chua_giao"], done)
    for g in keep:
        ps = [p for p in projects if p["nhom"] == g["nhom"]]
        g["giao"] = min([p["giao"] for p in ps] + [g["giao"]]) if ps else g["giao"]
        g["du"] = sum(p["du"] for p in ps)
        tl_eff = g["gn"] / (g["kh"] - g["du"]) if g["kh"] - g["du"] > 0 else 1
        g["xl"] = status(tl_eff, g["khoi"], g["giao"], g["due"], today, g["chua_giao"])
    projects.sort(key=lambda p: (order[p["khoi"]], [g["nhom"] for g in keep].index(p["nhom"]), p["stt"]))
    t = {"kh": sum(p["kh"] for p in projects), "gn": sum(p["gn"] for p in projects), "kh_g": kh_g, "gn_g": gn_g,
         "kh_chua": sum(p["kh"] for p in projects if p["chua_giao"]), "n_chua": sum(1 for p in projects if p["chua_giao"])}
    return keep, projects, t


# ---------- lịch sử giải ngân ----------
def update_history(hist, groups, today):
    daily = hist.setdefault("daily", {})
    cur = {g["nhom"]: round(g["gn"]) for g in groups if not g["chua_giao"] and g["gn"]}
    last = daily[max(daily)] if daily else {}
    if cur != last:
        daily[today.isoformat()] = cur
    return hist


def cum_on(daily, d, nhoms=None):
    keys = [k for k in daily if k <= d.isoformat()]
    if not keys:
        return 0.0
    row = daily[max(keys)]
    return float(sum(v for k, v in row.items() if nhoms is None or k in nhoms))


def periods(daily, today, kh_ref):
    def mk(label, start, end):
        end = min(end, today)
        a = cum_on(daily, start - dt.timedelta(days=1))
        b = cum_on(daily, end)
        return {"label": label, "start": start, "end": end, "in": b - a, "cum": b, "pct": b / kh_ref if kh_ref else 0}

    weeks, d = [], today - dt.timedelta(days=today.weekday())
    for _ in range(12):
        iso = d.isocalendar()
        weeks.append(mk(f"Tuần {iso[1]} ({d:%d/%m}–{(d + dt.timedelta(days=6)):%d/%m})", d, d + dt.timedelta(days=6)))
        d -= dt.timedelta(days=7)
    weeks.reverse()
    months = []
    for m in range(1, today.month + 1):
        s = dt.date(today.year, m, 1)
        nxt = dt.date(today.year + (m == 12), m % 12 + 1, 1)
        months.append(mk(f"Tháng {m}", s, nxt - dt.timedelta(days=1)))
    while len(months) > 1 and months[0]["cum"] == 0 and months[0]["in"] == 0:
        months.pop(0)
    quarters = []
    for q in range(1, (today.month - 1) // 3 + 2):
        s = dt.date(today.year, 3 * q - 2, 1)
        em = 3 * q
        nxt = dt.date(today.year + (em == 12), em % 12 + 1, 1)
        quarters.append(mk("Quý " + "I II III IV".split()[q - 1], s, nxt - dt.timedelta(days=1)))
    return weeks, months, quarters


def workdays(a, b):
    """Số ngày làm việc (thứ Hai đến thứ Sáu) từ a đến hết b, không trừ ngày lễ."""
    if b < a:
        return 0
    n, d = 0, a
    while d <= b:
        n += d.weekday() < 5
        d += dt.timedelta(days=1)
    return n


# ---------- định dạng ----------
def vi(x, d=0):
    s = f"{x:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def ty(x, unit=True):
    s = vi(x / 1e9, 1 if abs(x) >= 1e11 else 2)
    return s + (" tỷ đồng" if unit else "")


def pct(x):
    return vi(x * 100, 1) + "%"


def progress(today, due):
    return max(0.0, min(1.0, (today - YEAR_START).days / (due - YEAR_START).days))


BADGE = {"Đạt tiến độ": "ok", "Chậm tiến độ": "warn", "Cấp bách": "late", "Chờ UBND giao chi tiết": "neutral", "Đã quyết toán": "done"}
FILL = {"ok": "fill-ok", "warn": "fill-warn", "late": "fill-late", "neutral": "fill-neutral", "done": "fill-done"}


# ---------- hình vẽ ----------
def ring(frac, cls, label, value, sub, mark=None, small=False):
    r, c = 52, 2 * math.pi * 52
    tick = ""
    if mark is not None:
        ang = math.radians(-90 + 360 * min(max(mark, 0), 1))
        x1, y1 = 64 + (r - 8) * math.cos(ang), 64 + (r - 8) * math.sin(ang)
        x2, y2 = 64 + (r + 10) * math.cos(ang), 64 + (r + 10) * math.sin(ang)
        tick = f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="ring-tick"><title>Tiến độ thời gian {pct(mark)}</title></line>'
    return f'''<figure class="ring{' ring-sm' if small else ''}">
  <svg viewBox="0 0 128 128" role="img" aria-label="{e(label)}: {e(value)}">
    <circle cx="64" cy="64" r="{r}" class="ring-track"/>
    <circle cx="64" cy="64" r="{r}" class="ring-val {cls}" stroke-dasharray="{c*min(frac,1):.1f} {c:.1f}" transform="rotate(-90 64 64)"/>
    {tick}
    <text x="64" y="71" text-anchor="middle" class="ring-num">{e(value)}</text>
  </svg>
  <figcaption><b>{e(label)}</b><span>{e(sub)}</span></figcaption>
</figure>'''


def trend_svg(daily, today, kh_ref, nhoms):
    W, H, L, R, T, B = 960, 320, 64, 24, 34, 36
    x0, x1 = YEAR_START, DUE_2026
    span = (x1 - x0).days
    step = 20e9 if kh_ref > 80e9 else 10e9
    ymax = max(step, math.ceil(kh_ref * 1.04 / step) * step)
    X = lambda d: L + (W - L - R) * (d - x0).days / span
    Y = lambda v: T + (H - T - B) * (1 - v / ymax)
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Giải ngân lũy kế so với tiến độ thời gian">']
    v = 0.0
    while v <= ymax + 1:
        out.append(f'<line x1="{L}" x2="{W-R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>'
                   f'<text x="{L-8}" y="{Y(v)+4:.1f}" text-anchor="end" class="tick">{vi(v/1e9,0)}</text>')
        v += step
    for m in range(1, 14):
        d = dt.date(2026 + (m > 12), (m - 1) % 12 + 1, 1)
        if d > x1:
            break
        out.append(f'<text x="{X(d)+2:.1f}" y="{H-14}" class="tick">{"T" + str((m-1)%12+1) if m <= 12 else "T1/27"}</text>'
                   f'<line x1="{X(d):.1f}" x2="{X(d):.1f}" y1="{H-B}" y2="{H-B+5}" class="axis"/>')
    out.append(f'<text x="{L-8}" y="14" text-anchor="end" class="tick">tỷ đồng</text>')
    # tiến độ thời gian
    out.append(f'<line x1="{X(x0):.1f}" y1="{Y(0):.1f}" x2="{X(x1):.1f}" y2="{Y(kh_ref):.1f}" class="line-time"/>')
    out.append(f'<line x1="{L}" x2="{W-R}" y1="{Y(kh_ref):.1f}" y2="{Y(kh_ref):.1f}" class="line-plan"/>'
               f'<text x="{L+6}" y="{Y(kh_ref)-6:.1f}" class="tick">Kế hoạch vốn có hạn đến 31/01/2027: {ty(kh_ref)}</text>')
    # giải ngân lũy kế (bậc thang)
    pts, v = [(X(x0), Y(0))], 0.0
    for k in sorted(daily):
        d = dt.date.fromisoformat(k)
        if d > today:
            break
        nv = float(sum(val for n, val in daily[k].items() if n in nhoms))
        pts.append((X(d), Y(v)))
        pts.append((X(d), Y(nv)))
        v = nv
    pts.append((X(today), Y(v)))
    path = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
    area = f"{X(x0):.1f},{Y(0):.1f} " + path + f" {X(today):.1f},{Y(0):.1f}"
    out.append(f'<polygon points="{area}" class="area-gn"/><polyline points="{path}" class="line-gn"/>')
    # đường cần đạt từ hôm nay đến hạn
    out.append(f'<line x1="{X(today):.1f}" y1="{Y(v):.1f}" x2="{X(x1):.1f}" y2="{Y(kh_ref):.1f}" class="line-need"/>')
    tp = kh_ref * progress(today, x1)
    out.append(f'<line x1="{X(today):.1f}" x2="{X(today):.1f}" y1="{Y(0):.1f}" y2="{Y(tp):.1f}" class="grid"/>')
    out.append(f'<circle cx="{X(today):.1f}" cy="{Y(v):.1f}" r="5" class="dot-gn"/>'
               f'<text x="{X(today)-10:.1f}" y="{Y(v)+5:.1f}" text-anchor="end" class="val">Đã giải ngân {ty(v)}</text>')
    out.append(f'<circle cx="{X(today):.1f}" cy="{Y(tp):.1f}" r="4" class="dot-time"/>'
               f'<text x="{X(today)-10:.1f}" y="{Y(tp)-8:.1f}" text-anchor="end" class="val val-time">Theo tiến độ thời gian {ty(tp)}</text>')
    out.append("</svg>")
    return "".join(out)


def bars_svg(items, aria):
    W, H, L, R, T, B = 960, 220, 64, 12, 24, 44
    vmax = max([p["in"] for p in items] + [1])
    n = len(items)
    bw = (W - L - R) / n
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="{e(aria)}">']
    for i in range(0, 5):
        v = vmax * i / 4
        y = T + (H - T - B) * (1 - v / vmax)
        out.append(f'<line x1="{L}" x2="{W-R}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{L-8}" y="{y+4:.1f}" text-anchor="end" class="tick">{vi(v/1e9,1)}</text>')
    for i, p in enumerate(items):
        h = (H - T - B) * max(p["in"], 0) / vmax
        x = L + i * bw + bw * 0.18
        y = H - B - h
        short = p["label"].split(" (")[0].replace("Tháng ", "T").replace("Tuần ", "Tuần\u00a0")
        cls = "col col-now" if i == n - 1 else "col"
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.64:.1f}" height="{max(h,0):.1f}" rx="4" class="{cls}"><title>{e(p["label"])}: {e(ty(p["in"]))}</title></rect>')
        if p["in"] > 0:
            out.append(f'<text x="{x+bw*0.32:.1f}" y="{y-6:.1f}" text-anchor="middle" class="val">{vi(p["in"]/1e9,1)}</text>')
        out.append(f'<text x="{x+bw*0.32:.1f}" y="{H-B+18}" text-anchor="middle" class="tick">{e(short)}</text>')
    out.append(f'<text x="{L-8}" y="12" text-anchor="end" class="tick">tỷ đồng</text></svg>')
    return "".join(out)


def period_table(items):
    rows = "".join(f'<tr><td>{e(p["label"])}</td><td class="num">{ty(p["in"], False)}</td><td class="num">{ty(p["cum"], False)}</td><td class="num">{pct(p["pct"])}</td></tr>'
                   for p in reversed(items))
    return (f'<div class="table-wrap"><table class="ptable"><thead><tr><th>Kỳ</th><th class="num">Giải ngân trong kỳ<br>(tỷ đồng)</th>'
            f'<th class="num">Lũy kế đến cuối kỳ<br>(tỷ đồng)</th><th class="num">Lũy kế / kế hoạch<br>đã giao</th></tr></thead><tbody>{rows}</tbody></table></div>')


HEADER_PATTERN = '''<svg class="hero-pattern" viewBox="0 0 1200 460" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
<defs><filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<linearGradient id="neon" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#2bb3c8"/><stop offset="1" stop-color="#5DB75E"/></linearGradient></defs>
<g class="pt-rong" fill="none" stroke-width="1.6">
<polyline points="20,460 230,250 440,460"/><polyline points="70,460 230,300 390,460"/><polyline points="120,460 230,350 340,460"/>
<line x1="205" y1="225" x2="255" y2="275"/><line x1="255" y1="225" x2="205" y2="275"/>
<rect x="130" y="400" width="200" height="60"/><line x1="170" y1="400" x2="170" y2="460"/><line x1="210" y1="400" x2="210" y2="460"/><line x1="250" y1="400" x2="250" y2="460"/><line x1="290" y1="400" x2="290" y2="460"/>
</g>
<g class="pt-neon" fill="none" stroke="url(#neon)" stroke-width="2" filter="url(#glow)">
<path d="M700 460 C700 370 760 340 820 300 S 900 220 900 150"/><circle cx="900" cy="140" r="9"/>
<path d="M770 460 C770 390 830 360 890 320 S 990 250 1020 190"/><circle cx="1026" cy="180" r="9"/>
<path d="M850 460 C860 410 920 380 980 350 S 1100 300 1130 250"/><circle cx="1138" cy="240" r="9"/>
<path d="M620 0 C640 60 700 80 760 90"/><circle cx="770" cy="92" r="7"/>
<path d="M1030 0 C1030 40 1070 70 1130 80"/><circle cx="1140" cy="82" r="7"/>
</g></svg>'''


def render(groups, projects, t, hist, fetched):
    today = fetched.astimezone(TZ).date()
    upd = today.strftime("%d/%m/%Y")
    daily = hist["daily"]
    nhoms = {g["nhom"] for g in groups}
    kh_all = sum(g["kh"] for g in groups)
    gn_now = sum(g["gn"] for g in groups)
    kh_chua = sum(g["kh"] for g in groups if g["chua_giao"])
    g_due26 = [g for g in groups if g["due"] <= DUE_2026]
    kh_ref = sum(g["kh"] for g in g_due26)  # kế hoạch có hạn giải ngân đến 31/01/2027, dùng cho biểu đồ diễn biến
    tg = progress(today, DUE_2026)
    rate = gn_now / kh_all if kh_all else 0
    for g in groups:
        g["sub"] = ("truoc" if g["giao"] <= CUT_B else "sau") if g["khoi"] == "B" else ""
    cnt = {k: sum(1 for p in projects if p["xl"] == k) for k in BADGE}
    weeks, months, quarters = periods(daily, today, kh_all)
    wk, mo, qu = weeks[-1], months[-1], quarters[-1]
    prev_wk = weeks[-2] if len(weeks) > 1 else None
    tomorrow = today + dt.timedelta(days=1)

    def need(gs):
        left = sum(max(g["kh"] - g["gn"] - g["du"], 0) for g in gs)
        per = sum(max(g["kh"] - g["gn"] - g["du"], 0) / (workdays(tomorrow, g["due"]) or 1) for g in gs)
        return left, per

    # hai khối nguồn vốn
    blk = {}
    for k in ("A", "B"):
        gs = [g for g in groups if g["khoi"] == k]
        kh, gn = sum(g["kh"] for g in gs), sum(g["gn"] for g in gs)
        left, per = need(gs)
        blk[k] = {"gs": gs, "kh": kh, "gn": gn, "tl": gn / kh if kh else 0, "left": left, "per": per,
                  "chua": sum(g["kh"] for g in gs if g["chua_giao"]),
                  "n_cb": sum(1 for p in projects if p["khoi"] == k and p["xl"] == "Cấp bách"),
                  "n_ch": sum(1 for p in projects if p["khoi"] == k and p["xl"] == "Chậm tiến độ")}
    subs = {}
    for sk in ("truoc", "sau"):
        gs = [g for g in groups if g["sub"] == sk]
        kh, gn = sum(g["kh"] for g in gs), sum(g["gn"] for g in gs)
        subs[sk] = {"gs": gs, "kh": kh, "gn": gn, "tl": gn / kh if kh else 0, "chua": sum(g["kh"] for g in gs if g["chua_giao"])}
    tot_left, per_day = need(groups)

    take = (f"Đến ngày {upd}, phường đã giải ngân {ty(gn_now)}, đạt {pct(rate)} tổng kế hoạch vốn năm 2026 "
            f"({ty(kh_all)}); tiến độ thời gian đã qua {pct(tg)}. "
            f"Vốn cấp trên giao đạt {pct(blk['A']['tl'])} ({ty(blk['A']['gn'])}/{ty(blk['A']['kh'])}), "
            f"vốn HĐND phường giao đạt {pct(blk['B']['tl'])} ({ty(blk['B']['gn'])}/{ty(blk['B']['kh'])}; "
            f"phần giao trước ngày 30/9/2026 đạt {pct(subs['truoc']['tl'])}). "
            f"Tuần này giải ngân thêm {ty(wk['in'])}, từ đầu tháng {today.month} là {ty(mo['in'])}. "
            f"Để giải ngân hết kế hoạch đúng hạn, bình quân mỗi ngày làm việc cần giải ngân khoảng {ty(per_day)}, "
            f"riêng vốn cấp trên giao là {ty(blk['A']['per'])}.")
    if blk["A"]["n_cb"]:
        take += f" {blk['A']['n_cb']} dự án vốn cấp trên mới giao (chưa đủ {URGENT_DAYS} ngày) được xếp cấp bách, cần tập trung giải ngân ngay."
    n_done = [p for p in projects if p["done"]]
    if n_done:
        take += (f" {len(n_done)} dự án đã quyết toán, còn {vi(sum(p['du'] for p in n_done))} đồng vốn dư đã đề nghị cấp có thẩm quyền "
                 f"điều chỉnh giảm, không tính vào số vốn còn phải giải ngân.")
    if kh_chua:
        take += f" Trong tổng kế hoạch có {ty(kh_chua)} HĐND phường bổ sung sau ngày 30/9/2026, đang chờ UBND phường giao chi tiết."

    delta = f'Tuần trước {ty(prev_wk["in"])}' if prev_wk is not None else ""

    # thẻ hai khối
    def kcard(cls, label, value, sub, note):
        return (f'<div class="kpi {cls}"><p class="kpi-label">{e(label)}</p><p class="kpi-value">{e(value)}</p>'
                f'<p class="kpi-sub">{e(sub)}</p><p class="kpi-note">{e(note)}</p></div>')
    def split_line(sk):
        x = subs[sk]
        extra = f" · chờ UBND giao chi tiết {ty(x['chua'])}" if x["chua"] else ""
        return (f'<li><span>{e(SUB_B[sk])}</span><b>{pct(x["tl"])}</b>'
                f'<small>{ty(x["gn"])} / {ty(x["kh"])}{e(extra)}</small></li>')
    khoi_cards = "".join([
        kcard("k-red", "Tổng cộng toàn phường", pct(rate), f"{ty(gn_now)} / {ty(kh_all)}",
              f"Còn {ty(tot_left)}" + (f"; trong đó {ty(kh_chua)} chờ UBND giao chi tiết" if kh_chua else "")),
        kcard("k-gold", "A. " + KHOI["A"][0], pct(blk["A"]["tl"]), f"{ty(blk['A']['gn'])} / {ty(blk['A']['kh'])}",
              f"{KHOI['A'][1]}. Còn {ty(blk['A']['left'])}, mỗi ngày làm việc cần {ty(blk['A']['per'])}"),
        f'<div class="kpi k-brown"><p class="kpi-label">B. {e(KHOI["B"][0])}</p><p class="kpi-value">{pct(blk["B"]["tl"])}</p>'
        f'<p class="kpi-sub">{ty(blk["B"]["gn"])} / {ty(blk["B"]["kh"])}</p><ul class="kpi-split">{split_line("truoc")}{split_line("sau")}</ul></div>',
    ])

    # nhu cầu mỗi ngày, theo khối
    need_rows = []
    for k in ("A", "B"):
        gg = blk[k]["gs"]
        if not gg:
            continue
        need_rows.append(f'<tr class="grp"><td colspan="5">{k}. {e(KHOI[k][0])}</td></tr>')
        for g in gg:
            left = max(g["kh"] - g["gn"] - g["du"], 0)
            wd = workdays(tomorrow, g["due"])
            need_rows.append(f'<tr><td><b>{e(g["ma"])}.</b> {e(g["short"])}</td><td class="num">{ty(left, False)}</td><td class="num">{g["due"]:%d/%m/%Y}</td><td class="num">{wd}</td><td class="num strong">{ty(left/wd if wd else left, False)}</td></tr>')
        need_rows.append(f'<tr class="sub"><td>Cộng khối {k}</td><td class="num">{ty(blk[k]["left"], False)}</td><td></td><td></td><td class="num">{ty(blk[k]["per"], False)}</td></tr>')

    # nguồn vốn, theo khối
    src = []
    for k in ("A", "B"):
        src.append(f'<h3 class="khoi-h"><span class="khoi-tag">{k}</span>{e(KHOI[k][0])}<small>{e(KHOI[k][1])}</small></h3>')
        last_sub = None
        for g in blk[k]["gs"]:
            if g["sub"] and g["sub"] != last_sub:
                x = subs[g["sub"]]
                src.append(f'<p class="sub-h">{e(SUB_B[g["sub"]])}<span>{pct(x["tl"])} · {ty(x["gn"])} / {ty(x["kh"])}</span></p>')
                last_sub = g["sub"]
            n = sum(1 for p in projects if p["nhom"] == g["nhom"])
            b = BADGE[g["xl"]]
            if g["chua_giao"]:
                val, mark = f"{ty(g['gn'])} / {ty(g['kh'])} · HĐND phường phân bổ ngày {g['giao']:%d/%m/%Y}, UBND phường chưa giao chi tiết", ""
            else:
                od = own_progress(today, g["giao"], g["due"])
                val = f"{ty(g['gn'])} / {ty(g['kh'])} · giao từ ngày {g['giao']:%d/%m/%Y}, hạn {g['due']:%d/%m/%Y}"
                if g["du"]:
                    val += f"; {vi(g['du'])} đồng vốn dư sau quyết toán đã đề nghị điều chỉnh giảm, không tính vào số còn phải giải ngân"
                mark = f'<em style="left:calc({od*100:.2f}% - 1px)" title="Tiến độ thời gian từ ngày giao {pct(od)}"></em>'
            src.append(f'''<div class="src">
  <div class="src-top"><span class="src-name"><span class="src-no">{e(g["ma"])}</span>{e(g["long"])}</span><span class="src-right"><span class="badge badge-{b}">{e(g["xl"])}</span><span class="src-pct">{pct(g["tl"])}</span></span></div>
  <div class="bar" role="img" aria-label="{e(g['long'])}: {pct(g['tl'])}"><i class="{FILL[b]}" style="width:{min(100, g['tl']*100):.2f}%"></i>{mark}</div>
  <p class="src-meta">{e(val)} · {n} dự án · {e(g["basis"])}</p>
</div>''')

    # thẻ dự án
    tiles = []
    gmap = {g["nhom"]: g for g in groups}
    for p in projects:
        g = gmap[p["nhom"]]
        b = BADGE[p["xl"]]
        od = own_progress(today, p["giao"], p["due"])
        mark = "" if p["chua_giao"] or p["done"] else f'<em style="left:calc({od*100:.2f}% - 1px)"></em>'
        big = pct(p["tl"])
        tiles.append(f'''<details class="tile tile-{b}" data-khoi="{p["khoi"]}" data-nhom="{e(p["nhom"])}" data-xl="{e(p["xl"])}">
  <summary>
    <span class="tile-top"><span class="tile-grp">{e(g["ma"])} · {e(g["short"])}</span><span class="badge badge-{b}">{e(p["xl"])}</span></span>
    <span class="tile-name">{e(p["du_an"])}</span>
    <span class="tile-big">{e(big)}</span>
    <span class="bar bar-sm"><i class="{FILL[b]}" style="width:{min(100,p['tl']*100):.2f}%"></i>{mark}</span>
  </summary>
  <dl class="tile-dl"><div><dt>Kế hoạch vốn</dt><dd>{vi(p["kh"])} đ</dd></div><div><dt>Đã giải ngân</dt><dd>{vi(p["gn"])} đ</dd></div><div><dt>{"Vốn dư đề nghị giảm" if p["du"] else "Còn lại"}</dt><dd>{vi(p["kh"]-p["gn"])} đ</dd></div><div><dt>{"Ngày phân bổ" if p["chua_giao"] else "Ngày giao vốn"}</dt><dd>{p["giao"]:%d/%m/%Y}</dd></div><div><dt>Hạn giải ngân</dt><dd>{p["due"]:%d/%m/%Y}</dd></div><div><dt>Tiến độ thời gian</dt><dd>{"" if p["chua_giao"] else pct(od)}</dd></div>{('<div class="wide"><dt>Tình hình thực hiện</dt><dd>' + e(p["note"]) + '</dd></div>') if p.get("note") else ''}</dl>
</details>''')

    chips_khoi = "".join(f'<button type="button" class="chip" data-f="khoi" data-v="{k}">{k}. {e(KHOI[k][0])}</button>' for k in ("A", "B"))
    chips_nhom = "".join(f'<button type="button" class="chip" data-f="nhom" data-v="{e(g["nhom"])}">{e(g["ma"])}. {e(g["short"])}</button>' for g in groups)
    chips_xl = "".join(f'<button type="button" class="chip" data-f="xl" data-v="{k}">{k} · {cnt[k]}</button>' for k in BADGE if cnt[k])

    body_rows = []
    for k in ("A", "B"):
        body_rows.append(f'<tr class="khoi"><td colspan="6">{k}. {e(KHOI[k][0]).upper()}</td></tr>')
        last_sub = None
        for g in blk[k]["gs"]:
            if g["sub"] and g["sub"] != last_sub:
                if last_sub:
                    x = subs[last_sub]
                    body_rows.append(f'<tr class="sub"><td></td><td>Cộng {e(SUB_B[last_sub].lower())}</td><td class="num">{vi(x["kh"])}</td><td class="num">{vi(x["gn"])}</td><td class="num">{pct(x["tl"])}</td><td></td></tr>')
                body_rows.append(f'<tr class="grp2"><td colspan="6">{e(SUB_B[g["sub"]])}</td></tr>')
                last_sub = g["sub"]
            body_rows.append(f'<tr class="grp"><td colspan="6">{e(g["ma"])}. {e(g["long"])}</td></tr>')
            for p in [p for p in projects if p["nhom"] == g["nhom"]]:
                body_rows.append(f'<tr><td class="center">{p["stt"]}</td><td>{e(p["du_an"])}</td><td class="num">{vi(p["kh"])}</td><td class="num">{vi(p["gn"])}</td><td class="num">{pct(p["tl"])}</td><td><span class="badge badge-{BADGE[p["xl"]]}">{e(p["xl"])}</span></td></tr>')
        if last_sub:
            x = subs[last_sub]
            body_rows.append(f'<tr class="sub"><td></td><td>Cộng {e(SUB_B[last_sub].lower())}</td><td class="num">{vi(x["kh"])}</td><td class="num">{vi(x["gn"])}</td><td class="num">{pct(x["tl"])}</td><td></td></tr>')
        body_rows.append(f'<tr class="sub"><td></td><td>Cộng khối {k}</td><td class="num">{vi(blk[k]["kh"])}</td><td class="num">{vi(blk[k]["gn"])}</td><td class="num">{pct(blk[k]["tl"])}</td><td></td></tr>')

    vals = dict(
        upd=upd, take=e(take), site=SITE_URL, ogv=today.strftime("%Y%m%d"),
        og_desc=e(f"Đến {upd}: đã giải ngân {ty(gn_now)}, đạt {pct(rate)} kế hoạch vốn năm 2026; vốn cấp trên giao đạt {pct(blk['A']['tl'])}; tiến độ thời gian {pct(tg)}."),
        pattern=HEADER_PATTERN,
        ring1=ring(rate, "ring-gn", "Tổng cộng đã giải ngân", pct(rate), f"{ty(gn_now)} / {ty(kh_all)}", tg),
        ring_a=ring(blk["A"]["tl"], "ring-a", "A. Vốn cấp trên giao", pct(blk["A"]["tl"]), f"{ty(blk['A']['gn'])} / {ty(blk['A']['kh'])}", tg),
        ring_b=ring(blk["B"]["tl"], "ring-b", "B. Vốn HĐND phường giao", pct(blk["B"]["tl"]), f"{ty(blk['B']['gn'])} / {ty(blk['B']['kh'])}", tg),
        ring2=ring(tg, "ring-time", "Tiến độ thời gian", pct(tg), f"Còn {max(0,(DUE_2026-today).days)} ngày đến 31/01/2027", small=True),
        kh_ref=ty(kh_ref), tg_pct=pct(tg), k_kh=ty(kh_all), k_chua=ty(kh_chua), k_n=len(projects), k_ng=len(projects) - t["n_chua"],
        k_gn=ty(gn_now), k_left=ty(tot_left), khoi_cards=khoi_cards, urgent_days=URGENT_DAYS,
        w_lbl=e(wk["label"]), w_in=ty(wk["in"]), w_delta=e(delta),
        m_lbl=e(mo["label"]), m_in=ty(mo["in"]), m_prev=e(f'Tháng trước {ty(months[-2]["in"])}' if len(months) > 1 else ""),
        q_lbl=e(qu["label"]), q_in=ty(qu["in"]), q_prev=e(f'Quý trước {ty(quarters[-2]["in"])}' if len(quarters) > 1 else ""),
        y_in=ty(gn_now), y_pct=pct(rate),
        cnt_dat=cnt["Đạt tiến độ"], cnt_cham=cnt["Chậm tiến độ"], cnt_cb=cnt["Cấp bách"], cnt_chua=cnt["Chờ UBND giao chi tiết"], cnt_qt=cnt["Đã quyết toán"], b_cut="30/9/2026",
        trend=trend_svg(daily, today, kh_ref, {g["nhom"] for g in g_due26}),
        bars_w=bars_svg(weeks, "Giải ngân theo tuần"), bars_m=bars_svg(months, "Giải ngân theo tháng"), bars_q=bars_svg(quarters, "Giải ngân theo quý"),
        tab_w=period_table(weeks), tab_m=period_table(months), tab_q=period_table(quarters),
        need_rows="\n".join(need_rows), need_left=ty(tot_left, False), need_per=ty(per_day, False), per_day_num=ty(per_day, False),
        sources="\n".join(src), tiles="\n".join(tiles), chips_khoi=chips_khoi, chips_nhom=chips_nhom, chips_xl=chips_xl,
        rows="\n".join(body_rows), f_kh=vi(t["kh"]), f_gn=vi(t["gn"]), f_tl=pct(t["gn"] / t["kh"] if t["kh"] else 0),
    )
    out = (ROOT / "template.html").read_text(encoding="utf-8")
    for k, v in vals.items():
        out = out.replace("%%" + k + "%%", str(v))
    if "%%" in out:
        print("Mẫu trang còn chỗ chưa điền", file=sys.stderr)
        sys.exit(3)
    return out, {"upd": upd, "rate": rate, "tg": tg, "gn": gn_now, "kh": kh_all, "wk": wk["in"], "per_day": per_day}


# ---------- ảnh xem trước khi chia sẻ ----------
def font(size, bold=True):
    from PIL import ImageFont
    cands = [os.environ.get("OG_FONT", ""), str(ROOT / "fonts/Montserrat.ttf"),
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
    for c in cands:
        if c and pathlib.Path(c).exists():
            f = ImageFont.truetype(c, size)
            try:
                f.set_variation_by_name("Bold" if bold else "Medium")
            except Exception:
                pass
            return f
    return ImageFont.load_default()


def make_og(s):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Không có Pillow, bỏ qua ảnh xem trước")
        return
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), (246, 250, 252))
    d = ImageDraw.Draw(im)
    for yy in range(H):  # nền sáng chuyển sắc nhẹ
        t = yy / H
        d.line([(0, yy), (W, yy)], fill=tuple(int(a + (b - a) * t) for a, b in zip((251, 253, 254), (236, 245, 240))))
    for i, off in enumerate((0, 60, 120)):
        d.line([(20 + off, H), (230, 360 + off), (440 - off, H)], fill=(226, 200, 184), width=3)
    for k in range(3):
        d.arc([760 + k * 90, 140 + k * 60, 1300 + k * 90, 800 + k * 60], 180, 270, fill=(170, 222, 228), width=4)
    ink, muted, teal = (59, 42, 32), (107, 86, 72), (31, 142, 160)
    ep = ROOT / "emblem.webp"
    if ep.exists():
        em = Image.open(ep).convert("RGBA")
        em.thumbnail((230, 240))
        im.paste(em, (70, 50), em)
        x0 = 340
    else:
        logo = Image.open(ROOT / "logo.png").convert("RGBA")
        logo.thumbnail((270, 180))
        im.paste(logo, (60, 60), logo)
        x0 = 380
    d.text((x0, 70), "UBND PHƯỜNG TÂN LẬP", font=font(30), fill=(46, 158, 71))
    d.text((x0, 114), "Tình hình giải ngân", font=font(54), fill=ink)
    d.text((x0, 180), "vốn đầu tư năm 2026", font=font(54), fill=ink)
    d.text((60, 320), pct(s["rate"]), font=font(150), fill=ink)
    d.text((64, 490), f"đã giải ngân {ty(s['gn'])} / {ty(s['kh'])}", font=font(30, False), fill=muted)
    d.text((760, 350), "Tiến độ thời gian", font=font(30, False), fill=muted)
    d.text((760, 390), pct(s["tg"]), font=font(84), fill=(210, 65, 45))
    d.text((64, 540), f"Cập nhật ngày {s['upd']}", font=font(26, False), fill=teal)
    y = H - 14
    for x in range(W):
        if x < W // 2:
            c = tuple(int(a + (b - a) * x / (W / 2)) for a, b in zip((165, 121, 30), (250, 198, 8)))
        else:
            c = tuple(int(a + (b - a) * (x - W / 2) / (W / 2)) for a, b in zip((33, 110, 52), (59, 184, 68)))
        d.line([(x, y), (x, H)], fill=c)
    im.save(ROOT / "og.png", optimize=True)


def main():
    th = json.loads((ROOT / "tonghop.json").read_text(encoding="utf-8"))
    nq = json.loads((ROOT / "nq27.json").read_text(encoding="utf-8"))
    hp = ROOT / "history.json"
    hist = json.loads(hp.read_text(encoding="utf-8")) if hp.exists() else {"daily": {}}
    fetched = dt.datetime.fromisoformat(th["fetched_at"].replace("Z", "+00:00"))
    cp = ROOT / "cds_mtqg.json"
    cds = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else None
    groups, projects, t = model(th, nq, cds, fetched.astimezone(TZ).date())
    hist = update_history(hist, groups, fetched.astimezone(TZ).date())
    hp.write_text(json.dumps(hist, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    out, summary = render(groups, projects, t, hist, fetched)
    (ROOT / "index.html").write_text(out, encoding="utf-8")
    make_og(summary)
    print(f"OK: {len(projects)} dự án, kế hoạch {t['kh']:,.0f}, giải ngân {t['gn']:,.0f}, cập nhật {summary['upd']}")


if __name__ == "__main__":
    main()
