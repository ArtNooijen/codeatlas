# CodeAtlas Usage Guide

## CLI options
```
uv run codeatlas --repo <url> --fork-owner <owner> [options]
```

| Flag | Description |
| --- | --- |
| `--repo` | Source HTTPS URL (GitHub only today). |
| `--fork-owner` | Account/org that should own the fork. |
| `--workdir` | Local directory for clones (default `./workspaces`). |
| `--branch` | Branch to checkout/commit (default `main`). |
| `--token` | Explicit GitHub token. |
| `--token-env` | Env var to read the token from when `--token` is omitted (default `GITHUB_TOKEN`). |
| `--models` | Comma-separated Ollama models to run (defaults to config's `default`). |
| `--max-chars` | Character cap per file sent to the model (default 6000). |
| `--push` | Push the commit back to the fork after generation. |

## GitHub token notes
Set `GITHUB_TOKEN` (or your chosen env var) with `public_repo` scope. The token is used both for creating the fork and for pushing commits when `--push` is enabled.

## Ollama configuration
Adjust `codeatlas/config/models.yaml`:
1. Add each reachable Ollama host under `ollama_instances`.
2. Register models with the `instance` they should call.
3. Mark one `default: true` to control the CLI fallback.

## Git author configuration
The same config file now accepts an optional `git` block:

```yaml
git:
  author_name: "Docs Bot"
  author_email: "docs@example.com"
```

These settings control the `git commit` signature when CodeAtlas writes docs. If omitted, the defaults (`CodeAtlas` / `codeatlas@example.com`) are used. You can override either field at runtime with the `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL` environment variables.

## Customizing MkDocs
The generated `mkdocs.yml` uses the Material theme. You can safely add extra configuration (plugins, palettes, etc.); CodeAtlas preserves the file and only overwrites `site_name`, `theme`, and the nav list.

## Typical workflow
1. `uv run codeatlas --repo ... --fork-owner ... --token ...`
2. Inspect `docs/` and `mkdocs.yml` inside the cloned fork.
3. Run `uvx mkdocs serve` (or `uv run mkdocs serve`) from the fork to preview the site.
4. Use `--push` or manually push the new `docs` commit to publish the wiki.

## Troubleshooting
- **Fork already exists?** CodeAtlas simply reuses it; delete the local clone if you want a fresh checkout.
- **Model errors?** Ensure the Ollama instance is reachable and the model is pulled ahead of time.
- **No changes committed?** Either the repo already contains up-to-date docs or generation filtered out all files (non-supported extensions).
