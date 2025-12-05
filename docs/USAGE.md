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
| `--diagram-model` | Specific model for Mermaid diagrams (defaults to config). |
| `--diagram-prompt` | Custom prompt template for diagram generation. |
| `--max-chars` | Character cap per file sent to the model (default 6000). |
| `--push` | Push the commit back to the fork after generation. |
| `--create-review-pr` | Create a PR for documentation review instead of committing directly. |
| `--github-actions` | Run in GitHub Actions mode (auto-detected if `GITHUB_ACTIONS` env var is set). |

## GitHub token notes
Set `GITHUB_TOKEN` (or your chosen env var) with `public_repo` scope. The token is used both for creating the fork and for pushing commits when `--push` is enabled.

## Ollama configuration
Adjust `codeatlas/config/models.yaml`:
1. Add each reachable Ollama host under `ollama_instances`.
2. Register models with the `instance` they should call.
3. Mark one `default: true` to control the CLI fallback.
4. Optionally set `diagram_default_model` and `diagram_prompt` for Mermaid diagrams.
5. Optionally set `documentation_prompt` to customize the documentation generation prompt (see below).

## Git author configuration
The same config file now accepts an optional `git` block:

```yaml
git:
  author_name: "Docs Bot"
  author_email: "docs@example.com"
```

These settings control the `git commit` signature when CodeAtlas writes docs. If omitted, the defaults (`CodeAtlas` / `codeatlas@example.com`) are used. You can override either field at runtime with the `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL` environment variables.

## Customizing Documentation Prompts

### Documentation Prompt
Edit `documentation_prompt` in `models.yaml` to customize how documentation is generated:

```yaml
documentation_prompt: |
  You are CodeAtlas, an expert codebase documentarian. Summarize the file {path}
  from repository {repo_name}.

  Produce:
  1. Purpose summary
  2. Key functions/classes and their collaboration
  3. External dependencies or APIs used

  Imports detected:
  {imports}{dep_context}

  File content:
  {content}
```

Available placeholders:
- `{path}` - File path relative to repo root
- `{repo_name}` - Repository name
- `{language}` - Programming language (python, javascript, etc.)
- `{imports}` - Detected import/require statements
- `{dep_context}` - Dependency context showing file relationships
- `{content}` - File content (truncated to `--max-chars`)

### Diagram Prompt
Customize Mermaid diagram generation with `diagram_prompt` in `models.yaml`.

## Customizing MkDocs
The generated `mkdocs.yml` uses the Material theme. You can safely add extra configuration (plugins, palettes, etc.); CodeAtlas preserves the file and only overwrites `site_name`, `theme`, and the nav list.

## Typical workflows

### Basic Documentation Generation
1. `uv run codeatlas --repo ... --fork-owner ... --token ...`
2. Inspect `docs/` and `mkdocs.yml` inside the cloned fork.
3. Run `uvx mkdocs serve` (or `uv run mkdocs serve`) from the fork to preview the site.
4. Use `--push` or manually push the new `docs` commit to publish the wiki.

### Review PR Workflow
1. `uv run codeatlas --repo ... --fork-owner ... --token ... --create-review-pr`
2. Review the generated PR on GitHub.
3. Make any necessary edits directly in the PR.
4. Merge the PR when satisfied.

### GitHub Actions Workflow
1. Add `.github/workflows/auto-document.yml` to your repository.
2. Push to `main`/`master` or open a PR to trigger documentation generation.
3. Review the auto-generated PR with documentation changes.
4. Merge when ready.

## How It Works

### Documentation Detection
- **First run**: Documents all eligible source files
- **Subsequent runs**: Only documents files that:
  - Don't have existing documentation, OR
  - Were changed in the current PR/push (if repository already has docs)

### Dependency Analysis
CodeAtlas automatically extracts file dependencies for:
- **Python**: `import` and `from` statements
- **JavaScript/TypeScript**: `import`/`require`/`export` statements
- **Rust**: `use` statements and `mod` declarations
- **Go**: `import` statements

This dependency context is included in prompts to help the LLM generate better documentation.

### Excluded Files
The following are automatically excluded from documentation:
- `docs/` directory (to avoid documenting documentation)
- `site/` directory (built MkDocs site)
- `node_modules/`, `.venv/`, `venv/`, `__pycache__/`, `dist/`, `build/` (build artifacts)
- Binary files (images, executables, etc.)

## Troubleshooting
- **Fork already exists?** CodeAtlas simply reuses it; delete the local clone if you want a fresh checkout.
- **Model errors?** Ensure the Ollama instance is reachable and the model is pulled ahead of time.
- **No changes committed?** Either the repo already contains up-to-date docs or generation filtered out all files (non-supported extensions).
- **PR creation failed?** Ensure your GitHub token has `repo` scope and the branch was successfully pushed.
- **Git conflicts?** CodeAtlas automatically resets the working directory before checkout. If issues persist, delete the local clone.
- **Dependency analysis shows 0 files?** This is normal for repositories without supported file types or if dependency extraction couldn't resolve import paths.
