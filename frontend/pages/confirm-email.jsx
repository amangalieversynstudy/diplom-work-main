/**
 * Email-change confirmation landing page.
 *
 * The backend ProfileMeView.patch sends a confirmation email to the *new*
 * address containing
 *   {FRONTEND_URL}/confirm-email?token=<signed>
 *
 * Reads `token` from the query and GETs `/api/auth/confirm-email/?token=<>`,
 * which applies the pending email change. Until the link is opened the old
 * address stays active, so a typo can never lock anyone out.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { motion, AnimatePresence } from "framer-motion";
import Layout from "../components/Layout";
import { Auth } from "../lib/api";
import { Sparkles, Mail, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { useI18n } from "../lib/i18n";

export default function ConfirmEmail() {
  const router = useRouter();
  const { t } = useI18n();
  const [status, setStatus] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!router.isReady) return;

    const { token } = router.query;
    if (!token) {
      setStatus("error");
      setErrorMessage(t("auth.confirm.badLink"));
      return;
    }

    Auth.confirmEmailChange(token)
      .then(() => {
        setStatus("success");
        toast.success(t("auth.confirm.successToast"));
        setTimeout(() => router.push("/profile"), 3000);
      })
      .catch((err) => {
        setStatus("error");
        const detail =
          err?.response?.data?.detail || t("auth.confirm.invalidScroll");
        setErrorMessage(detail);
        toast.error(detail);
      });
  }, [router.isReady, router.query, router, t]);

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
              {status === "loading" && <LoadingState t={t} />}
              {status === "success" && <SuccessState t={t} />}
              {status === "error" && (
                <ErrorState
                  t={t}
                  message={errorMessage}
                  onBack={() => router.push("/profile")}
                />
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </Layout>
  );
}

function LoadingState({ t }) {
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
        {t("auth.confirm.loadingKicker")}
      </p>
      <h1 className="text-3xl md:text-4xl font-display font-bold text-text mb-3">
        {t("auth.confirm.loadingTitle")}
      </h1>
      <p className="text-muted">{t("auth.confirm.loadingBody")}</p>
    </>
  );
}

function SuccessState({ t }) {
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
        {t("auth.confirm.successKicker")}
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.4 }}
        className="text-3xl md:text-4xl font-display font-bold text-text mb-4"
      >
        {t("auth.confirm.successTitle")}
      </motion.h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5, duration: 0.4 }}
        className="text-muted text-lg"
      >
        {t("auth.confirm.successBody")}
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

function ErrorState({ t, message, onBack }) {
  return (
    <>
      <div className="w-20 h-20 mx-auto rounded-full bg-red-500/10 border border-red-500/40 flex items-center justify-center mb-6 shadow-inner">
        <Mail size={36} className="text-red-400" />
      </div>
      <p className="text-xs uppercase tracking-widest text-red-400 mb-3 font-bold">
        {t("auth.confirm.errorKicker")}
      </p>
      <h1 className="text-3xl md:text-4xl font-display font-bold text-text mb-3">
        {t("auth.confirm.errorTitle")}
      </h1>
      <p className="text-muted mb-8">
        {message || t("auth.confirm.invalidGeneric")}
      </p>
      <button
        onClick={onBack}
        className="px-6 py-3 bg-primary text-white rounded-2xl font-semibold hover:scale-105 transition-transform shadow-[0_0_15px_var(--primary-selection)]"
      >
        {t("auth.confirm.backToProfile")}
      </button>
    </>
  );
}
