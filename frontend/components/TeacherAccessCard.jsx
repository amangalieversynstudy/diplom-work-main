import { useId, useState } from "react";
import { useRouter } from "next/router";
import { toast } from "sonner";
import { GraduationCap, KeyRound } from "lucide-react";
import Button from "./Button";
import Card from "./Card";
import { Auth } from "../lib/api";
import { serverMessage } from "../lib/apiErrors";
import logger from "../lib/logger";

// «Активировать доступ преподавателя»: ученик вводит код пилота и становится преподавателем своих курсов и классов
// (POST /api/auth/activate-teacher/). После успеха сразу ведём в кабинет: шапка там уже покажет меню преподавателя.
export default function TeacherAccessCard({ t }) {
  const router = useRouter();
  const id = useId();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const activate = async (e) => {
    e.preventDefault();
    if (!code.trim()) {
      setError(t("pilot.activate.empty"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await Auth.activateTeacher(code.trim());
      toast.success(t("pilot.activate.success"));
      router.push("/teacher");
    } catch (err) {
      logger.error("Teacher activation failed:", err);
      const message = serverMessage(err, t("pilot.activate.error"));
      setError(message);
      toast.error(message);
      setBusy(false);
    }
  };

  return (
    <Card variant="scroll">
      <form onSubmit={activate} noValidate>
        <h2 className="flex items-center font-title text-xl text-text">
          <GraduationCap size={20} className="mr-2 text-primary" aria-hidden="true" /> {t("pilot.activate.title")}
        </h2>
        <p className="mt-2 text-sm text-muted">{t("pilot.activate.hint")}</p>
        <label htmlFor={`${id}-code`} className="mt-4 block text-sm font-medium text-muted">
          {t("pilot.activate.label")}
        </label>
        <div className="mt-1 flex flex-col gap-3 sm:flex-row">
          <input
            id={`${id}-code`}
            value={code}
            onChange={(e) => {
              setCode(e.target.value);
              setError("");
            }}
            placeholder={t("pilot.activate.placeholder")}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${id}-error` : undefined}
            className="min-h-[44px] w-full flex-1 rounded-xl border border-border bg-panel px-4 py-2 text-text outline-none transition-colors focus:border-primary"
          />
          <Button type="submit" icon={KeyRound} loading={busy} className="shrink-0">
            {busy ? t("pilot.activate.busy") : t("pilot.activate.button")}
          </Button>
        </div>
        {error ? (
          <p id={`${id}-error`} role="alert" className="mt-2 text-xs text-error">
            {error}
          </p>
        ) : null}
      </form>
    </Card>
  );
}
