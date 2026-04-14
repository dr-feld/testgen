# tests/conftest.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from testgen.domain.models import FunctionInfo, GenerationResult

@pytest.fixture
def sample_func_info():
    return FunctionInfo(
        name="add",
        signature="int add(int a, int b)",
        body="int add(int a, int b) { return a + b; }",
        docstring=None,
        includes=[],
        file_path=Path("math.cpp"),
        module_name="math",
    )

@pytest.fixture
def sample_cpp_file():
    return Path(__file__).parent / "fixtures" / "sample.cpp"

@pytest.fixture
def mock_config():
    return MagicMock()