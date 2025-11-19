import Layout from "../../components/Layout";
import Card from "../../components/Card";
import Button from "../../components/Button";
import Badge from "../../components/Badge";
import { useRouter } from "next/router";
import { toast } from "sonner";
import { Missions, missionStatus } from "../../lib/api";
import { useEffect, useState } from "react";
import { ScrollText, Sword, Sparkles } from "lucide-react";

export default function MissionDetail() {
  const router = useRouter();
  const { id } = router.query;
  const [mission, setMission] = useState(null);

  useEffect(() => {
    if (!id) return;
    Missions.get(id)
      .then(setMission)
      .catch(() => toast.error("Failed to load mission"));
  }, [id]);

  const refreshMission = async () => {
    const updated = await Missions.get(id);
    setMission(updated);
  };

  const onStart = async () => {
    try {
      await Missions.start(id);
      await refreshMission();
      toast.success("Mission started", { description: "Good luck!" });
    } catch (e) {
      const msg = e?.response?.data?.detail || "Cannot start mission";
      toast.error("Start failed", { description: msg });
    }
  };

  const onComplete = async () => {
    try {
      const res = await Missions.complete(id);
      await refreshMission();
      const xp = res?.xp_added ?? 0;
      toast.success("Mission completed", {
        description: xp ? `+${xp} XP gained` : "No XP this time",
      });
    } catch (e) {
      const msg = e?.response?.data?.detail || "Cannot complete mission";
      toast.error("Complete failed", { description: msg });
    }
  };

  const prereq = mission?.prerequisites?.length
    ? mission.prerequisites.map((p) => p.title).join(", ")
    : "None";
  const status = mission ? missionStatus(mission) : "locked";
  const completed = mission?.user_progress?.completed;
  const started = mission?.user_progress?.started_at;

  return (
    <Layout>
      <div className="text-xs uppercase tracking-[0.35em] text-white/60 mb-2">
        Mission #{mission?.id || id}
      </div>
      <section className="grid gap-6 md:grid-cols-[1.4fr,0.6fr] mb-6">
        <Card tone="aurora" title={mission?.title || "..."} subtitle="Quest dossier">
          <p className="text-sm text-white/80 leading-relaxed">
            {mission?.description || "Mission intel loading"}
          </p>
          <div className="flex flex-wrap gap-2 mt-4 text-xs">
            <Badge status={status}>{status}</Badge>
            {completed && <Badge status="completed">Completed</Badge>}
          </div>
        </Card>
        <Card tone="night" title="Reward" subtitle="XP payout">
          <div className="text-4xl text-gold font-display">
            +{mission?.xp_reward ?? 0} XP
          </div>
          <p className="text-sm text-white/70 mt-2">
            Bonus scales with streaks. Complete prerequisites for full credit.
          </p>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-3 mb-6">
        <Card tone="default" title="Prerequisites" subtitle={prereq}>
          <div className="text-sm text-white/75 space-y-2">
            <p>All previous intro quests must be cleared before unlocking this node.</p>
            <p className="text-white/60 flex items-center gap-2 text-xs uppercase tracking-[0.3em]">
              <ScrollText size={16} /> Chapter: {mission?.chapter || "Python"}
            </p>
          </div>
        </Card>
        <Card tone="ember" title="Strategy" subtitle="Suggested flow">
          <ul className="text-sm text-white/80 space-y-1 list-disc ml-5">
            <li>Review docs or class materials</li>
            <li>Run backend tests locally</li>
            <li>Commit progress to unlock Gate</li>
          </ul>
        </Card>
        <Card tone="moss" title="State" subtitle="Mission status">
          <div className="space-y-2 text-sm">
            <p>Started: {started ? new Date(started).toLocaleString() : "—"}</p>
            <p>Completed: {completed ? "Yes" : "Not yet"}</p>
          </div>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-[1.1fr,0.9fr]">
        <Card tone="night" title="Actions" subtitle="Trigger quest events">
          <div className="flex flex-wrap gap-3">
            <Button onClick={onStart}>
              <Sword size={18} /> Start
            </Button>
            <Button variant="outline" onClick={onComplete}>
              <Sparkles size={18} /> Complete
            </Button>
            <Button variant="ghost" onClick={() => router.back()}>
              Back
            </Button>
          </div>
        </Card>
        <Card tone="aurora" title="Mission log" subtitle="Telemetry">
          <ul className="text-sm text-white/80 space-y-2">
            <li>🔁 API-backed start/complete endpoints mocked locally</li>
            <li>🎯 XP applied to player profile instantly</li>
            <li>🧪 Retry: handles DRF validation errors gracefully</li>
          </ul>
        </Card>
      </section>
    </Layout>
  );
}
