import { defineRailway, github, project, service } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "diplom-work-main";
export default defineRailway(() => {
  const diplomWorkMain = service("diplom-work-main", {
    // builder from CaC: "dockerfile"
    source: github("amangalieversynstudy/diplom-work-main", { branch: "feature/final-polish", checkSuites: false }),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "/Dockerfile.backend" },
    start: "sh -c \"export DJANGO_SETTINGS_MODULE=core.settings.production && python3 manage.py migrate --noinput && python3 manage.py ensure_superuser && python3 manage.py collectstatic --noinput && python3 manage.py seed_course && python3 manage.py sync_course_protection && exec daphne -b 0.0.0.0 -p ${PORT:-8000} --access-log - core.asgi:application\"",
    replicas: { "sfo": 1 },
  });

  return project("resplendent-love", {
    variables: { managed: false },
    resources: [diplomWorkMain],
  });
});
