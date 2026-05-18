import { X } from "lucide-react";
import Button from "./Button";

const defaultPlans = [
  { id: "novice", title: "Novice", price: "₽990", perks: ["3 миссии", "Поддержка"] },
  { id: "champion", title: "Champion", price: "₽1 990", perks: ["Полный доступ", "Код-ревью"] },
  { id: "founder", title: "Founder", price: "₽3 490", perks: ["Персональная сессия", "Личный артефакт"] },
];

export default function PaywallModal({ open, onClose, onCheckout, loading, state, copy }) {
  if (!open) return null;
  const plans = copy?.plans?.length ? copy.plans : defaultPlans;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur">
      <div className="bg-surface px-6 py-8 rounded-3xl border border-border w-full max-w-xl text-text relative shadow-2xl">
        <button onClick={onClose} className="absolute top-6 right-6 text-muted hover:text-text transition-colors" aria-label="close">
          <X size={20} />
        </button>
        <p className="text-xs uppercase tracking-widest text-gold mb-2 font-bold">
          {copy?.badge || "Premium Gate"}
        </p>
        <h2 className="text-3xl font-display font-bold mb-3">{copy?.title || "Unlock premium content"}</h2>
        <p className="text-sm text-muted mb-6">
          {copy?.subtitle || "Get advanced missions, side quests, and XP boosters."}
        </p>
        <div className="grid md:grid-cols-3 gap-4">
          {plans.map((plan) => (
            <div key={plan.id} className="border border-border bg-panel rounded-2xl p-4 flex flex-col">
              <p className="text-xs uppercase tracking-widest text-muted font-bold mb-1">{plan.title}</p>
              <p className="text-xl font-semibold text-gold">{plan.price}</p>
              <ul className="mt-3 mb-4 text-sm text-text space-y-1.5 flex-1">
                {plan.perks.map((perk) => (
                  <li key={perk} className="flex gap-2"><span className="text-gold mt-0.5">•</span> {perk}</li>
                ))}
              </ul>
              <Button className="mt-3 w-full" onClick={() => onCheckout(plan.id)} disabled={loading}>
                {loading ? copy?.processing || "Processing" : copy?.planCta || "Activate"}
              </Button>
            </div>
          ))}
        </div>
        {state && (
          <div className="mt-6 p-4 rounded-xl bg-success/10 border border-success/20 text-sm text-text">
            <p>{state.message}</p>
            {state.perks && (
              <p className="text-xs text-muted mt-2">
                {(copy?.perksLabel || "Perks") + ": " + state.perks.join(", ")}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
