"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
import re
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config
from .logger import get_logger

logger = get_logger('mirofish.llm_client')

# HTTP-Status, bei denen ein Retry sinnlos ist (Auth/Guthaben/Request kaputt)
_NO_RETRY_STATUS = {400, 401, 402, 403, 404, 422}
_MAX_ATTEMPTS = 3


def _resolve_default_model() -> str:
    """Admin-Override (app_settings.json) vor .env-Wert."""
    try:
        from ..models.app_settings import AppSettings
        return AppSettings.effective_llm_model()
    except Exception:
        return Config.LLM_MODEL_NAME


class LLMClient:
    """LLM客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or _resolve_default_model()
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）
            
        Returns:
            模型响应文本
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format

        # Transiente Fehler (Timeout, 429, 5xx) automatisch wiederholen;
        # bei Auth-/Guthaben-Fehlern (401/402/...) sofort durchreichen.
        response = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except Exception as e:
                status = getattr(e, 'status_code', None)
                msg = str(e).lower()
                transient = (
                    status not in _NO_RETRY_STATUS and (
                        status in (408, 409, 429, 500, 502, 503, 504)
                        or 'timeout' in msg or 'timed out' in msg
                        or 'connection' in msg or 'overloaded' in msg
                        or 'rate limit' in msg
                    )
                )
                if not transient or attempt == _MAX_ATTEMPTS:
                    raise
                wait = 2 * attempt
                logger.warning(
                    f"LLM-Aufruf fehlgeschlagen (Versuch {attempt}/{_MAX_ATTEMPTS}, "
                    f"status={status}): {e} — Retry in {wait}s"
                )
                time.sleep(wait)
        content = response.choices[0].message.content
        # Manche Modelle (z. B. Gemini bei reinem Tool-Call/leerer Antwort) liefern
        # content=None -> re.sub würde crashen. Auf "" absichern.
        if content is None:
            content = ""
        # 部分模型（如MiniMax M2.5）会在content中包含<think>思考内容，需要移除
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            解析后的JSON对象
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # 清理markdown代码块标记
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"LLM返回的JSON格式无效: {cleaned_response}")

