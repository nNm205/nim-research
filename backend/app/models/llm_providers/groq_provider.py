from __future__ import annotations
import asyncio
import re
from typing import Any, Dict, List, Optional
import httpx
import requests
from app.config import settings
from app.models.llm_providers.base import LLMProvider
from app.utils.logger import logger

_DEFAULT_TIMEOUT = 60.0
_MAX_RETRIES_429 = 3
_RETRY_BACKOFF_FALLBACK_S = 8.0

class GroqProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = settings.GROQ_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> str:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if kwargs.get("response_format") == "json":
            payload["response_format"] = {"type": "json_object"}

        return await self._call(payload)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        if kwargs.get("response_format") == "json":
            payload["response_format"] = {"type": "json_object"}
        return await self._call(payload)

    def validate(self) -> bool:
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
                timeout=10,
            )
            return r.status_code == 200
        except Exception as e:
            print("Groq validate error:", e)
            return False

    def get_model_name(self) -> str:
        return self.model

    async def _call(self, payload: dict) -> str:
        url = f"{self.base_url}/chat/completions"
        attempt = 0
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            while True:
                response = await client.post(url, headers=self.headers, json=payload)

                if response.status_code == 429 and attempt < _MAX_RETRIES_429:
                    attempt += 1
                    delay = self._retry_delay_seconds(response)
                    logger.warning(
                        f"Groq 429 rate-limited (attempt {attempt}/{_MAX_RETRIES_429}). "
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
                        f"Groq API {response.status_code} for model "
                        f"{self.model!r}: {body}"
                    )

                data = response.json()
                return data["choices"][0]["message"]["content"]

    @staticmethod
    def _retry_delay_seconds(response: httpx.Response) -> float:
        retry_after = response.headers.get("Retry-After") or response.headers.get(
            "retry-after"
        )
        if retry_after:
            try:
                return float(retry_after) + 0.5
            except ValueError:
                pass

        try:
            body = response.json()
        except Exception:
            return _RETRY_BACKOFF_FALLBACK_S

        message = ""
        err = body.get("error")
        if isinstance(err, dict):
            message = err.get("message") or ""
        elif isinstance(err, str):
            message = err

        m = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", message, re.IGNORECASE)
        if m:
            return float(m.group(1)) + 0.5

        return _RETRY_BACKOFF_FALLBACK_S
