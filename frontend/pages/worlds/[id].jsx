import Layout from "../../components/Layout";
import Button from "../../components/Button";
import Link from "next/link";
import { useRouter } from "next/router";
import Badge from "../../components/Badge";
import Card from "../../components/Card";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Locations, missionStatus, Profile as ProfileAPI } from "../../lib/api"; // Убедитесь, что Profile импортирован
import AdventureMap from "../../components/AdventureMap";
import { toast } from "sonner";

export default function WorldDetail() {
  const router = useRouter();
  const { id } = router.query;
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
      .catch((e) => {
        toast.error("Не удалось загрузить данные локации.");
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
          Загрузка карты мира...
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="p-8 max-w-6xl mx-auto space-y-8">
        <header className="space-y-4">
          <Badge>Локация</Badge>
          <h1 className="text-4xl font-bold text-white tracking-wider">
            {world.title_ru || world.title}
          </h1>
          <p className="text-gray-400 max-w-2xl leading-relaxed">
            {world.description_ru || world.description}
          </p>
        </header>

        {/* Передаем класс в компонент карты */}
        <section>
          <AdventureMap nodes={world.missions || []} playerClass={playerClass} />
        </section>
        
        {/* Кнопка возврата или список миссий текстом */}
        <div className="flex justify-start">
           <Button variant="secondary" onClick={() => router.push('/worlds')}>
              Вернуться к списку миров
           </Button>
        </div>
      </div>
    </Layout>
  );
}