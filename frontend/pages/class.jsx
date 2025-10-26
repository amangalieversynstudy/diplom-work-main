import { useEffect } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { setPlayerClass, getPlayerClass } from "../lib/class";
import { toast } from "sonner";

const classes = [
  {
    id: "django",
    name: "Django Developer",
    desc: "Backend алхимик: ORM, DRF, Celery, Postgres.",
  },
  {
    id: "python",
    name: "Pythonista",
    desc: "Герой скриптов: основы Python, алгоритмы и трюки.",
  },
  {
    id: "devops",
    name: "DevOps Ranger",
    desc: "Проводник в мир Docker, CI/CD и клаудов.",
  },
];

export default function ChooseClassPage() {
  useEffect(() => {
    const chosen = getPlayerClass();
    if (chosen) window.location.href = "/worlds";
  }, []);

  function choose(id) {
    setPlayerClass(id);
    toast.success("Class selected");
    window.location.href = "/worlds";
  }

  return (
    <Layout>
      <h1 className="text-2xl font-semibold mb-4">Choose your class</h1>
      <div className="grid md:grid-cols-3 gap-6">
        {classes.map((c) => (
          <Card key={c.id} title={c.name} subtitle={c.desc}>
            <div className="mt-2">
              <Button onClick={() => choose(c.id)}>Select</Button>
            </div>
          </Card>
        ))}
      </div>
    </Layout>
  );
}
