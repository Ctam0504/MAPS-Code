"""
multi_agent_system.agents.base_agent
====================================
Lớp Agent cơ sở (BaseAgent) cho toàn bộ hệ thống.
Quản lý giao tiếp LLM (OpenAI/Ollama), làm sạch phản hồi, và trích xuất mã nguồn/JSON.
"""

import re
import json
import requests
from typing import Dict, Any, Optional
from openai import OpenAI
from .. import config

class BaseAgent:
    def __init__(
        self,
        model_name: str,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        num_ctx: int = 16384,
        num_predict: int = 4096,
        timeout: int = 300
    ):
        self.provider = config.LLM_PROVIDER
        self.model_name = model_name
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.timeout = timeout

        if self.provider == "openai":
            if not config.OPENAI_API_KEY:
                raise ValueError(
                    "LLM_PROVIDER=openai yêu cầu OPENAI_API_KEY trong file .env."
                )
            api_base_url = config.OPENAI_API_BASE
            api_key = config.OPENAI_API_KEY
        else:
            api_base_url = self.base_url
            api_key = "ollama"

        if not api_base_url.endswith("/v1"):
            api_base_url = f"{api_base_url}/v1"
        self.client = OpenAI(
            base_url=api_base_url,
            api_key=api_key,
            timeout=self.timeout
        )

    def call_llm(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        format_json: bool = False
    ) -> str:
        """
        Gọi LLM theo provider được chọn trong cấu hình môi trường.
        """
        if self.provider == "openai":
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload: Dict[str, Any] = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.num_predict
            }
            if format_json:
                payload["response_format"] = {"type": "json_object"}

            try:
                response = self.client.chat.completions.create(**payload)
                return response.choices[0].message.content or ""
            except Exception as e:
                print(
                    f"❌ [BaseAgent: {self.model_name}] "
                    f"Lỗi khi gọi OpenAI API: {e}"
                )
                return ""

        url = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
                "top_p": 0.95
            },
            "keep_alive": -1
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format_json:
            payload["format"] = "json"

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except Exception as e:
            print(f"❌ [BaseAgent: {self.model_name}] Lỗi khi gọi Ollama API: {e}")
            return ""

    @staticmethod
    def extract_code_block(text: str, language: str = "") -> str:
        """
        Trích xuất code từ Markdown block ```lang ... ``` hoặc fallback sạch.
        """
        if not text:
            return ""

        # 1. Làm sạch ký tự rác MoE nếu có
        for char in ['｜', '▁', '◁', '▷', '█', '░', '▒', '▓']:
            text = text.replace(char, '')

        # 2. Tìm khối code ```lang ... ```
        pattern = rf"```(?:{language}|[a-zA-Z0-9_\-\+]*)\s*(.*?)\s*```"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[-1].strip()

        # Nếu không có ``` nhưng bắt đầu bằng code
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]

        return "\n".join(lines).strip()

    @staticmethod
    def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
        """
        Tìm và parse object JSON trong chuỗi phản hồi của LLM.
        """
        if not text:
            return None

        # Thử parse trực tiếp
        try:
            return json.loads(text.strip())
        except Exception:
            pass

        # Tìm block json trong markdown
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass

        # Tìm dấu ngoặc nhọn đầu tiên và cuối cùng
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace + 1]
            try:
                return json.loads(candidate)
            except Exception:
                pass

        return None
