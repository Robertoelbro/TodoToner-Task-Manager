(() => {
  const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  function enhance() {
    for (const id of ['id_assignees', 'id_spectators', 'id_worker', 'id_supervisor']) {
      const control = document.getElementById(id);
      if (!control || control.dataset.searchReady) continue;
      control.dataset.searchReady = 'true';
      const single = control.tagName === 'SELECT';
      const title = {id_assignees:'Responsables', id_spectators:'Quién puede visualizar mi tarea', id_worker:'Responsable', id_supervisor:control.closest('.filter-field')?'Supervisor':'Supervisor a cargo'}[id];
      const wrapper = document.createElement('div'); wrapper.className = 'people-picker';
      const row = document.createElement('div'); row.className = 'people-picker-input';
      const input = document.createElement('input'); input.type = 'search'; input.id = id + '_search'; input.autocomplete = 'off';
      input.placeholder = 'Ejemplo: Juan Pérez'; input.setAttribute('aria-label', title);
      input.setAttribute('aria-controls', id + '_popup'); input.setAttribute('aria-expanded', 'false');
      const toggle = document.createElement('button'); toggle.type = 'button'; toggle.className = 'secondary'; toggle.textContent = '▾';
      toggle.setAttribute('aria-label', 'Abrir lista: ' + title); toggle.setAttribute('aria-controls', id + '_popup'); toggle.setAttribute('aria-expanded', 'false');
      const popup = document.createElement('div'); popup.id = id + '_popup'; popup.className = 'people-picker-popup'; popup.hidden = true;
      const status = document.createElement('p'); status.className = 'help'; status.setAttribute('role','status');
      const selected = document.createElement('div'); selected.className = 'people-selected';
      control.before(wrapper); row.append(input,toggle); wrapper.append(row,selected,popup,status); popup.append(control);
      if (single) {
        control.size = 4;
        if (id === 'id_worker' || (id === 'id_supervisor' && control.closest('.filter-field'))) {
          const empty = [...control.options].find(option => !option.value);
          if (empty) empty.textContent = 'Sin filtro';
        }
        const label = document.querySelector(`label[for="${id}"]`);
        if (label) {
          if (control.closest('.filter-field')) {
            label.classList.remove('sr-only');
            label.htmlFor = input.id;
            label.textContent = title;
          } else if (id === 'id_supervisor') {
            label.classList.remove('sr-only');
            label.htmlFor = input.id;
            label.textContent = 'Supervisor a cargo (opcional)';
            input.setAttribute('aria-label', 'Supervisor a cargo (opcional)');
          } else label.classList.add('sr-only');
        }
        control.setAttribute('aria-label',title);
      }
      const options = single ? Array.from(control.options).map(o=>o.cloneNode(true)) : null;
      function open(value) {
        popup.hidden = !value;
        input.setAttribute('aria-expanded',String(value)); toggle.setAttribute('aria-expanded',String(value));
        toggle.setAttribute('aria-label',(value ? 'Cerrar lista: ' : 'Abrir lista: ') + title);
      }
      function selections() {
        if (single) {
          selected.textContent = control.value ? control.selectedOptions[0]?.textContent || '' : '';
          return;
        }
        selected.replaceChildren();
        control.querySelectorAll('input:checked').forEach(check => {
          const chip = document.createElement('button'); chip.type = 'button'; chip.className = 'secondary small';
          const name = check.closest('label').textContent.trim(); chip.textContent = name + ' ×'; chip.setAttribute('aria-label','Quitar ' + name);
          if (check.dataset.assignedByArea === 'true') {
            chip.textContent = name + ' (área)'; chip.disabled = true;
            chip.setAttribute('aria-label', name + ', seleccionado por área');
            chip.title = 'Desmarca el área para quitar la selección automática.';
          }
          chip.addEventListener('click',()=>{check.checked=false;check.dispatchEvent(new Event('change',{bubbles:true}));input.focus();});
          selected.append(chip);
        });
      }
      function filter() {
        const query = normalize(input.value.trim()); let count = 0;
        if (single) {
          const current = control.value;
          const matches = options.filter(o=>!o.value || normalize(o.textContent).includes(query));
          count = matches.filter(o=>o.value).length;
          // Keep the selected value submitted even when it does not match the search.
          if (current && !matches.some(o=>o.value===current)) {
            const prior = options.find(o=>o.value===current).cloneNode(true); prior.hidden=true; matches.push(prior);
          }
          control.replaceChildren(...matches.map(o=>o.cloneNode(true))); control.value=current;
          control.size=Math.min(6,Math.max(2,matches.filter(o=>!o.hidden).length));
        } else control.querySelectorAll('label').forEach(label=>{
          const match=normalize(label.textContent).includes(query); label.parentElement.hidden=!match; if(match)count++;
        });
        status.textContent = count ? `${count} coincidencias.` : 'Sin coincidencias.';
      }
      toggle.addEventListener('click',()=>{if(popup.hidden){filter();open(true);}else open(false);});
      input.addEventListener('input',()=>{filter();open(true);});
      input.addEventListener('keydown',event=>{if(event.key==='ArrowDown'){event.preventDefault();filter();open(true);(single?control:control.querySelector('div:not([hidden]) input'))?.focus();}if(event.key==='Escape')open(false);});
      wrapper.addEventListener('keydown',event=>{if(event.key==='Escape'){open(false);input.focus();}});
      wrapper.addEventListener('focusout',()=>{setTimeout(()=>{if(!wrapper.contains(document.activeElement))open(false);},0);});
      control.addEventListener('change',()=>{selections();if(single){open(false);input.value='';input.focus();}});
      if (id === 'id_assignees' || id === 'id_spectators') {
        const areas = document.getElementById(id === 'id_assignees' ? 'id_assignee_areas' : 'id_spectator_areas');
        if (areas) {
          const checks = [...control.querySelectorAll('input[type=checkbox]')];
          const manual = new Set(checks.filter(check => check.checked).map(check => check.value));
          function syncAreas() {
            const selectedAreas = new Set([...areas.querySelectorAll('input:checked')].map(check => check.value));
            checks.forEach(check => {
              const automatic = selectedAreas.has(check.dataset.areaId);
              check.dataset.assignedByArea = String(automatic && !manual.has(check.value));
              check.checked = automatic || manual.has(check.value);
              check.disabled = automatic && !manual.has(check.value);
            });
            selections();
            if (selectedAreas.size) {
              const count = checks.filter(check => check.checked).length;
              status.textContent = count + (id === 'id_assignees' ? ' responsables seleccionados.' : ' usuarios con acceso seleccionados.') + ' Los marcados por área se incluyen automáticamente.';
            } else status.textContent = '';
          }
          areas.addEventListener('change', syncAreas);
          control.addEventListener('change', event => {
            const check = event.target;
            if (check.matches('input[type=checkbox]')) {
              if (check.checked) manual.add(check.value); else manual.delete(check.value);
              syncAreas();
            }
          });
          syncAreas();
        }
      }
      selections();
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
