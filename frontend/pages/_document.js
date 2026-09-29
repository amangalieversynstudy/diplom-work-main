import { Head, Html, Main, NextScript } from "next/document";

// Язык по умолчанию русский; при переключении RU/EN lib/i18n.js обновляет
// document.documentElement.lang.
export default function Document() {
  return (
    <Html lang="ru">
      <Head />
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
