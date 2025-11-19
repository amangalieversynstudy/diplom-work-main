import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import XPBar from "../components/XPBar";
import Button from "../components/Button";
import { Map, Swords, Flame, Compass, Crown, Sparkles } from "lucide-react";
import { getPlayerClass } from "../lib/class";

const questBoard = [
  {
    title: "Light the Forge",
    desc: "Spin up local docker stack and run first migrations.",
    reward: "+50 XP",
  },
  {
    title: "Scout the Worlds",
    desc: "Visit the world map and preview node coordinates.",
    reward: "+30 XP",
  },
  {
    title: "Master Your Class",
    desc: "Choose specialization and unlock class-specific quests.",
    reward: "Passive buff",
  },
];

const codexEntries = [
  {
    title: "Backend Trials",
    detail: "Celery + Redis jobs proven in smoke tests.",
  },
  {
    title: "Frontend Rituals",
    detail: "RPG UI system + onboarding revamp shipped.",
  },
  {
    title: "Guild Reputation",
    detail: "CI/CD with coverage + Codecov tracking.",
  },
];

const relics = [
  { label: "Artifact", value: "CI Sigil", icon: Sparkles },
  { label: "Allies", value: "Celery sprites", icon: Flame },
  { label: "Weather", value: "Stable build", icon: Compass },
];

export default function Home() {
  const [playerClass, setPlayerClass] = useState("Unaligned Initiate");

  useEffect(() => {
    const c = getPlayerClass();
    if (c) setPlayerClass(c);
  }, []);

  return (
    <Layout>
      <section className="grid gap-6 md:grid-cols-[1.5fr,1fr] mb-8">
        <Card tone="aurora" title="Command Console" subtitle="You stand before the Academy sanctum">
          <div className="space-y-6">
            <div>
              <p className="text-sm uppercase tracking-[0.4em] text-white/60">
                Current Oath
              </p>
              <h1 className="text-3xl md:text-4xl font-display mt-2">
                Forge a legendary {playerClass} destined for production.
              </h1>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => (window.location.href = "/worlds")}
                className="shadow-lg">
                <Map size={18} /> Continue Adventure
              </Button>
              <Button
                variant="secondary"
                onClick={() => (window.location.href = "/class")}
              >
                <Crown size={18} /> Switch Class
              </Button>
            </div>
          </div>
        </Card>
        <Card tone="moss" title="Character Sheet" subtitle={`Spec: ${playerClass}`}>
          <div className="space-y-4">
            <XPBar current={20} max={100} />
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="glass-panel p-3 rounded-2xl text-center">
                <p className="text-white/60 uppercase text-xs tracking-widest">Level</p>
                <p className="text-2xl font-semibold">I</p>
              </div>
              <div className="glass-panel p-3 rounded-2xl text-center">
                <p className="text-white/60 uppercase text-xs tracking-widest">Next Unlock</p>
                <p className="text-lg">Mission Map</p>
              </div>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-2 mb-8">
        <Card tone="night" title="Quest Board" subtitle="Pick your next objective">
          <div className="space-y-4">
            {questBoard.map((quest) => (
              <div key={quest.title} className="flex items-center justify-between gap-4 border border-white/5 rounded-2xl px-4 py-3 bg-black/20">
                <div>
                  <p className="font-medium">{quest.title}</p>
                  <p className="text-sm text-white/70">{quest.desc}</p>
                </div>
                <span className="text-xs text-gold uppercase tracking-[0.4em]">
                  {quest.reward}
                </span>
              </div>
            ))}
          </div>
        </Card>
        <Card tone="ember" title="Codex Updates" subtitle="Lore entries unlocked by progress">
          <div className="space-y-4">
            {codexEntries.map((entry) => (
              <div key={entry.title} className="p-4 rounded-2xl bg-black/30 border border-white/10">
                <p className="text-sm text-white/60">{entry.title}</p>
                <p className="text-lg font-semibold">{entry.detail}</p>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        {relics.map((item) => (
          <Card key={item.label} tone="default" title={item.label}>
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-2xl bg-white/10 border border-white/10">
                <item.icon size={24} className="text-accent" />
              </div>
              <div>
                <p className="text-xl font-semibold">{item.value}</p>
                <p className="text-sm text-white/60">Status nominal</p>
              </div>
            </div>
          </Card>
        ))}
        <Card tone="moss" title="Battle Plan" subtitle="Implementation checklist">
          <ul className="text-sm text-white/80 space-y-1 list-disc ml-5">
            <li>Deploy redesigned UI kit</li>
            <li>Keep missions synced with backend</li>
            <li>Document 50% milestone</li>
          </ul>
        </Card>
        <Card tone="aurora" title="Signals" subtitle="Live telemetry">
          <div className="flex flex-col gap-3 text-sm">
            <span className="inline-flex items-center gap-2"><Sparkles size={16} className="text-accent" /> XP gain boosted for newcomers</span>
            <span className="inline-flex items-center gap-2"><Swords size={16} className="text-rose-300" /> Mission Gate locked until Intro complete</span>
          </div>
        </Card>
      </section>
    </Layout>
  );
}
