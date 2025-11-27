# Simple developer Makefile for local demo

SHELL := /bin/bash

# Load .env if present
ifneq (,$(wildcard ./.env))
	include .env
	export $(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' .env)
endif

# Common env for backend
POSTGRES_DB ?= rpgdb
POSTGRES_USER ?= rpguser
POSTGRES_PASSWORD ?= rpgpass
POSTGRES_HOST ?= ci_local_postgres
REDIS_URL ?= redis://ci_local_redis:6379/0

COMMON_ENV = -e DJANGO_SETTINGS_MODULE=core.settings.base \
	-e POSTGRES_HOST=$(POSTGRES_HOST) \
	-e POSTGRES_DB=$(POSTGRES_DB) \
	-e POSTGRES_USER=$(POSTGRES_USER) \
	-e POSTGRES_PASSWORD=$(POSTGRES_PASSWORD) \
	-e REDIS_URL=$(REDIS_URL)

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  make deploy-local     - Run local stack (redis, postgres, backend, celery)"
	@echo "  make seed-demo        - Seed demo content + admin user"
	@echo "  make stop-local       - Stop local stack containers"
	@echo "  make logs             - Tail backend logs"
	@echo "  make redeploy-local   - Stop and run deploy-local"
	@echo "  make clean            - Remove local image/network/containers"
	@echo "  make ps               - Show ci_local_* containers"
	@echo "  make curl-health      - Quick health check (HTTP)"
	@echo "  make deploy-staging   - SSH deploy to staging via docker-compose"
	@echo "  make toc              - Generate/refresh TOC in README files (doctoc)"

.PHONY: deploy-local
deploy-local:
	@docker network create ci_local_net >/dev/null 2>&1 || true
	@for c in ci_local_backend ci_local_celery ci_local_postgres ci_local_redis; do docker rm -f $$c >/dev/null 2>&1 || true; done
	@docker run -d --name ci_local_redis --network ci_local_net redis:7 >/dev/null
	@docker run -d --name ci_local_postgres --network ci_local_net -e POSTGRES_DB=rpgdb -e POSTGRES_USER=rpguser -e POSTGRES_PASSWORD=rpgpass postgres:15 >/dev/null
	@echo -n "Waiting for Postgres"; \
	for i in `seq 1 30`; do \
		if docker exec ci_local_postgres pg_isready -U rpguser -d rpgdb >/dev/null 2>&1; then echo " OK"; break; fi; \
		echo -n "."; sleep 1; \
		if [ $$i -eq 30 ]; then echo "\nPostgres did not become ready"; exit 1; fi; \
	done
	@DOCKER_BUILDKIT=1 docker build -t backend-local:latest ./backend
	@docker run --rm --network ci_local_net $(COMMON_ENV) backend-local:latest python manage.py migrate --noinput
	@docker run --rm --network ci_local_net $(COMMON_ENV) backend-local:latest python manage.py collectstatic --noinput
	@$(MAKE) seed-demo
	@docker run -d --name ci_local_backend --network ci_local_net -p 8000:8000 $(COMMON_ENV) backend-local:latest >/dev/null
	@docker run -d --name ci_local_celery --network ci_local_net $(COMMON_ENV) backend-local:latest celery -A core worker -l info >/dev/null
	@echo -n "Waiting for backend"; \
	for i in `seq 1 30`; do \
		if curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then echo " OK"; break; fi; \
		echo -n "."; sleep 1; \
	done
	@echo "---"; echo "Backend started: http://localhost:8000"; echo "Admin: admin / admin123";

.PHONY: seed-demo
seed-demo:
	@docker run --rm --network ci_local_net $(COMMON_ENV) -e ALLOW_DEMO_SEED=true backend-local:latest python manage.py load_demo_content || true
	@docker run --rm --network ci_local_net $(COMMON_ENV) -e ALLOW_DEMO_SEED=true -e DEMO_ADMIN_USERNAME=admin -e DEMO_ADMIN_EMAIL=admin@example.com -e DEMO_ADMIN_PASSWORD=admin123 backend-local:latest python manage.py create_demo_superuser || true
	@docker run --rm --network ci_local_net $(COMMON_ENV) backend-local:latest python manage.py print_demo_summary || true

.PHONY: stop-local
stop-local:
	@for c in ci_local_backend ci_local_celery ci_local_postgres ci_local_redis; do docker rm -f $$c >/dev/null 2>&1 || true; done

.PHONY: logs
logs:
	@docker logs -f ci_local_backend

.PHONY: redeploy-local clean ps curl-health

redeploy-local:
	@$(MAKE) stop-local
	@$(MAKE) deploy-local

clean:
	@$(MAKE) stop-local
	-@docker image rm -f backend-local:latest >/dev/null 2>&1 || true
	-@docker network rm ci_local_net >/dev/null 2>&1 || true
	@echo "Cleaned local artifacts (image/network/containers)"

ps:
	@docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" --filter "name=ci_local_"

curl-health:
	@curl -fsS -i http://localhost:8000/healthz || true

.PHONY: toc
toc:
	@npx --yes doctoc --github --title "Содержание" README.md README.deploy.md

.PHONY: deploy-staging
deploy-staging:
	@if [ -z "$(DEPLOY_HOST)" ] || [ -z "$(DEPLOY_USER)" ]; then \
	  echo "Set DEPLOY_HOST and DEPLOY_USER (and optionally DEPLOY_DIR) in .env or env"; exit 1; \
	fi
	@echo "Deploying to $$DEPLOY_USER@$$DEPLOY_HOST..."
	@ssh -o StrictHostKeyChecking=no $(DEPLOY_USER)@$(DEPLOY_HOST) "\
	  set -e; \
	  cd $(DEPLOY_DIR); \
	  docker-compose pull || true; \
	  docker-compose up -d; \
	  docker-compose exec -T backend python manage.py migrate --noinput; \
	  if [ "$(DEMO_SEED)" = "true" ]; then \
	    ALLOW_DEMO_SEED=$(ALLOW_DEMO_SEED) docker-compose exec -T backend python manage.py load_demo_content || true; \
	    ALLOW_DEMO_SEED=$(ALLOW_DEMO_SEED) DEMO_ADMIN_USERNAME=admin DEMO_ADMIN_EMAIL=admin@example.com DEMO_ADMIN_PASSWORD=admin123 docker-compose exec -T backend python manage.py create_demo_superuser || true; \
	    docker-compose exec -T backend python manage.py print_demo_summary || true; \
	  fi; \
	  echo 'Staging deploy done.'; \
	"
