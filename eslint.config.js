// Lightweight ESLint config for static analysis of the vanilla-JS frontend.
// Focus: catch runtime bugs (undefined variables, typos) that pytest can't see.
// Run via:  npx eslint web/js/   (also invoked by test.sh)
const BROWSER_GLOBALS = {
  document: "readonly", window: "readonly", console: "readonly",
  setInterval: "readonly", clearInterval: "readonly",
  setTimeout: "readonly", clearTimeout: "readonly",
  requestAnimationFrame: "readonly", cancelAnimationFrame: "readonly",
  fetch: "readonly", location: "readonly", navigator: "readonly",
  localStorage: "readonly", Blob: "readonly", FileReader: "readonly",
  URL: "readonly", URLSearchParams: "readonly",
  confirm: "readonly", prompt: "readonly", alert: "readonly",
  getComputedStyle: "readonly", CustomEvent: "readonly", Event: "readonly",
  CSS: "readonly", HTMLElement: "readonly",
};

// App-level globals injected by the framework (api.js, router.js, etc.)
const APP_GLOBALS = {
  router: "readonly", ui: "readonly", api: "readonly", app: "readonly",
  t: "readonly", i18n: "readonly", charts: "readonly",
};

export default [
  {
    files: ["web/js/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: { ...BROWSER_GLOBALS, ...APP_GLOBALS },
    },
    rules: {
      // Catches the exact class of bug that broke proxy-pool.js
      // (referencing a variable that was never declared).
      "no-undef": "error",
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
  {
    // Vendored/third-party or generated files — skip.
    ignores: ["web/js/components.js", "node_modules/**", ".venv/**"],
  },
];
