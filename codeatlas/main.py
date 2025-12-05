"""Command-line entry for CodeAtlas."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml

from rich.console import Console

from .deps.analyzer import DependencyAnalyzer
from .docs.site import MkDocsSite
from .ingest.git_repo import RepoManager
from .llm.generate_docs import DocumentationGenerator
from .publish.git_ops import Publisher

console = Console()
from .review.review_manager import ReviewManager


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Automate repo documentation with MkDocs Material")
    parser.add_argument("--repo", required=False, help="Source repository HTTPS URL")
    parser.add_argument("--fork-owner", required=False, help="Fork owner/org for the mirrored repo")
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
        "--diagram-model",
        default=None,
        help="Model name for Mermaid diagrams (defaults to config value)",
    )
    parser.add_argument(
        "--diagram-prompt",
        default=None,
        help="Override prompt template used for diagram generation",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=6000,
        help="Maximum number of characters from each file to send to the model",
    )
    parser.add_argument("--push", action="store_true", help="Push commits back to the fork when finished")
    parser.add_argument(
        "--github-actions",
        action="store_true",
        help="Run in GitHub Actions mode (auto-detected if GITHUB_ACTIONS env var is set)",
    )
    parser.add_argument(
        "--create-review-pr",
        action="store_true",
        help="Create a PR for documentation review instead of committing directly",
    )
    args = parser.parse_args(argv)

    # Load config path before using it
    config_path = Path(args.config)

    # Auto-detect GitHub Actions mode
    is_github_actions = args.github_actions or os.getenv("GITHUB_ACTIONS") == "true"

    if is_github_actions:
        github_actions_mode(args, config_path)
    else:
        # Validate required args for CLI mode
        if not args.repo or not args.fork_owner:
            parser.error("--repo and --fork-owner are required in CLI mode")
        cli_mode(args, config_path)


def cli_mode(args: argparse.Namespace, config_path: Path) -> None:
    """Run in standard CLI mode."""
    from .review.review_manager import ReviewManager
    
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

    # Run dependency analysis
    analyzer = DependencyAnalyzer(repo_info)
    analyzer.analyze()
    repo_info.dependency_analyzer = analyzer

    model_list = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else None
    doc_gen = DocumentationGenerator(
        config_path=str(config_path),
        models=model_list,
        max_chars=args.max_chars,
        diagram_model=args.diagram_model,
        diagram_prompt=args.diagram_prompt,
    )
    generated_docs = doc_gen.generate(repo_info)

    site = MkDocsSite(repo_info)
    site.ensure_site_structure(generated_docs)

    publisher = Publisher(
        repo_info,
        author_name=git_config.get("author_name"),
        author_email=git_config.get("author_email"),
    )

    # Create review PR or commit directly
    if args.create_review_pr:
        review_mgr = ReviewManager(repo_info)
        review_branch = review_mgr.create_review_branch()
        documented_files = [str(doc.relative_to(repo_info.path)) for doc in generated_docs]
        publisher.commit_and_optionally_push(
            push=False, commit_message="docs: auto-generated documentation"
        )
        review_mgr.push_review_branch(review_branch)
        pr_url = review_mgr.create_review_pr(review_branch, documented_files=documented_files)
        if pr_url:
            console.print(f"[green]Review PR created: {pr_url}")
        else:
            console.print("[yellow]Failed to create PR, but branch was created and committed")
    else:
        publisher.commit_and_optionally_push(push=args.push)
        publisher.build_mkdocs_site()


def github_actions_mode(args: argparse.Namespace, config_path: Path) -> None:
    """Run in GitHub Actions mode."""
    from rich.console import Console

    console = Console()

    # Parse GitHub event context
    event_data = parse_github_event()
    if not event_data:
        console.print("[red]Failed to parse GitHub event data")
        return

    event_name = os.getenv("GITHUB_EVENT_NAME", "push")
    repository = os.getenv("GITHUB_REPOSITORY", "")
    ref = os.getenv("GITHUB_REF", "refs/heads/main")
    token = args.token or os.getenv("GITHUB_TOKEN")

    if not repository:
        console.print("[red]GITHUB_REPOSITORY not set")
        return

    owner, repo_name = repository.split("/", 1)
    branch = ref.replace("refs/heads/", "").replace("refs/pull/", "").split("/")[0]

    repo_url = f"https://github.com/{repository}"
    # In GitHub Actions, we're already in the workspace (checked out by actions/checkout)
    github_workspace = Path(os.getenv("GITHUB_WORKSPACE", "/tmp/codeatlas"))

    console.print(f"[cyan]GitHub Actions mode: {event_name} on {repository}@{branch}")

    # Create a minimal RepoManager just for utility methods
    repo_mgr = RepoManager(
        repo_url=repo_url,
        fork_owner=owner,
        workdir=github_workspace.parent,  # Not used, but required
        token=token,
        token_env="GITHUB_TOKEN",
    )

    # Check for existing docs
    has_docs = repo_mgr.has_existing_docs(github_workspace)
    repo_path = github_workspace

    if has_docs:
        # Get changed files
        if event_name == "pull_request":
            base_ref = event_data.get("pull_request", {}).get("base", {}).get("ref", branch)
            head_ref = event_data.get("pull_request", {}).get("head", {}).get("sha")
            if head_ref:
                changed_files = repo_mgr.get_changed_files(
                    repo_path, base_ref=f"refs/heads/{base_ref}", head_ref=head_ref
                )
        else:  # push
            changed_files = repo_mgr.get_changed_files(repo_path)

        if changed_files:
            filter_changed = True
            console.print(f"[cyan]Found {len(changed_files)} changed files")

    # Prepare repo with filtering
    # If we're using the existing workspace, we need to create RepoInfo manually
    if github_workspace.exists() and (github_workspace / ".git").exists():
        from .ingest.git_repo import RepoInfo
        files = list(repo_mgr._collect_files(github_workspace))
        if filter_changed and changed_files:
            changed_set = set(changed_files)
            files = [f for f in files if f.rel_path in changed_set]
        repo_info = RepoInfo(
            source_url=repo_url,
            fork_owner=owner,
            repo_name=repo_name,
            path=github_workspace,
            branch=branch,
            fork_url=repo_url,
            files=files,
            token=token,
        )
    else:
        repo_info = repo_mgr.prepare_repo(
            branch=branch, changed_files=changed_files, filter_changed=filter_changed
        )

    # Run dependency analysis
    analyzer = DependencyAnalyzer(repo_info)
    analyzer.analyze()
    repo_info.dependency_analyzer = analyzer

    config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config_data = config_data or {}
    git_config = config_data.get("git", {}) or {}

    model_list = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else None
    doc_gen = DocumentationGenerator(
        config_path=str(config_path),
        models=model_list,
        max_chars=args.max_chars,
        diagram_model=args.diagram_model,
        diagram_prompt=args.diagram_prompt,
    )
    generated_docs = doc_gen.generate(repo_info)

    if not generated_docs:
        console.print("[yellow]No documentation generated; nothing to commit.")
        return

    site = MkDocsSite(repo_info)
    site.ensure_site_structure(generated_docs)

    publisher = Publisher(
        repo_info,
        author_name=git_config.get("author_name"),
        author_email=git_config.get("author_email"),
    )

    # Create review PR or commit directly
    if args.create_review_pr or os.getenv("CODEATLAS_CREATE_REVIEW_PR", "false").lower() == "true":
        review_mgr = ReviewManager(repo_info)
        branch_suffix = None
        if event_name == "pull_request":
            pr_number = event_data.get("pull_request", {}).get("number")
            if pr_number:
                branch_suffix = f"pr-{pr_number}"

        review_branch = review_mgr.create_review_branch(branch_suffix=branch_suffix)
        documented_files = [str(doc.relative_to(repo_info.path)) for doc in generated_docs]
        publisher.commit_and_optionally_push(
            push=False, commit_message="docs: auto-generated documentation"
        )
        review_mgr.push_review_branch(review_branch)
        review_mgr.create_review_pr(review_branch, documented_files=documented_files)
    else:
        publisher.commit_and_optionally_push(
            push=True, commit_message="docs: auto-generated documentation"
        )
        publisher.build_mkdocs_site()


def parse_github_event() -> dict | None:
    """Parse GitHub event JSON file."""
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        return None

    try:
        with open(event_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


if __name__ == "__main__":
    cli()
