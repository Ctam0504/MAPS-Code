Hệ thống multi agent code generation multi file 3 mã nguồn python, java và c
Yêu cầu:
Các module, các file sắp xếp clean, có thể kế thừa mở rộng, chú thích rõ ràng
Sử dụng các file, tools đã có trong folder. Không chỉnh sửa gì các file gốc, nếu có thì làm 1 bản copy.
Cấu trúc project có thể tùy chỉnh các tham số, số lượng agent, số lượng vòng lặp self-correct rõ ràng ở 1 file.
Không cần execution để kiểm thử. Khi hoàn thiện mới bắt đầu kiểm thử.
Kiến trúc:
Agent planner: Tiếp nhận yêu cầu, đọc cây thư mục bằng GraphRAG đã xây dựng, xác định ngôn ngữ mã nguồn nếu có sẵn bằng tools, giao task cho coder, sửa đổi nếu được yêu cầu từ reviewer
Agent coder: Tiếp nhận task từ planner, sinh mã nguồn dựa trên ngôn ngữ do planner đưa ra, sửa đổi nếu được yêu cầu từ reviewer
Agent Tester: Tiếp nhận task, code và ngôn ngữ do planner đưa ra, sinh ra testcase, sửa đổi nếu được yêu cầu từ reviewer. Java sử dụng JUnit 5; sandbox compile và chạy JUnit suite tương tự cách Python dùng unittest.
Agent reviewer: Tiếp nhận task, code, testcase và cây thư mục. Từ đó quyết định xem nếu có mâu thuẫn thì planner, coder và tester ai là người sai
Workflow:
Người dùng nhập task và thiết lập folder input (có thể rỗng hoặc có file)
Planner tiếp nhận yêu cầu, xây dựng cây thư mục, xác định loại ngôn ngữ, phân tích, lập plan, giao task cho coder (file X làm gì, sử dụng các hàm thư viện gì..... dựa vào cây thư mục đã xây dựng), cập nhật lại plan, cây thư mục nếu có yêu cầu từ reviewer
Coder sinh ra mã nguồn từng file dựa trên những gì planner đã giao (task, loại ngôn ngữ), cập nhật lại code nếu có yêu cầu từ reviewer
Tester sinh ra các testcase dựa trên những gì planner và coder đã giao (task, code, loại ngôn ngữ), cập nhật lại testcase nếu có yêu cầu từ reviewer
Sandbox: dựa trên loại mã nguồn xác định engine kiểm thử (python, java, c), execution code và testcase tương ứng.
Nếu có mâu thuẫn, log lỗi sẽ được gửi về Reviewer, tiếp tục vòng lặp self-correction cho đến khi hết ngưỡng.
Nếu không có mẫu thuẫn, tiếp tục vòng lặp cho đến khi thõa mãn, sau đó cho ra kết quả là các file cuối cùng
Reviewer dựa vào log lỗi phân định planner (lỗi global), coder (lỗi local) hay tester (lỗi testcase) là người sai
Sau khi hết ngưỡng, sinh ra kết quả cuối cùng.