"""Repo ingestion utilities built around pygit2."""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import httpx
import pygit2  # type: ignore
from rich.console import Console


console = Console()


@dataclass
class FileRecord:
    """Lightweight metadata about each file in the repo."""

    rel_path: str
    language: str
    size_bytes: int


@dataclass
class RepoInfo:
    """Metadata describing a prepared repository checkout."""

    source_url: str
    fork_owner: str
    repo_name: str
    path: Path
    branch: str
    fork_url: str
    files: list[FileRecord] = field(default_factory=list)
    token: str | None = None
    dependency_analyzer: object | None = None  # DependencyAnalyzer instance


class RepoManager:
    """Handles forking, cloning, and collecting repo metadata."""

    def __init__(
        self,
        repo_url: str,
        fork_owner: str,
        workdir: Path,
        token: str | None = None,
        token_env: str = "GITHUB_TOKEN",
    ) -> None:
        self.repo_url = repo_url.rstrip("/")
        self.fork_owner = fork_owner
        self.workdir = workdir
        self.token = token or os.getenv(token_env)
        self.session = httpx.Client(timeout=30)
        self.workdir.mkdir(parents=True, exist_ok=True)

        parsed = urlparse(self.repo_url)
        if parsed.netloc != "github.com":
            raise ValueError("Only github.com repositories are supported right now.")
        parts = parsed.path.strip("/").split("/")
        if len(parts) < 2:
            raise ValueError("Repository URL must look like https://github.com/<owner>/<repo>")
        self.source_owner, self.repo_name = parts[:2]

    def prepare_repo(
        self,
        branch: str = "main",
        changed_files: list[str] | None = None,
        filter_changed: bool = False,
    ) -> RepoInfo:
        """Fork, clone, and collect metadata for the repository."""
        fork_url = self._ensure_fork()
        repo_path = self._clone_or_open(Path(self.workdir) / self.repo_name, fork_url, branch)
        all_files = list(self._collect_files(repo_path))
        
        # Filter files if changed_files provided and filter_changed is True
        if filter_changed and changed_files:
            changed_set = set(changed_files)
            files = [f for f in all_files if f.rel_path in changed_set]
        else:
            files = all_files
        
        return RepoInfo(
            source_url=self.repo_url,
            fork_owner=self.fork_owner,
            repo_name=self.repo_name,
            path=repo_path,
            branch=branch,
            fork_url=fork_url,
            files=files,
            token=self.token,
        )

    def _ensure_fork(self) -> str:
        if self.fork_owner == self.source_owner:
            console.print("[yellow]Fork owner matches source; using original repo URL.")
            return self.repo_url

        if not self.token:
            raise RuntimeError(
                "Forking requires a GitHub token. Provide --token or set the configured token env var."
            )

        fork_api = f"https://api.github.com/repos/{self.source_owner}/{self.repo_name}/forks"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}
        console.print(f"[cyan]Forking {self.source_owner}/{self.repo_name} into {self.fork_owner}...")
        fork_payload = self._fork_payload()
        resp = self.session.post(fork_api, json=fork_payload, headers=headers)

        if resp.status_code not in (202, 201):
            raise RuntimeError(f"Fork request failed: {resp.status_code} {resp.text}")

        fork_url = f"https://github.com/{self.fork_owner}/{self.repo_name}"
        self._wait_for_fork(headers, fork_url)
        return fork_url

    def _fork_payload(self) -> dict | None:
        """Return payload for fork creation; include org only when target is an org."""
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        user_resp = self.session.get(f"https://api.github.com/users/{self.fork_owner}", headers=headers)
        if user_resp.status_code != 200:
            console.print(f"[yellow]Could not verify owner type for {self.fork_owner}; treating as user.")
            return None
        owner_type = user_resp.json().get("type")
        if owner_type == "Organization":
            return {"organization": self.fork_owner}
        return None

        fork_url = f"https://github.com/{self.fork_owner}/{self.repo_name}"
        self._wait_for_fork(headers, fork_url)
        return fork_url

    def _wait_for_fork(self, headers: dict[str, str], fork_url: str) -> None:
        api_url = f"https://api.github.com/repos/{self.fork_owner}/{self.repo_name}"
        console.print("[cyan]Waiting for fork to be ready...")
        for _ in range(10):
            resp = self.session.get(api_url, headers=headers)
            if resp.status_code == 200:
                console.print("[green]Fork is ready.")
                return
            time.sleep(2)
        raise RuntimeError(f"Fork {fork_url} did not become available in time.")

    def _clone_or_open(self, repo_path: Path, fork_url: str, branch: str) -> Path:
        if repo_path.exists():
            console.print(f"[cyan]Opening existing repository at {repo_path}")
            try:
                repo = pygit2.Repository(str(repo_path))
            except (KeyError, pygit2.GitError):
                shutil.rmtree(repo_path)
                return self._clone_or_open(repo_path, fork_url, branch)
            self._fetch_origin(repo)
            # Reset any uncommitted changes before checking out
            self._reset_working_directory(repo)
            self._checkout_branch(repo, branch)
            return repo_path

        console.print(f"[cyan]Cloning {fork_url} into {repo_path}")
        callbacks = None
        if self.token:
            # Embed token into remote URL for HTTPS cloning.
            url = fork_url.replace("https://", f"https://{self.token}:x-oauth-basic@")
        else:
            url = fork_url
        repo = pygit2.clone_repository(url, str(repo_path), checkout_branch=branch, callbacks=callbacks)
        self._checkout_branch(repo, branch)
        return repo_path

    @staticmethod
    def _fetch_origin(repo: pygit2.Repository) -> None:
        remote = None
        for candidate in repo.remotes:
            if candidate.name == "origin":
                remote = candidate
                break
        if not remote:
            return
        try:
            remote.fetch()
        except Exception as exc:  # pragma: no cover - best effort
            console.print(f"[yellow]Fetch failed: {exc}")

    @staticmethod
    def _reset_working_directory(repo: pygit2.Repository) -> None:
        """Reset working directory to clean state before checkout."""
        try:
            # Get current HEAD
            head = repo.head
            if head:
                # Reset index and working directory to HEAD
                repo.reset(head.target, pygit2.GIT_RESET_HARD)
                console.print("[cyan]Reset working directory to clean state")
        except Exception as exc:
            console.print(f"[yellow]Could not reset working directory: {exc}")

    @staticmethod
    def _checkout_branch(repo: pygit2.Repository, branch: str) -> None:
        ref_name = f"refs/heads/{branch}"
        try:
            repo.lookup_reference(ref_name)
        except KeyError:
            try:
                origin_ref = repo.lookup_reference(f"refs/remotes/origin/{branch}")
            except KeyError:
                console.print(f"[yellow]Branch {branch} does not exist; staying on current HEAD.")
                return
            repo.create_reference(ref_name, origin_ref.target)
        repo.checkout(ref_name)

    def _collect_files(self, repo_path: Path) -> Iterable[FileRecord]:
        # Directories to exclude (to avoid documenting documentation and build artifacts)
        exclude_prefixes = [
            ".git/",
            "docs/",  # Exclude documentation directory
            "site/",  # Exclude built MkDocs site
            "node_modules/",
            ".venv/",
            "venv/",
            "__pycache__/",
            ".pytest_cache/",
            "dist/",
            "build/",
        ]
        
        for path in repo_path.rglob("*"):
            if path.is_dir():
                continue
            rel_path = path.relative_to(repo_path).as_posix()
            # Skip excluded directories
            if any(rel_path.startswith(prefix) for prefix in exclude_prefixes):
                continue
            language = self._language_for(rel_path)
            yield FileRecord(rel_path=rel_path, language=language, size_bytes=path.stat().st_size)

    @staticmethod
    def _language_for(rel_path: str) -> str:
        ext = Path(rel_path).suffix.lower()
        mapping = {
            ".py": "python",
            ".md": "markdown",
            ".js": "javascript",
            ".ts": "typescript",
            ".rs": "rust",
            ".go": "go",
        }
        return mapping.get(ext, "text")

    def has_existing_docs(self, repo_path: Path) -> bool:
        """Check if repository already has documentation."""
        docs_dir = repo_path / "docs"
        if not docs_dir.exists():
            return False
        # Check if docs directory has content (not just empty)
        code_docs = docs_dir / "code"
        if code_docs.exists() and any(code_docs.rglob("*.md")):
            return True
        # Check for any markdown files in docs
        return any(docs_dir.rglob("*.md"))

    def get_changed_files(
        self,
        repo_path: Path,
        base_ref: str | None = None,
        head_ref: str | None = None,
    ) -> list[str]:
        """Get list of changed files between two commits/branches."""
        try:
            repo = pygit2.Repository(str(repo_path))
        except (KeyError, pygit2.GitError):
            return []

        changed: list[str] = []

        if base_ref and head_ref:
            # Compare two specific refs
            try:
                base_commit = repo.revparse_single(base_ref)
                head_commit = repo.revparse_single(head_ref)
            except (KeyError, ValueError):
                return []
        elif base_ref:
            # Compare base_ref with HEAD
            try:
                base_commit = repo.revparse_single(base_ref)
                head_commit = repo.revparse_single("HEAD")
            except (KeyError, ValueError):
                return []
        else:
            # Compare HEAD with previous commit
            try:
                head_commit = repo.revparse_single("HEAD")
                if head_commit.parents:
                    base_commit = head_commit.parents[0]
                else:
                    return []  # No parent, can't compare
            except (KeyError, ValueError):
                return []

        try:
            diff = repo.diff(base_commit, head_commit)
            for patch in diff:
                if patch.delta.status in {
                    pygit2.GIT_DELTA_ADDED,
                    pygit2.GIT_DELTA_MODIFIED,
                    pygit2.GIT_DELTA_DELETED,
                }:
                    file_path = patch.delta.new_file.path or patch.delta.old_file.path
                    if file_path:
                        changed.append(file_path)
        except Exception as exc:
            console.print(f"[yellow]Error getting changed files: {exc}")
            return []

        return changed
