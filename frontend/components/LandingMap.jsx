import { useEffect, useState } from "react";
import Link from "next/link";
import { Compass, Lock, ScrollText } from "lucide-react";
import { MapBackdrop, MapTrail } from "./WorldMapParts";
import { mapCoords, mapPath } from "../lib/worldMap";
import { missionTitle } from "../lib/missions";
import { getTokens } from "../lib/auth";
import { useDictionary, useI18n } from "../lib/i18n";

// Сколько свитков показываем на карте лендинга
const NODES = 7;

/**
 * Карта миров на лендинге: статичная, узлы-свитки как призыв.
 * Открытый первый свиток ведёт на регистрацию (или на карту, если ученик уже вошёл),
 * на замок отвечает хранитель. Названия берём из каталога, который лендинг уже загрузил;
 * пока его нет, показываем безымянные свитки. На узком экране карта прокручивается по горизонтали.
 */
export default function LandingMap({ missions = [] }) {
  const { t, language } = useI18n();
  const landing = useDictionary().landing || {};
  const lines = landing.guardianLines || [];

  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    setSignedIn(Boolean(getTokens().access));
  }, []);
  const [speaking, setSpeaking] = useState(null); // индекс замка, к которому обратились

  const items = Array.from({ length: NODES }, (_, index) => {
    const mission = missions[index];
    const fallback = t("landing.mapScroll").replace("{n}", index + 1);
    return { id: mission?.id ?? `slot-${index}`, title: mission ? missionTitle(mission, language, fallback) : fallback };
  });
  const d = mapPath(items.length);
  const startHref = signedIn ? "/worlds" : "/register";
  const heroAt = mapCoords(0, items.length);

  return (
    <section className="py-10" aria-labelledby="landing-map-title">
      <div className="mb-5">
        <p className="text-xs font-bold uppercase tracking-widest text-primary mb-2">{t("landing.mapEyebrow")}</p>
        <h2 id="landing-map-title" className="font-title text-2xl sm:text-3xl lg:text-4xl text-text leading-tight">
          {t("landing.mapTitle")}
        </h2>
        <p className="text-muted text-sm sm:text-base leading-relaxed mt-2 max-w-2xl">{t("landing.mapDesc")}</p>
      </div>

      {/* на телефоне холст шире экрана и прокручивается по горизонтали, ничего не обрезая */}
      <div
        role="region"
        aria-label={t("landing.mapAria")}
        className="overflow-x-auto rounded-[2rem]"
      >
        <div className="relative h-[240px] sm:h-[280px] min-w-[760px] rounded-[2rem] border-8 border-ink bg-parchment shadow-2xl overflow-hidden">
          <MapBackdrop />
          <MapTrail d={d} revealed />

          {items.map((item, index) => {
            const coords = mapCoords(index, items.length);
            const locked = index > 0;
            const position = { left: `${coords.x}%`, top: `${coords.y}%` };
            const nodeClass =
              "absolute z-10 -translate-x-1/2 -translate-y-1/2 group rounded-full outline-none focus-visible:ring-4 focus-visible:ring-wax/60";
            const body = (
              <>
                {!locked && (
                  <span className="absolute inset-0 rounded-full bg-wax/40 animate-ping motion-reduce:animate-none" aria-hidden="true" />
                )}
                <span
                  className={`relative grid h-11 w-11 place-items-center rounded-full border-2 shadow-[0_4px_10px_rgba(62,39,35,0.4)] transition-transform duration-300 group-hover:scale-110 ${
                    locked ? "border-ink/60 bg-parchment text-ink" : "border-wax bg-parchment-light text-wax"
                  }`}
                >
                  {locked ? (
                    <Lock size={18} strokeWidth={2} aria-hidden="true" />
                  ) : (
                    <ScrollText size={22} strokeWidth={2.2} aria-hidden="true" />
                  )}
                </span>
                <span className="absolute left-1/2 top-full mt-1 w-28 -translate-x-1/2 truncate rounded bg-parchment-light/85 px-1 text-center text-xs font-bold text-ink-deep">
                  {item.title}
                </span>
              </>
            );
            return locked ? (
              <button
                key={item.id}
                type="button"
                className={nodeClass}
                style={position}
                aria-label={`${item.title}. ${t("landing.mapLocked")}`}
                aria-pressed={speaking === index}
                onClick={() => setSpeaking(index)}
              >
                {body}
              </button>
            ) : (
              <Link
                key={item.id}
                href={startHref}
                className={nodeClass}
                style={position}
                aria-label={`${item.title}. ${t("landing.mapOpen")}`}
              >
                {body}
              </Link>
            );
          })}

          {/* герой стоит у первого свитка */}
          <div
            className="absolute z-[5] pointer-events-none"
            style={{ left: `${heroAt.x}%`, top: `${heroAt.y}%` }}
            aria-hidden="true"
          >
            <span className="absolute left-0 top-0 grid h-8 w-8 -translate-x-1/2 -translate-y-[170%] place-items-center rounded-full border-2 border-wax bg-parchment-light text-wax shadow-[0_4px_10px_rgba(62,39,35,0.5)]">
              <Compass size={17} strokeWidth={2.5} />
            </span>
          </div>
        </div>
      </div>

      {/* реплика хранителя: под картой, чтобы не закрывать узлы */}
      <div
        role="status"
        aria-live="polite"
        className="mt-4 flex min-h-[3.5rem] flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-panel px-4 py-3"
      >
        <p className="text-sm text-muted">
          {speaking === null ? t("landing.mapHint") : lines.length ? lines[(speaking - 1) % lines.length] : ""}
        </p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm font-semibold">
          <Link href={startHref} className="text-primary hover:underline">
            {signedIn ? t("landing.mapToWorlds") : t("landing.mapRegister")}
          </Link>
          {!signedIn && (
            <Link href="/login" className="text-muted hover:text-text hover:underline">
              {t("landing.mapLogin")}
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
