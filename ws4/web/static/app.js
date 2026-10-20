// WS4 browser shell: reads the service's artefacts, no build step, relative URLs so it works
// under a proxy prefix as well as at the root.

const state = { run: null, year: 0, features: [], view: { s: 1, x: 0, y: 0 }, base: null };

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

function render() {
  const base = fit(state.features);
  if (!base) return;
  state.base = base;
  state.view = { s: 1, x: 0, y: 0 };
  applyView();
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
    const isTreated = Boolean(properties.treated);
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
  $('scale').textContent = `${base.scale.toFixed(4)} px/m · ${state.year}`;
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
  slider.min = body.min ?? 0;
  slider.max = body.max ?? 0;
  state.year = Number(slider.min);
  slider.value = state.year;
  $('year-label').textContent = state.year;
}

async function loadTargets() {
  try {
    const response = await fetch('api/targets');
    $('targets').textContent = response.ok ? await response.text() : 'no targets file is configured';
  } catch {
    $('targets').textContent = 'no targets file is configured';
  }
}

async function loadReports() {
  if (!state.run) return;
  const list = $('reports');
  list.replaceChildren();
  try {
    const body = await api(`api/runs/${encodeURIComponent(state.run)}/reports`);
    for (const report of body) {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = `api/runs/${encodeURIComponent(state.run)}/reports/${encodeURIComponent(report.name)}`;
      link.textContent = report.name;
      link.target = '_blank';
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

function wireControls() {
  $('run').addEventListener('change', async (event) => {
    state.run = event.target.value;
    await loadPeriods();
    await loadReports();
    await loadMap();
  });
  $('year').addEventListener('input', (event) => {
    state.year = Number(event.target.value);
    $('year-label').textContent = state.year;
  });
  $('year').addEventListener('change', () => loadMap());
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
  wireControls();
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
    await loadPeriods();
    await loadTargets();
    await loadReports();
    await loadMap();
  } catch (error) {
    statusLine(`service unavailable: ${error.message}`);
  }
}

start();
