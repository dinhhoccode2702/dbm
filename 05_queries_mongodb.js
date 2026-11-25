// =====================================================================
// SO SÁNH HIỆU NĂNG - PHÍA MONGODB  (đi cặp với 03_queries_mysql.sql)
// 8 truy vấn Q1..Q8 giống hệt bên MySQL (cùng điều kiện, cùng kết quả).
//
// CÁCH CHẠY TRONG MONGODB COMPASS
//   Kết nối localhost:27017 -> bấm ">_ Open MongoDB shell" ở thanh dưới cùng.
//   Copy TỪNG câu (hoặc từng cặp dòng) dán vào shell rồi Enter.
//
//   Mỗi truy vấn được viết 2 lần:
//     - Dòng 1: câu truy vấn để XEM KẾT QUẢ.
//     - Dòng 2: cùng câu đó nhưng bọc trong Date.now() để ĐO THỜI GIAN (ms).
//       Chạy dòng đo 3 lần, lấy lần thứ 3 (lần đầu còn phải đọc dữ liệu từ đĩa).
//   Muốn biết truy vấn có dùng index không: thêm .explain("executionStats")
//   (đã viết sẵn ở cuối mỗi phần). COLLSCAN = quét toàn bộ; IXSCAN = dùng index.
// =====================================================================

use quan_ly_nhan_khau

// Cho MongoDB dùng 2 GB bộ nhớ đệm, bằng với MySQL (chạy lại mỗi khi khởi động lại máy).
db.adminCommand({ setParameter: 1, wiredTigerEngineRuntimeConfig: "cache_size=2G" })


// =====================================================================
// PHẦN 1. KHÔNG CÓ INDEX PHỤ
// =====================================================================

// Xóa các index phụ (nếu có) để chỉ còn index cơ bản. Câu nào báo
// "index not found" là index đó chưa có, bỏ qua được.
db.citizens.dropIndex("ix_nk_ho_ten")
db.citizens.dropIndex("ix_nk_que_quan_ho_ten")
db.citizens.dropIndex("ix_nk_que_quan_ngay_sinh")
db.citizens.dropIndex("ix_nk_que_quan_gioi_tinh")
db.citizens.dropIndex("ix_tttv_trang_thai_loai")
db.population_logs.dropIndex("ix_bd_loai_ngay")
db.households.dropIndex("ix_hk_ngay_lap")
db.citizens.dropIndex("ix_ho_ten")      // index do 06_benchmark.py tạo
db.citizens.dropIndex("ix_que_quan")    // index do 06_benchmark.py tạo

// Xem danh sách index còn lại.
db.citizens.getIndexes()


// ---------------------------------------------------------------------
// Q1. Tìm tất cả nhân khẩu có họ tên chính xác là 'Le Van Hung'
//     (kết quả: 502 người). Tương đương: WHERE ho_ten = 'Le Van Hung'.
// ---------------------------------------------------------------------
db.citizens.find({ ho_ten: "Le Van Hung" }, { cccd: 1, ho_ten: 1, ngay_sinh: 1, gioi_tinh: 1, que_quan: 1 })

var t = Date.now(); db.citizens.find({ ho_ten: "Le Van Hung" }, { cccd: 1, ho_ten: 1, ngay_sinh: 1, gioi_tinh: 1, que_quan: 1 }).toArray(); print("Q1:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q2. Tìm người ở Hà Nội có họ tên bắt đầu bằng 'Tran Thi', sắp xếp theo tên,
//     lấy 100 người đầu. Regex /^Tran Thi/ (có dấu ^) tương đương LIKE 'Tran Thi%'.
// ---------------------------------------------------------------------
db.citizens.find({ que_quan: "Ha Noi", ho_ten: /^Tran Thi/ }, { cccd: 1, ho_ten: 1, que_quan: 1 }).sort({ ho_ten: 1 }).limit(100)

var t = Date.now(); db.citizens.find({ que_quan: "Ha Noi", ho_ten: /^Tran Thi/ }, { cccd: 1, ho_ten: 1, que_quan: 1 }).sort({ ho_ten: 1 }).limit(100).toArray(); print("Q2:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q3. Đếm số người quê Cần Thơ sinh trong thập niên 1990
//     (ngày sinh từ 01/01/1990 đến trước 01/01/2000). Kết quả: 9.618.
// ---------------------------------------------------------------------
db.citizens.countDocuments({ que_quan: "Can Tho", ngay_sinh: { $gte: ISODate("1990-01-01"), $lt: ISODate("2000-01-01") } })

var t = Date.now(); db.citizens.countDocuments({ que_quan: "Can Tho", ngay_sinh: { $gte: ISODate("1990-01-01"), $lt: ISODate("2000-01-01") } }); print("Q3:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q4. Thống kê dân số theo từng tỉnh và giới tính (phải đi qua cả 1 triệu người).
//     Tương đương: GROUP BY que_quan, gioi_tinh. Kết quả: 20 dòng.
// ---------------------------------------------------------------------
db.citizens.aggregate([
  { $group: { _id: { que_quan: "$que_quan", gioi_tinh: "$gioi_tinh" }, so_nguoi: { $sum: 1 } } },
  { $sort: { "_id.que_quan": 1, "_id.gioi_tinh": 1 } }
])

var t = Date.now(); db.citizens.aggregate([{ $group: { _id: { que_quan: "$que_quan", gioi_tinh: "$gioi_tinh" }, so_nguoi: { $sum: 1 } } }, { $sort: { "_id.que_quan": 1, "_id.gioi_tinh": 1 } }]).toArray(); print("Q4:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q5. Đếm số hồ sơ TẠM TRÚ đang còn hiệu lực, chia theo quê quán của người tạm trú.
//     Bên MySQL phải JOIN 2 bảng; bên MongoDB hồ sơ tạm trú nằm sẵn trong mảng
//     tam_tru_tam_vang của mỗi người, nên:
//       - $match + $elemMatch: chọn người có ít nhất 1 hồ sơ thỏa CẢ 2 điều kiện
//       - $unwind: tách mảng thành từng hồ sơ
//       - $match lần 2: chỉ giữ đúng các hồ sơ thỏa điều kiện
//       - $group: đếm theo quê quán.   Kết quả: 10 dòng.
// ---------------------------------------------------------------------
db.citizens.aggregate([
  { $match: { tam_tru_tam_vang: { $elemMatch: { trang_thai: "Dang hieu luc", loai: "Tam tru" } } } },
  { $unwind: "$tam_tru_tam_vang" },
  { $match: { "tam_tru_tam_vang.trang_thai": "Dang hieu luc", "tam_tru_tam_vang.loai": "Tam tru" } },
  { $group: { _id: "$que_quan", so_ho_so: { $sum: 1 } } },
  { $sort: { so_ho_so: -1, _id: 1 } }
])

var t = Date.now(); db.citizens.aggregate([{ $match: { tam_tru_tam_vang: { $elemMatch: { trang_thai: "Dang hieu luc", loai: "Tam tru" } } } }, { $unwind: "$tam_tru_tam_vang" }, { $match: { "tam_tru_tam_vang.trang_thai": "Dang hieu luc", "tam_tru_tam_vang.loai": "Tam tru" } }, { $group: { _id: "$que_quan", so_ho_so: { $sum: 1 } } }, { $sort: { so_ho_so: -1, _id: 1 } }]).toArray(); print("Q5:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q6. Đếm số biến động "Chuyển đến" theo từng tháng trong năm 2025.
//     $dateToString đổi ngày thành chuỗi 'YYYY-MM' để nhóm theo tháng. Kết quả: 12 dòng.
// ---------------------------------------------------------------------
db.population_logs.aggregate([
  { $match: { loai_bien_dong: "Chuyen den", ngay_bien_dong: { $gte: ISODate("2025-01-01"), $lt: ISODate("2026-01-01") } } },
  { $group: { _id: { $dateToString: { format: "%Y-%m", date: "$ngay_bien_dong" } }, so_bien_dong: { $sum: 1 } } },
  { $sort: { _id: 1 } }
])

var t = Date.now(); db.population_logs.aggregate([{ $match: { loai_bien_dong: "Chuyen den", ngay_bien_dong: { $gte: ISODate("2025-01-01"), $lt: ISODate("2026-01-01") } } }, { $group: { _id: { $dateToString: { format: "%Y-%m", date: "$ngay_bien_dong" } }, so_bien_dong: { $sum: 1 } } }, { $sort: { _id: 1 } }]).toArray(); print("Q6:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q7. Liệt kê thành viên của các hộ lập trong tháng 3/2000 (mã hộ, địa chỉ,
//     CCCD, họ tên, quan hệ với chủ hộ). Bên MySQL phải JOIN 3 bảng; bên MongoDB
//     danh sách thành viên đã nhúng sẵn trong mỗi hộ (mảng members), chỉ cần
//     $unwind để tách ra từng người. Kết quả: 4.048 dòng.
// ---------------------------------------------------------------------
db.households.aggregate([
  { $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } },
  { $unwind: "$members" },
  { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$members.cccd", ho_ten: "$members.ho_ten", quan_he: "$members.quan_he" } },
  { $sort: { ma_ho: 1, cccd: 1 } }
])

var t = Date.now(); db.households.aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $unwind: "$members" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$members.cccd", ho_ten: "$members.ho_ten", quan_he: "$members.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }]).toArray(); print("Q7:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q7b. (chỉ có ở MongoDB) Cùng kết quả với Q7 nhưng KHÔNG dùng dữ liệu nhúng:
//      $lookup sang collection citizens để "JOIN" giống MySQL.
//      So Q7 với Q7b để thấy lợi ích của việc nhúng dữ liệu.
// ---------------------------------------------------------------------
db.households.aggregate([
  { $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } },
  { $lookup: { from: "citizens", localField: "_id", foreignField: "ho_khau.ho_khau_id", as: "nk" } },
  { $unwind: "$nk" },
  { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$nk.cccd", ho_ten: "$nk.ho_ten", quan_he: "$nk.ho_khau.quan_he" } },
  { $sort: { ma_ho: 1, cccd: 1 } }
])

var t = Date.now(); db.households.aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $lookup: { from: "citizens", localField: "_id", foreignField: "ho_khau.ho_khau_id", as: "nk" } }, { $unwind: "$nk" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$nk.cccd", ho_ten: "$nk.ho_ten", quan_he: "$nk.ho_khau.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }]).toArray(); print("Q7b:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q8. Lấy 100 người cao tuổi nhất quê Nghệ An (lọc theo tỉnh, sắp xếp ngày sinh tăng dần).
// ---------------------------------------------------------------------
db.citizens.find({ que_quan: "Nghe An" }, { cccd: 1, ho_ten: 1, ngay_sinh: 1 }).sort({ ngay_sinh: 1 }).limit(100)

var t = Date.now(); db.citizens.find({ que_quan: "Nghe An" }, { cccd: 1, ho_ten: 1, ngay_sinh: 1 }).sort({ ngay_sinh: 1 }).limit(100).toArray(); print("Q8:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Xem kế hoạch thực thi (có dùng index hay không). Trong kết quả tìm:
//   winningPlan -> stage: COLLSCAN (quét toàn bộ) hoặc IXSCAN + indexName
//   executionStats -> totalDocsExamined (số document phải đọc), executionTimeMillis
// ---------------------------------------------------------------------
db.citizens.find({ ho_ten: "Le Van Hung" }).explain("executionStats")                                                   // Q1
db.citizens.find({ que_quan: "Ha Noi", ho_ten: /^Tran Thi/ }).sort({ ho_ten: 1 }).limit(100).explain("executionStats")  // Q2
db.citizens.find({ que_quan: "Can Tho", ngay_sinh: { $gte: ISODate("1990-01-01"), $lt: ISODate("2000-01-01") } }).explain("executionStats") // Q3
db.citizens.find({ tam_tru_tam_vang: { $elemMatch: { trang_thai: "Dang hieu luc", loai: "Tam tru" } } }).explain("executionStats")         // Q5
db.population_logs.find({ loai_bien_dong: "Chuyen den", ngay_bien_dong: { $gte: ISODate("2025-01-01"), $lt: ISODate("2026-01-01") } }).explain("executionStats") // Q6
db.households.find({ ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } }).explain("executionStats")                   // Q7
db.citizens.find({ que_quan: "Nghe An" }).sort({ ngay_sinh: 1 }).limit(100).explain("executionStats")                  // Q8


// =====================================================================
// PHẦN 2. CÓ INDEX PHỤ
// Tạo index, mỗi index ứng với 1 index cùng tên bên MySQL. Mỗi câu có đo thời
// gian tạo (chụp lại, đây cũng là số liệu so sánh). Sau đó chạy lại Q1..Q8 và
// các câu explain ở PHẦN 1.
// =====================================================================

// Cho Q1: tìm theo họ tên.
var t = Date.now(); db.citizens.createIndex({ ho_ten: 1 }, { name: "ix_nk_ho_ten" }); print("tạo ix_nk_ho_ten:", Date.now() - t, "ms")

// Cho Q2: lọc tỉnh rồi tìm tiền tố tên, kết quả đã sắp theo tên nên không phải sắp xếp lại.
var t = Date.now(); db.citizens.createIndex({ que_quan: 1, ho_ten: 1 }, { name: "ix_nk_que_quan_ho_ten" }); print("tạo ix_nk_que_quan_ho_ten:", Date.now() - t, "ms")

// Cho Q3 và Q8: lọc tỉnh rồi lọc/sắp xếp theo ngày sinh.
var t = Date.now(); db.citizens.createIndex({ que_quan: 1, ngay_sinh: 1 }, { name: "ix_nk_que_quan_ngay_sinh" }); print("tạo ix_nk_que_quan_ngay_sinh:", Date.now() - t, "ms")

// Cho Q4: nhóm theo tỉnh và giới tính. (MongoDB thường KHÔNG dùng index cho $group
// không có $match, nên Q4 có thể gần như không đổi - đây là điểm khác MySQL.)
var t = Date.now(); db.citizens.createIndex({ que_quan: 1, gioi_tinh: 1 }, { name: "ix_nk_que_quan_gioi_tinh" }); print("tạo ix_nk_que_quan_gioi_tinh:", Date.now() - t, "ms")

// Cho Q5: index trên trường nằm trong mảng (multikey index).
var t = Date.now(); db.citizens.createIndex({ "tam_tru_tam_vang.trang_thai": 1, "tam_tru_tam_vang.loai": 1 }, { name: "ix_tttv_trang_thai_loai" }); print("tạo ix_tttv_trang_thai_loai:", Date.now() - t, "ms")

// Cho Q6: lọc loại biến động rồi khoảng ngày.
var t = Date.now(); db.population_logs.createIndex({ loai_bien_dong: 1, ngay_bien_dong: 1 }, { name: "ix_bd_loai_ngay" }); print("tạo ix_bd_loai_ngay:", Date.now() - t, "ms")

// Cho Q7 và Q7b: lọc hộ theo ngày lập.
var t = Date.now(); db.households.createIndex({ ngay_lap: 1 }, { name: "ix_hk_ngay_lap" }); print("tạo ix_hk_ngay_lap:", Date.now() - t, "ms")

// Dung lượng dữ liệu và index (MB) để so với MySQL.
db.citizens.stats({ scale: 1048576 }).indexSizes
db.citizens.stats({ scale: 1048576 }).totalIndexSize

// -> Bây giờ kéo lên chạy lại Q1..Q8 và các câu explain.


// =====================================================================
// PHẦN 3. DỌN DẸP (chạy khi đã đo xong, trước khi chạy 06_benchmark.py)
// =====================================================================
db.citizens.dropIndex("ix_nk_ho_ten")
db.citizens.dropIndex("ix_nk_que_quan_ho_ten")
db.citizens.dropIndex("ix_nk_que_quan_ngay_sinh")
db.citizens.dropIndex("ix_nk_que_quan_gioi_tinh")
db.citizens.dropIndex("ix_tttv_trang_thai_loai")
db.population_logs.dropIndex("ix_bd_loai_ngay")
db.households.dropIndex("ix_hk_ngay_lap")
