// Terminal — обёртка над xterm.js под тёмную RPG-палитру.
// Через ref наружу торчат write/writeln/clear/reset/fit/focus.
// CSS для xterm подгружается глобально в pages/_app.js.

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

const RPG_THEME = {
  background: "#1e1e1e",
  foreground: "#d4d4d4",
  cursor: "#cca700",
  cursorAccent: "#1e1e1e",
  selectionBackground: "rgba(204, 167, 0, 0.35)",
  black: "#000000",
  red: "#f14c4c",
  green: "#23d18b",
  yellow: "#f5f543",
  blue: "#3b8eea",
  magenta: "#d670d6",
  cyan: "#29b8db",
  white: "#e5e5e5",
  brightBlack: "#666666",
  brightRed: "#f14c4c",
  brightGreen: "#23d18b",
  brightYellow: "#f5f543",
  brightBlue: "#3b8eea",
  brightMagenta: "#d670d6",
  brightCyan: "#29b8db",
  brightWhite: "#ffffff",
};

const Terminal = forwardRef(function Terminal({ className = "" }, ref) {
  const containerRef = useRef(null);
  const termRef = useRef(null);
  const fitRef = useRef(null);

  useImperativeHandle(
    ref,
    () => ({
      write: (data) => termRef.current?.write(data),
      writeln: (data) => termRef.current?.writeln(data),
      clear: () => termRef.current?.clear(),
      reset: () => termRef.current?.reset(),
      fit: () => fitRef.current?.fit(),
      focus: () => termRef.current?.focus(),
    }),
    []
  );

  useEffect(() => {
    let disposed = false;
    let resizeObs;

    (async () => {
      // Dynamic import keeps xterm out of the SSR bundle (it touches window).
      const [{ Terminal: XTerm }, { FitAddon }, { WebLinksAddon }] = await Promise.all([
        import("@xterm/xterm"),
        import("@xterm/addon-fit"),
        import("@xterm/addon-web-links"),
      ]);

      if (disposed || !containerRef.current) return;

      const term = new XTerm({
        cursorBlink: true,
        cursorStyle: "bar",
        fontFamily:
          'ui-monospace, SF Mono, Menlo, Monaco, "Cascadia Mono", Consolas, monospace',
        fontSize: 13,
        lineHeight: 1.25,
        convertEol: false, // we normalise to \r\n ourselves
        scrollback: 5000,
        allowProposedApi: true,
        theme: RPG_THEME,
      });

      const fit = new FitAddon();
      term.loadAddon(fit);
      term.loadAddon(new WebLinksAddon());
      term.open(containerRef.current);

      // Initial fit + sync to subsequent layout changes.
      try {
        fit.fit();
      } catch {
        /* container may not have layout yet — refit on next observer tick */
      }

      resizeObs = new ResizeObserver(() => {
        try {
          fit.fit();
        } catch {
          /* ignore — happens during unmount/teardown */
        }
      });
      resizeObs.observe(containerRef.current);

      termRef.current = term;
      fitRef.current = fit;

      term.writeln("\x1b[90m# Terminal ready. Press \x1b[33mRun\x1b[90m to execute.\x1b[0m");
    })();

    return () => {
      disposed = true;
      if (resizeObs) resizeObs.disconnect();
      if (termRef.current) {
        try {
          termRef.current.dispose();
        } catch {
          /* noop */
        }
        termRef.current = null;
      }
      fitRef.current = null;
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className={`w-full h-full bg-[#1e1e1e] ${className}`}
    />
  );
});

export default Terminal;
