import { useEffect, useMemo, useState } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import XPBar from "../components/XPBar";
import { Profile as ProfileAPI } from "../lib/api";
import Skeleton from "../components/Skeleton";
import { toast } from "sonner";
import { useDictionary } from "../lib/i18n";

export default function Profile() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const dict = useDictionary();
  const copy = dict.profile;
  const attributes = useMemo(
    () => [
      { label: copy.attributes.wisdom, key: "wisdom" },
      { label: copy.attributes.dex, key: "dex" },
      { label: copy.attributes.focus, key: "focus" },
    ],
    [copy.attributes]
  );

  useEffect(() => {
    let active = true;
    ProfileAPI.me()
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        const msg = e?.response?.data?.detail || copy.errors.load;
        toast.error(msg);
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [copy.errors.load]);

  const username = data?.username ?? dict.common.none;
  const email = data?.email ?? dict.common.none;
  const xp = data?.profile?.xp ?? 0;
  const level = data?.profile?.level ?? 1;
  const classRole = data?.profile?.class_role || dict.common.none;

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
          {copy.title}
        </p>
        <h1 className="text-3xl font-display">{username}</h1>
      </div>
      <section className="grid gap-6 md:grid-cols-[1.3fr,0.7fr] mb-6">
  <Card tone="aurora" title={`${dict.sheet.level} ${level}`} subtitle={`${copy.classLabel}: ${classRole}`}>
          <XPBar current={xp % 100} max={100} />
          <p className="text-sm text-white/70 mt-3">{dict.sheet.totalXp}: {xp}</p>
        </Card>
        <Card tone="night" title={copy.account} subtitle={email}>
          <p className="text-sm text-white/70">{copy.accountHelper}</p>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-3 mb-6">
        {attributes.map((attr) => (
          <Card key={attr.key} tone="default" title={attr.label}>
            <p className="text-3xl font-semibold">
              {((xp % 50) + level * 3) % 18}
            </p>
            <p className="text-xs text-white/60 uppercase tracking-[0.3em]">
              {copy.attributesLabel}
            </p>
          </Card>
        ))}
      </section>

      <section className="grid gap-6 md:grid-cols-[1.1fr,0.9fr]">
        <Card tone="moss" title={copy.talents.title} subtitle={copy.talents.subtitle}>
          <ul className="list-disc ml-5 text-sm text-white/80 space-y-1">
            {copy.talents.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
        <Card tone="ember" title={copy.inventory.title} subtitle={copy.inventory.subtitle}>
          <ul className="text-sm text-white/80 space-y-2">
            {copy.inventory.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
      </section>
    </Layout>
  );
}
