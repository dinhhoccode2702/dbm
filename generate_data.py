#!/usr/bin/env python3
"""Sinh CSV dữ liệu mẫu nhất quán cho cả 5 bảng MySQL (dùng chung cho MongoDB).

Ví dụ:
    py -3.12 generate_data.py --count 1000000 --output-dir data\\1m
    py -3.12 generate_data.py --count 100000  --output-dir data\\100k

Ràng buộc nghiệp vụ được bảo đảm:
- Mỗi nhân khẩu thuộc đúng một hộ. Hộ có id = h gồm các nhân khẩu h, h+N, h+2N, h+3N
  (N = số hộ); vị trí 0 là chủ hộ, vị trí 1 là vợ/chồng, vị trí 2+ là con/cha mẹ/anh chị em.
- Chủ hộ đủ 18 tuổi khi lập hộ; vợ/chồng khác giới, chênh tuổi <= 5 và đủ 18 tuổi khi vào hộ.
- Con sinh sau chủ hộ 18-45 năm, mang họ cha; cha/mẹ hơn chủ hộ 20-40 tuổi; cha mang họ chủ hộ.
- Số CCCD 12 số theo cấu trúc số định danh cá nhân: mã tỉnh khai sinh (3) + mã giới tính
  và thế kỷ sinh (1) + 2 số cuối năm sinh (2) + số ngẫu nhiên (6), không trùng.
- Ngày đăng ký, ngày vào hộ, tạm trú/tạm vắng, biến động đều không trước ngày sinh.
- Biến động "Sinh" trùng đúng ngày sinh; chỉ sinh cho người sinh từ 2010 (giai đoạn có dữ liệu).
"""
import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

FIRST_NAMES = ("An", "Binh", "Chau", "Dung", "Giang", "Ha", "Hung", "Khanh", "Linh", "Minh", "Nam", "Phuong", "Quang", "Trang", "Tuan")
MIDDLE_MALE = ("Van", "Duc", "Hoang", "Gia", "Thanh", "Bao", "Minh")
MIDDLE_FEMALE = ("Thi", "Ngoc", "Thanh", "Bao", "Gia", "Thu", "Kim")
LAST_NAMES = ("Nguyen", "Tran", "Le", "Pham", "Hoang", "Huynh", "Phan", "Vu", "Vo", "Dang")
# Tỉnh -> mã tỉnh trong số định danh cá nhân (3 chữ số đầu của CCCD).
PROVINCE_CODES = {
    "Ha Noi": "001", "Quang Ninh": "022", "Hai Phong": "031", "Nghe An": "040", "Da Nang": "048",
    "Khanh Hoa": "056", "Binh Duong": "074", "Dong Nai": "075", "Ho Chi Minh": "079", "Can Tho": "092",
}
PROVINCES = tuple(PROVINCE_CODES)
JOBS = ("Giao vien", "Ky su", "Nhan vien", "Bac si", "Cong nhan", "Kinh doanh", "Lao dong tu do", "Nong dan")
REASONS = ("Hoc tap", "Cong tac", "Thay doi noi o", "Ly do gia dinh")
END_OF_DATA = date(2026, 12, 31)
LAST_BIRTH = date(2025, 12, 31)


def random_date(rng: random.Random, first: date, last: date) -> date:
    """Ngày ngẫu nhiên trong [first, last] (bao gồm hai đầu)."""
    if last <= first:
        return first
    return first + timedelta(days=rng.randrange((last - first).days + 1))


def years(n: int) -> timedelta:
    return timedelta(days=round(365.25 * n))


def household_date(household_id: int) -> date:
    """Ngày lập hộ ổn định theo ID, nằm trong 1990-2010."""
    first = date(1990, 1, 1)
    span = (date(2010, 12, 31) - first).days + 1
    return first + timedelta(days=(household_id * 37) % span)


def job_for(rng: random.Random, birth: date) -> str:
    """Nghề nghiệp theo độ tuổi (tính tại 2026)."""
    age = 2026 - birth.year
    if age < 6:
        return "Tre em"
    if age < 18:
        return "Hoc sinh"
    if age < 23 and rng.random() < 0.6:
        return "Sinh vien"
    if age >= 62:
        return "Nghi huu"
    return rng.choice(JOBS)


def open_csv(path: Path):
    """Mở CSV UTF-8 để ghi; bộ đệm lớn giúp ghi hàng triệu dòng hiệu quả hơn."""
    return path.open("w", encoding="utf-8", newline="", buffering=1024 * 1024)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh dữ liệu CSV nhất quán cho 5 bảng quản lý nhân khẩu.")
    parser.add_argument("--count", type=int, choices=(100_000, 1_000_000, 10_000_000), default=100_000, help="Số nhân khẩu cần sinh")
    parser.add_argument("--output-dir", type=Path, default=Path("data"), help="Thư mục lưu năm file CSV")
    parser.add_argument("--seed", type=int, default=20261018, help="Seed để có thể tái tạo cùng bộ dữ liệu")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # tránh lỗi in tiếng Việt trên console cp1252

    rng = random.Random(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    household_count = (args.count + 3) // 4  # Trung bình 4 người/hộ.

    births: list[date] = [date.min] * (args.count + 1)
    relations: list[str] = [""] * (args.count + 1)
    head_sex: list[str] = [""] * (household_count + 1)
    head_last: list[str] = [""] * (household_count + 1)
    family_last: list[str] = [""] * (household_count + 1)  # họ của người cha trong hộ -> họ của con
    cccd_seq: dict[str, int] = {}

    # 1. Hộ khẩu: chu_ho_id trỏ tới nhân khẩu có ID cùng số.
    with open_csv(args.output_dir / "ho_khau.csv") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("id", "ma_ho", "dia_chi", "chu_ho_id", "ngay_lap"))
        for hid in range(1, household_count + 1):
            province = PROVINCES[(hid - 1) % len(PROVINCES)]
            writer.writerow((hid, f"HK{hid:010d}", f"So {hid} Duong {province}, {province}", hid, household_date(hid).isoformat()))

    # 2. Nhân khẩu: tuổi, giới tính, họ phụ thuộc vị trí trong hộ.
    with open_csv(args.output_dir / "nhan_khau.csv") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("id", "cccd", "ho_ten", "ngay_sinh", "gioi_tinh", "que_quan", "nghe_nghiep", "ngay_dang_ky"))
        for cid in range(1, args.count + 1):
            hid = ((cid - 1) % household_count) + 1
            position = (cid - 1) // household_count
            head_birth = births[hid] if position > 0 else None
            founded = household_date(hid)

            if position == 0:
                relation = "Chu ho"
                sex = "Nam" if rng.random() < 0.7 else "Nu"
                birth = random_date(rng, date(1940, 1, 1), min(date(1972, 12, 31), founded - years(18)))
                last = rng.choice(LAST_NAMES)
                head_sex[hid], head_last[hid] = sex, last
                if sex == "Nam":
                    family_last[hid] = last
            elif position == 1:
                relation = "Vo chong"
                sex = "Nu" if head_sex[hid] == "Nam" else "Nam"
                birth = random_date(rng, head_birth - years(5), min(head_birth + years(5), founded - years(18)))
                last = rng.choice(LAST_NAMES)
                if sex == "Nam":
                    family_last[hid] = last
            else:
                sex = rng.choice(("Nam", "Nu"))
                roll = rng.random()
                if head_birth.year >= 1960 and roll < 0.15:
                    relation = "Cha me"
                    birth = random_date(rng, head_birth - years(40), head_birth - years(20))
                    last = head_last[hid] if sex == "Nam" else rng.choice(LAST_NAMES)
                elif roll < 0.25:
                    relation = "Anh chi em"
                    birth = random_date(rng, head_birth - years(10), min(head_birth + years(10), LAST_BIRTH))
                    last = head_last[hid]
                else:
                    relation = "Con"
                    birth = random_date(rng, head_birth + years(18), min(head_birth + years(45), LAST_BIRTH))
                    last = family_last[hid] or head_last[hid]

            births[cid], relations[cid] = birth, relation
            middle = rng.choice(MIDDLE_MALE if sex == "Nam" else MIDDLE_FEMALE)
            hometown = rng.choice(PROVINCES)
            # Mã giới tính + thế kỷ: 0/1 = nam/nữ sinh thế kỷ 20, 2/3 = nam/nữ sinh thế kỷ 21.
            century_sex = (0 if birth.year < 2000 else 2) + (0 if sex == "Nam" else 1)
            prefix = f"{PROVINCE_CODES[hometown]}{century_sex}{birth.year % 100:02d}"
            cccd_seq[prefix] = cccd_seq.get(prefix, 0) + 1
            cccd = f"{prefix}{cccd_seq[prefix]:06d}"
            registered = random_date(rng, max(birth, date(2000, 1, 1)), END_OF_DATA)
            writer.writerow((cid, cccd, f"{last} {middle} {rng.choice(FIRST_NAMES)}", birth.isoformat(), sex, hometown, job_for(rng, birth), registered.isoformat()))

    # 3. Thành viên hộ: vào hộ khi hộ lập hoặc khi sinh ra (lấy ngày muộn hơn).
    with open_csv(args.output_dir / "thanh_vien_ho.csv") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("id", "ho_khau_id", "nhan_khau_id", "quan_he", "tu_ngay", "den_ngay"))
        for cid in range(1, args.count + 1):
            hid = ((cid - 1) % household_count) + 1
            writer.writerow((cid, hid, cid, relations[cid], max(household_date(hid), births[cid]).isoformat(), ""))

    # 4. Tạm trú/tạm vắng: một hồ sơ cho mỗi 10 người; ~80% đã kết thúc, ~20% đang hiệu lực.
    with open_csv(args.output_dir / "tam_tru_tam_vang.csv") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("id", "nhan_khau_id", "loai", "dia_chi_lien_quan", "tu_ngay", "den_ngay", "ly_do", "trang_thai"))
        record_id = 0
        for cid in range(10, args.count + 1, 10):
            record_id += 1
            start = random_date(rng, max(births[cid], date(2010, 1, 1)), END_OF_DATA)
            if rng.random() < 0.8:
                status, end = "Da ket thuc", random_date(rng, start, END_OF_DATA).isoformat()
            else:
                status, end = "Dang hieu luc", ""
            writer.writerow((record_id, cid, "Tam tru" if record_id % 2 else "Tam vang", f"So {cid} Duong {PROVINCES[cid % len(PROVINCES)]}, {PROVINCES[cid % len(PROVINCES)]}", start.isoformat(), end, rng.choice(REASONS), status))

    # 5. Biến động: một sự kiện cho mỗi 5 người. Người sinh từ 2010 có sự kiện "Sinh" đúng ngày sinh;
    # người khác có chuyển đến / chuyển đi / đổi thông tin. Không sinh "Tu" vì bảng nhân khẩu
    # không có trạng thái đã mất (tránh người đã mất vẫn còn trong hộ).
    with open_csv(args.output_dir / "bien_dong.csv") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("id", "nhan_khau_id", "loai_bien_dong", "ngay_bien_dong", "noi_dung", "nguoi_thuc_hien"))
        record_id = 0
        for cid in range(5, args.count + 1, 5):
            record_id += 1
            if births[cid].year >= 2010:
                event_type, when = "Sinh", births[cid]
            else:
                event_type = ("Chuyen den", "Chuyen di", "Doi thong tin")[record_id % 3]
                when = random_date(rng, max(births[cid], date(2010, 1, 1)), END_OF_DATA)
            writer.writerow((record_id, cid, event_type, when.isoformat(), f"Dang ky bien dong {event_type.lower()} cho nhan khau {cid}", "Can bo tu phap ho tich"))

    print(f"Đã tạo {args.count:,} nhân khẩu và {household_count:,} hộ khẩu trong {args.output_dir}")


if __name__ == "__main__":
    main()
