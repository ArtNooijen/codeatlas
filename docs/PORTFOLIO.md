# CodeAtlas - Portfolio Highlights

## Project Overview

**CodeAtlas** is an automated documentation generation system that uses LLMs (via Ollama) to create comprehensive documentation for Git repositories. It intelligently analyzes code dependencies, generates context-aware documentation, and integrates seamlessly with GitHub workflows.

### Key Features
- 🔄 Automatic repository forking and cloning
- 🔍 Multi-language dependency analysis (Python, JavaScript/TypeScript, Rust, Go)
- 🤖 LLM-powered documentation generation with context awareness
- 📊 Automatic Mermaid diagram generation
- 🔀 Review PR workflow for documentation approval
- ⚙️ GitHub Actions integration

---

## Code Snippets & Technical Highlights

### 1. Smart Repository Management with Fork Handling

**File:** `codeatlas/ingest/git_repo.py`

This code demonstrates intelligent repository handling that supports both forking and direct cloning, with robust error handling and branch management.

```python
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
```

**Why this approach:**
- **Conditional forking**: Only forks when necessary (when fork owner differs from source), avoiding unnecessary API calls
- **Organization support**: The `_fork_payload()` method detects if the target is an organization and includes the proper payload
- **Async handling**: Uses polling with `_wait_for_fork()` to handle GitHub's asynchronous fork creation
- **Error resilience**: Clear error messages help diagnose API failures

**The fork payload method** intelligently handles both user and organization forks:

```python
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
```

---

### 2. Multi-Language Dependency Analysis

**File:** `codeatlas/deps/analyzer.py`

This is one of the most sophisticated parts of CodeAtlas - it extracts dependencies across multiple languages and builds a bidirectional dependency graph.

```python
def _extract_python_deps(self, record: FileRecord, content: str) -> list[str]:
    """Extract Python import statements and resolve to file paths."""
    deps: list[str] = []
    file_dir = Path(record.rel_path).parent
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        # Handle: import module
        match = re.match(r"^import\s+(\w+)", line)
        if match:
            module = match.group(1)
            dep_path = self._resolve_python_module(file_dir, module)
            if dep_path:
                deps.append(dep_path)
            continue
        
        # Handle: from module import ...
        match = re.match(r"^from\s+([\w.]+)\s+import", line)
        if match:
            module = match.group(1)
            dep_path = self._resolve_python_module(file_dir, module)
            if dep_path:
                deps.append(dep_path)
            continue
        
        # Handle: from .module import ... (relative imports)
        match = re.match(r"^from\s+\.+([\w.]*)\s+import", line)
        if match:
            rel_module = match.group(1)
            dep_path = self._resolve_python_relative(file_dir, rel_module)
            if dep_path:
                deps.append(dep_path)
    
    return list(set(deps))  # Remove duplicates
```

**Why this approach:**
- **Pattern matching**: Uses regex to handle different import styles (`import X`, `from X import Y`, relative imports)
- **Path resolution**: The `_resolve_python_module()` method intelligently searches multiple locations (relative to file, repo root, with/without extensions)
- **Bidirectional graph**: The `analyze()` method builds both `dependencies` (what this file needs) and `dependents` (what needs this file) for comprehensive context

**The resolution logic** handles Python's complex module system:

```python
def _resolve_python_module(self, file_dir: Path, module: str) -> str | None:
    """Resolve Python module name to file path relative to repo root."""
    module_parts = module.split(".")
    
    # Try as relative path
    potential_path = file_dir / "/".join(module_parts)
    for ext in ["", ".py"]:
        test_path = potential_path.with_suffix(ext) if ext else potential_path
        full_path = self.repo_path / test_path
        if full_path.exists() and full_path.is_file():
            return str(test_path)
    
    # Try with __init__.py
    init_path = potential_path / "__init__.py"
    full_init_path = self.repo_path / init_path
    if full_init_path.exists():
        return str(init_path)
    
    # Try from repo root
    root_path = Path("/".join(module_parts))
    for ext in ["", ".py"]:
        test_path = root_path.with_suffix(ext) if ext else root_path
        full_path = self.repo_path / test_path
        if full_path.exists() and full_path.is_file():
            return str(test_path)
    
    return None
```

**Why this resolution strategy:**
- **Multiple search paths**: Tries relative to current file, then repo root (handles both local and absolute imports)
- **Extension handling**: Checks both with and without `.py` extension
- **Package support**: Handles `__init__.py` for Python packages
- **Graceful failure**: Returns `None` if not found, allowing the system to continue

---

### 3. Context-Aware LLM Prompt Building

**File:** `codeatlas/llm/generate_docs.py`

This code demonstrates how to build intelligent prompts that include dependency context, making the generated documentation much more accurate and useful.

```python
def _build_prompt(
    self,
    repo_info: RepoInfo,
    record: FileRecord,
    content: str,
    imports: list[str],
    dep_context: dict[str, list[str]] | None = None,
) -> str:
    imports_hint = "\n".join(imports) or "None"
    
    # Build dependency context section
    dep_section = ""
    if dep_context:
        deps = dep_context.get("dependencies", [])
        dependents = dep_context.get("dependents", [])
        
        if deps or dependents:
            dep_section = "\n\nDependency Context:\n"
            if deps:
                dep_section += f"- This file depends on: {', '.join(deps[:10])}"
                if len(deps) > 10:
                    dep_section += f" (and {len(deps) - 10} more)"
                dep_section += "\n"
            if dependents:
                dep_section += f"- Files that depend on this file: {', '.join(dependents[:10])}"
                if len(dependents) > 10:
                    dep_section += f" (and {len(dependents) - 10} more)"
                dep_section += "\n"
    
    # Use the configured prompt template
    prompt = self.documentation_prompt_template.format(
        path=record.rel_path,
        repo_name=repo_info.repo_name,
        language=record.language,
        imports=imports_hint,
        dep_context=dep_section,
        content=content,
    )
    return textwrap.dedent(prompt)
```

**Why this approach:**
- **Context enrichment**: Includes both dependencies and dependents, giving the LLM a complete picture of the file's role in the codebase
- **Token management**: Limits to top 10 dependencies/dependents to avoid prompt bloat while still providing useful context
- **Template flexibility**: Uses configurable prompt templates from YAML, allowing customization without code changes
- **Smart formatting**: Uses `textwrap.dedent()` to handle multi-line prompts cleanly

**The dependency context retrieval** leverages the analyzer:

```python
def _get_dependency_context(
    self, repo_info: RepoInfo, record: FileRecord
) -> dict[str, list[str]] | None:
    """Get dependency context for a file if analyzer is available."""
    if not repo_info.dependency_analyzer:
        return None
    
    analyzer = repo_info.dependency_analyzer
    deps = analyzer.get_file_dependencies(record.rel_path)
    dependents = analyzer.get_file_dependents(record.rel_path)
    
    return {
        "dependencies": deps[:20],  # Limit to avoid prompt bloat
        "dependents": dependents[:20],
    }
```

---

### 4. Intelligent File Processing with Skip Logic

**File:** `codeatlas/llm/generate_docs.py`

This code shows how CodeAtlas avoids redundant work by detecting existing documentation and skipping already-documented files.

```python
def generate(self, repo_info: RepoInfo) -> list[Path]:
    docs_root = repo_info.path / "docs"
    code_root = docs_root / "code"
    code_root.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    
    # Filter files that should be processed and don't have existing docs
    files = []
    for record in repo_info.files:
        if self._should_process(record) and not self._has_existing_doc(docs_root, record):
            files.append(record)
    
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
            # ... process file ...
```

**Why this approach:**
- **Incremental updates**: Only processes files without existing documentation, making re-runs efficient
- **Language filtering**: `_should_process()` only handles supported languages
- **Error resilience**: Gracefully handles binary files and encoding errors
- **Progress tracking**: Uses Rich library for beautiful progress bars
- **Memory efficiency**: Processes files one at a time rather than loading everything into memory

---

### 5. Review PR Workflow

**File:** `codeatlas/review/review_manager.py`

This code implements a sophisticated PR creation workflow that includes detailed PR descriptions and handles both user and organization repositories.

```python
def create_review_pr(
    self,
    branch_name: str,
    title: str | None = None,
    body: str | None = None,
    documented_files: list[str] | None = None,
) -> str | None:
    """Create a GitHub PR for documentation review."""
    parsed = urlparse(self.repo_info.fork_url)
    if parsed.netloc == "github.com":
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            owner = parts[0]
            repo = parts[1]
        else:
            owner, repo = self.repo_info.fork_owner, self.repo_info.repo_name
    else:
        owner, repo = self.repo_info.fork_owner, self.repo_info.repo_name
    
    base_branch = self.repo_info.branch

    if not title:
        title = f"docs: Auto-generated documentation review"

    if not body:
        body_lines = [
            "## Auto-Generated Documentation",
            "",
            "This PR contains automatically generated documentation. Please review the changes below.",
            "Click the files changed tab to see the proposed documentation updates.",
            "If everything looks good, approve and merge this PR to finalize the documentation.",
        ]
        if documented_files:
            body_lines.extend([
                "",
                "### Documented Files:",
                "",
            ])
            for file_path in documented_files[:50]:  # Limit to 50 files
                body_lines.append(f"- `{file_path}`")
            if len(documented_files) > 50:
                body_lines.append(f"\n... and {len(documented_files) - 50} more files")
        
        body_lines.extend([
            "",
            "### Review Instructions:",
            "",
            "1. Review the generated documentation",
            "2. Make any necessary edits",
            "3. Approve and merge this PR to finalize the documentation",
            "",
            "---",
            "*Generated by CodeAtlas*",
        ])
        body = "\n".join(body_lines)

    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"Bearer {self.token}",
        "Accept": "application/vnd.github+json",
    }
    
    payload = {
        "title": title,
        "body": body,
        "head": branch_name,
        "base": base_branch,
    }

    try:
        console.print(f"[cyan]Creating PR in {owner}/{repo} with head={branch_name}, base={base_branch}")
        resp = self.session.post(api_url, json=payload, headers=headers)
        if resp.status_code in (201, 200):
            pr_data = resp.json()
            pr_url = pr_data.get("html_url")
            pr_number = pr_data.get("number")
            console.print(f"[green]Created PR #{pr_number}: {pr_url}")
            return pr_url
        else:
            error_data = resp.json() if resp.text else {}
            console.print(f"[red]Failed to create PR: {resp.status_code}")
            console.print(f"[red]Error details: {error_data}")
            return None
    except Exception as exc:
        console.print(f"[red]Error creating PR: {exc}")
        return None
```

**Why this approach:**
- **Self-documenting PRs**: Automatically generates detailed PR descriptions with file lists and review instructions
- **Scalability**: Limits file list to 50 items to avoid overwhelming the PR description
- **Error handling**: Provides detailed error messages for debugging API failures
- **Flexible**: Supports both custom and auto-generated PR content

---

### 6. Dual-Mode CLI Architecture

**File:** `codeatlas/main.py`

This code demonstrates a clean architecture that supports both CLI and GitHub Actions modes with shared logic.

```python
def cli(argv: list[str] | None = None) -> None:
    # ... argument parsing ...
    
    # Auto-detect GitHub Actions mode
    is_github_actions = args.github_actions or os.getenv("GITHUB_ACTIONS") == "true"

    if is_github_actions:
        github_actions_mode(args, config_path)
    else:
        # Validate required args for CLI mode
        if not args.repo or not args.fork_owner:
            parser.error("--repo and --fork-owner are required in CLI mode")
        cli_mode(args, config_path)
```

**Why this approach:**
- **Environment detection**: Automatically detects GitHub Actions environment
- **Code reuse**: Both modes share the same core logic (dependency analysis, documentation generation)
- **Context adaptation**: GitHub Actions mode uses the existing workspace instead of cloning
- **Event parsing**: Handles different GitHub event types (push, pull_request)

**The GitHub Actions mode** intelligently handles the existing workspace:

```python
def github_actions_mode(args: argparse.Namespace, config_path: Path) -> None:
    """Run in GitHub Actions mode."""
    # Parse GitHub event context
    event_data = parse_github_event()
    event_name = os.getenv("GITHUB_EVENT_NAME", "push")
    repository = os.getenv("GITHUB_REPOSITORY", "")
    
    # Use existing workspace instead of cloning
    github_workspace = Path(os.getenv("GITHUB_WORKSPACE", "/tmp/codeatlas"))
    
    # Check for existing docs
    has_docs = repo_mgr.has_existing_docs(github_workspace)
    
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
```

**Why this approach:**
- **Incremental updates**: Only documents changed files when docs already exist
- **Event-aware**: Handles both push and pull_request events differently
- **Efficiency**: Avoids re-documenting unchanged files
- **Workspace reuse**: Uses the existing GitHub Actions checkout instead of cloning

---

## Technical Architecture Highlights

### Design Patterns Used

1. **Strategy Pattern**: Different dependency extractors for different languages
2. **Factory Pattern**: Model client creation based on configuration
3. **Template Method**: Configurable prompt templates
4. **Repository Pattern**: `RepoManager` abstracts Git operations

### Key Technical Decisions

1. **Multi-language support**: Extensible architecture allows adding new languages easily
2. **Context-aware prompts**: Dependency graph provides rich context to LLM
3. **Incremental processing**: Only processes what's needed, making it efficient for large repos
4. **Error resilience**: Graceful handling of API failures, encoding errors, and edge cases
5. **Configuration-driven**: YAML-based configuration allows customization without code changes

### Performance Optimizations

1. **Lazy evaluation**: Files processed one at a time
2. **Caching**: Existing documentation detection avoids redundant work
3. **Token management**: Limits dependency context to prevent prompt bloat
4. **Parallel-ready**: Architecture supports parallel processing (future enhancement)

---

## Technologies & Libraries

- **Python 3.11+**: Modern Python with type hints
- **pygit2**: Git operations
- **httpx**: Async-capable HTTP client for GitHub API
- **ollama**: LLM client library
- **rich**: Beautiful terminal output and progress bars
- **PyYAML**: Configuration management
- **MkDocs**: Documentation site generation

---

## Project Impact

CodeAtlas demonstrates:
- ✅ **Complex system integration**: Git, GitHub API, LLM services
- ✅ **Multi-language parsing**: Regex-based dependency extraction
- ✅ **Intelligent automation**: Context-aware documentation generation
- ✅ **Production-ready code**: Error handling, logging, configuration management
- ✅ **Developer experience**: CLI and CI/CD integration

