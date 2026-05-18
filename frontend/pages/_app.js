import "../styles/globals.css";
import { useEffect } from "react";
import { Toaster } from "sonner";
import { I18nProvider } from "../lib/i18n";
import { ThemeProvider, useTheme } from "../lib/theme";

// Initialise Lenis + GSAP ScrollTrigger in one place so every page benefits.
// Dynamic imports keep Next.js SSR happy (these libs touch window/document).
async function initSmoothScroll() {
  const [{ default: Lenis }, { gsap }, { ScrollTrigger }] = await Promise.all([
    import("lenis"),
    import("gsap"),
    import("gsap/ScrollTrigger"),
  ]);

  gsap.registerPlugin(ScrollTrigger);

  const lenis = new Lenis({
    duration: 1.2,
    easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    orientation: "vertical",
    gestureOrientation: "vertical",
    smoothWheel: true,
    wheelMultiplier: 1,
    touchMultiplier: 2,
  });

  // Sync ScrollTrigger with Lenis
  lenis.on("scroll", ScrollTrigger.update);

  gsap.ticker.add((time) => {
    lenis.raf(time * 1000);
  });

  gsap.ticker.lagSmoothing(0);

  // Expose globally so individual pages can access the instance
  window.__lenis = lenis;

  return lenis;
}

function AppContent({ Component, pageProps }) {
  const { theme } = useTheme();

  return (
    <>
      <Component {...pageProps} />
      <Toaster
        theme={theme}
        richColors
        position="top-right"
      />
    </>
  );
}

export default function MyApp({ Component, pageProps }) {
  useEffect(() => {
    let lenisInstance = null;
    initSmoothScroll().then((lenis) => {
      lenisInstance = lenis;
    });
    return () => {
      if (lenisInstance) {
        lenisInstance.destroy();
        window.__lenis = null;
      }
    };
  }, []);

  return (
    <I18nProvider>
      <ThemeProvider>
        <AppContent Component={Component} pageProps={pageProps} />
      </ThemeProvider>
    </I18nProvider>
  );
}
