// ── Nav ───────────────────────────────────────────
function toggleNav() {
  document.getElementById('nav-links').classList.toggle('open');
  document.getElementById('nav-burger').classList.toggle('open');
}

function closeNav() {
  document.getElementById('nav-links').classList.remove('open');
  document.getElementById('nav-burger').classList.remove('open');
}

// ── Theme ─────────────────────────────────────────
function toggleTheme() {
  const isLight = document.documentElement.classList.toggle('light');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  _syncToggleIcon();
  document.dispatchEvent(new CustomEvent('themechange', { detail: { light: isLight } }));
}

function _syncToggleIcon() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  const light = document.documentElement.classList.contains('light');
  btn.textContent = light ? '◑' : '◐';
  btn.setAttribute('aria-label', light ? 'Switch to dark mode' : 'Switch to light mode');
}

document.addEventListener('DOMContentLoaded', _syncToggleIcon);
