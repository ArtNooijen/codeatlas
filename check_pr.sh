#!/bin/bash

# Check if a PR was created for the documentation
# Usage: ./check_pr.sh

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Use values from .env or fallback to environment variables
REPO="${REPO:-ArtNooijen/BeerWithFriends-Front-end}"
TOKEN="${GITHUB_TOKEN:-${TOKEN}}"

echo "Checking for PRs in $REPO..."
echo ""

# Get recent PRs
curl -s -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/$REPO/pulls?state=open&sort=created&direction=desc" \
     | jq -r '.[] | "PR #\(.number): \(.title)\n   URL: \(.html_url)\n   Branch: \(.head.ref) -> \(.base.ref)\n   Created: \(.created_at)\n"'

