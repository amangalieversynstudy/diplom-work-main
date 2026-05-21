import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import XPBar from "../components/XPBar";
import Button from "../components/Button";
import { clearPlayerClass } from "../lib/class";
import api from "../lib/api"; // Твой настроенный axios instance
import { toast } from "sonner";
import { LogOut, Settings, Mail, User, Shield } from "lucide-react";

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
      // Запрашиваем реальные данные из Django DRF
      const response = await api.get("/users/me/"); // Убедись, что эндпоинт совпадает с твоим API
      setProfile(response.data);
      setFormData({
        username: response.data.username || "",
        email: response.data.email || ""
      });
    } catch (error) {
      console.error("Ошибка загрузки профиля:", error);
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
      await api.patch("/users/me/", formData); // Отправляем PATCH запрос на обновление
      toast.success("Данные профиля успешно обновлены!");
      setIsEditing(false);
      fetchProfile();
    } catch (error) {
      console.error(error);
      toast.error("Ошибка при сохранении данных");
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="pt-32 text-center text-muted animate-pulse">Загрузка профиля героя...</div>
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
              <p className="text-sm text-primary uppercase tracking-widest font-bold mb-4">
                Уровень {profile?.level || 1}
              </p>
              
              {/* Полоса опыта */}
              <XPBar currentXP={profile?.xp || 0} maxXP={(profile?.level || 1) * 1000} />
              
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