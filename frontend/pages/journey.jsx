import { useEffect, useState } from "react";
import { toast } from "sonner";
import Layout from "../components/Layout";
import JourneyView from "../components/JourneyView";
import { Learning } from "../lib/api";
import { useI18n } from "../lib/i18n";
import logger from "../lib/logger";

// «Мой путь»: личный экран ученика. Вся картина рисуется общим компонентом,
// тем же, что показывает преподавателю его ученика.
export default function Journey() {
  const { t, language } = useI18n();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    Learning.me()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        logger.error("journey load failed", err);
        if (active) {
          setFailed(true);
          toast.error(t("journey.loadFail"));
        }
      });
    return () => {
      active = false;
    };
    // язык меняет только названия шагов, поэтому перезагружаем при его смене
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

  return (
    <Layout>
      {data ? (
        <JourneyView data={data} mode="student" />
      ) : (
        <div className="mx-auto max-w-5xl pt-16">
          {failed ? (
            <p role="alert" className="text-center text-muted">
              {t("journey.loadFail")}
            </p>
          ) : (
            <div className="space-y-4" aria-busy="true">
              <div className="h-40 animate-pulse rounded-3xl border border-border bg-panel" />
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-28 animate-pulse rounded-2xl border border-border bg-panel" />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Layout>
  );
}
