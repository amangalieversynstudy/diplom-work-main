import { useEffect } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { setPlayerClass, getPlayerClass } from "../lib/class";
import { toast } from "sonner";
import { Code, ServerCog, Share2 } from "lucide-react";

const classes = [
  {
    id: "django",
    name: "Django Arcanist",
    desc: "ORM rituals, DRF glyphs, Celery familiars, Postgres temples.",
    crest: "🛡️",
    focus: "Backend control",
    icon: ServerCog,
  },
  {
    id: "python",
    name: "Python Spellblade",
    desc: "Scripts, algorithms, and automation scrolls for any guild quest.",
    crest: "🐍",
    focus: "Core mastery",
    icon: Code,
  },
  {
    id: "devops",
    name: "DevOps Ranger",
    desc: "Docker rituals, CI/CD wards, and multi-cloud scouting expertise.",
    crest: "⚙️",
    focus: "Deployment",
    icon: Share2,
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
      <section className="mb-6">
        <p className="text-xs uppercase tracking-[0.35em] text-white/60">
          Alignment
        </p>
        <h1 className="text-3xl font-display">Choose your specialization</h1>
        <p className="text-sm text-white/70 mt-2">
          Classes grant unique passives, cosmetic upgrades, and custom questlines.
        </p>
      </section>
      <div className="grid md:grid-cols-3 gap-6">
        {classes.map((c) => {
          const Icon = c.icon;
          return (
            <Card key={c.id} tone="aurora" title={c.name} subtitle={c.focus}>
              <div className="flex items-center gap-4 mb-4">
                <div className="text-4xl" aria-hidden>
                  {c.crest}
                </div>
                <Icon className="text-accent" />
              </div>
              <p className="text-sm text-white/80">{c.desc}</p>
              <Button className="mt-4" onClick={() => choose(c.id)}>
                Pledge allegiance
              </Button>
            </Card>
          );
        })}
      </div>
    </Layout>
  );
}
