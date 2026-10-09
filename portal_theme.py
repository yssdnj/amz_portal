THEME_CSS = """<style>
:root {
  --page-bg: #0d0d1a; --surface: #13131f; --topbar-bg: #191c2c;
  --dialog-bg: #191a26; --text: #e2e8f0; --heading: #f1f5f9;
  --muted: #a8b2c3; --subtle: #8792a4; --border: #45485d;
  --soft-border: #252637; --hover-bg: #303345; --button-bg: #2a2d3a;
  --blue: #60a5fa; --blue-bg: rgba(59,130,246,.12);
  --red: #fca5a5; --red-bg: rgba(239,68,68,.10);
  --gold: #efc178; --gold-bg: rgba(212,168,67,.08);
  --success-bg: #16805d; --success-border: #33ba90; --on-success: #ffffff;
  --switch-off: #363b49; --switch-thumb: #f1f5f9;
}
:root[data-theme="light"] {
  --page-bg: #f4f6f9; --surface: #ffffff; --topbar-bg: #ffffff;
  --dialog-bg: #ffffff; --text: #243244; --heading: #142235;
  --muted: #536174; --subtle: #647185; --border: #cbd3df;
  --soft-border: #dfe5ed; --hover-bg: #edf1f7; --button-bg: #eef2f7;
  --blue: #1d5fbb; --blue-bg: #edf4ff;
  --red: #a92535; --red-bg: #fff0f1; --gold: #805512; --gold-bg: #fff7e6;
  --success-bg: #107451; --success-border: #168560; --switch-off: #d1d8e3;
}
.theme-button {
  width: 34px; height: 34px; flex: 0 0 34px; padding: 0;
  display: grid; place-items: center; border: 1px solid var(--border);
  border-radius: 6px; color: var(--muted); background: transparent;
  cursor: pointer; letter-spacing: 0;
}
.theme-button:hover { color: var(--heading); background: var(--hover-bg); }
.theme-button:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
.theme-button svg { width: 17px; height: 17px; grid-area: 1 / 1; }
.theme-moon { display: none; }
[data-theme="light"] .theme-sun { display: none; }
[data-theme="light"] .theme-moon { display: block; }
</style>"""

THEME_INIT = """<script>
(() => {
  const key = 'amazon-portal-theme';
  const root = document.documentElement;
  const valid = value => value === 'light' || value === 'dark';
  const apply = value => {
    const theme = valid(value) ? value : 'dark';
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    const label = theme === 'dark' ? '切换到浅色' : '切换到深色';
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.setAttribute('aria-label', label);
      button.title = label;
    });
  };
  let saved = 'dark';
  try { saved = localStorage.getItem(key); } catch (_) {}
  apply(saved);
  document.addEventListener('DOMContentLoaded', () => apply(root.dataset.theme));
  document.addEventListener('click', event => {
    if (!(event.target instanceof Element) || !event.target.closest('[data-theme-toggle]')) return;
    const theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    apply(theme);
    try { localStorage.setItem(key, theme); } catch (_) {}
  });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) {
      try { if (event.storageArea !== localStorage) return; } catch (_) { return; }
      apply(event.newValue);
    }
  });
})();
</script>"""

THEME_BUTTON = """<button type="button" class="theme-button" data-theme-toggle aria-label="切换到浅色" title="切换到浅色">
  <svg class="theme-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg>
  <svg class="theme-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6.25 6.25 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/></svg>
</button>"""


def apply_theme(page: str) -> str:
    return (page.replace("__THEME_CSS__", THEME_CSS)
            .replace("__THEME_INIT__", THEME_INIT)
            .replace("__THEME_BUTTON__", THEME_BUTTON))
