/**
 * Email verification landing page.
 *
 * Backend RegisterView sends an email containing
 *   {FRONTEND_URL}/verify-email?uid=<base64>&token=<token>
 *
 * Reads `uid` + `token` from query and GETs
 * `/api/auth/verify-email/?uid=<>&token=<>` to activate the account.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { motion, AnimatePresence } from "framer-motion";
import Layout from "../components/Layout";
import api from "../lib/api";
import { Sparkles, Mail, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

export default function VerifyEmail() {
  const router = useRouter();
  const [status, setStatus] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!router.isReady) return;

    const { uid, token } = router.query;
    if (!uid || !token) {
      setStatus("error");
      setErrorMessage("Ссылка повреждена: отсутствует uid или token.");
      return;
    }

    api
      .get("/auth/verify-email/", { params: { uid, token } })
      .then(() => {
        setStatus("success");
        toast.success("Магическая печать снята! Добро пожаловать.");
        setTimeout(() => router.push("/login"), 3000);
      })
      .catch((err) => {
        setStatus("error");
        const detail =
          err?.response?.data?.detail || "Свиток поврежден или уже использован.";
        setErrorMessage(detail);
        toast.error(detail);
      });
  }, [router.isReady, router.query, router]);

  return (
    <Layout>
      <div className="flex items-center justify-center min-h-[70vh] px-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={status}
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -8 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="relative w-full max-w-md text-center rounded-[2.5rem] border border-border bg-surface p-10 md:p-14 overflow-hidden shadow-[0_0_40px_var(--primary-selection)]"
          >
            <div className="absolute inset-0 bg-gradient-to-b from-primary/15 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
              {status === "loading" && <LoadingState />}
              {status === "success" && <SuccessState />}
              {status === "error" && (
                <ErrorState
                  message={errorMessage}
                  onBack={() => router.push("/login")}
                />
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </Layout>
  );
}

function LoadingState() {
  return (
    <>
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 4, ease: "linear" }}
        className="w-20 h-20 mx-auto rounded-full bg-panel border border-border flex items-center justify-center mb-6 shadow-inner"
      >
        <Sparkles size={36} className="text-primary opacity-80" />
      </motion.div>
      <p className="text-xs uppercase tracking-widest text-primary mb-3 font-bold">
        Активация
      </p>
      <h1 className="text-3xl md:text-4xl font-display font-bold text-text mb-3">
        Расшифровка свитка...
      </h1>
      <p className="text-muted">Подожди, пока мы проверим твои печати.</p>
    </>
  );
}

function SuccessState() {
  return (
    <>
      <motion.div
        initial={{ scale: 0, rotate: -45 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ type: "spring", stiffness: 220, damping: 14, delay: 0.1 }}
        className="w-24 h-24 mx-auto rounded-full bg-primary/15 border-2 border-primary flex items-center justify-center mb-6 shadow-[0_0_30px_var(--primary)]"
      >
        <ShieldCheck size={48} className="text-primary" />
      </motion.div>
      <motion.p
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.4 }}
        className="text-xs uppercase tracking-widest text-primary mb-3 font-bold"
      >
        Печать снята
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.4 }}
        className="text-3xl md:text-4xl font-display font-bold text-text mb-4"
      >
        Путь открыт!
      </motion.h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5, duration: 0.4 }}
        className="text-muted text-lg"
      >
        Перенаправляем в зал входа...
      </motion.p>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: "100%" }}
        transition={{ duration: 3, ease: "linear" }}
        className="h-1 bg-gradient-to-r from-primary to-accent rounded-full mt-8"
        aria-hidden="true"
      />
    </>
  );
}

function ErrorState({ message, onBack }) {
  return (
    <>
      <div className="w-20 h-20 mx-auto rounded-full bg-red-500/10 border border-red-500/40 flex items-center justify-center mb-6 shadow-inner">
        <Mail size={36} className="text-red-400" />
      </div>
      <p className="text-xs uppercase tracking-widest text-red-400 mb-3 font-bold">
        Свиток повреждён
      </p>
      <h1 className="text-3xl md:text-4xl font-display font-bold text-text mb-3">
        Тёмная магия вмешалась
      </h1>
      <p className="text-muted mb-8">
        {message || "Ссылка недействительна. Запроси новую через таверну."}
      </p>
      <button
        onClick={onBack}
        className="px-6 py-3 bg-primary text-white rounded-2xl font-semibold hover:scale-105 transition-transform shadow-[0_0_15px_var(--primary-selection)]"
      >
        Вернуться к таверне
      </button>
    </>
  );
}
