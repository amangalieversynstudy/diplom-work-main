import { Head, Html, Main, NextScript } from "next/document";

// Тема ставится до первой отрисовки, по тем же правилам, что в lib/theme.js (сохранённая, иначе системная):
// без этого светлая тема мигала тёмной, пока не загрузится JavaScript.
const THEME_SCRIPT = `try{var t=localStorage.getItem("ui_theme")||(window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");document.documentElement.classList.toggle("dark",t==="dark")}catch(e){document.documentElement.classList.add("dark")}`;

// Язык по умолчанию русский; при переключении RU/EN lib/i18n.js обновляет
// document.documentElement.lang.
export default function Document() {
  return (
    <Html lang="ru">
      <Head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
