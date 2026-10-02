(() => {
  const labels = {green:"En plazo", yellow:"Próxima a vencer", red:"Por vencer", overdue:"Vencida", completed:"Finalizada"};
  function classify(start, end, completed, now) {
    if (completed) return "completed";
    const remaining = end - now, duration = end - start;
    if (remaining <= 0) return "overdue";
    if (duration > 0 && duration <= 86400000) {
      return remaining > duration * 2 / 3 ? "green" : remaining > duration / 3 ? "yellow" : "red";
    }
    return remaining < 86400000 ? "red" : remaining <= 172800000 ? "yellow" : "green";
  }
  function update() {
    const now = Date.now();
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
    if (!target || document.hidden || loading) return;
    loading = true;
    try {
      const response = await fetch(target.dataset.url, {credentials:"same-origin"});
      if (!response.ok || response.redirected || response.headers.get("X-Turno-Fragment") !== "alerts") throw new Error();
      target.innerHTML = await response.text();
      target.removeAttribute("data-stale");
    } catch {
      target.setAttribute("data-stale", "true");
    } finally { loading = false; update(); }
  }
  update();
  document.addEventListener("gantt:updated", update);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { update(); refreshAlerts(); } });
  setInterval(update, 30000);
  setInterval(refreshAlerts, 60000);
})();

