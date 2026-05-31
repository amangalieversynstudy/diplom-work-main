import Layout from "../../components/Layout";
import Button from "../../components/Button";
import { useRouter } from "next/router";
import Badge from "../../components/Badge";
import { useEffect, useState } from "react";
import { Locations, Profile as ProfileAPI } from "../../lib/api";
import AdventureMap from "../../components/AdventureMap";
import { toast } from "sonner";
import { useI18n } from "../../lib/i18n";

export default function WorldDetail() {
  const router = useRouter();
  const { id } = router.query;
  const { t, language } = useI18n();
  const [world, setWorld] = useState(null);
  const [loading, setLoading] = useState(true);
  const [playerClass, setPlayerClass] = useState(null); // Стейт для класса игрока

  useEffect(() => {
    if (!id) return;
    
    let active = true;

    // Параллельная загрузка мира и профиля
    Promise.all([
      Locations.get(id),
      ProfileAPI.me()
    ])
      .then(([worldData, userDoc]) => {
        if (!active) return;
        setWorld(worldData);
        
        // Извлекаем название роли/класса. Зависит от структуры вашей модели. 
        // Если class_role это строка:
        // setPlayerClass(userDoc?.profile?.class_role);
        // Если class_role это объект { name: "Warrior" }:
        setPlayerClass(userDoc?.profile?.class_role?.name || userDoc?.profile?.class_role);
      })
      .catch(() => {
        toast.error(t("worldsPage.toasts.locationFail"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [id]);

  if (loading || !world) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-screen text-white font-mono">
          {t("worldsPage.loadingLocation")}
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="p-8 max-w-6xl mx-auto space-y-8">
        <header className="space-y-4">
          <Badge>{t("worldsPage.locationBadge")}</Badge>
          <h1 className="text-4xl font-bold text-white tracking-wider">
            {(language === "en"
              ? world.title_en || world.title_ru
              : world.title_ru || world.title_en) || world.title}
          </h1>
          <p className="text-gray-400 max-w-2xl leading-relaxed">
            {(language === "en"
              ? world.description_en || world.description_ru
              : world.description_ru || world.description_en) || world.description}
          </p>
        </header>

        {/* Передаем класс в компонент карты */}
        <section>
          <AdventureMap nodes={world.missions || []} playerClass={playerClass} />
        </section>
        
        {/* Кнопка возврата или список миссий текстом */}
        <div className="flex justify-start">
           <Button variant="secondary" onClick={() => router.push('/worlds')}>
              {t("worldsPage.backToWorlds")}
           </Button>
        </div>
      </div>
    </Layout>
  );
}