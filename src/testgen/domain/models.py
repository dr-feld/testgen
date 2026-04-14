from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class FunctionInfo:
    name: str
    signature: str
    body: str
    docstring: Optional[str]
    includes: List[str]
    file_path: Path
    module_name: str


@dataclass(frozen=True)
class GenerationResult:
    content: str
    func_info: FunctionInfo
    model: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class SourceFileInfo:
    path: Path
    functions: List[FunctionInfo]