"""Extract file dependencies to build dependency graph for context."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict

from rich.console import Console

from ..ingest.git_repo import FileRecord, RepoInfo

console = Console()


class DependencyAnalyzer:
    """Extract import/require statements to build file dependency graph."""

    def __init__(self, repo_info: RepoInfo) -> None:
        self.repo_info = repo_info
        self.repo_path = repo_info.path
        # Maps file path -> list of files it depends on
        self.dependencies: DefaultDict[str, list[str]] = defaultdict(list)
        # Maps file path -> list of files that depend on it
        self.dependents: DefaultDict[str, list[str]] = defaultdict(list)

    def analyze(self) -> None:
        """Build dependency graph by analyzing all source files."""
        console.print("[cyan]Analyzing file dependencies...")
        
        # Process all files to extract dependencies
        for record in self.repo_info.files:
            if not self._should_analyze(record):
                continue
            
            file_path = self.repo_path / record.rel_path
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            
            deps = self._extract_dependencies(record, content)
            if deps:
                self.dependencies[record.rel_path] = deps
                # Build reverse mapping (dependents)
                for dep in deps:
                    self.dependents[dep].append(record.rel_path)
        
        console.print(f"[green]Analyzed dependencies for {len(self.dependencies)} files")

    def get_file_dependencies(self, file_path: str) -> list[str]:
        """Get list of files that the given file depends on."""
        return self.dependencies.get(file_path, [])

    def get_file_dependents(self, file_path: str) -> list[str]:
        """Get list of files that depend on the given file."""
        return self.dependents.get(file_path, [])

    def _should_analyze(self, record: FileRecord) -> bool:
        """Check if file should be analyzed for dependencies."""
        return record.language in {"python", "javascript", "typescript", "rust", "go"}

    def _extract_dependencies(self, record: FileRecord, content: str) -> list[str]:
        """Extract dependencies based on file language."""
        if record.language == "python":
            return self._extract_python_deps(record, content)
        elif record.language in {"javascript", "typescript"}:
            return self._extract_js_deps(record, content)
        elif record.language == "rust":
            return self._extract_rust_deps(record, content)
        elif record.language == "go":
            return self._extract_go_deps(record, content)
        return []

    def _extract_python_deps(self, record: FileRecord, content: str) -> list[str]:
        """Extract Python import statements and resolve to file paths."""
        deps: list[str] = []
        file_dir = Path(record.rel_path).parent
        
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Handle: import module
            match = re.match(r"^import\s+(\w+)", line)
            if match:
                module = match.group(1)
                dep_path = self._resolve_python_module(file_dir, module)
                if dep_path:
                    deps.append(dep_path)
                continue
            
            # Handle: from module import ...
            match = re.match(r"^from\s+([\w.]+)\s+import", line)
            if match:
                module = match.group(1)
                dep_path = self._resolve_python_module(file_dir, module)
                if dep_path:
                    deps.append(dep_path)
                continue
            
            # Handle: from .module import ... (relative imports)
            match = re.match(r"^from\s+\.+([\w.]*)\s+import", line)
            if match:
                rel_module = match.group(1)
                dep_path = self._resolve_python_relative(file_dir, rel_module)
                if dep_path:
                    deps.append(dep_path)
        
        return list(set(deps))  # Remove duplicates

    def _extract_js_deps(self, record: FileRecord, content: str) -> list[str]:
        """Extract JavaScript/TypeScript import/require statements."""
        deps: list[str] = []
        file_dir = Path(record.rel_path).parent
        
        # Match ES6 imports: import ... from 'module'
        pattern = r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]"
        for match in re.finditer(pattern, content):
            module = match.group(1)
            dep_path = self._resolve_js_module(file_dir, module)
            if dep_path:
                deps.append(dep_path)
        
        # Match require: require('module') or require("module")
        pattern = r"require\s*\(['\"]([^'\"]+)['\"]\)"
        for match in re.finditer(pattern, content):
            module = match.group(1)
            dep_path = self._resolve_js_module(file_dir, module)
            if dep_path:
                deps.append(dep_path)
        
        return list(set(deps))

    def _extract_rust_deps(self, record: FileRecord, content: str) -> list[str]:
        """Extract Rust use statements and mod declarations."""
        deps: list[str] = []
        file_dir = Path(record.rel_path).parent
        
        # Match: use crate::module or use super::module
        pattern = r"use\s+(?:crate|super|self)::([\w:]+)"
        for match in re.finditer(pattern, content):
            module = match.group(1).replace("::", "/")
            dep_path = self._resolve_rust_module(file_dir, module)
            if dep_path:
                deps.append(dep_path)
        
        # Match: mod module_name;
        pattern = r"mod\s+(\w+)\s*;"
        for match in re.finditer(pattern, content):
            module = match.group(1)
            dep_path = self._resolve_rust_module(file_dir, module)
            if dep_path:
                deps.append(dep_path)
        
        return list(set(deps))

    def _extract_go_deps(self, record: FileRecord, content: str) -> list[str]:
        """Extract Go import statements."""
        deps: list[str] = []
        file_dir = Path(record.rel_path).parent
        
        # Match: import "package" or import ( "package1" "package2" )
        # Single import
        pattern = r'import\s+["\']([^"\']+)["\']'
        for match in re.finditer(pattern, content):
            package = match.group(1)
            dep_path = self._resolve_go_package(file_dir, package)
            if dep_path:
                deps.append(dep_path)
        
        # Multi-line import block
        in_import_block = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ("):
                in_import_block = True
                continue
            if in_import_block:
                if stripped == ")":
                    in_import_block = False
                    continue
                match = re.search(r'["\']([^"\']+)["\']', stripped)
                if match:
                    package = match.group(1)
                    dep_path = self._resolve_go_package(file_dir, package)
                    if dep_path:
                        deps.append(dep_path)
        
        return list(set(deps))

    def _resolve_python_module(self, file_dir: Path, module: str) -> str | None:
        """Resolve Python module name to file path relative to repo root."""
        # Try relative to current file directory first
        module_parts = module.split(".")
        
        # Try as relative path
        potential_path = file_dir / "/".join(module_parts)
        for ext in ["", ".py"]:
            test_path = potential_path.with_suffix(ext) if ext else potential_path
            full_path = self.repo_path / test_path
            if full_path.exists() and full_path.is_file():
                return str(test_path)
        
        # Try with __init__.py
        init_path = potential_path / "__init__.py"
        full_init_path = self.repo_path / init_path
        if full_init_path.exists():
            return str(init_path)
        
        # Try from repo root
        root_path = Path("/".join(module_parts))
        for ext in ["", ".py"]:
            test_path = root_path.with_suffix(ext) if ext else root_path
            full_path = self.repo_path / test_path
            if full_path.exists() and full_path.is_file():
                return str(test_path)
        
        return None

    def _resolve_python_relative(self, file_dir: Path, rel_module: str) -> str | None:
        """Resolve Python relative import (from .module or from ..module)."""
        if not rel_module:
            # from . import something -> look for __init__.py in same dir
            init_path = file_dir / "__init__.py"
            if (self.repo_path / init_path).exists():
                return str(init_path)
            return None
        
        module_parts = rel_module.split(".")
        potential_path = file_dir / "/".join(module_parts)
        
        for ext in ["", ".py"]:
            test_path = potential_path.with_suffix(ext) if ext else potential_path
            full_path = self.repo_path / test_path
            if full_path.exists() and full_path.is_file():
                return str(test_path)
        
        return None

    def _resolve_js_module(self, file_dir: Path, module: str) -> str | None:
        """Resolve JavaScript/TypeScript module to file path."""
        # Skip node_modules and external packages (non-relative imports)
        if not module.startswith(".") and not module.startswith("/"):
            return None
        
        # Relative import
        if module.startswith("."):
            try:
                resolved = (file_dir / module).resolve()
                # Check if resolved path is within repo
                try:
                    potential_path = resolved.relative_to(self.repo_path)
                except ValueError:
                    # Path goes outside repo, skip it
                    return None
            except Exception:
                return None
        else:
            # Absolute path (unlikely but handle it)
            potential_path = Path(module.lstrip("/"))
        
        # Try common extensions
        for ext in ["", ".js", ".ts", ".jsx", ".tsx", ".vue"]:
            test_path = potential_path.with_suffix(ext) if ext else potential_path
            full_path = self.repo_path / test_path
            if full_path.exists() and full_path.is_file():
                return str(test_path)
        
        return None

    def _resolve_rust_module(self, file_dir: Path, module: str) -> str | None:
        """Resolve Rust module to file path."""
        # Try as .rs file
        potential_path = file_dir / f"{module}.rs"
        full_path = self.repo_path / potential_path
        if full_path.exists():
            return str(potential_path)
        
        # Try as mod.rs in directory
        mod_path = file_dir / module / "mod.rs"
        full_mod_path = self.repo_path / mod_path
        if full_mod_path.exists():
            return str(mod_path)
        
        return None

    def _resolve_go_package(self, file_dir: Path, package: str) -> str | None:
        """Resolve Go package to file path."""
        # Skip standard library and external packages
        if not package.startswith(".") and "/" not in package:
            return None
        
        # Relative imports
        if package.startswith("."):
            potential_path = (file_dir / package).resolve().relative_to(self.repo_path)
            full_path = self.repo_path / potential_path
            if full_path.exists() and full_path.is_file():
                return str(potential_path)
        
        return None

