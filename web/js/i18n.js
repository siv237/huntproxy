const i18n = {
  _lang: 'en',
  _fallback: 'en',
  _translations: {},
  _loaded: {},
  _listeners: [],

  get lang() { return this._lang; },

  async init() {
    await this._discoverLangs();
    const saved = localStorage.getItem('lang');
    const browser = navigator.language.split('-')[0];
    this._lang = saved || (this._isSupported(browser) ? browser : 'en');
    await this.loadLang(this._lang);
    if (this._lang !== this._fallback && !this._loaded[this._fallback]) {
      await this.loadLang(this._fallback);
    }
    document.documentElement.lang = this._lang;
    this._notify();
  },

  async setLang(lang) {
    if (lang === this._lang) return;
    this._lang = lang;
    localStorage.setItem('lang', lang);
    if (!this._loaded[lang]) await this.loadLang(lang);
    document.documentElement.lang = lang;
    this._notify();
    window.dispatchEvent(new CustomEvent('lang-changed', { detail: { lang } }));
  },

  async loadLang(lang) {
    if (this._loaded[lang]) return;
    try {
      const res = await fetch(`/locales/${lang}.json?v=24`);
      if (!res.ok) throw new Error(res.status);
      this._translations[lang] = await res.json();
      this._loaded[lang] = true;
    } catch (e) {
      console.warn('i18n: failed to load', lang, e);
      if (lang !== this._fallback) this._loaded[lang] = false;
    }
  },

  _knownLangs: null,

  _isSupported(lang) {
    if (!this._knownLangs) return ['en', 'de', 'es', 'fr', 'ru', 'zh'].includes(lang);
    return this._knownLangs.some(l => l.code === lang);
  },

  async _discoverLangs() {
    if (this._knownLangs) return;
    try {
      const res = await fetch('/locales/index.json?v=24');
      if (res.ok) {
        this._knownLangs = await res.json();
        return;
      }
    } catch (e) {}
    this._knownLangs = [
      { code: 'en', name: 'English', native: 'English' },
      { code: 'de', name: 'German', native: 'Deutsch' },
      { code: 'es', name: 'Spanish', native: 'Español' },
      { code: 'fr', name: 'French', native: 'Français' },
      { code: 'ru', name: 'Russian', native: 'Русский' },
      { code: 'zh', name: 'Chinese', native: '中文' },
    ];
  },

  getSupportedLangs() {
    return this._knownLangs || [
      { code: 'en', name: 'English', native: 'English' },
      { code: 'de', name: 'German', native: 'Deutsch' },
      { code: 'es', name: 'Spanish', native: 'Español' },
      { code: 'fr', name: 'French', native: 'Français' },
      { code: 'ru', name: 'Russian', native: 'Русский' },
      { code: 'zh', name: 'Chinese', native: '中文' },
    ];
  },

  t(key, params) {
    const val = this._resolve(key, this._translations[this._lang])
             ?? this._resolve(key, this._translations[this._fallback])
             ?? key;
    if (typeof val !== 'string') return String(val);
    if (!params) return val;
    return val.replace(/\{(\w+)\}/g, (_, k) => {
      return params[k] !== undefined ? String(params[k]) : `{${k}}`;
    });
  },

  tp(key, count, params) {
    const n = typeof count === 'number' ? count : parseInt(count) || 0;
    const forms = this._resolve(key, this._translations[this._lang])
               ?? this._resolve(key, this._translations[this._fallback]);
    if (!forms || typeof forms === 'string') return this.t(key, { ...params, count: n });
    const formKey = this._pluralForm(this._lang, n);
    const val = forms[formKey] ?? forms.other ?? forms.one ?? Object.values(forms)[0] ?? key;
    return val.replace(/\{count\}/g, String(n)).replace(/\{(\w+)\}/g, (_, k) => {
      if (k === 'count') return String(n);
      return params && params[k] !== undefined ? String(params[k]) : `{${k}}`;
    });
  },

  _resolve(key, obj) {
    if (!obj) return undefined;
    const parts = key.split('.');
    let cur = obj;
    for (const p of parts) {
      if (cur == null || typeof cur !== 'object') return undefined;
      cur = cur[p];
    }
    return cur;
  },

  _pluralForm(lang, n) {
    const abs = Math.abs(n);
    const mod10 = abs % 10;
    const mod100 = abs % 100;
    if (lang === 'ru') {
      if (mod10 === 1 && mod100 !== 11) return 'one';
      if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'few';
      return 'many';
    }
    return n === 1 ? 'one' : 'other';
  },

  onLocaleChange(fn) { this._listeners.push(fn); },
  _notify() { this._listeners.forEach(fn => fn(this._lang)); },
};

function t(key, params) { return i18n.t(key, params); }
function tp(key, count, params) { return i18n.tp(key, count, params); }
