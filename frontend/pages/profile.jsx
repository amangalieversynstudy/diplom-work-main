import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import XPBar from "../components/XPBar";
import { Profile as ProfileAPI } from "../lib/api";
import Skeleton from "../components/Skeleton";
import { toast } from "sonner";

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

  return (
    <Layout>
      <h1 className="text-2xl font-semibold mb-4">Profile</h1>
      {loading ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="grid md:grid-cols-2 gap-6">
          <Card title="Your Progress" subtitle={`${username} • Level ${level}`}>
            <XPBar current={xp % 100} max={100} />
            <p className="text-sm text-white/70 mt-2">Total XP: {xp}</p>
          </Card>
          <Card title="Account" subtitle={email}>
            <p className="text-sm text-white/70">
              Manage your account details.
            </p>
          </Card>
        </div>
      )}
    </Layout>
  );
}
