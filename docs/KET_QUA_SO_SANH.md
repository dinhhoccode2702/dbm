# Kết quả so sánh hiệu năng MySQL và MongoDB (bộ 1M)

Tài liệu này tổng hợp thời gian chạy của 5 truy vấn đọc (Q1–Q5, thêm Q5b chỉ có ở MongoDB) và 5 thao tác ghi (W1–W5) trong [03_queries_mysql.sql](../03_queries_mysql.sql) và [05_queries_mongodb.js](../05_queries_mongodb.js). Mỗi câu được chạy ở 2 chế độ: chỉ có index cơ bản, và có thêm index phụ.

## 1. Môi trường và nguồn số liệu

| Mục | Giá trị |
|---|---|
| Dữ liệu | 1.000.000 nhân khẩu, 250.000 hộ, 200.000 biến động |
| MySQL | 8.0.44, InnoDB, `innodb_buffer_pool_size` = 2 GB, `innodb_flush_log_at_trx_commit` = 1, binlog bật |
| MongoDB | 8.0.13 standalone, WiredTiger cache = 2 GB, ghi với `writeConcern { j: true }` |
| Máy | Laptop cá nhân, Windows 11, cả 2 server chạy trên cùng máy và dùng chung ổ C |

Số liệu có 2 nguồn:

- **(A) Đo tay, có ảnh chụp:** chạy trong MySQL Workbench và shell của MongoDB Compass, ngày 26/11/2026. Ảnh lưu trong [results/thu_cong/anh/](../results/thu_cong/anh/).
- **(B) Đo bằng script Python:** dùng `pymysql` và `pymongo`, cùng câu lệnh với 2 file trên. Mỗi câu đọc chạy 1 lần làm nóng rồi đo 3 lần, lấy trung vị. Mỗi câu ghi chạy trọn bộ W1→W5 3 lượt, lấy trung vị. Số liệu thô nằm ở [results/thu_cong/do_bang_script_1m.json](../results/thu_cong/do_bang_script_1m.json).

Nguồn (B) được dùng để **phân tích chính**, vì 3 lý do:
- Hai hệ được đo bằng cùng một công cụ, nên phần chi phí của công cụ là như nhau.
- Nguồn (A) thiếu một số câu ghi (mục 2.3).
- Với truy vấn trả về ít dòng, công cụ làm lệch số đo: Workbench chỉ hiển thị tới 1 ms, còn shell của Compass tốn vài chục ms để dựng kết quả.

Với các truy vấn nặng, (A) và (B) khớp nhau, sai lệch dưới 10% (bảng 2.1 và 3.1).

## 2. Số liệu đo tay từ ảnh chụp (A)

### 2.1. Truy vấn đọc, đơn vị ms

| Câu | MySQL không idx | Mongo không idx | MySQL có idx | Mongo có idx | Ảnh |
|---|---:|---:|---:|---:|---|
| Q1 | 1266 (578 + 688 fetch) | 1293 | < 1 | 80 | 02, 06, 04, 12 |
| Q2 | 922 | 1840 | < 1 | 15 | 02, 06, 04, 12 |
| Q3 | 3343 | 971 | 891 | 702 | 02, 07, 04, 12 |
| Q4 | 312 | 1669 | 172 | 70 | 02, 08, 04, 12 |
| Q5 | 984 | 1462 | 109 (93 + 16 fetch) | 61 | 02, 09, 04, 12 |
| Q5b | — | 1185 | — | 393 | 09, 12 |

Cách đọc số trong ảnh:
- **MySQL:** thời gian = Duration + Fetch, lấy ở lần chạy thứ 2 (dòng 20–24 và 34–38 trong panel Output). "< 1" nghĩa là Workbench hiển thị `0.000 sec`.
- **MongoDB không index:** lần chạy này dùng phiên bản cũ của file `.js` nên tên câu trong ảnh khác tên mới. Câu được đổi tên như sau:

  | Tên trong ảnh | Tên mới |
  |---|---|
  | Q4 | Q3 |
  | Q5 | Q4 |
  | Q7 | Q5 |
  | Q7b | Q5b |

  Q1 lấy lần đo thứ 4 (các lần đo: 3664, 1137, 1237, 1293 ms; lần đầu chậm vì còn đọc đĩa).

### 2.2. Thời gian tạo index, đơn vị ms

| Index | MySQL | MongoDB | Ảnh |
|---|---:|---:|---|
| ix_nk_ho_ten | 6125 | 6281 | 03, 11 |
| ix_nk_que_quan_ho_ten | 8782 | 5988 | 03, 11 |
| ix_nk_que_quan_gioi_tinh | 5656 | 6359 | 03, 11 |
| ix_tttv_trang_thai_loai | **391** | **6328** | 03, 11 |
| ix_hk_ngay_lap | 890 | 1902 | 03, 11 |
| ix_bd_loai_ngay | 1438 | 1640 | 03, 11 |

### 2.3. Thao tác ghi, đơn vị ms, và những câu chưa đo được

| Câu | MySQL không idx | Mongo không idx | MySQL có idx | Mongo có idx |
|---|---:|---:|---:|---:|
| W1 | ≈ 16 | 55 | thiếu | 39 |
| W2 | **lỗi 1175** | 2700 | 32 | thiếu |
| W2b | **lỗi 1175** | 902 | 62 | thiếu (chạy khi không còn ai cần đổi tên, 0 người) |
| W3 | 4938 | 4441 | 5563 | thiếu |
| W4 | thiếu | thiếu | thiếu | thiếu |
| W5 | thiếu | 55 | thiếu | thiếu |

Nguyên nhân thiếu số:
- **Lỗi 1175 ở MySQL:** Workbench bật sẵn "safe update mode", nên chặn `UPDATE`/`DELETE` có `WHERE` trên cột không có index. Ở chế độ không index, W2 và W4 đều bị chặn. Đã sửa bằng cách thêm `SET SQL_SAFE_UPDATES = 0;` vào PHẦN 0 của file `.sql`.
- **Chưa chạy W4 ở chế độ nào:** vì vậy dữ liệu thử còn sót lại trong DB, gồm 200.000 biến động ở MySQL và 100.000 ở MongoDB. Ở chế độ có index, W3 của MySQL được đo khi bảng đã có sẵn 100.000 dòng thử. Dữ liệu sót đã được dọn trước khi đo (B).
- **W1 chạy lại bị trùng khóa:** ảnh 01 có lỗi `Duplicate entry` ở MySQL, ảnh 13 có lỗi `E11000` ở MongoDB.

## 3. Số liệu đo bằng script (B), dùng để phân tích

Biểu đồ:
- [không index](../results/thu_cong/ket_qua_1m_no_index.png)
- [có index](../results/thu_cong/ket_qua_1m_with_index.png)

Trục thời gian dùng thang log.

### 3.1. Truy vấn đọc, đơn vị ms, trung vị 3 lần

| Câu | Nội dung | MySQL không idx | Mongo không idx | MySQL có idx | Mongo có idx |
|---|---|---:|---:|---:|---:|
| Q1 | Tìm theo họ tên (502 dòng) | 1028 | 1180 | 6.1 | 5.8 |
| Q2 | Tỉnh + tiền tố tên, sắp xếp, 100 dòng | 881 | 1794 | 3.4 | 2.7 |
| Q3 | Thống kê tỉnh × giới tính | 3274 | **968** | 931 | 859 |
| Q4 | Tạm trú hiệu lực theo quê | **190** | 1679 | 128 | 101 |
| Q5 | Thành viên các hộ lập 3/2000 (4048 dòng) | 315 | 466 | 109 | **49** |
| Q5b | Như Q5 nhưng Mongo dùng `$lookup` | — | 759 | — | 355 |

Kế hoạch thực thi lấy từ `EXPLAIN` và `explain("executionStats")`:

| Câu | MySQL không idx | MySQL có idx | Mongo không idx | Mongo có idx |
|---|---|---|---|---|
| Q1 | ALL | ref `ix_nk_ho_ten` | COLLSCAN, đọc 1.000.000 doc | IXSCAN, đọc 502 doc |
| Q2 | ALL | range `ix_nk_que_quan_ho_ten` | SORT ← COLLSCAN, 1.000.000 doc | LIMIT ← IXSCAN, đọc 100 doc |
| Q3 | ALL | index `ix_nk_que_quan_gioi_tinh` (quét toàn bộ index) | COLLSCAN | **vẫn COLLSCAN** |
| Q4 | `t`: ALL, `nk`: eq_ref PRIMARY | `t`: ref `ix_tttv_trang_thai_loai` | COLLSCAN, 1.000.000 doc | IXSCAN multikey, đọc 9.972 doc |
| Q5 | `hk`: ALL, `tv`: ref, `nk`: eq_ref | `hk`: range `ix_hk_ngay_lap` | COLLSCAN, 250.000 doc | IXSCAN, đọc 1.012 doc |

### 3.2. Thao tác ghi, đơn vị ms, trung vị 3 lượt

| Câu | Nội dung | MySQL không idx | Mongo không idx | MySQL có idx | Mongo có idx |
|---|---|---:|---:|---:|---:|
| W1 | Thêm 1 nhân khẩu vào hộ | 9.0 | 11.8 | 6.7 | 6.7 |
| W2 | Đổi tên 502 người | 2968 | **1276** | 61 | 58 |
| W2b | Đổi lại tên cũ | 3041 | 1292 | 37 | 92 |
| W3 | Nhập lô 100.000 biến động | 4838 | **3440** | 7330 | **4363** |
| W4 | Xóa lô 100.000 biến động | **3316** | 4265 | **4231** | 5688 |
| W5 | Xóa nhân khẩu và dữ liệu liên quan | 7.9 | 14.4 | 3.7 | 8.3 |

## 4. Nhận xét và giải thích

### 4.1. Index quyết định tốc độ tìm kiếm, ở cả hai hệ như nhau (Q1, Q2)

- **Không có index:** cả hai phải quét toàn bộ 1 triệu bản ghi, mất khoảng 1 giây.
- **Có index:** cả hai chỉ đọc đúng 502 hoặc 100 khóa, mất 3–6 ms, **nhanh hơn khoảng 170–650 lần**.
- **Khi có index, hai hệ gần như bằng nhau,** vì cả hai cùng dùng cấu trúc B-tree: đi từ gốc xuống lá rồi đọc các bản ghi cần lấy.

Khi không index, MongoDB chậm hơn ở Q2 (1794 so với 881 ms) vì hai lý do:
- Điều kiện `/^Tran Thi/` là biểu thức chính quy. MongoDB phải chạy bộ máy regex trên từng document, tốn hơn phép so sánh tiền tố của `LIKE 'Tran Thi%'`.
- MongoDB còn phải sắp xếp kết quả trong bộ nhớ (stage `SORT`).

Document của MongoDB cũng lớn hơn một dòng `nhan_khau`, vì chứa thêm `ho_khau` và mảng `tam_tru_tam_vang`. Do đó quét toàn bộ tốn hơn một chút. Điều này cũng thấy ở Q1: 1180 so với 1028 ms.

### 4.2. Gom nhóm toàn bảng: MongoDB nhanh hơn, nhưng index không giúp được MongoDB (Q3)

- **Không có index:** MongoDB nhanh hơn MySQL khoảng 3,4 lần (968 so với 3274 ms). Có hai lý do:
  - MySQL gom nhóm bằng bảng tạm nội bộ rồi sắp xếp.
  - Cột `que_quan` dùng collation `utf8mb4_0900_ai_ci` (không phân biệt dấu và hoa thường), nên mỗi phép so sánh chuỗi tốn hơn. `$group` của MongoDB dùng bảng băm và so sánh chuỗi theo byte.
- **Có index `(que_quan, gioi_tinh)`:**
  - MySQL quét thẳng index. Dữ liệu trong index đã sắp xếp sẵn theo đúng 2 cột cần nhóm, nên không cần bảng tạm, thời gian giảm từ 3274 xuống 931 ms.
  - MongoDB **vẫn quét toàn bộ collection** (COLLSCAN), vì `$group` không có `$match` đứng trước thì bộ tối ưu không chọn index. Thời gian gần như không đổi (968 thành 859 ms).

Sau khi có index, hai hệ ngang nhau. Đây là khác biệt đáng chú ý: cùng một index, MySQL tận dụng được cho `GROUP BY`, còn MongoDB thì không.

### 4.3. Nhúng dữ liệu: lợi khi đọc theo "cha", thiệt khi đọc theo "con" (Q4, Q5, Q5b)

**Q4: hồ sơ tạm trú, MySQL thắng khi không có index.** Đếm hồ sơ tạm trú là truy vấn xoay quanh dữ liệu "con":
- MySQL chỉ cần quét bảng `tam_tru_tam_vang`. Bảng này nhỏ, khoảng 9 MB so với 80 MB của `nhan_khau`. Sau đó MySQL tra khóa chính để lấy quê quán của 9.972 người, mất 190 ms.
- MongoDB nhúng hồ sơ tạm trú vào document công dân, nên không có collection nhỏ nào để quét. MongoDB phải đọc đủ 1.000.000 document, mất 1679 ms, chậm hơn khoảng 9 lần.

Khi có multikey index trên mảng, MongoDB chỉ đọc 9.972 document. Lúc này hai bên ngang nhau (101 so với 128 ms).

**Q5: danh sách thành viên hộ, MongoDB thắng khi có index.** Đây là truy vấn xoay quanh dữ liệu "cha", đúng là thứ được nhúng:
- MongoDB đọc 1.012 document hộ, danh sách thành viên có sẵn bên trong, mất 49 ms.
- MySQL phải JOIN 3 bảng: 1.012 dòng `ho_khau`, rồi 4.048 lần tra `thanh_vien_ho`, rồi 4.048 lần tra `nhan_khau`, mất 109 ms. **MongoDB nhanh hơn khoảng 2,2 lần.**

**Q5b: `$lookup` là cách "JOIN" của MongoDB, và chậm.** Cùng kết quả với Q5 nhưng không dùng dữ liệu nhúng mà tra sang `citizens`:
- Mất 355 ms, chậm hơn **7 lần** so với đọc dữ liệu nhúng ở Q5.
- Chậm hơn **3 lần** so với JOIN của MySQL.

Lý do là `$lookup` chạy riêng một truy vấn con cho từng document hộ, rồi dựng mảng kết quả dạng BSON. JOIN của MySQL được tối ưu sẵn trong bộ máy thực thi và chỉ trả về các cột cần.

**Kết luận:** thiết kế nhúng giúp MongoDB nhanh khi truy vấn đi đúng hướng nhúng (từ hộ xuống thành viên). Ngược hướng (từ tạm trú lên công dân) thì MongoDB phải đọc nhiều hơn. Thiết kế chuẩn hóa của MySQL không thiên về hướng nào, nhưng luôn phải trả chi phí JOIN.

### 4.4. Index tốn thời gian tạo và làm chậm ghi (bảng 2.2, W3, W4)

- **Tạo index trên 1 triệu bản ghi mất khoảng 6 giây ở cả hai hệ.**
- **Riêng `ix_tttv_trang_thai_loai`, MySQL chỉ mất 0,4 giây còn MongoDB mất 6,3 giây.** MySQL tạo index trên bảng nhỏ `tam_tru_tam_vang`. MongoDB phải tạo trên mảng nằm trong 1 triệu document công dân. Đây lại là hệ quả của việc nhúng.
- **W3 (nhập lô 100.000 dòng):** khi thêm index `ix_bd_loai_ngay`, MySQL chậm thêm 52% (4838 lên 7330 ms), MongoDB chậm thêm 27% (3440 lên 4363 ms). Mỗi dòng mới phải được chèn vào mọi index của bảng.
- **W4 (xóa 100.000 dòng):** cũng chậm hơn khoảng 30% ở cả hai hệ khi có thêm index.

Ở W3, MongoDB nhanh hơn MySQL (3440 so với 4838 ms khi không index). Có 3 lý do:
1. Với mỗi dòng mới, MySQL phải kiểm tra khóa ngoại `nhan_khau_id`, tức tra bảng `nhan_khau`. MongoDB không có khóa ngoại nên không phải kiểm tra.
2. MySQL đang bật binlog, nên mọi thay đổi được ghi thêm một lần vào binlog. MongoDB chạy standalone không có oplog.
3. `INSERT … SELECT` đọc và ghi cùng một bảng, nên MySQL phải chép kết quả `SELECT` ra bảng tạm trước khi chèn.

Ngược lại, ở W4 MySQL nhanh hơn (3316 so với 4265 ms). InnoDB chỉ đánh dấu dòng bị xóa, còn việc dọn dẹp thật được một luồng chạy nền (purge) làm sau. MongoDB xóa ngay từng document khỏi dữ liệu và khỏi mọi index.

### 4.5. Cập nhật dữ liệu bị lặp: MongoDB phải làm nhiều việc hơn (W2)

Về cách viết:
- MySQL đổi tên bằng **1 câu `UPDATE`**.
- MongoDB phải sửa **2 nơi**: `citizens` và mảng `households.members`, dùng `arrayFilters` để chỉ sửa đúng phần tử. Đây là cái giá của việc nhúng bản sao họ tên vào hộ (để Q5 nhanh).

Về thời gian:
- **Có index `ho_ten`:** hai bên ngang nhau (61 và 58 ms). Mỗi bên chỉ tìm 502 bản ghi qua index. Phần việc thêm của MongoDB nhỏ, vì việc tìm hộ dùng index `members.citizenId`.
- **Không có index:** MySQL chậm hơn rõ (2968 so với 1276 ms). Khi `UPDATE` quét toàn bảng, InnoDB **khóa từng dòng nó đọc qua** (mức cô lập REPEATABLE READ), nên quét 1 triệu dòng kèm khóa tốn hơn quét thường. MongoDB tách thành 2 bước: `distinct` quét để lấy 502 `_id` (không khóa), sau đó cập nhật theo `_id`.

Bài học thực tế: trong MySQL, `UPDATE` hay `DELETE` với `WHERE` không có index vừa chậm, vừa khóa nhiều dòng, nên Workbench mới chặn mặc định bằng "safe update mode".

### 4.6. Ghi một bản ghi: nhanh như nhau, khác nhau ở tính toàn vẹn (W1, W5)

Cả hai chỉ mất vài ms. MongoDB chậm hơn một chút (W5: 14,4 so với 7,9 ms) vì gửi 3 lệnh riêng, mỗi lệnh chờ ghi journal xuống đĩa (`j: true`). MySQL gom 3 câu vào 1 giao dịch và chỉ ghi đĩa 1 lần khi `COMMIT`.

Điểm khác biệt quan trọng nằm ở tính toàn vẹn chứ không ở tốc độ:
- **W1:** MySQL bọc 3 câu `INSERT` trong giao dịch, nên hoặc đủ cả 3 hoặc không có gì. MongoDB standalone không có giao dịch nhiều document: lỗi ở lệnh thứ 2 thì lệnh thứ 1 vẫn đã ghi.
- **W5:** MySQL chỉ cần 1 câu `DELETE`. Khóa ngoại `ON DELETE CASCADE` tự xóa dữ liệu liên quan trong `thanh_vien_ho` và `bien_dong`. MongoDB phải tự xóa ở 3 nơi; quên một bước là còn dữ liệu "mồ côi".

## 5. Tổng kết

| Tình huống | Hệ có lợi hơn | Lý do chính |
|---|---|---|
| Tìm kiếm có index (Q1, Q2) | Ngang nhau | Cùng dùng B-tree |
| Tìm kiếm không index | MySQL, nhẹ | Dòng nhỏ hơn document; `LIKE` rẻ hơn regex |
| Gom nhóm toàn bảng không index (Q3) | MongoDB | `$group` dùng bảng băm; MySQL dùng bảng tạm và so sánh theo collation |
| Gom nhóm có index (Q3) | Ngang nhau | MySQL dùng được index; MongoDB thì không |
| Đọc theo hướng nhúng (Q5) | MongoDB | Không cần JOIN |
| Đọc ngược hướng nhúng (Q4, không index) | MySQL | Bảng con nhỏ, quét nhanh |
| JOIN thực sự (Q5b so với Q5 của MySQL) | MySQL | `$lookup` chậm hơn JOIN khoảng 3 lần |
| Ghi lô lớn (W3) | MongoDB | Không kiểm tra khóa ngoại, không có binlog |
| Xóa lô lớn (W4) | MySQL | InnoDB dọn dẹp chậm ở luồng nền |
| Sửa dữ liệu bị lặp (W2) | MySQL về cách viết; tốc độ ngang nhau khi có index | MongoDB phải sửa 2 nơi |
| Toàn vẹn khi ghi nhiều nơi (W1, W5) | MySQL | Giao dịch và khóa ngoại `CASCADE` |

Không có hệ nào thắng tuyệt đối. **Index** ảnh hưởng tới tốc độ nhiều hơn việc chọn hệ nào: chênh lệch giữa có và không có index lên tới hàng trăm lần, còn chênh lệch giữa hai hệ thường chỉ 1–9 lần. Với MongoDB, **thiết kế nhúng** quyết định truy vấn nào nhanh, truy vấn nào chậm. Với MySQL, cái giá thường trực là JOIN, đổi lại là toàn vẹn dữ liệu được hệ quản trị bảo đảm.

## 6. Hạn chế

- Đo trên một laptop. Cả hai server dùng chung CPU, RAM và ổ C, và MongoDB chạy standalone. Kết quả không đại diện cho môi trường máy chủ thật.
- Toàn bộ dữ liệu khoảng 300–700 MB, nằm vừa trong bộ nhớ đệm 2 GB. Vì vậy số liệu phản ánh tốc độ khi **dữ liệu đã ở trong RAM**, chưa thể hiện ảnh hưởng của đọc đĩa.
- Câu đọc chỉ đo 3 lần, câu ghi 3 lượt. Chênh lệch dưới khoảng 15% (ví dụ Q1 và Q2 khi có index, W2 khi có index) nên coi là ngang nhau.
- Số đo bằng script (B) tính cả thời gian thư viện Python nhận và chuyển dữ liệu, như nhau cho cả hai hệ. Số đo tay (A) tính cả chi phí hiển thị của Workbench và Compass.
- Hai hệ dùng mô hình dữ liệu khác nhau (chuẩn hóa và nhúng), nên kết quả phản ánh **hệ quản trị cộng với cách thiết kế dữ liệu**, không chỉ riêng bộ máy lưu trữ.
