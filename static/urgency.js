(() => {
  let paused = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const pauseButton = document.getElementById('pause-updates');
  function showPause() {
    if (!pauseButton) return;
    pauseButton.setAttribute('aria-pressed', String(paused));
    pauseButton.textContent = paused ? 'Reanudar actualizaciones automáticas' : 'Pausar actualizaciones automáticas';
  }
  pauseButton?.addEventListener('click', () => { paused = !paused; showPause(); });
  showPause();
  const labels = {green:"En plazo", yellow:"Próxima a vencer", red:"Por vencer", overdue:"Vencida", completed:"Finalizada"};
  function classify(start, end, completed, now) {
    if (completed) return "completed";
    const remaining = end - now, duration = end - start;
    if (remaining <= 0) return "overdue";
    return duration > 0 && remaining <= duration * .25 ? "yellow" : "green";
  }
  function update() {
    if (paused) return;
    const now = window.turnoServerNow ? window.turnoServerNow() : Date.now();
    document.querySelectorAll("[data-urgency]").forEach(node => {
      const start = Date.parse(node.dataset.start), end = Date.parse(node.dataset.end);
      if (!Number.isFinite(start) || !Number.isFinite(end)) return;
      const state = classify(start, end, node.dataset.completed === "1", now);
      Object.keys(labels).forEach(name => node.classList.toggle("urgency-" + name, state === name));
      const label = node.querySelector(".urgency-label");
      if (label) label.textContent = labels[state];
    });
  }
  let loading = false;
  async function refreshAlerts() {
    const target = document.getElementById("deadline-alerts");
    if (!target || paused || document.hidden || loading || target.contains(document.activeElement)) return;
    loading = true;
    try {
      const response = await fetch(target.dataset.url, {credentials:"same-origin"});
      if (!response.ok || response.redirected || response.headers.get("X-Turno-Fragment") !== "alerts") throw new Error();
      const html = await response.text();
      if (paused || target.contains(document.activeElement)) return;
      target.innerHTML = html;
      target.dispatchEvent(new Event("alerts:updated", {bubbles:true}));
      target.removeAttribute("data-stale");
    } catch {
      target.setAttribute("data-stale", "true");
    } finally { loading = false; update(); }
  }
  update();
  document.addEventListener("gantt:updated", update);
  document.addEventListener("server-clock:sync", update);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { update(); refreshAlerts(); } });
  setInterval(update, 30000);
  setInterval(refreshAlerts, 60000);
})();

