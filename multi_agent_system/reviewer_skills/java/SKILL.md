# Java Reviewer Skill

## Phase 1: Investigation guidance

- **Quy trình điều tra hiện trường**:
  - Sử dụng `read_file` tệp gây ra lỗi trong mã nguồn đầu tiên (bỏ qua file testharness.java).
  - Nếu tệp bị lỗi gọi symbol/kiểu dữ liệu từ tệp khác nhưng bị lỗi chưa tìm thấy: Dùng `search_code` để tìm tệp chứa định nghĩa đối ứng để kiểm tra khai báo thực tế.
  - Nếu tệp định nghĩa đối ứng đã được tìm thấy, dùng `read_file` đọc tệp đó để kiểm tra khai báo thực tế.
  - Sau khi đã đọc nơi phát sinh lỗi và nơi định nghĩa đối ứng (tối đa 1-2 tệp), trình bày tóm tắt điều tra bằng văn bản thường rồi dừng gọi tool.
  - Không đưa code snippet vào tóm tắt điều tra.
### NGUYÊN TẮC ĐIỀU TRA HIỆN TRƯỜNG (PHA 1):
- Nhiệm vụ duy nhất là thu thập sự thật khách quan (facts) từ mã nguồn thực tế tại điểm lỗi và điểm định nghĩa đối ứng.
- Đọc tối đa 2-3 tệp liên quan trực tiếp, không đưa ra kết luận sớm ở Pha 1.
- Xác định đúng vị trí lỗi: Phân biệt rõ ràng giữa tệp kiểm thử và tệp mã nguồn dự án theo đúng log lỗi Sandbox.
- Không đoán nội dung mã nguồn, phải đọc mã nguồn tìm sự thật.
### ĐIỀU TRA CHECKED EXCEPTION:
- Với lỗi liên quan đến `try-catch` hoặc `throws`, bắt đầu từ đúng diagnostic và vị trí compiler nêu; không quét toàn project.
- Với `exception X is never thrown in body of corresponding try statement`, kiểm tra chữ ký compile-time của các lời gọi trong `try`, rồi lần qua wrapper/interface trực tiếp để tìm nơi exception bị bắt, bị nuốt hoặc được khai báo `throws`.
- Với `unreported exception X`, kiểm tra lời gọi gây lỗi và xác định caller thiếu `catch` hay `throws`.
- Kiểm tra yêu cầu/plan để biết tầng nào dự kiến xử lý exception. Chỉ đọc các file cần thiết để xác nhận luồng và hợp đồng.
- Tóm tắt điều tra phải ghi rõ diagnostic, các chữ ký liên quan và nơi exception được xử lý/không được propagate. Phase này chỉ thu thập facts, chưa đề xuất sửa.

## Phase 2: Verdict rules
### NGUYÊN TẮC PHÂN CHIA TRÁCH NHIỆM TỆP:
- Tệp kiểm thử dùng để kiểm tra mã nguồn (TestHarness.java): Thuộc về **Tester**.
- Tất cả các tệp mã nguồn dự án còn lại: Thuộc về **Coder** và **Planner**.
### NGUYÊN TẮC PHÁN QUYẾT THẨM PHÁN (PHA 2):
- Log lỗi Sandbox và hồ sơ chứng cứ là căn cứ tối thượng. Phán quyết phải giải thích đúng lỗi đầu tiên làm dừng thực thi.
- Tệp kiểm thử chỉ có tác dụng kiểm tra, không thuộc về mã nguồn lẫn yêu cầu của bài toán. Do đó, nếu tệp kiểm thử bị lỗi, không bao giờ gán trách nhiệm cho PLANNER.
- Tuân thủ Cây quyết định phân định trách nhiệm để chọn đúng 1 Target (CODER, PLANNER hoặc TESTER).
- Hướng dẫn sửa đổi (instructions) phải là thay đổi tối thiểu, cụ thể, bảo tồn các interface và hợp đồng kiến trúc đã có.
### NGUYÊN TẮC XỬ LÝ LỖI TẠI TỆP KIỂM THỬ (TEST HARNESS):
- Nếu log lỗi chỉ ra lỗi cú pháp, cấu trúc câu lệnh, hoặc import/include sai trực tiếp tại tệp kiểm thử (TestHarness.java):
  -> **100% LÀ LỖI CỦA TESTER (TESTCASE)**.
  -> NGHIÊM CẤM gán cho PLANNER hay CODER!
- Khi tệp kiểm thử bị lỗi, **LỖI HOẶC LÀ CODER HOẶC LÀ TESTER**.
- **Quy tắc phân định trách nhiệm**:
  - **Lỗi tại tệp kiểm thử**:
    + Nếu tệp kiểm thử tự bị lỗi cú pháp hoặc import sai hoặc thiếu -> Phán quyết: **TESTER (TESTCASE)**.
    + Nếu tệp kiểm thử gọi hàm/kiểu dữ liệu có trong đặc tả bài toán nhưng mã nguồn chưa có -> Phán quyết: **CODER (LOCAL)**.
    + Nếu tệp kiểm thử gọi hàm/kiểu dữ liệu tự bịa không có trong đặc tả bài toán -> Phán quyết: **TESTER (TESTCASE)**.
    + **TUYỆT ĐỐI KHÔNG gán PLANNER** khi lỗi xảy ra trong tệp kiểm thử.
  - **Lỗi tại tệp mã nguồn dự án**:
    + 100% thuộc về CODER hoặc PLANNER, nghiêm cấm đổ lỗi cho TESTER.
    + Nếu Plan đã có đề cập mà mã nguồn viết thiếu hoặc sai cú pháp, bịa đường dẫn không có trong plan -> Phán quyết: **CODER (LOCAL)**.
    + Chỉ khi Plan thiếu hẳn thành phần mà bài toán yêu cầu -> Phán quyết: **PLANNER (GLOBAL)**.
  - **Lỗi runtime assert thất bại**:
    + Phân định CODER (mã nguồn xử lý sai) hay TESTER (assert vô lý so với đặc tả).
### VERDICT CHO CHECKED EXCEPTION:
- Dựa trên evidence từ Phase 1 và yêu cầu/plan để chọn một hướng sửa nhất quán:
  - Nếu contract yêu cầu caller xử lý `X`, giữ `catch` tại caller và cho các wrapper trung gian khai báo `throws X` để propagate exception.
  - Nếu contract yêu cầu wrapper xử lý `X`, wrapper bắt exception tại đó; caller không bắt `X` nếu nó không được propagate.
- Không xóa `catch` chỉ để làm hết lỗi `exception X is never thrown`; không thêm `throw new X(...)` tùy tiện để làm `catch` reachable.
- Nếu đổi chữ ký `throws`, xét các caller bị ảnh hưởng và chỉ thị cập nhật chúng nhất quán.
- Nếu không có căn cứ xác định tầng xử lý trong yêu cầu/plan/hợp đồng hiện có, nêu rõ chưa đủ căn cứ; không tự chọn hướng sửa hoặc quy lỗi cho Planner.

