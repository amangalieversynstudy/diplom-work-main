import Link from "next/link";
import { useRouter } from "next/router";
import {
  Map, User2, Crown, Sparkles, Trophy, TrendingUp,
  ArrowUpRight, Sun, Moon, X, Eye, GraduationCap, LogOut
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useI18n, languages as supportedLanguages } from "../lib/i18n";
import { useTheme } from "../lib/theme";
import { Profile as ProfileAPI, revokeSession } from "../lib/api";
import TransitionLink from "./TransitionLink";
import { canTeach } from "../lib/roles";
import { VIEW_MODE_EVENT, isStudentView, setStudentView } from "../lib/viewMode";
import StreakReminder from "./StreakReminder";
import { motion } from "framer-motion";

const navLinks = [
  { href: "/worlds", labelKey: "nav.worlds", staffLabelKey: "nav.staffWorlds", icon: Map },
  { href: "/leaderboard", labelKey: "nav.legends", staffLabelKey: "nav.staffLegends", icon: Trophy },
  { href: "/journey", labelKey: "nav.journey", icon: TrendingUp },
  { href: "/profile", labelKey: "nav.character", staffLabelKey: "nav.staffCharacter", icon: User2 },
  { href: "/class", labelKey: "nav.class", icon: Crown },
];

// «Режим преподавателя / Глазами студента»: два положения, как у переключателя языка.
function ViewModeToggle({ studentView, onSwitch, t, className = "" }) {
  const modes = [
    [false, "pilot.viewMode.teacher", GraduationCap],
    [true, "pilot.viewMode.student", Eye],
  ];
  return (
    <div
      role="group"
      aria-label={t("pilot.viewMode.group")}
      className={`p-1 rounded-full border border-border bg-panel items-center gap-1 ${className}`}
    >
      {modes.map(([isStudent, key, Icon]) => {
        const active = studentView === isStudent;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={active}
            onClick={() => onSwitch(isStudent)}
            className={`inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-xs font-bold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 ${
              active ? "bg-primary text-on-primary" : "text-muted hover:text-text"
            }`}
          >
            <Icon size={14} aria-hidden="true" />
            {t(key)}
          </button>
        );
      })}
    </div>
  );
}

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
              isActive ? "text-on-primary" : "text-muted hover:text-text"
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

// Компактные переключатели для шапки на компьютере: одна кнопка на язык и одна на тему.
function CompactSettings() {
  const { language, setLanguage, t } = useI18n();
  const { theme, setTheme } = useTheme();
  const next = supportedLanguages.find((lang) => lang.id !== language) || supportedLanguages[0];
  const dark = theme === "dark";
  const cls =
    "grid h-10 w-10 place-items-center rounded-full border border-border bg-surface text-xs font-bold uppercase text-muted transition-colors hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60";
  return (
    <>
      <button type="button" onClick={() => setLanguage(next.id)} className={cls} aria-label={next.label} title={next.label}>
        {next.label}
      </button>
      <button
        type="button"
        onClick={() => setTheme(dark ? "light" : "dark")}
        className={cls}
        aria-label={t(dark ? "layout.themeLight" : "layout.themeDark")}
        title={t(dark ? "layout.themeLight" : "layout.themeDark")}
      >
        {dark ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
      </button>
    </>
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
      activeIcon: "text-on-primary",
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
  // аккаунт может преподавать; в режиме «Глазами студента» навигация у него ученическая
  const [isTeacherAccount, setIsTeacherAccount] = useState(false);
  const [studentView, setStudentViewState] = useState(false);
  const isStaff = isTeacherAccount && !studentView;
  const { t } = useI18n();
  const burgerRef = useRef(null);
  const closeRef = useRef(null);
  const menuRef = useRef(null);

  // Меню — модальное окно: фокус внутрь, Tab не выходит за его пределы, Escape
  // закрывает из любого места, а при закрытии фокус возвращается на кнопку меню.
  useEffect(() => {
    if (!isMenuOpen) return undefined;
    const burger = burgerRef.current; // кнопка на странице остаётся той же, пока открыто меню
    closeRef.current?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") {
        setIsMenuOpen(false);
        return;
      }
      if (e.key !== "Tab" || !menuRef.current) return;
      const items = [...menuRef.current.querySelectorAll("a[href], button, [tabindex]:not([tabindex='-1'])")].filter(
        (el) => !el.disabled
      );
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      burger?.focus();
    };
  }, [isMenuOpen]);

  // Преподавателю нужны кабинет, студия и аналитика, а «Мой путь» и «Класс» — экраны ученика.
  const staffLinks = useMemo(
    () => [
      { href: "/teacher", label: t("nav.teacher") },
      { href: "/studio", label: t("nav.studio") },
      { href: "/analytics", label: t("nav.analytics") },
    ],
    [t]
  );

  const translatedNavLinks = useMemo(
    () =>
      navLinks.map((item) => ({
        ...item,
        label: t(isStaff && item.staffLabelKey ? item.staffLabelKey : item.labelKey),
      })),
    [t, isStaff]
  );

  const menuLinks = !isAuthenticated
    ? []
    : isStaff
    ? translatedNavLinks.filter((item) => !["/journey", "/class"].includes(item.href))
    : translatedNavLinks;

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
        .then((me) => setIsTeacherAccount(canTeach(me)))
        .catch(() => setIsTeacherAccount(false));
    }
  }, []);

  // режим просмотра хранится в браузере: синхронизируем его с другими вкладками и экранами
  useEffect(() => {
    const sync = () => setStudentViewState(isStudentView());
    sync();
    window.addEventListener(VIEW_MODE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(VIEW_MODE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const switchView = (toStudent) => {
    setIsMenuOpen(false);
    if (toStudent === studentView) return;
    setStudentView(toStudent);
    toast.success(t(toStudent ? "pilot.viewMode.toastStudent" : "pilot.viewMode.toastTeacher"));
    const target = toStudent ? "/worlds" : "/teacher";
    if (router.pathname === target || router.asPath === target) {
      router.reload();
    } else {
      router.push(target);
    }
  };

  useEffect(() => {
    if (isMenuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
  }, [isMenuOpen]);

  const logout = async () => {
    await revokeSession();
    ["access", "refresh", "token", "access_token", "refresh_token", "view_as_student"].forEach((k) => localStorage.removeItem(k));
    setIsAuthenticated(false);
    setStudentViewState(false);
    setIsMenuOpen(false);
    router.push("/");
  };

  const isShrunk = scrolled && scrollDir === "down" && !isMenuOpen;

  return (
    <div className="min-h-screen flex flex-col text-text bg-bg relative overflow-x-hidden transition-colors duration-300">
      {/* Ссылка для клавиатуры: сразу к содержимому, минуя шапку и меню */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[1200] focus:rounded-lg focus:bg-panel focus:px-4 focus:py-2 focus:text-text focus:shadow-lg focus:ring-2 focus:ring-primary"
      >
        {t("layout.skipToContent")}
      </a>


      <header
        className={`fixed top-0 inset-x-0 z-[110] transition-all duration-500 ${
          (scrolled || fullBleed) && !isMenuOpen
            ? `bg-surface/90 backdrop-blur-md border-b border-border shadow-sm pointer-events-auto ${isShrunk ? "py-2" : "py-4"}`
            : "bg-transparent py-5 " + (isMenuOpen ? "pointer-events-none" : "pointer-events-auto")
        }`}
      >
        <div className="max-w-7xl 2xl:max-w-[87.5rem] 3xl:max-w-[100rem] 4xl:max-w-[120rem] mx-auto px-6 flex items-center justify-between gap-6">
          {/* спокойный логотип: без прыгающих букв и вращений */}
          <TransitionLink
            href="/"
            className={`flex shrink-0 items-center gap-2.5 ${isMenuOpen ? "pointer-events-none opacity-40" : ""}`}
          >
            <span className="grid h-9 w-9 place-items-center rounded-xl border border-primary/20 bg-primary/10">
              <Sparkles size={18} className="text-primary" aria-hidden="true" />
            </span>
            <span className="font-display text-xl font-bold uppercase tracking-tight text-text sm:text-2xl">RPG Academy</span>
          </TransitionLink>

          {/* на компьютере все разделы роли в шапке; выдвижное меню только на узких экранах */}
          <nav aria-label={t("layout.nav")} className="hidden xl:flex min-w-0 flex-1 items-center justify-center gap-0.5">
            {(!isAuthenticated ? [] : isStaff ? [...staffLinks, ...menuLinks] : menuLinks).map((item) => {
              const active = router.pathname === item.href || router.pathname.startsWith(`${item.href}/`);
              return (
                <TransitionLink
                  key={item.href}
                  href={item.href}
                  className={`rounded-full px-3 py-2 text-sm font-semibold transition-colors ${
                    active ? "bg-primary/10 text-primary" : "text-muted hover:bg-panel hover:text-text"
                  }`}
                >
                  {item.label}
                </TransitionLink>
              );
            })}
          </nav>

          <div className="flex shrink-0 items-center justify-end gap-2">
            {isAuthenticated && isTeacherAccount && (
              <ViewModeToggle studentView={studentView} onSwitch={switchView} t={t} className="hidden xl:flex" />
            )}
            <div className="hidden xl:flex items-center gap-2">
              <CompactSettings />
            </div>
            {isAuthenticated && (
              <button
                type="button"
                onClick={logout}
                aria-label={t("layout.logout")}
                title={t("layout.logout")}
                className="hidden xl:grid h-10 w-10 place-items-center rounded-full border border-border bg-surface text-muted transition-colors hover:text-error"
              >
                <LogOut size={17} aria-hidden="true" />
              </button>
            )}
            {!isAuthenticated && (
              <TransitionLink
                href="/login"
                className="hidden lg:inline-flex rounded-full border border-border bg-surface px-4 py-2 text-sm font-semibold text-text transition-colors hover:bg-panel"
              >
                {t("layout.login")}
              </TransitionLink>
            )}
            {!isAuthenticated && (
              <TransitionLink
                href="/register"
                className="hidden lg:inline-flex rounded-full bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition-colors hover:bg-primary-dk"
              >
                {t("layout.register")}
              </TransitionLink>
            )}
            <button
              ref={burgerRef}
              onClick={() => setIsMenuOpen(true)}
              aria-expanded={isMenuOpen}
              aria-controls="site-menu"
              aria-label={t("layout.nav")}
              className={`xl:hidden relative z-[110] grid h-10 w-10 place-items-center rounded-full border border-border bg-surface hover:bg-panel ${isMenuOpen ? "opacity-0 pointer-events-none" : "pointer-events-auto"}`}
            >
              <span className="flex flex-col gap-1.5" aria-hidden="true">
                <span className="block w-5 h-[2px] bg-text" />
                <span className="block w-5 h-[2px] bg-text" />
                <span className="block w-5 h-[2px] bg-text" />
              </span>
            </button>
          </div>
        </div>
      </header>

      <StreakReminder />

      {/* «Глазами студента»: всегда видно, в каком режиме преподаватель, и путь назад в один клик */}
      {isAuthenticated && isTeacherAccount && studentView && !isMenuOpen && (
        <div
          role="status"
          className="fixed bottom-4 left-4 right-4 z-[80] flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl border border-primary/30 bg-surface/95 px-4 py-3 shadow-lg backdrop-blur-md sm:right-auto sm:max-w-xl"
        >
          <Eye size={18} className="shrink-0 text-primary" aria-hidden="true" />
          <p className="min-w-0 flex-[1_1_12rem] text-xs leading-snug text-text">{t("pilot.viewMode.banner")}</p>
          <button
            type="button"
            onClick={() => switchView(false)}
            className="min-h-[36px] w-full rounded-full bg-primary px-3 text-xs font-bold text-on-primary transition-colors hover:bg-primary-dk sm:w-auto"
          >
            {t("pilot.viewMode.back")}
          </button>
        </div>
      )}

      <main id="main-content" tabIndex={-1} className={fullBleed ? "relative w-full flex-1" : `w-full flex-1 max-w-7xl 2xl:max-w-[87.5rem] 3xl:max-w-[100rem] 4xl:max-w-[120rem] mx-auto px-6 relative ${noBottomPadding ? "pt-10 pb-0" : "py-10"}`}>
        {children}
        {isAuthenticated && isTeacherAccount && studentView && (
          <div aria-hidden="true" className="h-28 shrink-0" />
        )}
      </main>

      {/* ── Sidebar Menu Drawer ── */}
      <div
        aria-hidden="true"
        className={`fixed inset-0 z-[90] bg-modal-overlay backdrop-blur-sm transition-opacity duration-500 ${
          isMenuOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={() => setIsMenuOpen(false)}
      />

      {/* Контейнер меню (справа) */}
      <div
        id="site-menu"
        ref={menuRef}
        role="dialog"
        aria-modal={isMenuOpen ? "true" : undefined}
        aria-label={t("layout.nav")}
        aria-hidden={isMenuOpen ? undefined : "true"}
        // закрытое меню только сдвинуто за экран: inert убирает его из порядка Tab и из дерева доступности
        inert={isMenuOpen ? undefined : ""}
        className={`fixed top-0 right-0 bottom-0 w-full max-w-[400px] z-[100] bg-surface border-l border-border shadow-2xl flex flex-col overflow-hidden transition-transform duration-500 ease-[cubic-bezier(0.6,0.05,0.01,0.9)] transition-colors duration-300 ${
          isMenuOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Контент меню */}
        <div
          className="relative z-10 w-full h-full flex flex-col pointer-events-auto"
        >
          <button
            ref={closeRef}
            onClick={() => setIsMenuOpen(false)}
            aria-label={t("layout.closeMenu")}
            className="absolute top-6 right-6 z-20 w-11 h-11 rounded-full border border-border bg-panel text-text flex items-center justify-center hover:text-primary hover:rotate-90 transition-all duration-300 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
          >
            <X size={20} strokeWidth={2.5} />
          </button>
          <div className="flex-1 overflow-y-auto pt-24 px-8 flex flex-col gap-6">
            {isAuthenticated && isTeacherAccount && (
              <ViewModeToggle studentView={studentView} onSwitch={switchView} t={t} className="flex self-start" />
            )}
            <span className="text-sm font-semibold text-faint uppercase tracking-wider">{t("layout.nav")}</span>
            <div className="flex flex-col gap-6">
            {menuLinks.map((item) => (
              <TransitionLink
                key={item.href}
                href={item.href}
                onClick={() => setIsMenuOpen(false)}
                className="group flex items-center gap-4 text-3xl font-bold text-text hover:text-primary transition-colors"
              >
                <span className="group-hover:text-[var(--primary)] transition-colors">{item.label}</span>
                <div className="w-8 h-8 rounded-full bg-[var(--primary)] text-on-primary flex items-center justify-center opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
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
                <div className="w-8 h-8 rounded-full bg-[var(--primary)] text-on-primary flex items-center justify-center opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
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
                <div className="w-8 h-8 rounded-full bg-[var(--primary)] text-on-primary flex items-center justify-center opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
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
                <div className="w-8 h-8 rounded-full bg-[var(--primary)] text-on-primary flex items-center justify-center opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
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
                <TransitionLink href="/register" onClick={() => setIsMenuOpen(false)} className="w-full py-3 rounded-xl bg-primary text-on-primary shadow-glow font-semibold text-center hover:scale-[1.02] transition-transform">
                  {t("layout.register")}
                </TransitionLink>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <button
                  onClick={logout}
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
                {menuLinks
                  .filter((item) => item.href !== "/class")
                  .map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="inline-block py-2 hover:text-primary-dk transition-colors"
                    >
                      {item.label}
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
