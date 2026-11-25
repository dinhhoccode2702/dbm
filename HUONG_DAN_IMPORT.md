# Hướng dẫn tự import dữ liệu vào MySQL và MongoDB

Mục tiêu: nạp **cùng một bộ dữ liệu** vào cả hai hệ, chụp ảnh làm minh chứng cho thời gian import, số bản ghi và dung lượng.

Thứ tự làm: **bộ 100k trước, bộ 1M sau**. Như vậy cuối cùng cả hai DB đều chứa bộ 1M, là bộ dùng cho benchmark chính.

> Ký hiệu 📸 = chỗ cần chụp màn hình. Gợi ý đặt tên ảnh có sẵn ở mỗi bước.

---

## 0. Chuẩn bị

### 0.1. Các file trong thư mục `D:\BTL_DBM`

| File | Dùng để |
|---|---|
| `generate_data.py` | Sinh 5 file CSV (đã sinh sẵn trong `data\1m` và `data\100k`) |
| `01_schema_mysql.sql` | Tạo database và 5 bảng MySQL |
| `02_load_mysql_100k.sql` | Nạp bộ 100k vào MySQL |
| `02_load_mysql.sql` | Nạp bộ 1M vào MySQL |
| `04_load_mongodb.py` | Nạp CSV vào MongoDB (tự in thời gian và dung lượng) |
| `03_queries_mysql.sql`, `05_queries_mongodb.js` | 8 truy vấn nặng (Q1–Q8) giống nhau ở 2 DB, chạy tay trong Workbench/Compass theo 2 phần: không index phụ và có index phụ |
| `06_benchmark.py`, `07_plot_results.py` | Đo hiệu năng và vẽ biểu đồ (mục 5) |
| `docs\` | Tài liệu nghiệp vụ và thiết kế CSDL |

### 0.2. Kiểm tra dữ liệu CSV

Mở PowerShell, chạy:

```powershell
cd D:\BTL_DBM
Get-ChildItem data\100k, data\1m | Select-Object Directory, Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
```

Nếu thư mục `data` trống hoặc bị xóa, sinh lại (seed cố định nên lần nào sinh cũng ra đúng một bộ dữ liệu):

```powershell
py -3.12 generate_data.py --count 100000  --output-dir data\100k
py -3.12 generate_data.py --count 1000000 --output-dir data\1m
```

📸 `00_csv_files.png`: danh sách file CSV và dung lượng.

### 0.3. Ghi lại cấu hình máy (bắt buộc phải có trong báo cáo hiệu năng)

```powershell
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
"RAM (GB): {0:N1}" -f ((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
Get-PhysicalDisk | Select-Object FriendlyName, MediaType, Size
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" --version
& "C:\Program Files\MongoDB\Server\8.0\bin\mongod.exe" --version | Select-Object -First 1
py -3.12 -c "import pymongo; print('pymongo', pymongo.version)"
```

📸 `00_cau_hinh_may.png`

### 0.4. Để số đo công bằng

- Đóng các chương trình nặng (trình duyệt nhiều tab, game, IDE đang build).
- **Đóng MongoDB Compass và MySQL Workbench trong lúc import.** Đã có lần Compass xóa database giữa lúc đang nạp.
- Cắm sạc laptop. Khi chạy pin, CPU bị hạ xung và kết quả đo bị sai lệch.
- Mỗi bộ dữ liệu nên import **3 lần**, lấy trung bình (hoặc trung vị). Ít nhất phải chụp một lần đầy đủ.

---

## 1. MySQL

### 1.1. Bật service và cho phép `LOAD DATA LOCAL`

```powershell
cd D:\BTL_DBM
$env:Path += ";C:\Program Files\MySQL\MySQL Server 8.0\bin"
Get-Service MYSQL80                      # Status phải là Running
mysql -u root -p -e "SET GLOBAL local_infile = 1; SELECT @@local_infile;"
```

- Nếu Status là `Stopped`: mở PowerShell bằng **Run as Administrator** rồi chạy `Start-Service MYSQL80`.
- `SET GLOBAL` mất hiệu lực khi MySQL khởi động lại. Khi đó chạy lại lệnh trên.

### 1.2. Tạo schema (chỉ làm một lần)

```powershell
mysql -u root -p -e "source 01_schema_mysql.sql"
```

Nếu database `quan_ly_nhan_khau` đã có từ trước thì không sao: script dùng `IF NOT EXISTS`, còn các script nạp ở bước sau tự TRUNCATE dữ liệu cũ.

### 1.3. Import và đo thời gian

Script dùng đường dẫn tuyệt đối `D:/BTL_DBM/data/...`. Nếu bạn để project ở thư mục khác, nhớ sửa đường dẫn trong 2 file `02_load_mysql*.sql`.

#### Cách A: MySQL Workbench

1. Bật phía server (chỉ cần một lần cho mỗi lần MySQL khởi động): chạy `SET GLOBAL local_infile = 1;` trong một tab query.
2. Bật phía client: về màn hình Home, chuột phải vào connection, chọn **Edit Connection…** → tab **Advanced** → ô **Others**, thêm một dòng `OPT_LOCAL_INFILE=1` → **Close**.
3. **Đóng tab connection đang mở rồi kết nối lại.** Cài đặt chỉ có hiệu lực với kết nối mới.
4. Mở file `02_load_mysql_100k.sql` (File → Open SQL Script), bấm ⚡ (Execute all).
5. Ở panel **Action Output** phía dưới, mỗi lệnh `LOAD DATA` hiện `100000 row(s) affected` kèm cột **Duration / Fetch**. Cột Duration chính là thời gian nạp.

📸 Chụp panel Action Output, phải thấy đủ 5 dòng `LOAD DATA` và cột Duration.

Nếu vẫn báo `Error Code: 3948` sau khi làm đủ các bước trên: kiểm tra bằng `SHOW GLOBAL VARIABLES LIKE 'local_infile';` (phải là `ON`), và chắc chắn bạn đã kết nối lại ở bước 3.

#### Cách B: dòng lệnh

Mở client MySQL ở chế độ tương tác:

```powershell
cd D:\BTL_DBM
mysql -u root -p --local-infile=1
```

Trong dấu nhắc `mysql>`:

```sql
source 02_load_mysql_100k.sql
```

Mỗi lệnh `LOAD DATA` sẽ in ra một dòng như sau:

```
Query OK, 100000 rows affected (0.85 sec)
Records: 100000  Deleted: 0  Skipped: 0  Warnings: 0
```

Kiểm tra:
- `Skipped: 0` và `Warnings: 0` ở cả 5 lệnh `LOAD DATA`. Nếu có Warnings, chạy `SHOW WARNINGS;` để xem nguyên nhân.
- Bảng đếm số dòng ở cuối: `100000 / 25000 / 100000 / 10000 / 20000`.
- `thanh_vien_mo_coi = 0`.

📸 `01_mysql_100k_load.png`: phần có 5 dòng `Query OK ... (x sec)`. Cuộn lên nếu cần, có thể chụp thành 2 ảnh.
📸 `02_mysql_100k_ketqua.png`: bảng số dòng, `thanh_vien_mo_coi` và bảng dung lượng (`data_mb`, `index_mb`).

Sau đó nạp bộ 1M, vẫn trong cùng cửa sổ `mysql>`:

```sql
source 02_load_mysql.sql
```

Số dòng phải là `1000000 / 250000 / 1000000 / 100000 / 200000`.

📸 `03_mysql_1m_load.png`, 📸 `04_mysql_1m_ketqua.png`

> **Thời gian import MySQL** = tổng thời gian của 5 lệnh `LOAD DATA`. Không tính TRUNCATE, ANALYZE hay các SELECT kiểm tra.
> Ghi vào bảng ở mục 3.
>
> **Lưu ý về `table_rows`:** cột này của `information_schema` chỉ là ước lượng, có thể lệch vài %. Số dòng chính xác là kết quả `COUNT(*)` ở bảng phía trên.

Muốn đo lại lần 2, lần 3: chạy lại `source 02_load_mysql.sql`. Script tự xóa dữ liệu cũ.

---

## 2. MongoDB

### 2.1. Kiểm tra service

```powershell
Get-Service MongoDB                      # Status phải là Running
py -3.12 -c "import pymongo; print(pymongo.version)"
```

Nếu báo thiếu pymongo: `py -3.12 -m pip install pymongo`.

### 2.2. Import và đo thời gian

```powershell
cd D:\BTL_DBM
py -3.12 04_load_mongodb.py --data-dir data\100k
```

Script tự xóa và tạo lại 3 collection, sau đó in ra:

```
citizens=100,000  households=25,000  population_logs=20,000  (đã đối chiếu)
Thời gian (giây):
  doc_bang_phu                0.76     <- đọc thanh_vien_ho + tam_tru_tam_vang vào RAM
  insert_citizens             6.74
  insert_households           1.03
  insert_population_logs      0.77
  create_indexes              1.97
  TONG                       11.28
Dung lượng (MB):  data(uncompressed) | storage(nén) | index
  ...
```

- `(đã đối chiếu)` nghĩa là số document trên server khớp với số đã gửi lên.
- Nếu script báo `LỖI: ... kỳ vọng ...`, có thể Compass hoặc chương trình khác đã can thiệp vào DB. Đóng chương trình đó rồi chạy lại.

📸 `05_mongo_100k.png`: toàn bộ output.

Sau đó nạp bộ 1M (mất khoảng 2–3 phút):

```powershell
py -3.12 04_load_mongodb.py --data-dir data\1m
```

Phải ra `citizens=1,000,000  households=250,000  population_logs=200,000  (đã đối chiếu)`.

📸 `06_mongo_1m.png`

### 2.3. (Tuỳ chọn) Ảnh minh chứng trong Compass

**Sau khi import xong**, mở MongoDB Compass và kết nối `mongodb://localhost:27017`. Vào database `quan_ly_nhan_khau`:
- Tab Collections hiển thị số document, dung lượng và số index của từng collection. 📸 `07_compass_collections.png`
- Mở `citizens` và xem một document: thông tin hộ (`ho_khau`) và mảng `tam_tru_tam_vang` được nhúng vào. 📸 `08_compass_citizen_doc.png`
- Mở `households` và xem mảng `members`. 📸 `09_compass_household_doc.png`

Hai ảnh document rất hữu ích ở phần "thiết kế lược đồ MongoDB" trong báo cáo.

---

## 3. Bảng ghi kết quả (điền vào báo cáo)

| Bộ dữ liệu | Hệ | Lần 1 (s) | Lần 2 (s) | Lần 3 (s) | Trung bình (s) | Dữ liệu (MB) | Index (MB) |
|---|---|---|---|---|---|---|---|
| 100k | MySQL (tổng 5 `LOAD DATA`) | | | | | | |
| 100k | MongoDB (`TONG`) | | | | | | |
| 1M | MySQL | | | | | | |
| 1M | MongoDB | | | | | | |

Cách lấy dung lượng:
- MySQL: cộng cột `data_mb` và `index_mb` của 5 bảng.
- MongoDB: cộng cột `storage(nén)` và `index` của 3 collection. Cột `data(uncompressed)` là kích thước BSON chưa nén, có thể nêu thêm để thấy hiệu quả nén của WiredTiger.

### Khi viết nhận xét, cần nói rõ hai quy trình khác nhau

- **MySQL** dùng `LOAD DATA INFILE`, công cụ nạp hàng loạt có sẵn trong server. Dữ liệu CSV dạng bảng được nạp thẳng, khóa chính và index được dựng trong lúc nạp (đã tắt `unique_checks` và `foreign_key_checks` để tăng tốc).
- **MongoDB** dùng script Python. Script phải đọc CSV, **dựng document lồng nhau** (nhúng hộ khẩu và tạm trú/tạm vắng vào nhân khẩu, nhúng thành viên vào hộ), rồi gửi lên qua `insert_many` theo lô 10.000 document. Index được tạo sau khi insert xong.
- Vì vậy thời gian import của MongoDB bao gồm cả bước biến đổi dữ liệu (ETL) mà MySQL không cần làm. Hai con số này **không phải phép so sánh tốc độ ghi thuần**. Tốc độ ghi thuần sẽ được đo riêng ở phần benchmark (insert/update/delete từng bản ghi và theo lô).

---

## 4. Lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| `ERROR 3948 (42000): Loading local data is disabled` | Phía server: `SET GLOBAL local_infile = 1;`. Phía client: dòng lệnh thì thêm `--local-infile=1`; Workbench thì thêm `OPT_LOCAL_INFILE=1` rồi kết nối lại (mục 1.3) |
| `ERROR 2068 (HY000): LOAD DATA LOCAL INFILE file request rejected` | Quên `--local-infile=1` khi mở `mysql` |
| `ERROR 2 (HY000): File '...' not found` | Sai đường dẫn: sửa `D:/BTL_DBM/data/...` trong file `.sql` cho đúng nơi để project |
| `ERROR 1049: Unknown database 'quan_ly_nhan_khau'` | Chưa chạy `01_schema_mysql.sql` |
| `ERROR 2003: Can't connect to MySQL server` | Service đã tắt: `Start-Service MYSQL80` (cần quyền Administrator) |
| `'mysql' is not recognized` | Chạy lại `$env:Path += ";C:\Program Files\MySQL\MySQL Server 8.0\bin"` |
| Python: `ServerSelectionTimeoutError` | MongoDB chưa chạy: `Start-Service MongoDB` (cần quyền Administrator) |
| Python: `LỖI: citizens có ... document, kỳ vọng ...` | Có chương trình khác xóa hoặc sửa DB trong lúc nạp. Đóng Compass rồi chạy lại |

---

## 5. Sau khi import: chạy benchmark

Điều kiện: cả hai DB chứa **cùng một bộ dữ liệu**. Script tự kiểm tra và dừng lại nếu hai bên không khớp.

```powershell
cd D:\BTL_DBM
py -3.12 -m pip install pymysql cryptography      # chỉ cần cài một lần
py -3.12 06_benchmark.py --label 1m --quick       # chạy thử khoảng 1 phút để chắc chắn mọi thứ chạy được
py -3.12 06_benchmark.py --label 1m               # chạy thật, khoảng 5-10 phút
```

- Đóng Compass và Workbench, đóng các chương trình nặng, cắm sạc trước khi chạy.
- Script đặt cache = 2 GB cho **cả** MySQL và MongoDB để so sánh công bằng. Cài đặt này hết hiệu lực khi restart service. Đổi bằng `--cache-gb 4`; dùng `--cache-gb 0` để giữ nguyên cấu hình hiện tại.
- Thao tác ghi chỉ tạo bản ghi thử (id ≥ 900.000.000) và tự xóa sau khi đo. Dữ liệu gốc không bị thay đổi.
- Kết quả được lưu vào `results\`:
  - `bench_1m_<thời gian>.csv`: số liệu.
  - `..._plans.csv`: kế hoạch thực thi (dùng index nào, có quét toàn bộ hay không).
  - `.json`: cấu hình môi trường đo.

📸 Chụp output trong cửa sổ PowerShell.

Vẽ biểu đồ và xuất bảng tổng hợp:

```powershell
py -3.12 07_plot_results.py results\bench_1m_<thời gian>.csv
```

Lệnh này tạo `..._no_index.png`, `..._with_index.png` và `..._summary.md`. Bảng trong `summary.md` có thể dán thẳng vào báo cáo.

**So sánh theo quy mô:** nạp lại bộ 100k vào **cả hai** DB (`02_load_mysql_100k.sql` và `04_load_mongodb.py --data-dir data\100k`), rồi chạy `py -3.12 06_benchmark.py --label 100k`. Sau đó vẽ biểu đồ từ cả hai file kết quả:

```powershell
py -3.12 07_plot_results.py results\bench_100k_*.csv results\bench_1m_*.csv
```

Lệnh này tạo thêm `scale_no_index.png` và `scale_with_index.png`. Nhớ nạp lại bộ 1M sau khi đo xong.
