import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { Lightbulb } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { tipGroup, readTipState, nextTip, markTipSeen, turnTipsOff, TIP_ORDER } from "../lib/tips";

/**
 * Подсказки первого визита: карточка внизу экрана, по одной, на карте и в миссии.
 * Показанные подсказки запоминает браузер, на сервер ничего не уходит. «Пропустить» гасит все.
 */
export default function FirstVisitTips({ enabled }) {
  const { t } = useI18n();
  const router = useRouter();
  const [tip, setTip] = useState(null);
  const group = tipGroup(router.pathname);

  useEffect(() => {
    if (!enabled || !group) {
      setTip(null);
      return;
    }
    setTip(nextTip(group, readTipState(window.localStorage)));
  }, [enabled, group, router.asPath]);

  if (!tip) return null;
  const order = TIP_ORDER[group];
  const step = order.indexOf(tip) + 1;

  const next = () => {
    markTipSeen(window.localStorage, tip);
    setTip(nextTip(group, readTipState(window.localStorage)));
  };
  const skip = () => {
    turnTipsOff(window.localStorage);
    setTip(null);
  };

  return (
    <div
      role="status"
      data-testid="first-visit-tip"
      className="fixed bottom-4 left-4 right-4 z-[85] flex flex-col gap-2 rounded-2xl border border-primary/30 bg-surface/95 px-4 py-3 shadow-lg backdrop-blur-md sm:right-auto sm:max-w-sm"
    >
      <div className="flex items-start gap-3">
        <Lightbulb size={18} className="mt-0.5 shrink-0 text-primary" aria-hidden="true" />
        <p className="text-sm leading-snug text-text">{t(`tips.${tip}`)}</p>
      </div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-muted">
          {t("tips.step").replace("{n}", step).replace("{total}", order.length)}
        </span>
        <span className="flex gap-2">
          <button type="button" onClick={skip} className="min-h-[36px] rounded-full px-3 text-xs font-semibold text-muted hover:text-text">
            {t("tips.skip")}
          </button>
          <button
            type="button"
            onClick={next}
            className="min-h-[36px] rounded-full bg-primary px-4 text-xs font-bold text-on-primary transition-colors hover:bg-primary-dk"
          >
            {t("tips.next")}
          </button>
        </span>
      </div>
    </div>
  );
}
