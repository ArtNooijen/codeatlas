#!/bin/bash

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    # Load lines 2-7 from .env file
    export $(sed -n '2,7p' .env | grep -v '^#' | xargs)
fi

# Ensure GITHUB_TOKEN is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN not set. Please set it in .env file or export it."
    exit 1
fi

# Get the script directory and change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Run codeatlas with review PR creation
# Example: ./run_with_review.sh https://github.com/user/repo your-github-handle
REPO_URL="${1:-https://github.com/Luke943/Euler-Maths}"
FORK_OWNER="${2:-ArtNooijen}"

uv run python -m codeatlas.main \
  --repo "$REPO_URL" \
  --fork-owner "$FORK_OWNER" \
  --token "$GITHUB_TOKEN" \
  --models qwen3:8b \
  --branch main \
  --create-review-pr