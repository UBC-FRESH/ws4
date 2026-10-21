// WS4 browser shell: reads the service's artefacts, no build step, relative URLs so it works
// under a proxy prefix as well as at the root.

const state = { run: null, year: 0, features: [], view: { s: 1, x: 0, y: 0 }, base: null, skin: null, targets: [], targetCells: new Map(), watched: new Set(), windowValues: new Map(), series: new Map(), runPaused: false, live: { active: false, schedule: new Map(), total: 0 }, history: [], yearChosen: false, chatSession: null, chatBusy: false, compareView: false, compare: null, compareAccounts: [], compareToken: 0, compareInitialized: false, layers: null, layerMode: 'current', patchClasses: new Set(), patchCatalog: [], compartmentAccounts: [], compartmentClasses: [], compartmentAccount: '', selectedCompartments: new Set(), baseAttributes: [], baseAttribute: '', roads: [], showRoads: false, usedRoads: [], showUsedRoads: false, blockElements: new Map() };

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
  const transform = `translate(${state.view.x} ${state.view.y}) scale(${state.view.s})`;
  $('viewport').setAttribute('transform', transform);
  $('roads-layer').setAttribute('transform', transform);
}

function drawRoads(features, klass) {
  const layer = $('roads-layer');
  for (const feature of features) {
    const geometry = feature.geometry;
    const lines = geometry?.type === 'LineString'
      ? [geometry.coordinates]
      : geometry?.type === 'MultiLineString'
        ? geometry.coordinates
        : [];
    for (const line of lines) {
      const points = line.map(([x, y]) => {
        const [px, py] = state.base.project([x, y]);
        return `${px.toFixed(1)},${py.toFixed(1)}`;
      }).join(' ');
      const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      polyline.setAttribute('points', points);
      polyline.setAttribute('class', klass);
      layer.append(polyline);
    }
  }
}

function renderRoads() {
  const layer = $('roads-layer');
  layer.replaceChildren();
  if (!state.base) return;
  if (state.showRoads && state.roads.length) drawRoads(state.roads, 'road');
  if (state.showUsedRoads && state.usedRoads.length) drawRoads(state.usedRoads, 'road used');
}

async function loadUsedRoads() {
  if (!state.layers?.used_roads) {
    state.usedRoads = [];
    renderRoads();
    return;
  }
  try {
    const body = await api(`api/runs/${encodeURIComponent(state.run)}/used-roads?year=${state.year}`);
    state.usedRoads = body.features ?? [];
    renderRoads();
  } catch (error) {
    state.usedRoads = [];
    state.showUsedRoads = false;
    renderRoads();
    renderLayerTree();
    $('layers-hint').textContent = `used roads unavailable: ${error.message}`;
  }
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
  state.blockElements = new Map();
  const groups = { treated: document.createElementNS('http://www.w3.org/2000/svg', 'g'),
                   untreated: document.createElementNS('http://www.w3.org/2000/svg', 'g') };
  let treated = 0, untreated = 0;
  const circles = [];
  const paths = [];
  for (const feature of state.features) {
    const geometry = feature.geometry;
    const properties = feature.properties ?? {};
    let isTreated;
    let klass;
    let fill = null;
    if (state.compareView && state.compare) {
      const flags = state.compare.blocks.get(String(properties.block_id)) ?? {};
      const inA = Boolean(flags.a);
      const inB = Boolean(flags.b);
      isTreated = inA || inB;
      klass = inA && inB
        ? 'compare-both treated'
        : inA
          ? 'compare-a treated'
          : inB
            ? 'compare-b treated'
            : 'untreated';
    } else if (state.layerMode === 'patches' && state.layers?.patches) {
      const patchClass = properties.patch_class;
      isTreated = Boolean(properties.treated) && state.patchClasses.has(patchClass);
      klass = isTreated ? 'patch-block treated' : 'untreated';
      if (isTreated) fill = patchColor(patchClass);
    } else if (state.layerMode === 'cumulative' && state.layers?.cumulative) {
      isTreated = Boolean(properties.treated);
      klass = isTreated
        ? (properties.current ? 'current treated' : 'past treated')
        : 'untreated';
      if (isTreated && !properties.current) fill = 'url(#earlier-hatch)';
    } else if (state.layerMode === 'compartments' && state.layers?.compartments) {
      if (properties.treated) {
        isTreated = true;
        klass = 'current treated';
      } else {
        const compartmentClass = properties.compartment_class;
        isTreated = Boolean(compartmentClass) && state.selectedCompartments.has(compartmentClass);
        klass = isTreated ? 'compartment treated' : 'untreated';
        if (isTreated) fill = compartmentColor(compartmentClass);
      }
    } else if (state.layerMode === 'base' && state.baseAttribute) {
      isTreated = false;
      klass = 'base untreated';
      fill = baseColor(state.baseAttribute, properties[state.baseAttribute]);
    } else {
      isTreated = Boolean(properties.treated);
      if (state.live.active) {
        const chain = state.live.schedule.get(String(properties.block_id));
        isTreated = chain
          ? chain.some((event) => Number(event[1]) === Number(state.year))
          : false;
      }
      klass = isTreated ? 'treated' : 'untreated';
    }
    const group = groups[isTreated ? 'treated' : 'untreated'];
    if (geometry?.type === 'Point') {
      const [cx, cy] = base.project(geometry.coordinates);
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', cx.toFixed(1));
      circle.setAttribute('cy', cy.toFixed(1));
      circle.setAttribute('r', '2.2');
      circle.setAttribute('class', `block ${klass}`);
      if (fill) circle.style.fill = fill;
      circle.dataset.block = properties.block_id;
      state.blockElements.set(String(properties.block_id), circle);
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
      path.setAttribute('fill-rule', 'evenodd');
      path.setAttribute('class', `block ${klass}`);
      if (fill) path.style.fill = fill;
      path.dataset.block = properties.block_id;
      state.blockElements.set(String(properties.block_id), path);
      paths.push(path);
      group.append(path);
    }
    if (isTreated) treated += 1; else untreated += 1;
  }
  viewport.append(groups.untreated, groups.treated);
  $('n-treated').textContent = treated.toLocaleString();
  $('n-untreated').textContent = untreated.toLocaleString();
  const baseMode = state.layerMode === 'base' && Boolean(state.baseAttribute);
  $('treated-label').textContent = layerLabel();
  const skinHasTreatments = state.skin?.layers ? state.skin.layers.includes('treatments') : true;
  $('treated-label').closest('label').hidden = baseMode || !skinHasTreatments;
  $('untreated-label').textContent = baseMode ? 'Blocks' : 'Untreated';
  $('scale').textContent = `year ${state.year} · 1 px ≈ ${Math.round(1 / base.scale)} m`;
  applyVisibility();
  if (refit) renderRoads();
}

function applyVisibility() {
  const showTreated = $('show-treated').checked;
  const showUntreated = $('show-untreated').checked;
  for (const element of document.querySelectorAll('#viewport .treated')) element.style.display = showTreated ? '' : 'none';
  for (const element of document.querySelectorAll('#viewport .untreated')) element.style.display = showUntreated ? '' : 'none';
}

function resetLiveMap() {
  if (!state.blockElements.size) return;
  for (const element of state.blockElements.values()) {
    element.setAttribute('class', 'block untreated');
    element.style.fill = '';
  }
  $('n-treated').textContent = '0';
  $('n-untreated').textContent = state.features.length.toLocaleString();
  applyVisibility();
}

function updateLiveBlocks(blocks) {
  if (!state.live.active || state.layerMode !== 'current' || !state.blockElements.size) return;
  for (const block of blocks) {
    const element = state.blockElements.get(String(block));
    if (!element) continue;
    const chain = state.live.schedule.get(String(block));
    const treated = chain
      ? chain.some((event) => Number(event[1]) === Number(state.year))
      : false;
    element.setAttribute('class', `block ${treated ? 'treated' : 'untreated'}`);
  }
  let treated = 0;
  for (const feature of state.features) {
    const chain = state.live.schedule.get(String(feature.properties?.block_id));
    if (chain?.some((event) => Number(event[1]) === Number(state.year))) treated += 1;
  }
  $('n-treated').textContent = treated.toLocaleString();
  $('n-untreated').textContent = (state.features.length - treated).toLocaleString();
  applyVisibility();
}

async function loadMap() {
  if (!state.run) return;
  statusLine('loading map…');
  const layer = state.layerMode === 'patches' && state.layers?.patches
    ? 'patches'
    : state.layerMode === 'cumulative' && state.layers?.cumulative
      ? 'cumulative'
      : state.layerMode === 'compartments' && state.layers?.compartments
        ? 'compartments'
        : state.layerMode === 'base' || (state.layers && !state.layers.treatments)
          ? 'blocks'
          : 'treatments';
  try {
    let query = `api/runs/${encodeURIComponent(state.run)}/map?year=${state.year}&layer=${layer}`;
    if (layer === 'compartments') {
      query += `&account=${encodeURIComponent(state.compartmentAccount)}`;
    }
    const body = await api(query);
    state.features = body.features ?? [];
    render();
    statusLine(`${state.features.length.toLocaleString()} blocks · ${layer} · year ${state.year}`);
    if (state.showUsedRoads) loadUsedRoads();
  } catch (error) {
    statusLine(`map unavailable: ${error.message}`);
  }
}

function compareNumber(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function accountTotals(rows) {
  const totals = new Map();
  for (const row of rows) {
    const name = String(row.account);
    totals.set(name, (totals.get(name) ?? 0) + Number(row.value));
  }
  return totals;
}

function syncCompareRuns() {
  const options = [...$('run').options].map((option) => ({ value: option.value, label: option.textContent }));
  if (!options.length) return;
  for (const id of ['compare-a', 'compare-b']) {
    const select = $(id);
    const current = select.value;
    select.replaceChildren();
    for (const option of options) {
      const element = document.createElement('option');
      element.value = option.value;
      element.textContent = option.label;
      select.append(element);
    }
    if (options.some((option) => option.value === current)) select.value = current;
  }
  const a = $('compare-a');
  const b = $('compare-b');
  if (!state.compareInitialized) {
    a.value = options.some((option) => option.value === state.run) ? state.run : options[0].value;
    const candidates = options.filter((option) => option.value !== a.value);
    const web = candidates.filter((option) => option.value.startsWith('web-'));
    const preferredB = web[web.length - 1]
      ?? candidates[candidates.length - 1]
      ?? options[0];
    b.value = preferredB ? preferredB.value : a.value;
    state.compareInitialized = true;
    return;
  }
  if (!options.some((option) => option.value === a.value)) {
    a.value = options.some((option) => option.value === state.run) ? state.run : options[0].value;
  }
  if (!options.some((option) => option.value === b.value) || b.value === a.value) {
    const other = options.find((option) => option.value !== a.value);
    b.value = other ? other.value : a.value;
  }
}

function clearCompareView() {
  if (!state.compareView) return;
  state.compareView = false;
  state.compare = null;
  $('treated-label').textContent = layerLabel();
  if (state.features.length) {
    if (state.live.active) render(false); else loadMap();
  }
}

function renderCompareTargets(rowsA, rowsB) {
  const table = $('compare-targets');
  const empty = $('compare-targets-empty');
  const body = table.querySelector('tbody');
  body.replaceChildren();
  const keyOf = (row) => `${row.account}|${row.year}`;
  const byB = new Map(rowsB.map((row) => [keyOf(row), row]));
  const byConfig = new Map(state.targets.map((row) => [keyOf(row), row]));
  const keys = [...new Set([...rowsA.map(keyOf), ...rowsB.map(keyOf)])].sort();
  if (!keys.length) {
    table.hidden = true;
    empty.hidden = false;
    empty.textContent = 'no targets configured';
    return;
  }
  empty.hidden = true;
  table.hidden = false;
  for (const key of keys) {
    const a = rowsA.find((row) => keyOf(row) === key);
    const b = byB.get(key);
    const config = byConfig.get(key);
    const tr = document.createElement('tr');
    const account = document.createElement('td');
    account.className = 'account';
    account.textContent = a?.account ?? b?.account ?? '';
    account.title = account.textContent;
    tr.append(account);
    const year = document.createElement('td');
    year.className = 'num';
    year.textContent = String(a?.year ?? b?.year ?? '');
    tr.append(year);
    for (const bound of [config?.minimum, config?.maximum]) {
      const td = document.createElement('td');
      td.className = 'num';
      td.textContent = bound === null || bound === undefined ? '—' : compareNumber(bound);
      tr.append(td);
    }
    for (const row of [a, b]) {
      const td = document.createElement('td');
      td.className = `num ${row?.status ?? ''}`;
      td.textContent = row ? `${compareNumber(row.value)} · ${row.status}` : '—';
      tr.append(td);
    }
    const delta = document.createElement('td');
    delta.className = 'num';
    const value = (b?.value ?? 0) - (a?.value ?? 0);
    delta.textContent = `${value > 0 ? '+' : ''}${compareNumber(value)}`;
    if (value > 0) delta.classList.add('compare-delta-positive');
    if (value < 0) delta.classList.add('compare-delta-negative');
    tr.append(delta);
    body.append(tr);
  }
}

function renderCompareAccounts() {
  const table = $('compare-accounts');
  const empty = $('compare-accounts-empty');
  const body = table.querySelector('tbody');
  body.replaceChildren();
  const query = $('compare-filter').value.trim().toLowerCase();
  const rows = state.compareAccounts
    .filter((row) => row.name.toLowerCase().includes(query))
    .slice(0, 200);
  if (!rows.length) {
    table.hidden = true;
    empty.hidden = false;
    empty.textContent = state.compareAccounts.length
      ? 'no accounts match the filter'
      : 'no account values at this year';
    return;
  }
  empty.hidden = true;
  table.hidden = false;
  for (const row of rows) {
    const tr = document.createElement('tr');
    const account = document.createElement('td');
    account.className = 'account';
    account.textContent = row.name;
    account.title = row.name;
    tr.append(account);
    for (const value of [row.a, row.b]) {
      const td = document.createElement('td');
      td.className = 'num';
      td.textContent = compareNumber(value);
      tr.append(td);
    }
    const delta = document.createElement('td');
    delta.className = 'num';
    delta.textContent = `${row.delta > 0 ? '+' : ''}${compareNumber(row.delta)}`;
    if (row.delta > 0) delta.classList.add('compare-delta-positive');
    if (row.delta < 0) delta.classList.add('compare-delta-negative');
    tr.append(delta);
    body.append(tr);
  }
}

async function loadComparison() {
  const runA = $('compare-a').value;
  const runB = $('compare-b').value;
  if (!runA || !runB) {
    $('compare-summary').textContent = 'choose two runs';
    return;
  }
  const token = ++state.compareToken;
  state.compareView = true;
  $('compare-summary').textContent = 'loading…';
  try {
    const [mapA, mapB, accountsA, accountsB, targetsA, targetsB] = await Promise.all([
      api(`api/runs/${encodeURIComponent(runA)}/map?year=${state.year}`),
      api(`api/runs/${encodeURIComponent(runB)}/map?year=${state.year}`),
      api(`api/runs/${encodeURIComponent(runA)}/accounts?year=${state.year}`),
      api(`api/runs/${encodeURIComponent(runB)}/accounts?year=${state.year}`),
      api(`api/runs/${encodeURIComponent(runA)}/targets`),
      api(`api/runs/${encodeURIComponent(runB)}/targets`),
    ]);
    if (token !== state.compareToken) return;
    state.features = mapA.features ?? [];
    const blocks = new Map();
    for (const feature of mapA.features ?? []) {
      const block = String(feature.properties?.block_id);
      blocks.set(block, { a: Boolean(feature.properties?.treated), b: false });
    }
    for (const feature of mapB.features ?? []) {
      const block = String(feature.properties?.block_id);
      const flags = blocks.get(block) ?? { a: false, b: false };
      flags.b = Boolean(feature.properties?.treated);
      blocks.set(block, flags);
    }
    let aOnly = 0, bOnly = 0, both = 0, neither = 0;
    for (const flags of blocks.values()) {
      if (flags.a && flags.b) both += 1;
      else if (flags.a) aOnly += 1;
      else if (flags.b) bOnly += 1;
      else neither += 1;
    }
    state.compare = { a: runA, b: runB, blocks };
    render(true);
    $('compare-summary').textContent =
      `year ${state.year} · A only ${aOnly.toLocaleString()} · B only ${bOnly.toLocaleString()} · both ${both.toLocaleString()} · neither ${neither.toLocaleString()}`
      + (accountsB.length ? '' : ' · B has no account values at this year');
    $('compare-year').textContent = state.year;
    renderCompareTargets(targetsA, targetsB);
    const totalsA = accountTotals(accountsA);
    const totalsB = accountTotals(accountsB);
    const names = new Set([...totalsA.keys(), ...totalsB.keys()]);
    state.compareAccounts = [...names]
      .map((name) => {
        const a = totalsA.get(name) ?? 0;
        const b = totalsB.get(name) ?? 0;
        return { name, a, b, delta: b - a };
      })
      .filter((row) => row.a !== 0 || row.b !== 0)
      .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta)
        || left.name.localeCompare(right.name));
    renderCompareAccounts();
    statusLine(`${state.features.length.toLocaleString()} blocks · ${runA} vs ${runB} · year ${state.year}`);
  } catch (error) {
    if (token !== state.compareToken) return;
    state.compareView = false;
    state.compare = null;
    $('compare-summary').textContent = `comparison unavailable: ${error.message}`;
    $('compare-targets').hidden = true;
    $('compare-accounts').hidden = true;
    $('treated-label').textContent = layerLabel();
  }
}

const PATCH_COLORS = { '0_10': '#f2c14e', '10_50': '#f78154', '50_150': '#9b5de5', '150_9999999': '#3a86ff' };
const PATCH_FALLBACK = ['#f2c14e', '#f78154', '#9b5de5', '#3a86ff', '#00bbf9', '#00f5d4'];

function patchColor(klass) {
  if (PATCH_COLORS[klass]) return PATCH_COLORS[klass];
  const index = Math.max(0, state.patchCatalog.indexOf(klass));
  return PATCH_FALLBACK[index % PATCH_FALLBACK.length];
}

function patchLabel(klass) {
  const labels = { '0_10': '0–10 ha', '10_50': '10–50 ha', '50_150': '50–150 ha', '150_9999999': '150+ ha' };
  return labels[klass] ?? String(klass).replaceAll('_', '–');
}

function baseAttributeInfo(name) {
  return state.baseAttributes.find((attribute) => attribute.name === name);
}

function baseColor(name, value) {
  const info = baseAttributeInfo(name);
  if (!info) return '#d9d9d9';
  const index = info.values.indexOf(String(value));
  if (index < 0) return '#d9d9d9';
  return `hsl(${Math.round((index * 137.508) % 360)} 55% 62%)`;
}

const COMPARTMENT_COLORS = {
  '0_10': '#8dd3c7',
  '10_50': '#80b1d3',
  '50_150': '#bc80bd',
  '150_9999999': '#fb8072',
};

function compartmentColor(klass) {
  return COMPARTMENT_COLORS[klass] ?? '#d9d9d9';
}

function compartmentLabel(klass) {
  const labels = { '0_10': '0–10 ha', '10_50': '10–50 ha', '50_150': '50–150 ha', '150_9999999': '150+ ha' };
  return labels[klass] ?? String(klass).replaceAll('_', '–');
}

function layerLabel() {
  if (state.layerMode === 'compartments') return 'Spread compartments';
  if (state.layerMode === 'base' && state.baseAttribute) {
    const info = baseAttributeInfo(state.baseAttribute);
    return `Base: ${info?.label ?? state.baseAttribute}`;
  }
  if (state.compareView && state.compare) return 'Treated in A or B';
  if (state.layerMode === 'cumulative') return 'Treated through the year';
  if (state.layerMode === 'patches') return 'Patches in the year';
  return 'Treated in the year';
}

function renderLayerTree() {
  const tree = $('layer-tree');
  if (!tree) return;
  tree.replaceChildren();
  const info = state.layers;
  if (!info) return;
  const layers = state.skin?.layers ?? ['blocks', 'treatments', 'patches', 'roads'];
  const group = (title) => {
    const box = document.createElement('div');
    box.className = 'layer-group';
    const heading = document.createElement('div');
    heading.className = 'layer-group-title';
    heading.textContent = title;
    box.append(heading);
    tree.append(box);
    return box;
  };
  const modeGroup = group('Colour by');
  const addMode = (value, label, enabled) => {
    const wrapper = document.createElement('label');
    wrapper.className = `layer-option${enabled ? '' : ' disabled'}`;
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'layer-mode';
    input.value = value;
    input.checked = state.layerMode === value;
    input.disabled = !enabled;
    input.addEventListener('change', () => {
      state.layerMode = value;
      state.baseAttribute = '';
      renderLayerTree();
      loadMap();
    });
    const text = document.createElement('span');
    text.textContent = label;
    wrapper.append(input, text);
    modeGroup.append(wrapper);
  };
  addMode('current', 'Current treatment', Boolean(info.treatments) && layers.includes('treatments'));
  addMode('cumulative', 'Cumulative through year', Boolean(info.cumulative) && layers.includes('treatments'));
  addMode('patches', 'Patch size class', Boolean(info.patches) && layers.includes('patches'));
  addMode('compartments', 'Spread compartments', Boolean(info.compartments) && layers.includes('compartments'));
  if (info.cumulative && layers.includes('treatments') && state.layerMode === 'cumulative') {
    const legend = document.createElement('div');
    legend.className = 'layer-legend';
    const current = document.createElement('span');
    current.className = 'layer-swatch current';
    const past = document.createElement('span');
    past.className = 'layer-swatch past';
    legend.append(current, document.createTextNode(' current · '), past, document.createTextNode(' earlier'));
    modeGroup.append(legend);
  }
  if (info.patches && layers.includes('patches') && state.patchCatalog.length) {
    const patchGroup = group('Patch size classes');
    for (const klass of state.patchCatalog) {
      const wrapper = document.createElement('label');
      wrapper.className = 'layer-option';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = state.patchClasses.has(klass);
      input.addEventListener('change', () => {
        if (input.checked) state.patchClasses.add(klass); else state.patchClasses.delete(klass);
        render(false);
      });
      const swatch = document.createElement('span');
      swatch.className = 'layer-swatch';
      swatch.style.background = patchColor(klass);
      const text = document.createElement('span');
      text.textContent = patchLabel(klass);
      wrapper.append(input, swatch, text);
      patchGroup.append(wrapper);
    }
  }
  if (state.baseAttributes.length && layers.includes('blocks')) {
    const baseGroup = group('Base colour');
    const wrapper = document.createElement('label');
    wrapper.className = 'layer-option';
    const select = document.createElement('select');
    select.id = 'base-attribute';
    const none = document.createElement('option');
    none.value = '';
    none.textContent = 'Off';
    select.append(none);
    for (const attribute of state.baseAttributes) {
      const option = document.createElement('option');
      option.value = attribute.name;
      option.textContent = attribute.label;
      select.append(option);
    }
    select.value = state.layerMode === 'base' ? state.baseAttribute : '';
    select.addEventListener('change', () => {
      if (select.value) {
        state.baseAttribute = select.value;
        state.layerMode = 'base';
      } else {
        state.baseAttribute = '';
        state.layerMode = info.treatments
          ? 'current'
          : info.patches
            ? 'patches'
            : info.compartments
              ? 'compartments'
              : 'current';
      }
      renderLayerTree();
      loadMap();
    });
    wrapper.append(select);
    baseGroup.append(wrapper);
    if (state.layerMode === 'base' && state.baseAttribute) {
      const attribute = baseAttributeInfo(state.baseAttribute);
      if (attribute) {
        const legend = document.createElement('div');
        legend.className = 'base-legend';
        for (const value of attribute.values) {
          const row = document.createElement('div');
          row.className = 'base-legend-row';
          const swatch = document.createElement('span');
          swatch.className = 'base-swatch';
          swatch.style.background = baseColor(attribute.name, value);
          const text = document.createElement('span');
          text.textContent = String(value);
          row.append(swatch, text);
          legend.append(row);
        }
        baseGroup.append(legend);
      }
    }
  }
  if (info.roads || info.used_roads) {
    const overlay = group('Overlays');
    if (info.roads) {
      const wrapper = document.createElement('label');
      wrapper.className = 'layer-option';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.id = 'show-roads';
      input.checked = state.showRoads;
      input.addEventListener('change', async () => {
        state.showRoads = input.checked;
        if (state.showRoads && !state.roads.length) {
          try {
            const body = await api('api/roads');
            state.roads = body.features ?? [];
          } catch (error) {
            $('layers-hint').textContent = `roads unavailable: ${error.message}`;
            state.showRoads = false;
            input.checked = false;
          }
        }
        renderRoads();
      });
      const text = document.createElement('span');
      text.textContent = 'Access roads (source)';
      wrapper.append(input, text);
      overlay.append(wrapper);
    }
    if (info.used_roads) {
      const usedWrapper = document.createElement('label');
      usedWrapper.className = 'layer-option';
      const usedInput = document.createElement('input');
      usedInput.type = 'checkbox';
      usedInput.id = 'show-used-roads';
      usedInput.checked = state.showUsedRoads;
      usedInput.addEventListener('change', () => {
        state.showUsedRoads = usedInput.checked;
        if (state.showUsedRoads) loadUsedRoads();
        else renderRoads();
      });
      const usedText = document.createElement('span');
      usedText.textContent = 'Used roads (run)';
      usedWrapper.append(usedInput, usedText);
      overlay.append(usedWrapper);
    }
  }
  if (info.compartments && layers.includes('compartments')) {
    const compartmentGroup = group('Spread compartments');
    if (state.compartmentAccounts.length > 1) {
      const wrapper = document.createElement('label');
      wrapper.className = 'layer-option';
      const select = document.createElement('select');
      for (const account of state.compartmentAccounts) {
        const option = document.createElement('option');
        option.value = account;
        option.textContent = account;
        select.append(option);
      }
      select.value = state.compartmentAccount;
      select.addEventListener('change', () => {
        state.compartmentAccount = select.value;
        loadMap();
      });
      wrapper.append(select);
      compartmentGroup.append(wrapper);
    }
    for (const klass of state.compartmentClasses) {
      const wrapper = document.createElement('label');
      wrapper.className = 'layer-option';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = state.selectedCompartments.has(klass);
      input.addEventListener('change', () => {
        if (input.checked) state.selectedCompartments.add(klass);
        else state.selectedCompartments.delete(klass);
        render(false);
      });
      const swatch = document.createElement('span');
      swatch.className = 'layer-swatch';
      swatch.style.background = compartmentColor(klass);
      const text = document.createElement('span');
      text.textContent = compartmentLabel(klass);
      wrapper.append(input, swatch, text);
      compartmentGroup.append(wrapper);
    }
  }
  if (!info.roads || !info.compartments || !info.used_roads) {
    const unavailable = group('Not written by this run');
    for (const [label, available, reason] of [
      ['Used roads (run)', info.used_roads, info.used_roads_reason],
      ['Spread compartments', info.compartments, info.compartments_reason],
    ]) {
      if (available) continue;
      const wrapper = document.createElement('label');
      wrapper.className = 'layer-option disabled';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.disabled = true;
      const text = document.createElement('span');
      text.textContent = label;
      const why = document.createElement('span');
      why.className = 'hint';
      why.textContent = reason ?? 'unavailable';
      wrapper.append(input, text, why);
      unavailable.append(wrapper);
    }
  }
  if (!info.treatments && !info.patches) {
    const note = document.createElement('p');
    note.className = 'hint';
    note.textContent = 'only the block geometry is available';
    tree.append(note);
  }
}

async function loadLayers() {
  const hint = $('layers-hint');
  try {
    const info = await api(`api/runs/${encodeURIComponent(state.run)}/layers`);
    state.layers = info;
    state.patchCatalog = [...(info.patch_classes ?? [])].sort(
      (left, right) => parseInt(left, 10) - parseInt(right, 10),
    );
    state.patchClasses = new Set(state.patchCatalog);
    state.compartmentAccounts = info.compartment_accounts ?? [];
    state.compartmentClasses = [...(info.compartment_classes ?? [])].sort(
      (left, right) => parseInt(left, 10) - parseInt(right, 10),
    );
    state.selectedCompartments = new Set(state.compartmentClasses);
    if (!state.compartmentAccounts.includes(state.compartmentAccount)) {
      state.compartmentAccount = state.compartmentAccounts[0] ?? '';
    }
    state.baseAttributes = info.base_attributes ?? [];
    if (!info.roads) {
      state.showRoads = false;
      state.roads = [];
      renderRoads();
    }
    if (!info.used_roads) {
      state.showUsedRoads = false;
      state.usedRoads = [];
      renderRoads();
    }
    if (!state.baseAttributes.some((attribute) => attribute.name === state.baseAttribute)) {
      state.baseAttribute = '';
    }
    const fallback = info.treatments
      ? 'current'
      : info.patches
        ? 'patches'
        : info.compartments
          ? 'compartments'
          : state.baseAttributes.length
            ? 'base'
            : 'current';
    if (state.layerMode === 'patches' && !info.patches) state.layerMode = fallback;
    if (state.layerMode === 'cumulative' && !info.cumulative) state.layerMode = fallback;
    if (state.layerMode === 'current' && !info.treatments) state.layerMode = fallback;
    if (state.layerMode === 'compartments' && !info.compartments) state.layerMode = fallback;
    if (state.layerMode === 'base') {
      if (!state.baseAttribute) state.baseAttribute = state.baseAttributes[0]?.name ?? '';
      if (!state.baseAttribute) state.layerMode = fallback;
    }
    renderLayerTree();
    const available = [];
    if (info.treatments) available.push('treatments');
    if (info.patches) available.push('patches');
    if (info.compartments) available.push('compartments');
    if (info.used_roads) available.push('used roads');
    hint.textContent = available.length
      ? `available: ${available.join(', ')}`
      : 'this run has no treatment, patch or compartment artifact';
  } catch (error) {
    state.layers = null;
    state.patchCatalog = [];
    state.patchClasses = new Set();
    renderLayerTree();
    hint.textContent = `layers unavailable: ${error.message}`;
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
  const panels = new Set(skin.panels ?? ['legend', 'targets', 'reports', 'comparison']);
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
  renderLayerTree();
}

async function loadSkins() {
  try {
    const skins = await api('api/skins');
    const select = $('skin');
    const current = select.value;
    // reloading on a run change must not append a second set of options or reset the choice
    select.replaceChildren();
    for (const skin of skins) {
      const option = document.createElement('option');
      option.value = skin.id;
      option.textContent = skin.title;
      select.append(option);
    }
    const preferred = skins.find((skin) => skin.id === current)
      ?? skins.find((skin) => skin.id === 'scenario-analyst')
      ?? skins[0];
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
  if (row.active === false) return 'off';
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
  if (row.active === false) {
    entry.text.textContent = 'off';
    if (entry.band) entry.band.style.display = 'none';
    if (entry.marker) entry.marker.style.display = 'none';
    return;
  }
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

function updateLiveTargets(values, iteration, series = []) {
  const liveSeries = new Map();
  for (const item of series) {
    const account = String(item.account);
    if (!liveSeries.has(account)) liveSeries.set(account, new Map());
    liveSeries.get(account).set(Number(item.year), Number(item.value));
  }
  for (const [account, years] of liveSeries) state.series.set(account, years);
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
    rows.forEach((row) => { row.active = row.active !== false; });
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
      tr.classList.toggle('inactive', row.active === false);
      const key = `${row.year}|${row.account}`;
      const on = document.createElement('td');
      const onBox = document.createElement('input');
      onBox.type = 'checkbox';
      onBox.checked = row.active !== false;
      onBox.title = 'price this target';
      onBox.addEventListener('change', () => {
        row.active = onBox.checked;
        tr.classList.toggle('inactive', !row.active);
        const entry = state.targetCells.get(key);
        if (entry) paintTarget(entry, entry.value);
        renderWatchPanel();
      });
      on.append(onBox);
      tr.append(on);
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
  syncCompareRuns();
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
      await loadPeriods(); await loadLayers(); await loadTargets(); await loadReports(); await loadMap();
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
  // a live search always has a schedule; the map must follow it, not a previous patch/cumulative view
  state.layerMode = 'current';
  renderLayerTree();
  resetLiveMap();
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
      updateLiveBlocks((payload.changed ?? []).map(([block]) => block));
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
      updateLiveTargets(payload.values ?? [], payload.iteration, payload.series ?? []);
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
  $('report-export').hidden = true;
  const url = `api/runs/${encodeURIComponent(state.run)}/reports/${encodeURIComponent(name)}`;
  if (!name.toLowerCase().endsWith('.csv')) {
    // the report name comes from the filesystem; never interpolate it into markup
    const link = document.createElement('a');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = `open ${name}`;
    preview.replaceChildren(link);
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

const STANDARD_REPORTS = [
  ['report_accounts.csv', 'Account summary'],
  ['report_targets.csv', 'Target status'],
  ['route_cost_report.csv', 'Route cost'],
  ['patch_accounts.csv', 'Patch accounts'],
  ['patch_metrics.csv', 'Patch metrics'],
  ['spread_metrics.csv', 'Spread metrics'],
  ['edge_metrics.csv', 'Edge contrast'],
  ['network_table.csv', 'Road network'],
  ['schedule.csv', 'Schedule'],
  ['account_values.csv', 'Account values'],
  ['product_values.csv', 'Product values'],
];

function csvCell(value) {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

async function loadReports() {
  if (!state.run) return;
  const list = $('reports');
  const standard = $('standard-reports');
  const empty = $('standard-reports-empty');
  list.replaceChildren();
  standard.replaceChildren();
  $('report-preview').replaceChildren();
  $('report-export').hidden = true;
  $('report-build-status').textContent = '';
  try {
    const body = await api(`api/runs/${encodeURIComponent(state.run)}/reports`);
    const byName = new Map(body.map((report) => [report.name, report]));
    const definitions = [...STANDARD_REPORTS];
    for (const report of body) {
      if (report.name.startsWith('route_cost_report.destination.')) {
        const suffix = report.name.slice('route_cost_report.destination.'.length, -4);
        definitions.push([report.name, `Route cost · ${suffix}`]);
      }
    }
    let shown = 0;
    for (const [name, label] of definitions) {
      if (!byName.has(name)) continue;
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = `api/runs/${encodeURIComponent(state.run)}/reports/${encodeURIComponent(name)}`;
      link.textContent = label;
      link.title = name;
      link.addEventListener('click', (event) => { event.preventDefault(); showReport(name); });
      item.append(link);
      standard.append(item);
      shown += 1;
    }
    empty.hidden = shown > 0;
    for (const report of body) {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = `api/runs/${encodeURIComponent(state.run)}/reports/${encodeURIComponent(report.name)}`;
      link.textContent = report.name;
      link.addEventListener('click', (event) => { event.preventDefault(); showReport(report.name); });
      item.append(link);
      list.append(item);
    }
    const slider = $('year');
    $('report-from').value = slider.min || 0;
    $('report-to').value = slider.max || 0;
    const accounts = await api(`api/runs/${encodeURIComponent(state.run)}/accounts`);
    const names = [...new Set(accounts.map((row) => String(row.account)))].sort();
    const datalist = $('account-names');
    datalist.replaceChildren();
    for (const name of names) {
      const option = document.createElement('option');
      option.value = name;
      datalist.append(option);
    }
  } catch (error) {
    list.textContent = `reports unavailable: ${error.message}`;
  }
}

async function buildReport() {
  const status = $('report-build-status');
  const exportLink = $('report-export');
  const preview = $('report-preview');
  status.textContent = 'building…';
  exportLink.hidden = true;
  try {
    const rows = await api(`api/runs/${encodeURIComponent(state.run)}/accounts`);
    const wanted = $('report-accounts').value
      .split(',')
      .map((name) => name.trim())
      .filter(Boolean);
    const from = $('report-from').value === '' ? -Infinity : Number($('report-from').value);
    const to = $('report-to').value === '' ? Infinity : Number($('report-to').value);
    const filtered = rows.filter((row) => {
      const account = String(row.account);
      const matches = wanted.length === 0
        || wanted.some((name) => account === name || account.startsWith(`${name}.`));
      const year = Number(row.year);
      return matches && year >= from && year <= to;
    });
    if (!filtered.length) {
      preview.textContent = 'no matching account values';
      status.textContent = '';
      return;
    }
    const table = [
      ['year', 'account', 'value'],
      ...filtered.map((row) => [row.year, row.account, row.value]),
    ];
    renderReport(table);
    const csv = table.map((row) => row.map(csvCell).join(',')).join('\n');
    if (exportLink.href.startsWith('blob:')) URL.revokeObjectURL(exportLink.href);
    exportLink.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    exportLink.download = `${state.run}-report.csv`;
    exportLink.hidden = false;
    status.textContent = `${filtered.length.toLocaleString()} rows`;
  } catch (error) {
    preview.textContent = `report unavailable: ${error.message}`;
    status.textContent = '';
  }
}

function showDetail(block) {
  const feature = state.features.find((candidate) => String(candidate.properties?.block_id) === String(block));
  if (!feature) return;
  const properties = feature.properties ?? {};
  if (state.compareView && state.compare) {
    const flags = state.compare.blocks.get(String(block)) ?? { a: false, b: false };
    $('detail').innerHTML = `<b>Block ${properties.block_id}</b><br>` +
      `A: ${flags.a ? 'treated' : '—'} · B: ${flags.b ? 'treated' : '—'}<br>` +
      `A only: ${flags.a && !flags.b ? 'yes' : 'no'} · B only: ${flags.b && !flags.a ? 'yes' : 'no'}`;
  } else if (state.layerMode === 'patches' && state.layers?.patches) {
    $('detail').innerHTML = `<b>Block ${properties.block_id}</b><br>` +
      `patch: ${properties.patch ?? '—'} · class: ${properties.patch_class ?? '—'}<br>` +
      `area: ${properties.patch_area_ha === null || properties.patch_area_ha === undefined ? '—' : Number(properties.patch_area_ha).toLocaleString()} ha` +
      ` · account: ${properties.patch_account ?? '—'}`;
  } else if (state.layerMode === 'cumulative' && state.layers?.cumulative) {
    $('detail').innerHTML = `<b>Block ${properties.block_id}</b><br>` +
      `current: ${properties.current ? 'yes' : 'no'} · earlier: ${properties.treated && !properties.current ? 'yes' : 'no'}<br>` +
      `treatments to date: ${(properties.treatments ?? []).join(', ') || '—'}`;
  } else if (state.layerMode === 'compartments' && state.layers?.compartments) {
    $('detail').innerHTML = `<b>Block ${properties.block_id}</b><br>` +
      `break: ${properties.treated ? 'yes' : 'no'} · compartment: ${properties.compartment ?? '—'}<br>` +
      `class: ${properties.compartment_class ? compartmentLabel(properties.compartment_class) : '—'}` +
      ` · area: ${properties.compartment_area_ha === null || properties.compartment_area_ha === undefined ? '—' : Number(properties.compartment_area_ha).toLocaleString()} ha` +
      ` · treatments: ${(properties.treatments ?? []).join(', ') || '—'}`;
  } else {
    $('detail').innerHTML = `<b>Block ${properties.block_id}</b><br>` +
      `treated: ${properties.treated ? 'yes' : 'no'}<br>` +
      `treatments: ${(properties.treatments ?? []).join(', ') || '—'}`;
  }
  if (properties.compartment !== undefined && properties.compartment !== null) {
    const line = document.createElement('div');
    line.textContent = `compartment: ${properties.compartment}`;
    $('detail').append(line);
  }
  for (const attribute of state.baseAttributes) {
    if (attribute.name === 'compartment') continue;
    const value = properties[attribute.name];
    if (value !== undefined && value !== null && value !== '') {
      const line = document.createElement('div');
      line.textContent = `${attribute.label}: ${value}`;
      $('detail').append(line);
    }
  }
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
    await loadLayers();
    await loadTargets();
    await loadReports();
    syncCompareRuns();
    $('compare-a').value = state.run;
    if ($('compare-b').value === state.run) {
      const other = [...$('compare-b').options].find((option) => option.value !== state.run);
      if (other) $('compare-b').value = other.value;
    }
    if (state.compareView) {
      await loadComparison();
    } else {
      await loadMap();
    }
  });
  $('year').addEventListener('input', (event) => {
    state.yearChosen = true;
    state.year = Number(event.target.value);
    $('year-label').textContent = state.year;
  });
  $('year').addEventListener('change', () => {
    if (state.compareView) { loadComparison(); return; }
    if (state.live.active) render(false); else loadMap();
    if (state.showUsedRoads) loadUsedRoads();
  });
  $('skin').addEventListener('change', async (event) => {
    const skins = await api('api/skins');
    const skin = skins.find((candidate) => candidate.id === event.target.value);
    if (skin) { applySkin(skin); await loadTargets(); }
  });
  $('save-targets').addEventListener('click', saveTargets);
  $('build-report').addEventListener('click', buildReport);
  $('compare-a').addEventListener('change', loadComparison);
  $('compare-b').addEventListener('change', loadComparison);
  $('compare-filter').addEventListener('input', renderCompareAccounts);
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
      const tab = button.dataset.tab;
      for (const name of ['legend', 'targets', 'reports', 'comparison']) $(`tab-${name}`).hidden = name !== tab;
      if (tab === 'comparison') {
        syncCompareRuns();
        loadComparison();
      } else if (state.compareView) {
        clearCompareView();
      }
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
    syncCompareRuns();
    await loadSkins();
    await loadAgent();
    await loadPeriods();
    await loadLayers();
    await loadTargets();
    await loadReports();
    await loadMap();
  } catch (error) {
    statusLine(`service unavailable: ${error.message}`);
  }
}

start();
