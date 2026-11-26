-- =====================================================================
-- SO SÁNH MYSQL VÀ MONGODB - PHÍA MYSQL  (đi cặp với 05_queries_mongodb.js)
--
-- Gồm 2 nhóm câu lệnh, mỗi câu đều có câu tương ứng bên MongoDB cùng số hiệu:
--   Q1..Q5 : ĐỌC dữ liệu (tìm kiếm, thống kê, JOIN)
--   W1..W5 : GHI dữ liệu (thêm, sửa, nhập lô, xóa). Chạy đủ W1 -> W5 thì
--            CSDL trở về đúng như trước khi chạy (dữ liệu thử bị xóa hết).
--
-- Chạy 2 chế độ:
--   PHẦN 1: chỉ có index cơ bản (khóa chính, UNIQUE, khóa ngoại)
--   PHẦN 2: tạo thêm index phụ rồi chạy lại Q1..Q5 và W1..W5
--   PHẦN 3: xóa index phụ để trả CSDL về trạng thái ban đầu
--
-- CÁCH CHẠY TRONG MYSQL WORKBENCH
--   1. Trên thanh công cụ của tab SQL, chọn "Don't Limit" (mặc định Workbench tự
--      thêm LIMIT 1000, làm sai kết quả Q5).
--   2. Đặt con trỏ vào câu rồi bấm Ctrl+Enter (chạy 1 câu), hoặc bôi đen một
--      khối rồi bấm Ctrl+Shift+Enter (chạy cả khối).
--   3. Xem panel Output: cột "Duration / Fetch" của mỗi câu là thời gian.
--      Thời gian = Duration + Fetch. Với W1 và W5 gồm nhiều câu thì cộng lại.
--   4. Câu ĐỌC: chạy 2 lần, lấy số của LẦN 2 (lần 1 còn phải đọc dữ liệu từ đĩa).
--      Câu GHI: chỉ chạy 1 lượt W1 -> W5 cho mỗi chế độ (chạy lại W1 hai lần sẽ
--      báo trùng khóa).
--   5. Câu EXPLAIN không chạy truy vấn, chỉ cho biết MySQL dùng index nào:
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

-- Tắt "safe update mode" của Workbench cho phiên này. Nếu không, W2 và W4 ở chế độ
-- không index báo lỗi 1175 (UPDATE/DELETE có WHERE không dùng cột index bị chặn).
SET SQL_SAFE_UPDATES = 0;



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
DROP INDEX ix_nk_que_quan_gioi_tinh ON nhan_khau;
DROP INDEX ix_tttv_trang_thai_loai ON tam_tru_tam_vang;
DROP INDEX ix_bd_loai_ngay ON bien_dong;
DROP INDEX ix_hk_ngay_lap ON ho_khau;
DROP INDEX ix_nk_que_quan_ngay_sinh ON nhan_khau; -- index của bản cũ, không còn dùng
DROP INDEX ix_nhan_khau_ho_ten ON nhan_khau;      -- index do 06_benchmark.py tạo
DROP INDEX ix_nhan_khau_que_quan ON nhan_khau;    -- index do 06_benchmark.py tạo
SHOW INDEX FROM nhan_khau;


-- ===================== CÁC CÂU ĐỌC (Q1..Q5) ==========================

-- Q1. Tìm tất cả nhân khẩu có họ tên chính xác là 'Le Van Hung'. Kết quả: 502 dòng.
--     Ý nghĩa: tìm kiếm đơn giản nhất. Không có index thì phải đọc cả 1 triệu dòng.
SELECT id, cccd, ho_ten, ngay_sinh, gioi_tinh, que_quan
FROM nhan_khau
WHERE ho_ten = 'Le Van Hung';

-- Q2. Tìm người ở Hà Nội có họ tên bắt đầu bằng 'Tran Thi', sắp xếp theo tên, lấy 100 người đầu.
--     Ý nghĩa: lọc 2 điều kiện + sắp xếp + giới hạn. LIKE 'abc%' (không có % ở đầu)
--     mới dùng được index. Kết quả: 100 dòng.
SELECT id, cccd, ho_ten, que_quan
FROM nhan_khau
WHERE que_quan = 'Ha Noi' AND ho_ten LIKE 'Tran Thi%'
ORDER BY ho_ten
LIMIT 100;

-- Q3. Thống kê dân số theo từng tỉnh và giới tính (phải đi qua cả 1 triệu người).
--     Ý nghĩa: GROUP BY trên toàn bộ bảng. Kết quả: 20 dòng.
SELECT que_quan, gioi_tinh, COUNT(*) AS so_nguoi
FROM nhan_khau
GROUP BY que_quan, gioi_tinh
ORDER BY que_quan, gioi_tinh;

-- Q4. Đếm số hồ sơ TẠM TRÚ đang còn hiệu lực, chia theo quê quán của người tạm trú.
--     Ý nghĩa: hồ sơ tạm trú nằm ở bảng riêng nên phải JOIN với nhan_khau để lấy
--     quê quán. (MongoDB: hồ sơ tạm trú nằm sẵn trong document công dân.) Kết quả: 10 dòng.
SELECT nk.que_quan, COUNT(*) AS so_ho_so
FROM tam_tru_tam_vang AS t
JOIN nhan_khau AS nk ON nk.id = t.nhan_khau_id
WHERE t.trang_thai = 'Dang hieu luc' AND t.loai = 'Tam tru'
GROUP BY nk.que_quan
ORDER BY so_ho_so DESC, nk.que_quan;

-- Q5. Liệt kê thành viên của các hộ lập trong tháng 3/2000 (mã hộ, địa chỉ, CCCD, họ tên,
--     quan hệ với chủ hộ). Ý nghĩa: JOIN 3 bảng ho_khau - thanh_vien_ho - nhan_khau.
--     (MongoDB: danh sách thành viên nằm sẵn trong document hộ.) Kết quả: 4048 dòng.
SELECT hk.ma_ho, hk.dia_chi, nk.cccd, nk.ho_ten, tv.quan_he
FROM ho_khau AS hk
JOIN thanh_vien_ho AS tv ON tv.ho_khau_id = hk.id
JOIN nhan_khau AS nk ON nk.id = tv.nhan_khau_id
WHERE hk.ngay_lap >= '2000-03-01' AND hk.ngay_lap < '2000-04-01'
ORDER BY hk.ma_ho, nk.cccd;

-- Kế hoạch thực thi (không chạy truy vấn, chỉ xem có dùng index không).
EXPLAIN SELECT id FROM nhan_khau WHERE ho_ten = 'Le Van Hung';
EXPLAIN SELECT id FROM nhan_khau WHERE que_quan = 'Ha Noi' AND ho_ten LIKE 'Tran Thi%' ORDER BY ho_ten LIMIT 100;
EXPLAIN SELECT que_quan, gioi_tinh, COUNT(*) FROM nhan_khau GROUP BY que_quan, gioi_tinh;
EXPLAIN SELECT nk.que_quan, COUNT(*) FROM tam_tru_tam_vang t JOIN nhan_khau nk ON nk.id = t.nhan_khau_id
        WHERE t.trang_thai = 'Dang hieu luc' AND t.loai = 'Tam tru' GROUP BY nk.que_quan;
EXPLAIN SELECT hk.ma_ho FROM ho_khau hk JOIN thanh_vien_ho tv ON tv.ho_khau_id = hk.id JOIN nhan_khau nk ON nk.id = tv.nhan_khau_id
        WHERE hk.ngay_lap >= '2000-03-01' AND hk.ngay_lap < '2000-04-01';


-- ===================== CÁC CÂU GHI (W1..W5) ==========================
-- Chạy đúng thứ tự W1 -> W5. Dữ liệu thử có dấu hiệu nhận biết riêng
-- (id 9000001, CCCD '999000000001', nguoi_thuc_hien = 'NHAP_LO_THU_NGHIEM')
-- nên không lẫn với dữ liệu thật, và W4, W5 xóa sạch chúng.

-- W1. Đăng ký 1 nhân khẩu mới (vừa sinh) vào hộ có sẵn (hộ id = 10).
--     MySQL phải ghi vào 3 BẢNG: nhan_khau, thanh_vien_ho, bien_dong. Bọc trong
--     giao dịch (START TRANSACTION ... COMMIT) để hoặc ghi đủ cả 3, hoặc không ghi gì.
--     Thời gian = cộng Duration của 3 câu INSERT và câu COMMIT.
START TRANSACTION;
INSERT INTO nhan_khau (id, cccd, ho_ten, ngay_sinh, gioi_tinh, que_quan, nghe_nghiep, ngay_dang_ky)
VALUES (9000001, '999000000001', 'Nguyen Thu Nghiem', '2025-11-20', 'Nam', 'Khanh Hoa', NULL, '2025-11-26');
INSERT INTO thanh_vien_ho (ho_khau_id, nhan_khau_id, quan_he, tu_ngay)
VALUES (10, 9000001, 'Con', '2025-11-26');
INSERT INTO bien_dong (nhan_khau_id, loai_bien_dong, ngay_bien_dong, noi_dung, nguoi_thuc_hien)
VALUES (9000001, 'Sinh', '2025-11-20', 'Dang ky khai sinh (du lieu thu nghiem)', 'Can bo thu nghiem');
COMMIT;

-- Kiểm tra: xem hồ sơ người vừa thêm. Phải JOIN 3 bảng mới ra đủ thông tin.
SELECT nk.id, nk.cccd, nk.ho_ten, tv.ho_khau_id, tv.quan_he, bd.loai_bien_dong, bd.ngay_bien_dong
FROM nhan_khau nk
JOIN thanh_vien_ho tv ON tv.nhan_khau_id = nk.id
JOIN bien_dong bd ON bd.nhan_khau_id = nk.id
WHERE nk.id = 9000001;

-- W2. Đổi họ tên cho 502 người tên 'Le Van Hung' thành 'Le Van Hung Moi'.
--     MySQL: họ tên chỉ lưu ở MỘT chỗ (bảng nhan_khau) nên chỉ cần 1 câu UPDATE.
--     (MongoDB: họ tên lưu ở 2 chỗ, citizens và households.members, phải sửa cả hai.)
--     Kết quả: "502 row(s) affected".
UPDATE nhan_khau SET ho_ten = 'Le Van Hung Moi' WHERE ho_ten = 'Le Van Hung';

-- W2b. Đổi lại tên cũ (để CSDL trở về như ban đầu). Cũng đo thời gian câu này.
UPDATE nhan_khau SET ho_ten = 'Le Van Hung' WHERE ho_ten = 'Le Van Hung Moi';

-- W3. Nhập lô 100.000 biến động mới (chép 100.000 biến động đầu tiên, đánh dấu
--     nguoi_thuc_hien = 'NHAP_LO_THU_NGHIEM'). Ý nghĩa: ghi số lượng lớn; mỗi dòng
--     mới đều phải cập nhật vào MỌI index của bảng bien_dong, nên càng nhiều index
--     thì càng chậm. So W3 ở PHẦN 1 và PHẦN 2 để thấy cái giá của index.
--     Kết quả: "100000 row(s) affected".
INSERT INTO bien_dong (nhan_khau_id, loai_bien_dong, ngay_bien_dong, noi_dung, nguoi_thuc_hien)
SELECT nhan_khau_id, loai_bien_dong, ngay_bien_dong, noi_dung, 'NHAP_LO_THU_NGHIEM'
FROM bien_dong
ORDER BY id
LIMIT 100000;

-- W4. Xóa lô 100.000 biến động vừa nhập ở W3. Kết quả: "100000 row(s) affected".
DELETE FROM bien_dong WHERE nguoi_thuc_hien = 'NHAP_LO_THU_NGHIEM';

-- W5. Xóa nhân khẩu đã thêm ở W1 cùng mọi dữ liệu liên quan.
--     MySQL chỉ cần 1 câu: khóa ngoại khai báo ON DELETE CASCADE nên các dòng của
--     người này trong thanh_vien_ho và bien_dong tự động bị xóa theo.
--     (MongoDB không có khóa ngoại, phải tự xóa ở từng collection.)
DELETE FROM nhan_khau WHERE id = 9000001;

-- Kiểm tra đã sạch dữ liệu thử: cả 3 số phải bằng 0.
SELECT (SELECT COUNT(*) FROM nhan_khau WHERE id = 9000001)                         AS nk_con_lai,
       (SELECT COUNT(*) FROM thanh_vien_ho WHERE nhan_khau_id = 9000001)           AS tv_con_lai,
       (SELECT COUNT(*) FROM bien_dong WHERE nguoi_thuc_hien = 'NHAP_LO_THU_NGHIEM'
                                          OR nhan_khau_id = 9000001)               AS bd_con_lai;


-- =====================================================================
-- PHẦN 2. CÓ INDEX PHỤ
-- Tạo index (chụp ảnh luôn thời gian tạo index, đó cũng là một số liệu so sánh),
-- sau đó chạy lại Q1..Q5, các câu EXPLAIN và W1..W5 của PHẦN 1.
-- =====================================================================
CREATE INDEX ix_nk_ho_ten             ON nhan_khau (ho_ten);                         -- Q1, W2
CREATE INDEX ix_nk_que_quan_ho_ten    ON nhan_khau (que_quan, ho_ten);               -- Q2
CREATE INDEX ix_nk_que_quan_gioi_tinh ON nhan_khau (que_quan, gioi_tinh);            -- Q3
CREATE INDEX ix_tttv_trang_thai_loai  ON tam_tru_tam_vang (trang_thai, loai);        -- Q4
CREATE INDEX ix_hk_ngay_lap           ON ho_khau (ngay_lap);                         -- Q5
CREATE INDEX ix_bd_loai_ngay          ON bien_dong (loai_bien_dong, ngay_bien_dong); -- tra cứu biến động; làm W3 chậm hơn
ANALYZE TABLE nhan_khau, tam_tru_tam_vang, bien_dong, ho_khau;
SHOW INDEX FROM nhan_khau;

-- Dung lượng index sau khi tạo (để so với MongoDB).
SELECT table_name,
       ROUND(data_length  / 1024 / 1024, 1) AS du_lieu_mb,
       ROUND(index_length / 1024 / 1024, 1) AS index_mb
FROM information_schema.tables
WHERE table_schema = 'quan_ly_nhan_khau'
ORDER BY table_name;

-- -> Bây giờ chạy lại Q1..Q5 (2 lần, lấy lần 2), các câu EXPLAIN và W1..W5 (1 lượt) ở PHẦN 1.


-- =====================================================================
-- PHẦN 3. DỌN DẸP (chạy khi đã đo xong, trước khi chạy 06_benchmark.py)
-- =====================================================================
DROP INDEX ix_nk_ho_ten ON nhan_khau;
DROP INDEX ix_nk_que_quan_ho_ten ON nhan_khau;
DROP INDEX ix_nk_que_quan_gioi_tinh ON nhan_khau;
DROP INDEX ix_tttv_trang_thai_loai ON tam_tru_tam_vang;
DROP INDEX ix_hk_ngay_lap ON ho_khau;
DROP INDEX ix_bd_loai_ngay ON bien_dong;
