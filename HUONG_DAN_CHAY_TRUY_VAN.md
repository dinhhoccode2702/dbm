# Hướng dẫn chạy Q1–Q8 trên MySQL và MongoDB để so sánh hiệu năng

File này hướng dẫn chạy tay `03_queries_mysql.sql` (MySQL Workbench) và `05_queries_mongodb.js` (MongoDB Compass), ghi số liệu theo cùng một cách ở cả hai bên rồi đưa vào báo cáo.

> 📸 = chỗ cần chụp màn hình. Tên ảnh gợi ý đặt ngay cạnh.

---

## 0. Nguyên tắc để so sánh công bằng

| Nguyên tắc | Cách làm |
|---|---|
| Cùng dữ liệu | Cả 2 DB đều đang chứa bộ **1M** (kiểm tra ở mục 1.3). |
| Cùng bộ nhớ đệm | Cả 2 bên đặt cache **2 GB** (PHẦN 0 của mỗi file). Cài đặt mất khi restart service hoặc khởi động lại máy, khi đó phải chạy lại. |
| Cùng truy vấn | Q1–Q8 hai bên có cùng điều kiện và **cùng số dòng kết quả** (bảng ở mục 1.3). |
| Cùng trạng thái index | Đo 2 chế độ: **không index phụ** và **có index phụ**. Hai bên dùng index tương ứng, cùng tên. |
| Cùng cách lấy số | **1 lần làm nóng (bỏ đi) + 3 lần đo, lấy trung vị**, áp dụng cho cả 2 bên. |
| Không tranh tài nguyên | Khi đo MySQL thì không chạy gì bên Mongo, và ngược lại. Đóng trình duyệt, IDE, cắm sạc laptop. |

> Lưu ý: trong 2 file truy vấn, phần chú thích đầu file đang ghi MySQL "lấy lần 2", Mongo "lấy lần 3". Nên thống nhất theo bảng trên (làm nóng 1 lần, đo 3 lần, lấy trung vị) để hai bên đo giống nhau. Nếu muốn, sửa luôn phần chú thích trong 2 file cho khớp.

### Hai loại thời gian, phải so đúng cặp

| Loại | MySQL | MongoDB | Ý nghĩa |
|---|---|---|---|
| **(A) Thời gian phía client** (số chính) | Workbench: `Duration + Fetch` | Hàm `bench()` (mục 3.2): `Date.now()` bao quanh `.toArray()` | Gửi truy vấn, chờ xử lý và nhận về toàn bộ kết quả. Người dùng cảm nhận đúng thời gian này. |
| **(B) Thời gian phía server** (số phụ) | `EXPLAIN ANALYZE`: số `actual time=…..X` ở dòng đầu tiên | `explain("executionStats")`: `executionTimeMillis` | Chỉ thời gian máy chủ xử lý, không tính truyền dữ liệu và công cụ hiển thị. |

Chỉ so (A) với (A) và (B) với (B). (A) có sai số do công cụ: Workbench và shell của Compass dựng kết quả theo cách khác nhau. Vì vậy cần thêm (B) làm đối chứng, nhất là với Q7 (4.048 dòng).

---

## 1. Chuẩn bị (làm 1 lần mỗi khi khởi động lại máy)

### 1.1. MySQL Workbench

1. Mở connection tới `quan_ly_nhan_khau`, mở file `03_queries_mysql.sql`.
2. Trên thanh công cụ của tab SQL, chọn **Don't Limit**. Nếu không, Workbench tự thêm `LIMIT 1000` và Q7 bị cắt kết quả.
3. Bôi đen **PHẦN 0**, bấm `Ctrl+Shift+Enter`. Kết quả `buffer_pool_mb` phải là **2048**.
   (Nếu chưa ra 2048 thì chờ vài giây rồi chạy lại câu `SELECT @@innodb_buffer_pool_size…`. MySQL đổi kích thước buffer pool ở chế độ nền.)

### 1.2. MongoDB Compass

1. Kết nối `localhost:27017`, bấm **>_ Open MongoDB shell** ở thanh dưới cùng.
2. Dán và chạy:

```js
use quan_ly_nhan_khau
db.adminCommand({ setParameter: 1, wiredTigerEngineRuntimeConfig: "cache_size=2G" })
```

Kết quả phải có `ok: 1`.

### 1.3. Kiểm tra 2 bên có cùng dữ liệu

MySQL:
```sql
SELECT (SELECT COUNT(*) FROM nhan_khau) nk, (SELECT COUNT(*) FROM ho_khau) hk,
       (SELECT COUNT(*) FROM tam_tru_tam_vang) tttv, (SELECT COUNT(*) FROM bien_dong) bd;
```
MongoDB:
```js
db.citizens.countDocuments(); db.households.countDocuments(); db.population_logs.countDocuments()
```

`nhan_khau` = `citizens`, `ho_khau` = `households`, `bien_dong` = `population_logs`. Ngoài ra, số dòng kết quả của từng truy vấn phải khớp (bộ 1M):

| Q | Kết quả đúng |
|---|---|
| Q1 | 502 dòng |
| Q2 | 100 dòng |
| Q3 | 9618 |
| Q4 | 20 dòng |
| Q5 | 10 dòng |
| Q6 | 12 dòng |
| Q7 / Q7b | 4048 dòng |
| Q8 | 100 dòng |

📸 `10_kiem_tra_so_ban_ghi_mysql.png`, `10_kiem_tra_so_ban_ghi_mongo.png`

---

## 2. Trình tự đo tổng thể

```
Bước 1  MySQL  PHẦN 1 (không index phụ): drop index phụ -> đo Q1..Q8 -> EXPLAIN
Bước 2  Mongo  PHẦN 1 (không index phụ): drop index phụ -> đo Q1..Q8 (+Q7b) -> explain
Bước 3  MySQL  PHẦN 2: tạo index (ghi thời gian tạo) -> đo lại Q1..Q8 -> EXPLAIN -> dung lượng
Bước 4  Mongo  PHẦN 2: tạo index (ghi thời gian tạo) -> đo lại Q1..Q8 (+Q7b) -> explain -> dung lượng
Bước 5  Cả hai PHẦN 3: xóa index phụ (trả DB về trạng thái ban đầu)
```

Khi đo bên nào thì để công cụ bên kia ở trạng thái nghỉ, không chạy lệnh gì.

---

## 3. Chạy bên MySQL (Workbench)

### 3.1. Xóa index phụ

Trong PHẦN 1, đặt con trỏ vào **từng** câu `DROP INDEX` rồi bấm `Ctrl+Enter`. Câu nào báo lỗi `1091 Can't DROP` là index đó chưa tồn tại, bỏ qua. Cuối cùng chạy `SHOW INDEX FROM nhan_khau;`: chỉ được còn `PRIMARY` và `uq_nhan_khau_cccd`.

### 3.2. Đo thời gian (A)

1. Bôi đen từ dòng `-- Q1.` đến hết câu Q8, bấm `Ctrl+Shift+Enter`. **Lần này là làm nóng, không ghi số.**
2. Chạy lại khối đó thêm **3 lần**. Sau mỗi lần, xem panel **Output** (Action Output): mỗi câu có cột **Duration / Fetch**, ví dụ `0.734 sec / 0.0012 sec`.
   Thời gian = Duration + Fetch, đổi ra ms.
3. Ghi 3 số của mỗi Q vào bảng (mục 6), lấy trung vị.

📸 `11_mysql_khong_index_lan1.png` … `_lan3.png`: panel Output thấy đủ 8 dòng và cột Duration/Fetch.

> Mẹo: chuột phải vào panel Output → **Copy Rows** để dán sang Excel, đỡ phải chép tay.

### 3.3. Kế hoạch thực thi và thời gian server (B)

- Bôi đen các câu `EXPLAIN` ở cuối PHẦN 1 và chạy. Ghi lại 2 cột cho mỗi Q:
  - `type`: `ALL` = quét toàn bảng, `ref`/`range` = dùng index, `index` = quét toàn bộ index.
  - `key`: tên index được dùng (NULL = không dùng).
  - `Extra`: `Using filesort` (phải sắp xếp thêm), `Using temporary` (tạo bảng tạm cho GROUP BY), `Using index` (chỉ đọc index, không đọc bảng).
- Lấy thời gian server (B): chạy lần lượt các câu dưới đây (mỗi câu là một Q đầy đủ). Kết quả là một ô văn bản dạng cây; chuột phải vào ô → **Open Value in Viewer** để đọc. Ở **dòng đầu tiên**, `actual time=a..b` thì **b** là tổng thời gian (ms).

```sql
EXPLAIN ANALYZE SELECT id, cccd, ho_ten, ngay_sinh, gioi_tinh, que_quan FROM nhan_khau WHERE ho_ten = 'Le Van Hung';
EXPLAIN ANALYZE SELECT id, cccd, ho_ten, que_quan FROM nhan_khau WHERE que_quan = 'Ha Noi' AND ho_ten LIKE 'Tran Thi%' ORDER BY ho_ten LIMIT 100;
EXPLAIN ANALYZE SELECT COUNT(*) FROM nhan_khau WHERE que_quan = 'Can Tho' AND ngay_sinh >= '1990-01-01' AND ngay_sinh < '2000-01-01';
EXPLAIN ANALYZE SELECT que_quan, gioi_tinh, COUNT(*) FROM nhan_khau GROUP BY que_quan, gioi_tinh ORDER BY que_quan, gioi_tinh;
EXPLAIN ANALYZE SELECT nk.que_quan, COUNT(*) AS so_ho_so FROM tam_tru_tam_vang t JOIN nhan_khau nk ON nk.id = t.nhan_khau_id
  WHERE t.trang_thai = 'Dang hieu luc' AND t.loai = 'Tam tru' GROUP BY nk.que_quan ORDER BY so_ho_so DESC, nk.que_quan;
EXPLAIN ANALYZE SELECT DATE_FORMAT(ngay_bien_dong, '%Y-%m') AS thang, COUNT(*) FROM bien_dong
  WHERE loai_bien_dong = 'Chuyen den' AND ngay_bien_dong >= '2025-01-01' AND ngay_bien_dong < '2026-01-01' GROUP BY thang ORDER BY thang;
EXPLAIN ANALYZE SELECT hk.ma_ho, hk.dia_chi, nk.cccd, nk.ho_ten, tv.quan_he FROM ho_khau hk
  JOIN thanh_vien_ho tv ON tv.ho_khau_id = hk.id JOIN nhan_khau nk ON nk.id = tv.nhan_khau_id
  WHERE hk.ngay_lap >= '2000-03-01' AND hk.ngay_lap < '2000-04-01' ORDER BY hk.ma_ho, nk.cccd;
EXPLAIN ANALYZE SELECT id, cccd, ho_ten, ngay_sinh FROM nhan_khau WHERE que_quan = 'Nghe An' ORDER BY ngay_sinh LIMIT 100;
```

📸 `12_mysql_khong_index_explain.png`, và ảnh cây `EXPLAIN ANALYZE` của vài truy vấn tiêu biểu (Q1, Q4, Q7).

### 3.4. Tạo index phụ và đo lại

1. Bôi đen các câu `CREATE INDEX` của PHẦN 2 và chạy. Ghi **Duration của từng câu**: đó là thời gian tạo index.
2. Chạy `ANALYZE TABLE …` và `SHOW INDEX`, rồi chạy câu `information_schema.tables` để lấy **dung lượng dữ liệu và index (MB)**.
3. Lặp lại mục 3.2 và 3.3 (làm nóng 1 lần, đo 3 lần, EXPLAIN, EXPLAIN ANALYZE).

📸 `13_mysql_tao_index.png`, `14_mysql_dung_luong.png`, `15_mysql_co_index_lan1..3.png`, `16_mysql_co_index_explain.png`

---

## 4. Chạy bên MongoDB (shell trong Compass)

### 4.1. Xóa index phụ

Dán khối `dropIndex` ở PHẦN 1 của `05_queries_mongodb.js`. Báo `index not found` thì bỏ qua. Chạy `db.citizens.getIndexes()`: chỉ còn `_id_`, `uq_cccd`, `ix_ho_khau_id`.

### 4.2. Đo thời gian (A) bằng hàm `bench`

Thay vì chép tay dòng `Date.now()` nhiều lần, dán hàm sau vào shell **một lần**. Hàm tự chạy 1 lần làm nóng, đo 3 lần rồi in trung vị:

```js
function bench(name, fn, n) {
  n = n || 3;
  fn();                                   // làm nóng, không tính
  var ts = [];
  for (var i = 0; i < n; i++) { var t = Date.now(); fn(); ts.push(Date.now() - t); }
  var s = ts.slice().sort(function (a, b) { return a - b; });
  print(name + " | các lần: " + ts.join(", ") + " ms | trung vị: " + s[Math.floor(n / 2)] + " ms");
}
```

Sau đó dán khối dưới đây (đúng các truy vấn trong file `.js`, mỗi câu đều có `.toArray()` để lấy hết kết quả về giống như Workbench):

```js
bench("Q1", () => db.citizens.find({ ho_ten: "Le Van Hung" }, { cccd: 1, ho_ten: 1, ngay_sinh: 1, gioi_tinh: 1, que_quan: 1 }).toArray())
bench("Q2", () => db.citizens.find({ que_quan: "Ha Noi", ho_ten: /^Tran Thi/ }, { cccd: 1, ho_ten: 1, que_quan: 1 }).sort({ ho_ten: 1 }).limit(100).toArray())
bench("Q3", () => db.citizens.countDocuments({ que_quan: "Can Tho", ngay_sinh: { $gte: ISODate("1990-01-01"), $lt: ISODate("2000-01-01") } }))
bench("Q4", () => db.citizens.aggregate([{ $group: { _id: { que_quan: "$que_quan", gioi_tinh: "$gioi_tinh" }, so_nguoi: { $sum: 1 } } }, { $sort: { "_id.que_quan": 1, "_id.gioi_tinh": 1 } }]).toArray())
bench("Q5", () => db.citizens.aggregate([{ $match: { tam_tru_tam_vang: { $elemMatch: { trang_thai: "Dang hieu luc", loai: "Tam tru" } } } }, { $unwind: "$tam_tru_tam_vang" }, { $match: { "tam_tru_tam_vang.trang_thai": "Dang hieu luc", "tam_tru_tam_vang.loai": "Tam tru" } }, { $group: { _id: "$que_quan", so_ho_so: { $sum: 1 } } }, { $sort: { so_ho_so: -1, _id: 1 } }]).toArray())
bench("Q6", () => db.population_logs.aggregate([{ $match: { loai_bien_dong: "Chuyen den", ngay_bien_dong: { $gte: ISODate("2025-01-01"), $lt: ISODate("2026-01-01") } } }, { $group: { _id: { $dateToString: { format: "%Y-%m", date: "$ngay_bien_dong" } }, so_bien_dong: { $sum: 1 } } }, { $sort: { _id: 1 } }]).toArray())
bench("Q7", () => db.households.aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $unwind: "$members" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$members.cccd", ho_ten: "$members.ho_ten", quan_he: "$members.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }]).toArray())
bench("Q7b", () => db.households.aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $lookup: { from: "citizens", localField: "_id", foreignField: "ho_khau.ho_khau_id", as: "nk" } }, { $unwind: "$nk" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$nk.cccd", ho_ten: "$nk.ho_ten", quan_he: "$nk.ho_khau.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }]).toArray())
bench("Q8", () => db.citizens.find({ que_quan: "Nghe An" }, { cccd: 1, ho_ten: 1, ngay_sinh: 1 }).sort({ ngay_sinh: 1 }).limit(100).toArray())
```

Mỗi dòng in ra dạng `Q1 | các lần: 812, 795, 801 ms | trung vị: 801 ms`. Trước khi đo nên chạy dòng "xem kết quả" của mỗi Q trong file `.js` một lần để kiểm tra số dòng có khớp bảng ở mục 1.3 không.

📸 `21_mongo_khong_index_bench.png`: thấy đủ 9 dòng in ra.

### 4.3. Kế hoạch thực thi và thời gian server (B)

Với `find`/`countDocuments`, dùng các dòng `.explain("executionStats")` có sẵn ở cuối PHẦN 1. Với `aggregate` (Q4, Q5, Q6, Q7, Q7b), đặt `.explain("executionStats")` **trước** `aggregate`:

```js
db.citizens.explain("executionStats").aggregate([{ $group: { _id: { que_quan: "$que_quan", gioi_tinh: "$gioi_tinh" }, so_nguoi: { $sum: 1 } } }, { $sort: { "_id.que_quan": 1, "_id.gioi_tinh": 1 } }])   // Q4
db.households.explain("executionStats").aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $unwind: "$members" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$members.cccd", ho_ten: "$members.ho_ten", quan_he: "$members.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }])   // Q7
db.households.explain("executionStats").aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $lookup: { from: "citizens", localField: "_id", foreignField: "ho_khau.ho_khau_id", as: "nk" } }, { $unwind: "$nk" }])   // Q7b
```

(Q5, Q6 làm tương tự: chép pipeline từ file `.js` vào sau `explain("executionStats").aggregate(`.)

Trong kết quả, ghi lại cho mỗi Q:

| Trường | Ý nghĩa |
|---|---|
| `winningPlan` … `stage` | `COLLSCAN` = quét toàn collection; `IXSCAN` + `indexName` = dùng index; `SORT` = phải sắp xếp trong bộ nhớ; `COUNT_SCAN`/`PROJECTION_COVERED` = chỉ đọc index |
| `executionStats.totalDocsExamined` | Số document phải đọc |
| `executionStats.totalKeysExamined` | Số khóa index phải đọc |
| `executionStats.executionTimeMillis` | **Thời gian server (B)** |

Với `aggregate`, các trường trên có thể nằm trong `stages[0].$cursor`; nếu không thấy ở cấp ngoài cùng thì tìm ở đó. Shell có thể thu gọn kết quả lồng sâu; khi đó thêm `JSON.stringify(…, null, 1)` hoặc chụp phần `executionStats`.

> Số document phải đọc là con số rất có giá trị cho báo cáo. Ví dụ không có index thì Q1 phải đọc 1.000.000 document; có index thì chỉ còn 502.

📸 `22_mongo_khong_index_explain_Q1.png`, `…_Q4.png`, `…_Q7.png`

### 4.4. Tạo index phụ và đo lại

1. Dán từng dòng `createIndex` của PHẦN 2. Mỗi dòng tự in `tạo ix_…: N ms`, đó là thời gian tạo index.
2. Lấy dung lượng (MB) của cả 3 collection:

```js
["citizens", "households", "population_logs"].forEach(function (c) {
  var s = db.getCollection(c).stats({ scale: 1048576 });
  print(c, "| dữ liệu (chưa nén):", s.size, "MB | trên đĩa:", s.storageSize, "MB | index:", s.totalIndexSize, "MB");
  printjson(s.indexSizes);
})
```

3. Lặp lại mục 4.2 (chỉ cần dán lại khối `bench`; hàm `bench` vẫn còn nếu chưa đóng shell) và mục 4.3.

📸 `23_mongo_tao_index.png`, `24_mongo_dung_luong.png`, `25_mongo_co_index_bench.png`, `26_mongo_co_index_explain.png`

---

## 5. Dọn dẹp

Chạy **PHẦN 3** ở cả hai file để xóa index phụ. Phải dọn trước khi chạy `06_benchmark.py`, vì script đó tự quản lý index của nó.

---

## 6. Bảng ghi số liệu (dán vào báo cáo)

### 6.1. Thời gian truy vấn (A), bộ 1M, đơn vị ms, trung vị của 3 lần

| Q | Nội dung | Số dòng | MySQL không idx | Mongo không idx | MySQL có idx | Mongo có idx | Nhanh hơn (không idx) | Nhanh hơn (có idx) |
|---|---|---:|---:|---:|---:|---:|---|---|
| Q1 | Tìm theo họ tên chính xác | 502 | | | | | | |
| Q2 | Tỉnh + tiền tố tên, sắp xếp, 100 dòng | 100 | | | | | | |
| Q3 | Đếm theo tỉnh + khoảng ngày sinh | 1 | | | | | | |
| Q4 | Thống kê tỉnh × giới tính | 20 | | | | | | |
| Q5 | Tạm trú hiệu lực theo quê (JOIN / mảng nhúng) | 10 | | | | | | |
| Q6 | Biến động "Chuyển đến" theo tháng | 12 | | | | | | |
| Q7 | Thành viên hộ lập 3/2000 (JOIN 3 bảng / nhúng) | 4048 | | | | | | |
| Q7b | Như Q7 nhưng dùng `$lookup` (chỉ Mongo) | 4048 | — | | — | | — | — |
| Q8 | 100 người cao tuổi nhất Nghệ An | 100 | | | | | | |

Cột "Nhanh hơn" ghi dạng `MySQL ×3.2` (= thời gian bên chậm / thời gian bên nhanh). Chênh dưới 15% thì ghi "tương đương".

### 6.2. Thời gian server (B) và kế hoạch thực thi

| Q | Chế độ | MySQL `type`/`key`/`Extra` | MySQL actual time (ms) | Mongo stage / index | Mongo docsExamined | Mongo executionTimeMillis |
|---|---|---|---:|---|---:|---:|
| Q1 | không idx | ALL / NULL / Using where | | COLLSCAN | 1.000.000 | |
| Q1 | có idx | | | | | |
| … | | | | | | |

### 6.3. Chi phí của index

| Index | Trên | Thời gian tạo MySQL (s) | Thời gian tạo Mongo (s) |
|---|---|---:|---:|
| ix_nk_ho_ten | ho_ten | | |
| ix_nk_que_quan_ho_ten | que_quan, ho_ten | | |
| ix_nk_que_quan_ngay_sinh | que_quan, ngay_sinh | | |
| ix_nk_que_quan_gioi_tinh | que_quan, gioi_tinh | | |
| ix_tttv_trang_thai_loai | trang_thai, loai (Mongo: multikey trên mảng) | | |
| ix_bd_loai_ngay | loai_bien_dong, ngay_bien_dong | | |
| ix_hk_ngay_lap | ngay_lap | | |

| | MySQL dữ liệu (MB) | MySQL index (MB) | Mongo dữ liệu trên đĩa (MB) | Mongo index (MB) |
|---|---:|---:|---:|---:|
| Trước khi tạo index phụ | | | | |
| Sau khi tạo index phụ | | | | |

(MySQL: cộng các bảng tương ứng. Mongo `storageSize` là dung lượng đã nén snappy, còn `size` là chưa nén; nên ghi cả hai.)

### 6.4. Vẽ biểu đồ bằng `07_plot_results.py` (tùy chọn)

Script vẽ đọc được file CSV có các cột của `06_benchmark.py`. Tạo file `results\thu_cong\ket_qua_1m.csv` (để trong thư mục con riêng, tránh ghi đè ảnh `scale_*.png` của benchmark), mỗi Q một dòng cho mỗi hệ và mỗi chế độ:

```csv
label,mode,op,group,title,system,rows,n,median_ms,p95_ms
1m,no_index,Q1,read,Tìm theo họ tên,MySQL,502,3,734,760
1m,no_index,Q1,read,Tìm theo họ tên,MongoDB,502,3,812,830
1m,with_index,Q1,read,Tìm theo họ tên,MySQL,502,3,1.2,1.5
...
```

- `median_ms` = trung vị 3 lần; `p95_ms` = lần chậm nhất trong 3 lần.
- Phải điền đủ số, không để trống. Q7b chỉ có dòng MongoDB.
- Số ở ví dụ trên là minh họa, thay bằng số thật.

```powershell
py -3.12 07_plot_results.py results\thu_cong\ket_qua_1m.csv
```

Kết quả gồm `ket_qua_1m_no_index.png`, `ket_qua_1m_with_index.png` và `ket_qua_1m_summary.md` (bảng có sẵn cột "Nhanh hơn ×k"). Nếu đo thêm bộ 100k (nạp lại 100k vào **cả hai** DB rồi làm lại toàn bộ từ mục 1), tạo thêm `ket_qua_100k.csv` với `label` = `100k` rồi chạy `07_plot_results.py results\thu_cong\ket_qua_*.csv` để có biểu đồ theo quy mô.

---

## 7. Đo khi cache lạnh (bắt buộc đọc từ đĩa)

Các mục 3–4 đo khi **cache nóng**: toàn bộ dữ liệu (MySQL khoảng 320 MB, Mongo khoảng 150 MB trên đĩa) đã nằm trong cache 2 GB nên truy vấn không đọc đĩa. Muốn đo truy vấn phải đọc dữ liệu thật từ đĩa thì trước **mỗi** lần đo phải xóa sạch cache:

| | Cache cần xóa | Cách xóa |
|---|---|---|
| MySQL | InnoDB buffer pool | Restart service **và** xóa file `ib_buffer_pool`. Nếu không xóa file này, MySQL tự nạp lại các trang cũ khi khởi động. Cache file của Windows không ảnh hưởng vì MySQL dùng `innodb_flush_method = unbuffered`. |
| MongoDB | WiredTiger cache **và** cache file của Windows | Restart service, rồi xóa standby list của Windows bằng RAMMap. Chỉ restart thì Windows vẫn giữ file `.wt` trong RAM. |

Script `08_lam_lanh_cache.ps1` làm hết các bước trên.

### 7.1. Chuẩn bị (1 lần)

1. Tải **RAMMap** (Sysinternals, miễn phí của Microsoft): https://learn.microsoft.com/sysinternals/downloads/rammap , giải nén `RAMMap64.exe` vào `D:\BTL_DBM\tools\`.
2. Trong Workbench, cho MySQL giữ buffer pool 2 GB sau khi restart (nếu không, sau restart nó về 128 MB) và không ghi file dump khi tắt:
   ```sql
   SET PERSIST innodb_buffer_pool_size = 2147483648;
   SET PERSIST innodb_buffer_pool_dump_at_shutdown = OFF;
   ```
3. Mở **PowerShell bằng Run as Administrator** (cần quyền này để dừng/bật service):
   ```powershell
   cd D:\BTL_DBM
   ```

### 7.2. Quy trình cho MỖI lần đo

```
(1) PowerShell admin:  powershell -ExecutionPolicy Bypass -File .\08_lam_lanh_cache.ps1 -Target mysql   (hoặc -Target mongo)
(2) Workbench / Compass: kết nối lại (Workbench thường tự kết nối lại; Compass thì mở lại shell và gõ `use quan_ly_nhan_khau`)
(3) Chạy ĐÚNG 1 truy vấn, CHỈ 1 lần  -> ghi thời gian
(4) Quay lại (1) cho truy vấn tiếp theo
```

- **Không** chạy nhiều Q liên tiếp sau một lần làm lạnh. Q1 đã đọc `nhan_khau` vào cache thì Q2, Q3, Q4 và Q8 sẽ chạy với cache nóng.
- **Không** dùng hàm `bench()` (nó có bước làm nóng). Bên Mongo dùng dòng đo một lần, ví dụ:
  `var t = Date.now(); db.citizens.find({ ho_ten: "Le Van Hung" }).toArray(); print("Q1:", Date.now() - t, "ms")`
- Mỗi Q đo 3 lần (3 vòng làm lạnh), lấy trung vị. Tổng cộng 8 Q × 3 lần × 2 chế độ × 2 DB = 96 vòng. Nếu không đủ thời gian, ưu tiên các Q nặng (Q1, Q4, Q7) hoặc chỉ đo 1 lần mỗi Q và ghi rõ điều đó trong báo cáo.

### 7.3. Chứng minh truy vấn đã đọc từ đĩa (nên chụp làm minh chứng)

MySQL: chạy câu dưới đây trước và sau truy vấn. Nếu `Innodb_buffer_pool_reads` (số trang phải đọc từ đĩa) tăng thì truy vấn đã đọc từ đĩa; khi cache nóng, số này gần như không đổi.
```sql
SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_reads';
```
MongoDB: so sánh số byte nạp vào cache trước và sau truy vấn:
```js
db.serverStatus().wiredTiger.cache["bytes read into cache"]
```

📸 `30_cache_lanh_script.png` (output script), `31_mysql_cache_lanh_Qx.png`, `32_mongo_cache_lanh_Qx.png`, và ảnh bộ đếm trước/sau.

### 7.4. Ghi vào báo cáo

Thêm 2 cột "cache lạnh" vào bảng 6.1. Khi phân tích, so sánh **lạnh với nóng** để thấy phần thời gian do đọc đĩa:

- Dữ liệu Mongo được nén (snappy), khoảng 150 MB trên đĩa so với khoảng 430 MB khi chưa nén, nên phải đọc ít byte hơn. MySQL không nén.
- Có index thì truy vấn chỉ đọc vài trang, nên chênh lệch lạnh/nóng nhỏ. Không có index thì phải đọc cả bảng từ đĩa.
- Máy dùng SSD nên đọc khoảng 100–300 MB chỉ mất thêm cỡ vài trăm ms. Chênh lệch lạnh/nóng sẽ lớn hơn nhiều trên HDD hoặc khi dữ liệu lớn hơn RAM.

### 7.5. Sau khi đo xong

```sql
SET PERSIST innodb_buffer_pool_dump_at_shutdown = ON;   -- trả lại mặc định
```

---

## 8. Gợi ý phân tích từng truy vấn trong báo cáo

Dùng số liệu thật để xác nhận hoặc bác bỏ các giả thuyết dưới đây. **Đừng chép kết luận nếu số liệu nói khác.**

| Q | Điểm cần phân tích |
|---|---|
| Q1 | Không index: cả hai phải quét toàn bộ 1M bản ghi. Document Mongo chứa mảng nhúng (`ho_khau`, `tam_tru_tam_vang`) nên to hơn một dòng `nhan_khau`, vì vậy quét có thể chậm hơn. Có index: cả hai chỉ đọc 502 khóa. So `docsExamined` / `rows` trước và sau. |
| Q2 | Index ghép `(que_quan, ho_ten)` vừa lọc vừa có sẵn thứ tự, nên mất bước sắp xếp (`Using filesort` hoặc stage `SORT` biến mất). Regex `^…` của Mongo tương đương `LIKE 'abc%'`. |
| Q3 | Truy vấn đếm. MySQL có thể chỉ đọc index (`Using index`). Mongo `countDocuments` có thể đọc phủ bởi index (`COUNT_SCAN`/`PROJECTION_COVERED`). Ghi lại bên nào chỉ đọc index. |
| Q4 | Gom nhóm trên toàn bộ dữ liệu. Có index `(que_quan, gioi_tinh)`, MySQL có thể quét index (`type=index`, `Using index`) thay vì quét bảng. Mongo `$group` không có `$match` thường vẫn `COLLSCAN`, tức là index gần như không giúp. Đây là điểm khác biệt đáng nêu. |
| Q5 | Mô hình dữ liệu khác nhau: MySQL phải **JOIN** `tam_tru_tam_vang` với `nhan_khau`. Mongo không cần JOIN (dữ liệu nhúng) nhưng phải `$unwind`, và index trên mảng là **multikey index**. |
| Q6 | Cấu trúc giống nhau ở hai bên (bảng/collection riêng, lọc rồi gom nhóm theo tháng). Đây là phép so sánh "thuần engine" ít bị ảnh hưởng bởi thiết kế dữ liệu. |
| Q7 vs Q7b | Lợi ích của **nhúng dữ liệu**: Q7 (Mongo, nhúng `members`) so với Q7 (MySQL, JOIN 3 bảng) và Q7b (Mongo, `$lookup`). Thông thường `$lookup` chậm hơn JOIN của MySQL; nhúng thì nhanh hơn cả hai. Đánh đổi: dữ liệu bị lặp (họ tên, CCCD nằm ở cả `citizens` và `households.members`), khi cập nhật phải sửa hai chỗ. |
| Q8 | Top-N. Có index `(que_quan, ngay_sinh)` thì cả hai chỉ cần đọc 100 khóa đầu tiên, không cần sắp xếp. Không index thì phải quét hết và sắp xếp. |
| Index | So thời gian tạo và dung lượng index. Index giúp đọc nhanh nhưng tốn đĩa và làm chậm ghi; phần ghi được đo trong `06_benchmark.py`. |

### Những hạn chế cần ghi rõ trong báo cáo

- Đo trên một máy cá nhân, MongoDB chạy standalone (không replica set, không sharding), nên kết quả không đại diện cho môi trường production.
- Thời gian (A) bao gồm cả chi phí của công cụ (Workbench / shell Compass). Vì vậy có thêm số (B) từ `EXPLAIN ANALYZE` / `executionStats` để đối chiếu.
- Chỉ đo 3 lần mỗi truy vấn. Số liệu có nhiều lần lặp và phân vị p95 lấy từ `06_benchmark.py`; phần chạy tay này dùng để minh họa kế hoạch thực thi và ảnh minh chứng.
- Hai bên dùng mô hình dữ liệu khác nhau (chuẩn hóa so với nhúng). Kết quả phản ánh **hệ quản trị cộng với cách thiết kế dữ liệu**, không chỉ riêng engine.
