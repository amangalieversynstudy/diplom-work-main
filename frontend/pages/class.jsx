import { useEffect, useMemo } from "react";
import { useRouter } from "next/router";
import { motion } from "framer-motion"; // <-- Добавили framer-motion
import Layout from "../components/Layout";
import Button from "../components/Button";
import { setPlayerClass, getPlayerClass } from "../lib/class";
import { toast } from "sonner";
import { Code, ServerCog, Share2 } from "lucide-react";
import { useDictionary } from "../lib/i18n";

const CLASS_ICONS = {
  django: ServerCog,
  python: Code,
  devops: Share2,
};

export default function ChooseClassPage() {
  const dict = useDictionary();
  const router = useRouter();

  const classes = useMemo(() => {
    return Object.entries(dict.classPage.classes).map(([id, data]) => ({
      id,
      ...data,
      icon: CLASS_ICONS[id] || Code,
    }));
  }, [dict.classPage.classes]);

  useEffect(() => {
    const chosen = getPlayerClass();
    if (chosen) router.push("/worlds"); 
  }, [router]);

  function choose(id) {
    setPlayerClass(id);
    toast.success(dict.classPage.toastSuccess);
    router.push("/worlds");
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto pt-24 pb-16 px-4 transition-colors duration-300">
        
        {/* ── Заголовок ── */}
        <header className="mb-16 text-center max-w-3xl mx-auto border-b border-border pb-10">
          <p className="text-xs uppercase tracking-widest text-primary mb-4 font-bold">
            {dict.classPage.alignment}
          </p>
          <h1 className="text-4xl md:text-6xl font-display font-bold text-text mb-6">
            {dict.classPage.heading}
          </h1>
          <p className="text-lg text-muted leading-relaxed">
            {dict.classPage.subheading}
          </p>
        </header>

        {/* ── Карточки классов ── */}
        <div className="grid lg:grid-cols-3 gap-8">
          {classes.map((c) => {
            const Icon = c.icon;
            return (
              <motion.div
                key={c.id}
                whileHover={{ scale: 1.05, y: -10 }} // Эффект левитации
                whileTap={{ scale: 0.98 }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                onClick={() => choose(c.id)}
                className="group relative flex flex-col p-8 rounded-[2.5rem] border border-border bg-surface hover:border-primary transition-all duration-500 hover:shadow-[0_0_40px_var(--primary-selection)] overflow-hidden cursor-pointer"
              >
                {/* Текстура пергамента на фоне */}
                <div className="absolute inset-0 pointer-events-none opacity-[0.12] dark:opacity-[0.15] mix-blend-multiply dark:mix-blend-overlay rounded-[inherit]">
                  <svg className="w-full h-full">
                    <filter id={`paper-noise-${c.id}`}>
                      <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="4" stitchTiles="stitch" />
                    </filter>
                    <rect width="100%" height="100%" filter={`url(#paper-noise-${c.id})`} />
                  </svg>
                </div>

                {/* Верхний градиентный блик при наведении */}
                <div className="absolute top-0 left-0 w-full h-40 bg-gradient-to-b from-primary/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700" />

                <div className="relative z-10 flex flex-col h-full pointer-events-none">
                  {/* Иконка и Герб */}
                  <div className="flex items-center justify-between mb-8">
                    <div className="w-16 h-16 rounded-2xl bg-panel border border-border flex items-center justify-center text-4xl shadow-inner group-hover:scale-110 group-hover:rotate-6 group-hover:border-primary/50 transition-all duration-500">
                      <span className="drop-shadow-md">{c.crest}</span>
                    </div>
                    <div className="w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center opacity-50 group-hover:opacity-100 group-hover:bg-primary group-hover:text-white transition-all duration-500 group-hover:shadow-[0_0_15px_var(--primary)]">
                      <Icon size={24} />
                    </div>
                  </div>

                  {/* Текст и описание */}
                  <div className="mb-8 flex-1">
                    <h3 className="text-2xl font-display font-bold text-text mb-2 group-hover:text-primary transition-colors duration-300">
                      {c.name}
                    </h3>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-accent mb-4">
                      {c.focus}
                    </p>
                    <p className="text-sm text-muted leading-relaxed">
                      {c.desc}
                    </p>
                  </div>

                  {/* Кнопка принятия клятвы (Визуальная, т.к. кликабельна вся карточка) */}
                  <Button 
                    className="w-full bg-panel text-text border border-border group-hover:bg-primary group-hover:text-white group-hover:border-primary-dk transition-all duration-300 shadow-none group-hover:shadow-[0_0_20px_var(--primary-selection)] pointer-events-none" 
                  >
                    {dict.classPage.cta}
                  </Button>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </Layout>
  );
}