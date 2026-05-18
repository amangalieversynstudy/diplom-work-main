import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import XPBar from "../components/XPBar";
import Button from "../components/Button";
import { Profile as ProfileAPI } from "../lib/api";
import Skeleton from "../components/Skeleton";
import { toast } from "sonner";
import { useDictionary } from "../lib/i18n";
import { getPlayerClass, clearPlayerClass } from "../lib/class";
import { Edit2, Check, X } from "lucide-react";

export default function Profile() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [localClass, setLocalClass] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editUsername, setEditUsername] = useState("");
  const dict = useDictionary();
  const copy = dict.profile;
  const router = useRouter();

  const attributes = useMemo(
    () => [
      { label: copy.attributes.wisdom, key: "wisdom" },
      { label: copy.attributes.dex, key: "dex" },
      { label: copy.attributes.focus, key: "focus" },
    ],
    [copy.attributes]
  );

  useEffect(() => {
    const token = localStorage.getItem("access") || localStorage.getItem("token") || localStorage.getItem("access_token");
    if (!token) {
      router.push("/login");
      return;
    }

    setLocalClass(getPlayerClass());
  }, []);

  useEffect(() => {
    let active = true;
    ProfileAPI.me()
      .then((d) => {
        if (active) {
          setData(d);
          setEditUsername(d?.username || "");
        }
      })
      .catch((e) => {
        const msg = e?.response?.data?.detail || copy.errors.load;
        toast.error(msg);
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [copy.errors.load]);

  const handleResetClass = () => {
    clearPlayerClass(); // Очищаем localStorage
    router.push("/class"); // Перенаправляем на выбор класса
  };

  const handleSaveUsername = async () => {
    if (!editUsername.trim()) {
      toast.error("Логин не может быть пустым");
      return;
    }
    try {
      const updatedData = await ProfileAPI.update({ username: editUsername });

      // Используем то, что реально сохранил и вернул сервер (чтобы избежать ложного успеха)
      const savedName = updatedData.username || editUsername;

      setData((prev) => ({ ...prev, username: savedName }));
      setIsEditing(false);
      toast.success("Логин успешно обновлен!");
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.response?.data?.username?.[0] || "Ошибка при обновлении логина";
      toast.error(msg);
    }
  };

  const username = data?.username || dict.common.none;
  const email = data?.email || dict.common.none;
  const xp = data?.profile?.xp ?? 0;
  const level = data?.profile?.level ?? 1;
  
  // Берём класс с бэкенда ИЛИ из локального хранилища, затем переводим
  const classRoleRaw = data?.profile?.class_role || localClass;
  const classRole = dict.classPage.classes[classRoleRaw]?.name || classRoleRaw || dict.common.none;

  if (loading) {
    return (
      <Layout>
        <div className="max-w-4xl mx-auto pt-24 pb-10 px-4">
          <Skeleton className="h-48 rounded-[2rem] bg-panel" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-4xl mx-auto pt-24 pb-10 px-4 transition-colors duration-300">
        {/* ── Заголовок профиля ── */}
        <header className="mb-12 border-b border-border pb-8">
          <p className="text-xs uppercase tracking-widest text-primary mb-3">
            {copy.title}
          </p>
          <div className="flex items-center gap-4 mb-2 min-h-[60px]">
            {isEditing ? (
              <div className="flex items-center gap-2 w-full max-w-sm">
                <input
                  type="text"
                  placeholder={dict.common.identifier || "Логин"}
                  value={editUsername}
                  onChange={(e) => setEditUsername(e.target.value)}
                  className="w-full text-2xl md:text-4xl font-display font-bold text-text bg-panel border border-border rounded-xl px-4 py-2 focus:outline-none focus:border-primary transition-colors"
                  autoFocus
                />
                <button onClick={handleSaveUsername} className="p-3 bg-success/10 text-success rounded-xl hover:bg-success/20 transition-colors" title="Сохранить">
                  <Check size={20} />
                </button>
                <button onClick={() => { setIsEditing(false); setEditUsername(username); }} className="p-3 bg-error/10 text-error rounded-xl hover:bg-error/20 transition-colors" title="Отмена">
                  <X size={20} />
                </button>
              </div>
            ) : (
              <>
                <h1 className="text-4xl md:text-5xl font-display font-bold text-text">
                  {username}
                </h1>
                <button onClick={() => setIsEditing(true)} className="p-2 text-muted hover:text-primary hover:bg-panel rounded-full transition-colors" title="Изменить логин">
                  <Edit2 size={20} />
                </button>
              </>
            )}
          </div>
          <p className="text-muted">{email}</p>
        </header>

        {/* ── Секция уровня и опыта ── */}
        <section className="mb-14">
          <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
            <div>
              <h2 className="text-3xl font-display font-bold text-text mb-1">
                {dict.sheet.level} {level}
              </h2>
              <p className="text-muted text-sm uppercase tracking-wider mt-2">
                {copy.classLabel}: <span className="font-semibold text-primary">{classRole}</span>
              </p>
            </div>
            <p className="text-sm text-muted font-medium bg-panel px-4 py-2 rounded-full border border-border">
              {dict.sheet.totalXp}: <span className="text-text font-bold">{xp}</span>
            </p>
          </div>
          
          <XPBar current={xp % 100} max={100} />
          
          <div className="mt-8">
            <Button
              variant="outline"
              onClick={handleResetClass}
              className="border-border text-muted hover:text-text hover:bg-panel transition-colors"
            >
              {dict.hero.secondaryCta}
            </Button>
          </div>
        </section>

        {/* ── Характеристики (в виде чистой сетки) ── */}
        <section className="mb-14">
          <h3 className="text-xs uppercase tracking-widest text-faint mb-6">{copy.attributesLabel || "Характеристики"}</h3>
          <div className="grid grid-cols-3 gap-4 border-y border-border py-8 bg-panel/30 rounded-3xl">
            {attributes.map((attr) => (
              <div key={attr.key} className="text-center border-r border-border last:border-r-0">
                <p className="text-4xl md:text-5xl font-display font-bold text-text mb-2">
                  {((xp % 50) + level * 3) % 18}
                </p>
                <p className="text-[10px] sm:text-xs text-muted uppercase tracking-widest">
                  {attr.label}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Таланты и Инвентарь (в виде текстовых блоков) ── */}
        <section className="grid md:grid-cols-2 gap-12 border-t border-border pt-12">
          <div>
            <h3 className="text-xl font-display font-bold text-text mb-2">{copy.talents.title}</h3>
            <p className="text-sm text-faint mb-6">{copy.talents.subtitle}</p>
            <ul className="space-y-4">
              {copy.talents.items.map((item) => (
                <li key={item} className="flex items-center gap-3 text-muted">
                  <span className="w-2 h-2 rounded-full bg-primary shadow-[0_0_8px_var(--primary)]" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          
          <div>
            <h3 className="text-xl font-display font-bold text-text mb-2">{copy.inventory.title}</h3>
            <p className="text-sm text-faint mb-6">{copy.inventory.subtitle}</p>
            <ul className="space-y-4">
              {copy.inventory.items.map((item) => (
                <li key={item} className="flex items-center gap-3 text-muted">
                  <span className="w-2 h-2 rounded-full bg-accent shadow-[0_0_8px_var(--accent)]" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </Layout>
  );
}