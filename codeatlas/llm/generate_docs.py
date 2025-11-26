"""LLM-powered documentation generation."""
from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml
from ollama import Client
from rich.console import Console
from rich.progress import Progress

from ..ingest.git_repo import FileRecord, RepoInfo

console = Console()

DEFAULT_DIAGRAM_PROMPT = """
You are an expert at reading source code and drawing Mermaid diagrams. Given
the {language} file at path {path}, analyse the functions/classes and show how
they call each other. Respond with Mermaid content only, no prose, for example:

graph TD
    A --> B

Use concise node names (function or method identifiers) and directional edges.
Source code:
{content}
"""


@dataclass
class ModelConfig:
    name: str
    instance: str
    default: bool = False


class DocumentationGenerator:
    """Generate per-file Markdown using Ollama."""

    def __init__(
        self,
        config_path: str,
        models: list[str] | None = None,
        max_chars: int = 6000,
        diagram_model: str | None = None,
        diagram_prompt: str | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.instances = self.config.get("ollama_instances", {})
        self.model_entries = [ModelConfig(**m) for m in self.config.get("models", [])]
        if not self.model_entries:
            raise ValueError("models.yaml must define at least one model entry.")
        self.max_chars = max_chars
        self.active_models = models or self._default_models()
        self.clients = {name: self._client_for(name) for name in self.active_models}
        self.diagram_model_name = diagram_model or self.config.get("diagram_default_model")
        self.diagram_prompt_template = (
            diagram_prompt or self.config.get("diagram_prompt") or DEFAULT_DIAGRAM_PROMPT
        )
        self.diagram_client = None
        if self.diagram_model_name:
            try:
                self.diagram_client = self._client_for(self.diagram_model_name)
            except ValueError as exc:
                console.print(f"[yellow]Diagram model error: {exc}")
                self.diagram_client = None

    def generate(self, repo_info: RepoInfo) -> list[Path]:
        docs_root = repo_info.path / "docs"
        code_root = docs_root / "code"
        code_root.mkdir(parents=True, exist_ok=True)
        generated: list[Path] = []
        files = [record for record in repo_info.files if self._should_process(record)]
        if not files:
            console.print("[yellow]No eligible files found for LLM documentation.")
            return generated

        with Progress(transient=True) as progress:
            task = progress.add_task("Generating docs", total=len(files))
            for record in files:
                file_path = repo_info.path / record.rel_path
                console.log(f"[cyan]Processing {record.rel_path}")
                try:
                    snippet = self._read_snippet(file_path)
                except UnicodeDecodeError:
                    console.log(f"[yellow]Skipping {record.rel_path}: non-text or invalid encoding")
                    progress.advance(task)
                    continue
                imports = self._extract_imports(record, snippet)
                prompt = self._build_prompt(repo_info, record, snippet, imports)
                sections = []
                for model_name, client in self.clients.items():
                    try:
                        response = client.generate(model=model_name, prompt=prompt, options={"temperature": 0.15})
                        text = response.get("response", "").strip()
                        if text:
                            sections.append((model_name, text))
                    except Exception as exc:  # pragma: no cover
                        console.print(f"[red]Model {model_name} failed on {record.rel_path}: {exc}")
                if not sections:
                    console.log(f"[yellow]No model output captured for {record.rel_path}")
                    progress.advance(task)
                    continue
                diagram = self._generate_diagram(record, snippet)
                doc_path = self._doc_path(docs_root, record)
                doc_path.parent.mkdir(parents=True, exist_ok=True)
                markdown = self._render_markdown(record, sections, imports, diagram)
                doc_path.write_text(markdown, encoding="utf-8")
                generated.append(doc_path)
                console.log(f"[green]Wrote {doc_path.relative_to(repo_info.path)}")
                progress.advance(task)

        self._write_index(docs_root, files)
        console.log(f"[green]Generated {len(generated)} documentation files")
        return generated

    def _load_config(self) -> dict:
        return yaml.safe_load(self.config_path.read_text(encoding="utf-8"))

    def _default_models(self) -> list[str]:
        for model in self.model_entries:
            if model.default:
                return [model.name]
        return [self.model_entries[0].name]

    def _client_for(self, model_name: str) -> Client:
        model_cfg = next((m for m in self.model_entries if m.name == model_name), None)
        if not model_cfg:
            raise ValueError(f"Unknown model {model_name}")
        instance_cfg = self.instances.get(model_cfg.instance)
        if not instance_cfg:
            raise ValueError(f"Model {model_name} references unknown instance {model_cfg.instance}")
        host = instance_cfg.get("host", "localhost")
        port = instance_cfg.get("port", 11434)
        base_url = f"http://{host}:{port}"
        timeout = instance_cfg.get("timeout", 30)
        return Client(host=base_url, timeout=timeout)

    def _should_process(self, record: FileRecord) -> bool:
        return record.language in {"python", "javascript", "typescript", "go", "rust", "text"}

    def _read_snippet(self, file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8")[: self.max_chars]

    def _build_prompt(
        self,
        repo_info: RepoInfo,
        record: FileRecord,
        content: str,
        imports: list[str],
    ) -> str:
        imports_hint = "\n".join(imports) or "None"
        prompt = f"""
        You are CodeAtlas, an expert codebase documentarian. Summarize the file {record.rel_path}
        from repository {repo_info.repo_name}.

        Produce:
        1. Purpose summary
        2. Key functions/classes and their collaboration
        3. External dependencies or APIs used
        4. Extension ideas, pitfalls, or TODOs

        Imports detected:
        {imports_hint}

        File content:
        {content}
        """
        return textwrap.dedent(prompt)

    def _extract_imports(self, record: FileRecord, content: str) -> list[str]:
        if record.language != "python":
            return []
        imports: list[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                imports.append(stripped)
            if len(imports) >= 20:
                break
        return imports

    def _render_markdown(
        self,
        record: FileRecord,
        sections: Iterable[tuple[str, str]],
        imports: list[str],
        diagram: str | None,
    ) -> str:
        header = f"# {record.rel_path}\n\n> Language: {record.language} | Size: {record.size_bytes} bytes\n\n"
        body = "\n\n".join(f"## Model {model}\n\n{response}" for model, response in sections)
        imports_block = "\n".join(f"- {imp}" for imp in imports) if imports else "None detected."
        diagram_block = ""
        if diagram:
            cleaned = diagram.strip()
            if cleaned.startswith("```"):
                diagram_block = f"\n\n## Function Diagram\n\n{cleaned}\n"
            else:
                diagram_block = f"\n\n## Function Diagram\n\n```mermaid\n{cleaned}\n```\n"
        return header + body + "\n\n## Detected Imports\n\n" + imports_block + "\n" + diagram_block

    def _doc_path(self, docs_root: Path, record: FileRecord) -> Path:
        rel_path = Path("code") / Path(record.rel_path)
        suffix = Path(record.rel_path).suffix
        final_suffix = f"{suffix}.md" if suffix else ".md"
        return (docs_root / rel_path).with_suffix(final_suffix)

    def _doc_link(self, record: FileRecord) -> str:
        rel_path = Path("code") / Path(record.rel_path)
        suffix = Path(record.rel_path).suffix
        final_suffix = f"{suffix}.md" if suffix else ".md"
        return str(rel_path.with_suffix(final_suffix)).replace("\\", "/")

    def _write_index(self, docs_root: Path, files: list[FileRecord]) -> None:
        index_path = docs_root / "index.md"
        lines = ["# CodeAtlas Documentation", "", "Generated pages:", ""]
        for record in sorted(files, key=lambda f: f.rel_path):
            lines.append(f"- [{record.rel_path}]({self._doc_link(record)})")
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _generate_diagram(self, record: FileRecord, content: str) -> str | None:
        if not self.diagram_client or not self.diagram_model_name:
            return None
        prompt = self._build_diagram_prompt(record, content)
        try:
            response = self.diagram_client.generate(
                model=self.diagram_model_name,
                prompt=prompt,
                options={"temperature": 0},
            )
        except Exception as exc:  # pragma: no cover
            console.print(f"[yellow]Diagram generation failed for {record.rel_path}: {exc}")
            return None
        diagram = response.get("response", "").strip()
        return diagram or None

    def _build_diagram_prompt(self, record: FileRecord, content: str) -> str:
        return self.diagram_prompt_template.format(
            path=record.rel_path,
            language=record.language,
            content=content,
        )
