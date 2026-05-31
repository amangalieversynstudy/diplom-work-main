import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Target, Zap, Trophy } from "lucide-react";
import { useI18n } from "../lib/i18n";

// Регистрируем плагин только на стороне клиента
if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

// Визуальная мета (иконка/цвет) статична — тексты приходят из словаря.
const featureMeta = [
  { icon: Target, color: "text-emerald-500", bg: "bg-emerald-500/10" },
  { icon: Zap, color: "text-amber-500", bg: "bg-amber-500/10" },
  { icon: Trophy, color: "text-sky-500", bg: "bg-sky-500/10" },
];

export default function FeaturesSection() {
  const container = useRef(null);
  const { t } = useI18n();
  const items = t("features.items");
  const features = featureMeta.map((meta, i) => ({
    ...meta,
    title: Array.isArray(items) ? items[i]?.title : "",
    desc: Array.isArray(items) ? items[i]?.desc : "",
  }));

  useGSAP(
    () => {
      gsap.fromTo(
        ".feature-card",
        { y: 80, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.8,
          stagger: 0.2,
          ease: "power3.out",
          scrollTrigger: {
            trigger: container.current,
            start: "top 75%", // Анимация стартует, когда верх секции достигает 75% высоты экрана
          },
        }
      );
    },
    { scope: container }
  );

  return (
    <section ref={container} className="relative py-32 bg-transparent text-white px-4 border-t border-white/10">
      <div className="max-w-6xl mx-auto z-10 relative">
        <h2 className="text-4xl md:text-5xl font-bold text-center mb-16 text-white">
          {t("features.heading")}
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {features.map((item, index) => {
            const Icon = item.icon;
            return (
              <div
                key={index}
                className="feature-card bg-white/5 p-8 rounded-3xl border border-white/10 transition-shadow hover:bg-white/10"
              >
                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-6 ${item.bg} ${item.color}`}>
                  <Icon className="w-7 h-7" />
                </div>
                <h3 className="text-xl font-bold mb-4 text-white">
                  {item.title}
                </h3>
                <p className="text-white/60 leading-relaxed">
                  {item.desc}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}