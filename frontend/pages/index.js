import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import XPBar from "../components/XPBar";
import Button from "../components/Button";
import { Map, Swords, Flame, Compass, Crown, Sparkles } from "lucide-react";
import { getPlayerClass } from "../lib/class";
import { useDictionary, formatHeadline } from "../lib/i18n";

export default function Home() {
  const [playerClass, setPlayerClass] = useState("");
  const dict = useDictionary();
  const hero = dict.hero;
  const sheet = dict.sheet;
  const quests = dict.quests;
  const codex = dict.codex;
  const relics = dict.relics;
  const classMap = dict.classPage?.classes || {};
  const playerClassName = classMap[playerClass]?.name || playerClass || hero.fallbackClass;
  const headline = formatHeadline(hero.headlineTemplate, playerClassName);
  const relicIconMap = {
    sparkles: Sparkles,
    flame: Flame,
    compass: Compass,
  };
  const signalIconMap = {
    sparkles: Sparkles,
    swords: Swords,
    flame: Flame,
  };

  useEffect(() => {
    const c = getPlayerClass();
    if (c) setPlayerClass(c);
  }, []);

  return (
    <Layout>
      <section className="grid gap-6 md:grid-cols-[1.5fr,1fr] mb-8">
        <Card tone="aurora" title={hero.cardTitle} subtitle={hero.cardSubtitle}>
          <div className="space-y-6">
            <div>
              <p className="text-sm uppercase tracking-[0.4em] text-white/60">
                {hero.oath}
              </p>
              <h1 className="text-3xl md:text-4xl font-display mt-2">{headline}</h1>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => (window.location.href = "/worlds")} className="shadow-lg">
                <Map size={18} /> {hero.primaryCta}
              </Button>
              <Button
                variant="secondary"
                onClick={() => (window.location.href = "/class")}
              >
                <Crown size={18} /> {hero.secondaryCta}
              </Button>
            </div>
          </div>
        </Card>
  <Card tone="moss" title={sheet.title} subtitle={`${sheet.spec}: ${playerClassName}`}>
          <div className="space-y-4">
            <XPBar current={20} max={100} />
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="glass-panel p-3 rounded-2xl text-center">
                <p className="text-white/60 uppercase text-xs tracking-widest">{sheet.level}</p>
                <p className="text-2xl font-semibold">I</p>
              </div>
              <div className="glass-panel p-3 rounded-2xl text-center">
                <p className="text-white/60 uppercase text-xs tracking-widest">{sheet.nextUnlock}</p>
                <p className="text-lg">{sheet.nextUnlockValue}</p>
              </div>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-2 mb-8">
        <Card tone="night" title={quests.title} subtitle={quests.subtitle}>
          <div className="space-y-4">
            {quests.items.map((quest) => (
              <div
                key={quest.title}
                className="flex items-center justify-between gap-4 border border-white/5 rounded-2xl px-4 py-3 bg-black/20"
              >
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
        <Card tone="ember" title={codex.title} subtitle={codex.subtitle}>
          <div className="space-y-4">
            {codex.entries.map((entry) => (
              <div key={entry.title} className="p-4 rounded-2xl bg-black/30 border border-white/10">
                <p className="text-sm text-white/60">{entry.title}</p>
                <p className="text-lg font-semibold">{entry.detail}</p>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        {relics.items.map((item) => {
          const Icon = relicIconMap[item.icon] || Sparkles;
          return (
            <Card key={item.label} tone="default" title={item.label}>
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-2xl bg-white/10 border border-white/10">
                  <Icon size={24} className="text-accent" />
                </div>
                <div>
                  <p className="text-xl font-semibold">{item.value}</p>
                  <p className="text-sm text-white/60">{relics.statusLabel}</p>
                </div>
              </div>
            </Card>
          );
        })}
        <Card tone="moss" title={relics.battlePlan.title} subtitle={relics.battlePlan.subtitle}>
          <ul className="text-sm text-white/80 space-y-1 list-disc ml-5">
            {relics.battlePlan.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
        <Card tone="aurora" title={relics.signals.title} subtitle={relics.signals.subtitle}>
          <div className="flex flex-col gap-3 text-sm">
            {relics.signals.items.map((signal, idx) => {
              const Icon = signalIconMap[signal.icon] || (idx % 2 ? Swords : Sparkles);
              return (
                <span key={idx} className="inline-flex items-center gap-2">
                  <Icon size={16} className={signal.icon === "swords" ? "text-rose-300" : "text-accent"} />
                  {signal.text}
                </span>
              );
            })}
          </div>
        </Card>
      </section>
    </Layout>
  );
}
