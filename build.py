#!/usr/bin/env python3
"""Dựng trang công khai tình hình giải ngân, UBND phường Tân Lập.

Đầu vào:  tonghop.json  (tab 'Tổng hợp' của bảng theo dõi, giữ nguyên các ô)
          nq27.json     (Biểu 02 kèm Nghị quyết số 27/NQ-HĐND)
          history.json  (giải ngân lũy kế theo ngày và nhóm nguồn vốn; tự ghi thêm mỗi lần chạy)
Đầu ra:   index.html, og.png (ảnh xem trước khi chia sẻ link), history.json
Dừng với mã lỗi khác 0 nếu số liệu không khớp (tổng nhóm, tổng cộng), để không đăng số sai.
"""
import json, sys, html, datetime as dt, pathlib, math, os, unicodedata

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


LABEL = [
    ("kéo dài", "Kế hoạch vốn năm 2025 kéo dài sang năm 2026", "Vốn 2025 kéo dài", "Quyết định số 1199/QĐ-UBND ngày 14/4/2026", dt.date(2026, 12, 31)),
    ("02558", "Kế hoạch vốn năm 2026 giao mới", "KH 2026 giao mới", "Quyết định số 02558/QĐ-UBND ngày 31/12/2025", DUE_2026),
    ("1133", "Kế hoạch vốn đầu tư công năm 2026, ngân sách phường", "Ngân sách phường", "Quyết định số 1133/QĐ-UBND ngày 17/6/2026 và số 1474/QĐ-UBND ngày 26/8/2026", DUE_2026),
    ("2347", "Kế hoạch vốn chi đầu tư phát triển khác, ngân sách tỉnh bổ sung có mục tiêu", "Ngân sách tỉnh bổ sung", "Quyết định số 2347/QĐ-UBND của UBND tỉnh; UBND phường giao đợt 1 tại Quyết định số 1385/QĐ-UBND", DUE_2026),
    ("CĐS", "Vốn chuyển đổi số, ngân sách tỉnh bổ sung có mục tiêu", "Chuyển đổi số", "Quyết định số 3164/QĐ-UBND ngày 30/9/2026 và số 3392/QĐ-UBND ngày 22/10/2026 của UBND tỉnh", DUE_2026),
    ("MTQG", "Vốn Chương trình mục tiêu quốc gia năm 2026 và vốn đối ứng ngân sách phường", "CT mục tiêu quốc gia", "Nghị quyết số 31/NQ-HĐND ngày 10/11/2026 của HĐND phường", DUE_2026),
    ("27/NQ", "Bổ sung kế hoạch vốn năm 2026 (tiền sử dụng đất)", "Bổ sung NQ 27", "Nghị quyết số 27/NQ-HĐND ngày 06/10/2026 của HĐND phường", dt.date(2027, 12, 31)),
]


def label(nguon):
    for key, long, short, basis, due in LABEL:
        if key in nguon:
            return long, short, basis, due
    return nguon, nguon[:24], "", DUE_2026


# Kế hoạch vốn năm 2026 của 02 dự án nhà văn hóa cộng đồng theo Biểu 02 kèm theo Nghị quyết số 31/NQ-HĐND
# ngày 10/11/2026 của HĐND phường (bảng theo dõi ghi tổng mức đầu tư ở cột số vốn giao). Tên dự án theo Nghị quyết.
NQ31_MTQG = [
    (("mliâo", "mlâo"), "Cải tạo, sửa chữa Nhà văn hóa cộng đồng buôn Kõ Mliâo", 1_127e6,
     "Quyết định số 1999/QĐ-UBND ngày 04/11/2026"),
    (("cuôr",), "Cải tạo, sửa chữa Nhà văn hóa cộng đồng buôn Ea Cuôr Kap", 672e6,
     "Quyết định số 2000/QĐ-UBND ngày 04/11/2026"),
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


def model(th, nq, cds=None):
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
                                 "note": r["note"], "basis_p": r["basis"]})
    giao = [p for p in projects if not p["chua_giao"]]
    kh_g, gn_g = sum(p["kh"] for p in giao), sum(p["gn"] for p in giao)
    chung = gn_g / kh_g if kh_g else 0
    for p in projects:
        p["tl"] = p["gn"] / p["kh"] if p["kh"] else 0
        p["xl"] = "Chờ giao chi tiết" if p["chua_giao"] else ("Tốt" if p["tl"] > 0.7 else "Trung bình" if p["tl"] >= chung else "Chậm")
    for g in keep:
        g["tl"] = g["gn"] / g["kh"] if g["kh"] else 0
        g["long"], g["short"], g["basis"], g["due"] = label(g["nguon"])
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


BADGE = {"Tốt": "ok", "Trung bình": "warn", "Chậm": "late", "Chờ giao chi tiết": "neutral"}


# ---------- hình vẽ ----------
def ring(frac, cls, label, value, sub):
    r, c = 52, 2 * math.pi * 52
    return f'''<figure class="ring">
  <svg viewBox="0 0 128 128" role="img" aria-label="{e(label)}: {e(value)}">
    <circle cx="64" cy="64" r="{r}" class="ring-track"/>
    <circle cx="64" cy="64" r="{r}" class="ring-val {cls}" stroke-dasharray="{c*min(frac,1):.1f} {c:.1f}" transform="rotate(-90 64 64)"/>
    <text x="64" y="70" text-anchor="middle" class="ring-num">{e(value)}</text>
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
               f'<text x="{L+6}" y="{Y(kh_ref)-6:.1f}" class="tick">Kế hoạch vốn đã giao {ty(kh_ref)}</text>')
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
        short = p["label"].split(" (")[0].replace("Tháng ", "T").replace("Tuần ", "Tuần ")
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


HEADER_PATTERN = '''<svg class="hero-pattern" viewBox="0 0 1200 420" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
<g fill="none" stroke="currentColor" stroke-width="1.4">
<polyline points="40,420 250,210 460,420"/><polyline points="90,420 250,260 410,420"/><polyline points="140,420 250,310 360,420"/>
<line x1="225" y1="185" x2="275" y2="235"/><line x1="275" y1="185" x2="225" y2="235"/>
<rect x="150" y="360" width="200" height="60"/><line x1="190" y1="360" x2="190" y2="420"/><line x1="230" y1="360" x2="230" y2="420"/><line x1="270" y1="360" x2="270" y2="420"/><line x1="310" y1="360" x2="310" y2="420"/>
<path d="M700 420 C700 330 760 300 820 260 S 900 180 900 110"/><circle cx="900" cy="100" r="10"/>
<path d="M760 420 C760 350 820 320 880 280 S 980 210 1010 150"/><circle cx="1016" cy="140" r="10"/>
<path d="M830 420 C840 370 900 340 960 310 S 1080 260 1110 210"/><circle cx="1118" cy="200" r="10"/>
<path d="M640 0 C660 60 720 80 780 90"/><circle cx="790" cy="92" r="8"/>
<path d="M1040 0 C1040 40 1080 70 1140 80"/><circle cx="1150" cy="82" r="8"/>
</g></svg>'''


def render(groups, projects, t, hist, fetched):
    today = fetched.astimezone(TZ).date()
    upd = today.strftime("%d/%m/%Y")
    daily = hist["daily"]
    g26 = [g for g in groups if not g["chua_giao"]]
    nhoms = {g["nhom"] for g in g26}
    kh_ref = sum(g["kh"] for g in g26)
    gn_now = sum(g["gn"] for g in g26)
    tg = progress(today, DUE_2026)
    rate = gn_now / kh_ref if kh_ref else 0
    cnt = {k: sum(1 for p in projects if p["xl"] == k) for k in BADGE}
    weeks, months, quarters = periods(daily, today, kh_ref)
    wk, mo, qu = weeks[-1], months[-1], quarters[-1]
    prev_wk = weeks[-2] if len(weeks) > 1 else None
    biggest = max(g26, key=lambda g: g["kh"] - g["gn"])

    # nhu cầu mỗi ngày
    need_rows, tot_left = [], 0.0
    tomorrow = today + dt.timedelta(days=1)
    for g in g26:
        left = max(g["kh"] - g["gn"], 0)
        wd = workdays(tomorrow, g["due"])
        tot_left += left
        need_rows.append(f'<tr><td><b>{e(g["nhom"])}.</b> {e(g["short"])}</td><td class="num">{ty(left, False)}</td><td class="num">{g["due"]:%d/%m/%Y}</td><td class="num">{wd}</td><td class="num strong">{ty(left/wd if wd else left, False)}</td></tr>')
    wd_all = workdays(tomorrow, DUE_2026)
    per_day = 0.0
    for g in g26:
        wd = workdays(tomorrow, g["due"])
        per_day += max(g["kh"] - g["gn"], 0) / (wd or 1)

    take = (f"Đến ngày {upd}, phường đã giải ngân {ty(gn_now)}, đạt {pct(rate)} kế hoạch vốn đã giao chi tiết "
            f"({ty(kh_ref)}), trong khi tiến độ thời gian đã qua {pct(tg)}. "
            f"Tuần này giải ngân thêm {ty(wk['in'])}, từ đầu tháng {today.month} là {ty(mo['in'])}. "
            f"Để giải ngân hết kế hoạch đúng hạn, bình quân mỗi ngày làm việc cần giải ngân khoảng {ty(per_day)}; "
            f"nguồn còn lại nhiều nhất là {biggest['long'].lower()} (còn {ty(biggest['kh']-biggest['gn'])}).")
    if t["n_chua"]:
        take += f" {t['n_chua']} dự án bổ sung theo Nghị quyết số 27/NQ-HĐND ({ty(t['kh_chua'])}) đang hoàn thiện thủ tục để giao chi tiết kế hoạch vốn."

    delta = ""
    if prev_wk is not None:
        delta = f'Tuần trước {ty(prev_wk["in"])}'

    # nguồn vốn
    src = []
    for g in groups:
        tdg = progress(today, g["due"])
        n = sum(1 for p in projects if p["nhom"] == g["nhom"])
        if g["chua_giao"]:
            val, fill, mark = f"{ty(g['kh'])} · chờ giao chi tiết", "fill-neutral", ""
        else:
            val = f"{ty(g['gn'])} / {ty(g['kh'])}"
            fill = "fill-ok" if g["tl"] >= tdg else "fill-warn"
            mark = f'<em style="left:calc({tdg*100:.2f}% - 1px)" title="Tiến độ thời gian {pct(tdg)}"></em>'
        src.append(f'''<div class="src">
  <div class="src-top"><span class="src-name"><span class="src-no">{e(g["nhom"])}</span>{e(g["long"])}</span><span class="src-pct">{"" if g["chua_giao"] else pct(g["tl"])}</span></div>
  <div class="bar" role="img" aria-label="{e(g['long'])}: {pct(g['tl'])}"><i class="{fill}" style="width:{min(100, g['tl']*100):.2f}%"></i>{mark}</div>
  <p class="src-meta">{e(val)} · {n} dự án · {e(g["basis"])}</p>
</div>''')

    # thẻ dự án
    tiles = []
    gmap = {g["nhom"]: g for g in groups}
    for p in projects:
        g = gmap[p["nhom"]]
        tdg = progress(today, g["due"])
        mark = "" if p["chua_giao"] else f'<em style="left:calc({tdg*100:.2f}% - 1px)"></em>'
        fill = {"Tốt": "fill-ok", "Trung bình": "fill-warn", "Chậm": "fill-late", "Chờ giao chi tiết": "fill-neutral"}[p["xl"]]
        big = ty(p["kh"]) if p["chua_giao"] else pct(p["tl"])
        tiles.append(f'''<details class="tile tile-{BADGE[p["xl"]]}" data-nhom="{e(p["nhom"])}" data-xl="{e(p["xl"])}">
  <summary>
    <span class="tile-top"><span class="tile-grp">{e(g["nhom"])} · {e(g["short"])}</span><span class="badge badge-{BADGE[p["xl"]]}">{e(p["xl"])}</span></span>
    <span class="tile-name">{e(p["du_an"])}</span>
    <span class="tile-big">{e(big)}</span>
    <span class="bar bar-sm"><i class="{fill}" style="width:{min(100,p['tl']*100):.2f}%"></i>{mark}</span>
  </summary>
  <dl class="tile-dl"><div><dt>Kế hoạch vốn</dt><dd>{vi(p["kh"])} đ</dd></div><div><dt>Đã giải ngân</dt><dd>{vi(p["gn"])} đ</dd></div><div><dt>Còn lại</dt><dd>{vi(p["kh"]-p["gn"])} đ</dd></div><div><dt>Hạn giải ngân</dt><dd>{g["due"]:%d/%m/%Y}</dd></div>{('<div class="wide"><dt>Tình hình thực hiện</dt><dd>' + e(p["note"]) + '</dd></div>') if p.get("note") else ''}</dl>
</details>''')

    chips_nhom = "".join(f'<button type="button" class="chip" data-f="nhom" data-v="{e(g["nhom"])}">{e(g["nhom"])}. {e(g["short"])}</button>' for g in groups)
    chips_xl = "".join(f'<button type="button" class="chip" data-f="xl" data-v="{k}">{k} · {cnt[k]}</button>' for k in BADGE if cnt[k])

    body_rows = []
    for g in groups:
        body_rows.append(f'<tr class="grp"><td colspan="6">{e(g["nhom"])}. {e(g["long"])}</td></tr>')
        for p in [p for p in projects if p["nhom"] == g["nhom"]]:
            body_rows.append(f'<tr><td class="center">{p["stt"]}</td><td>{e(p["du_an"])}</td><td class="num">{vi(p["kh"])}</td><td class="num">{vi(p["gn"])}</td><td class="num">{pct(p["tl"])}</td><td><span class="badge badge-{BADGE[p["xl"]]}">{e(p["xl"])}</span></td></tr>')

    vals = dict(
        upd=upd, take=e(take), site=SITE_URL, ogv=today.strftime("%Y%m%d"),
        og_desc=e(f"Đến {upd}: đã giải ngân {ty(gn_now)}, đạt {pct(rate)} kế hoạch vốn đã giao; tiến độ thời gian {pct(tg)}."),
        pattern=HEADER_PATTERN,
        ring1=ring(rate, "ring-gn", "Đã giải ngân", pct(rate), f"{ty(gn_now)} / {ty(kh_ref)}"),
        ring2=ring(tg, "ring-time", "Tiến độ thời gian", pct(tg), f"Còn {max(0,(DUE_2026-today).days)} ngày đến 31/01/2027"),
        kh_ref=ty(kh_ref), k_kh=ty(t["kh"]), k_n=len(projects), k_ng=len(projects) - t["n_chua"],
        k_gn=ty(gn_now), k_left=ty(tot_left),
        w_lbl=e(wk["label"]), w_in=ty(wk["in"]), w_delta=e(delta),
        m_lbl=e(mo["label"]), m_in=ty(mo["in"]), m_prev=e(f'Tháng trước {ty(months[-2]["in"])}' if len(months) > 1 else ""),
        q_lbl=e(qu["label"]), q_in=ty(qu["in"]), q_prev=e(f'Quý trước {ty(quarters[-2]["in"])}' if len(quarters) > 1 else ""),
        y_in=ty(gn_now), y_pct=pct(rate),
        cnt_tot=cnt["Tốt"], cnt_tb=cnt["Trung bình"], cnt_cham=cnt["Chậm"], cnt_chua=cnt["Chờ giao chi tiết"],
        trend=trend_svg(daily, today, kh_ref, nhoms),
        bars_w=bars_svg(weeks, "Giải ngân theo tuần"), bars_m=bars_svg(months, "Giải ngân theo tháng"), bars_q=bars_svg(quarters, "Giải ngân theo quý"),
        tab_w=period_table(weeks), tab_m=period_table(months), tab_q=period_table(quarters),
        need_rows="\n".join(need_rows), need_left=ty(tot_left, False), need_per=ty(per_day, False), per_day_num=ty(per_day, False),
        sources="\n".join(src), tiles="\n".join(tiles), chips_nhom=chips_nhom, chips_xl=chips_xl,
        rows="\n".join(body_rows), f_kh=vi(t["kh"]), f_gn=vi(t["gn"]), f_tl=pct(t["gn"] / t["kh"] if t["kh"] else 0),
    )
    out = (ROOT / "template.html").read_text(encoding="utf-8")
    for k, v in vals.items():
        out = out.replace("%%" + k + "%%", str(v))
    if "%%" in out:
        print("Mẫu trang còn chỗ chưa điền", file=sys.stderr)
        sys.exit(3)
    return out, {"upd": upd, "rate": rate, "tg": tg, "gn": gn_now, "kh": kh_ref, "wk": wk["in"], "per_day": per_day}


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
    im = Image.new("RGB", (W, H), "#331517")
    d = ImageDraw.Draw(im)
    gold = (226, 210, 151)
    for i, off in enumerate((0, 70, 140)):
        d.line([(40 + off, H), (300, 330 + off), (560 - off, H)], fill=(78, 44, 40), width=3)
    for k in range(3):
        d.arc([760 + k * 90, 120 + k * 60, 1300 + k * 90, 780 + k * 60], 180, 270, fill=(78, 44, 40), width=3)
    plate = Image.new("RGB", (300, 200), "white")
    logo = Image.open(ROOT / "logo.png").convert("RGBA")
    logo.thumbnail((270, 180))
    plate.paste(logo, ((300 - logo.width) // 2, (200 - logo.height) // 2), logo)
    mask = Image.new("L", plate.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 299, 199], 18, fill=255)
    im.paste(plate, (60, 60), mask)
    d.text((400, 78), "UBND PHƯỜNG TÂN LẬP", font=font(30), fill=(93, 183, 94))
    d.text((400, 122), "Tình hình giải ngân", font=font(52), fill=(234, 225, 226))
    d.text((400, 186), "vốn đầu tư năm 2026", font=font(52), fill=(234, 225, 226))
    d.text((60, 320), pct(s["rate"]), font=font(150), fill=(234, 225, 226))
    d.text((64, 490), f"đã giải ngân {ty(s['gn'])} / {ty(s['kh'])}", font=font(30, False), fill=gold)
    d.text((760, 350), "Tiến độ thời gian", font=font(30, False), fill=gold)
    d.text((760, 390), pct(s["tg"]), font=font(84), fill=(234, 225, 226))
    d.text((64, 540), f"Cập nhật ngày {s['upd']}", font=font(26, False), fill=(205, 186, 182))
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
    groups, projects, t = model(th, nq, cds)
    hist = update_history(hist, groups, fetched.astimezone(TZ).date())
    hp.write_text(json.dumps(hist, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    out, summary = render(groups, projects, t, hist, fetched)
    (ROOT / "index.html").write_text(out, encoding="utf-8")
    make_og(summary)
    print(f"OK: {len(projects)} dự án, kế hoạch {t['kh']:,.0f}, giải ngân {t['gn']:,.0f}, cập nhật {summary['upd']}")


if __name__ == "__main__":
    main()
