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
    ("CĐS", "Vốn chuyển đổi số, ngân sách tỉnh bổ sung có mục tiêu", "Chuyển đổi số", "Quyết định số 3164/QĐ-UBND ngày 30/9/2026 và số 3392/QĐ-UBND ngày 22/10/2026 của UBND tỉnh; UBND phường giao chi tiết chuẩn bị đầu tư tại Quyết định số 2021/QĐ-UBND ngày 05/11/2026 và số 2057/QĐ-UBND ngày 11/11/2026", DUE_2026, "A", dt.date(2026, 9, 30)),
    ("MTQG", "Vốn Chương trình mục tiêu quốc gia năm 2026 và vốn đối ứng ngân sách phường", "CT mục tiêu quốc gia", "Nghị quyết số 31/NQ-HĐND ngày 10/11/2026 của HĐND phường", DUE_2026, "A", dt.date(2026, 11, 10)),
    ("27/NQ", "Bổ sung kế hoạch vốn năm 2026 (tiền sử dụng đất)", "Bổ sung NQ 27", "Nghị quyết số 27/NQ-HĐND ngày 06/10/2026 của HĐND phường; UBND phường giao chi tiết đợt 1 (chuẩn bị đầu tư) tại Quyết định số 1994/QĐ-UBND ngày 03/11/2026", dt.date(2027, 12, 31), "B", dt.date(2026, 10, 6)),
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
HD_2347 = 'Đã bàn giao mặt bằng, khởi công ngày 01/11/2026; theo hợp đồng thi công (sau thương thảo với nhà thầu), hoàn thành toàn bộ khối lượng trước ngày 23/12/2026. '
TIEN_DO = [
    ("kéo dài", "Mầm non Tân Hòa", 81_686_000,
     "Dự án hoàn thành, đã phê duyệt quyết toán tại Quyết định số 1348/QĐ-UBND ngày 07/8/2026 của UBND phường. "
     "Số vốn còn lại 81.686.000 đồng không còn nhu cầu giải ngân; UBND phường đã đề nghị điều chỉnh giảm tại "
     "Báo cáo số 663/BC-UBND ngày 27/10/2026 gửi Sở Tài chính, chờ UBND tỉnh quyết định."),
    ("kéo dài", "Cao Đạt", 0,
     "Đang vận động bàn giao phần mặt bằng còn lại, tháo gỡ vướng mắc đơn thư. Thời hạn giải ngân vốn năm 2025 kéo dài "
     "được điều chỉnh đến hết ngày 31/12/2026 tại Quyết định số 3598/QĐ-UBND ngày 09/11/2026 của UBND tỉnh."
     " Ngày 13/11/2026 UBND phường phê duyệt phương án bồi thường, hỗ trợ đợt 3 (Quyết định số 2060/QĐ-UBND) và điều chỉnh, bổ sung phương án bồi thường, hỗ trợ (Quyết định số 2066/QĐ-UBND)."),
    ("02558", "Cao Đạt", 0, "Đang vận động bàn giao phần mặt bằng còn lại, tháo gỡ vướng mắc đơn thư. Ngày 13/11/2026 UBND phường phê duyệt phương án bồi thường, hỗ trợ đợt 3 (Quyết định số 2060/QĐ-UBND) và điều chỉnh, bổ sung phương án bồi thường, hỗ trợ (Quyết định số 2066/QĐ-UBND)."),
    ("1133", "Nguyễn Du", 0, "Đang thi công; Phòng KT-HT&ĐT đôn đốc, giám sát nhà thầu đẩy nhanh tiến độ."),
    ("1133", "Nguyễn Văn Cừ", 0, "Đang thi công; Phòng KT-HT&ĐT đôn đốc, giám sát nhà thầu đẩy nhanh tiến độ."),
    ("1133", "Trạm Y tế", 0, "Đang thi công; Phòng KT-HT&ĐT đôn đốc, giám sát nhà thầu đẩy nhanh tiến độ."),
    ("1133", "hội trường", 0, "Đang thi công; Phòng KT-HT&ĐT đôn đốc, giám sát nhà thầu đẩy nhanh tiến độ."),
    ("1133", "D8 và N14", 0, "Dự án đã được phê duyệt tại Quyết định số 2037/QĐ-UBND ngày 06/11/2026 của UBND phường; chủ đầu tư triển khai các bước tiếp theo."),
    ("1133", "hạ tầng kỹ thuật trên địa bàn", 0, "Dự án đã được phê duyệt tại Quyết định số 1731/QĐ-UBND ngày 09/10/2026 của UBND phường; chủ đầu tư triển khai các bước tiếp theo."),
    ("27/NQ", "Má Hai", 0, "Ngày 26/10/2026 chủ đầu tư phê duyệt dự toán và kế hoạch lựa chọn nhà thầu."),
    ("27/NQ", "Nguyễn Đình Thi", 0, "Ngày 26/10/2026 chủ đầu tư phê duyệt dự toán và kế hoạch lựa chọn nhà thầu."),
    ("27/NQ", "Tăng Bạt Hổ", 0, "Ngày 26/10/2026 chủ đầu tư phê duyệt dự toán và kế hoạch lựa chọn nhà thầu."),
    ("27/NQ", "Phạm Văn Đồng", 0, "Ngày 26/10/2026 chủ đầu tư phê duyệt dự toán và kế hoạch lựa chọn nhà thầu."),
    ("27/NQ", "Hoàng Minh Giám", 0, "Ngày 26/10/2026 chủ đầu tư phê duyệt dự toán và kế hoạch lựa chọn nhà thầu."),
    ("27/NQ", "phòng họp không giấy", 0, "Ngày 26/10/2026 chủ đầu tư phê duyệt dự toán và kế hoạch lựa chọn nhà thầu."),
    ("27/NQ", "Rạp chiếu bóng", 0, "Ngày 11/11/2026 chủ đầu tư phê duyệt kết quả chỉ định thầu gói thầu thẩm tra thiết kế bản vẽ thi công, dự toán."),
    # 06 dự án ngân sách tỉnh bổ sung (QĐ 2347): sơ đồ tiến độ và báo cáo của chủ đầu tư ngày 15/11/2026
    ("2347", "Kom Leo", 0, HD_2347 + "Theo sơ đồ tiến độ, từ 03/11 đến 28/11/2026 cày xới mặt đường hư hỏng nặng, thay lớp móng và thảm mặt đường; "
     "tiếp đến thảm tăng cường mặt đường bê tông nhựa, gia cố lề, rãnh thoát nước và hệ thống an toàn giao thông. Dự kiến phê duyệt quyết toán ngày 12/01/2027."),
    ("2347", "TDP 10B", 0, HD_2347 + "Theo sơ đồ tiến độ, từ 03/11 đến 28/11/2026 thi công nền, móng đường hư hỏng; "
     "tiếp đến thảm mặt đường bê tông nhựa, gia cố lề, rãnh thoát nước và hệ thống an toàn giao thông. Dự kiến phê duyệt quyết toán ngày 10/01/2027."),
    ("2347", "Đam San", 0, HD_2347 + "Theo sơ đồ tiến độ, đã thảm tăng cường mặt đường bê tông nhựa; từ 09/11 đến 19/11/2026 thay mới bó vỉa, hoàn trả vỉa hè; "
     "tiếp đến sửa chữa hệ thống thoát nước, điện trang trí và an toàn giao thông. Dự kiến phê duyệt quyết toán ngày 31/12/2026."),
    ("2347", "TDP 2B", 0, HD_2347 + "Theo sơ đồ tiến độ, từ 03/11 đến 23/11/2026 cày xới mặt đường hư hỏng nặng, thay lớp móng và thảm mặt đường; "
     "tiếp đến thảm tăng cường mặt đường bê tông nhựa, gia cố lề, rãnh thoát nước và hệ thống an toàn giao thông. Dự kiến phê duyệt quyết toán ngày 12/01/2027."),
    ("2347", "TDP 5B", 0, HD_2347 + "Ngày 14/11/2026 đơn vị thi công thảm bê tông nhựa trục 1, vệ sinh các trục 2, 3, 4, 5 và 7 để thảm. "
     "Theo sơ đồ tiến độ, từ 09/11 đến 24/11/2026 cày xới, thay kết cấu và thảm mặt đường đoạn hư hỏng nặng; tiếp đến gia cố lề, rãnh thoát nước. "
     "Dự kiến phê duyệt quyết toán ngày 05/01/2027."),
    ("2347", "TDP 9B", 0, HD_2347 + "Theo sơ đồ tiến độ, đã thảm tăng cường mặt đường bê tông nhựa; từ 09/11 đến 29/11/2026 cày xới mặt đường hư hỏng nặng, thay lớp móng và thảm mặt đường; "
     "tiếp đến gia cố lề, rãnh thoát nước. Dự kiến phê duyệt quyết toán ngày 10/01/2027."),
]

# Cập nhật từ văn bản trên iOffice (anh Phú đã duyệt ngày 15/11/2026): thay ghi chú của bảng số liệu khi bảng chưa kịp cập nhật.
CAP_NHAT = [
    ("CĐS", "trang thiết bị công nghệ thông tin", "UBND phường phê duyệt nhiệm vụ và dự toán chuẩn bị đầu tư tại Quyết định số 1993/QĐ-UBND ngày 03/11/2026; ngày 12/11/2026 chủ đầu tư phê duyệt kết quả chỉ định thầu các gói thầu tư vấn lập báo cáo nghiên cứu khả thi, thẩm định giá."),
    ("CĐS", "hạ tầng chuyển đổi số", "UBND phường phê duyệt nhiệm vụ và dự toán chuẩn bị đầu tư tại Quyết định số 2048/QĐ-UBND ngày 11/11/2026; chủ đầu tư đã phê duyệt kế hoạch lựa chọn nhà thầu tư vấn chuẩn bị đầu tư."),
    ("MTQG", "Kõ Mliâo", "UBND phường phê duyệt chủ trương đầu tư tại Quyết định số 1999/QĐ-UBND ngày 04/11/2026; chủ đầu tư triển khai các bước tiếp theo."),
    ("MTQG", "Ea Cuôr Kap", "UBND phường phê duyệt chủ trương đầu tư tại Quyết định số 2000/QĐ-UBND ngày 04/11/2026; chủ đầu tư triển khai các bước tiếp theo."),
]

# Kế hoạch giải ngân do chủ đầu tư báo cáo, theo nguồn: (mốc, tỷ lệ) và ghi chú
KH_GN = {
    "2347": ([(dt.date(2026, 11, 30), 0.60), (dt.date(2026, 12, 20), 0.98)],
             "Kế hoạch giải ngân của chủ đầu tư (vạch chấm trên thanh): đạt ít nhất 60% đến ngày 30/11/2026 và 98% trước ngày 20/12/2026; "
             "phần còn lại chủ yếu là chi phí dự phòng chưa phát sinh khối lượng. Theo hợp đồng thi công, 06 dự án hoàn thành toàn bộ khối lượng trước ngày 23/12/2026; "
             "chủ đầu tư đánh giá tiến độ hiện nay ổn định."),
}
DONE = "Đã quyết toán"
NEW = "Mới giao chi tiết"

# Quyết định của UBND phường giao chi tiết kế hoạch vốn (một phần) cho dự án.
# (khóa nguồn vốn, cụm tên dự án, số vốn giao chi tiết, căn cứ, ngày giao, tên dự án theo quyết định)
QD1994 = ("Quyết định số 1994/QĐ-UBND ngày 03/11/2026 của UBND phường (đợt 1, chuẩn bị đầu tư)", dt.date(2026, 11, 3))
GIAO_CT = [
    ("27/NQ", "Nguyễn Văn Cừ", 392e6, *QD1994, "Trường TH - THCS Nguyễn Văn Cừ"),
    ("27/NQ", "Hoàng Minh Giám", 88e6, *QD1994, "Đầu tư xây dựng đường Hoàng Minh Giám (đoạn khu dân cư TDP 4 đến đường Trương Quang Tuân)"),
    ("27/NQ", "Hùng Vương", 251e6, *QD1994, "Cải tạo các đường hẻm Hùng Vương – Ama Khê"),
    ("27/NQ", "Phạm Văn Đồng", 221e6, *QD1994, "Cải tạo 02 trục đường hẻm Phạm Văn Đồng"),
    ("27/NQ", "Má Hai", 152e6, *QD1994, "Cải tạo đường Má Hai"),
    ("27/NQ", "Nguyễn Đình Thi", 200e6, *QD1994, "Cải tạo đường Nguyễn Đình Thi"),
    ("27/NQ", "Tăng Bạt Hổ", 203e6, *QD1994, "Cải tạo đường Tăng Bạt Hổ"),
    ("27/NQ", "phòng họp không giấy", 107e6, *QD1994, "Đầu tư nâng cấp phòng họp không giấy tại phường Tân Lập"),
    ("27/NQ", "hội nghị truyền hình", 484e6, *QD1994, "Hệ thống hội nghị truyền hình trực tuyến và các hoạt động chuyển đổi số trên địa bàn phường Tân Lập"),
    ("27/NQ", "Rạp chiếu bóng", 59e6, *QD1994, "Phá dỡ, hoàn trả mặt bằng Rạp chiếu bóng 10-3"),
    ("CĐS", "trang thiết bị công nghệ thông tin", 53e6, "Quyết định số 2021/QĐ-UBND ngày 05/11/2026 của UBND phường (đợt 01, chuẩn bị đầu tư)", dt.date(2026, 11, 5), None),
    ("CĐS", "Trung tâm Phục vụ hành chính công", 115_273_161, "Quyết định số 2057/QĐ-UBND ngày 11/11/2026 của UBND phường (đợt 01, chuẩn bị đầu tư)", dt.date(2026, 11, 11), None),
]

# Sơ đồ tuyến (từ bản vẽ vị trí các tuyến của chủ đầu tư, đơn vị mét) và trạng thái thi công từng trục
SO_DO_TUYEN = {
    "TDP 5B": {"vb": "680 0 810 1030", "paths": {
        "1": "M1340 339 1328 341 1320 306M1050 86 1059 83M1148 311 1128 317M1014 94 1092 72M1051 218 1090 207M1055 85 1101 242M1132 349 1143 384 1328 341M1108 251 1118 248M1071 142 1073 142M1233 364 1233 363M1320 341 1321 345M1108 270 1078 278",
        "2": "M1257 88 1116 125 1131 176 1273 142M1285 140 1273 142 1247 54M1116 125 1108 95M1249 89 1249 90M1265 143 1266 144",
        "3": "M1320 306 1309 257M1312 270 1148 311M1128 317 1123 318M1116 294 1132 349M1126 334 1128 334M1123 312 1121 313M1195 297 1196 299",
        "4": "M866 138 856 140M860 139 918 322 948 441M940 472 956 470M903 326 949 314M848 141 895 128M882 264 932 251M878 197 879 196M925 349 926 349M946 469 961 468M985 466 925 473",
        "5": "M927 121 1014 431M949 314 1014 296M895 128 965 108M932 251 1002 232M930 125 928 125M1009 459 1015 458M1020 457 1026 456M1048 456 990 465",
        "6": "M1014 431 1020 458M948 441 956 470M1014 296 1043 288M747 975 755 1011M840 660 778 673M1101 242 1116 294M1103 252 1108 251M764 1009 741 1014M952 460 953 460M1015 458 1020 457M1078 278 1043 288 1075 410 1077 453 1048 456M990 465 985 466M925 473 774 489 802 634M807 661 809 672M814 698 871 989 570 1045 551 1066 525 1124 453 1235 299 1310 223 1343 90 1389 18 1405",
        "7": "M686 677 697 731M1463 533 840 660M778 673 689 691M1461 522 1465 542M802 634 807 661M809 672 814 698"
    }, "lab": {"1": (1065, 34), "2": (1280, 34), "3": (1232, 248), "4": (828, 110), "5": (945, 40), "6": (905, 850), "7": (1440, 492)}},
}
SO_DO_TUYEN["TDP 10B"] = {"vb": "0 0 3205 2512", "r": 95, "fs": 105, "paths": {
        "1": "M172 2340 330 2232 291 2183 542 2013 583 2055 1091 1702 1092 1332 1311 1265 1584 1068 1556 984 1561 925 1537 822 1538 732 1521 507 1545 497 1549 488 1562 420 1703 409 1746 373 1778 361 1920 339 2212 281 3033 172",
        "2": "M430 1795 351 1651 414 1621 393 1556 677 1443 839 1362 1088 1327",
        "3": "M684 1440 688 1618"
    }, "lab": {"1": (1450, 690), "2": (250, 1440), "3": (845, 1560)}}
# Đường giao thông buôn Kom Leo (15 trục) và TDP 9B (02 trục): theo tệp KMZ vị trí các trục của chủ đầu tư
SO_DO_TUYEN["Kom Leo"] = {"vb": "0 0 1061 1457", "r": 30, "fs": 34, "ten_nhom": "15 trục", "paths": {
        "all": "M956 390 744 389M952 689 738 683M959 247 956 390M956 390 954 538M954 538 952 689M952 689 949 845M949 845 948 955M948 955 947 1019M728 1163 729 1062M729 1062 734 835M734 835 738 683M738 683 741 535M510 1169 512 1005M512 1005 515 829M515 829 518 676M185 816 199 920M199 920 207 993M281 1176 312 1175M312 1175 510 1169M510 1169 728 1163M212 1053 212 1053 213 1060 213 1066 214 1072 215 1078 216 1084 216 1084 216 1084M207 993 212 1053M233 1171 233 1171 234 1174 235 1175 237 1177 239 1178 241 1178 241 1178 241 1178M216 1084 233 1171M241 1178 281 1176M734 835 612 832M612 832 515 829M515 829 371 823M371 823 310 821M310 821 185 816M166 815 166 815 163 815 160 815 157 815 154 815 151 815 151 815 151 815M185 816 166 815M151 815 141 816M310 821 311 669M311 669 314 526M314 526 196 520M196 520 67 520M67 520 81 663M175 769 175 769 175 765 173 761 171 757 169 754 167 750 167 750 167 750M182 816 175 769M154 736 154 736 154 736 152 733 150 731 149 728 148 725 147 722 147 722M167 750 154 736M147 722 141 664M593 98 750 101 877 103M325 1341 509 1342 693 1346 723 1346M510 1169 512 1005 515 829 518 676M309 821 311 669 314 526M534 243 614 245 747 246 830 246 959 247M738 683 713 681M954 538 950 538 949 538 933 538 914 537 899 537 878 537 859 537 854 536 843 536 823 536 802 536 789 536 770 535 754 535 754 535 746 535 741 535M67 520 67 523 68 537 70 554 72 575 74 592 76 610 77 619 78 630 80 648 81 658 81 661 81 663M734 835 729 834 715 834 697 834 680 833 662 833 644 832 634 832 627 832 612 832 608 832 589 831 568 830 546 830 534 829 528 829 515 829 499 828 478 827 456 826 434 825 430 825 412 824 407 824 388 823 371 823 366 823 344 822 334 822 330 821 309 821 293 820 273 819 250 819 234 818 226 818 206 817 194 816 185 816 172 815 166 815 159 815 156 815 151 815 141 816M185 816 185 818 185 819 185 820 188 838 190 856 192 872 195 888 197 904 198 915 199 920 201 938 202 945 205 972 207 991 207 993 208 1008 209 1014 210 1026 211 1040 212 1047 212 1053 214 1068 214 1069 216 1082 216 1084 219 1097 222 1112 222 1113 225 1132 229 1152 233 1171 236 1176 241 1178 253 1177 270 1176 273 1176 281 1176 293 1175 312 1175 329 1174 347 1174 366 1173 370 1173 387 1173 409 1172 429 1172 448 1171 467 1171 470 1170 487 1170 510 1169 527 1169 548 1168 566 1168 570 1168 586 1167 608 1167 627 1166 645 1166 662 1165 670 1165 680 1165 698 1164 718 1164 728 1163"
    }, "lab": {"6": (750, 40), "11": (445, 1417), "5": (817, 214), "7": (892, 355), "8": (876, 505), "4": (1021, 455), "9": (886, 657), "1": (641, 1124), "3": (459, 783), "2": (794, 910), "10": (590, 924), "12": (376, 688), "13": (224, 486), "15": (91, 696), "14": (40, 546)}}
SO_DO_TUYEN["TDP 9B"] = {"vb": "0 0 1823 807", "r": 52, "fs": 58, "paths": {
        "1": "M60 747 95 738M95 738 97 738 98 738 99 737 100 737 102 737 103 736 104 736 106 736 107 735 108 735 109 735 111 734 112 734 113 733 115 733 116 733 117 732 118 732 120 732 121 731 122 731 123 731 125 730 126 730 127 729 128 729 130 729 131 728 132 728 134 727 135 727 136 727 137 726 139 726 140 725 141 725 142 725 144 724 145 724 146 723 147 723 149 723 150 722 151 722 152 721 154 721 155 720 156 720M156 720 208 702M208 702 284 671M284 671 285 671 286 671 287 671 287 670 288 670 289 670 290 669 290 669 291 669 292 668 293 668 293 668 294 667 295 667 296 667 296 666 297 666 298 666 299 665 299 665 300 665 301 664 302 664 302 663 303 663 304 663 305 662 305 662 306 662 307 661 307 661 308 660 309 660 310 660 310 659 311 659 312 658 313 658 313 658 314 657 315 657 315 656 316 656 317 656 318 655 318 655 319 654 320 654M320 654 396 608M396 608 513 531M513 531 577 493M616 472 615 473 614 473 613 474 613 474 612 474 611 475 610 475 609 476 609 476 608 476 607 477 606 477 605 478 604 478 604 478 603 479 602 479 601 480 600 480 600 480 599 481 598 481 597 482 596 482 596 483 595 483 594 483 593 484 592 484 592 485 591 485 590 486 589 486 588 486 588 487 587 487 586 488 585 488 584 489 584 489 583 490 582 490 581 490 580 491 580 491 579 492 578 492 577 493M616 472 635 464M635 464 724 420M770 400 769 401 768 401 767 401 766 402 765 402 764 403 763 403 762 403 761 404 760 404 759 404 759 405 758 405 757 406 756 406 755 406 754 407 753 407 752 408 751 408 750 408 749 409 748 409 747 410 746 410 745 411 744 411 743 411 742 412 741 412 740 413 739 413 739 414 738 414 737 414 736 415 735 415 734 416 733 416 732 417 731 417 730 417 729 418 728 418 727 419 726 419 725 420 724 420M770 400 830 377M830 377 1154 256M1154 256 1270 216M1270 216 1540 125M1540 125 1763 60",
        "2": "M166 433 129 345 129 345 129 345 129 345 129 344 129 344 129 344 129 344 129 344 129 344 129 344 129 343 129 343 129 343 129 343 129 343 129 343 129 343 129 342 129 342 129 342 129 342 129 342 129 342 129 341 129 341 129 341 129 341 129 341 129 341 129 341 129 341 129 340 129 340 130 340 130 340 130 340 130 340 130 340 130 340 130 339 130 339 130 339 131 339 131 339 131 339 131 339 131 339 131 339 131 339 216 292 244 277 330 230 378 204 420 183 427 180 427 179"
    }, "lab": {"1": (60, 747), "2": (166, 433)}}
# Đường Đam San là một tuyến gần thẳng: thể hiện dạng dải theo lý trình (km0+000 đến km1+054 theo bản vẽ)
SO_DO_TUYEN["Đam San"] = {"kind": "strip", "dai": 1054, "ten": "Tuyến đường Đam San"}
TT_TRUC = {"tham": "Đã triển khai thảm bê tông nhựa", "cb": "Đang vệ sinh mặt đường, chuẩn bị thảm", "chua": "Chưa có báo cáo",
           "pv": "Phạm vi thi công; chưa có báo cáo tiến độ chi tiết"}
TRUC_TT = {
    "TDP 5B": ({"1": "tham", "2": "cb", "3": "cb", "4": "cb", "5": "cb", "7": "cb", "6": "chua"},
               "Theo báo cáo của chủ đầu tư ngày 14/11/2026. Sơ đồ thể hiện một phần trục 6, đoạn còn lại tiếp tục về hướng Tây Nam."),
    "TDP 10B": ({"1": "pv", "2": "pv", "3": "pv"}, "Theo bản vẽ vị trí các trục của chủ đầu tư."),
    "Đam San": ({"tuyen": "pv"}, "Theo bản vẽ vị trí tuyến của chủ đầu tư; lý trình từ Km0+000 đến Km1+054."),
    "Kom Leo": ({"all": "pv"}, "Theo bản vẽ tổng thể 15 trục của chủ đầu tư."),
    "TDP 9B": ({"1": "pv", "2": "pv"}, "Theo bản vẽ vị trí trục 1, trục 2 của chủ đầu tư."),
}
RANK = {"chua": 0, "pv": 1, "cb": 2, "tham": 3}



def pkey(name):
    n = unicodedata.normalize("NFC", name).lower().replace("–", "-").replace("—", "-")
    return re.sub(r"^dự án:?\s+", "", " ".join(n.split()))


# Tổng mức đầu tư, chủ đầu tư: tra cứu quyết định phê duyệt dự án (pd), chủ trương đầu tư (ct)
# hoặc phê duyệt quyết toán (qt) trên hệ thống iOffice; khóa là cụm từ trong tên dự án (chữ thường).
CDT_TT = "Trung tâm Cung ứng dịch vụ sự nghiệp công phường Tân Lập"
CDT_VH = "Phòng Văn hóa - Xã hội phường Tân Lập"
CDT_NGAN = {CDT_TT: "Trung tâm CƯDVSNC", CDT_VH: "Phòng VH-XH"}
CDT_MA = {CDT_TT: "tt", CDT_VH: "vh"}
THONG_TIN_DA = [
    ("cao đạt", 28_849_181_000, CDT_TT, "pd", "Quyết định số 1648/QĐ-UBND ngày 29/9/2026 của UBND phường phê duyệt điều chỉnh tổng mức đầu tư; Trung tâm là đại diện chủ đầu tư"),
    ("mầm non tân hòa", 3_417_352_000, CDT_TT, "qt", "Giá trị quyết toán theo Quyết định số 1348/QĐ-UBND ngày 07/8/2026 của UBND phường"),
    ("kom leo", 20_000_000_000, CDT_TT, "pd", "Quyết định số 1729/QĐ-UBND ngày 09/10/2026 của UBND phường phê duyệt dự án"),
    ("tdp 10b", 16_000_000_000, CDT_TT, "pd", "Quyết định số 1727/QĐ-UBND ngày 09/10/2026 của UBND phường phê duyệt dự án"),
    ("đam san", 16_000_000_000, CDT_TT, "pd", "Quyết định số 1730/QĐ-UBND ngày 09/10/2026 của UBND phường phê duyệt dự án"),
    ("tdp 2b", 13_500_000_000, CDT_TT, "pd", "Quyết định số 1728/QĐ-UBND ngày 09/10/2026 của UBND phường phê duyệt dự án"),
    ("tdp 5b", 12_000_000_000, CDT_TT, "pd", "Quyết định số 1726/QĐ-UBND ngày 09/10/2026 của UBND phường phê duyệt dự án"),
    ("tdp 9b", 7_500_000_000, CDT_TT, "pd", "Quyết định số 1725/QĐ-UBND ngày 09/10/2026 của UBND phường phê duyệt dự án"),
    ("trang thiết bị công nghệ thông tin", 1_528_000_000, CDT_VH, "ct", "Quyết định số 1921/QĐ-UBND ngày 23/10/2026 của UBND phường về chủ trương đầu tư"),
    ("hạ tầng chuyển đổi số tại trung tâm phục vụ", 2_758_000_000, CDT_VH, "ct", "Quyết định số 01928/QĐ-UBND ngày 27/10/2026 của UBND phường về chủ trương đầu tư"),
    ("kõ mliâo", 3_200_000_000, CDT_VH, "ct", "Quyết định số 1999/QĐ-UBND ngày 04/11/2026 của UBND phường về chủ trương đầu tư"),
    ("ea cuôr kap", 1_730_000_000, CDT_VH, "ct", "Quyết định số 2000/QĐ-UBND ngày 04/11/2026 của UBND phường về chủ trương đầu tư"),
    ("th - thcs nguyễn văn cừ", 55_955_000_000, CDT_TT, "ct", "Quyết định số 1652/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("tiểu học nguyễn du", 17_400_000_000, CDT_TT, "pd", "Quyết định số 1449/QĐ-UBND ngày 26/8/2026 của UBND phường phê duyệt dự án"),
    ("thcs nguyễn văn cừ", 20_000_000_000, CDT_TT, "pd", "Quyết định số 1450/QĐ-UBND ngày 26/8/2026 của UBND phường phê duyệt dự án"),
    ("d8 và n14", 48_213_000_000, CDT_TT, "pd", "Quyết định số 2037/QĐ-UBND ngày 06/11/2026 của UBND phường phê duyệt dự án"),
    ("trạm y tế", 2_300_000_000, CDT_TT, "pd", "Quyết định số 1448/QĐ-UBND ngày 26/8/2026 của UBND phường phê duyệt dự án"),
    ("hội trường, nhà làm việc đảng ủy", 2_300_000_000, CDT_TT, "pd", "Quyết định số 1445/QĐ-UBND ngày 25/8/2026 của UBND phường phê duyệt dự án"),
    ("hạ tầng kỹ thuật trên địa bàn", 19_911_000_000, CDT_TT, "pd", "Quyết định số 1731/QĐ-UBND ngày 09/10/2026 của UBND phường phê duyệt dự án"),
    ("ama khê", 5_600_000_000, CDT_TT, "ct", "Quyết định số 1657/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("nguyễn đình thi", 4_884_692_000, CDT_TT, "ct", "Quyết định số 1660/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("má hai", 3_268_492_000, CDT_TT, "ct", "Quyết định số 1659/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("tăng bạt hổ", 5_117_649_000, CDT_TT, "ct", "Quyết định số 1661/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("phạm văn đồng", 5_555_000_000, CDT_TT, "ct", "Quyết định số 1658/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("hoàng minh giám", 1_800_000_000, CDT_TT, "ct", "Quyết định số 1656/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("hội nghị truyền hình", 8_152_000_000, CDT_TT, "ct", "Quyết định số 1654/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("phòng họp không giấy", 1_720_000_000, CDT_TT, "ct", "Quyết định số 1653/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("rạp chiếu bóng", 1_000_000_000, CDT_TT, "ct", "Quyết định số 1655/QĐ-UBND ngày 29/9/2026 của UBND phường về chủ trương đầu tư"),
    ("c5-c6-c7", 63_357_000_000, CDT_TT, "ct", "Quyết định số 2001/QĐ-UBND ngày 04/11/2026 của UBND phường về chủ trương đầu tư"),
]
LOAI_TM = {"pd": "Tổng mức đầu tư", "ct": "Tổng mức đầu tư (theo chủ trương)", "qt": "Giá trị quyết toán"}
DAU_TM = {"pd": "", "ct": "*", "qt": "**"}


def thong_tin(du_an):
    k = pkey(du_an).replace(" – ", " - ")
    for key, tm, cdt, loai, cc in THONG_TIN_DA:
        if key in k:
            return {"tm": tm, "cdt": cdt, "loai": loai, "cc": cc}
    return None


def gom_the(projects, gmap, today):
    """Gom các dự án vốn HĐND phường giao (khối B) trùng tên ở nhiều nghị quyết, quyết định vào 01 thẻ."""
    cards, byk = [], {}
    for p in projects:
        if p["khoi"] == "B" and pkey(p["du_an"]) in byk:
            byk[pkey(p["du_an"])]["parts"].append(p)
            continue
        c = dict(p, parts=[p])
        if p["khoi"] == "B":
            byk[pkey(p["du_an"])] = c
        cards.append(c)
    for c in cards:
        ps = c["parts"]
        c["nhoms"] = [q["nhom"] for q in ps]
        if len(ps) == 1:
            continue
        for k in ("kh", "gn", "du", "chua", "kh_gct"):
            c[k] = sum(q.get(k, 0.0) for q in ps)
        c["tl"] = c["gn"] / c["kh"] if c["kh"] else 0
        c["chua_giao"] = all(q["chua_giao"] for q in ps)
        notes = []
        for q in ps:
            if q.get("note") and q["note"] not in notes:
                notes.append(q["note"])
        c["note"] = " ".join(notes)
        if any(not q["chua_giao"] for q in ps[1:]) and not c.get("done"):
            base = c["kh"] - c["chua"] - c["du"]
            c["xl"] = status(c["gn"] / base if base > 0 else 1, "B", c["giao"], c["due"], today, c["chua_giao"])
    return cards


def so_do_strip(sd, st):
    dai, x0, w = sd["dai"], 60, 980
    sx = lambda m: x0 + w * m / dai
    ticks = "".join(f'<line x1="{sx(m):.0f}" y1="58" x2="{sx(m):.0f}" y2="92" class="m-tick"/><text x="{sx(m):.0f}" y="116" class="m-km">H{m // 100}</text>'
                    for m in range(100, dai, 100))
    return (f'<svg class="tmap tstrip" viewBox="0 0 1100 150" role="img" aria-label="Sơ đồ lý trình {e(sd["ten"])}">'
            f'<line x1="{x0}" y1="56" x2="{x0 + w}" y2="56" class="m-vs"/><line x1="{x0}" y1="94" x2="{x0 + w}" y2="94" class="m-vs"/>'
            f'<path class="m-{st}" d="M{x0} 75H{x0 + w}"/>{ticks}'
            f'<text x="{x0}" y="36" class="m-end" text-anchor="start">Km0+000</text><text x="{x0 + w}" y="36" class="m-end" text-anchor="end">Km1+054</text></svg>')


def so_do(du_an):
    for key, sd in SO_DO_TUYEN.items():
        if key.lower() not in du_an.lower():
            continue
        tt, nguon = TRUC_TT.get(key, ({}, ""))
        if sd.get("kind") == "strip":
            st = tt.get("tuyen", "chua")
            svg = so_do_strip(sd, st)
            lg = f'<li><i class="m-{st}"></i>{e(sd["ten"])}: {TT_TRUC[st]}</li>'
        else:
            r, fs = sd.get("r", 34), sd.get("fs", 38)
            order = sorted(sd["paths"], key=lambda k: RANK.get(tt.get(k, "chua"), 0))
            g = "".join(f'<path class="m-{tt.get(k, "chua")}" d="{sd["paths"][k]}"/>' for k in order)
            g += "".join(f'<g class="m-lab"><circle cx="{x}" cy="{y}" r="{r}" style="stroke-width:{r / 8:.0f}"/><text x="{x}" y="{y + fs * 0.36:.0f}" style="font-size:{fs}px">{k}</text></g>'
                         for k, (x, y) in sd["lab"].items())
            svg = f'<svg class="tmap" viewBox="{sd["vb"]}" role="img" aria-label="Sơ đồ các trục của dự án">{g}</svg>'
            groups = {}
            for k in sorted(sd["paths"]):
                groups.setdefault(tt.get(k, "chua"), []).append(k)
            lg = "".join(f'<li><i class="m-{st}"></i>Trục {", ".join(ks)}: {TT_TRUC[st]}</li>' for st in ("tham", "cb", "pv", "chua") if (ks := groups.get(st)))
            if sd.get("ten_nhom"):
                st = tt.get("all", "chua")
                lg = f'<li><i class="m-{st}"></i>{e(sd["ten_nhom"])}: {TT_TRUC[st]}</li>'
        return (f'<div class="wide"><dt>Sơ đồ tuyến</dt><dd>{svg}'
                f'<ul class="map-lg">{lg}</ul><small class="map-src">{e(nguon)}</small></dd></div>')
    return ""


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
    if (today - giao).days < URGENT_DAYS:
        return "Cấp bách" if khoi == "A" else NEW
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
    ("Cải tạo các đường hẻm Hùng Vương – Ama Khê", 1_500e6),
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
        for key, ten, note in CAP_NHAT:
            if key in g["nguon"] and ten.lower() in p["du_an"].lower():
                p["note"] = note
        p["done"] = done
        p["kh_gct"] = 0.0
        for key, ten, amt, basis, ngay, ten_qd in GIAO_CT:
            if key in g["nguon"] and ten.lower() in p["du_an"].lower():
                p["kh_gct"], p["gct_basis"] = float(amt), basis
                if ten_qd:
                    p["du_an"] = ten_qd
                gct = (f"UBND phường đã giao chi tiết {vi(amt)} đồng để thực hiện chuẩn bị đầu tư tại {basis}; "
                       f"phần còn lại giao khi dự án được phê duyệt.")
                p["note"] = (p["note"] + " " + gct) if p.get("note") else gct
                if p["chua_giao"]:
                    p["chua_giao"], p["giao"] = False, ngay
        p["chua"] = p["kh"] if p["chua_giao"] else (max(p["kh"] - p["kh_gct"], 0) if g["khoi"] == "B" and p["kh_gct"] else 0.0)
        base = p["kh_gct"] if (g["khoi"] == "B" and p["kh_gct"]) else p["kh"] - p["du"]
        tl_eff = p["gn"] / base if base > 0 else 1
        p["xl"] = status(tl_eff, p["khoi"], p["giao"], p["due"], today, p["chua_giao"], done)
    for g in keep:
        ps = [p for p in projects if p["nhom"] == g["nhom"]]
        g["chua_giao"] = bool(ps) and all(p["chua_giao"] for p in ps)
        ps_g = [p for p in ps if not p["chua_giao"]]
        g["giao"] = min(p["giao"] for p in ps_g) if ps_g else g["giao"]
        g["du"] = sum(p["du"] for p in ps)
        g["chua"] = sum(p["chua"] for p in ps)
        g["kh_gct"] = sum(p["kh_gct"] for p in ps)
        base = g["kh"] - g["chua"] - g["du"]
        tl_eff = g["gn"] / base if base > 0 else 1
        g["xl"] = status(tl_eff, g["khoi"], g["giao"], g["due"], today, g["chua_giao"])
    projects.sort(key=lambda p: (order[p["khoi"]], [g["nhom"] for g in keep].index(p["nhom"]), p["stt"]))
    t = {"kh": sum(p["kh"] for p in projects), "gn": sum(p["gn"] for p in projects), "kh_g": kh_g, "gn_g": gn_g,
         "kh_chua": sum(p["chua"] for p in projects), "n_chua": sum(1 for p in projects if p["chua_giao"])}
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


BADGE = {"Đạt tiến độ": "ok", "Chậm tiến độ": "warn", "Cấp bách": "late", "Mới giao chi tiết": "new", "Chờ UBND giao chi tiết": "neutral", "Đã quyết toán": "done"}
FILL = {"new": "fill-new", "ok": "fill-ok", "warn": "fill-warn", "late": "fill-late", "neutral": "fill-neutral", "done": "fill-done"}


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
    kh_chua = sum(g["chua"] for g in groups)
    g_due26 = [g for g in groups if g["due"] <= DUE_2026]
    kh_ref = sum(g["kh"] for g in g_due26)  # kế hoạch có hạn giải ngân đến 31/01/2027, dùng cho biểu đồ diễn biến
    tg = progress(today, DUE_2026)
    rate = gn_now / kh_all if kh_all else 0
    for g in groups:
        g["sub"] = ("truoc" if g["giao"] <= CUT_B else "sau") if g["khoi"] == "B" else ""
    cards = gom_the(projects, {g["nhom"]: g for g in groups}, today)
    cnt = {k: sum(1 for p in cards if p["xl"] == k) for k in BADGE}
    weeks, months, quarters = periods(daily, today, kh_all)
    wk, mo, qu = weeks[-1], months[-1], quarters[-1]
    prev_wk = weeks[-2] if len(weeks) > 1 else None
    tomorrow = today + dt.timedelta(days=1)

    # nhu cầu giải ngân theo tuần (thứ Hai đến Chủ nhật): mức cần của tuần tính cố định từ đầu tuần
    # = vốn còn lại cuối Chủ nhật tuần trước chia cho số tuần còn đến hạn (quy đổi theo ngày làm việc, 5 ngày một tuần)
    monday = today - dt.timedelta(days=today.weekday())
    def wneed(g, mon):
        gn0 = min(cum_on(daily, mon - dt.timedelta(days=1), {g["nhom"]}), g["gn"])
        left0 = max(g["kh"] - gn0 - g["du"], 0)
        nw = workdays(mon, g["due"]) / 5
        return gn0, left0, nw, left0 / max(nw, 1)
    for g in groups:
        gn0, left0, nw, per = wneed(g, monday)
        g["w_left0"], g["w_n"], g["w_need"], g["w_in"] = left0, nw, per, g["gn"] - gn0
        pm = monday - dt.timedelta(days=7)
        if g["giao"] <= pm + dt.timedelta(days=6):
            p0, pl, pn, pp = wneed(g, pm)
            g["p_need"], g["p_in"] = pp, gn0 - p0
        else:
            g["p_need"], g["p_in"] = 0.0, 0.0

    def need(gs):
        left = sum(max(g["kh"] - g["gn"] - g["du"], 0) for g in gs)
        per = sum(g["w_need"] for g in gs)
        return left, per

    # hai khối nguồn vốn
    blk = {}
    for k in ("A", "B"):
        gs = [g for g in groups if g["khoi"] == k]
        kh, gn = sum(g["kh"] for g in gs), sum(g["gn"] for g in gs)
        left, per = need(gs)
        blk[k] = {"gs": gs, "kh": kh, "gn": gn, "tl": gn / kh if kh else 0, "left": left, "per": per,
                  "chua": sum(g["chua"] for g in gs),
                  "n_cb": sum(1 for p in projects if p["khoi"] == k and p["xl"] == "Cấp bách"),
                  "n_ch": sum(1 for p in projects if p["khoi"] == k and p["xl"] == "Chậm tiến độ")}
    subs = {}
    for sk in ("truoc", "sau"):
        gs = [g for g in groups if g["sub"] == sk]
        kh, gn = sum(g["kh"] for g in gs), sum(g["gn"] for g in gs)
        subs[sk] = {"gs": gs, "kh": kh, "gn": gn, "tl": gn / kh if kh else 0, "chua": sum(g["chua"] for g in gs)}
    tot_left, per_day = need(groups)
    w_in_all = sum(g["w_in"] for g in groups)
    p_need_all, p_in_all = sum(g["p_need"] for g in groups), sum(g["p_in"] for g in groups)

    take = (f"Đến ngày {upd}, phường đã giải ngân {ty(gn_now)}, đạt {pct(rate)} tổng kế hoạch vốn năm 2026 "
            f"({ty(kh_all)}); tiến độ thời gian đã qua {pct(tg)}. "
            f"Vốn cấp trên giao đạt {pct(blk['A']['tl'])} ({ty(blk['A']['gn'])}/{ty(blk['A']['kh'])}), "
            f"vốn HĐND phường giao đạt {pct(blk['B']['tl'])} ({ty(blk['B']['gn'])}/{ty(blk['B']['kh'])}; "
            f"phần giao trước ngày 30/9/2026 đạt {pct(subs['truoc']['tl'])}). "
            f"Tuần này giải ngân thêm {ty(wk['in'])}, từ đầu tháng {today.month} là {ty(mo['in'])}. "
            f"Để giải ngân hết kế hoạch đúng hạn, tuần này ({monday:%d/%m} đến {monday + dt.timedelta(days=6):%d/%m}) cần giải ngân khoảng {ty(per_day)}, "
            f"riêng vốn cấp trên giao là {ty(blk['A']['per'])}; đã giải ngân được {ty(w_in_all)}.")
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
              f"{KHOI['A'][1]}. Còn {ty(blk['A']['left'])}, tuần này cần {ty(blk['A']['per'])}"),
        f'<div class="kpi k-brown"><p class="kpi-label">B. {e(KHOI["B"][0])}</p><p class="kpi-value">{pct(blk["B"]["tl"])}</p>'
        f'<p class="kpi-sub">{ty(blk["B"]["gn"])} / {ty(blk["B"]["kh"])}</p><ul class="kpi-split">{split_line("truoc")}{split_line("sau")}</ul></div>',
    ])

    # nhu cầu mỗi tuần, theo khối
    def wpct(x, n):
        return pct(x / n) if n > 0 else ""
    need_rows = []
    for k in ("A", "B"):
        gg = blk[k]["gs"]
        if not gg:
            continue
        need_rows.append(f'<tr class="grp"><td colspan="7">{k}. {e(KHOI[k][0])}</td></tr>')
        for g in gg:
            need_rows.append(f'<tr><td><b>{e(g["ma"])}.</b> {e(g["short"])}</td><td class="num">{ty(g["w_left0"], False)}</td><td class="num">{g["due"]:%d/%m/%Y}</td>'
                             f'<td class="num">{vi(g["w_n"], 1)}</td><td class="num strong">{ty(g["w_need"], False)}</td><td class="num">{ty(g["w_in"], False)}</td><td class="num">{wpct(g["w_in"], g["w_need"])}</td></tr>')
        wl = sum(g["w_left0"] for g in gg); wi = sum(g["w_in"] for g in gg)
        need_rows.append(f'<tr class="sub"><td>Cộng khối {k}</td><td class="num">{ty(wl, False)}</td><td></td><td></td><td class="num">{ty(blk[k]["per"], False)}</td><td class="num">{ty(wi, False)}</td><td class="num">{wpct(wi, blk[k]["per"])}</td></tr>')
    w_bar = min(100, w_in_all / per_day * 100) if per_day else 0
    w_cmp = (f"Tuần trước ({monday - dt.timedelta(days=7):%d/%m} đến {monday - dt.timedelta(days=1):%d/%m}) cần {ty(p_need_all)}, "
             f"đã giải ngân {ty(p_in_all)}, đạt {wpct(p_in_all, p_need_all)}.") if p_need_all else ""

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
                if g["chua"]:
                    val += f"; UBND phường đã giao chi tiết {ty(g['kh_gct'])} để chuẩn bị đầu tư, còn {ty(g['chua'])} chờ giao chi tiết"
                if g["du"]:
                    val += f"; {vi(g['du'])} đồng vốn dư sau quyết toán đã đề nghị điều chỉnh giảm, không tính vào số còn phải giải ngân"
                mark = f'<em style="left:calc({od*100:.2f}% - 1px)" title="Tiến độ thời gian từ ngày giao {pct(od)}"></em>'
            plan = ""
            for key, (mocs, txt) in KH_GN.items():
                if key in g["nguon"]:
                    mark += "".join(f'<b class="tgt" style="left:calc({r*100:.2f}% - 1px)" title="Mục tiêu {pct(r)} đến {d:%d/%m/%Y}"></b>' for d, r in mocs)
                    plan = f'\n  <p class="src-plan">{e(txt)}</p>'
            src.append(f'''<div class="src">
  <div class="src-top"><span class="src-name"><span class="src-no">{e(g["ma"])}</span>{e(g["long"])}</span><span class="src-right"><span class="badge badge-{b}">{e(g["xl"])}</span><span class="src-pct">{pct(g["tl"])}</span></span></div>
  <div class="bar" role="img" aria-label="{e(g['long'])}: {pct(g['tl'])}"><i class="{FILL[b]}" style="width:{min(100, g['tl']*100):.2f}%"></i>{mark}</div>
  <p class="src-meta">{e(val)} · {n} dự án · {e(g["basis"])}</p>{plan}
</div>''')

    # thẻ dự án
    tiles = []
    gmap = {g["nhom"]: g for g in groups}

    tid, seen = {}, {}
    for p in cards:
        ma = gmap[p["nhom"]]["ma"]
        seen[ma] = seen.get(ma, 0) + 1
        tid[id(p)] = f"da-{ma.lower()}-{seen[ma]}"
    same = {}
    for p in cards:
        same.setdefault(pkey(p["du_an"]), []).append(p)

    def xref(p):
        others = [q for q in same[pkey(p["du_an"])] if q is not p]
        if not others:
            return "", ""
        tong = p["kh"] + sum(q["kh"] for q in others)
        links = "; ".join(f'<a href="#{tid[id(q)]}" class="xref-a">{e(gmap[q["nhom"]]["ma"])} · {e(gmap[q["nhom"]]["short"])}</a> {vi(q["kh"])} đồng' for q in others)
        dd = (f'<div class="wide"><dt>Dự án được bố trí vốn từ {len(others) + 1} nguồn</dt><dd>Ngoài {vi(p["kh"])} đồng tại nguồn này, dự án còn được bố trí: {links}. '
              f'Tổng vốn bố trí cho dự án từ các nguồn trên: {vi(tong)} đồng.</dd></div>')
        return f'<span class="tile-multi">Vốn từ {len(others) + 1} nguồn · tổng {ty(tong)}</span>', dd

    def gop(p):
        ps = p["parts"]
        if len(ps) < 2:
            return "", "", ""
        li = []
        for q in ps:
            gq = gmap[q["nhom"]]
            can = gq["basis"].split(";")[0]
            if q["chua_giao"]:
                tt = "chờ UBND phường giao chi tiết"
            elif q.get("chua"):
                tt = f"UBND phường đã giao chi tiết {vi(q['kh_gct'])} đồng, còn {vi(q['chua'])} đồng chờ giao chi tiết"
            else:
                tt = f"đã giao chi tiết, đã giải ngân {vi(q['gn'])} đồng"
            li.append(f'<li><b>{e(gq["ma"])} · {e(gq["short"])}</b> ({e(can)}): {vi(q["kh"])} đồng, {tt}; hạn giải ngân {q["due"]:%d/%m/%Y}.</li>')
        dd = f'<div class="wide"><dt>Vốn theo từng nghị quyết, quyết định</dt><dd><ul class="parts">{"".join(li)}</ul></dd></div>'
        grp = " + ".join(gmap[q["nhom"]]["ma"] for q in ps) + " · " + KHOI["B"][0]
        tag = f'{len(ps)} nguồn vốn' + (f' · chờ giao chi tiết {ty(p["chua"])}' if p.get("chua") else "")
        return grp, f'<span class="tile-multi">{e(tag)}</span>', dd
    for p in cards:
        g = gmap[p["nhom"]]
        grp, multi, xdd = gop(p)
        base_g = p["kh"] - p.get("chua", 0) - p["du"]
        sub = (f'<span class="tile-sub">Đạt {pct(p["gn"] / base_g)} phần đã giao chi tiết</span>'
               if len(p["parts"]) > 1 and p.get("chua") and base_g > 0 and p["gn"] > 0 else "")
        if not grp:
            grp = f'{g["ma"]} · {g["short"]}'
            multi, xdd = xref(p)
        b = BADGE[p["xl"]]
        od = own_progress(today, p["giao"], p["due"])
        od_bar = od * base_g / p["kh"] if (len(p["parts"]) > 1 and p.get("chua") and p["kh"]) else od
        mark = "" if p["chua_giao"] or p["done"] else f'<em style="left:calc({od_bar*100:.2f}% - 1px)"></em>'
        big = pct(p["tl"])
        th = " tile-th th-cds" if "CĐS" in g["nguon"] else (" tile-th th-mtqg" if "MTQG" in g["nguon"] else "")
        ti = thong_tin(p["du_an"])
        tt_dd = (f'<div class="wide"><dt>Chủ đầu tư</dt><dd>{e(ti["cdt"])}</dd></div><div class="wide"><dt>{LOAI_TM[ti["loai"]]}</dt><dd>{vi(ti["tm"])} đ<span class="cc">{e(ti["cc"])}.</span></dd></div>') if ti else ""
        tiles.append(f'''<details class="tile tile-{b}{th}" id="{tid[id(p)]}" data-khoi="{p["khoi"]}" data-nhom="{e(" ".join(p["nhoms"]))}" data-xl="{e(p["xl"])}" data-cdt="{CDT_MA.get((thong_tin(p["du_an"]) or {}).get("cdt"), "")}">
  <summary>
    <span class="tile-top"><span class="tile-grp">{e(grp)}</span><span class="badge badge-{b}">{e(p["xl"])}</span></span>
    <span class="tile-name">{e(p["du_an"])}</span>{multi}
    <span class="tile-big">{e(big)}</span>{sub}
    <span class="bar bar-sm"><i class="{FILL[b]}" style="width:{min(100,p['tl']*100):.2f}%"></i>{mark}</span>
  </summary>
  <dl class="tile-dl">{tt_dd}<div><dt>Kế hoạch vốn</dt><dd>{vi(p["kh"])} đ</dd></div><div><dt>Đã giải ngân</dt><dd>{vi(p["gn"])} đ</dd></div><div><dt>{"Vốn dư đề nghị giảm" if p["du"] else "Còn lại"}</dt><dd>{vi(p["kh"]-p["gn"])} đ</dd></div>{('<div><dt>Chờ UBND giao chi tiết</dt><dd>' + vi(p["chua"]) + ' đ</dd></div>') if len(p["parts"]) > 1 and p.get("chua") else ''}{('<div><dt>Đã giao chi tiết</dt><dd>' + vi(p["kh_gct"]) + ' đ</dd></div>') if p["kh_gct"] else ''}<div><dt>{"Ngày phân bổ" if p["chua_giao"] else "Ngày giao vốn"}</dt><dd>{p["giao"]:%d/%m/%Y}</dd></div><div><dt>Hạn giải ngân</dt><dd>{p["due"]:%d/%m/%Y}</dd></div><div><dt>Tiến độ thời gian</dt><dd>{"" if p["chua_giao"] else pct(od)}</dd></div>{xdd}{so_do(p["du_an"])}{('<div class="wide"><dt>Tình hình thực hiện</dt><dd>' + e(p["note"]) + '</dd></div>') if p.get("note") else ''}</dl>
</details>''')

    chips_khoi = "".join(f'<button type="button" class="chip" data-f="khoi" data-v="{k}">{k}. {e(KHOI[k][0])}</button>' for k in ("A", "B"))
    chips_nhom = "".join(f'<button type="button" class="chip" data-f="nhom" data-v="{e(g["nhom"])}">{e(g["ma"])}. {e(g["short"])}</button>' for g in groups)
    # tổng hợp theo chủ đầu tư
    cdts = {}
    for p in projects:
        ti = thong_tin(p["du_an"])
        c = ti["cdt"] if ti else "Chưa xác định chủ đầu tư"
        d = cdts.setdefault(c, {"kh": 0.0, "gn": 0.0, "A": [0.0, 0.0], "B": [0.0, 0.0], "da": set(), "xl": {}})
        d["kh"] += p["kh"]; d["gn"] += p["gn"]; d[p["khoi"]][0] += p["kh"]; d[p["khoi"]][1] += p["gn"]
        d["da"].add(pkey(p["du_an"]))
    for c in cards:
        ti = thong_tin(c["du_an"])
        k = ti["cdt"] if ti else "Chưa xác định chủ đầu tư"
        cdts[k]["xl"][c["xl"]] = cdts[k]["xl"].get(c["xl"], 0) + 1
    cdt_list = sorted(cdts.items(), key=lambda kv: -kv[1]["kh"])
    cdt_cards, cdt_rows = [], []
    for i, (c, d) in enumerate(cdt_list, 1):
        tl = d["gn"] / d["kh"] if d["kh"] else 0
        xl = "đánh giá theo nguồn vốn: " + ", ".join(f"{d['xl'][k]} {k[0].lower() + k[1:]}" for k in BADGE if d["xl"].get(k))
        ab = "; ".join(f"{KHOI[k][0]} {pct(d[k][1] / d[k][0] if d[k][0] else 0)} ({ty(d[k][1])} / {ty(d[k][0])})" for k in ("A", "B") if d[k][0])
        cdt_cards.append(f'''<div class="src cdt-card" data-cdt="{CDT_MA.get(c, "")}">
  <div class="src-top"><span class="src-name"><span class="src-no">{i}</span>{e(c)}</span><span class="src-right"><span class="src-pct">{pct(tl)}</span></span></div>
  <div class="bar" role="img" aria-label="{e(c)}: {pct(tl)}"><i class="fill-cdt" style="width:{min(100, tl*100):.2f}%"></i></div>
  <p class="src-meta">Đã giải ngân {ty(d["gn"])} / {ty(d["kh"])} kế hoạch vốn, còn lại {ty(d["kh"] - d["gn"])} · {len(d["da"])} dự án ({e(xl)})</p>
  <p class="src-meta">{e(ab)}</p>
</div>''')
        cdt_rows.append(f'<tr data-cdt="{e(c)}" data-n="{len(d["da"])}"><td class="center">{i}</td><td>{e(c)}</td><td class="center">{len(d["da"])}</td>'
                        f'<td class="num">{vi(d["kh"] / 1e6)}</td><td class="num">{vi(d["gn"] / 1e6)}</td><td class="num">{pct(tl)}</td><td class="num">{vi((d["kh"] - d["gn"]) / 1e6)}</td>'
                        f'<td class="num">{vi(d["A"][0] / 1e6)}</td><td class="num">{vi(d["A"][1] / 1e6)}</td><td class="num">{vi(d["B"][0] / 1e6)}</td><td class="num">{vi(d["B"][1] / 1e6)}</td></tr>')
    n_da = len({pkey(p["du_an"]) for p in projects})
    cdt_rows.append(f'<tr class="sub"><td></td><td>Tổng cộng</td><td class="center">{n_da}</td><td class="num">{vi(t["kh"] / 1e6)}</td><td class="num">{vi(t["gn"] / 1e6)}</td><td class="num">{pct(t["gn"] / t["kh"] if t["kh"] else 0)}</td><td class="num">{vi((t["kh"] - t["gn"]) / 1e6)}</td>'
                    f'<td class="num">{vi(blk["A"]["kh"] / 1e6)}</td><td class="num">{vi(blk["A"]["gn"] / 1e6)}</td><td class="num">{vi(blk["B"]["kh"] / 1e6)}</td><td class="num">{vi(blk["B"]["gn"] / 1e6)}</td></tr>')
    chips_cdt = "".join(f'<button type="button" class="chip" data-f="cdt" data-v="{CDT_MA[c]}">{e(c)}</button>' for c, _ in cdt_list if c in CDT_MA)

    chips_xl = "".join(f'<button type="button" class="chip" data-f="xl" data-v="{k}">{k} · {cnt[k]}</button>' for k in BADGE if cnt[k])

    def tr(x):  # bảng chi tiết: đơn vị triệu đồng, làm tròn
        return vi(x / 1e6)

    def tm_cells(du_an):
        ti = thong_tin(du_an)
        if not ti:
            return '<td class="cdt"></td><td class="num"></td>'
        cdt = CDT_NGAN.get(ti["cdt"], ti["cdt"])
        return (f'<td class="cdt" title="{e(ti["cdt"])}">{e(cdt)}</td>'
                f'<td class="num" title="{e(ti["cc"])}" data-v="{ti["tm"]:.0f}">{tr(ti["tm"])}{DAU_TM[ti["loai"]]}</td>')

    def sub_row(label, x):
        return f'<tr class="sub"><td></td><td>{e(label)}</td><td></td><td></td><td class="num" data-v="{x["kh"]:.0f}">{tr(x["kh"])}</td><td class="num" data-v="{x["gn"]:.0f}">{tr(x["gn"])}</td><td class="num" data-v="{x["tl"]:.6f}">{pct(x["tl"])}</td><td></td><td class="pr"></td></tr>'

    # bản in: thêm tình hình thực hiện, chủ đầu tư và quyết định làm căn cứ dưới tên dự án
    nmap = {pkey(c["du_an"]): c.get("note") or "" for c in cards}

    def pr_sub(du_an):
        ti = thong_tin(du_an)
        if not ti:
            return ""
        return f'<span class="pr-sub">Chủ đầu tư: {e(CDT_NGAN.get(ti["cdt"], ti["cdt"]))}. {e(ti["cc"])}.</span>'

    def pr_note(p):
        return f'<td class="pr pr-note">{e(p.get("note") or nmap.get(pkey(p["du_an"]), ""))}</td>'

    body_rows = []
    for k in ("A", "B"):
        body_rows.append(f'<tr class="khoi"><td colspan="9">{k}. {e(KHOI[k][0]).upper()}</td></tr>')
        last_sub = None
        for g in blk[k]["gs"]:
            if g["sub"] and g["sub"] != last_sub:
                if last_sub:
                    body_rows.append(sub_row("Cộng " + SUB_B[last_sub].lower(), subs[last_sub]))
                body_rows.append(f'<tr class="grp2"><td colspan="9">{e(SUB_B[g["sub"]])}</td></tr>')
                last_sub = g["sub"]
            body_rows.append(f'<tr class="grp"><td colspan="9">{e(g["ma"])}. {e(g["long"])}<span class="pr"> (hạn giải ngân {g["due"]:%d/%m/%Y})</span></td></tr>')
            for p in [p for p in projects if p["nhom"] == g["nhom"]]:
                body_rows.append(f'<tr><td class="center">{p["stt"]}</td><td>{e(p["du_an"])}{pr_sub(p["du_an"])}</td>{tm_cells(p["du_an"])}<td class="num" data-v="{p["kh"]:.0f}">{tr(p["kh"])}</td><td class="num" data-v="{p["gn"]:.0f}">{tr(p["gn"])}</td><td class="num" data-v="{p["tl"]:.6f}">{pct(p["tl"])}</td><td><span class="badge badge-{BADGE[p["xl"]]}">{e(p["xl"])}</span></td>{pr_note(p)}</tr>')
        if last_sub:
            body_rows.append(sub_row("Cộng " + SUB_B[last_sub].lower(), subs[last_sub]))
        body_rows.append(sub_row(f"Cộng khối {k}", blk[k]))

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
        cnt_dat=cnt["Đạt tiến độ"], cnt_cham=cnt["Chậm tiến độ"], cnt_cb=cnt["Cấp bách"], cnt_chua=cnt["Chờ UBND giao chi tiết"], cnt_qt=cnt["Đã quyết toán"], cnt_new=cnt["Mới giao chi tiết"], b_cut="30/9/2026",
        trend=trend_svg(daily, today, kh_ref, {g["nhom"] for g in g_due26}),
        bars_w=bars_svg(weeks, "Giải ngân theo tuần"), bars_m=bars_svg(months, "Giải ngân theo tháng"), bars_q=bars_svg(quarters, "Giải ngân theo quý"),
        tab_w=period_table(weeks), tab_m=period_table(months), tab_q=period_table(quarters),
        need_rows="\n".join(need_rows), need_left=ty(sum(g["w_left0"] for g in groups), False), need_per=ty(per_day, False), per_day_num=ty(per_day, False), need_in=ty(w_in_all, False), need_pct=wpct(w_in_all, per_day), w_this=f"{monday:%d/%m} đến {monday + dt.timedelta(days=6):%d/%m}", w_in_txt=ty(w_in_all), w_bar=f"{w_bar:.1f}", w_cmp=e(w_cmp),
        sources="\n".join(src), tiles="\n".join(tiles), chips_khoi=chips_khoi, chips_nhom=chips_nhom, chips_xl=chips_xl,
        rows="\n".join(body_rows), cdt_cards="\n".join(cdt_cards), cdt_rows="\n".join(cdt_rows), chips_cdt=chips_cdt, **{"opt_" + k: re.sub(r'<button type="button" class="chip" data-f="\w+" data-v="([^"]*)">(.*?)</button>', r'<option value="\1">\2</option>', v) for k, v in (("khoi", chips_khoi), ("nhom", chips_nhom), ("cdt", chips_cdt), ("xl", chips_xl))}, n_cdt=len(cdt_list), f_kh=vi(t["kh"] / 1e6), f_gn=vi(t["gn"] / 1e6), f_tl=pct(t["gn"] / t["kh"] if t["kh"] else 0), v_kh="%.0f" % t["kh"], v_gn="%.0f" % t["gn"], v_tl="%.6f" % (t["gn"] / t["kh"] if t["kh"] else 0),
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
