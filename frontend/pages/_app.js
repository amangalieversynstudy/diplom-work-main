import "../styles/globals.css";
import "@xterm/xterm/css/xterm.css";
import { useEffect } from "react";
import { Toaster } from "sonner";
import { I18nProvider } from "../lib/i18n";
import { ThemeProvider, useTheme } from "../lib/theme";
import Head from "next/head"; // <-- ИМПОРТ
import gsap from "gsap";
import { useRouter } from "next/router";
import { MotionConfig } from "framer-motion";
import { prefersReducedMotion } from "../lib/motion";

async function initSmoothScroll() {
  const [{ default: Lenis }, { gsap }, { ScrollTrigger }] = await Promise.all([
    import("lenis"),
    import("gsap"),
    import("gsap/ScrollTrigger"),
  ]);
  gsap.registerPlugin(ScrollTrigger);
  // Меньше длительность + cubic ease-out = ощутимо «резче», без потери плавности.
  const lenis = new Lenis({
    duration: 0.8,
    easing: (t) => 1 - Math.pow(1 - t, 3),
    orientation: "vertical",
    smoothWheel: true,
    wheelMultiplier: 1.1,
    touchMultiplier: 1.8,
  });
  lenis.on("scroll", ScrollTrigger.update);
  const tick = (time) => { lenis.raf(time * 1000); };
  gsap.ticker.add(tick);
  const destroy = lenis.destroy.bind(lenis);
  lenis.destroy = () => { gsap.ticker.remove(tick); destroy(); };
  gsap.ticker.lagSmoothing(0);
  window.__lenis = lenis;
  return lenis;
}

function AppContent({ Component, pageProps }) {
  const { theme } = useTheme();
  return (
    <>
      <Component {...pageProps} />
      <Toaster theme={theme} richColors position="top-right" />
    </>
  );
}

// В редакторе и на экране миссии свои панели прокрутки, а на сенсорных экранах
// плавная прокрутка не нужна: Lenis там не включаем.
function smoothScrollAllowedPath(path) {
  return !/^\/(missions|studio)(\/|$|\?)/.test(path);
}

export default function MyApp({ Component, pageProps }) {
  const router = useRouter();
  const smooth = smoothScrollAllowedPath(router.asPath);
  useEffect(() => {
    let lenisInstance = null;
    let cancelled = false;
    // Плавная прокрутка и анимации отключаются, если пользователь просил
    // уменьшить движение в системе: твины GSAP доигрываются мгновенно.
    if (prefersReducedMotion()) {
      gsap.globalTimeline.timeScale(100);
      return undefined;
    }
    if (!smooth || window.matchMedia("(pointer: coarse)").matches) return undefined;
    initSmoothScroll().then((lenis) => {
      if (cancelled) lenis.destroy();
      else lenisInstance = lenis;
    });
    return () => {
      cancelled = true;
      if (lenisInstance) {
        lenisInstance.destroy();
        window.__lenis = null;
      }
    };
  }, [smooth]);

  return (
    <>
      <Head>
        <title>RPG Academy: учись программировать как в игре</title>
        <meta name="description" content="Игровая платформа для обучения программированию: миссии, битвы и награды." />
        <meta property="og:title" content="RPG Academy" />
        <meta property="og:description" content="Учись программировать, проходя миссии и сражения!" />
        <meta property="og:image" content="/og-image.png" />
        <meta property="og:type" content="website" />
        <meta name="twitter:card" content="summary_large_image" />
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        <link rel="icon" href="/favicon-32.png" sizes="32x32" />
        <link rel="icon" href="/favicon-16.png" sizes="16x16" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
      </Head>
      <MotionConfig reducedMotion="user">
        <I18nProvider>
          <ThemeProvider>
            <AppContent Component={Component} pageProps={pageProps} />
          </ThemeProvider>
        </I18nProvider>
      </MotionConfig>
    </>
  );
}