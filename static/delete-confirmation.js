(() => {
  const form = document.querySelector('[data-delete-confirmation]');
  if (!form) return;
  const button = form.querySelector('[data-delete-button]');
  let readyAt;
  let timer;
  function tick() {
    const remaining = Math.max(0, Math.ceil((readyAt - performance.now()) / 1000));
    button.disabled = remaining > 0;
    button.textContent = remaining ? `Confirmar eliminación (${remaining} s)` : 'Confirmar eliminación';
    if (!remaining) clearInterval(timer);
  }
  function reset() {
    clearInterval(timer);
    readyAt = performance.now() + 5000;
    tick();
    timer = setInterval(tick, 100);
  }
  form.addEventListener('submit', (event) => {
    if (performance.now() < readyAt) event.preventDefault();
  });
  window.addEventListener('pageshow', (event) => { if (event.persisted) reset(); });
  reset();
})();
