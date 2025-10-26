import Layout from "../../components/Layout";
import Card from "../../components/Card";
import Button from "../../components/Button";
import { useRouter } from "next/router";
import { toast } from "sonner";
import { Missions } from "../../lib/api";
import { useEffect, useState } from "react";

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

  const onStart = async () => {
    try {
      await Missions.start(id);
      const updated = await Missions.get(id);
      setMission(updated);
      toast.success("Mission started", { description: "Good luck!" });
    } catch (e) {
      const msg = e?.response?.data?.detail || "Cannot start mission";
      toast.error("Start failed", { description: msg });
    }
  };

  const onComplete = async () => {
    try {
      const res = await Missions.complete(id);
      const updated = await Missions.get(id);
      setMission(updated);
      const xp = res?.xp_added ?? 0;
      toast.success("Mission completed", {
        description: xp ? `+${xp} XP gained` : "No XP this time",
      });
    } catch (e) {
      const msg = e?.response?.data?.detail || "Cannot complete mission";
      toast.error("Complete failed", { description: msg });
    }
  };

  const prereqList = (mission?.prerequisites || [])
    .map((p) => p.title)
    .join(", ");

  return (
    <Layout>
      <div className="mb-2 text-sm text-white/60">
        Mission #{mission?.id || id}
      </div>
      <h1 className="text-2xl font-semibold mb-4">{mission?.title || "..."}</h1>
      <div className="grid md:grid-cols-3 gap-6">
        <Card
          title="Description"
          subtitle={`Prerequisites: ${prereqList || "—"}`}
        >
          <p className="text-sm text-white/80">
            {mission?.description || "..."}
          </p>
        </Card>
        <Card title="Reward" subtitle={`+${mission?.xp_reward ?? 0} XP`}>
          <div className="text-3xl text-gold">
            +{mission?.xp_reward ?? 0} XP
          </div>
        </Card>
        <Card title="Actions">
          <div className="flex gap-2">
            <Button onClick={onStart}>Start</Button>
            <Button variant="outline" onClick={onComplete}>
              Complete
            </Button>
          </div>
        </Card>
      </div>
      <div className="mt-6">
        <Button variant="outline" onClick={() => router.back()}>
          Back
        </Button>
      </div>
    </Layout>
  );
}
