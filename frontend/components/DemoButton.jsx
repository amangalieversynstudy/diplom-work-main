import { useState } from "react";
import { useRouter } from "next/router";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import Button from "./Button";
import { Studio as StudioAPI } from "../lib/api";
import { serverMessage } from "../lib/apiErrors";
import logger from "../lib/logger";

// «Развернуть демо-пример»: сервер собирает показательный курс (backend/game/demo_course.py), кнопка ведёт в него.
export default function DemoButton({ t, variant = "secondary", className = "" }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const deploy = async () => {
    setBusy(true);
    try {
      const course = await StudioAPI.tracks.demo();
      toast.success(course.created ? t("pilot.demo.created") : t("pilot.demo.exists"));
      router.push(`/studio/${course.id}`);
    } catch (error) {
      logger.error("Demo course failed:", error);
      toast.error(serverMessage(error, t("pilot.demo.error")));
      setBusy(false);
    }
  };

  return (
    <Button variant={variant} icon={Sparkles} loading={busy} onClick={deploy} className={className}>
      {busy ? t("pilot.demo.busy") : t("pilot.demo.button")}
    </Button>
  );
}
