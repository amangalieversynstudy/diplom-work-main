#!/usr/bin/env bash
set -euo pipefail

# check_gitlab_vars.sh
# Usage: GITLAB_TOKEN=xxx PROJECT_ID=123 ./scripts/check_gitlab_vars.sh
# This script lists project CI variables and verifies required ones exist.

if [ -z "${GITLAB_TOKEN:-}" ] || [ -z "${PROJECT_ID:-}" ]; then
  echo "Usage: GITLAB_TOKEN=xxx PROJECT_ID=123 $0"
  exit 2
fi

API="https://gitlab.com/api/v4/projects/$PROJECT_ID/variables"

required=(DOCKER_REGISTRY DOCKER_USERNAME DOCKER_PASSWORD CODECOV_TOKEN DEPLOY_HOST DEPLOY_USER SSH_PRIVATE_KEY)

echo "Fetching CI variables for project $PROJECT_ID..."
vars=$(curl --silent --header "PRIVATE-TOKEN: $GITLAB_TOKEN" "$API")

missing=()
for v in "${required[@]}"; do
  if ! echo "$vars" | grep -q "\"key\": \"$v\""; then
    missing+=("$v")
  fi
done

if [ ${#missing[@]} -eq 0 ]; then
  echo "All required CI variables are present.";
  exit 0
else
  echo "Missing CI variables: ${missing[*]}";
  echo "Please add them in GitLab -> Settings -> CI/CD -> Variables (set Masked/Protected where appropriate)."
  exit 1
fi
