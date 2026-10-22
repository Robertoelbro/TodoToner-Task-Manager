(() => {
  const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  function enhance() {
    for (const id of ['id_assignees', 'id_spectators', 'id_worker', 'id_supervisor']) {
      const control = document.getElementById(id);
      if (!control || control.dataset.searchReady) continue;
      control.dataset.searchReady = 'true';
      const label = document.createElement('label'), input = document.createElement('input');
      input.type = 'search'; input.id = id + '_search'; input.autocomplete = 'off';
      input.placeholder = 'Ej.: rob'; input.setAttribute('aria-controls', id);
      label.htmlFor = input.id;
      label.textContent = 'Buscar por nombre en ' + ({id_assignees:'responsables',id_spectators:'espectadores',id_worker:'trabajadores',id_supervisor:'supervisores'}[id]);
      const status = document.createElement('p'); status.className = 'help'; status.setAttribute('role','status');
      control.before(label, input); control.after(status);
      const options = control.tagName === 'SELECT' ? Array.from(control.options).map(o=>o.cloneNode(true)) : null;
      input.addEventListener('input', () => {
        const query = normalize(input.value.trim());
        let count = 0;
        if (options) {
          const current = control.value;
          const matches = options.filter(o => !o.value || normalize(o.textContent).includes(query) || o.value === current);
          count = options.filter(o => o.value && normalize(o.textContent).includes(query)).length;
          control.replaceChildren(...matches.map(o=>o.cloneNode(true)));
          control.value = current;
        } else {
          control.querySelectorAll('label').forEach(item => {
            const match = normalize(item.textContent).includes(query);
            item.parentElement.hidden = !match;
            if (match) count++;
          });
        }
        status.textContent = `${count} coincidencias. Las selecciones anteriores se conservan.`;
      });
    }
  }
  enhance(); document.addEventListener('gantt:updated', enhance);
  const form = document.getElementById('users-search');
  if (!form) return;
  const input = document.getElementById('users-query'), results = document.getElementById('users-results');
  const feedback = document.getElementById('users-search-feedback');
  let timer, controller, sequence = 0;
  async function search() {
    const current = ++sequence;
    controller?.abort(); controller = new AbortController();
    const url = new URL(form.action || location.href); url.search = new URLSearchParams(new FormData(form));
    feedback.textContent = 'Buscando…'; results.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(url, {headers:{'X-Requested-With':'XMLHttpRequest'},signal:controller.signal,credentials:'same-origin'});
      if (!response.ok || response.redirected || response.headers.get('X-Turno-Fragment') !== 'users') throw new Error();
      const html = await response.text();
      if (current !== sequence) return;
      results.innerHTML = html; feedback.textContent = 'Resultados actualizados.';
      history.replaceState(null, '', url);
    } catch(error) {
      if (error.name !== 'AbortError' && current === sequence) feedback.textContent = 'No se pudo buscar. Reintenta o recarga la página.';
    } finally { if (current === sequence) results.removeAttribute('aria-busy'); }
  }
  input.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(search,250);});
  form.addEventListener('submit',event=>{event.preventDefault();clearTimeout(timer);search();});
})();
