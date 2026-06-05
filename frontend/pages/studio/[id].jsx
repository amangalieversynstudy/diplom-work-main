import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../../components/Layout";
import Button from "../../components/Button";
import ConfirmModal from "../../components/ConfirmModal";
import { Studio as StudioAPI, Profile as ProfileAPI } from "../../lib/api";
import logger from "../../lib/logger";
import { useI18n } from "../../lib/i18n";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronRight,
  Layers,
  Lock,
  Pencil,
  Plus,
  Save,
  Swords,
  Trash2,
  X,
} from "lucide-react";

const inputCls =
  "w-full rounded-xl border border-border bg-panel px-3.5 py-2.5 text-sm text-text placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-primary/50";

const sortByOrder = (arr) =>
  [...arr].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

// Одна миссия внутри раздела: просмотр + инлайн-редактирование.
function MissionRow({ mission, t, onReload, setConfirm, setError }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    title_ru: mission.title_ru || "",
    title_en: mission.title_en || "",
    xp_reward: mission.xp_reward ?? 10,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm({
      title_ru: mission.title_ru || "",
      title_en: mission.title_en || "",
      xp_reward: mission.xp_reward ?? 10,
    });
  }, [mission.title_ru, mission.title_en, mission.xp_reward]);

  const save = async () => {
    if (!form.title_ru.trim() && !form.title_en.trim()) return;
    setSaving(true);
    try {
      await StudioAPI.missions.update(mission.id, {
        title_ru: form.title_ru.trim(),
        title_en: form.title_en.trim(),
        xp_reward: Number(form.xp_reward) || 0,
      });
      setEditing(false);
      await onReload();
    } catch (e) {
      logger.error("Mission save failed:", e);
      setError(t("studio.saveError"));
    } finally {
      setSaving(false);
    }
  };

  const del = () =>
    setConfirm({
      title: t("studio.editor.confirmDeleteMissionTitle"),
      message: t("studio.editor.confirmDeleteMsg"),
      danger: true,
      confirmLabel: t("studio.editor.delete"),
      onConfirm: async () => {
        try {
          await StudioAPI.missions.remove(mission.id);
          await onReload();
        } catch (e) {
          logger.error("Mission delete failed:", e);
          setError(t("studio.saveError"));
        }
      },
    });

  if (editing) {
    return (
      <div className="rounded-xl border border-border bg-panel/60 p-3">
        <div className="grid sm:grid-cols-[1fr_1fr_auto] gap-2 items-start">
          <input
            className={inputCls}
            value={form.title_ru}
            placeholder={t("studio.editor.missionNameRu")}
            onChange={(e) => setForm({ ...form, title_ru: e.target.value })}
            autoFocus
          />
          <input
            className={inputCls}
            value={form.title_en}
            placeholder={t("studio.editor.missionNameEn")}
            onChange={(e) => setForm({ ...form, title_en: e.target.value })}
          />
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <Swords size={13} className="text-amber-400" />
              <input
                type="number"
                min={0}
                className={`${inputCls} w-20`}
                value={form.xp_reward}
                onChange={(e) =>
                  setForm({ ...form, xp_reward: e.target.value })
                }
                aria-label={t("studio.editor.xp")}
              />
            </div>
          </div>
        </div>
        <div className="flex gap-2 justify-end mt-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => setEditing(false)}
          >
            {t("studio.editor.cancel")}
          </Button>
          <Button type="button" onClick={save} disabled={saving}>
            <Check size={16} />
            {saving ? t("studio.editor.saving") : t("studio.editor.save")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="group flex items-center gap-3 rounded-xl border border-border bg-panel/40 px-3.5 py-2.5">
      <Swords size={15} className="shrink-0 text-muted" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-text">
          {mission.title_ru || mission.title_en || "—"}
        </p>
        {mission.title_en && mission.title_ru ? (
          <p className="truncate text-xs text-muted">{mission.title_en}</p>
        ) : null}
      </div>
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-amber-400/20 bg-amber-400/10 px-2 py-0.5 text-[11px] font-semibold text-amber-400">
        {mission.xp_reward ?? 0} {t("studio.editor.xp")}
      </span>
      <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={() => setEditing(true)}
          className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-panel hover:text-text"
          aria-label={t("studio.editor.edit")}
        >
          <Pencil size={15} />
        </button>
        <button
          onClick={del}
          className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-error/10 hover:text-error"
          aria-label={t("studio.editor.delete")}
        >
          <Trash2 size={15} />
        </button>
      </div>
    </div>
  );
}

// Раздел курса (Location) + его миссии.
function SectionCard({
  section,
  t,
  onReloadMissions,
  onReloadSections,
  setConfirm,
  setError,
}) {
  const [expanded, setExpanded] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    title_ru: section.title_ru || "",
    title_en: section.title_en || "",
  });
  const [savingEdit, setSavingEdit] = useState(false);
  const [addingMission, setAddingMission] = useState(false);
  const [missionForm, setMissionForm] = useState({
    title_ru: "",
    title_en: "",
    xp_reward: 10,
  });
  const [missionBusy, setMissionBusy] = useState(false);

  useEffect(() => {
    setEditForm({
      title_ru: section.title_ru || "",
      title_en: section.title_en || "",
    });
  }, [section.title_ru, section.title_en]);

  const missions = section.missions || [];

  const saveEdit = async () => {
    if (!editForm.title_ru.trim() && !editForm.title_en.trim()) return;
    setSavingEdit(true);
    try {
      await StudioAPI.locations.update(section.id, {
        title_ru: editForm.title_ru.trim(),
        title_en: editForm.title_en.trim(),
      });
      setEditing(false);
      await onReloadSections();
    } catch (e) {
      logger.error("Section save failed:", e);
      setError(t("studio.saveError"));
    } finally {
      setSavingEdit(false);
    }
  };

  const del = () =>
    setConfirm({
      title: t("studio.editor.confirmDeleteSectionTitle"),
      message: t("studio.editor.confirmDeleteMsg"),
      danger: true,
      confirmLabel: t("studio.editor.delete"),
      onConfirm: async () => {
        try {
          await StudioAPI.locations.remove(section.id);
          await onReloadSections();
        } catch (e) {
          logger.error("Section delete failed:", e);
          setError(t("studio.saveError"));
        }
      },
    });

  const addMission = async (e) => {
    e.preventDefault();
    if (!missionForm.title_ru.trim() && !missionForm.title_en.trim()) return;
    setMissionBusy(true);
    try {
      await StudioAPI.missions.create({
        location: section.id,
        title_ru: missionForm.title_ru.trim(),
        title_en: missionForm.title_en.trim(),
        xp_reward: Number(missionForm.xp_reward) || 0,
        order: missions.length,
      });
      setMissionForm({ title_ru: "", title_en: "", xp_reward: 10 });
      setAddingMission(false);
      await onReloadMissions(section.id);
    } catch (e2) {
      logger.error("Mission create failed:", e2);
      setError(t("studio.saveError"));
    } finally {
      setMissionBusy(false);
    }
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-sm">
      <div className="flex items-center gap-3 p-4">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-muted hover:bg-panel hover:text-text"
          aria-label={expanded ? "collapse" : "expand"}
        >
          {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </button>

        {editing ? (
          <div className="flex flex-1 flex-col gap-2 sm:flex-row">
            <input
              className={inputCls}
              value={editForm.title_ru}
              placeholder={t("studio.editor.sectionNameRu")}
              onChange={(e) =>
                setEditForm({ ...editForm, title_ru: e.target.value })
              }
              autoFocus
            />
            <input
              className={inputCls}
              value={editForm.title_en}
              placeholder={t("studio.editor.sectionNameEn")}
              onChange={(e) =>
                setEditForm({ ...editForm, title_en: e.target.value })
              }
            />
          </div>
        ) : (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="min-w-0 flex-1 text-left"
          >
            <p className="truncate text-base font-semibold text-text">
              {section.title_ru || section.title_en || "—"}
            </p>
            <p className="text-xs text-muted">
              {missions.length} {t("studio.editor.missions").toLowerCase()}
            </p>
          </button>
        )}

        <div className="flex shrink-0 items-center gap-1">
          {editing ? (
            <>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setEditing(false)}
              >
                {t("studio.editor.cancel")}
              </Button>
              <Button type="button" onClick={saveEdit} disabled={savingEdit}>
                <Check size={16} />
                {savingEdit
                  ? t("studio.editor.saving")
                  : t("studio.editor.save")}
              </Button>
            </>
          ) : (
            <>
              <button
                onClick={() => setEditing(true)}
                className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-panel hover:text-text"
                aria-label={t("studio.editor.edit")}
              >
                <Pencil size={15} />
              </button>
              <button
                onClick={del}
                className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-error/10 hover:text-error"
                aria-label={t("studio.editor.delete")}
              >
                <Trash2 size={15} />
              </button>
            </>
          )}
        </div>
      </div>

      {expanded && (
        <div className="space-y-2 border-t border-border bg-bg/40 p-4">
          {missions.length === 0 && !addingMission ? (
            <p className="py-2 text-center text-sm text-muted">
              {t("studio.editor.noMissions")}
            </p>
          ) : (
            missions.map((m) => (
              <MissionRow
                key={m.id}
                mission={m}
                t={t}
                onReload={() => onReloadMissions(section.id)}
                setConfirm={setConfirm}
                setError={setError}
              />
            ))
          )}

          {addingMission ? (
            <form
              onSubmit={addMission}
              className="rounded-xl border border-dashed border-border bg-panel/60 p-3"
            >
              <div className="grid items-start gap-2 sm:grid-cols-[1fr_1fr_auto]">
                <input
                  className={inputCls}
                  value={missionForm.title_ru}
                  placeholder={t("studio.editor.missionNameRu")}
                  onChange={(e) =>
                    setMissionForm({ ...missionForm, title_ru: e.target.value })
                  }
                  autoFocus
                />
                <input
                  className={inputCls}
                  value={missionForm.title_en}
                  placeholder={t("studio.editor.missionNameEn")}
                  onChange={(e) =>
                    setMissionForm({ ...missionForm, title_en: e.target.value })
                  }
                />
                <div className="flex items-center gap-1.5">
                  <Swords size={13} className="text-amber-400" />
                  <input
                    type="number"
                    min={0}
                    className={`${inputCls} w-20`}
                    value={missionForm.xp_reward}
                    onChange={(e) =>
                      setMissionForm({
                        ...missionForm,
                        xp_reward: e.target.value,
                      })
                    }
                    aria-label={t("studio.editor.xp")}
                  />
                </div>
              </div>
              <div className="mt-2 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setAddingMission(false);
                    setMissionForm({ title_ru: "", title_en: "", xp_reward: 10 });
                  }}
                >
                  {t("studio.editor.cancel")}
                </Button>
                <Button type="submit" disabled={missionBusy}>
                  {missionBusy
                    ? t("studio.editor.adding")
                    : t("studio.editor.add")}
                </Button>
              </div>
            </form>
          ) : (
            <button
              onClick={() => setAddingMission(true)}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-border py-2.5 text-sm font-medium text-muted hover:border-primary/40 hover:text-text"
            >
              <Plus size={16} /> {t("studio.editor.addMission")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function StudioEditorPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [allowed, setAllowed] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [track, setTrack] = useState(null);
  const [settings, setSettings] = useState({
    title_ru: "",
    title_en: "",
    description_ru: "",
    is_active: false,
  });
  const [savingSettings, setSavingSettings] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [sections, setSections] = useState([]);
  const [addingSection, setAddingSection] = useState(false);
  const [sectionForm, setSectionForm] = useState({ title_ru: "", title_en: "" });
  const [sectionBusy, setSectionBusy] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!router.isReady) return;
    const id = router.query.id;
    let cancelled = false;
    (async () => {
      try {
        const me = await ProfileAPI.me();
        const isStaff = !!(me?.is_staff ?? me?.user?.is_staff);
        if (cancelled) return;
        if (!isStaff) {
          setAllowed(false);
          setLoading(false);
          return;
        }
        setAllowed(true);
        const tr = await StudioAPI.tracks.get(id);
        if (cancelled) return;
        setTrack(tr);
        setSettings({
          title_ru: tr.title_ru || "",
          title_en: tr.title_en || "",
          description_ru: tr.description_ru || "",
          is_active: !!tr.is_active,
        });
        const locs = await StudioAPI.locations.list(id);
        const withMissions = await Promise.all(
          locs.map(async (loc) => {
            const missions = await StudioAPI.missions.list(loc.id);
            return { ...loc, missions: sortByOrder(missions) };
          })
        );
        if (!cancelled) setSections(sortByOrder(withMissions));
      } catch (e) {
        const status = e?.response?.status;
        if (status === 404 || status === 403) {
          if (!cancelled) setNotFound(true);
        } else if (status === 401) {
          if (!cancelled) setAllowed(false);
        } else {
          logger.error("Studio editor load failed:", e);
          if (!cancelled) setError(t("studio.loadError"));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router.isReady, router.query.id]);

  const reloadMissions = async (locId) => {
    const missions = await StudioAPI.missions.list(locId);
    setSections((prev) =>
      prev.map((s) =>
        s.id === locId ? { ...s, missions: sortByOrder(missions) } : s
      )
    );
  };

  const reloadSections = async () => {
    const locs = await StudioAPI.locations.list(track.id);
    const withMissions = await Promise.all(
      locs.map(async (loc) => {
        const missions = await StudioAPI.missions.list(loc.id);
        return { ...loc, missions: sortByOrder(missions) };
      })
    );
    setSections(sortByOrder(withMissions));
  };

  const saveSettings = async () => {
    setSavingSettings(true);
    setError("");
    try {
      const updated = await StudioAPI.tracks.update(track.id, {
        title_ru: settings.title_ru.trim(),
        title_en: settings.title_en.trim(),
        description_ru: settings.description_ru.trim(),
        is_active: settings.is_active,
      });
      setTrack(updated);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1800);
    } catch (e) {
      logger.error("Course save failed:", e);
      setError(t("studio.saveError"));
    } finally {
      setSavingSettings(false);
    }
  };

  const addSection = async (e) => {
    e.preventDefault();
    if (!sectionForm.title_ru.trim() && !sectionForm.title_en.trim()) return;
    setSectionBusy(true);
    try {
      await StudioAPI.locations.create({
        track: track.id,
        title_ru: sectionForm.title_ru.trim(),
        title_en: sectionForm.title_en.trim(),
        order: sections.length,
      });
      setSectionForm({ title_ru: "", title_en: "" });
      setAddingSection(false);
      await reloadSections();
    } catch (e2) {
      logger.error("Section create failed:", e2);
      setError(t("studio.saveError"));
    } finally {
      setSectionBusy(false);
    }
  };

  const deleteCourse = () =>
    setConfirm({
      title: t("studio.editor.confirmDeleteCourseTitle"),
      message: t("studio.editor.confirmDeleteCourseMsg"),
      danger: true,
      confirmLabel: t("studio.editor.delete"),
      onConfirm: async () => {
        try {
          await StudioAPI.tracks.remove(track.id);
          router.push("/studio");
        } catch (e) {
          logger.error("Course delete failed:", e);
          setError(t("studio.saveError"));
        }
      },
    });

  if (loading) {
    return (
      <Layout>
        <div className="max-w-5xl mx-auto pt-24 pb-16 px-4">
          <div className="h-5 w-40 bg-panel rounded animate-pulse mb-6" />
          <div className="h-9 w-80 bg-panel rounded-lg animate-pulse mb-8" />
          <div className="h-48 bg-surface border border-border rounded-3xl animate-pulse mb-6" />
          <div className="h-32 bg-surface border border-border rounded-3xl animate-pulse" />
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

  if (notFound) {
    return (
      <Layout>
        <div className="max-w-2xl mx-auto pt-32 pb-16 px-4 text-center">
          <p className="text-muted mb-8">{t("studio.editor.notFound")}</p>
          <Button onClick={() => router.push("/studio")} variant="outline">
            <ArrowLeft size={16} /> {t("studio.editor.back")}
          </Button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-5xl mx-auto pt-24 pb-16 px-4">
        <button
          onClick={() => router.push("/studio")}
          className="mb-5 inline-flex items-center gap-1.5 text-sm text-muted hover:text-text"
        >
          <ArrowLeft size={16} /> {t("studio.editor.back")}
        </button>

        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <h1 className="text-3xl md:text-4xl font-display font-bold text-text">
            {track?.title_ru || track?.title_en || "—"}
          </h1>
          <button
            onClick={deleteCourse}
            className="inline-flex items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-sm text-muted hover:border-error/40 hover:text-error"
          >
            <Trash2 size={15} /> {t("studio.editor.delete")}
          </button>
        </div>

        {/* Настройки курса */}
        <div className="mb-8 rounded-3xl border border-border bg-surface p-5 shadow-sm sm:p-6">
          <h2 className="mb-4 text-lg font-semibold text-text">
            {t("studio.editor.settings")}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-muted">
                {t("studio.form.titleRu")}
              </label>
              <input
                className={inputCls}
                value={settings.title_ru}
                onChange={(e) =>
                  setSettings({ ...settings, title_ru: e.target.value })
                }
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-muted">
                {t("studio.form.titleEn")}
              </label>
              <input
                className={inputCls}
                value={settings.title_en}
                onChange={(e) =>
                  setSettings({ ...settings, title_en: e.target.value })
                }
              />
            </div>
          </div>
          <div className="mt-4">
            <label className="mb-1.5 block text-xs font-semibold text-muted">
              {t("studio.form.descRu")}
            </label>
            <textarea
              className={`${inputCls} min-h-[80px] resize-y`}
              value={settings.description_ru}
              onChange={(e) =>
                setSettings({ ...settings, description_ru: e.target.value })
              }
            />
          </div>
          <label className="mt-4 flex cursor-pointer items-center gap-2.5 text-sm text-text">
            <input
              type="checkbox"
              checked={settings.is_active}
              onChange={(e) =>
                setSettings({ ...settings, is_active: e.target.checked })
              }
              className="h-4 w-4 rounded border-border text-primary focus:ring-primary/50"
            />
            {t("studio.editor.active")}
          </label>
          {error && <p className="mt-3 text-sm text-error">{error}</p>}
          <div className="mt-5 flex items-center justify-end gap-3">
            {savedFlash && (
              <span className="inline-flex items-center gap-1.5 text-sm text-emerald-400">
                <Check size={16} /> {t("studio.editor.saved")}
              </span>
            )}
            <Button onClick={saveSettings} disabled={savingSettings}>
              <Save size={16} />
              {savingSettings
                ? t("studio.editor.saving")
                : t("studio.editor.save")}
            </Button>
          </div>
        </div>

        {/* Разделы */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-text">
            <Layers size={18} className="text-primary" />
            {t("studio.editor.sections")}
          </h2>
          {!addingSection && (
            <Button variant="outline" onClick={() => setAddingSection(true)}>
              <Plus size={16} /> {t("studio.editor.addSection")}
            </Button>
          )}
        </div>

        {addingSection && (
          <form
            onSubmit={addSection}
            className="mb-4 rounded-2xl border border-dashed border-border bg-surface p-4"
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                className={inputCls}
                value={sectionForm.title_ru}
                placeholder={t("studio.editor.sectionNameRu")}
                onChange={(e) =>
                  setSectionForm({ ...sectionForm, title_ru: e.target.value })
                }
                autoFocus
              />
              <input
                className={inputCls}
                value={sectionForm.title_en}
                placeholder={t("studio.editor.sectionNameEn")}
                onChange={(e) =>
                  setSectionForm({ ...sectionForm, title_en: e.target.value })
                }
              />
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setAddingSection(false);
                  setSectionForm({ title_ru: "", title_en: "" });
                }}
              >
                {t("studio.editor.cancel")}
              </Button>
              <Button type="submit" disabled={sectionBusy}>
                {sectionBusy
                  ? t("studio.editor.adding")
                  : t("studio.editor.add")}
              </Button>
            </div>
          </form>
        )}

        {sections.length === 0 && !addingSection ? (
          <div className="rounded-3xl border border-border bg-surface p-10 text-center">
            <p className="text-muted">{t("studio.editor.noSections")}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sections.map((section) => (
              <SectionCard
                key={section.id}
                section={section}
                t={t}
                onReloadMissions={reloadMissions}
                onReloadSections={reloadSections}
                setConfirm={setConfirm}
                setError={setError}
              />
            ))}
          </div>
        )}
      </div>

      <ConfirmModal data={confirm} onClose={() => setConfirm(null)} />
    </Layout>
  );
}
