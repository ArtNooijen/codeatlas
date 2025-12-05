# CodeAtlas

CodeAtlas automatically documents Git repositories using Ollama. It can run via CLI or GitHub Actions, extracts file dependencies for context, detects missing documentation, generates docs for changed or undocumented files, and creates review PRs. The generated docs, `mkdocs.yml`, and supporting assets can be committed directly or reviewed via pull request.

## Requirements
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- A running [Ollama](https://ollama.ai/) instance (local or remote)
- A GitHub token with `public_repo` scope to allow forking and pushing (`GITHUB_TOKEN`)

Install dependencies once:
```bash
uv sync
```

## Quick start

### CLI Mode
```bash
uv run codeatlas \
  --repo https://github.com/user/project \
  --fork-owner your-github-handle \
  --token $GITHUB_TOKEN \
  --workdir /tmp/codeatlas
```

The CLI will:
1. Fork `user/project` into `your-github-handle` (unless you already own it).
2. Clone the fork into `--workdir`.
3. Extract file dependencies to provide context to the LLM.
4. Generate Markdown for undocumented files using `qwen3:8b` (or any models you request) plus optional Mermaid diagrams.
5. Create/refresh `docs/` and `mkdocs.yml` inside the fork using MkDocs Material.
6. Commit the changes; add `--push` to push them back to GitHub immediately.

### Review PR Mode
```bash
uv run codeatlas \
  --repo https://github.com/user/project \
  --fork-owner your-github-handle \
  --token $GITHUB_TOKEN \
  --create-review-pr
```

This creates a review branch and PR instead of committing directly, allowing you to review and modify the documentation before merging.

### GitHub Actions Mode
Add `.github/workflows/auto-document.yml` to your repository. The workflow automatically:
- Triggers on push and pull request events
- Documents only changed files (if docs exist) or all undocumented files
- Creates a review PR for documentation changes

See `docs/USAGE.md` for advanced arguments, token handling, and troubleshooting tips.

## Configuring models
`codeatlas/config/models.yaml` defines Ollama instances and available models:
- List every Ollama endpoint under `ollama_instances`.
- Reference those instances from the `models` section and mark one with `default: true` (defaults to `qwen3:8b`).
- Override at runtime with `--models qwen3:8b,llama3.1:8b`.
- Set `diagram_default_model` and `diagram_prompt` to control the dedicated model that builds Mermaid call-graph diagrams (`--diagram-model`/`--diagram-prompt` override them per run).
- Set `documentation_prompt` to customize the prompt used for generating documentation (see below).

## Customizing Prompts

### Documentation Prompt
Edit `documentation_prompt` in `models.yaml` to customize how documentation is generated. Available placeholders:
- `{path}` - File path
- `{repo_name}` - Repository name
- `{language}` - Programming language
- `{imports}` - Detected imports
- `{dep_context}` - Dependency context (files this depends on / files that depend on this)
- `{content}` - File content

### Mermaid Diagrams
- Add a secondary Ollama model dedicated to structural visualizations with `--diagram-model llama3.1:8b`.
- Customize the prompt template with `--diagram-prompt "Your template {path} {language} {content}"`.
- Each Markdown file will gain a `## Function Diagram` section containing the Mermaid output.

## Git author metadata
Use the same `models.yaml` file to control the commit signature CodeAtlas uses:

```yaml
git:
  author_name: "Docs Bot"
  author_email: "docs@example.com"
```

These values override the defaults (`CodeAtlas` / `codeatlas@example.com`). You can still override either field via the `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL` environment variables if needed for one-off runs.

## Features

### Smart Documentation Detection
- Only generates documentation for files that don't already have docs
- For repositories with existing docs, only documents files changed in PRs/pushes
- Automatically excludes `docs/`, `site/`, `node_modules/`, and other build artifacts

### Dependency Context
- Extracts file dependencies (imports, requires, etc.) for Python, JavaScript/TypeScript, Rust, and Go
- Provides dependency context to the LLM for better documentation quality
- Shows which files depend on the current file and which files it depends on

### Review Workflow
- Use `--create-review-pr` to create a PR instead of committing directly
- Review and modify generated documentation before merging
- Perfect for automated workflows via GitHub Actions

## Outputs inside the fork
- `docs/index.md` contains a generated table of contents.
- `docs/code/<path>.md` mirrors the repository layout and includes summaries per model plus detected imports and dependency context.
- `mkdocs.yml` is rewritten to use the Material theme and point at the generated docs.
- A commit named `docs: auto-generated documentation` is created; `--push` sends it to the fork's origin.
- MkDocs site is automatically built after committing.

## Developing CodeAtlas itself
- Update dependencies in `pyproject.toml` and re-run `uv lock`.
- Run lint/tests via `uv run <tool>`.
- Keep `config/models.yaml` up to date with the Ollama instances you want to target.
