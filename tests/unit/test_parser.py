"""Tests for analysis/parser.py (libclang backend)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Adjust import path if running tests from project root without install
# ---------------------------------------------------------------------------
from testgen.analysis.parser import CppParser, _INCLUDE_RE
from testgen.domain.models import FunctionInfo, SourceFileInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_cpp(tmp_path: Path, src: str, name: str = "test_input.cpp") -> Path:
    """Write *src* to a temp .cpp file and return its path."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(src), encoding="utf-8")
    return p


def func_names(info: SourceFileInfo) -> list[str]:
    return [f.name for f in info.functions]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser() -> CppParser:
    return CppParser()


# ---------------------------------------------------------------------------
# Basic cases
# ---------------------------------------------------------------------------

class TestBasicFunctions:
    def test_simple_function(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            int add(int a, int b) {
                return a + b;
            }
        """)
        result = parser.parse_file(p)
        assert isinstance(result, SourceFileInfo)
        assert "add" in func_names(result)

    def test_module_name_equals_stem(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "void noop() {}", name="math_utils.cpp")
        result = parser.parse_file(p)
        assert result.functions[0].module_name == "math_utils"

    def test_file_path_stored(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "void noop() {}")
        result = parser.parse_file(p)
        assert result.functions[0].file_path == p.resolve()

    def test_returns_source_file_info(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "void noop() {}")
        result = parser.parse_file(p)
        assert isinstance(result, SourceFileInfo)
        assert result.path == p.resolve()

    def test_file_not_found(self, parser: CppParser) -> None:
        with pytest.raises(FileNotFoundError):
            parser.parse_file(Path("/nonexistent/path/file.cpp"))

    def test_empty_file(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "")
        result = parser.parse_file(p)
        assert result.functions == []

    def test_multiple_functions(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            int add(int a, int b) { return a + b; }
            int sub(int a, int b) { return a - b; }
            int mul(int a, int b) { return a * b; }
        """)
        names = func_names(parser.parse_file(p))
        assert set(names) == {"add", "sub", "mul"}


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------

class TestSignature:
    def test_return_type_in_signature(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "double square(double x) { return x * x; }")
        f = parser.parse_file(p).functions[0]
        assert "double" in f.signature
        assert "square" in f.signature

    def test_parameter_names_in_signature(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "int add(int alpha, int beta) { return alpha + beta; }")
        f = parser.parse_file(p).functions[0]
        assert "alpha" in f.signature
        assert "beta" in f.signature

    def test_void_return(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "void noop(int x) { (void)x; }")
        f = parser.parse_file(p).functions[0]
        assert "void" in f.signature

    def test_const_ref_param(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            #include <string>
            int length(const std::string& s) { return static_cast<int>(s.size()); }
        """)
        f = parser.parse_file(p).functions[0]
        assert "string" in f.signature
        assert "s" in f.signature

    def test_namespace_qualified_name(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            namespace math {
                int add(int a, int b) { return a + b; }
            }
        """)
        f = parser.parse_file(p).functions[0]
        assert "math::add" in f.signature


# ---------------------------------------------------------------------------
# Body extraction
# ---------------------------------------------------------------------------

class TestBodyExtraction:
    def test_body_contains_function_text(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            int add(int a, int b) {
                return a + b;
            }
        """)
        f = parser.parse_file(p).functions[0]
        assert "return a + b" in f.body

    def test_multiline_body(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            int clamp(int v, int lo, int hi) {
                if (v < lo) return lo;
                if (v > hi) return hi;
                return v;
            }
        """)
        f = parser.parse_file(p).functions[0]
        assert "lo" in f.body
        assert "hi" in f.body

    def test_nested_braces_parsed_correctly(self, parser: CppParser, tmp_path: Path) -> None:
        """Nested {} must not confuse the parser (was the regex bug)."""
        p = write_cpp(tmp_path, """
            int nested(int x) {
                if (x > 0) {
                    if (x > 10) {
                        return 2;
                    }
                    return 1;
                }
                return 0;
            }
        """)
        f = parser.parse_file(p).functions[0]
        assert f.name == "nested"
        assert "return 2" in f.body


# ---------------------------------------------------------------------------
# Docstring / comments
# ---------------------------------------------------------------------------

class TestDocstring:
    def test_doxygen_comment_extracted(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            /// @brief Computes the sum.
            /// @param a first operand
            /// @return sum
            int add(int a, int b) { return a + b; }
        """)
        f = parser.parse_file(p).functions[0]
        assert f.docstring is not None
        assert "Computes" in f.docstring

    def test_block_comment_extracted(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            /**
             * Multiplies two integers.
             */
            int mul(int a, int b) { return a * b; }
        """)
        f = parser.parse_file(p).functions[0]
        assert f.docstring is not None
        assert "Multiplies" in f.docstring

    def test_no_comment_is_none(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "int add(int a, int b) { return a + b; }")
        f = parser.parse_file(p).functions[0]
        assert f.docstring is None


# ---------------------------------------------------------------------------
# Includes
# ---------------------------------------------------------------------------

class TestIncludes:
    def test_system_includes_extracted(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            #include <vector>
            #include <string>
            void noop() {}
        """)
        f = parser.parse_file(p).functions[0]
        assert "vector" in f.includes
        assert "string" in f.includes

    def test_local_includes_extracted(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            #include "mylib.h"
            #include "utils/helper.h"
            void noop() {}
        """)
        f = parser.parse_file(p).functions[0]
        assert "mylib.h" in f.includes
        assert "utils/helper.h" in f.includes

    def test_no_includes(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "void noop() {}")
        f = parser.parse_file(p).functions[0]
        assert f.includes == []


# ---------------------------------------------------------------------------
# C++ language features (C++11 and later)
# ---------------------------------------------------------------------------

class TestCppFeatures:
    def test_function_template(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            template<typename T>
            T identity(T x) { return x; }
        """)
        names = func_names(parser.parse_file(p))
        assert "identity" in names

    def test_static_inline(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "static inline int helper(int x) { return x * 2; }")
        names = func_names(parser.parse_file(p))
        assert "helper" in names

    def test_default_argument(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "int inc(int x, int step = 1) { return x + step; }")
        f = parser.parse_file(p).functions[0]
        assert f.name == "inc"
        assert "step" in f.signature

    def test_trailing_return_type(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "auto square(int x) -> int { return x * x; }")
        names = func_names(parser.parse_file(p))
        assert "square" in names

    def test_constexpr_function(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "constexpr int factorial(int n) { return n <= 1 ? 1 : n * factorial(n - 1); }")
        names = func_names(parser.parse_file(p))
        assert "factorial" in names

    def test_noexcept_function(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "int safe_add(int a, int b) noexcept { return a + b; }")
        names = func_names(parser.parse_file(p))
        assert "safe_add" in names

    def test_lambda_not_extracted_as_top_level(self, parser: CppParser, tmp_path: Path) -> None:
        """Lambdas inside function bodies must not be reported as separate functions."""
        p = write_cpp(tmp_path, """
            #include <algorithm>
            #include <vector>
            void sort_vec(std::vector<int>& v) {
                std::sort(v.begin(), v.end(), [](int a, int b) { return a < b; });
            }
        """)
        names = func_names(parser.parse_file(p))
        assert names == ["sort_vec"]

    def test_overloaded_functions(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            int process(int x) { return x; }
            double process(double x) { return x; }
        """)
        names = func_names(parser.parse_file(p))
        assert names.count("process") == 2

    def test_nested_namespaces(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            namespace outer {
                namespace inner {
                    int compute(int x) { return x * 3; }
                }
            }
        """)
        f = parser.parse_file(p).functions[0]
        assert "outer::inner::compute" in f.signature

    def test_class_method(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            class Calculator {
            public:
                int add(int a, int b) { return a + b; }
            };
        """)
        names = func_names(parser.parse_file(p))
        assert "add" in names

    def test_constructor_excluded_by_default(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            class Foo {
            public:
                Foo() {}
                int value() { return 42; }
            };
        """)
        names = func_names(parser.parse_file(p))
        assert "Foo" not in names
        assert "value" in names

    def test_destructor_excluded_by_default(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            class Foo {
            public:
                ~Foo() {}
                int value() { return 42; }
            };
        """)
        names = func_names(parser.parse_file(p))
        assert "~Foo" not in names

    def test_variadic_template(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            template<typename... Args>
            int count_args(Args... args) { return sizeof...(args); }
        """)
        names = func_names(parser.parse_file(p))
        assert "count_args" in names

    def test_header_file(self, parser: CppParser, tmp_path: Path) -> None:
        """.h files parse exactly like .cpp."""
        p = tmp_path / "utils.h"
        p.write_text("inline int double_it(int x) { return x * 2; }\n")
        names = func_names(parser.parse_file(p))
        assert "double_it" in names

    def test_declarations_without_body_excluded(self, parser: CppParser, tmp_path: Path) -> None:
        """Forward declarations (no body) must not be included."""
        p = write_cpp(tmp_path, """
            int add(int a, int b);          // declaration only
            int add(int a, int b) { return a + b; }  // definition
        """)
        funcs = parser.parse_file(p).functions
        assert len(funcs) == 1

    def test_function_returning_pointer(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "int* alloc(int n) { return new int[n]; }")
        f = parser.parse_file(p).functions[0]
        assert "alloc" in f.signature
        assert "*" in f.signature

    def test_attribute_annotated_function(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "[[nodiscard]] int compute(int x) { return x; }")
        names = func_names(parser.parse_file(p))
        assert "compute" in names

    def test_conversion_function_excluded_by_default(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, """
            class Foo {
            public:
                operator int() { return 42; }
                int value() { return 42; }
            };
        """)
        names = func_names(parser.parse_file(p))
        assert "operator int" not in names
        assert "value" in names

    def test_unnamed_parameter_in_signature(self, parser: CppParser, tmp_path: Path) -> None:
        p = write_cpp(tmp_path, "int foo(int, double) { return 0; }")
        f = parser.parse_file(p).functions[0]
        assert "int" in f.signature
        assert "double" in f.signature


# ---------------------------------------------------------------------------
# CppParser initialisation options
# ---------------------------------------------------------------------------

class TestCppParserInit:
    def test_custom_skip_kinds_includes_constructors(self, tmp_path: Path) -> None:
        parser = CppParser(skip_kinds=frozenset())
        p = write_cpp(tmp_path, """
            class Foo {
            public:
                Foo() {}
                int value() { return 42; }
            };
        """)
        names = func_names(parser.parse_file(p))
        assert "Foo" in names

    def test_custom_extra_args_accepted(self, tmp_path: Path) -> None:
        parser = CppParser(extra_args=["-std=c++17", "-x", "c++"])
        p = write_cpp(tmp_path, "int foo() { return 1; }")
        assert "foo" in func_names(parser.parse_file(p))

    def test_std_flag_not_duplicated_when_present_in_extra_args(self) -> None:
        parser = CppParser(extra_args=["-std=c++17", "-x", "c++"])
        count = sum(1 for arg in parser._extra_args if arg.startswith("-std="))
        assert count == 1

    def test_cpp_standard_inserted_when_missing_from_extra_args(self) -> None:
        parser = CppParser(extra_args=["-x", "c++"], cpp_standard="c++14")
        assert "-std=c++14" in parser._extra_args


# ---------------------------------------------------------------------------
# Error handling / diagnostics
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_preprocessor_error_raises_runtime_error(self, tmp_path: Path) -> None:
        parser = CppParser()
        p = write_cpp(tmp_path, """
            #error intentional fatal error
            void foo() {}
        """)
        with pytest.raises(RuntimeError, match="libclang reported errors"):
            parser.parse_file(p)

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        parser = CppParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file(tmp_path / "nonexistent.cpp")


# ---------------------------------------------------------------------------
# _INCLUDE_RE regex (unit tests, no libclang)
# ---------------------------------------------------------------------------

class TestIncludeRegex:
    def test_angle_bracket_include(self) -> None:
        assert _INCLUDE_RE.findall("#include <vector>") == ["vector"]

    def test_quoted_include(self) -> None:
        assert _INCLUDE_RE.findall('#include "myheader.h"') == ["myheader.h"]

    def test_multiple_includes(self) -> None:
        src = "#include <string>\n#include <vector>"
        assert _INCLUDE_RE.findall(src) == ["string", "vector"]

    def test_no_includes_returns_empty(self) -> None:
        assert _INCLUDE_RE.findall("int main() { return 0; }") == []

    def test_include_with_subdirectory_path(self) -> None:
        assert _INCLUDE_RE.findall('#include "utils/helper.h"') == ["utils/helper.h"]

    def test_include_with_spaces_around_hash(self) -> None:
        assert _INCLUDE_RE.findall("   #   include <cstdint>") == ["cstdint"]


# ---------------------------------------------------------------------------
# conftest fixtures integration
# ---------------------------------------------------------------------------

class TestConfixtures:
    def test_sample_cpp_file_parses(self, parser: CppParser, sample_cpp_file: Path) -> None:
        result = parser.parse_file(sample_cpp_file)
        assert isinstance(result, SourceFileInfo)
        assert any(f.name == "add" for f in result.functions)