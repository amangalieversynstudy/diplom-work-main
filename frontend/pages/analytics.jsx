import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import Button from "../components/Button";
import LearningMetrics from "../components/LearningMetrics";
import { Profile as ProfileAPI } from "../lib/api";
import logger from "../lib/logger";
import { useI18n } from "../lib/i18n";
import { BarChart3, Lock } from "lucide-react";

// Одна панель метрик вместо двух: раньше рядом стояли «общие итоги платформы» и
// «эффективность обучения», и «среднее число попыток» в них было разным.
export default function AnalyticsPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [allowed, setAllowed] = useState(null); // null = проверяем, false = не staff

  useEffect(() => {
    let cancelled = false;
    ProfileAPI.me()
      .then((me) => {
        if (!cancelled) setAllowed(!!(me?.is_staff ?? me?.user?.is_staff));
      })
      .catch((error) => {
        // 401 перехватит axios-интерсептор (редирект на /login).
        logger.error("Analytics gate failed:", error);
        if (!cancelled) setAllowed(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (allowed === null) {
    return (
      <Layout>
        <div className="max-w-6xl mx-auto pt-24 pb-16 px-4" aria-busy="true">
          <div className="h-9 w-72 bg-panel rounded-lg animate-pulse mb-3" />
          <div className="h-4 w-96 bg-panel rounded animate-pulse" />
        </div>
      </Layout>
    );
  }

  if (allowed === false) {
    return (
      <Layout>
        <div className="max-w-2xl mx-auto pt-32 pb-16 px-4 text-center">
          <div className="grid h-16 w-16 mx-auto place-items-center rounded-2xl bg-panel border border-border mb-6">
            <Lock size={28} className="text-muted" />
          </div>
          <h1 className="text-2xl font-display font-bold text-text mb-3">{t("analytics.staffOnly")}</h1>
          <p className="text-muted mb-8">{t("analytics.staffOnlyHint")}</p>
          <Button onClick={() => router.push("/")} variant="outline">
            {t("analytics.backHome")}
          </Button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto pt-24 pb-16 px-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary/10 border border-primary/20">
            <BarChart3 size={22} className="text-primary" />
          </div>
          <h1 className="text-3xl md:text-4xl font-display font-bold text-text">{t("analytics.title")}</h1>
        </div>
        <p className="text-muted mb-8">{t("analytics.subtitle")}</p>
        <LearningMetrics />
      </div>
    </Layout>
  );
}
