from __future__ import annotations

import logging
from pathlib import Path

from testgen.analysis.parser import CppParser
from testgen.config.models import AppConfig
from testgen.domain.models import FunctionInfo, GenerationResult
from testgen.generation.generator import TestGenerator
from testgen.llm.client import LLMClient
from testgen.output.writer import TestWriter
from testgen.prompt.builder import PromptBuilder

logger = logging.getLogger(__name__)


class Runner:
    """Оркестратор верхнего уровня. Знает что делать, но не как."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._parser = CppParser()
        self._writer = TestWriter(config.project)
        self._llm_client = LLMClient(config.llm)
        self._prompt_builder = PromptBuilder(config.llm)
        self._generator = TestGenerator(
            config=config,
            prompt_builder=self._prompt_builder,
            llm_client=self._llm_client,
        )

    def run_file(self, path: Path) -> list[Path]:
        """Генерирует тесты для всех функций файла. Возвращает пути к сохранённым файлам."""
        logger.info("Parsing %s...", path)
        file_info = self._parser.parse_file(path)

        functions = file_info.functions
        total = len(functions)
        logger.info("%d function(s) found", total)

        saved_paths: list[Path] = []

        for idx, func_info in enumerate(functions, start=1):
            logger.info("[%d/%d] %s", idx, total, func_info.signature)
            result = self._try_generate(func_info)
            if result is None:
                continue

            test_path = self._try_write(result)
            if test_path is None:
                continue

            saved_paths.append(test_path)
            logger.info("  → %s", test_path)

        logger.info("Done. %d/%d tests generated.", len(saved_paths), total)
        return saved_paths

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _try_generate(self, func_info: FunctionInfo) -> GenerationResult | None:
        """Генерирует тест, изолируя ошибки отдельной функции от общего прогона."""
        try:
            return self._generator.generate(func_info)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping %s — generation failed: %s",
                func_info.signature,
                exc,
            )
            return None

    def _try_write(self, result: GenerationResult) -> Path | None:
        """Сохраняет результат, изолируя ошибки записи от общего прогона."""
        try:
            return self._writer.write(result)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping %s — write failed: %s",
                result.func_info.signature,
                exc,
            )
            return None