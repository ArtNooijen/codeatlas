"""MkDocs site management."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from ..ingest.git_repo import RepoInfo


class MkDocsSite:
    """Ensures MkDocs config + docs structure land inside the forked repo."""

    def __init__(self, repo_info: RepoInfo) -> None:
        self.repo_info = repo_info
        self.repo_path = repo_info.path
        self.docs_root = self.repo_path / "docs"
        self.mkdocs_file = self.repo_path / "mkdocs.yml"

    def ensure_site_structure(self, generated_docs: Iterable[Path] | None = None) -> None:
        self.docs_root.mkdir(parents=True, exist_ok=True)
        index_path = self.docs_root / "index.md"
        if not index_path.exists():
            index_path.write_text("# CodeAtlas Documentation\n", encoding="utf-8")

        code_docs = list(generated_docs or self._discover_docs())
        config = self._load_config()
        config["site_name"] = f"{self.repo_info.repo_name} Documentation"
        config["docs_dir"] = "docs"
        config["theme"] = {"name": "material"}

        nav = [{"Home": "index.md"}]
        code_nav = self._build_code_nav(code_docs)
        if code_nav:
            nav.append({"Code Reference": code_nav})
        config["nav"] = nav

        self.mkdocs_file.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    def _discover_docs(self) -> list[Path]:
        code_root = self.docs_root / "code"
        return list(code_root.rglob("*.md")) if code_root.exists() else []

    def _build_code_nav(self, doc_paths: list[Path]) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for doc in sorted(doc_paths):
            rel = doc.relative_to(self.docs_root).as_posix()
            label = rel.removeprefix("code/").replace(".md", "")
            entries.append({label: rel})
        return entries

    def _load_config(self) -> dict:
        if not self.mkdocs_file.exists():
            return {}
        return yaml.safe_load(self.mkdocs_file.read_text(encoding="utf-8")) or {}
