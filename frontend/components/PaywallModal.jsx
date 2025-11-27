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
      <div className="bg-night px-6 py-5 rounded-2xl border border-white/10 w-full max-w-xl text-white relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-white/60" aria-label="close">
          <X size={20} />
        </button>
        <p className="text-xs uppercase tracking-[0.35em] text-white/60 mb-1">
          {copy?.badge || "Premium Gate"}
        </p>
        <h2 className="text-2xl font-display mb-3">{copy?.title || "Unlock premium content"}</h2>
        <p className="text-sm text-white/70 mb-4">
          {copy?.subtitle || "Get advanced missions, side quests, and XP boosters."}
        </p>
        <div className="grid md:grid-cols-3 gap-3">
          {plans.map((plan) => (
            <div key={plan.id} className="border border-white/10 rounded-xl p-3">
              <p className="text-xs uppercase tracking-[0.3em] text-white/60">{plan.title}</p>
              <p className="text-xl font-semibold text-gold">{plan.price}</p>
              <ul className="mt-2 text-sm text-white/70 space-y-1">
                {plan.perks.map((perk) => (
                  <li key={perk}>• {perk}</li>
                ))}
              </ul>
              <Button className="mt-3 w-full" onClick={() => onCheckout(plan.id)} disabled={loading}>
                {loading ? copy?.processing || "Processing" : copy?.planCta || "Activate"}
              </Button>
            </div>
          ))}
        </div>
        {state && (
          <div className="mt-4 text-sm text-white/80">
            <p>{state.message}</p>
            {state.perks && (
              <p className="text-xs text-white/60">
                {(copy?.perksLabel || "Perks") + ": " + state.perks.join(", ")}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
