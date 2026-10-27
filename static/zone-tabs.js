(() => {
  function setup() {
    document.querySelectorAll('[data-sheet-tabs], [data-zone-workspace]').forEach(root => {
      if (root.dataset.tabsReady) return;
      root.dataset.tabsReady = 'true';
      const tabs = [...root.querySelectorAll('[role=tab]')];
      function activate(tab) {
        tabs.forEach(item => { item.setAttribute('aria-selected', String(item === tab)); item.tabIndex = item === tab ? 0 : -1; });
        if (root.hasAttribute('data-zone-workspace')) {
          const sheet = root.querySelector('[role=tabpanel]');
          sheet.setAttribute('aria-labelledby', tab.id);
          let count = 0;
          root.querySelectorAll('[data-task-zones]').forEach(card => {
            const show = tab.dataset.zone === 'all' || card.dataset.taskZones.trim().split(/\s+/).includes(tab.dataset.zone);
            card.hidden = !show;
            if (show) count++;
          });
          root.querySelector('[data-zone-count]').textContent = `${count} tareas`;
          root.querySelector('[data-zone-empty]').hidden = count > 0;
          root.querySelectorAll('[data-related-zones]').forEach(item => {
            item.hidden = tab.dataset.zone !== 'all' && !item.dataset.relatedZones.trim().split(/\s+/).includes(tab.dataset.zone);
          });
          const alerts = [...root.querySelectorAll('[data-zone-alert]')];
          const alertCount = alerts.filter(item => !item.hidden).length;
          const badge = root.querySelector('[data-alert-count]');
          if (badge) badge.textContent = alertCount;
          const empty = root.querySelector('[data-zone-alert-empty]');
          if (empty) empty.hidden = alertCount > 0;
          const globalEmpty = root.querySelector('[data-alert-global-empty]');
          if (globalEmpty && empty) globalEmpty.hidden = true;

        } else root.querySelectorAll('[role=tabpanel]').forEach(panel => { panel.hidden = panel.id !== tab.getAttribute('aria-controls'); });
      }
      root.addEventListener('alerts:updated', () => activate(tabs.find(tab => tab.getAttribute('aria-selected') === 'true') || tabs[0]));
      tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => activate(tab));
        tab.addEventListener('keydown', event => {
          let next;
          if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
          if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
          if (event.key === 'Home') next = 0;
          if (event.key === 'End') next = tabs.length - 1;
          if (next !== undefined) { event.preventDefault(); activate(tabs[next]); tabs[next].focus(); }
        });
      });
    });
  }
  setup(); document.addEventListener('gantt:updated', setup);
})();
