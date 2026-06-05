import Link from "next/link";
import { useRouter } from "next/router";
import {
  Map, Swords, User2, Crown, Sparkles, Trophy,
  ArrowUpRight, Sun, Moon, X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useI18n, languages as supportedLanguages } from "../lib/i18n";
import { useTheme } from "../lib/theme";
import { Profile as ProfileAPI } from "../lib/api";
import CustomCursor from "./CustomCursor";
import TransitionLink from "./TransitionLink";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { motion } from "framer-motion";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

const navLinks = [
  { href: "/worlds", labelKey: "nav.worlds", icon: Map },
  { href: "/missions/1", labelKey: "nav.quest", icon: Swords },
  { href: "/leaderboard", labelKey: "nav.legends", icon: Trophy },
  { href: "/profile", labelKey: "nav.character", icon: User2 },
  { href: "/class", labelKey: "nav.class", icon: Crown },
];

function LanguageToggle() {
  const { language, setLanguage } = useI18n();

  return (
    <div className="relative p-1 rounded-full border border-border bg-panel flex items-center gap-1">
      {supportedLanguages.map((lang) => {
        const isActive = language === lang.id;
        return (
          <button
            key={lang.id}
            type="button"
            onClick={() => setLanguage(lang.id)}
            aria-pressed={isActive}
            className={`relative h-10 px-4 rounded-full text-xs font-bold uppercase tracking-wide transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 ${
              isActive ? "text-white" : "text-muted hover:text-text"
            }`}
          >
            {isActive && (
              <motion.span
                layoutId="lang-switcher-pill"
                className="absolute inset-0 rounded-full bg-primary"
                style={{ boxShadow: "0 0 18px var(--primary-selection)" }}
                transition={{ type: "spring", stiffness: 380, damping: 28 }}
              />
            )}
            <span className="relative z-10">{lang.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();

  const options = [
    {
      id: "light",
      icon: Sun,
      label: t("layout.themeLight"),
      activeBg: "bg-surface",
      activeIcon: "text-accent",
      glow: "0 0 18px var(--primary-selection)",
      idleRotate: -35,
    },
    {
      id: "dark",
      icon: Moon,
      label: t("layout.themeDark"),
      activeBg: "bg-primary",
      activeIcon: "text-white",
      glow: "0 0 22px var(--primary)",
      idleRotate: 35,
    },
  ];

  return (
    <div className="relative p-1 rounded-full border border-border bg-panel flex items-center gap-1">
      {options.map(({ id, icon: Icon, label, activeBg, activeIcon, glow, idleRotate }) => {
        const isActive = theme === id;
        return (
          <motion.button
            key={id}
            type="button"
            onClick={() => setTheme(id)}
            aria-label={label}
            aria-pressed={isActive}
            whileTap={{ scale: 0.92 }}
            className="relative w-10 h-10 rounded-full flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
          >
            {isActive && (
              <motion.span
                layoutId="theme-switcher-pill"
                className={`absolute inset-0 rounded-full ${activeBg}`}
                style={{ boxShadow: glow }}
                transition={{ type: "spring", stiffness: 380, damping: 28 }}
              />
            )}
            <motion.span
              animate={{
                rotate: isActive ? 0 : idleRotate,
                scale: isActive ? 1 : 0.82,
                opacity: isActive ? 1 : 0.55,
              }}
              transition={{ type: "spring", stiffness: 320, damping: 22 }}
              className="relative z-10 flex items-center justify-center"
            >
              <Icon
                size={18}
                className={`transition-colors duration-300 ${isActive ? activeIcon : "text-muted"}`}
              />
            </motion.span>
          </motion.button>
        );
      })}
    </div>
  );
}

export default function Layout({ children, hideFooter, noBottomPadding, fullBleed }) {
  const router = useRouter();
  const [scrolled, setScrolled] = useState(false);
  const [scrollDir, setScrollDir] = useState("up");
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isStaff, setIsStaff] = useState(false);
  const { t } = useI18n();

  const translatedNavLinks = useMemo(
    () =>
      navLinks.map((item) => ({
        ...item,
        label: t(item.labelKey),
      })),
    [t]
  );

  useEffect(() => {
    let lastScrollY = window.scrollY;
    const onScroll = () => {
      const currentScrollY = Math.max(window.scrollY, 0);
      setScrolled(currentScrollY > 24);
      
      if (Math.abs(currentScrollY - lastScrollY) < 10) return;
      
      if (currentScrollY > lastScrollY && currentScrollY > 80) {
        setScrollDir("down");
      } else if (currentScrollY < lastScrollY) {
        setScrollDir("up");
      }
      lastScrollY = currentScrollY;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    // Проверяем наличие токена авторизации
    const token = localStorage.getItem("access") || localStorage.getItem("token") || localStorage.getItem("access_token");
    setIsAuthenticated(!!token);
    // Ссылку на аналитику показываем только staff. Профиль запрашиваем
    // лишь при наличии токена — чтобы у анонимных посетителей публичных
    // страниц не дёргать API и не словить редирект на /login.
    if (token) {
      ProfileAPI.me()
        .then((me) => setIsStaff(!!(me?.is_staff ?? me?.user?.is_staff)))
        .catch(() => setIsStaff(false));
    }
  }, []);

  useEffect(() => {
    if (isMenuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
  }, [isMenuOpen]);

  useGSAP(() => {
    // On page load: overlay slides UP to reveal the page.
    // Works correctly in both cases:
    // - First visit: overlay was at yPercent:0 (visible) and slides up
    // - After navigation: TransitionLink left overlay at yPercent:0, now it slides up revealing new page
    gsap.fromTo(
      ".page-transition-overlay",
      { yPercent: 0 },
      { yPercent: -100, duration: 0.8, ease: "power3.inOut" }
    );
  }, []);

  const isShrunk = scrolled && scrollDir === "down" && !isMenuOpen;

  return (
    <div className="min-h-screen text-text bg-bg relative overflow-x-hidden transition-colors duration-300">
      {/* ── Page Transition Overlay ── */}
      {/* ── Page Transition Overlay ──
           Slides DOWN to cover page (TransitionLink on click)
           Slides UP to reveal page (Layout on mount)
           Does NOT trigger on errors/toasts — only during real navigation */}
      <div className="page-transition-overlay fixed inset-0 z-[999] bg-[var(--primary)] origin-top flex items-center justify-center pointer-events-none">
        <Sparkles className="w-12 h-12 text-white animate-spin-slow" />
      </div>

      <CustomCursor />

      <header
        className={`fixed top-0 inset-x-0 z-[110] transition-all duration-500 ${
          (scrolled || fullBleed) && !isMenuOpen
            ? `bg-surface/90 backdrop-blur-md border-b border-border shadow-sm pointer-events-auto ${isShrunk ? "py-2" : "py-4"}`
            : "bg-transparent py-5 " + (isMenuOpen ? "pointer-events-none" : "pointer-events-auto")
        }`}
      >
        <div className="max-w-7xl 2xl:max-w-[87.5rem] 3xl:max-w-[100rem] 4xl:max-w-[120rem] mx-auto px-6 flex items-center justify-between relative">
          {/* Пустой блок слева для балансировки флекс-контейнера */}
          <div className={`transition-all duration-500 ${isShrunk ? "w-10" : "w-12"}`} />

          {/* Центрированный интерактивный логотип */}
          <TransitionLink
            href="/"
            className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 group flex items-center px-2 sm:px-4 py-2 transition-all duration-500 ${isMenuOpen ? "pointer-events-none opacity-40 blur-md" : "pointer-events-auto"}`}
          >
            <div className={`relative rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center overflow-hidden transition-all duration-500 group-hover:scale-110 group-hover:shadow-[0_0_20px_var(--primary-selection)] mr-2 sm:mr-3 ${isShrunk ? "w-6 h-6 md:w-8 md:h-8" : "w-8 h-8 md:w-10 md:h-10"}`}>
              <Sparkles size={18} className={`text-primary relative z-10 transition-transform duration-700 group-hover:rotate-180 ${isShrunk ? "scale-75" : "scale-100"}`} />
            </div>
            <div className={`font-display font-bold tracking-tighter uppercase flex items-center text-text transition-all duration-500 ${isShrunk ? "text-base sm:text-xl md:text-3xl" : "text-lg sm:text-2xl md:text-4xl"}`}>
              {"RPG ACADEMY".split("").map((char, index) => (
                <span
                  key={index}
                  className="inline-block transition-all duration-200 ease-out hover:-translate-y-2 hover:text-transparent hover:bg-clip-text hover:bg-gradient-to-br hover:from-primary hover:to-accent"
                >
                  {char === " " ? "\u00A0" : char}
                </span>
              ))}
            </div>
          </TransitionLink>

          <button
            onClick={() => setIsMenuOpen(true)}
            aria-label={t("layout.nav")}
            className={`relative z-[110] rounded-full bg-surface border border-border shadow-sm flex flex-col justify-center items-center gap-1.5 hover:bg-panel transition-all duration-500 active:scale-95 ${isShrunk ? "w-10 h-10" : "w-12 h-12"} ${isMenuOpen ? "opacity-0 pointer-events-none" : "pointer-events-auto"}`}
          >
            <span className="block w-5 h-[2px] bg-text" />
            <span className="block w-5 h-[2px] bg-text" />
            <span className="block w-5 h-[2px] bg-text" />
          </button>
        </div>
      </header>

      <main className={fullBleed ? "relative" : `max-w-7xl 2xl:max-w-[87.5rem] 3xl:max-w-[100rem] 4xl:max-w-[120rem] mx-auto px-6 relative ${noBottomPadding ? "pt-10 pb-0" : "py-10"}`}>
        {children}
      </main>

      {/* ── Sidebar Menu Drawer ── */}
      <div
        role="button"
        tabIndex={isMenuOpen ? 0 : -1}
        aria-label={t("layout.closeMenu")}
        className={`fixed inset-0 z-[90] bg-modal-overlay backdrop-blur-sm transition-opacity duration-500 ${
          isMenuOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={() => setIsMenuOpen(false)}
        onKeyDown={(e) => e.key === "Escape" && setIsMenuOpen(false)}
      />

      {/* Контейнер меню (справа) */}
      <div
        className={`fixed top-0 right-0 bottom-0 w-full max-w-[400px] z-[100] bg-surface border-l border-border shadow-2xl flex flex-col overflow-hidden transition-transform duration-500 ease-[cubic-bezier(0.6,0.05,0.01,0.9)] transition-colors duration-300 ${
          isMenuOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Контент меню */}
        <div
          className="relative z-10 w-full h-full flex flex-col pointer-events-auto"
        >
          <button
            onClick={() => setIsMenuOpen(false)}
            aria-label={t("layout.closeMenu")}
            className="absolute top-6 right-6 z-20 w-11 h-11 rounded-full border border-border bg-panel text-text flex items-center justify-center hover:text-primary hover:rotate-90 transition-all duration-300 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
          >
            <X size={20} strokeWidth={2.5} />
          </button>
          <div className="flex-1 overflow-y-auto pt-24 px-8 flex flex-col gap-6">
            <span className="text-sm font-semibold text-faint uppercase tracking-wider">{t("layout.nav")}</span>
            <div className="flex flex-col gap-6">
            {translatedNavLinks.map((item) => (
              <TransitionLink
                key={item.href}
                href={item.href}
                onClick={() => setIsMenuOpen(false)}
                className="group flex items-center gap-4 text-3xl font-bold text-text hover:text-primary transition-colors"
              >
                <span className="group-hover:text-[var(--primary)] transition-colors">{item.label}</span>
                <div className="w-8 h-8 rounded-full bg-[var(--primary)] text-white flex items-center justify-center opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
                  <ArrowUpRight className="w-5 h-5" />
                </div>
              </TransitionLink>
            ))}
            {isStaff && (
              <TransitionLink
                href="/analytics"
                onClick={() => setIsMenuOpen(false)}
                className="group flex items-center gap-4 text-3xl font-bold text-text hover:text-primary transition-colors"
              >
                <span className="group-hover:text-[var(--primary)] transition-colors">
                  {t("analytics.title")}
                </span>
                <div className="w-8 h-8 rounded-full bg-[var(--primary)] text-white flex items-center justify-center opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
                  <ArrowUpRight className="w-5 h-5" />
                </div>
              </TransitionLink>
            )}
            {isStaff && (
              <TransitionLink
                href="/teacher"
                onClick={() => setIsMenuOpen(false)}
                className="group flex items-center gap-4 text-3xl font-bold text-text hover:text-primary transition-colors"
              >
                <span className="group-hover:text-[var(--primary)] transition-colors">
                  {t("teacher.title")}
                </span>
                <div className="w-8 h-8 rounded-full bg-[var(--primary)] text-white flex items-center justify-center opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
                  <ArrowUpRight className="w-5 h-5" />
                </div>
              </TransitionLink>
            )}
            {isStaff && (
              <TransitionLink
                href="/studio"
                onClick={() => setIsMenuOpen(false)}
                className="group flex items-center gap-4 text-3xl font-bold text-text hover:text-primary transition-colors"
              >
                <span className="group-hover:text-[var(--primary)] transition-colors">
                  {t("studio.title")}
                </span>
                <div className="w-8 h-8 rounded-full bg-[var(--primary)] text-white flex items-center justify-center opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
                  <ArrowUpRight className="w-5 h-5" />
                </div>
              </TransitionLink>
            )}
          </div>

          <div className="mt-auto pb-10 border-t border-border pt-6 flex flex-col gap-4">
            {!isAuthenticated ? (
              <div className="flex flex-col gap-3">
                <TransitionLink href="/login" onClick={() => setIsMenuOpen(false)} className="w-full py-3 rounded-xl border border-border text-muted font-semibold text-center hover:bg-panel transition-colors">
                  {t("layout.login")}
                </TransitionLink>
                <TransitionLink href="/register" onClick={() => setIsMenuOpen(false)} className="w-full py-3 rounded-xl bg-primary text-white shadow-glow font-semibold text-center hover:scale-[1.02] transition-transform">
                  {t("layout.register")}
                </TransitionLink>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <button
                  onClick={() => {
                    ["access", "refresh", "token", "access_token", "refresh_token"].forEach(k => localStorage.removeItem(k));
                    setIsAuthenticated(false);
                    setIsMenuOpen(false);
                    router.push("/");
                  }}
                  className="w-full py-3 rounded-xl border border-border text-muted font-semibold text-center hover:bg-panel hover:text-error transition-colors"
                >
                  {t("layout.logout")}
                </button>
              </div>
            )}
            <div className="flex justify-center items-center gap-4 mt-4">
              <LanguageToggle />
              <ThemeSwitcher />
            </div>
          </div>
        </div>
      </div>
      </div>

      {!hideFooter && (
        <footer className="border-t border-border bg-surface/50 backdrop-blur-xl mt-20 transition-colors duration-300">
          <div className="max-w-7xl 2xl:max-w-[87.5rem] 3xl:max-w-[100rem] 4xl:max-w-[120rem] mx-auto px-6 py-6">
            <div className="flex flex-wrap items-center justify-between gap-4 text-xs text-muted">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-lg border-primary/20 bg-primary/10 flex items-center justify-center">
                  <Sparkles size={11} className="text-primary" />
                </div>
                <span>© {new Date().getFullYear()} RPG Academy</span>
              </div>
              <span>{t("layout.footerNote")}</span>
              <div className="flex items-center gap-4">
                {["/worlds", "/profile", "/leaderboard"].map((href) => (
                  <Link key={href} href={href} className="hover:text-primary-dk transition-colors">
                    {href.slice(1).charAt(0).toUpperCase() + href.slice(2)}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </footer>
      )}
    </div>
  );
}
