import Link from "next/link";
import {
  Map,
  Swords,
  User2,
  Crown,
  Sparkles,
  Trophy,
  Shield,
  LogIn,
  UserPlus,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getPlayerClass } from "../lib/class";

const navLinks = [
  { href: "/", label: "Sanctum", icon: Sparkles },
  { href: "/worlds", label: "Worlds", icon: Map },
  { href: "/missions/1", label: "Quest", icon: Swords },
  { href: "/leaderboard", label: "Legends", icon: Trophy },
  { href: "/profile", label: "Character", icon: User2 },
  { href: "/class", label: "Class", icon: Crown },
];

export default function Layout({ children }) {
  const [pclass, setPclass] = useState(null);

  useEffect(() => {
    setPclass(getPlayerClass());
  }, []);

  return (
    <div className="min-h-screen text-white relative overflow-hidden">
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-b from-[#05060f] via-[#0f172a] to-[#030712]" />
        <div className="starfield" aria-hidden />
        <div className="absolute -left-32 top-12 w-96 h-96 bg-primary/30 blur-[140px] rounded-full animate-float" />
        <div className="absolute right-0 top-20 w-[420px] h-[420px] bg-accent/25 blur-[160px] rounded-full animate-float" />
        <div className="absolute bottom-[-120px] left-1/2 -translate-x-1/2 w-[520px] h-[520px] bg-gold/10 blur-[200px] rounded-full" />
      </div>

      <header className="sticky top-0 z-20 border-b border-white/10 bg-[#05060f]/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <Link href="/" className="font-display text-xl tracking-wider inline-flex items-center gap-3">
              <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs uppercase tracking-[0.3em]">
                RPG Academy
              </span>
              <span className="text-accent/90 text-sm">Build your legend</span>
            </Link>
            <div className="flex items-center gap-2 text-xs text-white/70">
              <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/15 bg-white/5">
                <Shield size={14} className="text-accent" />
                Season: Obsidian Dawn
              </span>
              {pclass && (
                <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/15 bg-white/5">
                  <Crown size={14} className="text-gold" />
                  {pclass}
                </span>
              )}
            </div>
          </div>
          <nav className="flex flex-wrap items-center gap-3 text-sm">
            {navLinks.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 transition"
              >
                <item.icon size={16} className="text-accent" />
                {item.label}
              </Link>
            ))}
            <div className="flex-1" />
            <Link
              href="/login"
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 hover:border-accent/60"
            >
              <LogIn size={16} /> Login
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/30 border border-accent/40 hover:bg-accent/40"
            >
              <UserPlus size={16} /> Join Legion
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 relative">
        <div className="absolute -z-10 inset-0 pointer-events-none">
          <div className="hidden md:block absolute inset-x-16 top-0 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent" />
        </div>
        {children}
      </main>

      <footer className="border-t border-white/10 bg-black/30 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 py-4 text-xs text-white/60 flex flex-wrap gap-3 justify-between">
          <span>© {new Date().getFullYear()} RPG Academy</span>
          <span>Made for the Diploma questline</span>
        </div>
      </footer>
    </div>
  );
}
