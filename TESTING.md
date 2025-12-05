# Testing CodeAtlas Auto-Documentation

## Prerequisites

1. **Ollama running**: Make sure Ollama is running and accessible
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   # Or for remote instance
   curl http://drutus:11434/api/tags
   ```

2. **GitHub Token** (for PR creation and pushing):
   ```bash
   export GITHUB_TOKEN="your_github_token_here"
   ```

3. **Dependencies installed**:
   ```bash
   uv sync
   ```

## Testing Locally (CLI Mode)

### Basic Test - Document a Repository

```bash
uv run codeatlas \
  --repo https://github.com/your-username/test-repo \
  --fork-owner your-username \
  --token $GITHUB_TOKEN \
  --workdir ./test-workspace
```

This will:
- Clone/fork the repository
- Extract dependencies
- Generate documentation for all undocumented files
- Create/update MkDocs site
- Commit changes (use `--push` to push to remote)

### Test with Review PR

```bash
uv run codeatlas \
  --repo https://github.com/your-username/test-repo \
  --fork-owner your-username \
  --token $GITHUB_TOKEN \
  --create-review-pr \
  --workdir ./test-workspace
```

This will create a review branch and PR instead of committing directly.

### Test with Specific Models

```bash
uv run codeatlas \
  --repo https://github.com/your-username/test-repo \
  --fork-owner your-username \
  --models qwen3:8b,llama3.1:8b \
  --token $GITHUB_TOKEN
```

## Testing GitHub Actions Mode Locally

You can simulate GitHub Actions mode locally:

```bash
# Set GitHub Actions environment variables
export GITHUB_ACTIONS="true"
export GITHUB_REPOSITORY="your-username/test-repo"
export GITHUB_REF="refs/heads/main"
export GITHUB_EVENT_NAME="push"
export GITHUB_WORKSPACE="$(pwd)/test-repo"
export GITHUB_TOKEN="your_token"

# Create a mock event file
mkdir -p .github
cat > .github/event.json << EOF
{
  "repository": {
    "full_name": "your-username/test-repo"
  }
}
EOF
export GITHUB_EVENT_PATH=".github/event.json"

# Run in GitHub Actions mode
uv run codeatlas --github-actions --create-review-pr
```

## Testing with GitHub Actions Workflow

### Setup

1. **Add the workflow to your repository**:
   - Copy `.github/workflows/auto-document.yml` to your target repository
   - Or add it to the codeatlas repository itself to test

2. **Ensure secrets are set**:
   - `GITHUB_TOKEN` is automatically provided by GitHub Actions
   - No additional secrets needed

### Trigger the Workflow

1. **On Push**:
   - Push to `main` or `master` branch
   - The workflow will automatically run

2. **On Pull Request**:
   - Open a new PR or update an existing one
   - The workflow will run and document changed files

### What to Expect

1. **First Run (No existing docs)**:
   - Scans all files in the repository
   - Generates documentation for undocumented files
   - Creates a PR with all generated docs

2. **Subsequent Runs (With existing docs)**:
   - Only documents changed files in the PR/push
   - Updates existing documentation if files changed
   - Creates a PR with only the changed files

## Verification Steps

### 1. Check Dependency Analysis

```bash
# After running, check if dependencies were extracted
# Look for console output: "Analyzed dependencies for X files"
```

### 2. Check Generated Documentation

```bash
# Navigate to the workspace
cd test-workspace/your-repo-name

# Check if docs were generated
ls -la docs/code/

# View a generated doc
cat docs/code/src/main.py.md
```

### 3. Check MkDocs Site

```bash
cd test-workspace/your-repo-name

# Check if mkdocs.yml exists
cat mkdocs.yml

# Build and serve locally (if mkdocs is installed)
mkdocs serve
# Visit http://127.0.0.1:8000
```

### 4. Check Review PR (if created)

- Go to your GitHub repository
- Look for a PR titled "docs: Auto-generated documentation review"
- Review the generated documentation
- Merge when satisfied

### 5. Verify Dependency Context in Docs

Open a generated documentation file and check if it includes:
- Dependency context section showing which files depend on this file
- Files that this file depends on
- This context helps the LLM generate better documentation

## Troubleshooting

### Issue: "No eligible files found"
- **Cause**: All files already have documentation or no supported files
- **Solution**: Check if `docs/code/` exists and has markdown files

### Issue: "Fork request failed"
- **Cause**: Invalid token or insufficient permissions
- **Solution**: Ensure `GITHUB_TOKEN` has `repo` scope

### Issue: "Model failed"
- **Cause**: Ollama instance not accessible or model not pulled
- **Solution**: 
  ```bash
  # Check Ollama
  ollama list
  # Pull model if needed
  ollama pull qwen3:8b
  ```

### Issue: "No changes detected"
- **Cause**: Documentation already up to date
- **Solution**: This is normal if nothing changed

### Issue: GitHub Actions workflow not running
- **Cause**: Workflow file not in correct location
- **Solution**: Ensure `.github/workflows/auto-document.yml` exists in the repository root

## Example Test Repository

Create a simple test repository:

```bash
mkdir test-repo && cd test-repo
git init
echo "def hello(): pass" > main.py
echo "from main import hello" > utils.py
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/test-repo.git
git push -u origin main
```

Then run codeatlas on it to test.

## Expected Output

When running successfully, you should see:

```
[cyan]Forking owner/repo into owner...
[green]Fork is ready.
[cyan]Cloning https://github.com/owner/repo into /path/to/workspace
[cyan]Analyzing file dependencies...
[green]Analyzed dependencies for 15 files
[cyan]Processing src/main.py
[green]Wrote docs/code/src/main.py.md
[green]Generated 15 documentation files
[green]Committed documentation as abc123...
[cyan]Building MkDocs site...
[green]MkDocs site built successfully
```


