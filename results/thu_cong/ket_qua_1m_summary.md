### Bộ 1m - chỉ index cơ bản (PK/UNIQUE/FK)

| Mã | Thao tác | MySQL trung vị (ms) | MySQL p95 | MongoDB trung vị (ms) | MongoDB p95 | Nhanh hơn |
|---|---|---:|---:|---:|---:|---|
| Q1 | Tìm theo họ tên | 1028.10 | 1028.10 | 1179.90 | 1179.90 | tương đương |
| Q2 | Tỉnh + tiền tố tên, sort, 100 dòng | 880.90 | 880.90 | 1794.00 | 1794.00 | MySQL ×2.0 |
| Q3 | Thống kê tỉnh × giới tính | 3274.20 | 3274.20 | 968.40 | 968.40 | MongoDB ×3.4 |
| Q4 | Tạm trú theo quê (JOIN / mảng nhúng) | 189.80 | 189.80 | 1678.60 | 1678.60 | MySQL ×8.8 |
| Q5 | Thành viên hộ (JOIN 3 bảng / nhúng) | 314.80 | 314.80 | 465.70 | 465.70 | MySQL ×1.5 |
| Q5b | Như Q5, Mongo dùng $lookup | - | - | 758.80 | 758.80 | - |
| W1 | Thêm 1 nhân khẩu | 9.00 | 9.70 | 11.80 | 15.90 | MySQL ×1.3 |
| W2 | Đổi tên 502 người | 2967.90 | 3121.80 | 1276.00 | 1305.10 | MongoDB ×2.3 |
| W2b | Đổi lại tên | 3041.40 | 3123.20 | 1292.40 | 1382.90 | MongoDB ×2.4 |
| W3 | Nhập lô 100k biến động | 4837.70 | 4865.60 | 3440.20 | 3537.10 | MongoDB ×1.4 |
| W4 | Xóa lô 100k biến động | 3316.10 | 3530.60 | 4265.40 | 4433.60 | MySQL ×1.3 |
| W5 | Xóa 1 nhân khẩu + liên quan | 7.90 | 14.60 | 14.40 | 15.00 | MySQL ×1.8 |

### Bộ 1m - có thêm index phụ

| Mã | Thao tác | MySQL trung vị (ms) | MySQL p95 | MongoDB trung vị (ms) | MongoDB p95 | Nhanh hơn |
|---|---|---:|---:|---:|---:|---|
| Q1 | Tìm theo họ tên | 6.10 | 6.10 | 5.80 | 5.80 | tương đương |
| Q2 | Tỉnh + tiền tố tên, sort, 100 dòng | 3.40 | 3.40 | 2.70 | 2.70 | MongoDB ×1.3 |
| Q3 | Thống kê tỉnh × giới tính | 930.70 | 930.70 | 858.70 | 858.70 | tương đương |
| Q4 | Tạm trú theo quê (JOIN / mảng nhúng) | 128.30 | 128.30 | 101.00 | 101.00 | MongoDB ×1.3 |
| Q5 | Thành viên hộ (JOIN 3 bảng / nhúng) | 109.10 | 109.10 | 49.00 | 49.00 | MongoDB ×2.2 |
| Q5b | Như Q5, Mongo dùng $lookup | - | - | 355.40 | 355.40 | - |
| W1 | Thêm 1 nhân khẩu | 6.70 | 10.20 | 6.70 | 9.90 | tương đương |
| W2 | Đổi tên 502 người | 60.70 | 84.30 | 58.30 | 114.60 | tương đương |
| W2b | Đổi lại tên | 36.90 | 39.20 | 92.30 | 123.80 | MySQL ×2.5 |
| W3 | Nhập lô 100k biến động | 7330.10 | 7500.20 | 4362.50 | 4457.10 | MongoDB ×1.7 |
| W4 | Xóa lô 100k biến động | 4231.30 | 4431.30 | 5688.00 | 5907.60 | MySQL ×1.3 |
| W5 | Xóa 1 nhân khẩu + liên quan | 3.70 | 4.30 | 8.30 | 9.80 | MySQL ×2.2 |

'Tương đương' = chênh lệch dưới 15%. ×k = bên nhanh hơn nhanh gấp k lần (theo trung vị).
