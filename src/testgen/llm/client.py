from __future__ import annotations

import json
from pathlib import Path

import httpx

from testgen.config.models import LLMConfig
from testgen.domain.models import GenerationResult, FunctionInfo


def _response_to_text(data: object) -> str:
    """Извлекает текст из ответа сервера — перебирает возможные поля."""
    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        for key in ("text", "content", "response", "answer", "output",
                    "result", "generated_text", "message"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val

        if isinstance(data.get("result"), dict):
            return _response_to_text(data["result"])
        if isinstance(data.get("data"), dict):
            return _response_to_text(data["data"])

    return json.dumps(data, ensure_ascii=False, indent=2)


class LLMClient:
    """Клиент для работы с LLM-сервером."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=config.timeout_seconds,
            proxy=config.proxy,
        )

    def complete(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        """Отправляет промпт и возвращает GenerationResult."""
        # Объединяем system + user в одну строку — сервер ожидает просто "prompt"
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        body = {
            "model": self.config.model_name,
            "prompt": full_prompt,
        }
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }
        print(self.config.api_base_url, headers, payload, flush=True)
        response = self._client.post(
            self.config.api_base_url,
            headers=headers,
            content=payload,
        )
        
        if response.status_code >= 400:
            raise RuntimeError(
                f"HTTP {response.status_code}: {response.text[:800]}"
            )

        try:
            data = response.json()
            content = _response_to_text(data)
        except json.JSONDecodeError:
            content = response.text.strip()

        if not content.strip():
            raise RuntimeError("LLM вернул пустой ответ")

        dummy_func = FunctionInfo(
            name="unknown",
            signature="",
            body="",
            docstring=None,
            includes=[],
            file_path=Path("unknown.cpp"),
            module_name="unknown",
        )

        usage = data.get("usage", {}) if isinstance(data, dict) else {}

        return GenerationResult(
            content=content,
            func_info=dummy_func,
            model=self.config.model_name,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> LLMClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()