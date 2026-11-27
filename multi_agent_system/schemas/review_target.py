from enum import Enum


class ReviewTarget(str, Enum):
    PLANNER = "PLANNER"   # Lỗi Global: mâu thuẫn giữa các file, sai interface, sai import
    CODER = "CODER"       # Lỗi Local: cú pháp trong 1 file, lỗi logic cài đặt bên trong hàm
    TESTER = "TESTER"     # Lỗi Testcase: assertion sai so với yêu cầu, giả định sai
    PASSED = "PASSED"     # Đạt yêu cầu, không có lỗi
