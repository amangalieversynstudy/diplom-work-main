const path = require("path");

module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  extends: [
    "next/core-web-vitals",
    "eslint:recommended",
    "plugin:jsx-a11y/recommended",
    "prettier",
  ],
  plugins: ["jsx-a11y"],
  settings: {
    next: {
      rootDir: [path.resolve(__dirname)],
    },
  },
  parserOptions: {
    requireConfigFile: false,
    sourceType: "module",
    allowImportExportEverywhere: true,
    babelOptions: {
      presets: [require.resolve("next/babel")],
      caller: {
        supportsTopLevelAwait: true,
      },
      cwd: path.resolve(__dirname),
    },
  },
  rules: {
    "react/react-in-jsx-scope": "off",
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "error",
    "jsx-a11y/no-autofocus": ["error", { ignoreNonDOM: true }],
    "no-console": ["error", { allow: ["warn", "error"] }],
  },
};
