#!/usr/bin/env python3
"""Benchmark MySQL và MongoDB trên cùng bộ dữ liệu quản lý nhân khẩu.

Ví dụ:
    py -3.12 06_benchmark.py --label 1m
    py -3.12 06_benchmark.py --label 100k --modes with_index
    py -3.12 06_benchmark.py --label 1m --quick          # chạy thử nhanh, ít lần lặp

Yêu cầu: đã nạp CÙNG một bộ CSV vào cả hai DB (02_load_mysql*.sql và 04_load_mongodb.py).
Thông tin kết nối MySQL lấy từ file .env (DB_HOST, DB_PORT, DB_DATABASE, DB_USERNAME, DB_PASSWORD).

Cách đo:
- Mỗi thao tác chạy vài lần "làm nóng" (không tính), sau đó đo N lần. Mỗi lần dùng một tham số
  khác nhau (CCCD, mã hộ...) lấy ngẫu nhiên theo seed cố định, nên hai hệ nhận đúng cùng tham số.
- Thời gian đo là thời gian phía client: gửi truy vấn, chờ server xử lý, nhận về TOÀN BỘ kết quả.
- Có 2 chế độ index: no_index (chỉ PK/unique/FK như lúc nạp) và with_index (thêm index phụ).
- Thao tác ghi chỉ tác động lên bản ghi thử nghiệm (id >= TEST_BASE) và được dọn sạch sau khi đo,
  nên dữ liệu gốc không bị thay đổi.
- Ghi MongoDB dùng write concern j=True (chờ ghi journal) để có cùng mức bền vững với
  MySQL innodb_flush_log_at_trx_commit=1 (fsync redo log mỗi lần commit).
- MongoDB chạy standalone (không phải replica set) nên KHÔNG có multi-document transaction:
  các thao tác ghi nhiều collection là các lệnh riêng lẻ, MySQL thì bọc trong 1 transaction.

Kết quả: results/bench_<label>_<thời gian>.csv (+ .json môi trường, + plans .csv).
Vẽ biểu đồ: py -3.12 07_plot_results.py results/bench_....csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import re
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pymysql
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, WriteConcern

TEST_BASE = 900_000_000        # id >= mốc này là dữ liệu thử nghiệm của benchmark
SEED = 20261125
PROVINCE_RANGE = ("Ha", "Hb")  # khớp 'Ha Noi', 'Hai Phong'
NAME_PREFIXES = ("Nguyen Van A", "Tran Thi H", "Le Duc M", "Pham Ngoc T", "Hoang Gia B", "Vu Thanh K", "Dang Van N", "Phan Thi L")

# Index phụ được bật/tắt giữa 2 chế độ. Hai bên tương đương nhau.
MYSQL_EXTRA_INDEXES = {
    ("nhan_khau", "ix_nhan_khau_ho_ten"): "CREATE INDEX ix_nhan_khau_ho_ten ON nhan_khau (ho_ten)",
    ("nhan_khau", "ix_nhan_khau_que_quan"): "CREATE INDEX ix_nhan_khau_que_quan ON nhan_khau (que_quan)",
    ("tam_tru_tam_vang", "ix_tttv_trang_thai_loai"): "CREATE INDEX ix_tttv_trang_thai_loai ON tam_tru_tam_vang (trang_thai, loai)",
}
MONGO_EXTRA_INDEXES = {
    "ix_ho_ten": [("ho_ten", ASCENDING)],
    "ix_que_quan": [("que_quan", ASCENDING)],
    "ix_tttv_trang_thai_loai": [("tam_tru_tam_vang.trang_thai", ASCENDING), ("tam_tru_tam_vang.loai", ASCENDING)],
}


# ---------------------------------------------------------------- kết nối & môi trường
def connect_mysql() -> pymysql.connections.Connection:
    load_dotenv(Path(__file__).with_name(".env"))
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USERNAME", "root"), password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_DATABASE", "quan_ly_nhan_khau"), charset="utf8mb4", autocommit=True,
    )


def mysql_all(conn, sql: str, params: Any = None) -> list:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def set_cache(conn, mdb, gb: float) -> None:
    """Cấp cùng dung lượng cache cho InnoDB buffer pool và WiredTiger (hiệu lực tới khi restart)."""
    size = int(gb * 1024**3)
    with conn.cursor() as cur:
        cur.execute("SET GLOBAL innodb_buffer_pool_size = %s", (size,))
    # Buffer pool đổi kích thước bất đồng bộ; chờ hoàn tất.
    for _ in range(120):
        status = mysql_all(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_resize_status'")
        if not status or "Completed" in status[0][1] or status[0][1] == "":
            break
        time.sleep(0.5)
    mdb.client.admin.command({"setParameter": 1, "wiredTigerEngineRuntimeConfig": f"cache_size={int(gb * 1024)}M"})


def environment(conn, mdb) -> dict:
    mysql_vars = dict(mysql_all(conn, "SHOW GLOBAL VARIABLES WHERE Variable_name IN "
                                      "('version','innodb_buffer_pool_size','innodb_flush_log_at_trx_commit')"))
    status = mdb.client.admin.command("serverStatus")
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "machine": platform.processor() or platform.machine(), "os": platform.platform(),
        "cpu_count": os.cpu_count(), "python": platform.python_version(),
        "pymysql": pymysql.__version__, "pymongo": __import__("pymongo").version,
        "mysql_version": mysql_vars.get("version"),
        "mysql_buffer_pool_mb": int(mysql_vars.get("innodb_buffer_pool_size", 0)) // 2**20,
        "mysql_flush_log_at_trx_commit": mysql_vars.get("innodb_flush_log_at_trx_commit"),
        "mongo_version": status["version"],
        "mongo_wt_cache_mb": int(status["wiredTiger"]["cache"]["maximum bytes configured"]) // 2**20,
        "mongo_write_concern": "w=1, j=True",
    }


def set_index_mode(conn, mdb, mode: str) -> None:
    existing = {(t, i) for t, i in mysql_all(conn, "SELECT DISTINCT table_name, index_name FROM information_schema.statistics WHERE table_schema = DATABASE()")}
    for (table, name), ddl in MYSQL_EXTRA_INDEXES.items():
        if mode == "with_index" and (table, name) not in existing:
            mysql_all(conn, ddl)
        if mode == "no_index" and (table, name) in existing:
            mysql_all(conn, f"DROP INDEX {name} ON {table}")
    mysql_all(conn, "ANALYZE TABLE nhan_khau, tam_tru_tam_vang")
    mongo_existing = {ix["name"] for ix in mdb.citizens.list_indexes()}
    for name, keys in MONGO_EXTRA_INDEXES.items():
        if mode == "with_index" and name not in mongo_existing:
            mdb.citizens.create_index(keys, name=name)
        if mode == "no_index" and name in mongo_existing:
            mdb.citizens.drop_index(name)


def cleanup_test_data(conn, mdb) -> None:
    """Xóa mọi bản ghi thử nghiệm (id >= TEST_BASE), kể cả từ lần chạy bị ngắt giữa chừng."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM bien_dong WHERE id >= %s OR nhan_khau_id >= %s", (TEST_BASE, TEST_BASE))
        cur.execute("DELETE FROM thanh_vien_ho WHERE nhan_khau_id >= %s", (TEST_BASE,))
        cur.execute("DELETE FROM nhan_khau WHERE id >= %s", (TEST_BASE,))
    mdb.population_logs.delete_many({"$or": [{"_id": {"$gte": TEST_BASE}}, {"nhan_khau_id": {"$gte": TEST_BASE}}]})
    mdb.citizens.delete_many({"_id": {"$gte": TEST_BASE}})
    mdb.households.update_many({"members.citizenId": {"$gte": TEST_BASE}},
                               {"$pull": {"members": {"citizenId": {"$gte": TEST_BASE}}}})


# ---------------------------------------------------------------- định nghĩa thao tác
@dataclass
class Op:
    code: str
    group: str                       # read / aggregate / join / write
    title: str                       # mô tả tiếng Việt cho báo cáo
    reps: int
    params: Callable[[int], list]    # n -> danh sách tham số (một tham số mỗi lần chạy)
    mysql: Callable | None
    mongo: Callable | None
    mysql_plan: Callable | None = None
    mongo_plan: Callable | None = None
    warmup: int = 3


def mysql_explain(conn, sql: str, params: Any) -> str:
    rows = mysql_all(conn, "EXPLAIN " + sql, params)
    # cột: id, select_type, table, partitions, type, possible_keys, key, key_len, ref, rows, filtered, Extra
    return " | ".join(f"{r[2]}:{r[4]}:{r[6] or '-'}" for r in rows)


def _find_key(obj: Any, key: str) -> Any:
    """Tìm giá trị đầu tiên của khóa `key` trong cấu trúc dict/list lồng nhau."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for child in children:
        found = _find_key(child, key)
        if found is not None:
            return found
    return None


def mongo_stages(explain_doc: dict) -> str:
    """Tên các stage của winning plan (bỏ qua rejectedPlans), vd 'FETCH>IXSCAN'."""
    stages = re.findall(r"'stage': '(\w+)'", str(_find_key(explain_doc, "winningPlan")))
    return ">".join(dict.fromkeys(stages)) or "-"


def mongo_agg_explain(mdb, coll: str, pipeline: list) -> str:
    doc = mdb.command({"explain": {"aggregate": coll, "pipeline": pipeline, "cursor": {}}, "verbosity": "queryPlanner"})
    pipeline_stages = [next(iter(s)) for s in doc.get("stages", [])]
    prefix = "[" + ",".join(pipeline_stages) + "] " if pipeline_stages else ""
    return prefix + mongo_stages(doc)


def build_ops(conn, mdb, max_citizen: int, max_household: int, quick: bool) -> list[Op]:
    rng = random.Random(SEED)
    scale = 0.2 if quick else 1.0
    r = lambda n: max(3, int(n * scale))

    def sample_ids(n: int, step: int = 1) -> list[int]:
        return [rng.randrange(1, max_citizen // step + 1) * step for _ in range(n)]

    def cccds_of(ids: list[int]) -> list[str]:
        found = dict(mysql_all(conn, f"SELECT id, cccd FROM nhan_khau WHERE id IN ({','.join(map(str, set(ids)))})"))
        return [found[i] for i in ids]

    ops: list[Op] = []

    # R1. Tra cứu nhân khẩu theo CCCD.
    sql_r1 = "SELECT id, cccd, ho_ten, ngay_sinh, gioi_tinh, que_quan FROM nhan_khau WHERE cccd = %s"
    proj_r1 = {"cccd": 1, "ho_ten": 1, "ngay_sinh": 1, "gioi_tinh": 1, "que_quan": 1}
    ops.append(Op("R1", "read", "Tra cứu nhân khẩu theo CCCD", r(300),
                  lambda n: cccds_of(sample_ids(n)),
                  lambda p: mysql_all(conn, sql_r1, (p,)),
                  lambda p: [mdb.citizens.find_one({"cccd": p}, proj_r1)],
                  lambda p: mysql_explain(conn, sql_r1, (p,)),
                  lambda p: mongo_stages(mdb.citizens.find({"cccd": p}, proj_r1).explain())))

    # R2. Tìm theo tiền tố họ tên + quê quán (Ha Noi, Hai Phong), sắp theo tên, 100 kết quả.
    sql_r2 = ("SELECT id, ho_ten, que_quan FROM nhan_khau WHERE ho_ten LIKE %s AND que_quan >= %s AND que_quan < %s "
              "ORDER BY ho_ten LIMIT 100")
    def mongo_r2_cursor(p):
        return (mdb.citizens.find({"ho_ten": {"$regex": "^" + re.escape(p)}, "que_quan": {"$gte": PROVINCE_RANGE[0], "$lt": PROVINCE_RANGE[1]}},
                                  {"ho_ten": 1, "que_quan": 1}).sort("ho_ten", 1).limit(100))
    ops.append(Op("R2", "read", "Tìm theo tiền tố họ tên + quê quán (100 dòng)", r(60),
                  lambda n: [NAME_PREFIXES[i % len(NAME_PREFIXES)] for i in range(n)],
                  lambda p: mysql_all(conn, sql_r2, (p + "%", *PROVINCE_RANGE)),
                  lambda p: list(mongo_r2_cursor(p)),
                  lambda p: mysql_explain(conn, sql_r2, (p + "%", *PROVINCE_RANGE)),
                  lambda p: mongo_stages(mongo_r2_cursor(p).explain())))

    # R3. Hồ sơ đầy đủ một nhân khẩu: thông tin cá nhân + hộ + tạm trú/tạm vắng (2 lượt gọi mỗi bên).
    sql_r3a = ("SELECT nk.id, nk.cccd, nk.ho_ten, nk.ngay_sinh, nk.gioi_tinh, nk.que_quan, nk.nghe_nghiep, "
               "tv.quan_he, tv.tu_ngay, hk.ma_ho, hk.dia_chi FROM nhan_khau nk "
               "JOIN thanh_vien_ho tv ON tv.nhan_khau_id = nk.id AND tv.den_ngay IS NULL "
               "JOIN ho_khau hk ON hk.id = tv.ho_khau_id WHERE nk.cccd = %s")
    sql_r3b = "SELECT * FROM tam_tru_tam_vang WHERE nhan_khau_id = %s ORDER BY tu_ngay DESC"
    def mysql_r3(p):
        person = mysql_all(conn, sql_r3a, (p,))
        return person + mysql_all(conn, sql_r3b, (person[0][0],))
    def mongo_r3(p):
        c = mdb.citizens.find_one({"cccd": p})
        c["ho_khau"].update(mdb.households.find_one({"_id": c["ho_khau"]["ho_khau_id"]}, {"_id": 0, "ma_ho": 1, "dia_chi": 1}))
        return [c] + c["tam_tru_tam_vang"]  # cùng "số dòng" với MySQL: 1 hồ sơ + k bản ghi tạm trú/tạm vắng
    ops.append(Op("R3", "read", "Hồ sơ đầy đủ 1 nhân khẩu (hộ + tạm trú/tạm vắng)", r(300),
                  lambda n: cccds_of(sample_ids(n, 10)), mysql_r3, mongo_r3,
                  lambda p: mysql_explain(conn, sql_r3a, (p,)),
                  lambda p: mongo_stages(mdb.citizens.find({"cccd": p}).explain())))

    # R4. Danh sách thành viên một hộ theo mã hộ.
    sql_r4 = ("SELECT nk.id, nk.cccd, nk.ho_ten, tv.quan_he FROM ho_khau hk "
              "JOIN thanh_vien_ho tv ON tv.ho_khau_id = hk.id JOIN nhan_khau nk ON nk.id = tv.nhan_khau_id "
              "WHERE hk.ma_ho = %s ORDER BY nk.id")
    ops.append(Op("R4", "read", "Danh sách thành viên 1 hộ theo mã hộ", r(300),
                  lambda n: [f"HK{rng.randrange(1, max_household + 1):010d}" for _ in range(n)],
                  lambda p: mysql_all(conn, sql_r4, (p,)),
                  lambda p: mdb.households.find_one({"ma_ho": p}, {"members": 1})["members"],
                  lambda p: mysql_explain(conn, sql_r4, (p,)),
                  lambda p: mongo_stages(mdb.households.find({"ma_ho": p}, {"members": 1}).explain())))

    # R5. Lịch sử biến động của một nhân khẩu theo CCCD.
    sql_r5 = ("SELECT bd.* FROM nhan_khau nk JOIN bien_dong bd ON bd.nhan_khau_id = nk.id "
              "WHERE nk.cccd = %s ORDER BY bd.ngay_bien_dong DESC")
    ops.append(Op("R5", "read", "Lịch sử biến động 1 nhân khẩu theo CCCD", r(300),
                  lambda n: cccds_of(sample_ids(n, 5)),
                  lambda p: mysql_all(conn, sql_r5, (p,)),
                  lambda p: list(mdb.population_logs.find({"cccd": p}).sort("ngay_bien_dong", -1)),
                  lambda p: mysql_explain(conn, sql_r5, (p,)),
                  lambda p: mongo_stages(mdb.population_logs.find({"cccd": p}).sort("ngay_bien_dong", -1).explain())))

    # A1. Thống kê số nhân khẩu theo giới tính và quê quán (quét toàn bộ).
    sql_a1 = ("SELECT gioi_tinh, que_quan, COUNT(*) AS so_nhan_khau FROM nhan_khau "
              "GROUP BY gioi_tinh, que_quan ORDER BY gioi_tinh, so_nhan_khau DESC")
    pipe_a1 = [{"$group": {"_id": {"gioi_tinh": "$gioi_tinh", "que_quan": "$que_quan"}, "so_nhan_khau": {"$sum": 1}}},
               {"$sort": {"_id.gioi_tinh": 1, "so_nhan_khau": -1}}]
    ops.append(Op("A1", "aggregate", "Thống kê nhân khẩu theo giới tính × quê quán", r(15),
                  lambda n: [None] * n,
                  lambda p: mysql_all(conn, sql_a1),
                  lambda p: list(mdb.citizens.aggregate(pipe_a1)),
                  lambda p: mysql_explain(conn, sql_a1, None),
                  lambda p: mongo_agg_explain(mdb, "citizens", pipe_a1), warmup=2))

    # A2. Số người đang tạm trú theo quê quán.
    sql_a2 = ("SELECT nk.que_quan, COUNT(*) AS so_nguoi FROM tam_tru_tam_vang t JOIN nhan_khau nk ON nk.id = t.nhan_khau_id "
              "WHERE t.trang_thai = 'Dang hieu luc' AND t.loai = 'Tam tru' GROUP BY nk.que_quan ORDER BY so_nguoi DESC")
    cond = {"trang_thai": "Dang hieu luc", "loai": "Tam tru"}
    pipe_a2 = [{"$match": {"tam_tru_tam_vang": {"$elemMatch": cond}}},
               {"$unwind": "$tam_tru_tam_vang"},
               {"$match": {"tam_tru_tam_vang.trang_thai": cond["trang_thai"], "tam_tru_tam_vang.loai": cond["loai"]}},
               {"$group": {"_id": "$que_quan", "so_nguoi": {"$sum": 1}}},
               {"$sort": {"so_nguoi": -1}}]
    ops.append(Op("A2", "aggregate", "Số người đang tạm trú theo quê quán", r(15),
                  lambda n: [None] * n,
                  lambda p: mysql_all(conn, sql_a2),
                  lambda p: list(mdb.citizens.aggregate(pipe_a2)),
                  lambda p: mysql_explain(conn, sql_a2, None),
                  lambda p: mongo_agg_explain(mdb, "citizens", pipe_a2), warmup=2))

    # J1/J2. Danh sách thành viên của 1000 hộ liên tiếp (4000 dòng).
    sql_j = ("SELECT hk.ma_ho, hk.dia_chi, nk.id, nk.ho_ten, tv.quan_he FROM ho_khau hk "
             "JOIN thanh_vien_ho tv ON tv.ho_khau_id = hk.id JOIN nhan_khau nk ON nk.id = tv.nhan_khau_id "
             "WHERE hk.id BETWEEN %s AND %s ORDER BY hk.id, nk.id")
    def pipe_j1(start):
        return [{"$match": {"_id": {"$gte": start, "$lte": start + 999}}}, {"$unwind": "$members"},
                {"$project": {"_id": 1, "ma_ho": 1, "dia_chi": 1, "id": "$members.citizenId", "ho_ten": "$members.ho_ten", "quan_he": "$members.quan_he"}},
                {"$sort": {"_id": 1, "id": 1}}]
    def pipe_j2(start):
        return [{"$match": {"_id": {"$gte": start, "$lte": start + 999}}},
                {"$lookup": {"from": "citizens", "localField": "_id", "foreignField": "ho_khau.ho_khau_id", "as": "nk"}},
                {"$unwind": "$nk"},
                {"$project": {"_id": 1, "ma_ho": 1, "dia_chi": 1, "id": "$nk._id", "ho_ten": "$nk.ho_ten", "quan_he": "$nk.ho_khau.quan_he"}},
                {"$sort": {"_id": 1, "id": 1}}]
    j_params = lambda n: [rng.randrange(1, max_household - 1000) for _ in range(n)]
    ops.append(Op("J1", "join", "Thành viên của 1000 hộ (MongoDB: dữ liệu nhúng)", r(40), j_params,
                  lambda p: mysql_all(conn, sql_j, (p, p + 999)),
                  lambda p: list(mdb.households.aggregate(pipe_j1(p))),
                  lambda p: mysql_explain(conn, sql_j, (p, p + 999)),
                  lambda p: mongo_agg_explain(mdb, "households", pipe_j1(p))))
    ops.append(Op("J2", "join", "Thành viên của 1000 hộ (MongoDB: $lookup)", r(40), j_params,
                  None,
                  lambda p: list(mdb.households.aggregate(pipe_j2(p))),
                  None,
                  lambda p: mongo_agg_explain(mdb, "households", pipe_j2(p))))

    # ---- Thao tác ghi: chỉ trên bản ghi thử nghiệm id >= TEST_BASE ----
    wc = WriteConcern(w=1, j=True)
    citizens_w = mdb.citizens.with_options(write_concern=wc)
    households_w = mdb.households.with_options(write_concern=wc)
    logs_w = mdb.population_logs.with_options(write_concern=wc)
    n_write = r(200)
    new_people = [(TEST_BASE + i, rng.randrange(1, max_household + 1)) for i in range(1, n_write + 4)]  # +warmup

    def mysql_w1(p):
        cid, hid = p
        with conn.cursor() as cur:
            conn.begin()
            cur.execute("INSERT INTO nhan_khau (id, cccd, ho_ten, ngay_sinh, gioi_tinh, que_quan, nghe_nghiep, ngay_dang_ky) "
                        "VALUES (%s, %s, 'Nguyen Van Moi', '2026-01-15', 'Nam', 'Ha Noi', 'Tre em', '2026-02-01')", (cid, f"9{cid:011d}"))
            cur.execute("INSERT INTO thanh_vien_ho (ho_khau_id, nhan_khau_id, quan_he, tu_ngay) VALUES (%s, %s, 'Con', '2026-02-01')", (hid, cid))
            conn.commit()
    def mongo_w1(p):
        cid, hid = p
        born, reg = datetime(2026, 1, 15), datetime(2026, 2, 1)
        citizens_w.insert_one({"_id": cid, "cccd": f"9{cid:011d}", "ho_ten": "Nguyen Van Moi", "ngay_sinh": born, "gioi_tinh": "Nam",
                               "que_quan": "Ha Noi", "nghe_nghiep": "Tre em", "ngay_dang_ky": reg,
                               "ho_khau": {"ho_khau_id": hid, "quan_he": "Con", "tu_ngay": reg}, "tam_tru_tam_vang": []})
        households_w.update_one({"_id": hid}, {"$push": {"members": {"citizenId": cid, "cccd": f"9{cid:011d}", "ho_ten": "Nguyen Van Moi", "quan_he": "Con"}}})
    ops.append(Op("W1", "write", "Đăng ký nhân khẩu mới vào hộ có sẵn", n_write,
                  lambda n: new_people[: n + 3], mysql_w1, mongo_w1))

    def mysql_w2(p):
        with conn.cursor() as cur:
            cur.execute("UPDATE nhan_khau SET ho_ten = 'Nguyen Van Doi Ten' WHERE id = %s", (p[0],))
    def mongo_w2(p):
        cid, hid = p
        citizens_w.update_one({"_id": cid}, {"$set": {"ho_ten": "Nguyen Van Doi Ten"}})
        # Họ tên được sao chép (denormalize) trong households.members nên phải cập nhật cả 2 nơi.
        households_w.update_one({"_id": hid, "members.citizenId": cid}, {"$set": {"members.$.ho_ten": "Nguyen Van Doi Ten"}})
    ops.append(Op("W2", "write", "Cập nhật họ tên nhân khẩu", n_write,
                  lambda n: new_people[: n + 3], mysql_w2, mongo_w2))

    def mysql_w3(p):
        with conn.cursor() as cur:
            cur.execute("INSERT INTO bien_dong (id, nhan_khau_id, loai_bien_dong, ngay_bien_dong, noi_dung, nguoi_thuc_hien) "
                        "VALUES (%s, %s, 'Doi thong tin', '2026-03-01', 'Doi ho ten', 'Can bo tu phap ho tich')", (p[0], p[0]))
    def mongo_w3(p):
        logs_w.insert_one({"_id": p[0], "nhan_khau_id": p[0], "cccd": f"9{p[0]:011d}", "loai_bien_dong": "Doi thong tin",
                           "ngay_bien_dong": datetime(2026, 3, 1), "noi_dung": "Doi ho ten", "nguoi_thuc_hien": "Can bo tu phap ho tich"})
    ops.append(Op("W3", "write", "Ghi nhận 1 biến động", n_write,
                  lambda n: new_people[: n + 3], mysql_w3, mongo_w3))

    bulk_size = 10_000
    def bulk_rows(batch_no):
        base = TEST_BASE + 10_000_000 + batch_no * bulk_size
        return [(base + i, 1 + i, "Chuyen den", "2026-04-01", "Nhap lo", "Can bo tu phap ho tich") for i in range(bulk_size)]
    def mysql_w4(batch_no):
        rows = bulk_rows(batch_no)
        with conn.cursor() as cur:
            conn.begin()
            cur.executemany("INSERT INTO bien_dong (id, nhan_khau_id, loai_bien_dong, ngay_bien_dong, noi_dung, nguoi_thuc_hien) "
                            "VALUES (%s, %s, %s, %s, %s, %s)", rows)
            conn.commit()
    def mongo_w4(batch_no):
        docs = [{"_id": r_[0], "nhan_khau_id": r_[1], "cccd": None, "loai_bien_dong": r_[2], "ngay_bien_dong": datetime(2026, 4, 1),
                 "noi_dung": r_[4], "nguoi_thuc_hien": r_[5]} for r_ in bulk_rows(batch_no)]
        logs_w.insert_many(docs, ordered=False)
    ops.append(Op("W4", "write", f"Nhập lô {bulk_size:,} biến động", r(10),
                  lambda n: list(range(n + 2)), mysql_w4, mongo_w4, warmup=2))

    def mysql_w5(p):
        with conn.cursor() as cur:
            conn.begin()
            # FK ON DELETE CASCADE tự xóa thanh_vien_ho và bien_dong liên quan.
            cur.execute("DELETE FROM nhan_khau WHERE id = %s", (p[0],))
            conn.commit()
    def mongo_w5(p):
        cid, hid = p
        citizens_w.delete_one({"_id": cid})
        households_w.update_one({"_id": hid}, {"$pull": {"members": {"citizenId": cid}}})
        logs_w.delete_many({"nhan_khau_id": cid})
    ops.append(Op("W5", "write", "Xóa nhân khẩu (kèm thành viên hộ, biến động)", n_write,
                  lambda n: new_people[: n + 3], mysql_w5, mongo_w5))
    return ops


# ---------------------------------------------------------------- chạy đo
def measure(fn: Callable, params: list, warmup: int) -> tuple[list[float], int]:
    rows = 0
    for p in params[:warmup]:
        fn(p)
    times = []
    for p in params[warmup:]:
        t0 = time.perf_counter()
        result = fn(p)
        times.append((time.perf_counter() - t0) * 1000)
        if result is not None:
            rows = len(result)
    return times, rows


def summarize(times: list[float]) -> dict:
    s = sorted(times)
    p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
    return {"n": len(s), "median_ms": statistics.median(s), "p95_ms": p95, "mean_ms": statistics.fmean(s),
            "min_ms": s[0], "max_ms": s[-1], "stdev_ms": statistics.stdev(s) if len(s) > 1 else 0.0}


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark MySQL vs MongoDB - quản lý nhân khẩu")
    parser.add_argument("--label", required=True, help="Nhãn bộ dữ liệu đang nạp, vd 1m hoặc 100k")
    parser.add_argument("--modes", nargs="+", default=["no_index", "with_index"], choices=["no_index", "with_index"])
    parser.add_argument("--ops", nargs="*", help="Chỉ chạy các thao tác này, vd: R1 R2 A1")
    parser.add_argument("--cache-gb", type=float, default=2.0, help="Cache cho CẢ HAI DB (GB); 0 = giữ nguyên cấu hình")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument("--quick", action="store_true", help="Giảm số lần lặp còn ~20%% để chạy thử")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    conn = connect_mysql()
    mdb = MongoClient(args.mongo_uri)["quan_ly_nhan_khau"]

    # Kiểm tra hai bên cùng dữ liệu.
    max_citizen = mysql_all(conn, "SELECT COUNT(*) FROM nhan_khau WHERE id < %s", (TEST_BASE,))[0][0]
    max_household = mysql_all(conn, "SELECT COUNT(*) FROM ho_khau")[0][0]
    mongo_citizens = mdb.citizens.count_documents({"_id": {"$lt": TEST_BASE}})
    probe = mysql_all(conn, "SELECT cccd FROM nhan_khau WHERE id = 5")[0][0]
    if mongo_citizens != max_citizen or mdb.citizens.find_one({"_id": 5})["cccd"] != probe:
        raise SystemExit(f"Hai DB không cùng dữ liệu (MySQL {max_citizen:,} vs MongoDB {mongo_citizens:,}). Hãy nạp lại cùng một bộ CSV.")
    print(f"Dữ liệu: {max_citizen:,} nhân khẩu, {max_household:,} hộ (khớp giữa 2 DB)")

    if args.cache_gb > 0:
        set_cache(conn, mdb, args.cache_gb)
        print(f"Đã đặt cache = {args.cache_gb} GB cho cả InnoDB và WiredTiger (hết hiệu lực khi restart service)")
    env = environment(conn, mdb)
    env.update({"label": args.label, "citizens": max_citizen, "households": max_household})
    print(f"MySQL {env['mysql_version']} buffer pool {env['mysql_buffer_pool_mb']} MB | MongoDB {env['mongo_version']} WT cache {env['mongo_wt_cache_mb']} MB")

    cleanup_test_data(conn, mdb)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).with_name("results")
    out_dir.mkdir(exist_ok=True)
    out_csv = out_dir / f"bench_{args.label}_{stamp}.csv"
    out_plans = out_dir / f"bench_{args.label}_{stamp}_plans.csv"
    (out_dir / f"bench_{args.label}_{stamp}.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")

    results, plans = [], []
    try:
        for mode in args.modes:
            print(f"\n=== Chế độ {mode} ===")
            set_index_mode(conn, mdb, mode)
            ops = build_ops(conn, mdb, max_citizen, max_household, args.quick)
            if args.ops:
                ops = [o for o in ops if o.code in args.ops]
            for op in ops:
                params = op.params(op.reps + op.warmup)
                row_counts = {}
                for system, fn, plan_fn in (("MySQL", op.mysql, op.mysql_plan), ("MongoDB", op.mongo, op.mongo_plan)):
                    if fn is None:
                        continue
                    times, rows = measure(fn, params, op.warmup)
                    row_counts[system] = rows
                    stat = summarize(times)
                    results.append({"label": args.label, "mode": mode, "op": op.code, "group": op.group, "title": op.title,
                                    "system": system, "rows": rows, **{k: round(v, 3) if isinstance(v, float) else v for k, v in stat.items()}})
                    if plan_fn is not None:
                        plans.append({"label": args.label, "mode": mode, "op": op.code, "system": system, "plan": plan_fn(params[0])})
                    print(f"  {op.code} {system:<8} median {stat['median_ms']:9.3f} ms   p95 {stat['p95_ms']:9.3f} ms   n={stat['n']:<4} rows={rows}")
                if op.group != "write" and len(set(row_counts.values())) > 1:
                    print(f"  ! {op.code}: số dòng trả về khác nhau {row_counts}")
            cleanup_test_data(conn, mdb)
    finally:
        cleanup_test_data(conn, mdb)
        if results:
            with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(results[0]))
                w.writeheader()
                w.writerows(results)
            with out_plans.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["label", "mode", "op", "system", "plan"])
                w.writeheader()
                w.writerows(plans)
            print(f"\nĐã lưu: {out_csv}\n        {out_plans}")


if __name__ == "__main__":
    main()
