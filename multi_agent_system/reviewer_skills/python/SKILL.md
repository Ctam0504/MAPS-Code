# Python Reviewer Skill

## Phase 1: Investigation guidance

- **Quy trình điều tra hiện trường**:
  - Sử dụng `read_file` tệp gây ra lỗi trong mã nguồn đầu tiên (bỏ qua file testharness.py).
  - Nếu tệp bị lỗi gọi symbol/kiểu dữ liệu từ tệp khác nhưng bị lỗi chưa tìm thấy: Dùng `search_code` để tìm tệp chứa định nghĩa đối ứng để kiểm tra khai báo thực tế.
  - Nếu tệp định nghĩa đối ứng đã được tìm thấy, dùng `read_file` đọc tệp đó để kiểm tra khai báo thực tế.
  - Sau khi đã đọc nơi phát sinh lỗi và nơi định nghĩa đối ứng (tối đa 1-2 tệp), trình bày tóm tắt điều tra bằng văn bản thường rồi dừng gọi tool.
  - Tóm tắt điều tra nêu nguyên nhân được xác minh và các đường dẫn liên quan; không đưa code snippet.
### NGUYÊN TẮC ĐIỀU TRA HIỆN TRƯỜNG (PHA 1):
- Nhiệm vụ duy nhất là thu thập sự thật khách quan (facts) từ mã nguồn thực tế tại điểm lỗi và điểm định nghĩa đối ứng.
- Đọc tối đa 2-3 tệp liên quan trực tiếp, không phán xét trách nhiệm, không đưa ra kết luận sớm ở Pha 1.
- Xác định đúng vị trí lỗi: Phân biệt rõ ràng giữa tệp kiểm thử và tệp mã nguồn dự án theo đúng log lỗi Sandbox.
- Tệp kiểm thử (testharness.py) chỉ dùng để kiểm tra mã nguồn, không thuộc về mã nguồn của yêu cầu bài toán. Do đó, nếu tệp kiểm thử đưa ra các hàm hoặc assert vô lý so với yêu cầu bài toán thì lỗi ở tệp kiểm thử.
- Không đoán nội dung mã nguồn, phải đọc mã nguồn tìm sự thật.

## Phase 2: Verdict rules
### NGUYÊN TẮC PHÂN CHIA TRÁCH NHIỆM TỆP:
- Tệp kiểm thử (TestHarness.py): Thuộc về **Tester**.
- Tất cả các tệp mã nguồn dự án còn lại: Thuộc về **Coder** và **Planner**.
### NGUYÊN TẮC PHÁN QUYẾT THẨM PHÁN (PHA 2):
- Log lỗi Sandbox và hồ sơ chứng cứ là căn cứ tối thượng. Phán quyết phải giải thích đúng lỗi đầu tiên làm dừng thực thi.
- Tệp kiểm thử chỉ có tác dụng kiểm tra, không thuộc về mã nguồn của yêu cầu bài toán. Do đó, nếu tệp kiểm thử bị lỗi, không bao giờ gán trách nhiệm cho PLANNER.
- Tuân thủ Cây quyết định phân định trách nhiệm để chọn đúng 1 Target (CODER, PLANNER hoặc TESTER).
- Hướng dẫn sửa đổi (instructions) phải là thay đổi tối thiểu, cụ thể, bảo tồn các interface và hợp đồng kiến trúc đã có.
### NGUYÊN TẮC XỬ LÝ LỖI TẠI TỆP KIỂM THỬ (TEST HARNESS):
- Nếu log lỗi chỉ ra lỗi cú pháp, cấu trúc câu lệnh, hoặc import/include sai trực tiếp tại tệp kiểm thử:
  -> **100% LÀ LỖI CỦA TESTER (TESTCASE)**.
  -> NGHIÊM CẤM gán cho PLANNER hay CODER!
- Khi tệp kiểm thử bị lỗi, **TUYỆT ĐỐI LOẠI TRỪ PLANNER**.
- **Quy tắc phân định trách nhiệm**:
  - **Lỗi tại tệp kiểm thử**:
    + Nếu tệp kiểm thử tự bị lỗi cú pháp hoặc import sai hoặc thiếu -> Phán quyết: **TESTER (TESTCASE)**.
    + Nếu tệp kiểm thử gọi hàm/kiểu dữ liệu có trong đặc tả bài toán nhưng mã nguồn chưa có -> Phán quyết: **CODER (LOCAL)**.
    + Nếu tệp kiểm thử gọi hàm/kiểu dữ liệu tự bịa không có trong đặc tả bài toán -> Phán quyết: **TESTER (TESTCASE)**.
    + **TUYỆT ĐỐI KHÔNG gán PLANNER** khi lỗi xảy ra trong tệp kiểm thử.
  - **Lỗi tại tệp mã nguồn dự án**:
    + 100% thuộc về CODER hoặc PLANNER, nghiêm cấm đổ lỗi cho TESTER.
    + Nếu Plan đã có đề cập mà mã nguồn viết thiếu hoặc sai cú pháp -> Phán quyết: **CODER (LOCAL)**.
    + Chỉ khi Plan thiếu hẳn thành phần mà bài toán yêu cầu -> Phán quyết: **PLANNER (GLOBAL)**.
  - **Lỗi runtime assert thất bại**:
    + mã nguồn xử lý sai yêu cầu bài toán --> Phán quyết: **CODER (LOCAL)** 
    + Testharness đưa ra các assert hoặc testcase vô lý so với yêu cầu bài toán --> phán quyết:  **TESTER (TESTCASE)**