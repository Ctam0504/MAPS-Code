"""
multi_agent_system.agents.reviewer_agent
======================================
Agent Reviewer: Tiếp nhận task, plan, code đa tệp, testcase, cây thư mục và log lỗi Sandbox.
Thẩm định nguyên nhân cốt lõi và phân định chính xác:
- PLANNER: Lỗi Global (mâu thuẫn giữa các file, sai import, lệch interface)
- CODER: Lỗi Local (cú pháp nội bộ trong 1 file, lỗi logic cài đặt thân hàm)
- TESTER: Lỗi Testcase (assert sai kỳ vọng, testcase vi phạm yêu cầu bài toán)
"""

import json
from typing import Dict, Optional, Any, List
from .base_agent import BaseAgent
from ..schemas import MultiFilePlan, ReviewDecision, ReviewTarget
from .. import config
import re
class ReviewerAgent(BaseAgent):
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(
            model_name=model_name or config.REVIEWER_MODEL,
            base_url=base_url,
            temperature=0.1
        )

    def review(
        self,
        task_goal: str,
        plan: MultiFilePlan,
        files_dict: Dict[str, str],
        test_cases: str,
        error_msg: str
    ) -> ReviewDecision:
        """
        Thẩm định log lỗi và phân định trách nhiệm.
        """
        code_overview = ""
        for filepath, content in files_dict.items():
            code_overview += f"\n--- FILE: `{filepath}` ---\n```{plan.target_language}\n{content}\n```\n"

        prompt = f"""BẠN LÀ META-LOGIC AUDITOR & ROOT-CAUSE SYSTEM ANALYZER.
Nhiệm vụ: Phân tích sự cố thực thi Sandbox, đối chiếu toàn bộ mã nguồn đa tệp và yêu cầu bài toán,
sau đó PHÁN QUYẾT CHÍNH XÁC AI LÀ NGƯỜI SAI (PLANNER, CODER, hay TESTER).

### [1. YÊU CẦU BÀI TOÁN GỐC (SPECIFICATION)]:
{task_goal}

### [2. PLAN HIỆN TẠI (PLANNER)]:
Kiến trúc: {plan.architecture_pattern}
Các tệp: {[f.filepath for f in plan.files]}

### [3. TOÀN BỘ MÃ NGUỒN CÁC TỆP (CODER)]:
{code_overview}

### [4. KỊCH BẢN KIỂM THỬ (TESTER)]:
```{plan.target_language}
{test_cases}
```

### [5. NHẬT KÝ LỖI SANDBOX THỰC TẾ]:
{error_msg if error_msg else "Mã nguồn thực thi thành công, không có lỗi runtime."}

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

### ĐỊNH DẠNG TRẢ VỀ:
Trả về DUY NHẤT một JSON Object hợp lệ:
{{
"status": "REJECTED",
"target": "PLANNER" | "CODER" | "TESTER",
"error_category": "GLOBAL" | "LOCAL" | "TESTCASE",
"failed_files": ["chỉ các file chứa nguyên nhân gốc cần sửa, không gồm caller hoặc file chỉ được nhắc tới"],
"root_cause": "nguyên nhân đã xác minh và vị trí phát sinh thực sự; phân biệt với nơi lỗi được gọi hoặc phát hiện",
"instructions": "cách sửa tối thiểu, cụ thể, hợp lệ với code/API thực tế; nêu file và thay đổi cần thực hiện",
"audit_table": "tóm tắt đối chiếu"
}}
"""

        raw_resp = self.call_llm(prompt, format_json=True)
        json_obj = self.extract_json_object(raw_resp)

        if json_obj and "target" in json_obj:
            try:
                target_str = str(json_obj.get("target", "UNKNOWN")).upper().strip()
                if "PLANNER" in target_str:
                    target_enum = ReviewTarget.PLANNER
                    cat = "GLOBAL"
                elif "TESTER" in target_str:
                    target_enum = ReviewTarget.TESTER
                    cat = "TESTCASE"
                elif "PASSED" in target_str:
                    target_enum = ReviewTarget.PASSED
                    cat = "NONE"
                else:
                    target_enum = ReviewTarget.CODER
                    cat = "LOCAL"

                raw_audit = json_obj.get("audit_table", "")
                if isinstance(raw_audit, (dict, list)):
                    audit_table_val = json.dumps(raw_audit, ensure_ascii=False, indent=2)
                else:
                    audit_table_val = str(raw_audit) if raw_audit is not None else ""

                # Chuẩn hóa danh sách failed_files từ JSON
                raw_failed_files = json_obj.get("failed_files")
                if raw_failed_files is None and json_obj.get("failed_file"):
                    raw_failed_files = [json_obj.get("failed_file")]
                    
                failed_files_list: List[str] = []
                if isinstance(raw_failed_files, list):
                    failed_files_list = [str(f).strip().strip("`'\"") for f in raw_failed_files if f]
                elif isinstance(raw_failed_files, str):
                    failed_files_list = [f.strip().strip("`'\"") for f in raw_failed_files.split(",") if f.strip()]

                # Lọc danh sách tệp thực tế trong project để chống hallucination
                valid_failed_files = [f for f in failed_files_list if f in files_dict]

                # Tạo kwargs tương thích dù Schema có failed_files hay failed_file
                decision_kwargs = {
                    "status": str(json_obj.get("status", "REJECTED")),
                    "target": target_enum,
                    "error_category": str(json_obj.get("error_category", cat)),
                    "root_cause": str(json_obj.get("root_cause", "Phát hiện lỗi khi thực thi sandbox.")),
                    "instructions": str(json_obj.get("instructions", "Vui lòng kiểm tra và sửa đổi theo log lỗi.")),
                    "audit_table": audit_table_val
                }

                # Kiểm tra thuộc tính schema để tránh ValidationError
                schema_fields = getattr(ReviewDecision, "__fields__", {}) or getattr(ReviewDecision, "__annotations__", {})
                if "failed_files" in schema_fields:
                    decision_kwargs["failed_files"] = valid_failed_files
                if "failed_file" in schema_fields:
                    decision_kwargs["failed_file"] = valid_failed_files[0] if valid_failed_files else None

                decision = ReviewDecision(**decision_kwargs)
                setattr(decision, "failed_files", valid_failed_files)
                return decision

            except Exception as e:
                print(f"⚠️ [Reviewer] Lỗi cấu trúc JSON sang ReviewDecision: {e}")

        # Fallback regex parsing nếu JSON bị lỗi hoàn toàn
        return self._fallback_parse_decision(raw_resp, error_msg, files_dict)

    def _fallback_parse_decision(
        self, 
        text: str, 
        error_msg: str, 
        files_dict: Dict[str, str]
    ) -> ReviewDecision:
        """
        Bảo hiểm bóc tách dữ liệu bằng Regex khi LLM không trả về đúng cú pháp JSON.
        """
        target_enum = ReviewTarget.CODER
        category = "LOCAL"

        text_upper = text.upper()
        if "TARGET: PLANNER" in text_upper or '"PLANNER"' in text_upper or "GLOBAL" in text_upper:
            target_enum = ReviewTarget.PLANNER
            category = "GLOBAL"
        elif "TARGET: TESTER" in text_upper or '"TESTER"' in text_upper or "TESTCASE" in text_upper:
            target_enum = ReviewTarget.TESTER
            category = "TESTCASE"
        elif "PASSED" in text_upper and not error_msg:
            target_enum = ReviewTarget.PASSED
            category = "NONE"

        # Trích xuất danh sách failed_files từ text
        failed_files: List[str] = []
        ff_json = re.search(r'"failed_files"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if ff_json:
            raw_list = ff_json.group(1)
            extracted = [re.sub(r'["\s\']', '', f) for f in raw_list.split(",") if f.strip()]
            failed_files = [f for f in extracted if f in files_dict]
        else:
            ff_single = re.search(r'"failed_file"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if ff_single:
                fp = ff_single.group(1).strip()
                if fp in files_dict:
                    failed_files = [fp]

        # Trích xuất root_cause
        root_cause = ""
        rc_json = re.search(r'"root_cause"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if rc_json:
            root_cause = rc_json.group(1).encode('utf-8').decode('unicode-escape', errors='ignore').strip()
        else:
            rc_match = re.search(r"ROOT_CAUSE:?\s*(.*?)(?=\n[A-Z_]+:|$)", text, re.IGNORECASE | re.DOTALL)
            if rc_match:
                root_cause = rc_match.group(1).strip()

        if not root_cause:
            if error_msg:
                lines = [l.strip() for l in error_msg.splitlines() if l.strip()]
                root_cause = lines[-1] if lines else "Lỗi thực thi sandbox."
            else:
                root_cause = "Không thể phân tích chi tiết lỗi."

        root_cause = re.sub(r'^[\s":*]+', '', root_cause).strip()

        # Trích xuất instructions
        instructions = ""
        ins_json = re.search(r'"instructions"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if ins_json:
            instructions = ins_json.group(1).encode('utf-8').decode('unicode-escape', errors='ignore').strip()
        else:
            ins_match = re.search(r"INSTRUCTION[S]?:?\s*(.*?)(?=\n[A-Z_]+:|$)", text, re.IGNORECASE | re.DOTALL)
            if ins_match:
                instructions = ins_match.group(1).strip()

        if not instructions:
            instructions = "Vui lòng đối chiếu log lỗi và sửa đổi mã nguồn tương ứng."

        instructions = re.sub(r'^[\s":*]+', '', instructions).strip()

        decision_kwargs = {
            "status": "PASSED" if target_enum == ReviewTarget.PASSED else "REJECTED",
            "target": target_enum,
            "error_category": category,
            "root_cause": root_cause,
            "instructions": instructions,
            "audit_table": ""
        }

        schema_fields = getattr(ReviewDecision, "__fields__", {}) or getattr(ReviewDecision, "__annotations__", {})
        if "failed_files" in schema_fields:
            decision_kwargs["failed_files"] = failed_files
        if "failed_file" in schema_fields:
            decision_kwargs["failed_file"] = failed_files[0] if failed_files else None

        decision = ReviewDecision(**decision_kwargs)
        setattr(decision, "failed_files", failed_files)
        return decision