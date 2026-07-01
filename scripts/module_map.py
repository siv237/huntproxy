#!/usr/bin/env python3
"""Generate MODULES.md — live map of the hunt/ package.

Scans every Python module, extracts:
  - line count
  - public classes and functions (not starting with _)
  - imports from other hunt.* modules (coupling map)

Output: MODULES.md in the project root.

Run:
    python scripts/module_map.py
    # or via test.sh --map
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUNT = ROOT / "hunt"
OUTPUT = ROOT / "MODULES.md"


def _line_count(path: Path) -> int:
    """Count non-blank, non-comment lines."""
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            n += 1
    return n


def _public_defs(tree: ast.AST) -> list[tuple[str, str]]:
    """Return [(name, type)] for public classes and functions."""
    out = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                kind = "class" if isinstance(node, ast.ClassDef) else "async" if isinstance(node, ast.AsyncFunctionDef) else "def"
                out.append((node.name, kind))
    return out


def _hunt_imports(tree: ast.AST) -> list[str]:
    """Return sorted list of hunt.* modules imported."""
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("hunt"):
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("hunt"):
                    mods.add(alias.name)
    return sorted(mods)


def _group(files: list[Path]) -> dict[str, list[Path]]:
    """Group files by directory: 'hunt/', 'hunt/handlers/', etc."""
    groups: dict[str, list[Path]] = {}
    for f in files:
        rel = f.relative_to(HUNT.parent)
        key = str(rel.parent) + "/"
        groups.setdefault(key, []).append(f)
    for k in groups:
        groups[k].sort(key=lambda p: p.name)
    return dict(sorted(groups.items()))


def _file_docstring(path: Path, tree: ast.AST) -> str:
    """Extract first line of module docstring, if any."""
    if tree.body and isinstance(tree.body[0], ast.Expr):
        e = tree.body[0].value
        if isinstance(e, ast.Constant) and isinstance(e.value, str):
            first = e.value.strip().split("\n")[0]
            return first[:80]
    return ""


def generate():
    files = sorted(HUNT.rglob("*.py"))
    files = [f for f in files if "__pycache__" not in str(f)]

    # Parse all modules
    modules = []
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError:
            continue
        rel = f.relative_to(HUNT.parent)
        modules.append({
            "path": str(rel),
            "file": f,
            "lines": _line_count(f),
            "defs": _public_defs(tree),
            "imports": _hunt_imports(tree),
            "doc": _file_docstring(f, tree),
        })

    groups = _group([m["file"] for m in modules])

    lines = []
    lines.append("# Карта модулей\n")
    lines.append("Автоматически сгенерировано из исходного кода. Не редактировать руками.\n")
    lines.append(f"Запуск: `python scripts/module_map.py`\n")
    lines.append(f"Всего модулей: {len(modules)} | Всего строк: {sum(m['lines'] for m in modules)}\n")
    lines.append("---\n")

    # Summary table
    lines.append("## Сводка\n")
    lines.append("| Модуль | Строк | Публичные классы/функции | Импортирует из hunt |\n")
    lines.append("|--------|-------|--------------------------|---------------------|\n")
    for m in sorted(modules, key=lambda x: x["path"]):
        defs = ", ".join(f"`{n}`" for n, _ in m["defs"][:5])
        if len(m["defs"]) > 5:
            defs += f" +{len(m['defs']) - 5}"
        imports = ", ".join(m["imports"][:4])
        if len(m["imports"]) > 4:
            imports += f" +{len(m['imports']) - 4}"
        lines.append(f"| `{m['path']}` | {m['lines']} | {defs or '—'} | {imports or '—'} |\n")
    lines.append("\n---\n")

    # Detailed by group
    for group, group_files in groups.items():
        lines.append(f"## {group}\n")
        for f in group_files:
            m = next(x for x in modules if x["file"] == f)
            lines.append(f"### `{m['path']}` ({m['lines']} строк)\n")
            if m["doc"]:
                lines.append(f"*{m['doc']}*\n")
            if m["defs"]:
                lines.append("**Публичные:**\n")
                for name, kind in m["defs"]:
                    lines.append(f"- `{name}` ({kind})\n")
                lines.append("\n")
            if m["imports"]:
                lines.append("**Зависимости:** " + ", ".join(f"`{x}`" for x in m["imports"]) + "\n")
            lines.append("\n")

    # Coupling: who imports whom
    lines.append("---\n")
    lines.append("## Связанность (кто импортирует кого)\n")
    lines.append("| Модуль | Импортирует |\n")
    lines.append("|--------|-------------|\n")
    for m in sorted(modules, key=lambda x: x["path"]):
        if m["imports"]:
            lines.append(f"| `{m['path']}` | {', '.join('`' + x + '`' for x in m['imports'])} |\n")
    lines.append("\n")

    OUTPUT.write_text("".join(lines), encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)} — {len(modules)} modules, {sum(m['lines'] for m in modules)} lines")


if __name__ == "__main__":
    generate()
