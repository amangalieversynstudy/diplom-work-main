import Link from "next/link";
import {
  Home,
  Globe2,
  Trophy,
  User,
  LogIn,
  UserPlus,
  Crown,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getPlayerClass } from "../lib/class";

export default function Layout({ children }) {
  const [pclass, setPclass] = useState(null);
  useEffect(() => {
    setPclass(getPlayerClass());
  }, []);
  return (
    <div className="min-h-screen bg-bg text-white">
      <header className="sticky top-0 z-10 bg-surface/80 backdrop-blur border-b border-white/10">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="font-bold text-lg inline-flex items-center gap-2">
            RPG Academy{" "}
            {pclass && (
              <span className="text-xs bg-white/10 px-2 py-1 rounded inline-flex items-center gap-1">
                <Crown size={14} /> {pclass}
              </span>
            )}
          </div>
          <nav className="flex gap-4 text-sm items-center">
            <Link
              className="hover:text-accent inline-flex items-center gap-2"
              href="/"
            >
              <Home size={16} />
              Dashboard
            </Link>
            <Link
              className="hover:text-accent inline-flex items-center gap-2"
              href="/worlds"
            >
              <Globe2 size={16} />
              Worlds
            </Link>
            <Link
              className="hover:text-accent inline-flex items-center gap-2"
              href="/leaderboard"
            >
              <Trophy size={16} />
              Leaderboard
            </Link>
            <Link
              className="hover:text-accent inline-flex items-center gap-2"
              href="/profile"
            >
              <User size={16} />
              Profile
            </Link>
            <Link
              className="hover:text-accent inline-flex items-center gap-2"
              href="/class"
            >
              <Crown size={16} />
              Choose Class
            </Link>
            <span className="opacity-30">|</span>
            <Link
              className="hover:text-accent inline-flex items-center gap-2"
              href="/login"
            >
              <LogIn size={16} />
              Login
            </Link>
            <Link
              className="hover:text-accent inline-flex items-center gap-2"
              href="/register"
            >
              <UserPlus size={16} />
              Register
            </Link>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
