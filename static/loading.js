(() => {
  window.turnoLoading = (node, active) => {
    if (!node) return;
    node.classList.toggle('skeleton-loading', active);
    if (active) {
      node.setAttribute('aria-busy', 'true');
      if (!node.querySelector(':scope > .skeleton-placeholder')) {
        const placeholder = document.createElement('div');
        placeholder.className = 'skeleton-placeholder';
        placeholder.setAttribute('aria-hidden', 'true');
        for (let i = 0; i < 5; i++) placeholder.append(document.createElement('span'));
        node.append(placeholder);
      }
    } else {
      node.removeAttribute('aria-busy');
      node.querySelector(':scope > .skeleton-placeholder')?.remove();
    }
  };
  const feedback = document.createElement('p');
  feedback.className = 'async-feedback';
  feedback.setAttribute('role', 'status');
  document.querySelector('main')?.prepend(feedback);
  const pending = new Set();
  document.addEventListener('submit', async event => {
    const form = event.target.closest('form.task-dismiss');
    if (!form) return;
    event.preventDefault();
    const node = form.closest('[data-task-id]');
    if (!node || pending.has(node.dataset.taskId)) return;
    const id = node.dataset.taskId;
    pending.add(id);
    const copies = [...document.querySelectorAll('[data-task-id]')].filter(item => item.dataset.taskId === id);
    const hadFocus = copies.some(item => item.contains(document.activeElement));
    const buttons = copies.flatMap(item => [...item.querySelectorAll('.task-dismiss button')]);
    buttons.forEach(button => { button.disabled = true; });
    copies.forEach(item => window.turnoLoading(item, true));
    feedback.textContent = 'Ocultando tarea…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form),
        credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest'}, signal: controller.signal});
      if (!response.ok || response.redirected || !response.headers.get('Content-Type')?.includes('application/json')) throw new Error();
      const result = await response.json();
      if (!result.hidden || String(result.task_id) !== id) throw new Error();
      const workspace = node.closest('[data-zone-workspace]');
      copies.forEach(item => item.remove());
      workspace?.dispatchEvent(new Event('alerts:updated', {bubbles: true}));
      document.dispatchEvent(new Event('task:hidden'));
      feedback.textContent = 'Tarea oculta. Se conserva en Historial.';
      if (hadFocus) {
        const destination = workspace?.querySelector('[data-task-zones]:not([hidden]) h2 a') || document.querySelector('main');
        destination?.focus({preventScroll: true});
      }
    } catch {
      copies.forEach(item => window.turnoLoading(item, false));
      buttons.forEach(button => { button.disabled = false; });
      feedback.textContent = 'No se pudo confirmar la acción. Reintenta; la tarea se conserva en Historial.';
    } finally {
      clearTimeout(timeout);
      pending.delete(id);
    }
  });
})();
