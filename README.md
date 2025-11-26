# CodeAtlas

CodeAtlas forks any public Git repository, clones the fork locally, summarizes every source file with Ollama, and publishes a MkDocs Material site directly inside the fork. The generated docs, `mkdocs.yml`, and supporting assets travel with the fork so you can push and host them anywhere.

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
3. Generate Markdown for every supported file using `qwen3:8b` (or any models you request).
4. Create/refresh `docs/` and `mkdocs.yml` inside the fork using MkDocs Material.
5. Commit the changes; add `--push` to push them back to GitHub immediately.

See `docs/USAGE.md` for advanced arguments, token handling, and troubleshooting tips.

## Configuring models
`codeatlas/config/models.yaml` defines Ollama instances and available models:
- List every Ollama endpoint under `ollama_instances`.
- Reference those instances from the `models` section and mark one with `default: true` (defaults to `qwen3:8b`).
- Override at runtime with `--models qwen3:8b,llama3.1:8b`.

## Outputs inside the fork
- `docs/index.md` contains a generated table of contents.
- `docs/code/<path>.md` mirrors the repository layout and includes summaries per model plus detected imports.
- `mkdocs.yml` is rewritten to use the Material theme and point at the generated docs.
- A commit named `docs: refresh CodeAtlas output` is created; `--push` sends it to the fork's origin.

## Developing CodeAtlas itself
- Update dependencies in `pyproject.toml` and re-run `uv lock`.
- Run lint/tests via `uv run <tool>`.
- Keep `config/models.yaml` up to date with the Ollama instances you want to target.
