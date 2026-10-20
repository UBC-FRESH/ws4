// WS4 browser shell: reads the service's artefacts, no build step, relative URLs so it works
// under a proxy prefix as well as at the root.

const state = { run: null, year: 0, features: [], view: { s: 1, x: 0, y: 0 }, base: null, skin: null, targets: [], targetCells: new Map(), watched: new Set(), windowValues: new Map(), series: new Map(), runPaused: false, live: { active: false, schedule: new Map(), total: 0 }, history: [], yearChosen: false, chatSession: null, chatBusy: false };

const $ = (id) => document.getElementById(id);
const statusLine = (text) => { $('status').textContent = text; };

async function api(path) {
  const response = await fetch(path, { headers: { accept: 'application/json' } });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail ?? detail; } catch { /* not json */ }
    throw new Error(detail);
  }
  return response.json();
}

function coordinates(geometry) {
  if (!geometry) return [];
  if (geometry.type === 'Point') return [geometry.coordinates];
  if (geometry.type === 'Polygon') return geometry.coordinates.flat();
  if (geometry.type === 'MultiPolygon') return geometry.coordinates.flat(2);
  return [];
}

function bounds(features) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const feature of features) {
    for (const [x, y] of coordinates(feature.geometry)) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  return Number.isFinite(minX) ? { minX, minY, maxX, maxY } : null;
}

function fit(features) {
  const box = bounds(features);
  document.addEventListener('click', (event) => {
    const button = event.target.closest('#start-run');
    if (!button || button.disabled) return;
    event.preventDefault();
    if (state.live.active) togglePause(); else startRun();
  });
  document.addEventListener('click', (event) => {
    const stop = event.target.closest('#stop-run');
    if (!stop || stop.disabled) return;
    event.preventDefault();
    stopRun();
  });
  const svg = $('map');
  const width = svg.clientWidth || 800;
  const height = svg.clientHeight || 600;
  if (!box) return null;
  const spanX = Math.max(box.maxX - box.minX, 1);
  const spanY = Math.max(box.maxY - box.minY, 1);
  const pad = 24;
  const scale = Math.min((width - 2 * pad) / spanX, (height - 2 * pad) / spanY);
  const offsetX = pad + (width - 2 * pad - spanX * scale) / 2;
  const offsetY = pad + (height - 2 * pad - spanY * scale) / 2;
  return {
    project: ([x, y]) => [offsetX + (x - box.minX) * scale, height - offsetY - (y - box.minY) * scale],
    scale,
    metresPerPixel: 1 / scale,
  };
}

function applyView() {
  $('viewport').setAttribute('transform', `translate(${state.view.x} ${state.view.y}) scale(${state.view.s})`);
}

function render(refit = true) {
  if (refit || !state.base) {
    const base = fit(state.features);
    if (!base) return;
    state.base = base;
    state.view = { s: 1, x: 0, y: 0 };
    applyView();
  }
  const base = state.base;
  const viewport = $('viewport');
  viewport.replaceChildren();
  const groups = { treated: document.createElementNS('http://www.w3.org/2000/svg', 'g'),
                   untreated: document.createElementNS('http://www.w3.org/2000/svg', 'g') };
  let treated = 0, untreated = 0;
  const circles = [];
  const paths = [];
  for (const feature of state.features) {
    const geometry = feature.geometry;
    const properties = feature.properties ?? {};
    let isTreated = Boolean(properties.treated);
    if (state.live.active) {
      const chain = state.live.schedule.get(String(properties.block_id));
      isTreated = chain
        ? chain.some((event) => Number(event[1]) === Number(state.year))
        : false;
    }
    const klass = isTreated ? 'treated' : 'untreated';
    const group = groups[klass];
    if (geometry?.type === 'Point') {
      const [cx, cy] = base.project(geometry.coordinates);
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', cx.toFixed(1));
      circle.setAttribute('cy', cy.toFixed(1));
      circle.setAttribute('r', '2.2');
      circle.setAttribute('class', `block ${klass}`);
      circle.dataset.block = properties.block_id;
      circles.push(circle);
      group.append(circle);
    } else if (geometry?.type === 'Polygon' || geometry?.type === 'MultiPolygon') {
      const rings = geometry.type === 'Polygon' ? geometry.coordinates : geometry.coordinates.flat();
      const d = rings.map((ring) => ring.map((point, index) => {
        const [x, y] = base.project(point);
        return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ') + ' Z').join(' ');
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', d);
      path.setAttribute('class', `block ${klass}`);
      path.dataset.block = properties.block_id;
      paths.push(path);
      group.append(path);
    }
    if (isTreated) treated += 1; else untreated += 1;
  }
  viewport.append(groups.untreated, groups.treated);
  $('n-treated').textContent = treated.toLocaleString();
  $('n-untreated').textContent = untreated.toLocaleString();
  $('scale').textContent = `year ${state.year} · 1 px ≈ ${Math.round(1 / base.scale)} m`;
  applyVisibility();
}

function applyVisibility() {
  const showTreated = $('show-treated').checked;
  const showUntreated = $('show-untreated').checked;
  for (const element of document.querySelectorAll('#viewport .treated')) element.style.display = showTreated ? '' : 'none';
  for (const element of document.querySelectorAll('#viewport .untreated')) element.style.display = showUntreated ? '' : 'none';
}

async function loadMap() {
  if (!state.run) return;
  statusLine('loading map…');
  try {
    const body = await api(`api/runs/${encodeURIComponent(state.run)}/map?year=${state.year}`);
    state.features = body.features ?? [];
    render();
    statusLine(`${state.features.length.toLocaleString()} blocks · year ${state.year}`);
  } catch (error) {
    statusLine(`map unavailable: ${error.message}`);
  }
}

async function loadPeriods() {
  const body = await api(`api/runs/${encodeURIComponent(state.run)}/periods`);
  const slider = $('year');
  const low = Number(body.min ?? 0);
  const high = Number(body.max ?? 0);
  const wanted = Number.isFinite(state.year) ? state.year : low;
  slider.min = low;
  slider.max = high;
  // keep the analyst's year across a run finishing; only clamp it into the new horizon
  state.year = Math.min(Math.max(wanted, low), high);
  slider.value = state.year;
  $('year-label').textContent = state.year;
}

function applySkin(skin) {
  state.skin = skin;
  const panels = new Set(skin.panels ?? ['legend', 'targets', 'reports']);
  for (const button of document.querySelectorAll('nav.tabs button')) {
    button.hidden = !panels.has(button.dataset.tab);
  }
  const active = document.querySelector('nav.tabs button.active');
  if (active && active.hidden) {
    const first = [...document.querySelectorAll('nav.tabs button')].find((button) => !button.hidden);
    if (first) first.click();
  }
  $('show-treated').closest('label').hidden = !(skin.layers ?? []).includes('treatments');
  $('show-untreated').closest('label').hidden = !(skin.layers ?? []).includes('blocks');
  const readOnly = Boolean(skin.read_only) || !(skin.actions ?? []).includes('edit_targets');
  $('save-targets').hidden = readOnly || !document.querySelector('#targets-table:not([hidden])');
  $('start-run').hidden = Boolean(skin.read_only);
  for (const input of document.querySelectorAll('#targets-table input')) input.disabled = readOnly;
}

async function loadSkins() {
  try {
    const skins = await api('api/skins');
    const select = $('skin');
    for (const skin of skins) {
      const option = document.createElement('option');
      option.value = skin.id;
      option.textContent = skin.title;
      select.append(option);
    }
    const preferred = skins.find((skin) => skin.id === 'scenario-analyst') ?? skins[0];
    if (preferred) {
      select.value = preferred.id;
      applySkin(preferred);
    }
  } catch { /* the application still works without skins */ }
}

function numberInput(value, field, index) {
  const input = document.createElement('input');
  input.type = 'number';
  input.step = 'any';
  input.value = value ?? '';
  input.dataset.field = field;
  input.dataset.index = index;
  return input;
}

function loadWatched() {
  try {
    const raw = window.localStorage.getItem('ws4.watched');
    if (raw !== null) state.watched = new Set(JSON.parse(raw));
  } catch { /* a private window may refuse storage */ }
}

function saveWatched() {
  try { window.localStorage.setItem('ws4.watched', JSON.stringify([...state.watched])); } catch { /* ignore */ }
}

function makeMini() {
  const mini = document.createElement('span');
  mini.className = 'mini';
  const band = document.createElement('span');
  band.className = 'mini-band';
  const marker = document.createElement('span');
  marker.className = 'mini-marker';
  mini.append(band, marker);
  return { mini, band, marker };
}

function statusOf(row, value) {
  if (value === undefined || value === null) return 'unknown';
  if (row.minimum !== null && value < row.minimum) return 'below';
  if (row.maximum !== null && value > row.maximum) return 'above';
  return 'met';
}

function renderWatchPanel() {
  const panel = $('watch-panel');
  panel.replaceChildren();
  const watched = state.targets.filter((row) => state.watched.has(`${row.year}|${row.account}`));
  if (!watched.length) {
    panel.textContent = 'no targets selected — tick a target in the table below';
    return;
  }
  const groups = new Map();
  for (const row of watched) {
    if (!groups.has(row.account)) groups.set(row.account, []);
    groups.get(row.account).push(row);
  }
  const svgNS = 'http://www.w3.org/2000/svg';
  for (const [account, rows] of groups) {
    const targetsByYear = new Map(rows.map((row) => [Number(row.year), row]));
    const series = state.series.get(account) ?? new Map();
    const periodWidth = Number(rows[0].period_width ?? 1);
    const accumulating = account.startsWith('product.');
    const cellYears = [];
    for (const row of rows) {
      const rowWidth = Math.max(1, Number(row.period_width ?? periodWidth));
      for (let year = Number(row.year) - rowWidth + 1; year <= Number(row.year); year += 1) {
        if (year >= 0) cellYears.push(year);
      }
    }
    const rawYears = [...series.keys()];
    const lowYear = rawYears.length ? Math.min(...rawYears, ...cellYears) : Math.min(...cellYears);
    const highYear = rawYears.length ? Math.max(...rawYears, ...cellYears) : Math.max(...cellYears);
    const years = [...new Set([
      ...rawYears,
      ...cellYears,
      ...rows.map((row) => Number(row.year)),
      ...[...state.windowValues.keys()]
        .filter((key) => key.endsWith(`|${account}`))
        .map((key) => Number(key.split('|')[0])),
    ])].filter((year) => year >= lowYear && year <= highYear).sort((left, right) => left - right);
    if (!years.length) continue;
    const valueAt = (year) => {
      const live = state.windowValues.get(`${year}|${account}`);
      if (live !== undefined) return Number(live);
      if (!accumulating) return series.has(year) ? Number(series.get(year)) : undefined;
      const windowWidth = Math.max(1, Number(targetsByYear.get(year)?.period_width ?? periodWidth));
      let total = 0;
      let found = false;
      for (let offset = 0; offset < windowWidth; offset += 1) {
        const value = series.get(year - offset);
        if (value !== undefined) { total += Number(value); found = true; }
      }
      return found ? total : 0;
    };
    const values = years.map(valueAt);
    const latestTarget = rows.reduce((left, right) => (Number(left.year) >= Number(right.year) ? left : right));
    const latestValue = state.windowValues.get(`${latestTarget.year}|${account}`) ?? valueAt(Number(latestTarget.year));
    const card = document.createElement('div');
    card.className = 'window-card';
    if (periodWidth > 1) card.title = `${account}: ${accumulating ? 'sum' : 'level'} over a ${periodWidth}-year period`;
    const title = document.createElement('div');
    title.className = 'window-title';
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = account;
    name.title = account;
    const badge = document.createElement('span');
    badge.className = 'window-badge';
    if (latestValue !== undefined) {
      const status = statusOf(latestTarget, latestValue);
      badge.textContent = `${Number(latestValue).toLocaleString(undefined, { maximumFractionDigits: 1 })}${status ? ` · ${status}` : ''}`;
      if (status) badge.classList.add(status);
    } else {
      badge.textContent = '—';
    }
    title.append(name, badge);
    card.append(title);
    const width = 320, height = 92, left = 34, right = 8, top = 8, bottom = 22;
    let low = Infinity, high = -Infinity;
    for (const row of rows) {
      for (const bound of [row.minimum, row.maximum]) {
        if (bound !== null && bound !== undefined && Number.isFinite(Number(bound))) {
          low = Math.min(low, Number(bound));
          high = Math.max(high, Number(bound));
        }
      }
    }
    for (const value of values) {
      if (value !== undefined && Number.isFinite(Number(value))) {
        low = Math.min(low, Number(value));
        high = Math.max(high, Number(value));
      }
    }
    if (!Number.isFinite(low) || !Number.isFinite(high)) { low = 0; high = 1; }
    if (low === high) { low -= 0.5; high += 0.5; }
    const pad = (high - low) * 0.12;
    const domainLow = low - pad, domainHigh = high + pad;
    const step = years.length > 1 ? (width - left - right) / (years.length - 1) : 0;
    const x = (index) => (years.length === 1
      ? left + (width - left - right) / 2
      : left + index * step);
    const y = (value) => top + (1 - (value - domainLow) / (domainHigh - domainLow)) * (height - top - bottom);
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('class', 'window-svg');
    const axis = document.createElementNS(svgNS, 'line');
    axis.setAttribute('x1', left); axis.setAttribute('x2', width - right);
    axis.setAttribute('y1', height - bottom); axis.setAttribute('y2', height - bottom);
    axis.setAttribute('class', 'window-axis');
    svg.append(axis);
    const bandWidth = Math.max(4, Math.min(16, step * 0.6 || 12));
    rows.forEach((row) => {
      const index = years.indexOf(Number(row.year));
      if (index < 0) return;
      if (row.minimum !== null && row.maximum !== null) {
        const band = document.createElementNS(svgNS, 'rect');
        band.setAttribute('x', x(index) - bandWidth / 2);
        band.setAttribute('y', y(row.maximum));
        band.setAttribute('width', bandWidth);
        band.setAttribute('height', Math.max(1, y(row.minimum) - y(row.maximum)));
        band.setAttribute('class', 'window-band');
        svg.append(band);
      } else if (row.minimum !== null || row.maximum !== null) {
        const bound = row.minimum ?? row.maximum;
        const line = document.createElementNS(svgNS, 'line');
        line.setAttribute('x1', x(index) - bandWidth / 2); line.setAttribute('x2', x(index) + bandWidth / 2);
        line.setAttribute('y1', y(bound)); line.setAttribute('y2', y(bound));
        line.setAttribute('class', 'window-bound');
        svg.append(line);
      }
    });
    const defined = values.map((value, index) => ({ value, index }))
                          .filter((entry) => entry.value !== undefined);
    if (defined.length > 1) {
      const line = document.createElementNS(svgNS, 'polyline');
      line.setAttribute('points', defined.map((entry) => `${x(entry.index)},${y(entry.value)}`).join(' '));
      line.setAttribute('class', 'window-line');
      svg.append(line);
    }
    for (const entry of defined) {
      const dot = document.createElementNS(svgNS, 'circle');
      dot.setAttribute('cx', x(entry.index));
      dot.setAttribute('cy', y(entry.value));
      dot.setAttribute('r', years.length > 40 ? 1.4 : 2.2);
      const year = years[entry.index];
      const target = targetsByYear.get(year);
      dot.setAttribute('class', `window-dot ${target ? statusOf(target, entry.value) : ''}`);
      const tip = document.createElementNS(svgNS, 'title');
      tip.textContent = `${year}: ${Number(entry.value).toLocaleString()}${target ? ` (${statusOf(target, entry.value)})` : ''}`;
      dot.append(tip);
      svg.append(dot);
    }
    const labelEvery = Math.max(1, Math.ceil(years.length / 6));
    years.forEach((year, index) => {
      if (index % labelEvery && index !== years.length - 1) return;
      const label = document.createElementNS(svgNS, 'text');
      label.setAttribute('x', x(index));
      label.setAttribute('y', height - 6);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('class', 'window-label');
      label.textContent = String(year);
      svg.append(label);
    });
    card.append(svg);
    panel.append(card);
  }
}

function paintTarget(entry, value) {
  entry.value = value;
  const row = entry.row;
  if (value === undefined || value === null) {
    entry.text.textContent = '—';
    if (entry.band) entry.band.style.display = 'none';
    if (entry.marker) entry.marker.style.display = 'none';
    return;
  }
  const low = row.minimum ?? Math.min(0, value);
  const high = row.maximum ?? Math.max(value, low + 1);
  const width = Math.max(high - low, Math.abs(value) * 0.2, 1e-9);
  const domainLow = low - width * 0.05;
  const domainHigh = high + width * 0.05;
  const position = (edge) => {
    const ratio = (edge - domainLow) / (domainHigh - domainLow);
    return `${Math.min(100, Math.max(0, ratio * 100))}%`;
  };
  if (entry.band) {
    entry.band.style.display = '';
    entry.band.style.left = position(low);
    entry.band.style.width = `${Math.max(0, Math.min(100, ((high - low) / (domainHigh - domainLow)) * 100))}%`;
  }
  if (entry.marker) {
    entry.marker.style.display = '';
    entry.marker.style.left = position(value);
  }
  let status = 'met';
  if (row.minimum !== null && value < row.minimum) status = 'below';
  else if (row.maximum !== null && value > row.maximum) status = 'above';
  entry.text.textContent = `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })} · ${status}`;
}

function updateLiveTargets(values, iteration) {
  let painted = 0;
  for (const item of values) {
    const key = `${item.year}|${item.account}`;
    const value = Number(item.value);
    if (state.watched.has(key)) { state.windowValues.set(key, value); painted += 1; }
    const entry = state.targetCells.get(key);
    if (entry) paintTarget(entry, value);
  }
  if (painted) renderWatchPanel();
  if (painted && iteration !== undefined) {
    $('run-status').textContent = `live target state at iteration ${iteration} (${painted} cells)`;
  }
}

async function loadTargets() {
  const empty = $('targets-empty');
  const table = $('targets-table');
  const button = $('save-targets');
  try {
    state.targetCells = new Map();
    state.windowValues = new Map();
    const rows = await api('api/targets.json');
    state.targets = rows;
    if (!rows.length) {
      empty.hidden = false;
      table.hidden = true;
      button.hidden = true;
      return;
    }
    empty.hidden = true;
    table.hidden = false;
    button.hidden = false;
    if (!state.yearChosen) {
      const slider = $('year');
      const low = Number(slider.min || 0);
      const high = Number(slider.max || 0);
      const first = Number(rows[0].year);
      state.year = Math.min(Math.max(first, low), high);
      slider.value = state.year;
      $('year-label').textContent = state.year;
    }
    const body = table.querySelector('tbody');
    body.replaceChildren();
    const keys = rows.map((row) => `${row.year}|${row.account}`);
    if (state.watched.size === 0 && window.localStorage.getItem('ws4.watched') === null) {
      for (const key of keys.slice(0, 8)) state.watched.add(key);
      saveWatched();
    }
    const values = {};
    state.series = new Map();
    try {
      const realized = await api(`api/runs/${encodeURIComponent(state.run)}/targets`);
      for (const item of realized) {
        (values[item.year] ??= {})[item.account] = item.value;
      }
      const all = await api(`api/runs/${encodeURIComponent(state.run)}/accounts`);
      for (const item of all) {
        if (!state.series.has(item.account)) state.series.set(item.account, new Map());
        state.series.get(item.account).set(Number(item.year), Number(item.value));
      }
    } catch { /* no realized values for this run */ }
    rows.forEach((row, index) => {
      const tr = document.createElement('tr');
      const key = `${row.year}|${row.account}`;
      const account = document.createElement('td');
      account.className = 'account';
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.checked = state.watched.has(key);
      box.title = 'watch this target';
      box.addEventListener('change', () => {
        if (box.checked) state.watched.add(key); else state.watched.delete(key);
        saveWatched();
        renderWatchPanel();
      });
      const label = document.createElement('span');
      label.textContent = row.account;
      label.title = row.account;
      const valueLine = document.createElement('div');
      valueLine.className = 'account-value';
      account.append(box, label, valueLine);
      tr.append(account);
      const year = document.createElement('td');
      year.textContent = row.year;
      tr.append(year);
      for (const field of ['minimum', 'maximum', 'min_weight', 'max_weight']) {
        const td = document.createElement('td');
        td.append(numberInput(row[field], field, index));
        tr.append(td);
      }
      state.targetCells.set(`${row.year}|${row.account}`, {
        row, text: valueLine, band: null, marker: null, value: values[row.year]?.[row.account],
      });
      body.append(tr);
    });
    for (const entry of state.targetCells.values()) paintTarget(entry, entry.value);
    for (const row of rows) {
      const value = values[row.year]?.[row.account];
      if (value !== undefined) state.windowValues.set(`${row.year}|${row.account}`, Number(value));
    }
    renderWatchPanel();
    if (state.skin) applySkin(state.skin);
  } catch (error) {
    empty.hidden = false;
    empty.textContent = `targets unavailable: ${error.message}`;
    table.hidden = true;
    button.hidden = true;
  }
}

async function saveTargets() {
  const rows = state.targets.map((row) => ({ ...row }));
  for (const input of document.querySelectorAll('#targets-table input[data-field]')) {
    const index = Number(input.dataset.index);
    const field = input.dataset.field;
    if (!rows[index] || !field) continue;
    rows[index][field] = input.value === '' ? null : Number(input.value);
  }
  try {
    const response = await fetch('api/targets.json', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(rows),
    });
    if (!response.ok) {
      const detail = (await response.json()).detail ?? response.statusText;
      throw new Error(detail);
    }
    $('targets-status').textContent = `saved ${rows.length} targets`;
    loadTargets().catch(() => { /* the run does not depend on the table refresh */ });
    return true;
  } catch (error) {
    $('targets-status').textContent = `not saved: ${error.message}`;
    return false;
  }
}

async function fillRuns(summary, preferred) {
  const select = $('run');
  select.replaceChildren();
  for (const run of summary.runs ?? []) {
    const option = document.createElement('option');
    option.value = run.id;
    option.textContent = `${run.id} (${run.kind ?? 'run'})`;
    select.append(option);
  }
  const chosen = (summary.runs ?? []).find((run) => run.id === preferred) ?? (summary.runs ?? [])[0];
  if (!chosen) return false;
  select.value = chosen.id;
  state.run = chosen.id;
  return true;
}

let runWatch = { id: null, timer: null, source: null, started: 0, done: false };

function drawSpark() {
  const svg = $('spark');
  if (!svg) return;
  svg.replaceChildren();
  const data = state.history;
  if (data.length < 2) return;
  const low = Math.min(...data.map((point) => point.objective));
  const high = Math.max(...data.map((point) => point.objective));
  const span = Math.max(high - low, 1e-9);
  const points = data
    .map((point, index) => `${(index / (data.length - 1)) * 138 + 1},${24 - ((point.objective - low) / span) * 22}`)
    .join(' ');
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  line.setAttribute('points', points);
  line.setAttribute('fill', 'none');
  line.setAttribute('stroke', '#2f7d4f');
  line.setAttribute('stroke-width', '1.2');
  svg.append(line);
}

let repaintPending = false;
function scheduleRepaint() {
  if (repaintPending) return;
  repaintPending = true;
  window.requestAnimationFrame(() => { repaintPending = false; if (state.features.length) render(false); });
}

function showRun(text, live) {
  $('run-panel').hidden = false;
  $('run-detail').textContent = text;
  $('run-panel').style.borderColor = live ? '#b7d7c2' : '#d9e2ec';
}

function stopRunWatch() {
  if (runWatch.timer) { clearInterval(runWatch.timer); runWatch.timer = null; }
  if (runWatch.source) { runWatch.source.close(); runWatch.source = null; }
}

function elapsed() {
  const seconds = Math.max(0, Math.round((Date.now() - runWatch.started) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

async function finishRun(id) {
  if (runWatch.done) return;
  runWatch.done = true;
  stopRunWatch();
  state.live.active = false;
  $('start-run').textContent = '▶ Play';
  $('stop-run').hidden = true;
  state.runPaused = false;
  showRun(`run ${id} · done`, false);
  $('run-status').textContent = '';
  try {
    const summary = await api('api/summary');
    if (await fillRuns(summary, id)) {
      await loadPeriods(); await loadTargets(); await loadReports(); await loadMap();
    }
  } catch { /* the run is done; a refresh failure is not fatal */ }
  window.setTimeout(() => { $('run-panel').hidden = true; }, 6000);
}

async function pollRun(id) {
  if (id !== runWatch.id) return;
  try {
    const status = await api(`api/runs/${encodeURIComponent(id)}/status`);
    state.runPaused = Boolean(status.paused);
    $('start-run').textContent = state.runPaused ? '▶ Resume' : '⏸ Pause';
    if (status.status === 'failed') {
      stopRunWatch();
      $('start-run').textContent = '▶ Play';
      $('stop-run').hidden = true;
      showRun(`run ${id} · the search exited without a summary — see console.log`, false);
      return;
    }
    if (!status.running) { await finishRun(id); return; }
    const step = status.last_step;
    const shown = state.live.total || step?.total || step?.iteration;
    const island = step?.island ? ` · ${step.island}` : '';
    const progress = step
      ? `${Number(shown).toLocaleString()} iterations · best ${Number(step.objective).toFixed(2)}${island}`
      : (runWatch.islands > 1 ? `starting ${runWatch.islands} islands…` : 'waiting for the first step…');
    showRun(`run ${id} · ${progress} · ${elapsed()}`, true);
  } catch (error) {
    showRun(`run ${id} · status unavailable: ${error.message}`, true);
  }
}

async function togglePause() {
  if (!runWatch.id) return;
  const action = state.runPaused ? 'run' : 'pause';
  try {
    await fetch(`api/runs/${encodeURIComponent(runWatch.id)}/control`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    state.runPaused = !state.runPaused;
    $('start-run').textContent = state.runPaused ? '▶ Resume' : '⏸ Pause';
    showRun(`run ${runWatch.id} · ${state.runPaused ? 'paused' : 'running'} · ${elapsed()}`, true);
  } catch (error) {
    showRun(`run ${runWatch.id} · control failed: ${error.message}`, true);
  }
}

async function stopRun() {
  if (!runWatch.id) return;
  $('stop-run').disabled = true;
  try {
    await fetch(`api/runs/${encodeURIComponent(runWatch.id)}/control`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ action: 'stop' }),
    });
    showRun(`run ${runWatch.id} · stopping…`, true);
  } catch (error) {
    showRun(`run ${runWatch.id} · stop failed: ${error.message}`, true);
  } finally {
    window.setTimeout(() => { $('stop-run').disabled = false; }, 1000);
  }
}

async function startRun() {
  stopRunWatch();
  const status = $('run-status');
  $('start-run').disabled = true;
  showRun('saving targets…', true);
  let saved = false;
  try { saved = await saveTargets(); } catch (error) { saved = false; }
  if (!saved) {
    $('start-run').disabled = false;
    $('start-run').textContent = '▶ Play';
    const reason = $('targets-status').textContent || 'no reason given';
    showRun(`targets not saved: ${reason}`, false);
    return;
  }
  const iterations = Number($('run-iterations')?.value || 0);
  const timeLimit = ($('run-time-limit')?.value || '').trim();
  const seed = Number($('run-seed')?.value || 1);
  const years = Number($('run-years')?.value || 50);
  const islands = Number($('run-islands')?.value || 1);
  status.textContent = '';
  runWatch = { id: null, timer: null, source: null, started: Date.now(), done: false, islands: 1 };
  state.live = { active: true, schedule: new Map(), total: 0 };
  state.runPaused = false;
  state.history = [];
  drawSpark();
  showRun('posting the run request…', true);
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch('api/runs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ iterations, time_limit: timeLimit, seed, years, islands }),
      signal: controller.signal,
    });
    window.clearTimeout(timer);
    if (!response.ok) {
      const detail = (await response.json()).detail ?? response.statusText;
      throw new Error(detail);
    }
    const run = await response.json();
    runWatch.id = run.id;
    runWatch.islands = Number(run.islands || 1);
    $('start-run').disabled = false;
    $('start-run').textContent = '⏸ Pause';
    $('stop-run').hidden = false;
    pollRun(run.id);
    runWatch.timer = setInterval(() => pollRun(run.id), 2000);
    const events = new EventSource(`api/runs/${encodeURIComponent(run.id)}/events`);
    runWatch.source = events;
    events.addEventListener('started', () => showRun(`run ${run.id} · ${run.islands ?? 1} island${Number(run.islands ?? 1) === 1 ? '' : 's'} · connected · ${elapsed()}`, true));
    events.addEventListener('schedule', (event) => {
      const payload = JSON.parse(event.data);
      if (payload.reset) state.live.schedule = new Map();
      for (const [block, chain] of payload.changed ?? []) {
        state.live.schedule.set(String(block), chain);
      }
      scheduleRepaint();
    });
    events.addEventListener('progress', (event) => {
      const step = JSON.parse(event.data);
      state.live.total = Number(step.total ?? step.iteration);
      state.history.push({ iteration: step.total ?? step.iteration, objective: Number(step.objective) });
      if (state.history.length > 2000) state.history.shift();
      drawSpark();
      if (!state.runPaused) {
        const shown = step.total ?? step.iteration;
        const island = step.island ? ` · ${step.island}` : '';
        showRun(
          `run ${run.id} · ${Number(shown).toLocaleString()} iterations · best ${Number(step.objective).toFixed(2)}${island} · ${elapsed()}`,
          true,
        );
      }
    });
    events.addEventListener('targets', (event) => {
      const payload = JSON.parse(event.data);
      updateLiveTargets(payload.values ?? [], payload.iteration);
    });
    events.addEventListener('done', () => finishRun(run.id));
    events.addEventListener('error', () => { /* the poll decides; the proxy may buffer SSE */ });
  } catch (error) {
    window.clearTimeout(timer);
    state.live.active = false;
    $('start-run').disabled = false;
    $('start-run').textContent = '▶ Play';
    $('stop-run').hidden = true;
    const reason = error.name === 'AbortError' ? 'the request timed out after 20 s' : error.message;
    showRun(`not started: ${reason}`, false);
  }
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"') {
        if (text[index + 1] === '"') { field += '"'; index += 1; } else quoted = false;
      } else field += character;
    } else if (character === '"') quoted = true;
    else if (character === ',') { row.push(field); field = ''; }
    else if (character === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else if (character !== '\r') field += character;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  return rows;
}

function renderReport(rows) {
  const preview = $('report-preview');
  preview.replaceChildren();
  if (!rows.length) { preview.textContent = 'the report is empty'; return; }
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const header = document.createElement('tr');
  for (const name of rows[0]) {
    const cell = document.createElement('th'); cell.textContent = name; header.append(cell);
  }
  head.append(header); table.append(head);
  const body = document.createElement('tbody');
  for (const row of rows.slice(1, 201)) {
    const tr = document.createElement('tr');
    for (const value of row) { const cell = document.createElement('td'); cell.textContent = value; tr.append(cell); }
    body.append(tr);
  }
  table.append(body); preview.append(table);
}

async function showReport(name) {
  const preview = $('report-preview');
  const url = `api/runs/${encodeURIComponent(state.run)}/reports/${encodeURIComponent(name)}`;
  if (!name.toLowerCase().endsWith('.csv')) {
    preview.innerHTML = `<a href="${url}" target="_blank">open ${name}</a>`;
    return;
  }
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(response.statusText);
    renderReport(parseCsv(await response.text()));
  } catch (error) {
    preview.textContent = `report unavailable: ${error.message}`;
  }
}

async function loadReports() {
  if (!state.run) return;
  const list = $('reports');
  list.replaceChildren();
  $('report-preview').replaceChildren();
  try {
    const body = await api(`api/runs/${encodeURIComponent(state.run)}/reports`);
    for (const report of body) {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = `api/runs/${encodeURIComponent(state.run)}/reports/${encodeURIComponent(report.name)}`;
      link.textContent = report.name;
      link.addEventListener('click', (event) => { event.preventDefault(); showReport(report.name); });
      item.append(link);
      list.append(item);
    }
  } catch (error) {
    list.textContent = `reports unavailable: ${error.message}`;
  }
}

function showDetail(block) {
  const feature = state.features.find((candidate) => String(candidate.properties?.block_id) === String(block));
  if (!feature) return;
  const properties = feature.properties ?? {};
  $('detail').innerHTML = `<b>Block ${properties.block_id}</b><br>` +
    `treated: ${properties.treated ? 'yes' : 'no'}<br>` +
    `treatments: ${(properties.treatments ?? []).join(', ') || '—'}`;
}

function wireSplitter() {
  const splitter = $('splitter');
  const sidebar = $('sidebar');
  if (!splitter || !sidebar) return;
  const root = document.documentElement;
  try {
    const saved = window.localStorage.getItem('ws4.sidebar');
    if (saved) root.style.setProperty('--panel-width', saved);
  } catch { /* ignore */ }
  let drag = null;
  splitter.addEventListener('pointerdown', (event) => {
    drag = { x: event.clientX, width: sidebar.getBoundingClientRect().width };
    splitter.setPointerCapture(event.pointerId);
    splitter.classList.add('dragging');
  });
  splitter.addEventListener('pointermove', (event) => {
    if (!drag) return;
    const width = Math.max(220, Math.min(window.innerWidth * 0.6, drag.width + (event.clientX - drag.x)));
    root.style.setProperty('--panel-width', `${Math.round(width)}px`);
  });
  splitter.addEventListener('pointerup', () => {
    if (!drag) return;
    drag = null;
    splitter.classList.remove('dragging');
    try { window.localStorage.setItem('ws4.sidebar', root.style.getPropertyValue('--panel-width')); } catch { /* ignore */ }
    if (state.features.length) render();
  });
}

function renderMarkdown(text) {
  const escapes = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const escape = (value) => String(value).replace(/[&<>"']/g, (character) => escapes[character]);
  return String(text).split('```').map((piece, index) => {
    if (index % 2 === 1) {
      const body = piece.replace(/^[^\n]*\n/, '');
      return `<pre><code>${escape(body)}</code></pre>`;
    }
    return escape(piece)
      .replace(/`([^`\n]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/\n/g, '<br>');
  }).join('');
}

function appendChat(role, text) {
  const log = $('chat-log');
  const hint = log.querySelector('.hint');
  if (hint) hint.remove();
  const bubble = document.createElement('div');
  bubble.className = `chat-msg ${role}`;
  if (role === 'agent') bubble.innerHTML = renderMarkdown(text); else bubble.textContent = text;
  log.append(bubble);
  log.scrollTop = log.scrollHeight;
  return bubble;
}

async function sendChat(event) {
  if (event?.preventDefault) event.preventDefault();
  if (state.chatBusy) return;
  const input = $('chat-input');
  const message = input.value.trim();
  if (!message) return;
  state.chatBusy = true;
  $('chat-send').disabled = true;
  appendChat('user', message);
  input.value = '';
  const thinking = appendChat('agent', 'thinking…');
  thinking.classList.add('thinking');
  $('chat-status').textContent = '';
  try {
    const response = await fetch('api/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        message,
        session: state.chatSession || null,
        run: state.run || null,
        year: state.year,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `chat failed (${response.status})`);
    state.chatSession = payload.session || state.chatSession;
    thinking.classList.remove('thinking');
    thinking.innerHTML = renderMarkdown(payload.reply || '(no reply)');
    if (Array.isArray(payload.actions) && payload.actions.length) {
      const row = document.createElement('div');
      row.className = 'chat-actions';
      for (const action of payload.actions) {
        const chip = document.createElement('span');
        chip.className = 'chat-action';
        chip.textContent = `${action.tool}${action.summary ? `: ${action.summary}` : ''}`;
        chip.title = chip.textContent;
        row.append(chip);
      }
      thinking.append(row);
    }
  } catch (error) {
    thinking.classList.remove('thinking');
    thinking.classList.add('error');
    thinking.textContent = `chat unavailable: ${error.message}`;
  } finally {
    state.chatBusy = false;
    $('chat-send').disabled = false;
    input.focus();
    $('chat-log').scrollTop = $('chat-log').scrollHeight;
  }
}

function newChat() {
  state.chatSession = null;
  const log = $('chat-log');
  log.replaceChildren();
  const hint = document.createElement('p');
  hint.className = 'hint';
  hint.textContent = 'New conversation. The assistant can read the repository and run commands when the service allows it.';
  log.append(hint);
  $('chat-status').textContent = '';
  $('chat-input').focus();
}

async function loadAgent() {
  try {
    const info = await api('api/agent');
    const model = info.model ? String(info.model).split('/').pop() : 'agent';
    $('chat-model').textContent = info.enabled ? model : 'disabled';
    if (!info.enabled) {
      $('chat-input').disabled = true;
      $('chat-send').disabled = true;
      $('chat-status').textContent = 'restart with --allow-agent to enable the assistant';
    } else if (!info.available) {
      $('chat-status').textContent = 'opencode is not on the service PATH';
    }
  } catch {
    $('chat-model').textContent = 'unavailable';
  }
}

function wireControls() {
  wireSplitter();
  $('run').addEventListener('change', async (event) => {
    state.run = event.target.value;
    await loadSkins();
    await loadAgent();
    await loadPeriods();
    await loadTargets();
    await loadReports();
    await loadMap();
  });
  $('year').addEventListener('input', (event) => {
    state.yearChosen = true;
    state.year = Number(event.target.value);
    $('year-label').textContent = state.year;
  });
  $('year').addEventListener('change', () => { if (state.live.active) render(false); else loadMap(); });
  $('skin').addEventListener('change', async (event) => {
    const skins = await api('api/skins');
    const skin = skins.find((candidate) => candidate.id === event.target.value);
    if (skin) { applySkin(skin); await loadTargets(); }
  });
  $('save-targets').addEventListener('click', saveTargets);
  $('chat-form').addEventListener('submit', sendChat);
  $('chat-new').addEventListener('click', newChat);
  $('chat-input').addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      $('chat-form').requestSubmit();
    }
  });
  $('show-treated').addEventListener('change', applyVisibility);
  $('show-untreated').addEventListener('change', applyVisibility);
  for (const button of document.querySelectorAll('nav.tabs button')) {
    button.addEventListener('click', () => {
      for (const other of document.querySelectorAll('nav.tabs button')) other.classList.toggle('active', other === button);
      for (const name of ['legend', 'targets', 'reports']) $(`tab-${name}`).hidden = name !== button.dataset.tab;
    });
  }
  const svg = $('map');
  svg.addEventListener('click', (event) => {
    const target = event.target.closest('[data-block]');
    if (target) showDetail(target.dataset.block);
  });
  svg.addEventListener('wheel', (event) => {
    event.preventDefault();
    const rect = svg.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const factor = event.deltaY < 0 ? 1.2 : 1 / 1.2;
    const view = state.view;
    view.x = px - (px - view.x) * factor;
    view.y = py - (py - view.y) * factor;
    view.s = Math.min(Math.max(view.s * factor, 0.2), 80);
    applyView();
  }, { passive: false });
  let drag = null;
  svg.addEventListener('pointerdown', (event) => {
    drag = { x: event.clientX, y: event.clientY, vx: state.view.x, vy: state.view.y };
    svg.classList.add('dragging');
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener('pointermove', (event) => {
    if (!drag) return;
    state.view.x = drag.vx + (event.clientX - drag.x);
    state.view.y = drag.vy + (event.clientY - drag.y);
    applyView();
  });
  svg.addEventListener('pointerup', () => { drag = null; svg.classList.remove('dragging'); });
  window.addEventListener('resize', () => { if (state.features.length) render(); });
}

async function start() {
  if (!$('run-years') || !$('start-run') || !$('watch-panel')) {
    statusLine('this page is an older build — hard-reload (Ctrl-Shift-R) once');
    return;
  }
  wireControls();
  loadWatched();
  try {
    const summary = await api('api/summary');
    const select = $('run');
    for (const run of summary.runs ?? []) {
      const option = document.createElement('option');
      option.value = run.id;
      option.textContent = `${run.id} (${run.kind ?? 'run'})`;
      select.append(option);
    }
    const preferred = (summary.runs ?? []).find((run) => run.id === 'run-dated3') ?? (summary.runs ?? [])[0];
    if (!preferred) { statusLine('no runs found'); return; }
    select.value = preferred.id;
    state.run = preferred.id;
    await loadSkins();
    await loadAgent();
    await loadPeriods();
    await loadTargets();
    await loadReports();
    await loadMap();
  } catch (error) {
    statusLine(`service unavailable: ${error.message}`);
  }
}

start();
