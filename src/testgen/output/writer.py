from __future__ import annotations

from pathlib import Path
from testgen.domain.models import GenerationResult
from testgen.config.models import ProjectConfig


class TestWriter:
    """Сохраняет сгенерированный тест на диск"""

    def __init__(self, project_config: ProjectConfig):
        self.project_config = project_config
        self.project_config.tests_path.mkdir(parents=True, exist_ok=True)

    def write(self, result: GenerationResult) -> Path:
        """Сохраняет тест и возвращает путь к файлу"""
        module_name = result.func_info.module_name or result.func_info.file_path.stem
        
        # Имя файла: test_{module}_{function}.cpp
        filename = f"test_{module_name}_{result.func_info.name}.cpp"
        
        output_dir = self.project_config.tests_path / module_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / filename
        
        output_path.write_text(result.content, encoding="utf-8")
        
        return output_path