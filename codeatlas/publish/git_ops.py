"""Git publishing helpers."""
from __future__ import annotations

import os

import pygit2  # type: ignore
from rich.console import Console

from ..ingest.git_repo import RepoInfo

console = Console()


class Publisher:
    """Commits generated artifacts back into the forked repo."""

    def __init__(self, repo_info: RepoInfo) -> None:
        self.repo_info = repo_info
        self.repo = pygit2.Repository(str(repo_info.path))

    def commit_and_optionally_push(self, push: bool = False) -> None:
        if not self._stage_changes():
            console.print("[yellow]No changes detected; skipping commit.")
            return
        commit_id = self._commit()
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

    def _commit(self) -> str:
        index = self.repo.index
        tree_id = index.write_tree()
        signature = self._signature()
        parents = [] if self.repo.head_is_unborn else [self.repo.head.target]
        ref = f"refs/heads/{self.repo_info.branch}"
        commit_id = self.repo.create_commit(
            ref,
            signature,
            signature,
            "docs: refresh CodeAtlas output",
            tree_id,
            parents,
        )
        return str(commit_id)

    def _signature(self) -> pygit2.Signature:
        name = os.getenv("GIT_AUTHOR_NAME", "CodeAtlas")
        email = os.getenv("GIT_AUTHOR_EMAIL", "codeatlas@CGI.com")
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
