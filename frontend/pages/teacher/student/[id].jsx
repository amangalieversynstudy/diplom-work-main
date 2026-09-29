import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { toast } from "sonner";
import Layout from "../../../components/Layout";
import JourneyView from "../../../components/JourneyView";
import { Teacher as TeacherAPI } from "../../../lib/api";
import { useI18n } from "../../../lib/i18n";
import logger from "../../../lib/logger";

// Один ученик глазами преподавателя: та же картина, что видит сам ученик на «Моём пути».
// Сервер отдаёт её только по курсам этого преподавателя; чужой ученик даёт 404.
export default function TeacherStudentPage() {
  const router = useRouter();
  const { id } = router.query;
  const { t, language } = useI18n();
  const [data, setData] = useState(null);
  const [failure, setFailure] = useState(null);

  useEffect(() => {
    if (!id) return undefined;
    let active = true;
    setFailure(null);
    TeacherAPI.studentLearning(id)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        logger.error("teacher student load failed", err);
        const status = err?.response?.status;
        if (active) {
          setFailure(status === 404 || status === 403 ? "notFound" : "failed");
          if (status !== 404 && status !== 403) toast.error(t("teacherStudent.loadFail"));
        }
      });
    return () => {
      active = false;
    };
    // язык меняет только названия шагов, поэтому перезагружаем при его смене
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, language]);

  return (
    <Layout>
      {data ? (
        <JourneyView data={data} mode="teacher" backHref="/teacher" />
      ) : failure ? (
        <div className="mx-auto max-w-2xl pt-24 text-center">
          <p role="alert" className="text-lg text-muted">
            {t(failure === "notFound" ? "teacherStudent.notFound" : "teacherStudent.loadFail")}
          </p>
          <button
            type="button"
            onClick={() => router.push("/teacher")}
            className="mt-6 inline-flex min-h-[44px] items-center rounded-full border border-border px-5 py-2.5 font-medium text-text transition-colors hover:bg-panel"
          >
            {t("teacherStudent.back")}
          </button>
        </div>
      ) : (
        <div className="mx-auto max-w-5xl pt-16" aria-busy="true">
          <div className="h-40 animate-pulse rounded-3xl border border-border bg-panel" />
        </div>
      )}
    </Layout>
  );
}
