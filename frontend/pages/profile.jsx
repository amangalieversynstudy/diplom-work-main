import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import XPBar from "../components/XPBar";
import { Profile as ProfileAPI } from "../lib/api";
import Skeleton from "../components/Skeleton";
import { toast } from "sonner";

const attributes = [
  { label: "Wisdom", key: "wisdom" },
  { label: "Dexterity", key: "dex" },
  { label: "Focus", key: "focus" },
];

export default function Profile() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    ProfileAPI.me()
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        const msg = e?.response?.data?.detail || "Failed to load profile";
        toast.error(msg);
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const username = data?.username ?? "Adventurer";
  const email = data?.email ?? "—";
  const xp = data?.profile?.xp ?? 0;
  const level = data?.profile?.level ?? 1;
  const classRole = data?.profile?.class_role || "Unaligned";

  if (loading) {
    return (
      <Layout>
        <Skeleton className="h-48" />
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mb-4">
        <p className="text-xs uppercase tracking-[0.4em] text-white/60">
          Character Sheet
        </p>
        <h1 className="text-3xl font-display">{username}</h1>
      </div>
      <section className="grid gap-6 md:grid-cols-[1.3fr,0.7fr] mb-6">
        <Card tone="aurora" title={`Level ${level}`} subtitle={`Class: ${classRole}`}>
          <XPBar current={xp % 100} max={100} />
          <p className="text-sm text-white/70 mt-3">Total XP: {xp}</p>
        </Card>
        <Card tone="night" title="Account" subtitle={email}>
          <p className="text-sm text-white/70">
            Use DRF auth endpoints to update credentials and tokens.
          </p>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-3 mb-6">
        {attributes.map((attr) => (
          <Card key={attr.key} tone="default" title={attr.label}>
            <p className="text-3xl font-semibold">
              {((xp % 50) + level * 3) % 18}
            </p>
            <p className="text-xs text-white/60 uppercase tracking-[0.3em]">
              Attribute
            </p>
          </Card>
        ))}
      </section>

      <section className="grid gap-6 md:grid-cols-[1.1fr,0.9fr]">
        <Card tone="moss" title="Talents" subtitle="Unlocked bonuses">
          <ul className="list-disc ml-5 text-sm text-white/80 space-y-1">
            <li>XP gain +10% when missions chained</li>
            <li>Celery monitoring available from dashboard</li>
            <li>CI smoke tests visible in Codex</li>
          </ul>
        </Card>
        <Card tone="ember" title="Inventory" subtitle="Key artifacts">
          <ul className="text-sm text-white/80 space-y-2">
            <li>✨ JWT Token — valid</li>
            <li>📜 Postman collection synced</li>
            <li>🗝️ GitLab deploy key stored in vault</li>
          </ul>
        </Card>
      </section>
    </Layout>
  );
}
