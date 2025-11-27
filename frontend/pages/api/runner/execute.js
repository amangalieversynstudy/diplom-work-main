const sleep = (ms = 400) => new Promise((resolve) => setTimeout(resolve, ms));

function summarizeTests(code = "", challenge = {}) {
  const expectedSnippet = (challenge.expectedSnippet || "return").toLowerCase();
  const includesSnippet = code.toLowerCase().includes(expectedSnippet);
  const printsHello = /print\(.*hello/i.test(code);

  const baseTests = [
    {
      name: "Syntax",
      status: code.trim() ? "passed" : "failed",
      detail: code.trim() ? "Code submitted" : "Пустой ввод",
    },
    {
      name: "Snippet",
      status: includesSnippet ? "passed" : "failed",
      detail: includesSnippet
        ? "Основная функция найдена"
        : `Нет ожидаемого фрагмента: ${expectedSnippet}`,
    },
    {
      name: "Greeting",
      status: printsHello ? "passed" : "warning",
      detail: printsHello
        ? "Приветствие найдено"
        : "Совет: добавь print('Hello Adventurer')",
    },
  ];

  return {
    success: includesSnippet,
    stdout: includesSnippet
      ? challenge.sampleOutput || "🎉 Все испытания пройдены"
      : "",
    stderr: includesSnippet
      ? ""
      : `❌ Не найден ожидаемый фрагмент: ${expectedSnippet}`,
    tests: baseTests,
    score: includesSnippet ? 100 : 45,
  };
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ detail: "Method not allowed" });
  }
  const { language = "python", code = "", challenge = {} } = req.body || {};
  await sleep(650);
  const result = summarizeTests(code, challenge);
  return res.status(200).json({ language, ...result, timestamp: Date.now() });
}
