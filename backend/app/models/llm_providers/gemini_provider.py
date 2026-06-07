from __future__ import annotations
import asyncio
import re
from typing import Dict, List, Optional
import httpx
import requests
from app.models.llm_providers.base import LLMProvider
from app.utils.logger import logger


_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_TIMEOUT = 120.0
_MAX_RETRIES_429 = 3
_RETRY_BACKOFF_FALLBACK_S = 8.0


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        base_url: Optional[str] = None,
    ) -> None:
        if not api_key:
            raise ValueError("GeminiProvider requires an api_key")
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> str:
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "generationConfig": self._gen_config(temperature, max_tokens, **kwargs),
        }
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}

        return await self._call(payload)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> str:
        system_prompt: Optional[str] = None
        if messages and messages[0].get("role") == "system":
            system_prompt = messages[0].get("content")
            messages = messages[1:]

        contents: list[dict] = []
        for msg in messages:
            role = msg.get("role")
            if role not in {"user", "assistant", "model"}:
                continue
            
            gemini_role = "model" if role == "assistant" else role
            text = msg.get("content") or ""
            if not text:
                continue
            contents.append({"role": gemini_role, "parts": [{"text": text}]})

        payload: dict = {
            "contents": contents,
            "generationConfig": self._gen_config(
                kwargs.get("temperature", 0.7),
                kwargs.get("max_tokens", 1024),
                **kwargs,
            ),
        }
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}

        return await self._call(payload)

    def validate(self) -> bool:
        try:
            r = requests.post(
                f"{self.base_url}/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json={
                    "contents": [
                        {"role": "user", "parts": [{"text": "hi"}]}
                    ],
                    "generationConfig": {"maxOutputTokens": 5},
                },
                timeout=10,
            )
            return r.status_code == 200
        except Exception as e:
            print("Gemini validate error:", e)
            return False

    def get_model_name(self) -> str:
        return self.model

    def _gen_config(
        self,
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> dict:
        cfg: dict = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if "top_p" in kwargs:
            cfg["topP"] = kwargs["top_p"]
        if "top_k" in kwargs:
            cfg["topK"] = kwargs["top_k"]
        if kwargs.get("response_format") == "json":
            cfg["responseMimeType"] = "application/json"
        return cfg

    async def _call(self, payload: dict) -> str:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        attempt = 0
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            while True:
                response = await client.post(
                    url, params={"key": self.api_key}, json=payload
                )
                if response.status_code == 429 and attempt < _MAX_RETRIES_429:
                    attempt += 1
                    delay = self._retry_delay_seconds(response)
                    logger.warning(
                        f"Gemini 429 rate-limited (attempt {attempt}/{_MAX_RETRIES_429}). "
                        f"Sleeping {delay:.1f}s before retry."
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code >= 400:
                    try:
                        body = response.json()
                    except Exception:
                        body = {"raw": response.text[:500]}
                    raise RuntimeError(
                        f"Gemini API {response.status_code} for model "
                        f"{self.model!r}: {body}"
                    )

                data = response.json()
                return self._extract_text(data)

    @staticmethod
    def _retry_delay_seconds(response: httpx.Response) -> float:
        try:
            body = response.json()
        except Exception:
            return _RETRY_BACKOFF_FALLBACK_S

        details = (body.get("error") or {}).get("details") or []
        for d in details:
            if isinstance(d, dict) and d.get("@type", "").endswith("RetryInfo"):
                raw = d.get("retryDelay")
                if isinstance(raw, str):
                    m = re.match(r"^(\d+(?:\.\d+)?)s$", raw)
                    if m:
                        return float(m.group(1)) + 0.5
        return _RETRY_BACKOFF_FALLBACK_S

    def _extract_text(self, data: dict) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            feedback = data.get("promptFeedback") or {}
            reason = feedback.get("blockReason")
            if reason:
                raise RuntimeError(f"Gemini blocked the prompt: {reason}")
            return ""

        first = candidates[0] or {}
        finish_reason = first.get("finishReason") or ""
        content = first.get("content") or {}
        parts = content.get("parts") or []

        texts: list[str] = []
        for part in parts:
            text = part.get("text")
            if isinstance(text, str):
                texts.append(text)
        result = "".join(texts)

        if finish_reason == "MAX_TOKENS":
            logger.warning(
                f"Gemini returned MAX_TOKENS finishReason for model {self.model!r}. "
                f"Output truncated at {len(result)} chars — increase max_tokens "
                f"or shorten the prompt."
            )

        return result
