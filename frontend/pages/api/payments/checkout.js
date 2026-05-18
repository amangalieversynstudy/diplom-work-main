const sleep = (ms = 500) => new Promise((resolve) => setTimeout(resolve, ms));

const PLANS = {
  novice: { amount: 990, currency: "RUB", perks: ["3 миссии", "Доступ к чату"] },
  champion: { amount: 1990, currency: "RUB", perks: ["Полная карта", "Код-ревью"] },
  founder: { amount: 3490, currency: "RUB", perks: ["1:1 созвон", "Именной артефакт"] },
};

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ detail: "Method not allowed" });
  }
  const { plan = "champion", email = "hero@example.com" } = req.body || {};
  await sleep();
  const selected = PLANS[plan] || PLANS.champion;
  const intentId = `fake_intent_${Date.now()}`;
  return res.status(200).json({
    success: true,
    intent: {
      id: intentId,
      status: "succeeded",
      amount: selected.amount,
      currency: selected.currency,
    },
    perks: selected.perks,
    receiptEmail: email,
    message: "Оплата смоделирована. Доступ открыт на 30 дней.",
  });
}
