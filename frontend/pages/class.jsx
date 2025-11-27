import { useEffect, useMemo } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { setPlayerClass, getPlayerClass } from "../lib/class";
import { toast } from "sonner";
import { Code, ServerCog, Share2 } from "lucide-react";
import { useDictionary } from "../lib/i18n";

const CLASS_ICONS = {
  django: ServerCog,
  python: Code,
  devops: Share2,
};

export default function ChooseClassPage() {
  const dict = useDictionary();
  const classes = useMemo(() => {
    return Object.entries(dict.classPage.classes).map(([id, data]) => ({
      id,
      ...data,
      icon: CLASS_ICONS[id] || Code,
    }));
  }, [dict.classPage.classes]);

  useEffect(() => {
    const chosen = getPlayerClass();
    if (chosen) window.location.href = "/worlds";
  }, []);

  function choose(id) {
    setPlayerClass(id);
    toast.success(dict.classPage.toastSuccess);
    window.location.href = "/worlds";
  }

  return (
    <Layout>
      <section className="mb-6">
        <p className="text-xs uppercase tracking-[0.35em] text-white/60">
          {dict.classPage.alignment}
        </p>
        <h1 className="text-3xl font-display">{dict.classPage.heading}</h1>
        <p className="text-sm text-white/70 mt-2">
          {dict.classPage.subheading}
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
                {dict.classPage.cta}
              </Button>
            </Card>
          );
        })}
      </div>
    </Layout>
  );
}
