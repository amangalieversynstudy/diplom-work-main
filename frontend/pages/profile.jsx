import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import XPBar from "../components/XPBar";
import Button from "../components/Button";
import Card from "../components/Card";
import ClassPortrait from "../components/ClassPortrait";
import AchievementsPanel from "../components/AchievementsPanel";
import { clearPlayerClass } from "../lib/class";
import {
  Profile as ProfileAPI,
  Achievements as AchievementsAPI,
  revokeSession,
} from "../lib/api";
import logger from "../lib/logger";
import { toast } from "sonner";
import { LogOut, Settings, Mail, User, Shield, Flame, ChevronDown, Sparkles, FlaskConical, ScrollText } from "lucide-react";
import { useI18n } from "../lib/i18n";

export default function ProfilePage() {
  const router = useRouter();
  const { t } = useI18n();
  const [profile, setProfile] = useState(null);
  const [achievements, setAchievements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  
  const [formData, setFormData] = useState({
    username: "",
    email: ""
  });

  useEffect(() => {
    fetchProfile();
    fetchAchievements();
    // загрузка один раз при открытии страницы
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchAchievements = async () => {
    try {
      const data = await AchievementsAPI.list();
      setAchievements(Array.isArray(data) ? data : []);
    } catch (error) {
      // Достижения — украшение профиля, а не критичный путь: при ошибке просто
      // не показываем секцию, не роняя страницу.
      logger.error("Achievements load failed:", error);
    }
  };

  const fetchProfile = async () => {
    try {
      // ProfileAPI.me() сам пробует /profile/me/, а при 404 — /auth/me/
      const data = await ProfileAPI.me();

      // Бэкенд возвращает ProfileSerializer: {xp, level, user: {username, email, ...}}
      // ИЛИ UserDetailSerializer: {username, email, profile: {xp, level, ...}}.
      // Нормализуем оба варианта в плоскую структуру.
      const userBlock = data.user ?? data;
      const profileBlock = data.profile ?? data;

      const merged = {
        username: userBlock.username || data.username || "",
        email: userBlock.email || data.email || "",
        xp: profileBlock.xp ?? 0,
        level: profileBlock.level ?? 1,
        class_role: profileBlock.class_role ?? data.class_role ?? null,
        ai_summons: profileBlock.ai_summons ?? 0,
        hint_scrolls: profileBlock.hint_scrolls ?? 0,
        skeleton_scrolls: profileBlock.skeleton_scrolls ?? 0,
        rank: profileBlock.rank ?? null,
        current_streak: profileBlock.current_streak ?? 0,
        longest_streak: profileBlock.longest_streak ?? 0,
        streak_active: profileBlock.streak_active ?? false,
        streak_at_risk: profileBlock.streak_at_risk ?? false,
        research_consent: profileBlock.research_consent ?? false,
      };

      setProfile(merged);
      setFormData({
        username: merged.username,
        email: merged.email,
      });
    } catch (error) {
      logger.error("Profile load failed:", error);
      toast.error(t("profile.toasts.loadError"));
    } finally {
      setLoading(false);
    }
  };

  // Класс на сервере остаётся прежним, пока ученик не выберет другой, поэтому это переход к выбору,
  // а не «сброс» (раньше тост уверял, что класс сброшен).
  const handleResetClass = () => {
    clearPlayerClass();
    router.push("/class");
  };

  const handleLogout = async () => {
    await revokeSession();
    clearPlayerClass();
    router.push("/login");
  };

  // Согласие на использование активности в исследовании: сохраняется сразу,
  // без кнопки «Сохранить», чтобы отзыв согласия был в один клик.
  const handleConsentChange = async (checked) => {
    const previous = !!profile?.research_consent;
    setProfile((p) => ({ ...p, research_consent: checked }));
    try {
      const updated = await ProfileAPI.update({ research_consent: checked });
      setProfile((p) => ({ ...p, research_consent: !!updated?.research_consent }));
      toast.success(t("profile.toasts.saved"));
    } catch (error) {
      logger.error(error);
      setProfile((p) => ({ ...p, research_consent: previous }));
      toast.error(t("profile.toasts.saveError"));
    }
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    try {
      const updated = await ProfileAPI.update(formData);
      // Смена email не применяется сразу: бэк шлёт ссылку-подтверждение на новый
      // адрес и возвращает email_change_pending. Старый адрес активен до клика.
      if (updated?.email_change_pending) {
        toast.success(
          (t("profile.toasts.emailPending") || "").replace(
            "{email}",
            updated.email_change_pending
          ),
          { duration: 6000 }
        );
      } else {
        toast.success(t("profile.toasts.saved"));
      }
      setIsEditing(false);
      fetchProfile();
    } catch (error) {
      logger.error(error);
      const detail =
        error?.response?.data?.detail ||
        Object.values(error?.response?.data || {})[0] ||
        t("profile.toasts.saveError");
      toast.error(String(detail));
    }
  };

if (loading) {
    return (
      <Layout>
        <div className="max-w-4xl mx-auto pt-24 pb-16 px-4">
          <div className="h-10 bg-panel rounded w-1/3 mb-8 animate-pulse" />
          <div className="grid md:grid-cols-3 gap-8">
            <div className="md:col-span-1 space-y-6">
              <div className="bg-panel border border-border rounded-3xl p-6 text-center animate-pulse">
                <div className="w-24 h-24 mx-auto bg-border rounded-full mb-4" />
                <div className="h-6 bg-border rounded w-1/2 mx-auto mb-2" />
                <div className="h-4 bg-border rounded w-1/3 mx-auto mb-6" />
                <div className="h-2 bg-border rounded w-full mb-8" />
                <div className="h-10 bg-border rounded w-full mb-3" />
                <div className="h-10 bg-border rounded w-full" />
              </div>
            </div>
            <div className="md:col-span-2">
              <div className="bg-panel border border-border rounded-3xl p-8 animate-pulse">
                <div className="h-6 bg-border rounded w-1/3 mb-8" />
                <div className="h-16 bg-border rounded-xl w-full mb-4" />
                <div className="h-16 bg-border rounded-xl w-full" />
              </div>
            </div>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-4xl mx-auto pt-24 pb-16 px-4">
        <h1 className="text-4xl font-title mb-8 text-text">{t("profile.heroProfile")}</h1>

        <div className="grid md:grid-cols-3 gap-8">
          {/* Hero column - avatar & stats */}
          <div className="md:col-span-1 space-y-6">
            <Card variant="scroll" className="text-center">
              <div className="mx-auto mb-4 flex justify-center">
                <ClassPortrait
                  role={profile?.class_role}
                  size={104}
                  label={profile?.class_role ? t(`profile.classes.${profile.class_role}`) : undefined}
                />
              </div>
              <h2 className="font-title text-2xl text-text mb-1">
                {profile?.username || t("profile.unknownPlayer")}
              </h2>
              {profile?.class_role && (
                <p className="text-xs text-accent uppercase tracking-widest font-bold mb-1">
                  {t(`profile.classes.${profile.class_role}`) || t("profile.unknownClass")}
                </p>
              )}
              <div className="flex items-center justify-center gap-2 mb-4">
                <p className="text-sm text-primary uppercase tracking-widest font-bold">
                  {t("profile.level")} {profile?.level || 1}
                </p>
                {profile?.rank && (
                  <span className="px-2 py-0.5 text-xs uppercase tracking-widest font-bold rounded-full bg-accent/15 border border-accent/40 text-accent-dk">
                    {profile.rank.title_ru || profile.rank.title_en || profile.rank.slug}
                  </span>
                )}
              </div>

              {/* Полоса опыта (100 XP = 1 level) */}
              <XPBar
                current={(profile?.xp || 0) % 100}
                max={100}
              />

              {/* Стрик — серия дней подряд с завершёнными миссиями */}
              <div className="mt-5 flex items-center justify-center gap-3 rounded-2xl border border-border bg-panel px-4 py-3">
                <Flame
                  size={26}
                  className={profile?.streak_active ? "text-orange-500" : "text-faint"}
                  fill={profile?.streak_active ? "currentColor" : "none"}
                />
                <div className="text-left">
                  <p className="flex items-baseline gap-1 text-xl font-bold leading-none text-text">
                    {profile?.streak_active ? profile.current_streak : 0}
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                      {t("profile.streak.label")}
                    </span>
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {(profile?.longest_streak || 0) > 0
                      ? `${t("profile.streak.best")}: ${profile.longest_streak}`
                      : t("profile.streak.start")}
                  </p>
                </div>
              </div>

              {/* Инвентарь: расходуемые предметы героя */}
              <div className="mt-5 text-left">
                <p className="mb-2 text-xs font-bold uppercase tracking-widest text-muted">
                  {t("profile.inventoryTitle")}
                </p>
                <ul className="grid grid-cols-3 gap-2">
                  {[
                    { key: "ai_summons", Icon: Sparkles, label: t("profile.summons") },
                    { key: "hint_scrolls", Icon: FlaskConical, label: t("codeRunner.items.clarity") },
                    { key: "skeleton_scrolls", Icon: ScrollText, label: t("codeRunner.items.architect") },
                  ].map(({ key, Icon, label }) => (
                    <li
                      key={key}
                      className="flex flex-col items-center rounded-xl border border-border bg-panel px-1 py-2 text-center"
                    >
                      <Icon size={20} className="text-primary" aria-hidden="true" />
                      <span className="mt-1 text-lg font-bold leading-none tabular-nums text-text">
                        {profile?.[key] ?? 0}
                      </span>
                      <span className="mt-1 text-[11px] leading-tight text-muted">{label}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-6 pt-6 border-t border-border space-y-3">
                <Button onClick={handleResetClass} variant="outline" className="w-full text-sm">
                  <Shield size={16} className="mr-2" /> {profile?.class_role ? t("profile.changeClass") : t("profile.chooseClass")}
                </Button>
                <Button onClick={handleLogout} variant="ghost" className="w-full text-sm text-red-700 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 hover:bg-red-500/10">
                  <LogOut size={16} className="mr-2" /> {t("profile.logout")}
                </Button>
              </div>
            </Card>
          </div>

          {/* Правая колонка - Настройки */}
          <div className="md:col-span-2">
            <Card variant="scroll">
              <details className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between [&::-webkit-details-marker]:hidden">
                  <span className="font-title text-xl text-text flex items-center">
                    <Settings size={20} className="mr-2 text-primary" /> {t("profile.accountSettings")}
                  </span>
                  <ChevronDown size={20} className="text-muted transition-transform group-open:rotate-180" aria-hidden="true" />
                </summary>
              <div className="mt-6">
              <div className="flex justify-end mb-4">
                {!isEditing && (
                  <Button onClick={() => setIsEditing(true)} variant="outline" size="sm">
                    {t("profile.editBtn")}
                  </Button>
                )}
              </div>

              {isEditing ? (
                <form onSubmit={handleSaveProfile} className="space-y-4">
                  <div>
                    <label htmlFor="profile-username" className="block text-sm font-medium text-muted mb-1">{t("profile.usernameLabel")}</label>
                    <input
                      id="profile-username"
                      type="text"
                      value={formData.username}
                      onChange={(e) => setFormData({...formData, username: e.target.value})}
                      className="w-full bg-panel border border-border rounded-xl px-4 py-2 text-text focus:border-primary outline-none transition-colors"
                      required
                    />
                  </div>
                  <div>
                    <label htmlFor="profile-email" className="block text-sm font-medium text-muted mb-1">{t("profile.emailLabel")}</label>
                    <input
                      id="profile-email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({...formData, email: e.target.value})}
                      className="w-full bg-panel border border-border rounded-xl px-4 py-2 text-text focus:border-primary outline-none transition-colors"
                      required
                    />
                  </div>
                  <div className="flex gap-3 pt-4">
                    <Button type="submit" className="bg-primary text-on-primary">{t("profile.saveBtn")}</Button>
                    <Button type="button" variant="ghost" onClick={() => setIsEditing(false)}>{t("profile.cancelBtn")}</Button>
                  </div>
                </form>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center p-4 bg-panel border border-border rounded-xl">
                    <User size={20} className="text-muted mr-4" />
                    <div>
                      <p className="text-xs text-muted font-medium mb-1">{t("profile.loginField")}</p>
                      <p className="text-text font-medium">{profile?.username || t("profile.notSet")}</p>
                    </div>
                  </div>
                  <div className="flex items-center p-4 bg-panel border border-border rounded-xl">
                    <Mail size={20} className="text-muted mr-4" />
                    <div>
                      <p className="text-xs text-muted font-medium mb-1">{t("profile.emailField")}</p>
                      <p className="text-text font-medium">{profile?.email || t("profile.emailNotSet")}</p>
                    </div>
                  </div>
                </div>
              )}
              </div>
              </details>

              <div className="mt-6 pt-6 border-t border-border">
                <label className="flex items-start gap-3 cursor-pointer py-1">
                  <input
                    type="checkbox"
                    className="mt-0.5 h-6 w-6 shrink-0 accent-[var(--primary)]"
                    checked={!!profile?.research_consent}
                    onChange={(e) => handleConsentChange(e.target.checked)}
                  />
                  <span className="text-sm text-text">
                    {t("profile.researchConsentLabel")}
                    <span className="block text-xs text-muted mt-1">
                      {t("profile.researchConsentHint")}
                    </span>
                  </span>
                </label>
              </div>
            </Card>
          </div>
        </div>

        <AchievementsPanel items={achievements} />
      </div>
    </Layout>
  );
}