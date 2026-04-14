from __future__ import annotations

from pathlib import Path
from testgen.domain.models import FunctionInfo, GenerationResult
from testgen.config.models import AppConfig
from testgen.prompt.builder import PromptBuilder
from testgen.llm.client import LLMClient
from testgen.postprocess.processor import postprocess   # будет создан дальше


class TestGenerator:
    """Основная логика генерации одного теста"""

    def __init__(self, config: AppConfig, prompt_builder: PromptBuilder, llm_client: LLMClient):
        self.config = config
        self.prompt_builder = prompt_builder
        self.llm_client = llm_client

    def generate(self, func_info: FunctionInfo) -> GenerationResult:
        """Генерирует тест для одной функции"""
        # 1. Собираем промпты
        system_prompt, user_prompt = self.prompt_builder.build(func_info, self.config.project)
        
        # 2. Отправляем в LLM
        result = self.llm_client.complete(system_prompt, user_prompt)
        
        # 3. Постобработка
        clean_code = postprocess(result.content)

        # Обновляем результат
        result = GenerationResult(
            content=clean_code,
            func_info=func_info,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

        return result