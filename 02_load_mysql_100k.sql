-- Nạp 5 file CSV vào MySQL. Chạy được nhiều lần (TRUNCATE trước khi nạp).
-- Yêu cầu:
--   * Server: SET GLOBAL local_infile = 1;   (chạy một lần bằng tài khoản root)
--   * Client: mysql --local-infile=1 ...
--   * Workbench: Edit Connection > Advanced > Others thêm dòng OPT_LOCAL_INFILE=1, rồi kết nối lại.
--   * Đường dẫn CSV là tuyệt đối (D:/BTL_DBM/...). File này nạp bộ 100k; bộ 1m dùng 02_load_mysql.sql.
USE quan_ly_nhan_khau;
SET NAMES utf8mb4;

-- Tắt kiểm tra FK/unique trong phiên để nạp nhanh; dữ liệu sinh ra đã nhất quán.
SET SESSION foreign_key_checks = 0;
SET SESSION unique_checks = 0;

TRUNCATE TABLE bien_dong;
TRUNCATE TABLE tam_tru_tam_vang;
TRUNCATE TABLE thanh_vien_ho;
TRUNCATE TABLE ho_khau;
TRUNCATE TABLE nhan_khau;

LOAD DATA LOCAL INFILE 'D:/BTL_DBM/data/100k/nhan_khau.csv'
INTO TABLE nhan_khau
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(id, cccd, ho_ten, ngay_sinh, gioi_tinh, que_quan, @nghe_nghiep, ngay_dang_ky)
SET nghe_nghiep = NULLIF(@nghe_nghiep, '');

LOAD DATA LOCAL INFILE 'D:/BTL_DBM/data/100k/ho_khau.csv'
INTO TABLE ho_khau
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(id, ma_ho, dia_chi, chu_ho_id, ngay_lap);

LOAD DATA LOCAL INFILE 'D:/BTL_DBM/data/100k/thanh_vien_ho.csv'
INTO TABLE thanh_vien_ho
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(id, ho_khau_id, nhan_khau_id, quan_he, tu_ngay, @den_ngay)
SET den_ngay = NULLIF(@den_ngay, '');

LOAD DATA LOCAL INFILE 'D:/BTL_DBM/data/100k/tam_tru_tam_vang.csv'
INTO TABLE tam_tru_tam_vang
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(id, nhan_khau_id, loai, dia_chi_lien_quan, tu_ngay, @den_ngay, @ly_do, trang_thai)
SET den_ngay = NULLIF(@den_ngay, ''),
    ly_do = NULLIF(@ly_do, '');

LOAD DATA LOCAL INFILE 'D:/BTL_DBM/data/100k/bien_dong.csv'
INTO TABLE bien_dong
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(id, nhan_khau_id, loai_bien_dong, ngay_bien_dong, noi_dung, @nguoi_thuc_hien)
SET nguoi_thuc_hien = NULLIF(@nguoi_thuc_hien, '');

SET SESSION unique_checks = 1;
SET SESSION foreign_key_checks = 1;

-- Cập nhật thống kê cho optimizer trước khi đo truy vấn.
ANALYZE TABLE nhan_khau, ho_khau, thanh_vien_ho, tam_tru_tam_vang, bien_dong;

-- Kiểm tra số dòng (100k: 100000 / 25000 / 100000 / 10000 / 20000).
SELECT 'nhan_khau' AS bang, COUNT(*) AS so_dong FROM nhan_khau
UNION ALL SELECT 'ho_khau', COUNT(*) FROM ho_khau
UNION ALL SELECT 'thanh_vien_ho', COUNT(*) FROM thanh_vien_ho
UNION ALL SELECT 'tam_tru_tam_vang', COUNT(*) FROM tam_tru_tam_vang
UNION ALL SELECT 'bien_dong', COUNT(*) FROM bien_dong;

-- Kiểm tra toàn vẹn tham chiếu (vì đã tắt FK khi nạp): kết quả phải là 0.
SELECT COUNT(*) AS thanh_vien_mo_coi
FROM thanh_vien_ho tv LEFT JOIN nhan_khau nk ON nk.id = tv.nhan_khau_id
WHERE nk.id IS NULL;

-- Dung lượng dữ liệu + index (dùng để so sánh với MongoDB).
SELECT table_name,
       table_rows,
       ROUND(data_length / 1024 / 1024, 1)  AS data_mb,
       ROUND(index_length / 1024 / 1024, 1) AS index_mb
FROM information_schema.tables
WHERE table_schema = 'quan_ly_nhan_khau'
ORDER BY table_name;
