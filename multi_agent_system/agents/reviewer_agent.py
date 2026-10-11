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
   - Đọc ngược từ đoạn `Caused by:` hoặc dòng lỗi sâu nhất trong [5. NHẬT KÝ LỖI SANDBOX THỰC TẾ].
   - Trích xuất chính xác: Tên file (`filepath`), số dòng (`line_number`), tên class/method, và loại Exception / Syntax error.
2. PHÂN TÍCH LUỒNG TRUY CẬP LỖI (DATAFLOW & CALL CHAIN):
   - Nếu lỗi xảy ra tại File A (ví dụ: `NullPointerException` hoặc `cannot find symbol`):
     + Kiểm tra xem dữ liệu/interface/class được truyền vào File A đến từ file nào (File B, File C).
     + Nếu File A bị hỏng do nhận sai Contract / null từ File B: Root Cause nằm ở **File B**, không phải File A.
     + Nếu File A tự tính toán sai logic nội bộ hoặc sai syntax: Root Cause nằm ở **File A**.
3. XÁC ĐỊNH DANH SÁCH FILE LỖI (`failed_files`):
   - Liệt kê đầy đủ tất cả các tệp thực sự chứa nguồn gốc gây lỗi vào danh sách `failed_files` (chỉ điền tên tệp có trong dự án, không chèn ký tự thừa).

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
"failed_files": ["danh_sách", "các_file", "thực_sự_bị_lỗi_cần_sửa"],
"root_cause": "nguyên nhân kỹ thuật cốt lõi kèm vị trí file và dòng bị lỗi",
"instructions": "chỉ thị sửa đổi cho các file cụ thể cho target agent",
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