import "../styles/globals.css";
import "@xterm/xterm/css/xterm.css";
import { useEffect } from "react";
import { Toaster } from "sonner";
import { I18nProvider } from "../lib/i18n";
import { ThemeProvider, useTheme } from "../lib/theme";
import Head from "next/head"; // <-- ИМПОРТ

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
  gsap.ticker.add((time) => { lenis.raf(time * 1000); });
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

export default function MyApp({ Component, pageProps }) {
  useEffect(() => {
    let lenisInstance = null;
    initSmoothScroll().then((lenis) => { lenisInstance = lenis; });
    return () => {
      if (lenisInstance) {
        lenisInstance.destroy();
        window.__lenis = null;
      }
    };
  }, []);

  return (
    <>
      <Head>
        <title>RPG Academy</title>
        <meta name="description" content="A gamified platform for learning programming." />
        <meta property="og:title" content="RPG Academy" />
        <meta property="og:description" content="Learn to code by completing missions and battles!" />
        <meta property="og:image" content="/og-image.png" />
        <meta property="og:type" content="website" />
        <meta name="twitter:card" content="summary_large_image" />
        <link rel="icon" href="/favicon-32.png" sizes="32x32" />
        <link rel="icon" href="/favicon-16.png" sizes="16x16" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
      </Head>
      <I18nProvider>
        <ThemeProvider>
          <AppContent Component={Component} pageProps={pageProps} />
        </ThemeProvider>
      </I18nProvider>
    </>
  );
}