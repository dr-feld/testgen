from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

import clang.cindex as cx

from testgen.domain.models import FunctionInfo, SourceFileInfo

_libclang_configured = False


def _configure_libclang() -> None:
    """Find and configure libclang from the sighingnow/libclang package."""
    global _libclang_configured
    if _libclang_configured:
        return

    import clang
    clang_package_dir = Path(clang.__file__).parent

    candidates = [
        clang_package_dir / "native" / "libclang.dll",      # Windows
        clang_package_dir / "native" / "libclang.so",       # Linux
        clang_package_dir / "native" / "libclang.dylib",    # macOS
    ]

    for candidate in candidates:
        if candidate.exists():
            cx.Config.set_library_file(str(candidate))
            _libclang_configured = True
            return

    raise RuntimeError(
        f"libclang не найден в {clang_package_dir / 'native'}. "
        "Установите пакет: pip install libclang"
    )

_configure_libclang()
# ---------------------------------------------------------------------------
# Kinds that represent callable definitions we want to extract
# ---------------------------------------------------------------------------
_FUNCTION_KINDS = frozenset(
    {
        cx.CursorKind.FUNCTION_DECL,
        cx.CursorKind.FUNCTION_TEMPLATE,
        cx.CursorKind.CXX_METHOD,
        cx.CursorKind.CONSTRUCTOR,
        cx.CursorKind.DESTRUCTOR,
        cx.CursorKind.CONVERSION_FUNCTION,
    }
)

# Kinds whose children we skip entirely (lambdas, local functions, etc.)
_SKIP_PARENT_KINDS = frozenset(
    {
        cx.CursorKind.COMPOUND_STMT,
        cx.CursorKind.LAMBDA_EXPR,
    }
)

_INCLUDE_RE = re.compile(r"^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]", re.MULTILINE)


def _default_extra_args() -> list[str]:
    """Return sensible compiler flags for parsing arbitrary C++ code.

    We try to find GCC's internal headers (stddef.h, etc.) automatically so
    that templates resolve correctly.  If ``clang`` is available on PATH we
    use its ``-print-resource-dir`` instead.
    """
    args = ["-std=c++17", "-x", "c++"]

    try:
        result = subprocess.run(
            ["clang", "-print-resource-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            args += ["-isystem", result.stdout.strip() + "/include"]
            return args
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fall back to GCC headers shipped alongside libclang on Debian/Ubuntu.
    # Search across all installed GCC versions and architectures.
    gcc_root = Path("/usr/lib/gcc")
    if gcc_root.is_dir():
        candidates = sorted(gcc_root.glob("*/*/include"), reverse=True)  # newest first
        for candidate in candidates:
            if (candidate / "stddef.h").exists():
                args += ["-isystem", str(candidate)]
                break

    return args


def _build_signature(cursor: cx.Cursor) -> str:
    """Build a human-readable signature: ``const std::string & ns::foo(int x, bool flag)``"""
    parts: list[str] = []
    parent = cursor.semantic_parent
    while parent and parent.kind != cx.CursorKind.TRANSLATION_UNIT:
        parts.insert(0, parent.spelling)
        parent = parent.semantic_parent
    qualified_name = "::".join(parts + [cursor.spelling]) if parts else cursor.spelling

    param_parts: list[str] = []
    for p in cursor.get_arguments():
        ptype = p.type.spelling
        pname = p.spelling
        param_parts.append(f"{ptype} {pname}" if pname else ptype)

    return_type = cursor.result_type.spelling
    return f"{return_type} {qualified_name}({', '.join(param_parts)})"


def _extract_source(source_lines: list[str], cursor: cx.Cursor) -> str:
    """Slice the exact source text covered by *cursor*'s extent."""
    start = cursor.extent.start
    end = cursor.extent.end

    # extent lines are 1-based
    chunk = source_lines[start.line - 1 : end.line]
    if not chunk:
        return ""

    if len(chunk) == 1:
        return chunk[0][start.column - 1 : end.column]

    lines = [chunk[0][start.column - 1:]] + chunk[1:-1] + [chunk[-1][:end.column]]
    return "".join(lines)


def _collect_functions(
    cursor: cx.Cursor,
    source_lines: list[str],
    file_path: Path,
    module_name: str,
    includes: list[str],
    skip_kinds: frozenset[cx.CursorKind],
) -> list[FunctionInfo]:
    """Recursively walk the AST and collect top-level function definitions."""
    results: list[FunctionInfo] = []

    for child in cursor.get_children():
        # Only process nodes that belong to our file
        if child.location.file is None or Path(child.location.file.name) != file_path:
            continue

        is_def = child.is_definition() or child.kind == cx.CursorKind.FUNCTION_TEMPLATE
        if child.kind in _FUNCTION_KINDS and child.kind not in skip_kinds and is_def:
            # Skip compiler-generated functions (e.g. implicit constructors)
            if child.is_default_method():
                continue

            results.append(
                FunctionInfo(
                    name=child.spelling,
                    signature=_build_signature(child),
                    body=_extract_source(source_lines, child),
                    docstring=child.raw_comment,
                    includes=includes,
                    file_path=file_path,
                    module_name=module_name,
                )
            )

        # Recurse into namespaces and classes, but not into function bodies
        elif child.kind not in _SKIP_PARENT_KINDS:
            results.extend(
                _collect_functions(child, source_lines, file_path, module_name, includes, skip_kinds)
            )

    return results


class CppParser:
    """C++ parser backed by libclang.

    Handles C++11 and later: templates, lambdas, nested namespaces, classes,
    ``auto`` return types, variadic templates, ``[[attributes]]``, etc.

    Parameters
    ----------
    extra_args:
        Additional flags forwarded to the Clang compiler driver (e.g. ``-I``
        paths for project headers).  When *None* a sensible default is derived
        automatically (``-std=c++17`` + GCC / Clang resource headers).
    skip_kinds:
        Set of ``CursorKind`` values to ignore during traversal.  Defaults to
        constructors, destructors, and conversion operators — things that are
        rarely useful to unit-test in isolation.
    """

    def __init__(
        self,
        extra_args: Optional[list[str]] = None,
        cpp_standard: str = "c++11",
        skip_kinds: Optional[frozenset[cx.CursorKind]] = None,
    ) -> None:
        _configure_libclang()
        self._index = cx.Index.create()
        self._extra_args: list[str] = extra_args if extra_args is not None else _default_extra_args()

        if not any(arg.startswith("-std=") for arg in self._extra_args):
            self._extra_args.insert(0, f"-std={cpp_standard}")

        self._skip_kinds: frozenset[cx.CursorKind] = skip_kinds if skip_kinds is not None else frozenset(
            {
                cx.CursorKind.CONSTRUCTOR,
                cx.CursorKind.DESTRUCTOR,
                cx.CursorKind.CONVERSION_FUNCTION,
            }
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, file_path: Path) -> SourceFileInfo:
        """Parse *file_path* and return all function definitions found in it.

        Raises
        ------
        FileNotFoundError
            If *file_path* does not exist on disk.
        RuntimeError
            If libclang reports fatal parse errors.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_path = file_path.resolve()
        source = file_path.read_text(encoding="utf-8")
        source_lines = source.splitlines(keepends=True)
        module_name = file_path.stem
        includes = _INCLUDE_RE.findall(source)

        tu = self._index.parse(str(file_path), args=self._extra_args)
        self._check_diagnostics(tu, file_path)

        functions = _collect_functions(
            tu.cursor, source_lines, file_path, module_name, includes, self._skip_kinds
        )

        return SourceFileInfo(path=file_path, functions=functions)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_diagnostics(tu: cx.TranslationUnit, file_path: Path) -> None:
        """Raise *RuntimeError* if the TU has fatal (error-level) diagnostics."""
        fatal = [
            d
            for d in tu.diagnostics
            if d.severity >= cx.Diagnostic.Error
            # Ignore "file not found" for system headers — we still get a valid AST
            and "file not found" not in d.spelling
        ]
        if fatal:
            messages = "\n".join(f"  {d.spelling}" for d in fatal)
            raise RuntimeError(
                f"libclang reported errors while parsing {file_path}:\n{messages}"
            )
