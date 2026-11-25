#!/usr/bin/env python3
"""Nạp 5 file CSV vào MongoDB theo mô hình Hybrid (nhúng + tham chiếu).

Ví dụ:
    py -3.12 04_load_mongodb.py --data-dir data\\1m
    py -3.12 04_load_mongodb.py --data-dir data\\100k --uri mongodb://localhost:27017

Thiết kế collection (database quan_ly_nhan_khau):
- citizens        : 1 document / nhân khẩu, _id = id nhân khẩu (khớp MySQL).
                    Nhúng thông tin hộ (ho_khau_id, quan_he, tu_ngay) và mảng
                    tam_tru_tam_vang (số lượng nhỏ, luôn đọc cùng hồ sơ).
- households      : 1 document / hộ, _id = id hộ. Nhúng snapshot thành viên
                    (citizenId, cccd, ho_ten, quan_he) để đọc hộ không cần join.
- population_logs : biến động, tách riêng vì tăng không giới hạn theo thời gian;
                    tham chiếu bằng nhan_khau_id (+ cccd để tra nhanh).

Script XÓA và tạo lại 3 collection trên mỗi lần chạy. Index được tạo SAU khi
nạp xong (nhanh hơn so với duy trì index trong lúc insert).
"""
import argparse
import csv
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from pymongo import ASCENDING, DESCENDING, MongoClient

BATCH_SIZE = 10_000


def to_date(value: str):
    """'YYYY-MM-DD' -> datetime (BSON Date); chuỗi rỗng -> None (tương đương NULL)."""
    return datetime.strptime(value, "%Y-%m-%d") if value else None


def read_csv(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def insert_batches(collection, docs) -> int:
    """insert_many theo lô, ordered=False để server ghi song song."""
    total, batch = 0, []
    for doc in docs:
        batch.append(doc)
        if len(batch) >= BATCH_SIZE:
            collection.insert_many(batch, ordered=False)
            total += len(batch)
            batch.clear()
    if batch:
        collection.insert_many(batch, ordered=False)
        total += len(batch)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Nạp CSV quản lý nhân khẩu vào MongoDB (Hybrid).")
    parser.add_argument("--data-dir", type=Path, default=Path("data/1m"))
    parser.add_argument("--uri", default="mongodb://localhost:27017")
    parser.add_argument("--db", default="quan_ly_nhan_khau")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # tránh lỗi in tiếng Việt trên console cp1252

    client = MongoClient(args.uri)
    db = client[args.db]
    timings: dict[str, float] = {}

    # ---- Đọc các bảng phụ vào bộ nhớ để nhúng ----
    t0 = time.perf_counter()
    membership = {}  # nhan_khau_id -> (ho_khau_id, quan_he, tu_ngay)
    for row in read_csv(args.data_dir / "thanh_vien_ho.csv"):
        membership[int(row["nhan_khau_id"])] = (int(row["ho_khau_id"]), row["quan_he"], to_date(row["tu_ngay"]))

    residence = defaultdict(list)  # nhan_khau_id -> [hồ sơ tạm trú/tạm vắng]
    for row in read_csv(args.data_dir / "tam_tru_tam_vang.csv"):
        residence[int(row["nhan_khau_id"])].append({
            "id": int(row["id"]),
            "loai": row["loai"],
            "dia_chi_lien_quan": row["dia_chi_lien_quan"],
            "tu_ngay": to_date(row["tu_ngay"]),
            "den_ngay": to_date(row["den_ngay"]),
            "ly_do": row["ly_do"] or None,
            "trang_thai": row["trang_thai"],
        })
    timings["doc_bang_phu"] = time.perf_counter() - t0

    for name in ("citizens", "households", "population_logs"):
        db.drop_collection(name)

    # ---- citizens ----
    members_by_household = defaultdict(list)
    cccd_by_id = {}  # dùng để gắn CCCD vào population_logs

    def citizen_docs():
        for row in read_csv(args.data_dir / "nhan_khau.csv"):
            cid = int(row["id"])
            cccd_by_id[cid] = row["cccd"]
            hid, relation, joined = membership[cid]
            members_by_household[hid].append({"citizenId": cid, "cccd": row["cccd"], "ho_ten": row["ho_ten"], "quan_he": relation})
            yield {
                "_id": cid,
                "cccd": row["cccd"],
                "ho_ten": row["ho_ten"],
                "ngay_sinh": to_date(row["ngay_sinh"]),
                "gioi_tinh": row["gioi_tinh"],
                "que_quan": row["que_quan"],
                "nghe_nghiep": row["nghe_nghiep"] or None,
                "ngay_dang_ky": to_date(row["ngay_dang_ky"]),
                "ho_khau": {"ho_khau_id": hid, "quan_he": relation, "tu_ngay": joined},
                "tam_tru_tam_vang": residence.get(cid, []),
            }

    t0 = time.perf_counter()
    n_citizens = insert_batches(db.citizens, citizen_docs())
    timings["insert_citizens"] = time.perf_counter() - t0

    # ---- households ----
    def household_docs():
        for row in read_csv(args.data_dir / "ho_khau.csv"):
            hid = int(row["id"])
            yield {
                "_id": hid,
                "ma_ho": row["ma_ho"],
                "dia_chi": row["dia_chi"],
                "chu_ho_id": int(row["chu_ho_id"]),
                "ngay_lap": to_date(row["ngay_lap"]),
                "members": sorted(members_by_household.get(hid, []), key=lambda m: m["citizenId"]),
            }

    t0 = time.perf_counter()
    n_households = insert_batches(db.households, household_docs())
    timings["insert_households"] = time.perf_counter() - t0

    # ---- population_logs ----
    def log_docs():
        for row in read_csv(args.data_dir / "bien_dong.csv"):
            cid = int(row["nhan_khau_id"])
            yield {
                "_id": int(row["id"]),
                "nhan_khau_id": cid,
                "cccd": cccd_by_id[cid],
                "loai_bien_dong": row["loai_bien_dong"],
                "ngay_bien_dong": to_date(row["ngay_bien_dong"]),
                "noi_dung": row["noi_dung"],
                "nguoi_thuc_hien": row["nguoi_thuc_hien"] or None,
            }

    t0 = time.perf_counter()
    n_logs = insert_batches(db.population_logs, log_docs())
    timings["insert_population_logs"] = time.perf_counter() - t0

    # ---- Index tương ứng với index PRIMARY/UNIQUE/KEY của MySQL ----
    # (index phụ cho Q1-Q8 được tạo/xóa trong 05_queries_mongodb.js; 06_benchmark.py có bộ index riêng).
    t0 = time.perf_counter()
    db.citizens.create_index([("cccd", ASCENDING)], unique=True, name="uq_cccd")
    db.citizens.create_index([("ho_khau.ho_khau_id", ASCENDING)], name="ix_ho_khau_id")
    db.households.create_index([("ma_ho", ASCENDING)], unique=True, name="uq_ma_ho")
    db.households.create_index([("chu_ho_id", ASCENDING)], name="ix_chu_ho")
    db.households.create_index([("members.citizenId", ASCENDING)], name="ix_members_citizen")
    db.population_logs.create_index([("nhan_khau_id", ASCENDING), ("ngay_bien_dong", DESCENDING)], name="ix_log_nk_ngay")
    db.population_logs.create_index([("cccd", ASCENDING), ("ngay_bien_dong", DESCENDING)], name="ix_log_cccd_ngay")
    timings["create_indexes"] = time.perf_counter() - t0

    # Đối chiếu số document thực tế trên server với số đã gửi.
    expected = {"citizens": n_citizens, "households": n_households, "population_logs": n_logs}
    for name, count in expected.items():
        actual = db[name].count_documents({})
        if actual != count:
            raise SystemExit(f"LỖI: {name} có {actual:,} document, kỳ vọng {count:,}. "
                             "Có tiến trình khác (vd. Compass) xóa/sửa DB trong lúc nạp? Hãy chạy lại.")

    print(f"citizens={n_citizens:,}  households={n_households:,}  population_logs={n_logs:,}  (đã đối chiếu)")
    print("Thời gian (giây):")
    for step, seconds in timings.items():
        print(f"  {step:<24}{seconds:8.2f}")
    print(f"  {'TONG':<24}{sum(timings.values()):8.2f}")

    # Ép WiredTiger ghi checkpoint xuống đĩa, nếu không storageSize có thể còn bằng 0.
    client.admin.command("fsync")
    print("Dung lượng (MB):  data(uncompressed) | storage(nén) | index")
    for name in ("citizens", "households", "population_logs"):
        s = db.command("collStats", name)
        print(f"  {name:<16}{s['size'] / 2**20:10.1f} {s['storageSize'] / 2**20:12.1f} {s['totalIndexSize'] / 2**20:9.1f}")


if __name__ == "__main__":
    main()
