/* Keep section links usable as ordinary anchors without scripting. */
(() => {
  const team = document.querySelector('[data-my-team-sections]');
  if (!team) return;
  const panels = Array.from(team.querySelectorAll('[data-team-section]'));
  const links = team.querySelectorAll('.thq-tabs a');

  function showSection() {
    const target = document.getElementById(location.hash.slice(1));
    const section = target && team.contains(target) && target.closest('[data-team-section]');
    const missingWeek = !target && /^#bye-week-(?:[1-9]|1[0-8])$/.test(location.hash);
    const selected = section || (missingWeek && document.getElementById('team-byes')) || panels[0];
    if (section && target !== section) {
      // Deep links also expose evidence nested inside a closed disclosure.
      for (let node = target; node !== section; node = node.parentElement) {
        if (node.tagName === 'DETAILS') node.open = true;
      }
      if (target.id === 'my-team-submitted') document.getElementById('my-team-submitted-details').open = true;
      if (target.id === 'full-roster') document.getElementById('my-team-roster').open = true;
    }
    for (const panel of panels) panel.hidden = panel !== selected;
    for (const link of links) {
      if (link.hash === '#' + selected.id) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    }

    if (!section || target === section) return;
    requestAnimationFrame(() => {
      if (location.hash === '#' + target.id && !section.hidden) {
        target.scrollIntoView({block: 'start'});
      }
    });
  }

  showSection();
  addEventListener('hashchange', showSection);
})();
