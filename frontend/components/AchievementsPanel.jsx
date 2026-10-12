import {
  Crown,
  Flag,
  Flame,
  Footprints,
  Lock,
  Star,
  Swords,
  Trophy,
} from "lucide-react";
import { useI18n } from "../lib/i18n";
import Card from "./Card";
import EmptyScroll from "./EmptyScroll";

// Каталог достижений живёт на бэкенде (game/achievements.py) и присылает имя
// иконки строкой. Карта переводит это имя в компонент lucide-react. Любой
// неизвестный ключ безопасно падает на Star.
const ICONS = { Footprints, Swords, Crown, Flag, Star, Flame };

/**
 * Сетка достижений для страницы профиля.
 *
 * @param {{items: Array<{slug,icon,target,current,earned,earned_at}>}} props
 */
export default function AchievementsPanel({ items = [] }) {
  const { t } = useI18n();
  const earnedCount = items.filter((a) => a.earned).length;

  if (items.length === 0) {
    return (
      <EmptyScroll icon={Trophy} className="mt-8">
        {t("achievements.empty")}
      </EmptyScroll>
    );
  }

  return (
    <Card variant="scroll" className="mt-8">
      <div className="flex items-center justify-between mb-6">
        <h3 className="font-title text-2xl text-text flex items-center">
          <Trophy size={20} className="mr-2 text-accent" />
          {t("achievements.title")}
        </h3>
        <span className="text-sm text-muted font-medium tabular-nums">
          {earnedCount} / {items.length}
        </span>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
          {items.map((a) => {
            const Icon = ICONS[a.icon] || Star;
            const pct =
              a.target > 0
                ? Math.min(100, Math.round((a.current / a.target) * 100))
                : 0;
            return (
              <div
                key={a.slug}
                className={`flex gap-4 p-4 rounded-2xl border transition-colors ${
                  a.earned
                    ? "bg-accent/10 border-accent/40"
                    : "bg-panel border-border"
                }`}
              >
                <div
                  className={`shrink-0 w-12 h-12 rounded-full flex items-center justify-center border-2 ${
                    a.earned
                      ? "bg-accent/20 border-accent/50 text-accent"
                      : "bg-surface border-border text-muted"
                  }`}
                >
                  {a.earned ? <Icon size={24} /> : <Lock size={20} />}
                </div>
                <div className="min-w-0 flex-1">
                  <h4
                    className={`font-bold truncate ${
                      a.earned ? "text-text" : "text-muted"
                    }`}
                  >
                    {t(`achievements.items.${a.slug}.title`)}
                  </h4>
                  <p className="text-xs text-muted mt-0.5">
                    {t(`achievements.items.${a.slug}.desc`)}
                  </p>
                  {a.earned ? (
                    <p className="text-xs text-accent-dk uppercase tracking-widest font-bold mt-2">
                      {t("achievements.earnedLabel")}
                    </p>
                  ) : (
                    <div className="mt-2">
                      <div className="h-1.5 bg-surface rounded-full overflow-hidden border border-border">
                        <div
                          className="h-full w-full origin-left bg-primary transition-transform"
                          style={{ transform: `scaleX(${pct / 100})` }}
                        />
                      </div>
                      <p className="text-xs text-muted mt-1 tabular-nums">
                        {a.current} / {a.target}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
      </div>
    </Card>
  );
}
