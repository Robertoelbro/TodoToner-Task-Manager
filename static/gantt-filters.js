(() => {
  const content = document.getElementById("gantt-content");
  const feedback = document.getElementById("filter-feedback");
  if (!content) return;
  let controller;
  let sequence = 0;
  async function update(url, push = true) {
    const focused = content.contains(document.activeElement) ? document.activeElement : null;
    const focusId = focused?.id;
    const current = ++sequence;
    if (controller) controller.abort();
    controller = new AbortController();
    content.setAttribute("aria-busy", "true");
    feedback.textContent = "Actualizando filtros…";
    const button = content.querySelector('button[type="submit"], .filter-actions button');
    if (button) button.disabled = true;
    try {
      const response = await fetch(url, {
        headers: {"X-Requested-With": "XMLHttpRequest"},
        credentials: "same-origin",
        signal: controller.signal
      });
      if (response.redirected || response.headers.get("X-Turno-Fragment") !== "gantt") {
        throw new Error("La sesión pudo haber caducado. Vuelve a iniciar sesión y reintenta.");
      }
      if (!response.ok) throw new Error("No fue posible aplicar los filtros. Inténtalo nuevamente.");
      const html = await response.text();
      if (current !== sequence) return;
      content.innerHTML = html;
      if (focused) {
        const replacement = focusId ? document.getElementById(focusId) : null;
        (replacement || content.querySelector('.filter-actions button'))?.focus();
      }
      document.dispatchEvent(new Event("gantt:updated"));
      if (push) history.pushState(null, "", url);
      const hasErrors = content.querySelector(".errorlist, .errors");
      feedback.textContent = hasErrors ? "Revisa los filtros indicados." : "Filtros aplicados.";
      if (hasErrors) content.querySelector('input[aria-invalid="true"], select[aria-invalid="true"]')?.focus();
    } catch (error) {
      if (error.name !== "AbortError" && current === sequence) {
        feedback.textContent = error.message || "Error de conexión. Inténtalo nuevamente.";
      }
    } finally {
      if (current === sequence) {
        content.removeAttribute("aria-busy");
        const submit = content.querySelector(".filter-actions button");
        if (submit) submit.disabled = false;
      }
    }
  }
  content.addEventListener("submit", (event) => {
    if (event.target.id !== "gantt-filters") return;
    event.preventDefault();
    const url = new URL(event.target.action);
    url.search = new URLSearchParams(new FormData(event.target)).toString();
    update(url);
  });
  content.addEventListener("click", (event) => {
    const clear = event.target.closest("#gantt-clear, #gantt-overdue");
    if (!clear) return;
    event.preventDefault();
    update(new URL(clear.href));
  });
  window.addEventListener("popstate", () => update(new URL(location.href), false));
})();

