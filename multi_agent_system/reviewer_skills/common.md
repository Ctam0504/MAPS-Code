### QUY TRÌNH THẨM ĐỊNH VÀ NGUYÊN TẮC PHÂN ĐỊNH TRÁCH NHIỆM:
Danh sách file trách nhiệm sửa lỗi:
 + Tester: file test_harness.py, test_harness.java, test_harness.c
 + Coder và Planner: tất cả các file còn lại trong project.

BƯỚC 1: QUY TRÌNH XÁC ĐỊNH NGUYÊN NHÂN CỐT LÕI (ROOT CAUSE ANALYSIS):
1. TRUY VẾT LỖI TỪ STACK TRACE / LOG:
   - Xác định loại lỗi trước: lỗi khởi tạo/import, compile/syntax, exception runtime, assertion failure, hay lỗi môi trường.
   - Với stack trace, phân biệt (a) nơi testcase gọi vào chương trình, (b) nơi exception thực sự phát sinh, và (c) các frame trung gian. Frame của test chỉ là điểm gọi, không tự động là nơi gây lỗi.
   - Dùng frame ứng dụng sâu nhất có liên quan đến exception làm vị trí phát sinh; bỏ qua frame thư viện/runtime nếu chúng không phải nguyên nhân. Với lỗi assertion hoặc API sai trong test harness, kiểm tra chính dòng test gây lỗi.
   - Trích xuất filepath, line number, class/method/symbol và loại lỗi chính xác. Không gọi lỗi runtime là lỗi compile.
   - Nếu log có nhiều test lỗi, phân tích từng lỗi riêng và không gộp các lỗi khác nguyên nhân thành một kết luận.
2. PHÂN TÍCH LUỒNG TRUY CẬP LỖI (DATAFLOW & CALL CHAIN):
   - Không kết luận root cause chỉ từ file đầu/cuối của traceback. Đối chiếu dòng lỗi với nội dung thực tế của source, test, plan và specification.
   - Truy ngược giá trị/API gây lỗi đến nơi tạo ra hoặc định nghĩa sai. Nếu source vi phạm contract hoặc có lỗi nội bộ, root cause thuộc file nguồn đó dù testcase kích hoạt lỗi. Nếu source tuân thủ contract nhưng testcase gọi API sai hoặc đặt kỳ vọng không có căn cứ, root cause thuộc testcase.
   - Với tên chưa định nghĩa/import thiếu, xác định file đang dùng tên đó và kiểm tra import/định nghĩa ngay tại file đó; không quy lỗi cho file chỉ vì file đó định nghĩa symbol được nhắc đến.
   - Phân biệt bằng chứng trực tiếp với giả thuyết. Không khẳng định dataflow, contract hoặc nguyên nhân không thể chứng minh từ ngữ cảnh đã cung cấp.
3. XÁC ĐỊNH DANH SÁCH FILE LỖI (`failed_files`):
   - Chỉ liệt kê file chứa root cause cần sửa; không liệt kê file chỉ gọi hàm, xuất hiện trong stack trace hoặc được nhắc trong phần giải thích.
   - Chỉ dùng đường dẫn chính xác tồn tại trong project hoặc testcase được cung cấp. Nếu chưa xác định được file gốc từ bằng chứng thì để danh sách rỗng, không đoán file.

BƯỚC 1B: ĐỀ XUẤT CÁCH SỬA CÓ THỂ THỰC THI:
1. Đối chiếu root cause với code hiện tại, API/signature thực tế, plan và specification trước khi đề xuất thay đổi.
2. Chỉ dẫn sửa phải cụ thể: nêu file cần sửa, lỗi cần xử lý và thay đổi tối thiểu đủ khắc phục root cause. Đảm bảo thay đổi phù hợp với ngôn ngữ và kiểu đối tượng thực tế.
3. Không đề xuất gọi method/field/import/constructor chưa tồn tại hoặc không phù hợp với kiểu đối tượng. Không đưa ra hướng dẫn chung chung, lặp lại chính dòng gây lỗi, hay chỉ thị không làm thay đổi nguyên nhân.
4. Trước khi trả kết quả, tự kiểm tra: nếu làm đúng instructions thì lỗi trong log có được loại bỏ không, và thay đổi có tạo lỗi mới hoặc vi phạm specification không? Nếu không thể xác minh, nêu giới hạn thay vì đoán.
5. Ưu tiên bản sửa nhỏ nhất và chỉ liệt kê file thực sự cần thay đổi. Nếu log có nhiều root cause độc lập, ghi rõ chúng và cách sửa tương ứng trong instructions, đồng thời chọn target cần xử lý ở vòng hiện tại.

BƯỚC 2: CÂY QUYẾT ĐỊNH PHÂN ĐỊNH TRÁCH NHIỆM (CHỌN DUY NHẤT 1 TARGET):

1. **LỖI BIÊN DỊCH / CÚ PHÁP TẠI TỆP MÃ NGUỒN DỰ ÁN (TUYỆT ĐỐI KHÔNG CHỌN TESTER):**
   - Nếu tệp bị lỗi trong log là tệp mã nguồn của Coder/Planner (ví dụ: `services/MovieService.java:8: error: cannot find symbol`, `data/MovieRepository.java`, `Main.java`):
     -> NGUYÊN TẮC CỐT LÕI: Khi mã nguồn dự án không biên dịch được. Do đó lỗi 100% thuộc về CODER hoặc PLANNER, NGHIÊM CẤM ĐỔ LỖI CHO TESTER!
   - Phân định giữa PLANNER và CODER (Căn cứ vào plan và code):
     + **PLANNER (GLOBAL)**: Plan thiếu, sai, lệch class, method, interface giữa các file trong plan. 
     + **CODER (LOCAL)**: Plan đúng, có đề cập nhưng Coder không triển khai đúng, thiếu những gì plan đề cập, sai cú pháp, sai logic thân hàm.

2. LỖI BIÊN DỊCH / KHÔNG TÌM THẤY KÝ HIỆU TẠI TỆP KIỂM THỬ (TEST HARNESS):
   (Áp dụng khi log lỗi biên dịch/import chỉ ra vị trí đứt gãy xuất hiện, nằm trong file TestHarness)

   👉 BẮT BUỘC LẤY SPECIFICATION LÀM CHÂN LÝ ĐỂ ĐỐI CHIẾU:
   Trích xuất đúng Class / Method / Field / Signature đang bị báo lỗi trong TestHarness và so sánh với [1. YÊU CẦU BÀI TOÁN GỐC (SPECIFICATION)]:

   + TRƯỜNG HỢP 2.1 - CODER SAI (CODER / LOCAL):
     Nếu Class / Method / Signature /Interface mà TestHarness gọi CÓ ĐƯỢC YÊU CẦU TRONG SPECIFICATION, nhưng Coder không khai báo, đặt sai tên, truyền sai tham số, hoặc chưa triển khai.
     -> PHÁN QUYẾT: CODER (LOCAL).
     -> Root cause: Coder vi phạm hợp đồng (Contract) đã được quy định trong Specification.

   + TRƯỜNG HỢP 2.2 - TESTER SAI (TESTER / TESTCASE):
     Nếu Class / Method / Signature /Interface mà TestHarness gọi KHÔNG XUẤT HIỆN TRONG SPECIFICATION (Tester tự bịa ra tên hàm/Class/Interface mới, truyền thêm tham số không có trong đề bài, hoặc import/include sai package, class, thư viện).
     -> PHÁN QUYẾT: TESTER (TESTCASE).
     -> Root cause: Tester tự ý thay đổi Hợp đồng API (Contract) khác với yêu cầu bài toán gốc.

3. **LỖI RUNTIME / ASSERTION FAILURE (MÃ CHẠY ĐƯỢC NHƯNG TEST THẤT BẠI):**
   - Áp dụng khi mã nguồn và TestHarness đều biên dịch thành công, nhưng khi thực thi bị Exception hoặc Assert fail.
   - Đối chiếu với [1. YÊU CẦU BÀI TOÁN GỐC]:
     + Nếu Coder tính toán sai thuật toán hoặc không đáp ứng đúng yêu cầu đề bài -> Chọn **CODER (LOCAL)**.
     + Nếu Coder đã làm đúng yêu cầu đề bài nhưng Testcase, assertion của file test kiểm tra điều kiện vô lý hoặc sai giá trị kỳ vọng -> Chọn **TESTER (TESTCASE)**.
