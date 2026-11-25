-- Lược đồ MySQL cho quản lý nhân khẩu.
-- Chạy bằng MySQL 8.0.18 trở lên để sử dụng EXPLAIN ANALYZE ở tệp truy vấn.
CREATE DATABASE IF NOT EXISTS quan_ly_nhan_khau
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE quan_ly_nhan_khau;

SET NAMES utf8mb4;

-- CCCD là chuỗi để giữ số 0 đầu; các ID nội bộ dùng INT AUTO_INCREMENT.
CREATE TABLE IF NOT EXISTS nhan_khau (
  id INT NOT NULL AUTO_INCREMENT,
  cccd CHAR(12) NOT NULL,
  ho_ten VARCHAR(150) NOT NULL,
  ngay_sinh DATE NOT NULL,
  gioi_tinh ENUM('Nam','Nu','Khac') NOT NULL,
  que_quan VARCHAR(200) NOT NULL,
  nghe_nghiep VARCHAR(120) NULL,
  ngay_dang_ky DATE NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_nhan_khau_cccd (cccd)
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC;

CREATE TABLE IF NOT EXISTS ho_khau (
  id INT NOT NULL AUTO_INCREMENT,
  ma_ho CHAR(12) NOT NULL,
  dia_chi VARCHAR(255) NOT NULL,
  chu_ho_id INT NOT NULL,
  ngay_lap DATE NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_ho_khau_ma_ho (ma_ho),
  KEY ix_ho_khau_chu_ho (chu_ho_id),
  CONSTRAINT fk_ho_khau_chu_ho FOREIGN KEY (chu_ho_id)
    REFERENCES nhan_khau (id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC;

CREATE TABLE IF NOT EXISTS thanh_vien_ho (
  id INT NOT NULL AUTO_INCREMENT,
  ho_khau_id INT NOT NULL,
  nhan_khau_id INT NOT NULL,
  quan_he ENUM('Chu ho','Vo chong','Con','Cha me','Anh chi em','Khac') NOT NULL,
  tu_ngay DATE NOT NULL,
  den_ngay DATE NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_thanh_vien_ho (ho_khau_id, nhan_khau_id),
  KEY ix_thanh_vien_nhan_khau (nhan_khau_id),
  CONSTRAINT fk_thanh_vien_ho FOREIGN KEY (ho_khau_id)
    REFERENCES ho_khau (id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_thanh_vien_nhan_khau FOREIGN KEY (nhan_khau_id)
    REFERENCES nhan_khau (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC;

CREATE TABLE IF NOT EXISTS tam_tru_tam_vang (
  id INT NOT NULL AUTO_INCREMENT,
  nhan_khau_id INT NOT NULL,
  loai ENUM('Tam tru','Tam vang') NOT NULL,
  dia_chi_lien_quan VARCHAR(255) NOT NULL,
  tu_ngay DATE NOT NULL,
  den_ngay DATE NULL,
  ly_do VARCHAR(500) NULL,
  trang_thai ENUM('Dang hieu luc','Da ket thuc','Da huy') NOT NULL DEFAULT 'Dang hieu luc',
  PRIMARY KEY (id),
  KEY ix_tttv_nhan_khau_thoi_gian (nhan_khau_id, tu_ngay),
  CONSTRAINT fk_tttv_nhan_khau FOREIGN KEY (nhan_khau_id)
    REFERENCES nhan_khau (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC;

CREATE TABLE IF NOT EXISTS bien_dong (
  id INT NOT NULL AUTO_INCREMENT,
  nhan_khau_id INT NOT NULL,
  loai_bien_dong ENUM('Sinh','Tu','Chuyen den','Chuyen di','Doi thong tin') NOT NULL,
  ngay_bien_dong DATE NOT NULL,
  noi_dung VARCHAR(1000) NOT NULL,
  nguoi_thuc_hien VARCHAR(150) NULL,
  PRIMARY KEY (id),
  KEY ix_bien_dong_nhan_khau_ngay (nhan_khau_id, ngay_bien_dong),
  CONSTRAINT fk_bien_dong_nhan_khau FOREIGN KEY (nhan_khau_id)
    REFERENCES nhan_khau (id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC;
