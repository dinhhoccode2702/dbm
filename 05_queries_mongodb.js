// =====================================================================
// SO SÁNH MYSQL VÀ MONGODB - PHÍA MONGODB  (đi cặp với 03_queries_mysql.sql)
//
// Gồm 2 nhóm câu lệnh, cùng số hiệu với bên MySQL:
//   Q1..Q5 (+Q5b) : ĐỌC dữ liệu (cùng điều kiện, cùng kết quả với MySQL)
//   W1..W5        : GHI dữ liệu (thêm, sửa, nhập lô, xóa). Chạy đủ W1 -> W5 thì
//                   CSDL trở về đúng như trước khi chạy.
//
// CÁCH CHẠY TRONG MONGODB COMPASS
//   Rê chuột vào tên kết nối ở thanh bên trái -> bấm ">_" (Open MongoDB shell).
//   KHÔNG gõ vào ô lọc của tab Documents (ô đó chỉ nhận điều kiện lọc).
//   Copy TỪNG câu dán vào shell rồi Enter.
//
//   Mỗi truy vấn đọc được viết 2 lần:
//     - Dòng 1: câu truy vấn để XEM KẾT QUẢ.
//     - Dòng 2: cùng câu đó nhưng bọc trong Date.now() để ĐO THỜI GIAN (ms).
//       Chạy dòng đo 2 lần, lấy lần 2 (lần đầu còn phải đọc dữ liệu từ đĩa).
//   Câu ghi chỉ có dòng đo; chạy 1 lượt W1 -> W5 cho mỗi chế độ.
//
//   Các câu ghi dùng writeConcern { j: true }: chờ ghi xong nhật ký (journal)
//   xuống đĩa rồi mới báo thành công, giống MySQL (mỗi COMMIT đều ghi đĩa).
//   Nếu bỏ đi, MongoDB trả lời sớm hơn và phép so sánh không công bằng.
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
db.citizens.dropIndex("ix_nk_que_quan_gioi_tinh")
db.citizens.dropIndex("ix_tttv_trang_thai_loai")
db.households.dropIndex("ix_hk_ngay_lap")
db.population_logs.dropIndex("ix_bd_loai_ngay")
db.citizens.dropIndex("ix_nk_que_quan_ngay_sinh") // index của bản cũ, không còn dùng
db.citizens.dropIndex("ix_ho_ten")                // index do 06_benchmark.py tạo
db.citizens.dropIndex("ix_que_quan")              // index do 06_benchmark.py tạo

// Xem danh sách index còn lại: chỉ còn _id_, uq_cccd, ix_ho_khau_id.
db.citizens.getIndexes()


// ======================== CÁC CÂU ĐỌC (Q1..Q5) ========================

// ---------------------------------------------------------------------
// Q1. Tìm tất cả nhân khẩu có họ tên chính xác là 'Le Van Hung' (502 người).
//     SQL: SELECT ... FROM nhan_khau WHERE ho_ten = 'Le Van Hung'
//     find(điều kiện, các trường cần lấy): 1 = lấy trường đó.
// ---------------------------------------------------------------------
db.citizens.find({ ho_ten: "Le Van Hung" }, { cccd: 1, ho_ten: 1, ngay_sinh: 1, gioi_tinh: 1, que_quan: 1 })

var t = Date.now(); db.citizens.find({ ho_ten: "Le Van Hung" }, { cccd: 1, ho_ten: 1, ngay_sinh: 1, gioi_tinh: 1, que_quan: 1 }).toArray(); print("Q1:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q2. Tìm người ở Hà Nội có họ tên bắt đầu bằng 'Tran Thi', sắp xếp theo tên,
//     lấy 100 người đầu.
//     SQL: WHERE que_quan = 'Ha Noi' AND ho_ten LIKE 'Tran Thi%' ORDER BY ho_ten LIMIT 100
//     Regex /^Tran Thi/ (có dấu ^ = "bắt đầu bằng") tương đương LIKE 'Tran Thi%'.
// ---------------------------------------------------------------------
db.citizens.find({ que_quan: "Ha Noi", ho_ten: /^Tran Thi/ }, { cccd: 1, ho_ten: 1, que_quan: 1 }).sort({ ho_ten: 1 }).limit(100)

var t = Date.now(); db.citizens.find({ que_quan: "Ha Noi", ho_ten: /^Tran Thi/ }, { cccd: 1, ho_ten: 1, que_quan: 1 }).sort({ ho_ten: 1 }).limit(100).toArray(); print("Q2:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q3. Thống kê dân số theo từng tỉnh và giới tính (phải đi qua cả 1 triệu người).
//     SQL: SELECT que_quan, gioi_tinh, COUNT(*) ... GROUP BY que_quan, gioi_tinh
//     $group: _id là khóa nhóm (ở đây gồm 2 trường), $sum: 1 = đếm. Kết quả: 20 dòng.
// ---------------------------------------------------------------------
db.citizens.aggregate([
  { $group: { _id: { que_quan: "$que_quan", gioi_tinh: "$gioi_tinh" }, so_nguoi: { $sum: 1 } } },
  { $sort: { "_id.que_quan": 1, "_id.gioi_tinh": 1 } }
])

var t = Date.now(); db.citizens.aggregate([{ $group: { _id: { que_quan: "$que_quan", gioi_tinh: "$gioi_tinh" }, so_nguoi: { $sum: 1 } } }, { $sort: { "_id.que_quan": 1, "_id.gioi_tinh": 1 } }]).toArray(); print("Q3:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q4. Đếm số hồ sơ TẠM TRÚ đang còn hiệu lực, chia theo quê quán của người tạm trú.
//     MySQL phải JOIN 2 bảng. MongoDB KHÔNG cần JOIN vì hồ sơ tạm trú nằm sẵn
//     trong mảng tam_tru_tam_vang của mỗi công dân:
//       - $match + $elemMatch: chọn người có ít nhất 1 hồ sơ thỏa CẢ 2 điều kiện
//       - $unwind: tách mảng, mỗi hồ sơ thành 1 document riêng
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

var t = Date.now(); db.citizens.aggregate([{ $match: { tam_tru_tam_vang: { $elemMatch: { trang_thai: "Dang hieu luc", loai: "Tam tru" } } } }, { $unwind: "$tam_tru_tam_vang" }, { $match: { "tam_tru_tam_vang.trang_thai": "Dang hieu luc", "tam_tru_tam_vang.loai": "Tam tru" } }, { $group: { _id: "$que_quan", so_ho_so: { $sum: 1 } } }, { $sort: { so_ho_so: -1, _id: 1 } }]).toArray(); print("Q4:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q5. Liệt kê thành viên của các hộ lập trong tháng 3/2000 (mã hộ, địa chỉ,
//     CCCD, họ tên, quan hệ với chủ hộ). MySQL phải JOIN 3 bảng. MongoDB:
//     danh sách thành viên đã nhúng sẵn trong mỗi hộ (mảng members), chỉ cần
//     $unwind để tách ra từng người. Kết quả: 4.048 dòng.
// ---------------------------------------------------------------------
db.households.aggregate([
  { $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } },
  { $unwind: "$members" },
  { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$members.cccd", ho_ten: "$members.ho_ten", quan_he: "$members.quan_he" } },
  { $sort: { ma_ho: 1, cccd: 1 } }
])

var t = Date.now(); db.households.aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $unwind: "$members" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$members.cccd", ho_ten: "$members.ho_ten", quan_he: "$members.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }]).toArray(); print("Q5:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Q5b. (chỉ có ở MongoDB) Cùng kết quả với Q5 nhưng KHÔNG dùng dữ liệu nhúng:
//      $lookup sang collection citizens, tức là "JOIN" giống MySQL.
//      So Q5 với Q5b để thấy lợi ích của việc nhúng, và so Q5b với Q5 của MySQL
//      để thấy JOIN của MongoDB ($lookup) so với JOIN của MySQL.
// ---------------------------------------------------------------------
db.households.aggregate([
  { $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } },
  { $lookup: { from: "citizens", localField: "_id", foreignField: "ho_khau.ho_khau_id", as: "nk" } },
  { $unwind: "$nk" },
  { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$nk.cccd", ho_ten: "$nk.ho_ten", quan_he: "$nk.ho_khau.quan_he" } },
  { $sort: { ma_ho: 1, cccd: 1 } }
])

var t = Date.now(); db.households.aggregate([{ $match: { ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } } }, { $lookup: { from: "citizens", localField: "_id", foreignField: "ho_khau.ho_khau_id", as: "nk" } }, { $unwind: "$nk" }, { $project: { _id: 0, ma_ho: 1, dia_chi: 1, cccd: "$nk.cccd", ho_ten: "$nk.ho_ten", quan_he: "$nk.ho_khau.quan_he" } }, { $sort: { ma_ho: 1, cccd: 1 } }]).toArray(); print("Q5b:", Date.now() - t, "ms")


// ---------------------------------------------------------------------
// Xem kế hoạch thực thi (có dùng index hay không). Trong kết quả tìm:
//   winningPlan -> stage: COLLSCAN (quét toàn bộ) hoặc IXSCAN + indexName
//   executionStats -> totalDocsExamined (số document phải đọc), executionTimeMillis
// ---------------------------------------------------------------------
db.citizens.find({ ho_ten: "Le Van Hung" }).explain("executionStats")                                                   // Q1
db.citizens.find({ que_quan: "Ha Noi", ho_ten: /^Tran Thi/ }).sort({ ho_ten: 1 }).limit(100).explain("executionStats")  // Q2
db.citizens.explain("executionStats").aggregate([{ $group: { _id: { que_quan: "$que_quan", gioi_tinh: "$gioi_tinh" }, so_nguoi: { $sum: 1 } } }])  // Q3
db.citizens.find({ tam_tru_tam_vang: { $elemMatch: { trang_thai: "Dang hieu luc", loai: "Tam tru" } } }).explain("executionStats")         // Q4
db.households.find({ ngay_lap: { $gte: ISODate("2000-03-01"), $lt: ISODate("2000-04-01") } }).explain("executionStats")                   // Q5


// ======================== CÁC CÂU GHI (W1..W5) ========================
// Chạy đúng thứ tự W1 -> W5. Dữ liệu thử có dấu hiệu nhận biết riêng
// (_id 9000001, CCCD "999000000001", nguoi_thuc_hien = "NHAP_LO_THU_NGHIEM")
// nên không lẫn với dữ liệu thật, và W4, W5 xóa sạch chúng.

// ---------------------------------------------------------------------
// W1. Đăng ký 1 nhân khẩu mới (vừa sinh) vào hộ có sẵn (hộ _id = 10).
//     MySQL ghi 3 bảng trong 1 giao dịch. MongoDB ghi 3 collection bằng 3 lệnh:
//       1) insertOne vào citizens: thông tin hộ (ho_khau) nằm luôn trong document,
//          không cần bảng thanh_vien_ho riêng
//       2) updateOne households + $push: thêm người này vào mảng members của hộ
//       3) insertOne vào population_logs: ghi biến động "Sinh"
//     MongoDB đang chạy standalone (không phải replica set) nên KHÔNG có giao dịch
//     bao quanh 3 lệnh: nếu lệnh 2 lỗi thì lệnh 1 vẫn đã ghi. Đây là điểm khác MySQL.
// ---------------------------------------------------------------------
var t = Date.now(); db.citizens.insertOne({ _id: 9000001, cccd: "999000000001", ho_ten: "Nguyen Thu Nghiem", ngay_sinh: ISODate("2025-11-20"), gioi_tinh: "Nam", que_quan: "Khanh Hoa", nghe_nghiep: null, ngay_dang_ky: ISODate("2025-11-26"), ho_khau: { ho_khau_id: 10, quan_he: "Con", tu_ngay: ISODate("2025-11-26") }, tam_tru_tam_vang: [] }, { writeConcern: { w: 1, j: true } }); db.households.updateOne({ _id: 10 }, { $push: { members: { citizenId: 9000001, cccd: "999000000001", ho_ten: "Nguyen Thu Nghiem", quan_he: "Con" } } }, { writeConcern: { w: 1, j: true } }); db.population_logs.insertOne({ nhan_khau_id: 9000001, cccd: "999000000001", loai_bien_dong: "Sinh", ngay_bien_dong: ISODate("2025-11-20"), noi_dung: "Dang ky khai sinh (du lieu thu nghiem)", nguoi_thuc_hien: "Can bo thu nghiem" }, { writeConcern: { w: 1, j: true } }); print("W1:", Date.now() - t, "ms")

// Kiểm tra: xem hồ sơ người vừa thêm. Chỉ cần đọc 1 document, không JOIN.
db.citizens.findOne({ _id: 9000001 })
db.households.findOne({ _id: 10 }, { ma_ho: 1, members: 1 })


// ---------------------------------------------------------------------
// W2. Đổi họ tên cho 502 người tên 'Le Van Hung' thành 'Le Van Hung Moi'.
//     MySQL chỉ cần 1 câu UPDATE. MongoDB phải sửa 2 CHỖ vì họ tên được lưu lặp lại
//     (cái giá của việc nhúng ở Q5):
//       1) distinct: lấy danh sách _id của những người cần đổi tên
//       2) updateMany citizens: đổi tên trong hồ sơ công dân
//       3) updateMany households: đổi tên trong mảng members của các hộ có người đó.
//          "members.$[m]" + arrayFilters = chỉ sửa đúng phần tử m có citizenId
//          nằm trong danh sách, không đụng tới các thành viên khác trong hộ.
// ---------------------------------------------------------------------
var t = Date.now(); var ids = db.citizens.distinct("_id", { ho_ten: "Le Van Hung" }); db.citizens.updateMany({ _id: { $in: ids } }, { $set: { ho_ten: "Le Van Hung Moi" } }, { writeConcern: { w: 1, j: true } }); db.households.updateMany({ "members.citizenId": { $in: ids } }, { $set: { "members.$[m].ho_ten": "Le Van Hung Moi" } }, { arrayFilters: [{ "m.citizenId": { $in: ids } }], writeConcern: { w: 1, j: true } }); print("W2:", Date.now() - t, "ms, số người:", ids.length)

// W2b. Đổi lại tên cũ (để CSDL trở về như ban đầu). Cũng đo thời gian câu này.
var t = Date.now(); var ids = db.citizens.distinct("_id", { ho_ten: "Le Van Hung Moi" }); db.citizens.updateMany({ _id: { $in: ids } }, { $set: { ho_ten: "Le Van Hung" } }, { writeConcern: { w: 1, j: true } }); db.households.updateMany({ "members.citizenId": { $in: ids } }, { $set: { "members.$[m].ho_ten": "Le Van Hung" } }, { arrayFilters: [{ "m.citizenId": { $in: ids } }], writeConcern: { w: 1, j: true } }); print("W2b:", Date.now() - t, "ms, số người:", ids.length)

// Kiểm tra: cả 2 số phải bằng 0 (không còn tên 'Le Van Hung Moi' ở đâu).
db.citizens.countDocuments({ ho_ten: "Le Van Hung Moi" })
db.households.countDocuments({ "members.ho_ten": "Le Van Hung Moi" })


// ---------------------------------------------------------------------
// W3. Nhập lô 100.000 biến động mới (chép 100.000 biến động đầu tiên, đánh dấu
//     nguoi_thuc_hien = "NHAP_LO_THU_NGHIEM"). Tương đương INSERT ... SELECT của MySQL:
//       - $sort + $limit: lấy 100.000 biến động đầu tiên
//       - $unset "_id": bỏ _id cũ để MongoDB tự sinh _id mới (ObjectId)
//       - $set: gắn dấu nhận biết
//       - $merge: ghi kết quả vào lại collection population_logs
//     Mỗi document mới đều phải cập nhật vào MỌI index của collection, nên càng nhiều
//     index thì càng chậm. So W3 ở PHẦN 1 và PHẦN 2 để thấy cái giá của index.
// ---------------------------------------------------------------------
var t = Date.now(); db.population_logs.aggregate([{ $sort: { _id: 1 } }, { $limit: 100000 }, { $unset: "_id" }, { $set: { nguoi_thuc_hien: "NHAP_LO_THU_NGHIEM" } }, { $merge: { into: "population_logs", whenMatched: "fail", whenNotMatched: "insert" } }], { writeConcern: { w: 1, j: true } }); print("W3:", Date.now() - t, "ms")

// Kiểm tra: phải ra 100000.
db.population_logs.countDocuments({ nguoi_thuc_hien: "NHAP_LO_THU_NGHIEM" })


// ---------------------------------------------------------------------
// W4. Xóa lô 100.000 biến động vừa nhập ở W3.
//     SQL: DELETE FROM bien_dong WHERE nguoi_thuc_hien = 'NHAP_LO_THU_NGHIEM'
// ---------------------------------------------------------------------
var t = Date.now(); var r = db.population_logs.deleteMany({ nguoi_thuc_hien: "NHAP_LO_THU_NGHIEM" }, { writeConcern: { w: 1, j: true } }); print("W4:", Date.now() - t, "ms, đã xóa:", r.deletedCount)


// ---------------------------------------------------------------------
// W5. Xóa nhân khẩu đã thêm ở W1 cùng mọi dữ liệu liên quan.
//     MySQL chỉ cần 1 câu DELETE vì khóa ngoại ON DELETE CASCADE tự xóa theo.
//     MongoDB KHÔNG có khóa ngoại, phải tự xóa ở từng nơi:
//       1) deleteOne citizens: xóa hồ sơ công dân
//       2) updateOne households + $pull: rút người này khỏi mảng members của hộ
//       3) deleteMany population_logs: xóa các biến động của người này
//     Quên bước 2 hoặc 3 thì sẽ còn dữ liệu "mồ côi" trỏ tới người không còn tồn tại.
// ---------------------------------------------------------------------
var t = Date.now(); db.citizens.deleteOne({ _id: 9000001 }, { writeConcern: { w: 1, j: true } }); db.households.updateOne({ _id: 10 }, { $pull: { members: { citizenId: 9000001 } } }, { writeConcern: { w: 1, j: true } }); db.population_logs.deleteMany({ nhan_khau_id: 9000001 }, { writeConcern: { w: 1, j: true } }); print("W5:", Date.now() - t, "ms")

// Kiểm tra đã sạch dữ liệu thử: cả 3 số phải bằng 0.
db.citizens.countDocuments({ _id: 9000001 })
db.households.countDocuments({ "members.citizenId": 9000001 })
db.population_logs.countDocuments({ $or: [{ nhan_khau_id: 9000001 }, { nguoi_thuc_hien: "NHAP_LO_THU_NGHIEM" }] })


// =====================================================================
// PHẦN 2. CÓ INDEX PHỤ
// Tạo index, mỗi index ứng với 1 index cùng tên bên MySQL. Mỗi câu có đo thời
// gian tạo (chụp lại, đây cũng là số liệu so sánh). Sau đó chạy lại Q1..Q5b,
// các câu explain và W1..W5 ở PHẦN 1.
// =====================================================================

// Cho Q1 và W2: tìm theo họ tên.
var t = Date.now(); db.citizens.createIndex({ ho_ten: 1 }, { name: "ix_nk_ho_ten" }); print("tạo ix_nk_ho_ten:", Date.now() - t, "ms")

// Cho Q2: lọc tỉnh rồi tìm tiền tố tên, kết quả đã sắp theo tên nên không phải sắp xếp lại.
var t = Date.now(); db.citizens.createIndex({ que_quan: 1, ho_ten: 1 }, { name: "ix_nk_que_quan_ho_ten" }); print("tạo ix_nk_que_quan_ho_ten:", Date.now() - t, "ms")

// Cho Q3: nhóm theo tỉnh và giới tính. (MongoDB thường KHÔNG dùng index cho $group
// không có $match, nên Q3 có thể gần như không đổi - đây là điểm khác MySQL.)
var t = Date.now(); db.citizens.createIndex({ que_quan: 1, gioi_tinh: 1 }, { name: "ix_nk_que_quan_gioi_tinh" }); print("tạo ix_nk_que_quan_gioi_tinh:", Date.now() - t, "ms")

// Cho Q4: index trên trường nằm trong mảng (multikey index).
var t = Date.now(); db.citizens.createIndex({ "tam_tru_tam_vang.trang_thai": 1, "tam_tru_tam_vang.loai": 1 }, { name: "ix_tttv_trang_thai_loai" }); print("tạo ix_tttv_trang_thai_loai:", Date.now() - t, "ms")

// Cho Q5 và Q5b: lọc hộ theo ngày lập.
var t = Date.now(); db.households.createIndex({ ngay_lap: 1 }, { name: "ix_hk_ngay_lap" }); print("tạo ix_hk_ngay_lap:", Date.now() - t, "ms")

// Index tra cứu biến động theo loại và ngày. Không truy vấn đọc nào ở đây dùng nó,
// nhưng nó làm W3 (nhập lô) chậm hơn vì mỗi document mới phải thêm vào index này.
var t = Date.now(); db.population_logs.createIndex({ loai_bien_dong: 1, ngay_bien_dong: 1 }, { name: "ix_bd_loai_ngay" }); print("tạo ix_bd_loai_ngay:", Date.now() - t, "ms")

// Dung lượng dữ liệu và index (MB) để so với MySQL.
db.citizens.stats({ scale: 1048576 }).indexSizes
db.citizens.stats({ scale: 1048576 }).totalIndexSize

// -> Bây giờ kéo lên chạy lại Q1..Q5b (2 lần, lấy lần 2), các câu explain và W1..W5 (1 lượt).


// =====================================================================
// PHẦN 3. DỌN DẸP (chạy khi đã đo xong, trước khi chạy 06_benchmark.py)
// =====================================================================
db.citizens.dropIndex("ix_nk_ho_ten")
db.citizens.dropIndex("ix_nk_que_quan_ho_ten")
db.citizens.dropIndex("ix_nk_que_quan_gioi_tinh")
db.citizens.dropIndex("ix_tttv_trang_thai_loai")
db.households.dropIndex("ix_hk_ngay_lap")
db.population_logs.dropIndex("ix_bd_loai_ngay")
