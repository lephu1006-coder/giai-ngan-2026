#!/usr/bin/env python3
"""Dựng trang công khai tình hình giải ngân từ dữ liệu bảng Tổng hợp.

Đầu vào:  tonghop.json  (kết quả get_values của tab 'Tổng hợp', giữ nguyên)
          nq27.json     (Biểu 02 kèm Nghị quyết số 27/NQ-HĐND)
Đầu ra:   index.html
Dừng với mã lỗi khác 0 nếu số liệu không khớp (tổng nhóm, tổng cộng), để không đăng số sai.
"""
import json, sys, html, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
TZ = datetime.timezone(datetime.timedelta(hours=7))


def num(s):
    t = str(s or "").replace(".", "").replace(",", ".").strip()
    try:
        return float(t) if t else 0.0
    except ValueError:
        return 0.0


def load():
    th = json.loads((ROOT / "tonghop.json").read_text(encoding="utf-8"))
    nq = json.loads((ROOT / "nq27.json").read_text(encoding="utf-8"))
    return th, nq


def parse(values):
    groups, rows, total = [], [], None
    g = None
    for v in values:
        v = list(v) + [""] * 6
        tt = str(v[0]).strip()
        name = str(v[1]).strip()
        if not tt and name.upper().startswith("TỔNG CỘNG"):
            total = (num(v[3]), num(v[4]))
            continue
        if tt and all(c in "IVXLC" for c in tt):
            g = {"nhom": tt, "nguon": name, "kh": num(v[3]), "gn": num(v[4]), "co_von": str(v[3]).strip() != ""}
            groups.append(g)
            continue
        if g and tt.isdigit() and name:
            rows.append({"nhom": g["nhom"], "stt": int(tt), "du_an": name, "kh": num(v[3]), "gn": num(v[4]),
                         "co_von": str(v[3]).strip() != ""})
    return groups, rows, total


def validate(groups, rows, total):
    errs = []
    for g in groups:
        rs = [r for r in rows if r["nhom"] == g["nhom"]]
        if not g["co_von"]:
            continue
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
    ("kéo dài", "Kế hoạch vốn năm 2025 kéo dài sang năm 2026", "Quyết định số 1199/QĐ-UBND ngày 14/4/2026", (2026, 12, 31)),
    ("02558", "Kế hoạch vốn năm 2026 giao mới", "Quyết định số 02558/QĐ-UBND ngày 31/12/2025", (2027, 1, 31)),
    ("1133", "Kế hoạch vốn đầu tư công năm 2026, ngân sách phường", "Quyết định số 1133/QĐ-UBND ngày 17/6/2026 và số 1474/QĐ-UBND ngày 26/8/2026", (2027, 1, 31)),
    ("2347", "Kế hoạch vốn chi đầu tư phát triển khác, ngân sách tỉnh bổ sung có mục tiêu", "Quyết định số 2347/QĐ-UBND của UBND tỉnh; UBND phường giao đợt 1 tại Quyết định số 1385/QĐ-UBND", (2027, 1, 31)),
    ("27/NQ", "Bổ sung kế hoạch vốn năm 2026 (tiền sử dụng đất)", "Nghị quyết số 27/NQ-HĐND ngày 06/10/2026 của HĐND phường", (2027, 12, 31)),
]


def label(nguon):
    for key, short, basis, due in LABEL:
        if key in nguon:
            return short, basis, datetime.date(*due)
    return nguon, "", datetime.date(2027, 1, 31)


def model(th, nq):
    groups, rows, total = parse(th["values"])
    errs = validate(groups, rows, total)
    if errs:
        print("SỐ LIỆU KHÔNG KHỚP, KHÔNG DỰNG TRANG:\n- " + "\n- ".join(errs), file=sys.stderr)
        sys.exit(2)
    empty = [g for g in groups if not g["co_von"]]
    keep_groups = [g for g in groups if g["co_von"]]
    projects = [dict(r, chua_giao=False) for r in rows if any(g["nhom"] == r["nhom"] for g in keep_groups)]
    nq_nhom = empty[0]["nhom"] if empty else "V"
    sheet_has_nq = any(("27/NQ" in g["nguon"] or "10 dự án mới" in g["nguon"]) and g["co_von"] for g in groups)
    nq_nguon = "Bổ sung kế hoạch vốn năm 2026 theo 27/NQ-HĐND"
    if not sheet_has_nq:
        keep_groups.append({"nhom": nq_nhom, "nguon": nq_nguon, "kh": sum(float(x["ke_hoach"]) for x in nq),
                            "gn": sum(float(x["da_giai_ngan"]) for x in nq), "co_von": True, "chua_giao": True})
        for x in nq:
            projects.append({"nhom": nq_nhom, "stt": int(x["stt"]), "du_an": x["du_an"], "kh": float(x["ke_hoach"]),
                             "gn": float(x["da_giai_ngan"]), "chua_giao": True})
    giao = [p for p in projects if not p["chua_giao"]]
    kh_g, gn_g = sum(p["kh"] for p in giao), sum(p["gn"] for p in giao)
    chung = gn_g / kh_g if kh_g else 0
    for p in projects:
        p["tl"] = p["gn"] / p["kh"] if p["kh"] else 0
        p["xl"] = "Chờ giao chi tiết" if p["chua_giao"] else ("Tốt" if p["tl"] > 0.7 else "Trung bình" if p["tl"] >= chung else "Chậm")
    for g in keep_groups:
        g.setdefault("chua_giao", False)
        g["tl"] = g["gn"] / g["kh"] if g["kh"] else 0
        g["short"], g["basis"], g["due"] = label(g["nguon"])
    return keep_groups, projects, {"kh": sum(p["kh"] for p in projects), "gn": sum(p["gn"] for p in projects),
                                   "kh_g": kh_g, "gn_g": gn_g, "chung": chung,
                                   "kh_chua": sum(p["kh"] for p in projects if p["chua_giao"]),
                                   "n_chua": sum(1 for p in projects if p["chua_giao"])}


def vi(x, d=0):
    s = f"{x:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def ty(x):
    return vi(x / 1e9, 1 if x >= 1e11 else 2) + " tỷ đồng"


def pct(x):
    return vi(x * 100, 1) + "%"


def progress(today, due):
    start = datetime.date(2026, 1, 1)
    return max(0.0, min(1.0, (today - start).days / (due - start).days))


BADGE = {"Tốt": "ok", "Trung bình": "warn", "Chậm": "late", "Chờ giao chi tiết": "neutral"}


def render(groups, projects, t, fetched):
    e = html.escape
    today = fetched.astimezone(TZ).date()
    tg = progress(today, datetime.date(2027, 1, 31))
    cnt = {k: sum(1 for p in projects if p["xl"] == k) for k in BADGE}
    biggest = max((g for g in groups if not g["chua_giao"]), key=lambda g: g["kh"] - g["gn"])
    upd = fetched.astimezone(TZ).strftime("%d/%m/%Y")

    src_rows = []
    for g in groups:
        tdg = progress(today, g["due"])
        fill = "fill-neutral" if g["chua_giao"] else ("fill-ok" if g["tl"] >= tdg else "fill-warn")
        val = (ty(g["kh"]) + " · chờ giao chi tiết") if g["chua_giao"] else f"{ty(g['gn'])} / {ty(g['kh'])} · {pct(g['tl'])}"
        mark = "" if g["chua_giao"] else f'<em style="left:calc({tdg*100:.2f}% - 1px)" title="Tiến độ thời gian {pct(tdg)}"></em>'
        n = sum(1 for p in projects if p["nhom"] == g["nhom"])
        src_rows.append(f'''<div class="src">
  <div class="src-top"><span class="src-name">{e(g["nhom"])}. {e(g["short"])} · {n} dự án</span><span class="src-val">{e(val)}</span></div>
  <div class="bar" role="img" aria-label="{e(g['short'])}: {pct(g['tl'])}"><i class="{fill}" style="width:{min(100, g['tl']*100):.2f}%"></i>{mark}</div>
  <p class="src-basis">{e(g["basis"])}</p>
</div>''')

    body_rows = []
    for g in groups:
        body_rows.append(f'<tr class="grp"><td colspan="6">{e(g["nhom"])}. {e(g["short"])}</td></tr>')
        for p in [p for p in projects if p["nhom"] == g["nhom"]]:
            body_rows.append(f'''<tr><td class="center">{p["stt"]}</td><td>{e(p["du_an"])}</td><td class="num">{vi(p["kh"])}</td><td class="num">{vi(p["gn"])}</td><td class="num">{pct(p["tl"])}</td><td><span class="badge badge-{BADGE[p["xl"]]}">{e(p["xl"])}</span></td></tr>''')

    take = (f"Đến ngày {upd}, phường đã giải ngân {ty(t['gn'])}, đạt {pct(t['gn_g']/t['kh_g'] if t['kh_g'] else 0)} "
            f"trên {ty(t['kh_g'])} vốn đã giao chi tiết; tiến độ thời gian của kế hoạch năm 2026 là {pct(tg)}. "
            f"Có {cnt['Tốt']} dự án đạt tốt, {cnt['Trung bình']} trung bình, {cnt['Chậm']} chậm. "
            f"Nguồn còn phải giải ngân nhiều nhất là {biggest['short'].lower()} (còn {ty(biggest['kh']-biggest['gn'])}).")
    if t["n_chua"]:
        take += f" {t['n_chua']} dự án bổ sung theo Nghị quyết số 27/NQ-HĐND ({ty(t['kh_chua'])}) đang hoàn thiện thủ tục để giao chi tiết kế hoạch vốn."

    vals = dict(
        upd=upd, take=e(take),
        k_kh=ty(t["kh"]), k_n=len(projects), k_ng=len(projects) - t["n_chua"],
        k_gn=ty(t["gn"]), k_tl=pct(t["gn"] / t["kh"] if t["kh"] else 0),
        k_tlg=pct(t["gn_g"] / t["kh_g"] if t["kh_g"] else 0), k_khg=ty(t["kh_g"]),
        k_tg=pct(tg), k_left=max(0, (datetime.date(2027, 1, 31) - today).days),
        sources="\n".join(src_rows), rows="\n".join(body_rows),
        f_kh=vi(t["kh"]), f_gn=vi(t["gn"]), f_tl=pct(t["gn"] / t["kh"] if t["kh"] else 0),
        year=today.year,
    )
    out = TEMPLATE
    for k, v in vals.items():
        out = out.replace("%%" + k + "%%", str(v))
    if "%%" in out:
        print("Mẫu trang còn chỗ chưa điền", file=sys.stderr)
        sys.exit(3)
    return out


TEMPLATE = (ROOT / "template.html").read_text(encoding="utf-8") if (ROOT / "template.html").exists() else ""


def main():
    th, nq = load()
    fetched = datetime.datetime.fromisoformat(th["fetched_at"].replace("Z", "+00:00"))
    groups, projects, t = model(th, nq)
    out = render(groups, projects, t, fetched)
    (ROOT / "index.html").write_text(out, encoding="utf-8")
    print(f"OK: {len(projects)} dự án, kế hoạch {t['kh']:,.0f}, giải ngân {t['gn']:,.0f}, cập nhật {fetched.astimezone(TZ):%d/%m/%Y %H:%M}")


if __name__ == "__main__":
    main()
