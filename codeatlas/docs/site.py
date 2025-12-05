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
        
        # Create material/overrides directory for theme customizations
        material_overrides = self.repo_path / "material" / "overrides"
        material_overrides.mkdir(parents=True, exist_ok=True)

        code_docs = list(generated_docs or self._discover_docs())
        config = self._load_config()
        config["site_name"] = f"{self.repo_info.repo_name} Documentation"
        config["docs_dir"] = "docs"
        
        # Build comprehensive Material theme configuration
        theme_config = {
            "name": "material",
            "custom_dir": "material/overrides",
            "features": [
                "content.action.edit",
                "content.action.view",
                "content.code.annotate",
                "content.code.copy",
                "content.tooltips",
                "navigation.footer",
                "navigation.indexes",
                "navigation.sections",
                "navigation.tabs",
                "navigation.top",
                "navigation.tracking",
                "search.highlight",
                "search.share",
                "search.suggest",
                "toc.follow",
            ],
            "palette": [
                {
                    "media": "(prefers-color-scheme)",
                    "toggle": {
                        "icon": "material/link",
                        "name": "Switch to light mode",
                    },
                },
                {
                    "media": "(prefers-color-scheme: light)",
                    "scheme": "default",
                    "primary": "indigo",
                    "accent": "indigo",
                    "toggle": {
                        "icon": "material/toggle-switch",
                        "name": "Switch to dark mode",
                    },
                },
                {
                    "media": "(prefers-color-scheme: dark)",
                    "scheme": "slate",
                    "primary": "black",
                    "accent": "indigo",
                    "toggle": {
                        "icon": "material/toggle-switch-off",
                        "name": "Switch to system preference",
                    },
                },
            ],
            "font": {
                "text": "Roboto",
                "code": "Roboto Mono",
            },
        }
        
        # Add favicon if it exists
        favicon_path = self.repo_path / "docs" / "assets" / "favicon.png"
        if favicon_path.exists():
            theme_config["favicon"] = "assets/favicon.png"
        
        # Add logo if provided in config or if default exists
        # Check for logo in existing config first, then check common locations
        existing_theme = config.get("theme", {})
        if isinstance(existing_theme, dict) and "logo" in existing_theme:
            theme_config["logo"] = existing_theme["logo"]
        else:
            # Check common logo locations
            for logo_path in [
                self.repo_path / "docs" / "assets" / "logo.png",
                self.repo_path / "docs" / "assets" / "logo.svg",
                self.repo_path / "logo.png",
                self.repo_path / "logo.svg",
            ]:
                if logo_path.exists():
                    if logo_path.parent == self.repo_path / "docs" / "assets":
                        theme_config["logo"] = f"assets/{logo_path.name}"
                    else:
                        theme_config["logo"] = logo_path.name
                    break
        
        config["theme"] = theme_config

        # Ensure Mermaid support is enabled
        if "markdown_extensions" not in config:
            config["markdown_extensions"] = []
        extensions = config["markdown_extensions"]
        # Check if pymdownx.superfences is already configured
        superfences_idx = None
        for i, ext in enumerate(extensions):
            if isinstance(ext, dict) and "pymdownx.superfences" in ext:
                superfences_idx = i
                break
        if superfences_idx is None:
            # Add pymdownx.superfences with Mermaid support
            extensions.append({
                "pymdownx.superfences": {
                    "custom_fences": [
                        {
                            "name": "mermaid",
                            "class": "mermaid",
                            "format": "!!python/name:pymdownx.superfences.fence_code_format"
                        }
                    ]
                }
            })
        else:
            # Update existing superfences config
            superfences = extensions[superfences_idx]["pymdownx.superfences"]
            if "custom_fences" not in superfences:
                superfences["custom_fences"] = []
            # Check if mermaid is already in custom_fences
            mermaid_exists = any(
                fence.get("name") == "mermaid" for fence in superfences["custom_fences"]
            )
            if not mermaid_exists:
                superfences["custom_fences"].append({
                    "name": "mermaid",
                    "class": "mermaid",
                    "format": "!!python/name:pymdownx.superfences.fence_code_format"
                })

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
            # Remove .md extension from the end for MkDocs navigation
            # (MkDocs adds it automatically, and including it can cause routing issues)
            if rel.endswith(".md"):
                nav_path = rel[:-3]  # Remove last 3 characters (.md)
            else:
                nav_path = rel
            # Create a readable label from the file path
            label = rel.removeprefix("code/")
            if label.endswith(".md"):
                label = label[:-3]
            entries.append({label: nav_path})
        return entries

    def _load_config(self) -> dict:
        if not self.mkdocs_file.exists():
            return {}
        return yaml.safe_load(self.mkdocs_file.read_text(encoding="utf-8")) or {}
