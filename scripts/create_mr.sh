#!/usr/bin/env bash
set -euo pipefail

# create_mr.sh
# Usage: GITLAB_TOKEN=xxx PROJECT_ID=123 SOURCE_BRANCH=feature/compose-health-tests TARGET_BRANCH=main ./scripts/create_mr.sh

if [ -z "${GITLAB_TOKEN:-}" ] || [ -z "${PROJECT_ID:-}" ] || [ -z "${SOURCE_BRANCH:-}" ]; then
  echo "Usage: GITLAB_TOKEN=xxx PROJECT_ID=123 SOURCE_BRANCH=feature/... [TARGET_BRANCH=main] $0"
  exit 2
fi

TARGET_BRANCH=${TARGET_BRANCH:-main}
TITLE="[MR] Stabilize CI/CD and add health checks"
DESCRIPTION=$(cat .gitlab-mr-template.md | sed 's/"/\"/g')

API="https://gitlab.com/api/v4/projects/$PROJECT_ID/merge_requests"

echo "Creating MR: $SOURCE_BRANCH -> $TARGET_BRANCH"
response=$(curl --silent --header "PRIVATE-TOKEN: $GITLAB_TOKEN" -X POST "$API" \
  -d "source_branch=$SOURCE_BRANCH" \
  -d "target_branch=$TARGET_BRANCH" \
  -d "title=$TITLE" \
  -d "description=$DESCRIPTION")

echo "$response" | jq -r '.web_url'
