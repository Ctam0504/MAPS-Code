# C Reviewer Skill

## Phase 1: Investigation guidance

- **Quy trình điều tra hiện trường**:
  - Khám nghiệm điểm lỗi đầu tiên trong log Sandbox bằng `read_file`.
  - Nếu tệp bị lỗi gọi symbol/kiểu dữ liệu từ tệp khác nhưng bị lỗi chưa tìm thấy: Dùng `read_file` đọc tệp định nghĩa đối ứng để kiểm tra khai báo thực tế.
  - Sau khi đã đọc nơi phát sinh lỗi và nơi định nghĩa đối ứng (tối đa 1-2 tệp), trình bày tóm tắt điều tra bằng văn bản thường rồi dừng gọi tool.

## Phase 2: Verdict rules

- **Quy tắc phân định trách nhiệm**:
  - **Lỗi tại tệp kiểm thử**:
    + Nếu tệp kiểm thử tự bị lỗi cú pháp hoặc import/include sai -> Phán quyết: **TESTER (TESTCASE)**.
    + Nếu tệp kiểm thử gọi hàm/kiểu dữ liệu có trong đặc tả bài toán nhưng mã nguồn chưa có -> Phán quyết: **CODER (LOCAL)**.
    + Nếu tệp kiểm thử gọi hàm/kiểu dữ liệu tự bịa không có trong đặc tả bài toán -> Phán quyết: **TESTER (TESTCASE)**.
    + **TUYỆT ĐỐI KHÔNG gán PLANNER** khi lỗi xảy ra trong tệp kiểm thử.
  - **Lỗi tại tệp mã nguồn dự án**:
    + 100% thuộc về CODER hoặc PLANNER, nghiêm cấm đổ lỗi cho TESTER.
    + Nếu Plan đã có đề cập mà mã nguồn viết thiếu hoặc sai cú pháp -> Phán quyết: **CODER (LOCAL)**.
    + Chỉ khi Plan thiếu hẳn thành phần mà bài toán yêu cầu -> Phán quyết: **PLANNER (GLOBAL)**.
  - **Lỗi runtime assert thất bại**:
    + Phân định CODER (mã nguồn xử lý sai) hay TESTER (assert vô lý so với đặc tả).
