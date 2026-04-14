from __future__ import annotations

import re
from pathlib import Path
from testgen.domain.models import FunctionInfo, SourceFileInfo


class CppParser:
    """Простой парсер C++ для MVP (регулярки + libclang можно добавить позже)"""

    def parse_file(self, file_path: Path) -> SourceFileInfo:
        """Парсит файл и возвращает список функций"""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        module_name = file_path.stem

        functions = self._extract_functions(content, file_path, module_name)

        return SourceFileInfo(
            path=file_path,
            functions=functions
        )

    def _extract_functions(self, code: str, file_path: Path, module_name: str) -> list[FunctionInfo]:
        """Очень простой экстрактор функций (для MVP)"""
        functions = []

        # Простой regex для поиска функций (неидеально, но работает для начала)
        pattern = r'(?:(?:inline|static|virtual|const)\s+)?(\w+)\s+(\w+)\s*\(([^)]*)\)\s*\{(.*?)\}'
        matches = re.finditer(pattern, code, re.DOTALL | re.MULTILINE)

        for match in matches:
            return_type = match.group(1)
            name = match.group(2)
            params = match.group(3)
            body = match.group(4)

            signature = f"{return_type} {name}({params})"

            functions.append(FunctionInfo(
                name=name,
                signature=signature.strip(),
                body=f"{signature} {{{body}}}",
                docstring=None,          # TODO: добавить извлечение Doxygen позже
                includes=[],             # TODO: извлекать #include позже
                file_path=file_path,
                module_name=module_name
            ))

        return functions