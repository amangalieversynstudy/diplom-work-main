import "../styles/globals.css";
import { Toaster } from "sonner";
import { I18nProvider } from "../lib/i18n";

export default function MyApp({ Component, pageProps }) {
  return (
    <I18nProvider>
      <Component {...pageProps} />
      <Toaster richColors position="top-right" />
    </I18nProvider>
  );
}
