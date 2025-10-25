CI requirements and how to finish pipeline setup

Required CI variables (set in GitLab -> Settings -> CI/CD -> Variables):

- DOCKER_REGISTRY - registry host (e.g. docker.io or ghcr.io)
- DOCKER_USERNAME - username for registry
- DOCKER_PASSWORD - password or personal access token for registry
- CODECOV_TOKEN - token for codecov (optional; if not set, coverage upload will be skipped)

Runner requirements:

- A GitLab Runner capable of running Docker-in-Docker (if you plan to build/push images), or use a shell runner with docker available.
- Sufficient permissions to start sibling containers (dind) if using docker-in-docker.

Recommended pipeline flow:

1. lint-backend
2. pytest-backend (creates coverage and junit artifacts)
3. frontend-ci
4. build-backend-image (build & push image when registry creds present)
5. smoke-test-image (pull and health-check the pushed image)
6. deploy-staging (manual)

How to trigger and test:

- Push branch (feature branch) to remote; open Merge Request targeting `main`.
- Ensure CI variables are set (see above).
- Monitor pipeline in GitLab; inspect logs for job failures and forwarded artifacts (junit/coverage).

Notes:

- `deploy-staging` is a manual placeholder — replace with your environment-specific commands (kubectl/helm/ssh).
- If you don't want to use Docker-in-Docker, change build jobs to run on a runner with docker access or use build services like GitLab's buildkit.

SSH deploy variables and notes:

- DEPLOY_HOST - hostname or IP of the target deploy server (for SSH deploy)
- DEPLOY_USER - user to connect as on the deploy server
- SSH_PRIVATE_KEY - private SSH key (value only) used by CI to connect to deploy server

The `deploy-staging` job performs a remote SSH command on the host. By default it runs a placeholder remote command to pull the image and print a message. Replace the remote command with your real deploy process, for example:

ssh $DEPLOY_USER@$DEPLOY_HOST "cd /srv/myapp && docker-compose pull backend && docker-compose up -d"

Make sure the `SSH_PRIVATE_KEY` variable is set as protected and masked in GitLab for security.
