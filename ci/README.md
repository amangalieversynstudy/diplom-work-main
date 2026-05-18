CI requirements and how to finish pipeline setup

Required CI variables (set in GitLab -> Settings -> CI/CD -> Variables):

- DOCKER_REGISTRY - registry host (e.g. docker.io or ghcr.io)
- DOCKER_USERNAME - username for registry
- DOCKER_PASSWORD - password or personal access token for registry
- CODECOV_TOKEN - token for codecov (optional; if not set, coverage upload will be skipped)

Runner requirements:

- A GitLab Runner capable of running Docker-in-Docker (if you plan to build/push images), or use a shell runner with docker available.
- Sufficient permissions to start sibling containers (dind) if using docker-in-docker.

Recommended pipeline flow (actual jobs in this repo):

1. frontend-lint
2. frontend-build
3. backend-test
4. backend-build-image
5. smoke-backend-image
6. deploy-local (manual)

How to trigger and test:

- Push branch (feature branch) to remote; open Merge Request targeting `main`.
- Ensure CI variables are set (see above).
- Monitor pipeline in GitLab; inspect logs for job failures and forwarded artifacts (junit/coverage).

Notes:

- `deploy-staging` is a manual placeholder — replace with your environment-specific commands (kubectl/helm/ssh).
- If you don't want to use Docker-in-Docker, change build jobs to run on a runner with docker access or use build services like GitLab's buildkit.

Runner setup on macOS (docker executor)
--------------------------------------

1) Install and start runner:

```bash
brew install gitlab-runner
sudo gitlab-runner install
sudo gitlab-runner start
```

2) Register runner:

```bash
sudo gitlab-runner register
# GitLab URL: https://gitlab.com (or your self-hosted)
# Registration token: <copy from Settings → CI/CD → Runners>
# Description: mac-local
# Tags: self-hosted, mac
# Executor: docker
# Default Docker image: docker:27.2.0
```

3) Enable Docker socket and privileged mode (for sibling containers):

Edit `config.toml` (e.g. `/Users/<user>/.gitlab-runner/config.toml`) and set:

```toml
[[runners]]
	name = "mac-local"
	url = "https://gitlab.com"
	token = "REDACTED"
	executor = "docker"
	[runners.docker]
		image = "docker:27.2.0"
		privileged = true
		volumes = ["/var/run/docker.sock:/var/run/docker.sock", "/cache"]
```

Restart runner:

```bash
sudo gitlab-runner restart
```

Optional automatic CI validation
--------------------------------
The repository previously included a helper script to automatically validate CI variables from the pipeline. That script has been removed to keep CI self-contained. If you still want automatic validation, run the helper locally or add an equivalent job that calls the GitLab API from CI using a protected `GITLAB_TOKEN` and `PROJECT_ID`.

SSH deploy variables and notes:

- DEPLOY_HOST - hostname or IP of the target deploy server (for SSH deploy)
- DEPLOY_USER - user to connect as on the deploy server
- SSH_PRIVATE_KEY - private SSH key (value only) used by CI to connect to deploy server

The `deploy-staging` job performs a remote SSH command on the host. By default it runs a placeholder remote command to pull the image and print a message. Replace the remote command with your real deploy process, for example:

ssh $DEPLOY_USER@$DEPLOY_HOST "cd /srv/myapp && docker-compose pull backend && docker-compose up -d"

Make sure the `SSH_PRIVATE_KEY` variable is set as protected and masked in GitLab for security.

Local runner and deploy-local
-----------------------------
If you don't have a remote server, you can run the deploy steps on your local machine by registering a GitLab Runner with a tag `local` and running jobs that require that tag.

Quick steps to run pipeline jobs locally (recommended for testing):

1. Install GitLab Runner locally (https://docs.gitlab.com/runner/install/).
2. Register a runner and set the tag `local` (when prompted for tags, enter `local`).
3. Make sure your runner has Docker available (or use a shell runner with docker).
4. In the pipeline UI, run the `deploy-local` job manually; it will load the `backend_image.tar` artifact created by the build job and start the container on the runner host.

Notes:

- The `deploy-local` job is manual and uses the runner tag `local` to avoid running accidental deploys in shared CI.
- Ports: `deploy-local` maps backend to port 8000 on the runner host. Ensure the port is free.
- Default runner tags for most jobs are `[self-hosted, mac]` as configured in `.gitlab-ci.yml`. Make sure your runner has these tags or adjust them.
