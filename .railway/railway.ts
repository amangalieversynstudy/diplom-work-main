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
    healthcheck: { path: "/healthz", timeout: 300 },
    restartPolicy: { type: "ON_FAILURE", maxRetries: 5 },
    replicas: { "sfo": 1 },
  });

  return project("resplendent-love", {
    variables: { managed: false },
    resources: [diplomWorkMain],
  });
});
