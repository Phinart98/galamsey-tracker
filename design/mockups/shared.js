document.querySelectorAll('.compare').forEach((el) => {
  const range = el.querySelector('input[type=range]');
  if (!range) return;
  const set = () => el.style.setProperty('--pos', range.value + '%');
  range.addEventListener('input', set);
  set();
});

const btn = document.querySelector('.theme-btn');
if (btn) {
  const root = document.documentElement;
  const current = () => root.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const label = () => { btn.textContent = current() === 'dark' ? 'Light mode' : 'Dark mode'; };
  btn.addEventListener('click', () => { root.dataset.theme = current() === 'dark' ? 'light' : 'dark'; label(); });
  label();
}
