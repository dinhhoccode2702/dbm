# Nghiệp vụ quản lý nhân khẩu

Tài liệu này mô tả bài toán nghiệp vụ mà cơ sở dữ liệu (CSDL) của đề tài phục vụ: các khái niệm, quy tắc nghiệp vụ và căn cứ pháp lý của từng quy tắc, các chức năng của hệ thống, và những giả định đơn giản hóa so với thực tế.

**Phạm vi:** hệ thống quản lý nhân khẩu ở cấp cơ sở (xã, phường), dùng để lưu hồ sơ công dân, hộ gia đình, tạm trú, tạm vắng và lịch sử biến động. Đây là mô hình rút gọn để phục vụ việc so sánh hiệu năng MySQL và MongoDB, không phải bản sao của Cơ sở dữ liệu quốc gia về dân cư.

---

## 1. Căn cứ pháp lý

| # | Văn bản | Nội dung dùng trong đề tài |
|---|---|---|
| [1] | **Luật Cư trú số 68/2020/QH14**, ngày 13/11/2020, hiệu lực từ 01/07/2021 (văn bản hợp nhất 01/VBHN-VPQH năm 2025) | Khái niệm cư trú, thường trú, tạm trú, tạm vắng; nguyên tắc mỗi công dân có một nơi thường trú; nghĩa vụ đăng ký tạm trú và khai báo tạm vắng; quyền và nghĩa vụ của chủ hộ; bãi bỏ sổ hộ khẩu giấy |
| [2] | **Thông tư 55/2021/TT-BCA**, ngày 15/05/2021, quy định chi tiết một số điều và biện pháp thi hành Luật Cư trú (sửa đổi bởi Thông tư 66/2023/TT-BCA và Thông tư 53/2025/TT-BCA) | Thủ tục khai báo tạm vắng (Điều 16), thông báo lưu trú |
| [3] | **Luật Căn cước số 26/2023/QH15**, ngày 27/11/2023, hiệu lực từ 01/07/2024 (thay thế Luật Căn cước công dân 2014) | Số định danh cá nhân (Điều 12); thông tin của công dân trong Cơ sở dữ liệu quốc gia về dân cư |
| [4] | **Nghị định 137/2015/NĐ-CP** (Điều 13) | Cấu trúc 12 chữ số của số định danh cá nhân |
| [5] | **Luật Hộ tịch số 60/2014/QH13**, hiệu lực từ 01/01/2016 | Đăng ký khai sinh trong 60 ngày kể từ ngày sinh; đăng ký khai tử |
| [6] | **Nghị quyết 202/2025/QH15**, ngày 12/06/2025, về sắp xếp đơn vị hành chính cấp tỉnh | Từ 01/07/2025 cả nước còn 34 đơn vị cấp tỉnh; Bình Dương và Bà Rịa - Vũng Tàu nhập vào TP. Hồ Chí Minh |

> **Cần đối chiếu trước khi nộp:** số điều và khoản trong bảng trên được tổng hợp từ các trang tra cứu pháp luật (thuvienphapluat.vn, luatvietnam.vn, cổng phổ biến pháp luật của các tỉnh). Khi trích dẫn nguyên văn trong báo cáo, hãy đối chiếu với văn bản hợp nhất mới nhất trên vbpl.vn hoặc thuvienphapluat.vn, vì Luật Cư trú và Thông tư 55/2021 đã được sửa đổi nhiều lần.

---

## 2. Khái niệm

| Khái niệm | Ý nghĩa (theo [1], diễn đạt lại) | Thể hiện trong CSDL |
|---|---|---|
| **Cư trú** | Việc công dân sinh sống tại một địa điểm thuộc đơn vị hành chính cấp xã | Toàn bộ hệ thống |
| **Nơi thường trú** | Nơi công dân sinh sống ổn định, lâu dài và đã được đăng ký thường trú | Hộ mà nhân khẩu đang là thành viên (`thanh_vien_ho` có `den_ngay` rỗng) |
| **Nơi tạm trú** | Nơi công dân sinh sống trong một thời gian nhất định ngoài nơi thường trú và đã đăng ký tạm trú | `tam_tru_tam_vang` với `loai = 'Tam tru'` |
| **Tạm vắng** | Công dân vắng mặt ở nơi cư trú trong một khoảng thời gian, thuộc các trường hợp phải khai báo | `tam_tru_tam_vang` với `loai = 'Tam vang'` |
| **Đăng ký cư trú** | Gồm đăng ký thường trú, đăng ký tạm trú, khai báo tạm vắng, thông báo lưu trú, khai báo và điều chỉnh thông tin cư trú | Các thao tác ghi của hệ thống |
| **Hộ gia đình, chủ hộ** | Những người cùng đăng ký cư trú tại một chỗ ở; chủ hộ đại diện cho hộ khi thực hiện thủ tục cư trú | `ho_khau` (có `chu_ho_id`), quan hệ với chủ hộ lưu ở `thanh_vien_ho.quan_he` |
| **Số định danh cá nhân** | Dãy 12 chữ số, mỗi công dân một số duy nhất, không lặp lại; cũng là số trên thẻ căn cước | `nhan_khau.cccd`, ràng buộc UNIQUE |
| **Biến động nhân khẩu** | Các sự kiện làm thay đổi tình trạng dân cư: sinh, tử, chuyển đến, chuyển đi, thay đổi thông tin | `bien_dong` |

**Về tên gọi "hộ khẩu":** theo khoản 3 Điều 38 của [1], sổ hộ khẩu và sổ tạm trú bằng giấy chỉ còn giá trị đến hết ngày 31/12/2022. Từ 01/01/2023, thông tin cư trú được quản lý bằng dữ liệu điện tử. Trong đề tài, bảng `ho_khau` và mã `ma_ho` hiểu là **hộ gia đình đã đăng ký thường trú** trong CSDL, không phải cuốn sổ giấy. Tên `ho_khau` được giữ vì đây là thuật ngữ quen thuộc của bài toán.

---

## 3. Quy tắc nghiệp vụ

Mỗi quy tắc ghi rõ nguồn gốc và cách CSDL bảo đảm quy tắc đó. Cột "Mức bảo đảm" phân biệt rõ: ràng buộc do hệ quản trị CSDL tự kiểm tra, hay chỉ do dữ liệu sinh ra hoặc ứng dụng tuân thủ.

| Mã | Quy tắc | Nguồn | Mức bảo đảm trong CSDL |
|---|---|---|---|
| NV01 | Mỗi công dân có một số định danh 12 chữ số, duy nhất | [3] Điều 12 | **Hệ quản trị**: `UNIQUE(cccd)` (MySQL), unique index `uq_cccd` (MongoDB) |
| NV02 | Số định danh gồm: 3 số mã tỉnh nơi đăng ký khai sinh, 1 số mã thế kỷ và giới tính (thế kỷ 20: nam 0, nữ 1; thế kỷ 21: nam 2, nữ 3), 2 số cuối năm sinh, 6 số ngẫu nhiên | [4] Điều 13 | Dữ liệu sinh ra tuân thủ, đã kiểm tra trên toàn bộ dữ liệu. CSDL không kiểm tra (có thể bổ sung CHECK hoặc `$jsonSchema`) |
| NV03 | Tại một thời điểm, mỗi công dân chỉ có một nơi thường trú, nghĩa là thuộc đúng một hộ đang hiệu lực | [1], nguyên tắc cư trú | Dữ liệu sinh ra tuân thủ. MySQL hiện chỉ có `UNIQUE(ho_khau_id, nhan_khau_id)`, chưa chặn được việc một người thuộc 2 hộ cùng lúc (xem mục 6) |
| NV04 | Mỗi hộ có đúng một chủ hộ; các thành viên khác ghi quan hệ với chủ hộ | [1], quy định về chủ hộ | **Hệ quản trị**: `ho_khau.chu_ho_id` NOT NULL, có FK tới `nhan_khau`, `ON DELETE RESTRICT` (không xóa được người đang là chủ hộ). `quan_he` là ENUM |
| NV05 | Công dân đến sống ngoài phạm vi cấp xã nơi thường trú **từ 30 ngày trở lên** thì phải đăng ký tạm trú | [1] Điều 27 | Bản ghi `Tam tru` có `tu_ngay`, `den_ngay` và trạng thái `Dang hieu luc` / `Da ket thuc` / `Da huy` |
| NV06 | Công dân thuộc các trường hợp luật định phải khai báo tạm vắng khi đi khỏi nơi cư trú | [1] Điều 31; [2] Điều 16 | Bản ghi `Tam vang`, cùng bảng với tạm trú |
| NV07 | Trẻ em được đăng ký khai sinh trong 60 ngày kể từ ngày sinh; khi đó phát sinh biến động "Sinh" | [5] | Dữ liệu: biến động `Sinh` có `ngay_bien_dong` trùng ngày sinh |
| NV08 | Chuyển đến, chuyển đi, thay đổi thông tin nhân thân đều được ghi lại thành lịch sử, không ghi đè | [1], đăng ký và điều chỉnh thông tin cư trú | Bảng hoặc collection biến động chỉ thêm mới (append-only); có index `(nhan_khau_id, ngay_bien_dong)` để tra lịch sử |
| NV09 | Mọi sự kiện của một người (đăng ký, vào hộ, tạm trú, biến động) không thể xảy ra trước ngày sinh | Ràng buộc logic, không phải quy định pháp luật | Dữ liệu sinh ra tuân thủ, đã kiểm tra |
| NV10 | Quan hệ trong hộ phải hợp lý về tuổi và giới tính: chủ hộ đủ 18 tuổi khi lập hộ; vợ/chồng khác giới, chênh nhau không quá 5 tuổi; con nhỏ hơn chủ hộ 18–45 tuổi; cha/mẹ lớn hơn chủ hộ 20–40 tuổi | Giả định để dữ liệu thực tế hơn | Dữ liệu sinh ra tuân thủ, đã kiểm tra |

---

## 4. Chức năng của hệ thống

Các chức năng dưới đây là thao tác hằng ngày của cán bộ quản lý nhân khẩu. Mỗi chức năng tương ứng một thao tác được đo trong benchmark (`06_benchmark.py`).

| Chức năng nghiệp vụ | Người dùng | Mã benchmark |
|---|---|---|
| Tra cứu nhân khẩu theo số CCCD | Cán bộ tiếp dân | R1 |
| Tìm kiếm nhân khẩu theo họ tên và quê quán | Cán bộ | R2 |
| Xem hồ sơ đầy đủ một nhân khẩu: thông tin cá nhân, hộ, lịch sử tạm trú/tạm vắng | Cán bộ | R3 |
| Xem danh sách thành viên một hộ | Cán bộ, tổ dân phố | R4 |
| Xem lịch sử biến động của một nhân khẩu | Cán bộ | R5 |
| Thống kê dân số theo giới tính và quê quán | Lãnh đạo, báo cáo định kỳ | A1 |
| Thống kê số người đang tạm trú theo quê quán | Lãnh đạo | A2 |
| In danh sách thành viên của nhiều hộ (một khu phố) | Tổ dân phố | J1, J2 |
| Đăng ký nhân khẩu mới vào hộ (ví dụ trẻ mới sinh) | Cán bộ | W1 |
| Điều chỉnh thông tin nhân thân (ví dụ đổi họ tên) | Cán bộ | W2 |
| Ghi nhận một biến động | Cán bộ | W3 |
| Nhập dữ liệu biến động theo lô (đồng bộ từ hệ thống khác) | Quản trị hệ thống | W4 |
| Xóa nhân khẩu (dùng để đo chi phí xóa) | Quản trị hệ thống | W5 |

**Lưu ý về W5:** trong thực tế, cơ quan quản lý không xóa vật lý hồ sơ công dân. Khi người dân chuyển đi hoặc qua đời, cơ quan **xóa đăng ký thường trú**, tức là đóng bản ghi bằng cách điền `den_ngay` và ghi biến động. W5 được giữ lại chỉ để so sánh chi phí xóa có lan truyền (cascade) giữa hai hệ quản trị.

---

## 5. Giả định và đơn giản hóa

Các điểm dưới đây khác với thực tế. Đề tài chấp nhận chúng vì không ảnh hưởng đến mục tiêu so sánh hiệu năng.

1. **Dữ liệu là dữ liệu giả lập**, sinh bằng `generate_data.py` với seed cố định nên có thể tái tạo. Đề tài không dùng dữ liệu thật vì dữ liệu cá nhân được pháp luật bảo vệ (Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân).
2. Tên **không dấu**, chỉ gồm 10 họ, 15 tên và 7 tên đệm cho mỗi giới tính. Vì vậy số người trùng tên rất cao, khác với thực tế.
3. Chỉ dùng **10 tỉnh** làm quê quán và mã tỉnh trong CCCD. Mã tỉnh (ví dụ 001 Hà Nội, 079 TP. Hồ Chí Minh) lấy theo danh sách mã tỉnh dùng cho số định danh (63 tỉnh trước sắp xếp). Quê quán là thông tin lịch sử nên có thể dùng tên tỉnh cũ như Bình Dương. Ngược lại, địa chỉ hộ trong một hệ thống thực tế phải theo đơn vị hành chính hiện hành ([6]).
4. Mỗi nhân khẩu chỉ thuộc **một hộ trong suốt thời gian có dữ liệu**. Không có lịch sử chuyển hộ, dù schema đã hỗ trợ việc này qua `tu_ngay`/`den_ngay`.
5. **Không có trạng thái "đã mất"**, nên không sinh biến động "Tử". Nếu sinh biến động "Tử" mà người đó vẫn là thành viên đang hiệu lực của hộ thì dữ liệu sẽ mâu thuẫn.
6. Hộ có đúng 4 người. Thứ tự trong hộ: chủ hộ, vợ/chồng, rồi 2 người là con, cha/mẹ hoặc anh/chị/em.
7. Không mô hình hóa: lưu trú dưới 30 ngày, nơi ở hiện tại, dân tộc, tôn giáo, quốc tịch, ảnh và vân tay.

---

## 6. Hướng hoàn thiện

- **Bảo đảm NV03 ngay ở mức CSDL.** Trong MySQL, thêm cột sinh tự động `dang_hieu_luc = IF(den_ngay IS NULL, nhan_khau_id, NULL)` và đặt `UNIQUE` trên cột này. MySQL cho phép nhiều giá trị NULL trong cột UNIQUE, nên các bản ghi đã kết thúc không bị chặn. Trong MongoDB, nơi thường trú hiện tại đã là trường đơn `ho_khau` trong document công dân, nên một người tự động chỉ có một hộ.
- Thêm trạng thái sống/mất và biến động "Tử", gắn với việc xóa đăng ký thường trú.
- Thêm `CHECK` (MySQL) hoặc `$jsonSchema` validator (MongoDB) cho định dạng CCCD và các giá trị liệt kê.

---

## Nguồn tham khảo đã tra cứu

- Luật Cư trú 2020: https://thuvienphapluat.vn/van-ban/Quyen-dan-su/Luat-68-2020-QH14-cu-tru-435315.aspx; văn bản hợp nhất 01/VBHN-VPQH 2025: https://thuvienphapluat.vn/van-ban/Quyen-dan-su/Van-ban-hop-nhat-01-VBHN-VPQH-2025-Luat-Cu-tru-647143.aspx
- Điều 27 Luật Cư trú (tạm trú từ 30 ngày): https://hethongphapluat.com/luat-cu-tru-2020/dieu-27
- Sổ hộ khẩu hết giá trị sau 31/12/2022: https://pbgdpl.cantho.gov.vn/so-ho-khau-so-tam-tru-se-het-gia-tri-su-dung-sau-ngay-31122022
- Thông tư 55/2021/TT-BCA: https://thuvienphapluat.vn/van-ban/Quyen-dan-su/Circular-55-2021-TT-BCA-elaborating-Residence-Law-478700.aspx
- Luật Căn cước 2023: https://thuvienphapluat.vn/van-ban/quyen-dan-su/Luat-Can-cuoc-26-2023-QH15-552422.aspx
- Cấu trúc 12 số CCCD: https://luatvietnam.vn/tin-phap-luat/y-nghia-12-chu-so-tren-the-can-cuoc-cong-dan-230-17670-article.html
- Luật Hộ tịch 2014: https://thuvienphapluat.vn/van-ban/quyen-dan-su/luat-hotich-2014-259727.aspx
- Nghị quyết 202/2025/QH15: https://thuvienphapluat.vn/van-ban/Bo-may-hanh-chinh/Nghi-quyet-202-2025-QH15-660927.aspx
