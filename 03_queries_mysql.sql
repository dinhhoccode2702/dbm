-- =====================================================================
-- SO SÁNH HIỆU NĂNG - PHÍA MYSQL  (đi cặp với 05_queries_mongodb.js)
-- 8 truy vấn tốn thời gian, chạy 2 lần:
--   PHẦN 1: chỉ có index cơ bản (khóa chính, UNIQUE, khóa ngoại)
--   PHẦN 2: tạo thêm index phụ rồi chạy lại đúng 8 truy vấn đó
--   PHẦN 3: xóa index phụ để trả CSDL về trạng thái ban đầu
--
-- CÁCH CHẠY TRONG MYSQL WORKBENCH
--   1. Trên thanh công cụ của tab SQL, chọn "Don't Limit" (mặc định Workbench tự
--      thêm LIMIT 1000, làm sai kết quả Q7).
--   2. Bôi đen từng PHẦN rồi bấm Ctrl+Shift+Enter (chạy vùng chọn).
--   3. Xem panel Output: cột "Duration / Fetch" của mỗi câu là thời gian.
--      Thời gian truy vấn = Duration + Fetch.
--   4. Chạy mỗi phần 2 lần, lấy số của LẦN 2 (lần 1 còn phải đọc dữ liệu từ đĩa
--      vào bộ nhớ). Chụp ảnh panel Output làm minh chứng.
--   5. Các câu EXPLAIN không chạy truy vấn, chỉ cho biết MySQL dùng index nào:
--      type = ALL nghĩa là quét toàn bảng; key = tên index nếu có dùng.
-- =====================================================================
USE quan_ly_nhan_khau;

-- ---------------------------------------------------------------------
-- PHẦN 0. CHUẨN BỊ (chạy 1 lần mỗi khi khởi động lại máy/service)
-- Cho MySQL cùng dung lượng bộ nhớ đệm với MongoDB (2 GB), nếu không
-- MySQL chỉ có 128 MB mặc định và bị thiệt khi so sánh.
-- ---------------------------------------------------------------------
SET GLOBAL innodb_buffer_pool_size = 2147483648;
SELECT @@innodb_buffer_pool_size / 1024 / 1024 AS buffer_pool_mb;



-- =====================================================================
-- PHẦN 1. KHÔNG CÓ INDEX PHỤ
-- =====================================================================
-- Xóa các index phụ để chỉ còn index cơ bản. Chạy TỪNG câu bằng Ctrl+Enter
-- (đặt con trỏ vào câu). Câu nào báo lỗi 1091 "Can't DROP ..." là index đó chưa có, bỏ qua.
-- Muốn bôi đen cả khối rồi chạy một lần: bật menu Query > "Continue on SQL Script Error"
-- trước. Nếu không bật, Workbench gặp lỗi 1091 đầu tiên là dừng, các câu sau không chạy.
-- (MySQL 8.0 không có cú pháp DROP INDEX IF EXISTS.)
DROP INDEX ix_nk_ho_ten ON nhan_khau;
DROP INDEX ix_nk_que_quan_ho_ten ON nhan_khau;
DROP INDEX ix_nk_que_quan_ngay_sinh ON nhan_khau;
DROP INDEX ix_nk_que_quan_gioi_tinh ON nhan_khau;
DROP INDEX ix_tttv_trang_thai_loai ON tam_tru_tam_vang;
DROP INDEX ix_bd_loai_ngay ON bien_dong;
DROP INDEX ix_hk_ngay_lap ON ho_khau;
DROP INDEX ix_nhan_khau_ho_ten ON nhan_khau;    -- index do 06_benchmark.py tạo
DROP INDEX ix_nhan_khau_que_quan ON nhan_khau;  -- index do 06_benchmark.py tạo
SHOW INDEX FROM nhan_khau;

-- Q1. Tìm tất cả nhân khẩu có họ tên chính xác là 'Le Van Hung'. Kết quả: 502 dòng.
SELECT id, cccd, ho_ten, ngay_sinh, gioi_tinh, que_quan
FROM nhan_khau
WHERE ho_ten = 'Le Van Hung';

-- Q2. Tìm người ở Hà Nội có họ tên bắt đầu bằng 'Tran Thi', sắp xếp theo tên, lấy 100 người đầu.
--     LIKE 'abc%' (không có % ở đầu) mới dùng được index.
SELECT id, cccd, ho_ten, que_quan
FROM nhan_khau
WHERE que_quan = 'Ha Noi' AND ho_ten LIKE 'Tran Thi%'
ORDER BY ho_ten
LIMIT 100;

-- Q3. Đếm số người quê Cần Thơ sinh trong thập niên 1990 (01/01/1990 đến trước 01/01/2000). Kết quả: 9618.
SELECT COUNT(*) AS so_nguoi
FROM nhan_khau
WHERE que_quan = 'Can Tho'
  AND ngay_sinh >= '1990-01-01' AND ngay_sinh < '2000-01-01';

-- Q4. Thống kê dân số theo từng tỉnh và giới tính (phải đi qua cả 1 triệu người). Kết quả: 20 dòng.
SELECT que_quan, gioi_tinh, COUNT(*) AS so_nguoi
FROM nhan_khau
GROUP BY que_quan, gioi_tinh
ORDER BY que_quan, gioi_tinh;

-- Q5. Đếm số hồ sơ TẠM TRÚ đang còn hiệu lực, chia theo quê quán của người tạm trú.
--     Phải JOIN bảng tam_tru_tam_vang với nhan_khau để lấy quê quán. Kết quả: 10 dòng.
SELECT nk.que_quan, COUNT(*) AS so_ho_so
FROM tam_tru_tam_vang AS t
JOIN nhan_khau AS nk ON nk.id = t.nhan_khau_id
WHERE t.trang_thai = 'Dang hieu luc' AND t.loai = 'Tam tru'
GROUP BY nk.que_quan
ORDER BY so_ho_so DESC, nk.que_quan;

-- Q6. Đếm số biến động "Chuyển đến" theo từng tháng trong năm 2025.
--     DATE_FORMAT đổi ngày thành 'YYYY-MM' để nhóm theo tháng. Kết quả: 12 dòng.
SELECT DATE_FORMAT(ngay_bien_dong, '%Y-%m') AS thang, COUNT(*) AS so_bien_dong
FROM bien_dong
WHERE loai_bien_dong = 'Chuyen den'
  AND ngay_bien_dong >= '2025-01-01' AND ngay_bien_dong < '2026-01-01'
GROUP BY thang
ORDER BY thang;

-- Q7. Liệt kê thành viên của các hộ lập trong tháng 3/2000 (mã hộ, địa chỉ, CCCD, họ tên,
--     quan hệ với chủ hộ). JOIN 3 bảng ho_khau - thanh_vien_ho - nhan_khau. Kết quả: 4048 dòng.
SELECT hk.ma_ho, hk.dia_chi, nk.cccd, nk.ho_ten, tv.quan_he
FROM ho_khau AS hk
JOIN thanh_vien_ho AS tv ON tv.ho_khau_id = hk.id
JOIN nhan_khau AS nk ON nk.id = tv.nhan_khau_id
WHERE hk.ngay_lap >= '2000-03-01' AND hk.ngay_lap < '2000-04-01'
ORDER BY hk.ma_ho, nk.cccd;

-- Q8. Lấy 100 người cao tuổi nhất quê Nghệ An (lọc theo tỉnh, sắp xếp ngày sinh tăng dần).
SELECT id, cccd, ho_ten, ngay_sinh
FROM nhan_khau
WHERE que_quan = 'Nghe An'
ORDER BY ngay_sinh
LIMIT 100;

-- Kế hoạch thực thi (không chạy truy vấn, chỉ xem có dùng index không).
EXPLAIN SELECT id FROM nhan_khau WHERE ho_ten = 'Le Van Hung';
EXPLAIN SELECT id FROM nhan_khau WHERE que_quan = 'Ha Noi' AND ho_ten LIKE 'Tran Thi%' ORDER BY ho_ten LIMIT 100;
EXPLAIN SELECT COUNT(*) FROM nhan_khau WHERE que_quan = 'Can Tho' AND ngay_sinh >= '1990-01-01' AND ngay_sinh < '2000-01-01';
EXPLAIN SELECT que_quan, gioi_tinh, COUNT(*) FROM nhan_khau GROUP BY que_quan, gioi_tinh;
EXPLAIN SELECT nk.que_quan, COUNT(*) FROM tam_tru_tam_vang t JOIN nhan_khau nk ON nk.id = t.nhan_khau_id
        WHERE t.trang_thai = 'Dang hieu luc' AND t.loai = 'Tam tru' GROUP BY nk.que_quan;
EXPLAIN SELECT COUNT(*) FROM bien_dong WHERE loai_bien_dong = 'Chuyen den' AND ngay_bien_dong >= '2025-01-01' AND ngay_bien_dong < '2026-01-01';
EXPLAIN SELECT hk.ma_ho FROM ho_khau hk JOIN thanh_vien_ho tv ON tv.ho_khau_id = hk.id JOIN nhan_khau nk ON nk.id = tv.nhan_khau_id
        WHERE hk.ngay_lap >= '2000-03-01' AND hk.ngay_lap < '2000-04-01';
EXPLAIN SELECT id FROM nhan_khau WHERE que_quan = 'Nghe An' ORDER BY ngay_sinh LIMIT 100;


-- =====================================================================
-- PHẦN 2. CÓ INDEX PHỤ
-- Tạo index (chụp ảnh luôn thời gian tạo index, đó cũng là một số liệu so sánh),
-- sau đó bôi đen lại từ "Q1" đến hết các câu EXPLAIN của PHẦN 1 và chạy lại.
-- =====================================================================
CREATE INDEX ix_nk_ho_ten             ON nhan_khau (ho_ten);                       -- Q1
CREATE INDEX ix_nk_que_quan_ho_ten    ON nhan_khau (que_quan, ho_ten);             -- Q2
CREATE INDEX ix_nk_que_quan_ngay_sinh ON nhan_khau (que_quan, ngay_sinh);          -- Q3, Q8
CREATE INDEX ix_nk_que_quan_gioi_tinh ON nhan_khau (que_quan, gioi_tinh);          -- Q4
CREATE INDEX ix_tttv_trang_thai_loai  ON tam_tru_tam_vang (trang_thai, loai);      -- Q5
CREATE INDEX ix_bd_loai_ngay          ON bien_dong (loai_bien_dong, ngay_bien_dong); -- Q6
CREATE INDEX ix_hk_ngay_lap           ON ho_khau (ngay_lap);                       -- Q7
ANALYZE TABLE nhan_khau, tam_tru_tam_vang, bien_dong, ho_khau;
SHOW INDEX FROM nhan_khau;

-- Dung lượng index sau khi tạo (để so với MongoDB).
SELECT table_name,
       ROUND(data_length  / 1024 / 1024, 1) AS du_lieu_mb,
       ROUND(index_length / 1024 / 1024, 1) AS index_mb
FROM information_schema.tables
WHERE table_schema = 'quan_ly_nhan_khau'
ORDER BY table_name;

-- -> Bây giờ chạy lại Q1..Q8 và các câu EXPLAIN ở PHẦN 1 (2 lần, lấy lần 2).


-- =====================================================================
-- PHẦN 3. DỌN DẸP (chạy khi đã đo xong, trước khi chạy 06_benchmark.py)
-- =====================================================================
DROP INDEX ix_nk_ho_ten ON nhan_khau;
DROP INDEX ix_nk_que_quan_ho_ten ON nhan_khau;
DROP INDEX ix_nk_que_quan_ngay_sinh ON nhan_khau;
DROP INDEX ix_nk_que_quan_gioi_tinh ON nhan_khau;
DROP INDEX ix_tttv_trang_thai_loai ON tam_tru_tam_vang;
DROP INDEX ix_bd_loai_ngay ON bien_dong;
DROP INDEX ix_hk_ngay_lap ON ho_khau;
