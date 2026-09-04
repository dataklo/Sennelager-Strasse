(function () {
  'use strict';

  const states = {
    open: { label: 'Geöffnet', headline: 'Durchfahrt aktuell möglich', icon: '✓', color: 'green' },
    closed: { label: 'Gesperrt', headline: 'Durchfahrt aktuell gesperrt', icon: '✕', color: 'red' },
    changing: { label: 'Statuswechsel heute', headline: 'Durchfahrt ändert sich heute', icon: '↕', color: 'yellow' },
    unknown: { label: 'Unbekannt', headline: 'Durchfahrtsstatus unbekannt', icon: '?', color: 'gray' }
  };
  const weekdays = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
  const months = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];

  function localIso(date) {
    return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');
  }

  function stateFor(row) { return states[row?.status] || states.unknown; }

  function transitionLabel(row) {
    if (!row || row.status !== 'changing') return stateFor(row).label;
    const text = String(row.times || '').toLowerCase();
    if (/(open\s+from|opens?\s+from|closed\s+until)/.test(text)) return 'Öffnet heute';
    if (/(closed\s+from|closes?\s+from|open\s+until)/.test(text)) return 'Schließt heute';
    return states.changing.label;
  }

  function makeBadge(row) {
    const state = stateFor(row);
    const badge = document.createElement('span');
    badge.className = `status-badge ${state.color}`;
    const icon = document.createElement('span');
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = state.icon;
    badge.append(icon, document.createTextNode(transitionLabel(row)));
    return badge;
  }

  function setCurrentStatus(row) {
    const state = stateFor(row);
    const bar = document.getElementById('status-bar');
    if (bar) {
      bar.classList.remove('green', 'red', 'yellow', 'gray');
      bar.classList.add(state.color);
    }
    document.getElementById('status-icon')?.replaceChildren(state.icon);
    document.getElementById('current-status')?.replaceChildren(state.headline);
    document.getElementById('today-label')?.replaceChildren(state.headline);
  }

  function formatUpdate(value) {
    if (!value) return 'noch nie';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'unbekannt';
    return new Intl.DateTimeFormat('de-DE', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
      timeZone: 'Europe/Berlin'
    }).format(date) + ' Uhr';
  }

  function dayHeading(date, today, index) {
    if (index === 0 && localIso(date) === localIso(today)) return 'Heute';
    const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1);
    if (localIso(date) === localIso(tomorrow)) return 'Morgen';
    return weekdays[date.getDay()];
  }

  function renderUpcoming(schedule, today) {
    const target = document.getElementById('upcoming-list');
    if (!target) return;
    target.replaceChildren();
    Object.keys(schedule).filter((iso) => iso >= localIso(today)).sort().slice(0, 4).forEach((iso, index) => {
      const date = new Date(`${iso}T12:00:00`);
      const card = document.createElement('article');
      card.className = `summary-card ${stateFor(schedule[iso]).color}${iso === localIso(today) ? ' today' : ''}`;
      const heading = document.createElement('p'); heading.className = 'summary-date';
      heading.textContent = `${dayHeading(date, today, index)} · ${date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })}`;
      card.append(heading, makeBadge(schedule[iso]));
      target.append(card);
    });
    document.getElementById('upcoming-empty')?.toggleAttribute('hidden', target.children.length > 0);
  }

  function isoWeek(date) {
    const value = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    value.setUTCDate(value.getUTCDate() + 4 - (value.getUTCDay() || 7));
    const yearStart = new Date(Date.UTC(value.getUTCFullYear(), 0, 1));
    return Math.ceil((((value - yearStart) / 86400000) + 1) / 7);
  }

  function makeDayCard(date, month, today, row) {
    const state = stateFor(row);
    const iso = localIso(date);
    const card = document.createElement('article');
    card.className = `day-card ${state.color}${date < new Date(today.getFullYear(), today.getMonth(), today.getDate()) ? ' past' : ''}${iso === localIso(today) ? ' today' : ''}${date.getMonth() !== month.getMonth() ? ' outside-month' : ''}`;
    const dow = document.createElement('div'); dow.className = 'dow'; dow.textContent = weekdays[date.getDay()].slice(0, 2);
    const dom = document.createElement('div'); dom.className = 'dom'; dom.textContent = date.getDate();
    const label = document.createElement('div'); label.className = 'label'; label.textContent = `${state.icon} ${transitionLabel(row)}`;
    card.append(dow, dom, label);
    if (row?.times) { const times = document.createElement('div'); times.className = 'times'; times.textContent = row.times; card.append(times); }
    return card;
  }

  function renderCalendar(schedule, today) {
    const target = document.getElementById('calendar-main');
    if (!target) return;
    target.replaceChildren();
    const future = Object.keys(schedule).filter((iso) => iso >= localIso(today)).sort();
    const last = future.length ? new Date(`${future.at(-1)}T12:00:00`) : today;
    let month = new Date(today.getFullYear(), today.getMonth(), 1, 12);
    while (month <= last) {
      const section = document.createElement('section'); section.className = 'month-block';
      const title = document.createElement('h3'); title.textContent = `${months[month.getMonth()]} ${month.getFullYear()}`; section.append(title);
      const end = new Date(month.getFullYear(), month.getMonth() + 1, 0, 12);
      let cursor = new Date(month); cursor.setDate(cursor.getDate() - ((cursor.getDay() + 6) % 7));
      while (cursor <= end) {
        const week = document.createElement('div'); week.className = 'calendar-row';
        const weekLabel = document.createElement('div'); weekLabel.className = 'calendar-week-label'; weekLabel.textContent = `KW ${isoWeek(cursor)}`; week.append(weekLabel);
        for (let i = 0; i < 7; i += 1) { const date = new Date(cursor); date.setDate(cursor.getDate() + i); week.append(makeDayCard(date, month, today, schedule[localIso(date)])); }
        if (new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + 6) >= today) section.append(week);
        cursor.setDate(cursor.getDate() + 7);
      }
      target.append(section); month = new Date(month.getFullYear(), month.getMonth() + 1, 1, 12);
    }
  }

  function initializeControls() {
    const body = document.body;
    if (localStorage.getItem('theme') === 'dark') body.classList.add('theme-dark');
    if (localStorage.getItem('colorblind') === 'on') body.classList.add('colorblind');
    const theme = document.getElementById('theme-toggle'); const contrast = document.getElementById('cb-toggle');
    const sync = () => { theme?.classList.toggle('active', body.classList.contains('theme-dark')); contrast?.classList.toggle('active', body.classList.contains('colorblind')); };
    theme?.addEventListener('click', () => { body.classList.toggle('theme-dark'); localStorage.setItem('theme', body.classList.contains('theme-dark') ? 'dark' : 'light'); sync(); });
    contrast?.addEventListener('click', () => { body.classList.toggle('colorblind'); localStorage.setItem('colorblind', body.classList.contains('colorblind') ? 'on' : 'off'); sync(); }); sync();

    const modal = document.getElementById('ics-modal'); const input = document.getElementById('ics-link-input');
    if (input) input.value = `${window.location.origin}/calendar.ics`;
    document.getElementById('open-ics-popup')?.addEventListener('click', () => { if (modal) { modal.hidden = false; input?.focus(); } });
    document.querySelectorAll('[data-close="ics-modal"]').forEach((button) => button.addEventListener('click', () => { if (modal) modal.hidden = true; }));
    document.getElementById('copy-ics-link')?.addEventListener('click', async () => { if (input) await navigator.clipboard.writeText(input.value); });
  }

  initializeControls();
  fetch('/data/status_data.json', { cache: 'no-store' }).then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); }).then((data) => {
    const today = new Date(); const schedule = data.schedule || {}; const updated = formatUpdate(data.last_fetch_utc);
    setCurrentStatus(schedule[localIso(today)]); document.getElementById('last-update')?.replaceChildren(updated); document.getElementById('source-last-update')?.replaceChildren(updated);
    document.getElementById('today-date')?.replaceChildren(today.toLocaleDateString('de-DE')); renderUpcoming(schedule, today); renderCalendar(schedule, today);
  }).catch((error) => console.error('Statusdaten konnten nicht geladen werden:', error));
}());
