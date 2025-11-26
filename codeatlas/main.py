"""Command-line entry for CodeAtlas."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .ingest.git_repo import RepoManager
from .llm.generate_docs import DocumentationGenerator
from .docs.site import MkDocsSite
from .publish.git_ops import Publisher


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Automate repo documentation with MkDocs Material")
    parser.add_argument("--repo", required=True, help="Source repository HTTPS URL")
    parser.add_argument("--fork-owner", required=True, help="Fork owner/org for the mirrored repo")
    parser.add_argument("--workdir", default=str(Path.cwd() / "workspaces"), help="Working directory for clones")
    parser.add_argument("--config", default=str(Path(__file__).parent / "config" / "models.yaml"), help="Path to model config file")
    parser.add_argument("--branch", default="main", help="Branch to target in the fork")
    parser.add_argument(
        "--token",
        default=None,
        help="Explicit GitHub token for forking/pushing (falls back to env var)",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable to read the GitHub token from when --token is absent",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated list of Ollama model names to run (defaults to config's primary model)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=6000,
        help="Maximum number of characters from each file to send to the model",
    )
    parser.add_argument("--push", action="store_true", help="Push commits back to the fork when finished")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_data = config_data or {}
    git_config = config_data.get("git", {}) or {}

    repo_mgr = RepoManager(
        repo_url=args.repo,
        fork_owner=args.fork_owner,
        workdir=Path(args.workdir),
        token=args.token,
        token_env=args.token_env,
    )
    repo_info = repo_mgr.prepare_repo(branch=args.branch)

    model_list = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else None
    doc_gen = DocumentationGenerator(config_path=str(config_path), models=model_list, max_chars=args.max_chars)
    generated_docs = doc_gen.generate(repo_info)

    site = MkDocsSite(repo_info)
    site.ensure_site_structure(generated_docs)

    publisher = Publisher(
        repo_info,
        author_name=git_config.get("author_name"),
        author_email=git_config.get("author_email"),
    )
    publisher.commit_and_optionally_push(push=args.push)


if __name__ == "__main__":
    cli()
