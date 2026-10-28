import { useEffect, useId, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../../components/Layout";
import Button from "../../components/Button";
import DemoButton from "../../components/DemoButton";
import EmptyState from "../../components/EmptyState";
import TemplatePicker from "../../components/TemplatePicker";
import { Studio as StudioAPI, Profile as ProfileAPI } from "../../lib/api";
import { COURSE_TEMPLATES } from "../../lib/studioTemplates";
import logger from "../../lib/logger";
import { useI18n } from "../../lib/i18n";
import { unit } from "../../lib/plural";
import {
  BookOpen,
  GraduationCap,
  Layers,
  Lock,
  Plus,
  Swords,
  X,
} from "lucide-react";
import { canTeach } from "../../lib/roles";

const inputCls =
  "w-full rounded-xl border border-border bg-panel px-3.5 py-2.5 text-sm text-text placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-primary/50";

// Карточка одного курса в списке студии.
function CourseCard({ track, onOpen, t, language }) {
  return (
    <button
      onClick={onOpen}
      className="text-left bg-surface border border-border rounded-3xl p-5 shadow-sm hover:border-primary/40 transition-colors group"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div
          className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border"
          style={{
            color: track.color_theme || "var(--primary)",
            borderColor: "var(--border)",
            background: "var(--panel)",
          }}
        >
          <BookOpen size={18} />
        </div>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${
            track.is_active
              ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-700 dark:text-emerald-400"
              : "border-border bg-panel text-muted"
          }`}
        >
          {track.is_active ? t("studio.active") : t("studio.draft")}
        </span>
      </div>
      <p className="text-base font-semibold text-text truncate">
        {track.title_ru || track.title_en || "—"}
      </p>
      {track.title_en && track.title_ru ? (
        <p className="text-xs text-muted truncate mb-3">{track.title_en}</p>
      ) : (
        <div className="mb-3" />
      )}
      <div className="flex items-center gap-4 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <Layers size={13} /> {track.locations_count} {unit(t, language, "section", track.locations_count)}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Swords size={13} /> {track.missions_count} {unit(t, language, "mission", track.missions_count)}
        </span>
      </div>
    </button>
  );
}

export default function StudioIndexPage() {
  const router = useRouter();
  const { t, language } = useI18n();
  const uid = useId();
  const [allowed, setAllowed] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tracks, setTracks] = useState([]);
  const [creating, setCreating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ title_ru: "", title_en: "", description_ru: "" });
  const [template, setTemplate] = useState(null);
  const [error, setError] = useState("");

  const pickTemplate = (preset) => {
    setForm({ ...form, ...preset.form });
    setTemplate(preset.id);
    setError("");
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await ProfileAPI.me();
        const isStaff = canTeach(me);
        if (cancelled) return;
        if (!isStaff) {
          setAllowed(false);
          setLoading(false);
          return;
        }
        setAllowed(true);
        const rows = await StudioAPI.tracks.list();
        if (!cancelled) setTracks(rows);
      } catch (e) {
        if (e?.response?.status === 403) {
          if (!cancelled) setAllowed(false);
        } else {
          logger.error("Studio load failed:", e);
          if (!cancelled) setError(t("studio.loadError"));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.title_ru.trim() && !form.title_en.trim()) {
      setError(t("studio.form.titleRequired"));
      return;
    }
    setSubmitting(true);
    try {
      const created = await StudioAPI.tracks.create({
        title_ru: form.title_ru.trim(),
        title_en: form.title_en.trim(),
        description_ru: form.description_ru.trim(),
      });
      router.push(`/studio/${created.id}`);
    } catch (e2) {
      logger.error("Course create failed:", e2);
      setError(t("studio.saveError"));
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="max-w-6xl mx-auto pt-24 pb-16 px-4">
          <div className="h-9 w-72 bg-panel rounded-lg animate-pulse mb-3" />
          <div className="h-4 w-96 bg-panel rounded animate-pulse mb-8" />
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-36 bg-surface border border-border rounded-3xl animate-pulse"
              />
            ))}
          </div>
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
          <h1 className="text-2xl font-display font-bold text-text mb-3">
            {t("studio.staffOnly")}
          </h1>
          <p className="text-muted mb-8">{t("studio.staffOnlyHint")}</p>
          <Button onClick={() => router.push("/")} variant="outline">
            {t("studio.backHome")}
          </Button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto pt-24 pb-16 px-4">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary/10 border border-primary/20">
                <GraduationCap size={22} className="text-primary" />
              </div>
              <h1 className="text-3xl md:text-4xl font-display font-bold text-text">
                {t("studio.title")}
              </h1>
            </div>
            <p className="text-muted">{t("studio.subtitle")}</p>
          </div>
          {!creating && (
            <Button onClick={() => setCreating(true)}>
              <Plus size={18} /> {t("studio.newCourse")}
            </Button>
          )}
        </div>

        {creating && (
          <form
            onSubmit={submit}
            className="bg-surface border border-border rounded-3xl p-5 sm:p-6 shadow-sm mb-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-text">
                {t("studio.newCourse")}
              </h2>
              <button
                type="button"
                onClick={() => {
                  setCreating(false);
                  setError("");
                }}
                className="text-muted hover:text-text"
                aria-label={t("studio.form.cancel")}
              >
                <X size={18} />
              </button>
            </div>
            <TemplatePicker
              templates={COURSE_TEMPLATES}
              picked={template}
              onPick={pickTemplate}
              t={t}
              language={language}
            />
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor={`${uid}-title_ru`} className="block text-xs font-semibold text-muted mb-1.5">
                  {t("studio.form.titleRu")}
                </label>
                <input
                  id={`${uid}-title_ru`}
                  className={inputCls}
                  value={form.title_ru}
                  placeholder={t("studio.form.titlePlaceholder")}
                  onChange={(e) => setForm({ ...form, title_ru: e.target.value })}
                  // eslint-disable-next-line jsx-a11y/no-autofocus -- поле появляется после нажатия кнопки
                  autoFocus
                />
              </div>
              <div>
                <label htmlFor={`${uid}-title_en`} className="block text-xs font-semibold text-muted mb-1.5">
                  {t("studio.form.titleEn")}
                </label>
                <input
                  id={`${uid}-title_en`}
                  className={inputCls}
                  value={form.title_en}
                  onChange={(e) => setForm({ ...form, title_en: e.target.value })}
                />
              </div>
            </div>
            <div className="mt-4">
              <label htmlFor={`${uid}-desc`} className="block text-xs font-semibold text-muted mb-1.5">
                {t("studio.form.descRu")}
              </label>
              <textarea
                id={`${uid}-desc`}
                className={`${inputCls} min-h-[80px] resize-y`}
                value={form.description_ru}
                onChange={(e) =>
                  setForm({ ...form, description_ru: e.target.value })
                }
              />
            </div>
            {error && <p className="text-sm text-error mt-3">{error}</p>}
            <div className="flex gap-3 justify-end mt-5">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setCreating(false);
                  setError("");
                }}
              >
                {t("studio.form.cancel")}
              </Button>
              <Button type="submit" loading={submitting}>
                {submitting ? t("studio.form.creating") : t("studio.form.create")}
              </Button>
            </div>
          </form>
        )}

        {error && !creating && <p className="text-sm text-error mb-4">{error}</p>}

        {tracks.length === 0 && !creating ? (
          <EmptyState icon={BookOpen} title={t("pilot.empty.studioTitle")} hint={t("pilot.empty.studioHint")}>
            <Button icon={Plus} onClick={() => setCreating(true)}>
              {t("studio.newCourse")}
            </Button>
            <DemoButton t={t} />
          </EmptyState>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {tracks.map((track) => (
              <CourseCard
                language={language}
                key={track.id}
                track={track}
                t={t}
                onOpen={() => router.push(`/studio/${track.id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
