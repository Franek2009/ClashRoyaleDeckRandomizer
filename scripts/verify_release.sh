#!/usr/bin/env bash
# Read-only release gate. Requires gh and a token with contents/deployments read.
set -euo pipefail
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${RELEASE_SHA:?RELEASE_SHA is required}"
if [[ ! "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Invalid release commit SHA." >&2
    exit 1
fi
main_sha=$(gh api "repos/$GITHUB_REPOSITORY/commits/main" --jq '.sha')
if [[ "$RELEASE_SHA" != "$main_sha" ]]; then
    echo "Release tag does not identify current main." >&2
    exit 1
fi
deployment=$(gh api "repos/$GITHUB_REPOSITORY/deployments?environment=github-pages&per_page=1" --jq '.[0] | [.id, .sha] | @tsv')
read -r deployment_id deployed_sha <<< "$deployment"
if [[ ! "$deployment_id" =~ ^[0-9]+$ || "$deployed_sha" != "$RELEASE_SHA" ]]; then
    echo "Latest Pages deployment does not match the release commit." >&2
    exit 1
fi
state=$(gh api "repos/$GITHUB_REPOSITORY/deployments/$deployment_id/statuses?per_page=1" --jq '.[0].state // empty')
if [[ "$state" != success ]]; then
    echo "Matching Pages deployment is not successful." >&2
    exit 1
fi
echo "Release SHA matches main and successful Pages deployment: $RELEASE_SHA"
