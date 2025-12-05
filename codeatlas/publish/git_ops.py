"""Git publishing helpers."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pygit2  # type: ignore
from rich.console import Console

from ..ingest.git_repo import RepoInfo

console = Console()


class Publisher:
    """Commits generated artifacts back into the forked repo."""

    def __init__(
        self,
        repo_info: RepoInfo,
        author_name: str | None = None,
        author_email: str | None = None,
    ) -> None:
        self.repo_info = repo_info
        self.repo = pygit2.Repository(str(repo_info.path))
        self.author_name = author_name
        self.author_email = author_email

    def commit_and_optionally_push(
        self, push: bool = False, commit_message: str | None = None
    ) -> None:
        if not self._stage_changes():
            console.print("[yellow]No changes detected; skipping commit.")
            return
        commit_id = self._commit(commit_message)
        console.print(f"[green]Committed documentation as {commit_id}")
        if push:
            self._push()

    def _stage_changes(self) -> bool:
        status = self.repo.status()
        if not status:
            return False
        index = self.repo.index
        index.add_all()
        index.write()
        return True

    def _commit(self, commit_message: str | None = None) -> str:
        index = self.repo.index
        tree_id = index.write_tree()
        signature = self._signature()
        parents = [] if self.repo.head_is_unborn else [self.repo.head.target]
        ref = f"refs/heads/{self.repo_info.branch}"
        message = commit_message or "docs: refresh CodeAtlas output"
        commit_id = self.repo.create_commit(
            ref,
            signature,
            signature,
            message,
            tree_id,
            parents,
        )
        return str(commit_id)

    def _signature(self) -> pygit2.Signature:
        name = (
            self.author_name
            or os.getenv("GIT_AUTHOR_NAME")
            or "CodeAtlas"
        )
        email = (
            self.author_email
            or os.getenv("GIT_AUTHOR_EMAIL")
            or "codeatlas@CGI.com"
        )
        return pygit2.Signature(name, email)

    def _push(self) -> None:
        remote = self._origin_remote()
        if remote is None:
            console.print("[yellow]No origin remote configured; skipping push.")
            return
        callbacks = None
        if self.repo_info.token:
            credentials = pygit2.UserPass(self.repo_info.token, "x-oauth-basic")
            callbacks = pygit2.RemoteCallbacks(credentials=credentials)
        try:
            remote.push([f"refs/heads/{self.repo_info.branch}"], callbacks=callbacks)
            console.print("[green]Pushed documentation to origin.")
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Failed to push docs: {exc}") from exc

    def _origin_remote(self) -> pygit2.Remote | None:
        for remote in self.repo.remotes:
            if remote.name == "origin":
                return remote
        return None

    def build_mkdocs_site(self) -> bool:
        """Build MkDocs site after documentation is committed."""
        repo_path = self.repo_info.path
        mkdocs_yml = repo_path / "mkdocs.yml"
        
        if not mkdocs_yml.exists():
            console.print("[yellow]No mkdocs.yml found; skipping build.")
            return False

        console.print("[cyan]Building MkDocs site...")
        try:
            # Run mkdocs build
            result = subprocess.run(
                ["mkdocs", "build"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            if result.returncode == 0:
                console.print("[green]MkDocs site built successfully")
                return True
            else:
                console.print(f"[yellow]MkDocs build completed with warnings: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            console.print("[red]MkDocs build timed out")
            return False
        except FileNotFoundError:
            console.print("[yellow]mkdocs command not found; skipping build.")
            return False
        except Exception as exc:
            console.print(f"[yellow]Error building MkDocs site: {exc}")
            return False
