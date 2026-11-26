# Hướng dẫn chạy Q1–Q5 và W1–W5 trên MySQL và MongoDB để so sánh hiệu năng

File này hướng dẫn chạy tay `03_queries_mysql.sql` (MySQL Workbench) và `05_queries_mongodb.js` (MongoDB Compass), ghi số liệu theo cùng một cách ở cả hai bên rồi đưa vào báo cáo.

> 📸 = chỗ cần chụp màn hình. Tên ảnh gợi ý đặt ngay cạnh.

---

## 0. Nguyên tắc để so sánh công bằng

| Nguyên tắc | Cách làm |
|---|---|
| Cùng dữ liệu | Cả 2 DB đều đang chứa bộ **1M** (kiểm tra ở mục 1.3). |
| Cùng bộ nhớ đệm | Cả 2 bên đặt cache **2 GB** (PHẦN 0 của mỗi file). Cài đặt mất khi restart service hoặc khởi động lại máy, khi đó phải chạy lại. |
| Cùng truy vấn | Q1–Q5 và W1–W5 hai bên có cùng điều kiện và **cùng số dòng kết quả** (bảng ở mục 1.3). |
| Cùng trạng thái index | Đo 2 chế độ: **không index phụ** và **có index phụ**. Hai bên dùng index tương ứng, cùng tên. |
| Cùng cách lấy số | Câu đọc: **1 lần làm nóng (bỏ đi) + 3 lần đo, lấy trung vị**. Câu ghi: **1 lượt W1→W5** mỗi chế độ (chạy lặp sẽ trùng khóa). |
| Cùng độ bền khi ghi | MySQL ghi đĩa ở mỗi COMMIT; Mongo dùng `writeConcern { j: true }` (đã viết sẵn trong file). |
| Không tranh tài nguyên | Khi đo MySQL thì không chạy gì bên Mongo, và ngược lại. Đóng trình duyệt, IDE, cắm sạc laptop. |


### Hai loại thời gian, phải so đúng cặp

| Loại | MySQL | MongoDB | Ý nghĩa |
|---|---|---|---|
| **(A) Thời gian phía client** (số chính) | Workbench: `Duration + Fetch` | Hàm `bench()` (mục 3.2): `Date.now()` bao quanh `.toArray()` | Gửi truy vấn, chờ xử lý và nhận về toàn bộ kết quả. Người dùng cảm nhận đúng thời gian này. |
| **(B) Thời gian phía server** (số phụ) | `EXPLAIN ANALYZE`: số `actual time=…..X` ở dòng đầu tiên | `explain("executionStats")`: `executionTimeMillis` | Chỉ thời gian máy chủ xử lý, không tính truyền dữ liệu và công cụ hiển thị. |

Chỉ so (A) với (A) và (B) với (B). (A) có sai số do công cụ: Workbench và shell của Compass dựng kết quả theo cách khác nhau. Vì vậy cần thêm (B) làm đối chứng, nhất là với Q5 (4.048 dòng).

---

## 1. Chuẩn bị (làm 1 lần mỗi khi khởi động lại máy)

### 1.1. MySQL Workbench

1. Mở connection tới `quan_ly_nhan_khau`, mở file `03_queries_mysql.sql`.
2. Trên thanh công cụ của tab SQL, chọn **Don't Limit**. Nếu không, Workbench tự thêm `LIMIT 1000` và Q5 bị cắt kết quả.
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

| Câu | Kết quả đúng |
|---|---|
| Q1 | 502 dòng |
| Q2 | 100 dòng |
| Q3 | 20 dòng |
| Q4 | 10 dòng |
| Q5 / Q5b | 4048 dòng |
| W1 | thêm 1 người (MySQL: 3 dòng ở 3 bảng; Mongo: 1 document + 1 phần tử `members` + 1 biến động) |
| W2 / W2b | 502 người đổi tên (Mongo: 502 công dân, 500 hộ vì có hộ chứa 2 người cùng tên) |
| W3 / W4 | 100000 biến động thêm / xóa |
| W5 | các câu kiểm tra cuối cùng đều ra 0 |

📸 `10_kiem_tra_so_ban_ghi_mysql.png`, `10_kiem_tra_so_ban_ghi_mongo.png`

---

## 2. Trình tự đo tổng thể

```
Bước 1  MySQL  PHẦN 1 (không index phụ): drop index phụ -> đo Q1..Q5 -> EXPLAIN -> W1..W5
Bước 2  Mongo  PHẦN 1 (không index phụ): drop index phụ -> đo Q1..Q5 (+Q5b) -> explain -> W1..W5
Bước 3  MySQL  PHẦN 2: tạo index (ghi thời gian tạo) -> đo lại Q1..Q5 -> EXPLAIN -> W1..W5 -> dung lượng
Bước 4  Mongo  PHẦN 2: tạo index (ghi thời gian tạo) -> đo lại Q1..Q5 (+Q5b) -> explain -> W1..W5 -> dung lượng
Bước 5  Cả hai PHẦN 3: xóa index phụ (trả DB về trạng thái ban đầu)
```

Khi đo bên nào thì để công cụ bên kia ở trạng thái nghỉ, không chạy lệnh gì.

---

## 3. Chạy bên MySQL (Workbench)

### 3.1. Xóa index phụ

Trong PHẦN 1, đặt con trỏ vào **từng** câu `DROP INDEX` rồi bấm `Ctrl+Enter`. Câu nào báo lỗi `1091 Can't DROP` là index đó chưa tồn tại, bỏ qua. Cuối cùng chạy `SHOW INDEX FROM nhan_khau;`: chỉ được còn `PRIMARY` và `uq_nhan_khau_cccd`.

### 3.2. Đo thời gian (A)

1. Bôi đen từ dòng `-- Q1.` đến hết câu Q5, bấm `Ctrl+Shift+Enter`. **Lần này là làm nóng, không ghi số.**
2. Chạy lại khối đó thêm **3 lần**. Sau mỗi lần, xem panel **Output** (Action Output): mỗi câu có cột **Duration / Fetch**, ví dụ `0.734 sec / 0.0012 sec`.
   Thời gian = Duration + Fetch, đổi ra ms.
3. Ghi 3 số của mỗi Q vào bảng (mục 6), lấy trung vị.

📸 `11_mysql_khong_index_lan1.png` … `_lan3.png`: panel Output thấy đủ 5 dòng và cột Duration/Fetch.

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
EXPLAIN ANALYZE SELECT que_quan, gioi_tinh, COUNT(*) FROM nhan_khau GROUP BY que_quan, gioi_tinh ORDER BY que_quan, gioi_tinh;
EXPLAIN ANALYZE SELECT nk.que_quan, COUNT(*) AS so_ho_so FROM tam_tru_tam_vang t JOIN nhan_khau nk ON nk.id = t.nhan_khau_id
  WHERE t.trang_thai = 'Dang hieu luc' AND t.loai = 'Tam tru' GROUP BY nk.que_quan ORDER BY so_ho_so DESC, nk.que_quan;
EXPLAIN ANALYZE SELECT hk.ma_ho, hk.dia_chi, nk.cccd, nk.ho_ten, tv.quan_he FROM ho_khau hk
  JOIN thanh_vien_ho tv ON tv.ho_khau_id = hk.id JOIN nhan_khau nk ON nk.id = tv.nhan_khau_id
  WHERE hk.ngay_lap >= '2000-03-01' AND hk.ngay_lap < '2000-04-01' ORDER BY hk.ma_ho, nk.cccd;
```

📸 `12_mysql_khong_index_explain.png`, và ảnh cây `EXPLAIN ANALYZE` của vài truy vấn tiêu biểu (Q1, Q3, Q5).

### 3.3b. Các câu ghi W1–W5

Chạy **từng câu** theo thứ tự W1 → W5 (Ctrl+Enter), **một lượt** cho mỗi chế độ. Ghi Duration của từng câu; W1 = cộng 3 câu INSERT và câu COMMIT. Câu kiểm tra cuối cùng phải ra `0, 0, 0`.

📸 `17_mysql_ghi_khong_index.png`

### 3.4. Tạo index phụ và đo lại

1. Bôi đen các câu `CREATE INDEX` của PHẦN 2 và chạy. Ghi **Duration của từng câu**: đó là thời gian tạo index.
2. Chạy `ANALYZE TABLE …` và `SHOW INDEX`, rồi chạy câu `information_schema.tables` để lấy **dung lượng dữ liệu và index (MB)**.
3. Lặp lại mục 3.2, 3.3 và 3.3b.

📸 `13_mysql_tao_index.png`, `14_mysql_dung_luong.png`, `15_mysql_co_index_lan1..3.png`, `16_mysql_co_index_explain.png`, `18_mysql_ghi_co_index.png`

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
bench("Q3", () => db.citizens.aggregate([{ $group: { _id: { que_quan: "$que_quan", gioi_tinh: "$gioi_tinh" }, so_nguoi: { $sum: 1 } } }, { $sort: { "_id.que_quan": 1, "_id.gioi_tinh": 1 } }]).toArray())
bench("Q4", () => db.citizens.aggregate([{ $match: { tam_tru_tam_vang: { $elemMatch: { trang_thai: "Dang hieu luc", loai: "Tam tru" } } } }, { $unwind: "$tam_tru_tam_vang" }, { $match: { "tam_tru_tam_vang.trang_thai": "Dang hieu luc", "tam_tru_tam_vang.loai": "Tam tru" } }, { $group: { _id: "$que_quan", so_ho_so: { $sum: 1 } } }, { $sort: { so_ho_so: -1, _id: 1 } }]).toArray())
bench("Q5", () => db.households.aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $unwind: "$members" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$members.cccd", ho_ten: "$members.ho_ten", quan_he: "$members.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }]).toArray())
bench("Q5b", () => db.households.aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $lookup: { from: "citizens", localField: "_id", foreignField: "ho_khau.ho_khau_id", as: "nk" } }, { $unwind: "$nk" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$nk.cccd", ho_ten: "$nk.ho_ten", quan_he: "$nk.ho_khau.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }]).toArray())
```

Mỗi dòng in ra dạng `Q1 | các lần: 812, 795, 801 ms | trung vị: 801 ms`. Trước khi đo nên chạy dòng "xem kết quả" của mỗi Q trong file `.js` một lần để kiểm tra số dòng có khớp bảng ở mục 1.3 không.

📸 `21_mongo_khong_index_bench.png`: thấy đủ 6 dòng in ra.

> Câu ghi W1–W5 **không** dùng `bench` (chạy lặp sẽ trùng khóa). Dán từng dòng `var t = …; print("W…")` trong file `.js` theo thứ tự, một lượt mỗi chế độ, rồi chạy các câu kiểm tra (phải ra 0).
> 📸 `27_mongo_ghi_khong_index.png`, `28_mongo_ghi_co_index.png`

### 4.3. Kế hoạch thực thi và thời gian server (B)

Với `find`/`countDocuments`, dùng các dòng `.explain("executionStats")` có sẵn ở cuối PHẦN 1. Với `aggregate` (Q3, Q4, Q5, Q5b), đặt `.explain("executionStats")` **trước** `aggregate`:

```js
db.citizens.explain("executionStats").aggregate([{ $group: { _id: { que_quan: "$que_quan", gioi_tinh: "$gioi_tinh" }, so_nguoi: { $sum: 1 } } }, { $sort: { "_id.que_quan": 1, "_id.gioi_tinh": 1 } }])   // Q3
db.households.explain("executionStats").aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $unwind: "$members" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$members.cccd", ho_ten: "$members.ho_ten", quan_he: "$members.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }])   // Q5
db.households.explain("executionStats").aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $lookup: { from: "citizens", localField: "_id", foreignField: "ho_khau.ho_khau_id", as: "nk" } }, { $unwind: "$nk" }])   // Q5b
```

(Q4 làm tương tự: chép pipeline từ file `.js` vào sau `explain("executionStats").aggregate(`.)

Trong kết quả, ghi lại cho mỗi Q:

| Trường | Ý nghĩa |
|---|---|
| `winningPlan` … `stage` | `COLLSCAN` = quét toàn collection; `IXSCAN` + `indexName` = dùng index; `SORT` = phải sắp xếp trong bộ nhớ; `COUNT_SCAN`/`PROJECTION_COVERED` = chỉ đọc index |
| `executionStats.totalDocsExamined` | Số document phải đọc |
| `executionStats.totalKeysExamined` | Số khóa index phải đọc |
| `executionStats.executionTimeMillis` | **Thời gian server (B)** |

Với `aggregate`, các trường trên có thể nằm trong `stages[0].$cursor`; nếu không thấy ở cấp ngoài cùng thì tìm ở đó. Shell có thể thu gọn kết quả lồng sâu; khi đó thêm `JSON.stringify(…, null, 1)` hoặc chụp phần `executionStats`.

> Số document phải đọc là con số rất có giá trị cho báo cáo. Ví dụ không có index thì Q1 phải đọc 1.000.000 document; có index thì chỉ còn 502.

📸 `22_mongo_khong_index_explain_Q1.png`, `…_Q3.png`, `…_Q5.png`

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

3. Lặp lại mục 4.2 (chỉ cần dán lại khối `bench`; hàm `bench` vẫn còn nếu chưa đóng shell), mục 4.3 và các câu ghi W1–W5.

📸 `23_mongo_tao_index.png`, `24_mongo_dung_luong.png`, `25_mongo_co_index_bench.png`, `26_mongo_co_index_explain.png`

---

## 5. Dọn dẹp

Chạy **PHẦN 3** ở cả hai file để xóa index phụ. Phải dọn trước khi chạy `06_benchmark.py`, vì script đó tự quản lý index của nó.

---

## 6. Bảng ghi số liệu (dán vào báo cáo)

### 6.1. Thời gian (A), bộ 1M, đơn vị ms

Câu đọc: trung vị của 3 lần. Câu ghi: 1 lần.

| Câu | Nội dung | Số dòng | MySQL không idx | Mongo không idx | MySQL có idx | Mongo có idx | Nhanh hơn (không idx) | Nhanh hơn (có idx) |
|---|---|---:|---:|---:|---:|---:|---|---|
| Q1 | Tìm theo họ tên chính xác | 502 | | | | | | |
| Q2 | Tỉnh + tiền tố tên, sắp xếp, 100 dòng | 100 | | | | | | |
| Q3 | Thống kê tỉnh × giới tính | 20 | | | | | | |
| Q4 | Tạm trú hiệu lực theo quê (JOIN / mảng nhúng) | 10 | | | | | | |
| Q5 | Thành viên hộ lập 3/2000 (JOIN 3 bảng / nhúng) | 4048 | | | | | | |
| Q5b | Như Q5 nhưng dùng `$lookup` (chỉ Mongo) | 4048 | — | | — | | — | — |
| W1 | Thêm 1 nhân khẩu (3 bảng + giao dịch / 3 collection) | 1 | | | | | | |
| W2 | Đổi họ tên 502 người (1 bảng / 2 collection) | 502 | | | | | | |
| W2b | Đổi lại tên cũ | 502 | | | | | | |
| W3 | Nhập lô 100.000 biến động | 100000 | | | | | | |
| W4 | Xóa lô 100.000 biến động | 100000 | | | | | | |
| W5 | Xóa nhân khẩu + dữ liệu liên quan (CASCADE / tự xóa) | 1 | | | | | | |

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
| ix_nk_que_quan_gioi_tinh | que_quan, gioi_tinh | | |
| ix_tttv_trang_thai_loai | trang_thai, loai (Mongo: multikey trên mảng) | | |
| ix_bd_loai_ngay | loai_bien_dong, ngay_bien_dong (làm W3 chậm hơn) | | |
| ix_hk_ngay_lap | ngay_lap | | |

| | MySQL dữ liệu (MB) | MySQL index (MB) | Mongo dữ liệu trên đĩa (MB) | Mongo index (MB) |
|---|---:|---:|---:|---:|
| Trước khi tạo index phụ | | | | |
| Sau khi tạo index phụ | | | | |

(MySQL: cộng các bảng tương ứng. Mongo `storageSize` là dung lượng đã nén snappy, còn `size` là chưa nén; nên ghi cả hai.)

### 6.4. Vẽ biểu đồ bằng `07_plot_results.py` (tùy chọn)

Script vẽ đọc được file CSV có các cột của `06_benchmark.py`. Tạo file `results\thu_cong\ket_qua_1m.csv` (để trong thư mục con riêng, tránh ghi đè ảnh `scale_*.png` của benchmark), mỗi câu một dòng cho mỗi hệ và mỗi chế độ:

```csv
label,mode,op,group,title,system,rows,n,median_ms,p95_ms
1m,no_index,Q1,read,Tìm theo họ tên,MySQL,502,3,734,760
1m,no_index,Q1,read,Tìm theo họ tên,MongoDB,502,3,812,830
1m,with_index,Q1,read,Tìm theo họ tên,MySQL,502,3,1.2,1.5
...
```

- `median_ms` = trung vị 3 lần; `p95_ms` = lần chậm nhất trong 3 lần.
- Phải điền đủ số, không để trống. Q5b chỉ có dòng MongoDB. Câu ghi để `group` = `write`.
- Số ở ví dụ trên là minh họa, thay bằng số thật.

```powershell
py -3.12 07_plot_results.py results\thu_cong\ket_qua_1m.csv
```

Kết quả gồm `ket_qua_1m_no_index.png`, `ket_qua_1m_with_index.png` và `ket_qua_1m_summary.md` (bảng có sẵn cột "Nhanh hơn ×k"). Nếu đo thêm bộ 100k (nạp lại 100k vào **cả hai** DB rồi làm lại toàn bộ từ mục 1), tạo thêm `ket_qua_100k.csv` với `label` = `100k` rồi chạy `07_plot_results.py results\thu_cong\ket_qua_*.csv` để có biểu đồ theo quy mô.

---

## 7. Lệnh xóa cache (khi cần)

Chạy trong **PowerShell mở bằng Run as Administrator**. Sau khi xóa cache, chạy lại PHẦN 0 (MySQL) hoặc lệnh `setParameter` (Mongo) để đặt lại cache 2 GB.

**MySQL** (xóa buffer pool):
```powershell
Stop-Service MYSQL80
Remove-Item "C:\ProgramData\MySQL\MySQL Server 8.0\Data\ib_buffer_pool" -ErrorAction SilentlyContinue
Start-Service MYSQL80
```
Bắt buộc phải xóa file `ib_buffer_pool`. Nếu không, MySQL tự nạp lại cache cũ khi khởi động.

**MongoDB** (xóa WiredTiger cache và cache file của Windows):
```powershell
Stop-Service MongoDB
D:\BTL_DBM\tools\RAMMap64.exe -accepteula -Et
Start-Service MongoDB
```
`RAMMap64.exe` tải miễn phí tại https://learn.microsoft.com/sysinternals/downloads/rammap , giải nén vào `D:\BTL_DBM\tools\`. Không có RAMMap thì vẫn restart được, nhưng Windows còn giữ file dữ liệu trong RAM nên Mongo chưa lạnh hoàn toàn.

---

## 8. Gợi ý phân tích từng truy vấn trong báo cáo

Dùng số liệu thật để xác nhận hoặc bác bỏ các giả thuyết dưới đây. **Đừng chép kết luận nếu số liệu nói khác.**

| Câu | Điểm cần phân tích |
|---|---|
| Q1 | Không index: cả hai phải quét toàn bộ 1M bản ghi. Document Mongo chứa mảng nhúng (`ho_khau`, `tam_tru_tam_vang`) nên to hơn một dòng `nhan_khau`, vì vậy quét có thể chậm hơn. Có index: cả hai chỉ đọc 502 khóa. So `docsExamined` / `rows` trước và sau. |
| Q2 | Index ghép `(que_quan, ho_ten)` vừa lọc vừa có sẵn thứ tự, nên mất bước sắp xếp (`Using filesort` hoặc stage `SORT` biến mất). Regex `^…` của Mongo tương đương `LIKE 'abc%'`. |
| Q3 | Gom nhóm trên toàn bộ dữ liệu. Có index `(que_quan, gioi_tinh)`, MySQL có thể quét index (`type=index`, `Using index`) thay vì quét bảng. Mongo `$group` không có `$match` thường vẫn `COLLSCAN`, tức là index gần như không giúp. Đây là điểm khác biệt đáng nêu. |
| Q4 | Mô hình dữ liệu khác nhau: MySQL phải **JOIN** `tam_tru_tam_vang` với `nhan_khau`. Mongo không cần JOIN (dữ liệu nhúng) nhưng phải `$unwind`, và index trên mảng là **multikey index**. |
| Q5 vs Q5b | Lợi ích của **nhúng dữ liệu**: Q5 (Mongo, nhúng `members`) so với Q5 (MySQL, JOIN 3 bảng) và Q5b (Mongo, `$lookup`). Thông thường `$lookup` chậm hơn JOIN của MySQL; nhúng thì nhanh hơn cả hai. |
| W1 | Cách viết khác nhau: MySQL 3 `INSERT` vào 3 bảng, bọc trong giao dịch. Mongo 3 lệnh (`insertOne`, `updateOne` + `$push`, `insertOne`) **không có giao dịch** vì chạy standalone. Cả hai chỉ mất vài ms; điểm đáng nêu là tính toàn vẹn, không phải tốc độ. |
| W2 / W2b | **Cái giá của nhúng**: MySQL sửa 1 chỗ, Mongo phải sửa 2 chỗ (`citizens` và `households.members` với `arrayFilters`). Không có index `ho_ten` thì cả hai phải quét toàn bộ để tìm 502 người; có index thì tìm nhanh nhưng phải cập nhật thêm index. |
| W3 / W4 | Ghi và xóa số lượng lớn. So không index với có index (`ix_bd_loai_ngay`) để thấy **index làm chậm ghi**. MySQL dùng `INSERT … SELECT`, Mongo dùng `$merge`; cả hai xử lý trên server. |
| W5 | MySQL 1 câu `DELETE`, khóa ngoại `ON DELETE CASCADE` tự xóa dữ liệu liên quan. Mongo không có khóa ngoại, phải tự xóa ở 3 nơi (`deleteOne`, `$pull`, `deleteMany`); quên một bước là còn dữ liệu mồ côi. |
| Index | So thời gian tạo và dung lượng index. Index giúp đọc nhanh nhưng tốn đĩa và làm chậm ghi (xem W3). |

### Những hạn chế cần ghi rõ trong báo cáo

- Đo trên một máy cá nhân, MongoDB chạy standalone (không replica set, không sharding), nên kết quả không đại diện cho môi trường production.
- Thời gian (A) bao gồm cả chi phí của công cụ (Workbench / shell Compass). Vì vậy có thêm số (B) từ `EXPLAIN ANALYZE` / `executionStats` để đối chiếu.
- Câu đọc chỉ đo 3 lần, câu ghi chỉ đo 1 lần. Nếu cần nhiều lần lặp và phân vị p95 thì lấy từ `06_benchmark.py`.
- Hai bên dùng mô hình dữ liệu khác nhau (chuẩn hóa so với nhúng). Kết quả phản ánh **hệ quản trị cộng với cách thiết kế dữ liệu**, không chỉ riêng engine.
