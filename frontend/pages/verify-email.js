/**
 * Email verification landing page.
 *
 * The backend RegisterView sends an email containing
 *   {FRONTEND_URL}/verify-email?uid=<base64>&token=<token>
 *
 * This page reads `uid` + `token` from the query string and GETs
 * `/api/auth/verify-email/?uid=<>&token=<>` to activate the account.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/router";
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

  const Icon =
    status === "success" ? ShieldCheck : status === "error" ? Mail : Sparkles;

  return (
    <Layout>
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <Icon
          size={64}
          className={`mb-6 ${
            status === "success"
              ? "text-primary"
              : status === "error"
              ? "text-red-400"
              : "text-muted animate-pulse"
          }`}
        />
        <h1 className="text-4xl font-display font-bold mb-4 text-text">
          {status === "loading" && "Расшифровка свитка..."}
          {status === "success" && "Путь открыт!"}
          {status === "error" && "Темная магия вмешалась"}
        </h1>
        <p className="text-muted text-lg max-w-md">
          {status === "loading" && "Подожди, пока мы проверим твои печати."}
          {status === "success" &&
            "Перенаправляем в зал входа..."}
          {status === "error" &&
            (errorMessage ||
              "Ссылка недействительна. Запроси новую через таверну (login).")}
        </p>
        {status === "error" && (
          <button
            onClick={() => router.push("/login")}
            className="mt-8 px-6 py-3 bg-primary text-white rounded-2xl font-semibold hover:scale-105 transition-transform"
          >
            Вернуться к таверне
          </button>
        )}
      </div>
    </Layout>
  );
}
