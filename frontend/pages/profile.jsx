import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import XPBar from "../components/XPBar";
import Button from "../components/Button";
import { clearPlayerClass } from "../lib/class";
import { Profile as ProfileAPI } from "../lib/api";
import logger from "../lib/logger";
import { toast } from "sonner";
import { LogOut, Settings, Mail, User, Shield } from "lucide-react";

// Maps backend ClassRole pk → frontend display name (must match dictionaries/ru.js classPage.classes)
const CLASS_NAMES = {
  1: "Python-спеллблейд",
  2: "Арканист Django",
  3: "DevOps-рейнджер",
};

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  
  const [formData, setFormData] = useState({
    username: "",
    email: ""
  });

  useEffect(() => {
    fetchProfile();
  }, []);

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
      };

      setProfile(merged);
      setFormData({
        username: merged.username,
        email: merged.email,
      });
    } catch (error) {
      logger.error("Ошибка загрузки профиля:", error);
      toast.error("Не удалось загрузить данные профиля");
    } finally {
      setLoading(false);
    }
  };

  const handleResetClass = () => {
    // Очищаем кэш класса и отправляем на страницу выбора
    clearPlayerClass();
    toast.success("Класс успешно сброшен. Выберите новый путь!");
    router.push("/class");
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    clearPlayerClass();
    router.push("/login");
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    try {
      await ProfileAPI.update(formData);
      toast.success("Данные профиля успешно обновлены!");
      setIsEditing(false);
      fetchProfile();
    } catch (error) {
      logger.error(error);
      const detail =
        error?.response?.data?.detail ||
        Object.values(error?.response?.data || {})[0] ||
        "Ошибка при сохранении данных";
      toast.error(String(detail));
    }
  };

if (loading) {
    return (
      <Layout>
        <div className="max-w-4xl mx-auto pt-24 pb-16 px-4">
          <div className="h-10 bg-[#2a2a2e] rounded w-1/3 mb-8 animate-pulse" />
          <div className="grid md:grid-cols-3 gap-8">
            <div className="md:col-span-1 space-y-6">
              <div className="bg-[#2a2a2e] border border-[#222] rounded-3xl p-6 text-center animate-pulse">
                <div className="w-24 h-24 mx-auto bg-[#3f3f46] rounded-full mb-4" />
                <div className="h-6 bg-[#3f3f46] rounded w-1/2 mx-auto mb-2" />
                <div className="h-4 bg-[#3f3f46] rounded w-1/3 mx-auto mb-6" />
                <div className="h-2 bg-[#3f3f46] rounded w-full mb-8" />
                <div className="h-10 bg-[#3f3f46] rounded w-full mb-3" />
                <div className="h-10 bg-[#3f3f46] rounded w-full" />
              </div>
            </div>
            <div className="md:col-span-2">
              <div className="bg-[#2a2a2e] border border-[#222] rounded-3xl p-8 animate-pulse">
                <div className="h-6 bg-[#3f3f46] rounded w-1/3 mb-8" />
                <div className="h-16 bg-[#3f3f46] rounded-xl w-full mb-4" />
                <div className="h-16 bg-[#3f3f46] rounded-xl w-full" />
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
        <h1 className="text-4xl font-display font-bold mb-8 text-text">Профиль Героя</h1>
        
        <div className="grid md:grid-cols-3 gap-8">
          {/* Левая колонка - Аватар и Статистика */}
          <div className="md:col-span-1 space-y-6">
            <div className="bg-surface border border-border rounded-3xl p-6 text-center shadow-sm">
              <div className="w-24 h-24 mx-auto bg-panel border border-border rounded-full flex items-center justify-center mb-4">
                <User size={40} className="text-muted" />
              </div>
              <h2 className="text-2xl font-bold text-text mb-1">{profile?.username || "Неизвестный"}</h2>
              {profile?.class_role && (
                <p className="text-xs text-accent uppercase tracking-widest font-bold mb-1">
                  {CLASS_NAMES[profile.class_role] || "Класс неизвестен"}
                </p>
              )}
              <div className="flex items-center justify-center gap-2 mb-4">
                <p className="text-sm text-primary uppercase tracking-widest font-bold">
                  Уровень {profile?.level || 1}
                </p>
                {profile?.rank && (
                  <span className="px-2 py-0.5 text-[10px] uppercase tracking-widest font-bold rounded-full bg-accent/15 border border-accent/40 text-accent">
                    {profile.rank.title_ru || profile.rank.title_en || profile.rank.slug}
                  </span>
                )}
              </div>

              {/* Полоса опыта (100 XP = 1 level) */}
              <XPBar
                current={(profile?.xp || 0) % 100}
                max={100}
              />
              
              <div className="mt-6 pt-6 border-t border-border space-y-3">
                <Button onClick={handleResetClass} variant="outline" className="w-full text-sm">
                  <Shield size={16} className="mr-2" /> Сменить класс
                </Button>
                <Button onClick={handleLogout} variant="ghost" className="w-full text-sm text-red-500 hover:text-red-600 hover:bg-red-500/10">
                  <LogOut size={16} className="mr-2" /> Выйти
                </Button>
              </div>
            </div>
          </div>

          {/* Правая колонка - Настройки */}
          <div className="md:col-span-2">
            <div className="bg-surface border border-border rounded-3xl p-8 shadow-sm">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-bold text-text flex items-center">
                  <Settings size={20} className="mr-2 text-primary" /> Настройки аккаунта
                </h3>
                {!isEditing && (
                  <Button onClick={() => setIsEditing(true)} variant="outline" size="sm">
                    Редактировать
                  </Button>
                )}
              </div>

              {isEditing ? (
                <form onSubmit={handleSaveProfile} className="space-y-4">
                  <div>
                    <label htmlFor="profile-username" className="block text-sm font-medium text-muted mb-1">Имя пользователя</label>
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
                    <label htmlFor="profile-email" className="block text-sm font-medium text-muted mb-1">Электронная почта</label>
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
                    <Button type="submit" className="bg-primary text-white">Сохранить</Button>
                    <Button type="button" variant="ghost" onClick={() => setIsEditing(false)}>Отмена</Button>
                  </div>
                </form>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center p-4 bg-panel border border-border rounded-xl">
                    <User size={20} className="text-muted mr-4" />
                    <div>
                      <p className="text-xs text-muted font-medium mb-1">Логин</p>
                      <p className="text-text font-medium">{profile?.username || "Не указан"}</p>
                    </div>
                  </div>
                  <div className="flex items-center p-4 bg-panel border border-border rounded-xl">
                    <Mail size={20} className="text-muted mr-4" />
                    <div>
                      <p className="text-xs text-muted font-medium mb-1">Email</p>
                      <p className="text-text font-medium">{profile?.email || "Не указана"}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}