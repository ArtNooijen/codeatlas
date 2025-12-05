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

# Run codeatlas with review PR creation
cd /Users/artnooijen/Documents/CGI/codeatlas && \
uv run python -m codeatlas.main \
  --repo https://github.com/JManders07/BeerWithFriends-Front-end \
  --fork-owner ArtNooijen \
  --token "$GITHUB_TOKEN" \
  --models qwen3:8b \
  --branch main \
  --create-review-pr
