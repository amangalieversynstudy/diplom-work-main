import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Layout from "../../components/Layout";
import api from "../../lib/api";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function VerifyEmail() {
  const router = useRouter();
  const { token } = router.query;
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    if (!token) return;
    api.get(`/users/auth/verify/${token}/`)
      .then(() => {
        setStatus("success");
        toast.success("Магическая печать снята! Добро пожаловать.");
        setTimeout(() => router.push("/login"), 3000);
      })
      .catch(() => {
        setStatus("error");
        toast.error("Свиток поврежден или уже использован.");
      });
  }, [token, router]);

  return (
    <Layout>
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <Sparkles size={64} className={`mb-6 ${status === 'success' ? 'text-primary' : 'text-muted animate-pulse'}`} />
        <h1 className="text-4xl font-display font-bold mb-4 text-text">
          {status === "loading" && "Расшифровка свитка..."}
          {status === "success" && "Путь открыт!"}
          {status === "error" && "Темная магия вмешалась"}
        </h1>
        <p className="text-muted text-lg">
          {status === "loading" && "Подожди, пока мы проверим твои печати."}
          {status === "success" && "Перенаправляем в зал входа..."}
          {status === "error" && "Ссылка недействительна. Запроси новую через таверну (login)."}
        </p>
      </div>
    </Layout>
  );
}