import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { toast } from "sonner";
import Card from "./Card";
import Button from "./Button";
import { Classes } from "../lib/api";
import { getTokens } from "../lib/auth";
import { rememberJoinCode, normalizeJoinCode } from "../lib/join";
import { useDictionary } from "../lib/i18n";
import logger from "../lib/logger";

const fill = (template, values) =>
  Object.entries(values).reduce((text, [key, value]) => text.replace(`{${key}}`, value), template);

// Вступление в класс: кто приглашает, что он увидит, согласие и кнопка. Без входа сначала вход.
export default function JoinClassPanel({ initialCode = "" }) {
  const copy = useDictionary().classes?.join || {};
  const router = useRouter();
  const [code, setCode] = useState(normalizeJoinCode(initialCode));
  const [signedIn, setSignedIn] = useState(null);
  const [info, setInfo] = useState(null);
  const [problem, setProblem] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSignedIn(Boolean(getTokens().access));
  }, []);

  async function look(value) {
    setProblem("");
    setInfo(null);
    setAgreed(false);
    const clean = normalizeJoinCode(value);
    if (!clean) {
      setProblem(copy.needCode || "Введите код класса.");
      return;
    }
    setBusy(true);
    try {
      setInfo({ ...(await Classes.lookup(clean)), code: clean });
    } catch (error) {
      const status = error?.response?.status;
      setProblem(
        status === 404
          ? copy.notFound || "Такого класса нет. Проверьте код."
          : status === 429
          ? copy.tooMany || "Слишком много попыток. Подождите немного."
          : copy.error || "Не удалось проверить код. Попробуйте ещё раз."
      );
      logger.error("Class lookup failed:", error);
    } finally {
      setBusy(false);
    }
  }

  // ссылка с кодом: сразу показываем приглашение
  useEffect(() => {
    if (signedIn && initialCode) look(initialCode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signedIn]);

  async function join() {
    setBusy(true);
    try {
      await Classes.join(info.code);
      toast.success(fill(copy.joined || "Вы в классе «{title}»", { title: info.title }));
      router.push("/worlds");
    } catch (error) {
      const detail = error?.response?.data?.detail;
      setProblem(detail || copy.error || "Не удалось вступить. Попробуйте ещё раз.");
      logger.error("Class join failed:", error);
    } finally {
      setBusy(false);
    }
  }

  function goAuth(path) {
    rememberJoinCode(code || initialCode);
    router.push(path);
  }

  if (signedIn === null) return null;

  if (!signedIn) {
    return (
      <Card variant="scroll" title={copy.title || "Вступить в класс"} subtitle={copy.signInFirst || "Чтобы вступить в класс, войдите или зарегистрируйтесь. Код сохранится."}>
        <div className="flex flex-col gap-3">
          <Button variant="rune" onClick={() => goAuth("/register")}>
            {copy.register || "Создать аккаунт ученика"}
          </Button>
          <Button variant="outline" onClick={() => goAuth("/login")}>
            {copy.login || "У меня уже есть аккаунт"}
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card variant="scroll" title={copy.title || "Вступить в класс"} subtitle={copy.subtitle || "Код вам дал преподаватель."}>
      {!info ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            look(code);
          }}
        >
          <label className="text-sm text-muted">
            {copy.codeLabel || "Код класса"}
            <input
              className="mt-1 w-full rounded-2xl border border-border bg-panel px-4 py-2 font-mono uppercase tracking-widest text-text focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30"
              value={code}
              maxLength={16}
              autoComplete="off"
              placeholder="K7M2QP9X"
              onChange={(event) => setCode(event.target.value)}
            />
          </label>
          {problem ? (
            <p role="alert" className="text-sm text-error">{problem}</p>
          ) : null}
          <Button variant="rune" type="submit" disabled={busy}>
            {busy ? copy.checking || "Проверяем…" : copy.check || "Найти класс"}
          </Button>
        </form>
      ) : info.own ? (
        <p className="text-sm text-text">{copy.own || "Это ваш собственный класс."}</p>
      ) : info.joined ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-text">{fill(copy.already || "Вы уже в классе «{title}».", { title: info.title })}</p>
          <Button variant="rune" onClick={() => router.push("/worlds")}>{copy.toMap || "На карту"}</Button>
        </div>
      ) : !info.open ? (
        <p className="text-sm text-text">{copy.closed || "Набор в этот класс закрыт. Спросите преподавателя."}</p>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-text">
            {fill(copy.invite || "{teacher} приглашает вас в курс «{title}».", {
              teacher: info.teacher || copy.teacherFallback || "Преподаватель",
              title: info.title,
            })}
          </p>
          <label className="flex cursor-pointer items-start gap-3 text-sm text-muted">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 shrink-0 accent-[var(--primary)]"
              checked={agreed}
              onChange={(event) => setAgreed(event.target.checked)}
            />
            <span>
              {copy.consent ||
                "Я понимаю, что преподаватель увидит мой ник, мой прогресс в этом курсе и то, как решены шаги (подсказки, Мудрец, вставленный код), а одноклассники увидят меня в таблице класса. Выйти из класса можно в любой момент."}
            </span>
          </label>
          {problem ? (
            <p role="alert" className="text-sm text-error">{problem}</p>
          ) : null}
          <div className="flex gap-3">
            <Button variant="rune" onClick={join} disabled={!agreed || busy}>
              {busy ? copy.joining || "Вступаем…" : copy.join || "Присоединиться"}
            </Button>
            <Button variant="outline" onClick={() => router.push("/worlds")}>
              {copy.cancel || "Отмена"}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
