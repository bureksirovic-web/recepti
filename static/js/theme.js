(function () {
  const STORAGE_KEY = 'theme';
  const THEMES = ['light', 'dark', 'system'];
  const html = document.documentElement;

  function getPreferredTheme() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && THEMES.includes(stored)) return stored;
    return 'system';
  }

  function getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function resolveTheme(pref) {
    return pref === 'system' ? getSystemTheme() : pref;
  }

  function applyTheme(theme) {
    html.setAttribute('data-theme', resolveTheme(theme));
  }

  function setTheme(theme) {
    localStorage.setItem(STORAGE_KEY, theme);
    applyTheme(theme);
    updateToggle(theme);
  }

  function createToggle() {
    const pref = getPreferredTheme();
    const current = resolveTheme(pref);
    const btn = document.createElement('button');
    btn.className = 'btn btn-ghost btn-icon';
    btn.setAttribute('aria-label', 'Toggle theme');
    btn.id = 'theme-toggle';
    updateToggle(pref);
    btn.addEventListener('click', toggleTheme);
    return btn;
  }

  function updateToggle(pref) {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    const current = resolveTheme(pref);
    const iconId = current === 'dark' ? '#icon-moon' : '#icon-sun';
    btn.innerHTML = `<svg class="icon" aria-hidden="true"><use href="${iconId}"/></svg>`;
    btn.title = pref === 'system' ? `Theme: system (${current})` : `Theme: ${current}`;
  }

  function toggleTheme() {
    const currentPref = getPreferredTheme();
    const currentResolved = resolveTheme(currentPref);
    const next = currentResolved === 'dark' ? 'light' : 'dark';
    setTheme(next);
  }

  function init() {
    applyTheme(getPreferredTheme());
    updateToggle(getPreferredTheme());
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (getPreferredTheme() === 'system') applyTheme('system');
    });
  }

  window.ReceptiTheme = { createToggle, setTheme, getPreferredTheme };

  init();
})();