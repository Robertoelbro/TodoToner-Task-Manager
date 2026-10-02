(() => {
  const clock = document.querySelector('[data-server-clock]');
  if (!clock) return;
  const time = clock.querySelector('time');
  const preferenceKey = 'turno-clock-open';
  try { clock.open = localStorage.getItem(preferenceKey) !== 'false'; } catch {}
  clock.addEventListener('toggle', () => {
    try { localStorage.setItem(preferenceKey, String(clock.open)); } catch {}
  });
  let epoch = null, anchor = 0, formatter, pending = false;
  function render() {
    if (epoch === null) return;
    const date = new Date(epoch + performance.now() - anchor);
    time.textContent = formatter.format(date);
    time.dateTime = date.toISOString();
  }
  async function sync() {
    if (pending) return;
    pending = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const start = performance.now();
    try {
      const response = await fetch(clock.dataset.url, {cache: 'no-store', signal: controller.signal});
      if (!response.ok) throw new Error('Clock unavailable');
      const data = await response.json();
      if (!Number.isFinite(data.timestamp)) throw new Error('Invalid timestamp');
      formatter = new Intl.DateTimeFormat('es-CL', {timeZone: data.timezone, hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'});
      anchor = performance.now();
      epoch = data.timestamp + (anchor - start) / 2;
      time.title = 'Hora del servidor';
      render();
    } catch {
      time.title = epoch === null ? 'Sin conexión con el servidor' : 'Hora estimada: pendiente de sincronización';
    } finally {
      clearTimeout(timeout);
      pending = false;
    }
  }
  setInterval(render, 1000);
  setInterval(sync, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) sync(); });
  window.addEventListener('online', sync);
  sync();
})();
