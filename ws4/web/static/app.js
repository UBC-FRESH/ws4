// WS4 browser shell: reads the service's artefacts, no build step, relative URLs so it works
// under a proxy prefix as well as at the root.

import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

const state = { run: null, year: 0, features: [], view: { s: 1, x: 0, y: 0 }, base: null, skin: null, targets: [], pickedAccount: null, selectedAccounts: new Set(), targetCells: new Map(), watched: new Set(), targetSignature: "", windowValues: new Map(), series: new Map(), runPaused: false, live: { active: false, schedule: new Map(), total: 0 }, history: [], periods: [], periodIndex: 0, periodWidth: 1, yearChosen: false, chatSession: null, chatBusy: false, compareView: false, compare: null, compareAccounts: [], compareToken: 0, compareInitialized: false, layers: null, layerMode: 'current', patchClasses: new Set(), patchCatalog: [], compartmentAccounts: [], compartmentClasses: [], compartmentAccount: '', selectedCompartments: new Set(), baseAttributes: [], baseAttribute: '', roads: [], showRoads: false, usedRoads: [], showUsedRoads: false, blockElements: new Map(), mapEngine: (typeof window.maplibregl !== 'undefined' ? 'maplibre' : 'svg'), mapLibre: null, mapLibreReady: false, mapLoading: false, suppressViewportReload: false, mapTotals: null, mapFitted: false, lidar: null, lidarField: '', lidarRange: null, carbon: null, carbonAccount: '', workspace: 'map', subview: { results: 'reports', data: 'dataset' }, datasetSummary: null, geometryAvailable: true, selectedBlock: null, selectedGeometry: null, pendingBlock: null, pendingPeriod: null, urlReady: false, targetSeries: null, chartDirty: false, targetSort: { key: null, direction: 1 }, sdmd: { available: false, regions: [], aus: [], region: '', au: '', source: '', detail: null, plots: [], yield: [], points: null, regimes: [], preview: null, trajectory: '', trajectoryData: null, yieldMetric: 'volume_m3_ha' }, runSource: null, runSummary: null, fire: { scenes: [], selected: '', selectedB: '', payloads: new Map(), activePayload: null, playing: false }, console: { schema: null, token: '', job: null, timer: null, offset: 0, busy: false }, portfolioScan: [], portfolioTargets: [], pareto: { available: false, artifact: '', data: null, chart: null, cloud: null, selected: null, pinned: [], screen: [], artifacts: [] } };

state.estate3d = { open: false, features: [], yaw: -0.55, zoom: 1, exaggeration: 1, hits: [] };
const ESTATE_3D_LIMIT = 2000;

state.sdmd.coverage = [];
state.sdmd.coverageBec = '';

const $ = (id) => document.getElementById(id);
const TILE_VERSION = 'v9';
const statusLine = (text) => { $('status').textContent = text; };

function showToast(message, error = false) {
  const toast = $('toast');
  if (!toast) return;
  if (toastTimer) clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.toggle('error', error);
  toast.hidden = false;
  toastTimer = window.setTimeout(() => { toast.hidden = true; }, 2200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { accept: 'application/json', ...(options.headers || {}) },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail ?? detail; } catch { /* not json */ }
    throw new Error(detail);
  }
  return response.json();
}

async function apiPost(path) {
  const response = await fetch(path, { method: 'POST', headers: { accept: 'application/json' } });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail ?? detail; } catch { /* not json */ }
    throw new Error(detail);
  }
  return response.json();
}

async function loadProfiles() {
  const bar = $('profile-bar');
  const select = $('profile-select');
  const status = $('profile-status');
  try {
    const profiles = await api('api/scenario-profiles');
    select.replaceChildren();
    for (const profile of profiles) {
      const option = document.createElement('option');
      option.value = profile.name;
      option.textContent = profile.description
        ? `${profile.name} — ${profile.description}`
        : profile.name;
      select.appendChild(option);
    }
    bar.hidden = profiles.length === 0;
    status.textContent = profiles.length ? `${profiles.length} profiles` : '';
  } catch {
    bar.hidden = true;
  }
}

async function applyProfile() {
  const select = $('profile-select');
  const button = $('apply-profile');
  const status = $('profile-status');
  if (!select.value) return;
  button.disabled = true;
  status.textContent = `loading ${select.value}…`;
  try {
    const result = await apiPost(`api/scenario-profiles/${encodeURIComponent(select.value)}/apply`);
    status.textContent = `loaded ${select.value}: ${result.targets} targets`;
    showToast(`loaded profile ${select.value}`);
    await loadTargets();
  } catch (error) {
    status.textContent = `profile failed: ${error.message}`;
    showToast('profile load failed', true);
  } finally {
    button.disabled = false;
  }
}

async function startProfileRun() {
  const select = $('profile-select');
  const button = $('run-profile');
  const status = $('profile-status');
  if (!select.value) return;
  const requestedGenerations = Number($('profile-generations')?.value || 5000);
  // Profile effect tables and candidate caches are built for the 200-year horizon.
  const years = 200;
  const seed = Number($('run-seed')?.value || 7);
  const timeLimit = ($('run-time-limit')?.value || '').trim();
  // A wall-clock budget is authoritative; otherwise use the generation cap.
  const timeBudget = /^\d{1,2}:\d{2}:\d{2}$/.test(timeLimit);
  const generations = timeBudget ? 1_000_000 : requestedGenerations;
  stopRunWatch();
  button.disabled = true;
  status.textContent = 'saving current targets…';
  try {
    if (state.chartDirty) await saveTargetCharts();
    else await saveTargets();
  } catch (error) {
    status.textContent = `targets not saved: ${error.message}`;
    button.disabled = false;
    return;
  }
  status.textContent = `starting ${select.value}…`;
  runWatch = { id: null, timer: null, source: null, started: Date.now(), done: false, islands: 1 };
  state.live = { active: true, schedule: new Map(), total: 0, display: 'live' };
  state.layerMode = 'current';
  state.mapTotals = null;
  state.runPaused = false;
  state.history = [];
  renderLayerTree();
  resetLiveMap();
  drawSpark();
  showRun(`starting profile ${select.value}…`, true);
  try {
    const response = await fetch('api/runs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        profile: select.value,
        generations,
        years,
        seed,
        population: 64,
        time_limit: timeLimit,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `profile run failed (${response.status})`);
    status.textContent = payload.fallback_reason
      ? `running state engine · ${payload.fallback_reason}`
      : `running ${select.value}`;
    showToast(payload.fallback_reason || `profile ${select.value} started`);
    runWatch.id = payload.id;
    runWatch.islands = 1;
    $('start-run').textContent = 'Pause';
    $('stop-run').hidden = false;
    pollRun(payload.id);
    runWatch.timer = setInterval(() => pollRun(payload.id), 2000);
    openRunStream(payload.id, 1);
  } catch (error) {
    state.live.active = false;
    $('stop-run').hidden = true;
    status.textContent = `profile run failed: ${error.message}`;
    showToast('profile run failed', true);
    showRun(`profile run failed: ${error.message}`, false);
  } finally {
    button.disabled = false;
  }
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
  if (state.mapEngine === 'maplibre') {
    setMapLibreRoads();
    return;
  }
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
    const suffix = state.mapEngine === 'maplibre' ? '&format=wgs84' : '';
    const body = await api(`api/runs/${encodeURIComponent(state.run)}/used-roads?year=${state.year}${suffix}`);
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

const LIDAR_RAMP = [
  [68, 1, 84],
  [59, 82, 139],
  [33, 145, 140],
  [94, 201, 98],
  [253, 231, 37],
];
const LIDAR_MISSING = '#d5dce5';

function rampColor(stops, value) {
  const scaled = Math.max(0, Math.min(1, value)) * (stops.length - 1);
  const index = Math.min(stops.length - 2, Math.floor(scaled));
  const fraction = scaled - index;
  const left = stops[index];
  const right = stops[index + 1];
  const channel = (offset) => Math.round(left[offset] + (right[offset] - left[offset]) * fraction);
  return `rgb(${channel(0)}, ${channel(1)}, ${channel(2)})`;
}

function lidarColor(value) {
  const range = state.lidarRange;
  if (!range || !Number.isFinite(value)) return LIDAR_MISSING;
  const span = range[1] - range[0];
  const t = span > 0 ? (value - range[0]) / span : 0.5;
  return rampColor(LIDAR_RAMP, t);
}

function lidarFieldInfo(name) {
  return (state.lidar?.fields ?? []).find((field) => field.name === name) ?? null;
}

function lidarCoverage() {
  const info = state.lidar;
  if (!info?.available) return null;
  const field = lidarFieldInfo(state.lidarField);
  const valid = Number(field?.valid_count ?? info.block_count) || 0;
  const total = Number(info.total_blocks) || 0;
  return {
    valid,
    total,
    fraction: total > 0 ? valid / total : null,
    label: field ? field.label : 'any LiDAR field',
  };
}

function lidarCoverageText() {
  const coverage = lidarCoverage();
  if (!coverage) return '';
  const total = coverage.total.toLocaleString();
  const pct = coverage.fraction === null ? '' : ` · ${(coverage.fraction * 100).toFixed(1)}%`;
  return `${coverage.valid.toLocaleString()} / ${total} blocks${pct}`;
}

function renderLidarCoverage() {
  const row = $('lidar-coverage-row');
  const badge = $('lidar-coverage');
  const note = $('lidar-coverage-note');
  if (!row || !badge || !note) return;
  const coverage = lidarCoverage();
  if (!coverage || !coverage.total) {
    row.hidden = true;
    return;
  }
  row.hidden = false;
  badge.textContent = lidarCoverageText();
  note.textContent = state.lidarField
    ? `${coverage.label} · dataset-wide`
    : 'blocks with any LiDAR field';
}

function updateLidarRange() {
  const field = lidarFieldInfo(state.lidarField);
  if (!field) {
    state.lidarRange = null;
    renderLidarLegend();
    renderLidarCoverage();
    return;
  }
  if (Number.isFinite(field.min) && Number.isFinite(field.max)) {
    state.lidarRange = [Number(field.min), Number(field.max)];
  } else {
    const values = [];
    for (const feature of state.features) {
      const value = Number(feature.properties?.[field.name]);
      if (Number.isFinite(value)) values.push(value);
    }
    state.lidarRange = values.length ? [Math.min(...values), Math.max(...values)] : null;
  }
  renderLidarLegend();
  renderLidarCoverage();
}

function renderLidarLegend() {
  const legend = $('lidar-legend');
  if (!legend) return;
  const field = lidarFieldInfo(state.lidarField);
  if (!field || !state.lidarRange) {
    legend.hidden = true;
    return;
  }
  legend.hidden = false;
  const unit = field.unit ? ` ${field.unit}` : '';
  $('lidar-legend-title').textContent = `${field.label}${unit ? ` (${field.unit})` : ''}`;
  $('lidar-min').textContent = Number(state.lidarRange[0]).toLocaleString(undefined, { maximumFractionDigits: 2 }) + unit;
  $('lidar-max').textContent = Number(state.lidarRange[1]).toLocaleString(undefined, { maximumFractionDigits: 2 }) + unit;
}

function featureStyle(properties) {
  if (state.lidarField) {
    const value = Number(properties[state.lidarField]);
    return {
      treated: Boolean(properties.treated),
      fill: Number.isFinite(value) ? lidarColor(value) : LIDAR_MISSING,
      opacity: 1,
    };
  }
  let treated = false;
  let fill = null;
  let opacity = 1;
  if (state.compareView && state.compare) {
    const flags = state.compare.blocks.get(String(properties.block_id)) ?? {};
    const inA = Boolean(flags.a);
    const inB = Boolean(flags.b);
    treated = inA || inB;
    fill = inA && inB ? '#6b4c9a' : inA ? '#c0392b' : inB ? '#1f6feb' : null;
  } else if (state.layerMode === 'patches' && state.layers?.patches) {
    const patchClass = properties.patch_class;
    treated = Boolean(properties.treated) && state.patchClasses.has(patchClass);
    if (treated) fill = patchColor(patchClass);
  } else if (state.layerMode === 'cumulative' && state.layers?.cumulative) {
    treated = Boolean(properties.treated);
    if (treated && !properties.current) fill = '#f0d2b0';
  } else if (state.layerMode === 'compartments' && state.layers?.compartments) {
    if (properties.treated) {
      treated = true;
    } else {
      const compartmentClass = properties.compartment_class;
      treated = Boolean(compartmentClass) && state.selectedCompartments.has(compartmentClass);
      if (treated) fill = compartmentColor(compartmentClass);
    }
  } else if (state.layerMode === 'base' && state.baseAttribute) {
    treated = false;
    fill = baseColor(state.baseAttribute, properties[state.baseAttribute]);
  } else {
    treated = Boolean(properties.treated);
    if (state.live.active) {
      const chain = state.live.schedule.get(String(properties.block_id));
      treated = chain ? chain.some((event) => inCurrentPeriod(event[1])) : false;
    }
  }
  if (!fill) fill = treated ? '#c0392b' : '#d9e4dc';
  if (!treated && !(state.layerMode === 'base' && state.baseAttribute)) opacity = 0.78;
  const selected = String(properties.block_id) === String(state.selectedBlock);
  const visible = treated ? $('show-treated').checked : $('show-untreated').checked;
  return { treated, fill, opacity: visible ? opacity : 0, selected };
}

function ensureMapLibre() {
  if (state.mapLibre) return state.mapLibre;
  if (typeof window.maplibregl === 'undefined') {
    return null;
  }
  try {
    $('maplibre-map').hidden = false;
    $('map').hidden = true;
    const map = new window.maplibregl.Map({
      container: 'maplibre-map',
      style: {
        version: 8,
        sources: {
          basemap: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [{ id: 'basemap', type: 'raster', source: 'basemap' }],
      },
      center: [-123.5, 54.5],
      zoom: 5,
    });
    map.addControl(new window.maplibregl.NavigationControl(), 'top-right');
    map.on('load', () => {
      map.addSource('land-base', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addSource('blocks', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addSource('roads', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addSource('used-roads', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addLayer({
        id: 'land-base-fill',
        type: 'fill',
        source: 'land-base',
        paint: {
          'fill-color': '#e6ebe2',
          'fill-opacity': 0.35,
        },
      });
      map.addLayer({
        id: 'blocks-fill',
        type: 'fill',
        source: 'blocks',
        filter: ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'MultiPolygon']],
        paint: {
          'fill-color': ['to-color', ['get', '_fill']],
          'fill-opacity': ['get', '_opacity'],
          'fill-outline-color': 'rgba(0,0,0,0.22)',
        },
      });
      map.addLayer({
        id: 'blocks-points',
        type: 'circle',
        source: 'blocks',
        filter: ['==', ['geometry-type'], 'Point'],
        paint: {
          'circle-radius': 3,
          'circle-color': ['get', '_fill'],
          'circle-opacity': ['get', '_opacity'],
          'circle-stroke-color': 'rgba(0,0,0,0.25)',
          'circle-stroke-width': 0.4,
        },
      });
      map.addLayer({
        id: 'roads-line',
        type: 'line',
        source: 'roads',
        paint: { 'line-color': '#4c5661', 'line-width': 0.8, 'line-opacity': 0.65 },
      });
      map.addLayer({
        id: 'used-roads-line',
        type: 'line',
        source: 'used-roads',
        paint: { 'line-color': '#6d28d9', 'line-width': 1.6, 'line-opacity': 0.9 },
      });
      map.addSource('selected-block', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      map.addLayer({
        id: 'selected-block-line',
        type: 'line',
        source: 'selected-block',
        filter: ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'MultiPolygon']],
        paint: { 'line-color': '#111827', 'line-width': 2.2, 'line-opacity': 1 },
      });
      map.addLayer({
        id: 'selected-block-point',
        type: 'circle',
        source: 'selected-block',
        filter: ['==', ['geometry-type'], 'Point'],
        paint: { 'circle-radius': 5, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#111827', 'circle-stroke-width': 2 },
      });
      for (const interactive of ['blocks-fill', 'blocks-points']) {
        map.on('click', interactive, (event) => {
          const feature = event.features?.[0];
          if (feature) showDetail(feature.properties.block_id, null, feature.geometry ?? null);
        });
        map.on('mouseenter', interactive, () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', interactive, () => { map.getCanvas().style.cursor = ''; });
      }
      let viewportTimer = null;
      map.on('dragstart', () => { state.userInteracted = true; });
      map.on('zoomstart', (event) => { if (event.originalEvent) state.userInteracted = true; });
      map.on('moveend', () => {
        if (!state.mapLibreReady || state.mapLoading || state.suppressViewportReload || state.vectorActive) return;
        if (!state.userInteracted) return;
        state.userInteracted = false;
        window.clearTimeout(viewportTimer);
        viewportTimer = window.setTimeout(() => { loadMap(true); }, 250);
      });
      state.mapLibreReady = true;
      loadLandBase(map);
      renderMapLibre(true);
      if (state.run) loadMap(false);
    });
    map.on('error', () => { /* a missing basemap tile must not hide the blocks */ });
    state.mapLibre = map;
    state.mapFitted = false;
    return map;
  } catch (error) {
    state.mapEngine = 'svg';
    $('maplibre-map').hidden = true;
    $('map').hidden = false;
    $('layers-hint').textContent = `MapLibre unavailable: ${error.message}`;
    window.setTimeout(() => loadMap(), 0);
    return null;
  }
}

function extendMapBounds(bounds, coordinates) {
  if (Array.isArray(coordinates) && coordinates.length >= 2 && typeof coordinates[0] === 'number') {
    bounds.extend([coordinates[0], coordinates[1]]);
  } else if (Array.isArray(coordinates)) {
    for (const child of coordinates) extendMapBounds(bounds, child);
  }
}

function fitMapLibre(features) {
  if (!state.mapLibre || !features.length) return;
  const bounds = new window.maplibregl.LngLatBounds();
  for (const feature of features) {
    if (feature.geometry?.coordinates) extendMapBounds(bounds, feature.geometry.coordinates);
  }
  if (!bounds.isEmpty()) {
    state.suppressViewportReload = true;
    window.setTimeout(() => { state.suppressViewportReload = false; }, 700);
    state.mapLibre.fitBounds(bounds, { padding: 30, duration: 0, maxZoom: 12 });
  }
}

function setMapLibreRoads() {
  if (!state.mapLibre || !state.mapLibreReady) return;
  const roads = state.mapLibre.getSource('roads');
  const used = state.mapLibre.getSource('used-roads');
  if (roads) roads.setData({ type: 'FeatureCollection', features: state.showRoads ? state.roads : [] });
  if (used) used.setData({ type: 'FeatureCollection', features: state.showUsedRoads ? state.usedRoads : [] });
}

async function loadLandBase(map = state.mapLibre) {
  if (!map) return;
  try {
    const body = await api('api/land-base?format=wgs84');
    const source = map.getSource('land-base');
    if (source) source.setData(body);
    if (!state.mapFitted && body.features?.length) {
      const box = new window.maplibregl.LngLatBounds();
      for (const feature of body.features) {
        if (feature.geometry?.coordinates) extendMapBounds(box, feature.geometry.coordinates);
      }
      if (!box.isEmpty()) {
        state.mapFitted = true;
        state.suppressViewportReload = true;
        window.setTimeout(() => { state.suppressViewportReload = false; }, 700);
        map.fitBounds(box, { padding: 30, duration: 0 });
      }
    }
  } catch (error) {
    // The underlay is optional: a service without --land-base has none.
  }
}

async function fitVectorBounds() {
  if (!state.mapLibre || state.mapFitted) return;
  try {
    const body = await api('api/geometry/bounds?format=wgs84');
    const bounds = body.bounds;
    if (!Array.isArray(bounds) || bounds.length !== 4) return;
    const [west, south, east, north] = bounds.map(Number);
    if (![west, south, east, north].every(Number.isFinite)) return;
    state.mapFitted = true;
    state.suppressViewportReload = true;
    window.setTimeout(() => { state.suppressViewportReload = false; }, 700);
    state.mapLibre.fitBounds([[west, south], [east, north]], {
      padding: 30, duration: 0, maxZoom: 12,
    });
  } catch { /* a service without geometry keeps the default view */ }
}

function renderMapLibre(refit = true) {
  const map = ensureMapLibre();
  if (!map || !state.mapLibreReady) return;
  map.resize();
  const features = state.features.map((feature) => {
    const properties = feature.properties ?? {};
    const style = featureStyle(properties);
    return {
      ...feature,
      properties: { ...properties, _fill: style.fill, _opacity: style.opacity, _selected: style.selected },
    };
  });
  const source = map.getSource('blocks');
  if (source) source.setData({ type: 'FeatureCollection', features });
  setMapLibreRoads();
  if (liveView() && state.vectorActive) {
    renderLiveCounts();
  } else {
    let treated = 0;
    for (const feature of state.features) {
      if (featureStyle(feature.properties ?? {}).treated) treated += 1;
    }
    const treatedTotal = state.mapTotals ? state.mapTotals.treated : treated;
    const untreatedTotal = state.mapTotals ? state.mapTotals.untreated : state.features.length - treated;
    $('n-treated').textContent = treatedTotal.toLocaleString();
    $('n-untreated').textContent = untreatedTotal.toLocaleString();
  }
  const baseMode = state.layerMode === 'base' && Boolean(state.baseAttribute);
  $('treated-label').textContent = layerLabel();
  const skinHasTreatments = state.skin?.layers ? state.skin.layers.includes('treatments') : true;
  $('treated-label').closest('label').hidden = baseMode || !skinHasTreatments;
  $('untreated-label').textContent = baseMode ? 'Blocks' : 'Untreated';
  const period = currentPeriod();
  $('scale').textContent = `period ${state.periodIndex + 1}${period ? ` · years ${period.start}-${period.end}` : ''} · MapLibre`;
  renderMapLegend();
  updateSelectedOverlay();
  if (refit) fitMapLibre(features);
}

function setMapEngine(engine) {
  if (engine === state.mapEngine) return;
  state.mapEngine = engine;
  if (engine === 'maplibre') {
    $('map').hidden = true;
    $('maplibre-map').hidden = false;
    state.features = [];
    state.roads = [];
    state.usedRoads = [];
    state.base = null;
    ensureMapLibre();
    if (state.mapLibre) state.mapLibre.resize();
  } else {
    $('maplibre-map').hidden = true;
    $('map').hidden = false;
    if (state.mapLibre) state.mapLibre.remove();
    state.mapLibre = null;
    state.mapLibreReady = false;
    state.features = [];
    state.roads = [];
    state.usedRoads = [];
    state.base = null;
  }
  loadMap();
  if (state.showRoads) loadSourceRoads();
  if (state.showUsedRoads) loadUsedRoads();
  renderLayerTree();
}

async function loadSourceRoads() {
  if (!state.showRoads) return;
  try {
    const suffix = state.mapEngine === 'maplibre' ? '?format=wgs84' : '';
    const body = await api(`api/roads${suffix}`);
    state.roads = body.features ?? [];
    renderRoads();
  } catch (error) {
    $('layers-hint').textContent = `roads unavailable: ${error.message}`;
    state.showRoads = false;
    state.roads = [];
    renderRoads();
    renderLayerTree();
  }
}

function render(refit = true) {
  if (state.mapEngine === 'maplibre') {
    renderMapLibre(refit);
    return;
  }
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
    if (state.lidarField) {
      const value = Number(properties[state.lidarField]);
      isTreated = Boolean(properties.treated);
      klass = isTreated ? 'treated' : 'untreated';
      fill = Number.isFinite(value) ? lidarColor(value) : LIDAR_MISSING;
    } else if (state.compareView && state.compare) {
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
          ? chain.some((event) => inCurrentPeriod(event[1]))
          : false;
      }
      klass = isTreated ? 'treated' : 'untreated';
    }
    if (String(properties.block_id) === String(state.selectedBlock)) klass += ' selected';
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
  $('scale').textContent = `period ${state.periodIndex + 1} · year ${state.year} · 1 px ≈ ${Math.round(1 / base.scale)} m`;
  applyVisibility();
  renderMapLegend();
  if (refit) renderRoads();
}

function applyVisibility() {
  if (state.mapEngine === 'maplibre') {
    updateVectorPaint();
    renderMapLibre(false);
    return;
  }
  if (state.lidarField) {
    for (const element of document.querySelectorAll('#viewport .block')) element.style.display = '';
    renderMapLegend();
    return;
  }
  const showTreated = $('show-treated').checked;
  const showUntreated = $('show-untreated').checked;
  for (const element of document.querySelectorAll('#viewport .treated')) element.style.display = showTreated ? '' : 'none';
  for (const element of document.querySelectorAll('#viewport .untreated')) element.style.display = showUntreated ? '' : 'none';
  renderMapLegend();
}

function updateSelectedOverlay() {
  const map = state.mapLibre;
  if (!map || !map.getSource) return;
  const source = map.getSource('selected-block');
  if (!source) return;
  const geometry = state.selectedGeometry;
  const data = geometry
    ? { type: 'Feature', properties: {}, geometry }
    : { type: 'FeatureCollection', features: [] };
  source.setData(data);
}

function renderMapLegend() {
  const legend = $('map-legend');
  if (!legend) return;
  if ($('map-wrap').hidden) { legend.hidden = true; return; }
  legend.replaceChildren();
  const title = document.createElement('div');
  title.className = 'map-legend-title';
  if (state.live.active) {
    title.textContent = `${state.live.display === 'static' ? 'Static' : 'Live'} · ${layerLabel()}`;
  } else {
    title.textContent = layerLabel();
  }
  legend.append(title);
  if (state.live.active && state.mapEngine === 'maplibre') {
    const liveLabel = document.createElement('label');
    liveLabel.className = 'map-legend-row map-live-toggle';
    const liveBox = document.createElement('input');
    liveBox.type = 'checkbox';
    liveBox.checked = state.live.display !== 'static';
    liveBox.addEventListener('change', () => setLiveDisplay(liveBox.checked ? 'live' : 'static'));
    liveLabel.append(liveBox, document.createTextNode('Live schedule'));
    legend.append(liveLabel);
  }
  const row = (label, color, count, className = '') => {
    const line = document.createElement('div');
    line.className = 'map-legend-row';
    const swatch = document.createElement('span');
    swatch.className = `map-legend-swatch ${className}`.trim();
    if (color) swatch.style.background = color;
    const text = document.createElement('span');
    text.textContent = label;
    line.append(swatch, text);
    if (count !== undefined) {
      const value = document.createElement('span');
      value.className = 'map-legend-count';
      value.textContent = count;
      line.append(value);
    }
    legend.append(line);
    return line;
  };
  if (state.lidarField) {
    const field = lidarFieldInfo(state.lidarField);
    const bar = document.createElement('div');
    bar.className = 'map-legend-row';
    const swatch = document.createElement('span');
    swatch.className = 'map-legend-swatch lidar';
    swatch.style.width = '3rem';
    swatch.style.height = '.45rem';
    const range = document.createElement('span');
    if (state.lidarRange) {
      const unit = field?.unit ? ` ${field.unit}` : '';
      range.textContent = `${Number(state.lidarRange[0]).toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit} → ${Number(state.lidarRange[1]).toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit}`;
    } else {
      range.textContent = 'LiDAR values';
    }
    bar.append(swatch, range);
    legend.append(bar);
    const coverage = document.createElement('div');
    coverage.className = 'map-legend-row';
    coverage.textContent = `Coverage ${lidarCoverageText()}`;
    legend.append(coverage);
    row('No value', LIDAR_MISSING);
  } else if (state.compareView && state.compare) {
    row('A only', '#c0392b');
    row('B only', '#1f6feb');
    row('Both', '#6b4c9a');
  } else if (state.layerMode === 'base' && state.baseAttribute) {
    const info = baseAttributeInfo(state.baseAttribute);
    const note = document.createElement('div');
    note.className = 'map-legend-row';
    note.textContent = `Blocks coloured by ${info?.label ?? state.baseAttribute}`;
    legend.append(note);
  } else {
    const treatedLabel = state.layerMode === 'cumulative' ? 'Treated now' : 'Treated';
    row(treatedLabel, '#c0392b', $('n-treated').textContent, 'treated');
    if (state.layerMode === 'cumulative' && state.layers?.cumulative) {
      row('Treated earlier', '#e6c49e', undefined, 'past');
    }
    row('Untreated', null, $('n-untreated').textContent, 'untreated');
    const showUntreated = $('show-untreated').checked;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = showUntreated ? 'Treated only' : 'Show all blocks';
    button.addEventListener('click', () => {
      $('show-untreated').checked = !$('show-untreated').checked;
      applyVisibility();
    });
    legend.append(button);
  }
  legend.hidden = false;
}

function resetLiveMap() {
  if (state.mapEngine === 'maplibre') {
    renderMapLibre(false);
    return;
  }
  if (!state.blockElements.size) return;
  for (const element of state.blockElements.values()) {
    element.setAttribute('class', 'block untreated');
    element.style.fill = '';
  }
  $('n-treated').textContent = '0';
  $('n-untreated').textContent = state.features.length.toLocaleString();
  applyVisibility();
}

function updateLiveBlocks(blocks, reset = false) {
  if (state.mapEngine === 'maplibre') {
    if (liveView() && state.vectorActive) {
      const map = state.mapLibre;
      if (reset) clearLiveFeatureState();
      for (const block of blocks) {
        const chain = state.live.schedule.get(String(block));
        const treated = chain
          ? chain.some((event) => inCurrentPeriod(event[1]))
          : false;
        try {
          map.setFeatureState(
            { source: 'blocks-vector', sourceLayer: 'blocks', id: Number(block) },
            { liveTreated: treated },
          );
        } catch { /* a tile without the feature id simply keeps its neutral colour */ }
      }
      renderLiveCounts();
      renderMapLegend();
      return;
    }
    if (state.live.active && state.layerMode === 'current') renderMapLibre(false);
    return;
  }
  if (!state.live.active || state.layerMode !== 'current' || !state.blockElements.size) return;
  for (const block of blocks) {
    const element = state.blockElements.get(String(block));
    if (!element) continue;
    const chain = state.live.schedule.get(String(block));
    const treated = chain
      ? chain.some((event) => inCurrentPeriod(event[1]))
      : false;
    element.setAttribute('class', `block ${treated ? 'treated' : 'untreated'}`);
  }
  let treated = 0;
  for (const feature of state.features) {
    const chain = state.live.schedule.get(String(feature.properties?.block_id));
    if (chain?.some((event) => inCurrentPeriod(event[1]))) treated += 1;
  }
  $('n-treated').textContent = treated.toLocaleString();
  $('n-untreated').textContent = (state.features.length - treated).toLocaleString();
  applyVisibility();
}

function mapLayerName() {
  if (state.layerMode === 'patches' && state.layers?.patches) return 'patches';
  if (state.layerMode === 'cumulative' && state.layers?.cumulative) return 'cumulative';
  if (state.layerMode === 'compartments' && state.layers?.compartments) return 'compartments';
  if (state.layerMode === 'base' || (state.layers && !state.layers.treatments)) return 'blocks';
  return 'treatments';
}

function vectorMode(layer) {
  return state.mapEngine === 'maplibre'
    && !state.compareView
    && ['blocks', 'treatments', 'cumulative'].includes(layer);
}

function vectorColorExpression() {
  if (state.compareView) {
    return ['match', ['get', 'compare'],
      'a', '#c0392b',
      'b', '#1f6feb',
      'both', '#6b4c9a',
      '#2f7d4f'];
  }
  const grid = state.layerMode === 'blocks' || (state.layers && !state.layers.treatments)
    ? ['interpolate', ['linear'], ['coalesce', ['get', 'treated_share'], 0], 0, '#d9e4dc', 1, '#d9e4dc']
    : ['interpolate', ['linear'], ['coalesce', ['get', 'treated_share'], 0],
      0, '#d9e4dc', 0.02, '#e8b26a', 0.05, '#d97706', 0.15, '#b91c1c'];
  if (state.layerMode === 'cumulative' && state.layers?.cumulative) {
    return ['case',
      ['has', 'treated_share'], grid,
      ['all', ['==', ['get', 'treated'], true], ['==', ['get', 'current'], false]], '#f0d2b0',
      ['==', ['get', 'treated'], true], '#c0392b',
      '#d9e4dc'];
  }
  return ['case', ['has', 'treated_share'], grid, ['==', ['get', 'treated'], true], '#c0392b', '#d9e4dc'];
}

function vectorOpacityExpression() {
  const showTreated = $('show-treated').checked;
  const showUntreated = $('show-untreated').checked;
  if (state.compareView) {
    return ['case',
      ['==', ['get', 'compare'], 'none'], showUntreated ? 0.12 : 0,
      showTreated ? 1 : 0];
  }
  return ['case',
    ['has', 'treated_share'], 0.85,
    ['==', ['get', 'treated'], true], showTreated ? 1 : 0,
    showUntreated ? 0.78 : 0];
}

function updateVectorPaint() {
  const map = state.mapLibre;
  if (!map || !state.vectorActive) return;
  const color = vectorColorExpression();
  const opacity = vectorOpacityExpression();
  for (const id of ['blocks-vector-fill', 'blocks-vector-points']) {
    if (!map.getLayer(id)) continue;
    map.setPaintProperty(id, id.endsWith('fill') ? 'fill-color' : 'circle-color', color);
    map.setPaintProperty(id, id.endsWith('fill') ? 'fill-opacity' : 'circle-opacity', opacity);
  }
  if (state.live.active) updateLiveVectorPaint();
}

function ensureLiveVectorLayers(map) {
  if (map.getLayer('live-vector-fill')) return;
  map.addLayer({
    id: 'live-vector-fill',
    type: 'fill',
    source: 'blocks-vector',
    'source-layer': 'blocks',
    filter: ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'MultiPolygon']],
    paint: {
      'fill-color': ['case', ['boolean', ['feature-state', 'liveTreated'], false], '#c0392b', '#d9e4dc'],
      'fill-opacity': 0.78,
      'fill-outline-color': 'rgba(0,0,0,0.22)',
    },
  });
  map.addLayer({
    id: 'live-vector-points',
    type: 'circle',
    source: 'blocks-vector',
    'source-layer': 'blocks',
    filter: ['==', ['geometry-type'], 'Point'],
    paint: {
      'circle-radius': 3,
      'circle-color': ['case', ['boolean', ['feature-state', 'liveTreated'], false], '#c0392b', '#d9e4dc'],
      'circle-opacity': 0.78,
      'circle-stroke-color': 'rgba(0,0,0,0.25)',
      'circle-stroke-width': 0.4,
    },
  });
}

function setLiveVectorMode(live) {
  const map = state.mapLibre;
  if (!map) return;
  for (const id of ['live-vector-fill', 'live-vector-points']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', live ? 'visible' : 'none');
  }
  for (const id of ['blocks-vector-fill', 'blocks-vector-points']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', live ? 'none' : (state.vectorActive ? 'visible' : 'none'));
  }
  if (live) updateLiveVectorPaint();
}

function updateLiveVectorPaint() {
  const map = state.mapLibre;
  if (!map || !map.getLayer('live-vector-fill')) return;
  const showTreated = $('show-treated').checked;
  const showUntreated = $('show-untreated').checked;
  const fillOpacity = ['case',
    ['boolean', ['feature-state', 'liveTreated'], false], showTreated ? 1 : 0,
    showUntreated ? 0.78 : 0];
  const pointOpacity = ['case',
    ['boolean', ['feature-state', 'liveTreated'], false], showTreated ? 1 : 0,
    showUntreated ? 0.78 : 0];
  map.setPaintProperty('live-vector-fill', 'fill-opacity', fillOpacity);
  map.setPaintProperty('live-vector-points', 'circle-opacity', pointOpacity);
}

function clearLiveFeatureState() {
  const map = state.mapLibre;
  const source = map?.getSource('blocks-vector');
  if (!map || !source) return;
  try { map.removeFeatureState({ source: 'blocks-vector', sourceLayer: 'blocks' }); } catch { /* source may be replacing */ }
}

function liveTreatedCount() {
  let treated = 0;
  for (const chain of state.live.schedule.values()) {
    if (chain.some((event) => inCurrentPeriod(event[1]))) treated += 1;
  }
  return treated;
}

function renderLiveCounts() {
  const treated = liveTreatedCount();
  const total = state.mapTotals ? state.mapTotals.treated + state.mapTotals.untreated : 0;
  $('n-treated').textContent = treated.toLocaleString();
  $('n-untreated').textContent = Math.max(0, total - treated).toLocaleString();
}

function liveView() {
  return state.live.active && state.live.display !== 'static';
}

function applyLiveSchedule() {
  const map = state.mapLibre;
  if (!map || !liveView() || !state.vectorActive) return;
  for (const [block, chain] of state.live.schedule) {
    const treated = chain.some((event) => inCurrentPeriod(event[1]));
    try {
      map.setFeatureState(
        { source: 'blocks-vector', sourceLayer: 'blocks', id: Number(block) },
        { liveTreated: treated },
      );
    } catch { /* a tile without the feature id keeps its neutral colour */ }
  }
}

function setLiveDisplay(display) {
  if (!state.live.active) return;
  state.live.display = display === 'static' ? 'static' : 'live';
  state.mapTotals = null;
  loadMap(true);
}

function installVectorSource(url) {
  const map = state.mapLibre;
  if (!map) return false;
  const existing = map.getSource('blocks-vector');
  if (existing) {
    if (state.vectorUrl !== url) {
      existing.setTiles([url]);
      state.vectorUrl = url;
    }
  } else {
    map.addSource('blocks-vector', { type: 'vector', tiles: [url], minzoom: 0, maxzoom: 16 });
    const before = map.getLayer('roads-line') ? 'roads-line' : undefined;
    const fillLayer = {
      id: 'blocks-vector-fill',
      type: 'fill',
      source: 'blocks-vector',
      'source-layer': 'blocks',
      filter: ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'MultiPolygon']],
      paint: {
        'fill-color': '#d9e4dc',
        'fill-opacity': 0.78,
        'fill-outline-color': 'rgba(0,0,0,0.22)',
      },
    };
    const pointLayer = {
      id: 'blocks-vector-points',
      type: 'circle',
      source: 'blocks-vector',
      'source-layer': 'blocks',
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 3,
        'circle-color': '#d9e4dc',
        'circle-opacity': 0.78,
        'circle-stroke-color': 'rgba(0,0,0,0.25)',
        'circle-stroke-width': 0.4,
      },
    };
    if (before) {
      map.addLayer(fillLayer, before);
      map.addLayer(pointLayer, before);
    } else {
      map.addLayer(fillLayer);
      map.addLayer(pointLayer);
    }
    for (const interactive of ['blocks-vector-fill', 'blocks-vector-points']) {
      map.on('click', interactive, (event) => {
        const feature = event.features?.[0];
        if (feature) showDetail(feature.properties.block_id, feature.properties, feature.geometry ?? null);
      });
      map.on('mouseenter', interactive, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', interactive, () => { map.getCanvas().style.cursor = ''; });
    }
    state.vectorUrl = url;
  }
  ensureLiveVectorLayers(map);
  state.vectorActive = true;
  for (const id of ['blocks-vector-fill', 'blocks-vector-points']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'visible');
  }
  for (const id of ['blocks-fill', 'blocks-points']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'none');
  }
  setLiveVectorMode(Boolean(state.live.active));
  updateVectorPaint();
  return true;
}

function ensureVectorSource(url) {
  const map = state.mapLibre;
  if (!map) return;
  const install = () => installVectorSource(url);
  if (map.loaded()) install();
  else map.once('idle', install);
}

function hideVectorLayers() {
  state.vectorActive = false;
  const map = state.mapLibre;
  if (!map) return;
  for (const id of ['blocks-vector-fill', 'blocks-vector-points']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'none');
  }
  for (const id of ['blocks-fill', 'blocks-points']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'visible');
  }
  for (const id of ['live-vector-fill', 'live-vector-points']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'none');
  }
}

async function loadMap(preserveView = false) {
  if (!state.run) return;
  const requestId = ++mapLoadSequence;
  if (!state.geometryAvailable) {
    setMapLoading(false);
    return;
  }
  if (state.mapEngine === 'maplibre' && !state.mapLibre) ensureMapLibre();
  if (state.mapEngine === 'maplibre' && !state.mapLibreReady) {
    state.mapRetries = (state.mapRetries || 0) + 1;
    if (state.mapRetries > 40) return;
    window.setTimeout(() => loadMap(preserveView), 300);
    return;
  }
  state.mapRetries = 0;
  state.mapLoading = true;
  statusLine('loading map…');
  if (periodPlayTimer) setMapLoading(false);
  else setMapLoading(true, 'Loading map…');
  const lidarField = state.lidarField ? lidarFieldInfo(state.lidarField) : null;
  const layer = state.lidarField || liveView() ? 'blocks' : mapLayerName();
  try {
    const period = currentPeriod();
    const end = period ? Number(period.end) : state.year;
    const span = period ? ` · years ${period.start}-${period.end}` : '';
    if (state.mapEngine === 'maplibre' && vectorMode(layer) && !state.lidarField) {
      const base = new URL('.', document.baseURI).href;
      let tileUrl = `${base}api/runs/${encodeURIComponent(state.run)}/tiles/{z}/{x}/{y}.mvt?year=${end}&layer=${layer}&v=${TILE_VERSION}`;
      if (period) tileUrl += `&period_start=${period.start}`;
      state.vectorActive = true;
      state.features = [];
      ensureVectorSource(tileUrl);
      await fitVectorBounds();
      if (requestId !== mapLoadSequence) return;
      let stats = `api/runs/${encodeURIComponent(state.run)}/map-stats?year=${end}&layer=${layer}`;
      if (period) stats += `&period_start=${period.start}`;
      try {
        const body = await api(stats);
        if (requestId !== mapLoadSequence) return;
        if (liveView()) {
          const total = Number(body.total_treated ?? 0) + Number(body.total_untreated ?? 0);
          state.mapTotals = { treated: 0, untreated: total };
          clearLiveFeatureState();
          setLiveVectorMode(true);
          applyLiveSchedule();
          renderLiveCounts();
          statusLine(`live · ${total.toLocaleString()} blocks · ${layer} · period ${state.periodIndex + 1}${span}`);
        } else {
          state.mapTotals = {
            treated: body.total_treated ?? 0,
            untreated: body.total_untreated ?? 0,
          };
          setLiveVectorMode(false);
          $('n-treated').textContent = Number(state.mapTotals.treated).toLocaleString();
          $('n-untreated').textContent = Number(state.mapTotals.untreated).toLocaleString();
          statusLine(`${state.mapTotals.treated.toLocaleString()} treated blocks · ${layer} · MVT · period ${state.periodIndex + 1}${span}`);
        }
      } catch {
        state.mapTotals = null;
        statusLine(`MVT · ${layer} · period ${state.periodIndex + 1}${span}`);
      }
      renderMapLegend();
      if (state.showUsedRoads) loadUsedRoads();
      return;
    }
    hideVectorLayers();
    state.mapTotals = null;
    let query = `api/runs/${encodeURIComponent(state.run)}/map?year=${end}&layer=${layer}`;
    query += periodQuery();
    if (state.lidarField) query += '&lidar=1';
    if (layer === 'compartments') {
      query += `&account=${encodeURIComponent(state.compartmentAccount)}`;
    }
    if (state.mapEngine === 'maplibre') {
      query += '&format=wgs84';
      const map = state.mapLibre;
      if (map) {
        const bounds = map.getBounds();
        query += `&bbox=${bounds.getWest()},${bounds.getSouth()},${bounds.getEast()},${bounds.getNorth()}`;
        query += `&zoom=${map.getZoom().toFixed(2)}`;
      }
    }
    const body = await api(query);
    if (requestId !== mapLoadSequence) return;
    state.features = body.features ?? [];
    state.mapTotals = state.live.active
      ? null
      : body.overview
        ? { treated: body.total_treated ?? 0, untreated: body.total_untreated ?? 0 }
        : null;
    updateLidarRange();
    render(!preserveView);
    const place = state.mapEngine === 'maplibre' ? 'in view' : '';
    const noun = body.overview_mode === 'treated' ? 'treated blocks' : 'blocks';
    const sourceLabel = lidarField ? `LiDAR: ${lidarField.label}` : layer;
    statusLine(`${state.features.length.toLocaleString()} ${noun} ${place} · ${sourceLabel}${state.live.active ? ' · live' : ''} · period ${state.periodIndex + 1}${span}`);
    if (state.showUsedRoads) loadUsedRoads();
  } catch (error) {
    if (requestId !== mapLoadSequence) return;
    if (/no geometry layer/i.test(error.message)) setGeometryAvailability(false);
    statusLine(`map unavailable: ${error.message}`);
  } finally {
    if (requestId === mapLoadSequence) {
      state.mapLoading = false;
      setMapLoading(false);
    }
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
  if (state.mapEngine === 'maplibre' || state.features.length) {
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
    account.className = 'account account-link';
    account.textContent = a?.account ?? b?.account ?? '';
    account.title = `${account.textContent} — open in Plan targets`;
    account.tabIndex = 0;
    account.setAttribute('role', 'button');
    const open = () => openPlanForAccount(account.textContent);
    account.addEventListener('click', open);
    account.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        open();
      }
    });
    tr.append(account);
    const kind = document.createElement('td');
    kind.textContent = a?.kind ?? b?.kind ?? config?.kind ?? '';
    tr.append(kind);
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

async function stopSearch(id) {
  const status = $('search-run-status');
  try {
    const body = await api(`api/search/${encodeURIComponent(id)}/stop`, { method: 'POST' });
    status.textContent = `${id} · ${body.status}`;
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
    await loadSearch();
  } catch (error) {
    status.textContent = `${id} · stop failed: ${error.message}`;
  }
}

async function loadSearch(preferred = '') {
  populateScanAccounts();
  populateScaffoldAccounts();
  const empty = $('search-empty');
  const select = $('search-select');
  const table = $('search-table');
  const summary = $('search-summary');
  try {
    const artifacts = await api('api/search');
    select.replaceChildren();
    const jobs = $('search-jobs');
    jobs.replaceChildren();
    const ready = artifacts.filter((artifact) => !artifact.status);
    for (const artifact of artifacts.filter((item) => item.status)) {
      const item = document.createElement('li');
      item.textContent = `${artifact.id} · ${artifact.kind} · ${artifact.status} `;
      if (artifact.status === 'running') {
        const stop = document.createElement('button');
        stop.type = 'button';
        stop.textContent = 'Stop';
        stop.addEventListener('click', () => stopSearch(artifact.id));
        item.append(stop);
      }
      jobs.append(item);
    }
    if (!ready.length) {
      empty.hidden = false;
      empty.textContent = 'no completed portfolio or tuner artifacts yet — launch one below or use scripts/portfolio.py / scripts/tune.py';
      summary.textContent = '';
      table.hidden = true;
      $('search-explore').disabled = true;
      $('search-delete').disabled = true;
      $('search-clean-failed').disabled = true;
      return;
    }
    empty.hidden = true;
    $('search-clean-failed').disabled = !ready.some(
      (artifact) => artifact.kind === 'portfolio' && artifact.usable === false
    );
    for (const artifact of ready) {
      const option = document.createElement('option');
      option.value = artifact.id;
      const details = artifact.kind === 'portfolio'
        ? ` · ${Number(artifact.front_size || 0)} front · ${Number(artifact.members || 0)} members${artifact.failures ? ` · ${artifact.failures} failed` : ''}`
        : '';
      option.textContent = `${artifact.id} (${artifact.kind})${details}`;
      select.append(option);
    }
    if (preferred && ready.some((artifact) => artifact.id === preferred)) {
      select.value = preferred;
    }
    await renderSearchArtifact(select.value);
  } catch (error) {
    empty.hidden = false;
    empty.textContent = `search artifacts unavailable: ${error.message}`;
    table.hidden = true;
  }
}

function searchFileUrl(id, path) {
  const encoded = String(path).split('/').map((part) => encodeURIComponent(part)).join('/');
  return `api/search/${encodeURIComponent(id)}/files/${encoded}`;
}

function searchLink(id, path, label) {
  const link = document.createElement('a');
  link.href = searchFileUrl(id, path);
  link.textContent = label;
  link.target = '_blank';
  link.rel = 'noopener';
  return link;
}

function showSearchDetail(id, data) {
  const detail = $('search-detail');
  detail.replaceChildren();
  detail.hidden = false;
  if (!data) {
    detail.textContent = 'select a row for details';
    return;
  }
  const title = document.createElement('h3');
  title.textContent = data.label ?? 'artifact';
  detail.append(title);
  const metadata = document.createElement('p');
  metadata.className = 'hint';
  metadata.textContent = data.seed !== undefined ? `seed ${data.seed} · ${data.status ?? ''}` : '';
  if (data.error) metadata.textContent += ` · ${data.error}`;
  detail.append(metadata);
  if (data.factors) {
    const factors = document.createElement('pre');
    factors.textContent = JSON.stringify(data.factors, null, 2);
    detail.append(factors);
  }
  if (data.metrics) {
    const metrics = document.createElement('ul');
    for (const [key, value] of Object.entries(data.metrics)) {
      const item = document.createElement('li');
      item.textContent = `${key}: ${compareNumber(value)}`;
      metrics.append(item);
    }
    detail.append(metrics);
  }
  const links = document.createElement('p');
  for (const [key, label, path] of [
    ['schedule', 'Schedule', data.schedule],
    ['targets', 'Targets', data.targets],
    ['front', 'front.csv', 'front.csv'],
    ['report', 'portfolio.md', 'portfolio.md'],
    ['console', 'console.log', 'console.log'],
  ]) {
    if (!path) continue;
    if (links.childNodes.length) links.append(' · ');
    links.append(searchLink(id, path, label));
  }
  detail.append(links);
}

async function renderSearchArtifact(id) {
  const table = $('search-table');
  const summary = $('search-summary');
  const detail = $('search-detail');
  if (!id) return;
  detail.hidden = true;
  detail.replaceChildren();
  try {
    const body = await api(`api/search/${encodeURIComponent(id)}`);
    const head = table.querySelector('thead');
    const tbody = table.querySelector('tbody');
    head.replaceChildren();
    tbody.replaceChildren();
    const addHead = (labels) => {
      const tr = document.createElement('tr');
      for (const label of labels) {
        const th = document.createElement('th');
        th.textContent = label;
        tr.append(th);
      }
      head.append(tr);
    };
    const addRow = (values, className = '') => {
      const tr = document.createElement('tr');
      if (className) tr.className = className;
      for (const value of values) {
        const td = document.createElement('td');
        td.textContent = value;
        tr.append(td);
      }
      tbody.append(tr);
      return tr;
    };
    if (body.kind === 'portfolio') {
      $('search-explore').disabled = false;
      $('search-delete').disabled = false;
      const data = body.data ?? {};
      const metrics = Array.isArray(data.metrics) ? data.metrics : [];
      const front = new Set(data.outcome_front ?? data.front ?? []);
      const members = Array.isArray(data.members) ? data.members : [];
      summary.textContent = `portfolio · ${members.length} members · ${front.size} on the front · ${data.failures ?? 0} failures · ${data.iterations ?? '?'} iterations · ${data.years ?? '?'} years`;
      addHead(['Member', 'Seed', 'Objective', ...metrics, 'Status', 'Front']);
      for (const member of members) {
        const key = `${member.label ?? ''}:${String(member.seed ?? '').padStart(3, '0')}`;
        const row = addRow([
          member.label ?? '',
          String(member.seed ?? ''),
          member.objective === null || member.objective === undefined ? 'failed' : compareNumber(member.objective),
          ...metrics.map((metric) => compareNumber(member.metrics?.[metric] ?? 0)),
          member.status ?? '',
          front.has(key) ? 'front' : '',
        ], front.has(key) ? 'search-front' : '');
        row.addEventListener('click', () => showSearchDetail(body.id, member));
      }
      const first = members.find((member) => front.has(`${member.label}:${String(member.seed).padStart(3, '0')}`)) ?? members[0];
      if (first) showSearchDetail(body.id, first);
      table.hidden = false;
      return;
    }
    if (body.kind === 'tuning') {
      $('search-explore').disabled = true;
      $('search-delete').disabled = true;
      const data = body.data ?? {};
      const candidates = Array.isArray(data.candidates) ? data.candidates : [];
      const byLabel = new Map(candidates.map((candidate) => [candidate.label, candidate]));
      const ranking = Array.isArray(data.ranking) ? data.ranking : [];
      summary.textContent = `tuning · ${data.mode ?? ''} · ${candidates.length} candidates · ${data.failures ?? 0} failures · winner ${data.winner?.label ?? 'none'}`;
      addHead(['Rank', 'Candidate', 'Best', 'Median', 'Runs', 'Failures', 'Parameters']);
      ranking.forEach((label, index) => {
        const candidate = byLabel.get(label) ?? {};
        const failures = Array.isArray(candidate.failures) ? candidate.failures : [];
        const row = addRow([
          String(index + 1),
          label,
          compareNumber(candidate.best ?? 0),
          compareNumber(candidate.median ?? 0),
          String(candidate.runs ?? 0),
          String(failures.length),
          JSON.stringify(candidate.parameters ?? {}),
        ], index === 0 ? 'search-front' : '');
        row.addEventListener('click', () => showSearchDetail(body.id, {
          label,
          status: failures.length ? `${failures.length} failures` : 'ok',
          error: failures.join('; '),
          metrics: { best: candidate.best ?? 0, median: candidate.median ?? 0 },
        }));
      });
      if (data.winner) {
        showSearchDetail(body.id, {
          label: `winner ${data.winner.label}`,
          status: data.mode,
          metrics: { best: data.winner.best ?? 0, median: data.winner.median ?? 0 },
        });
      }
      table.hidden = false;
      return;
    }
    if (body.kind === 'lp') {
      const data = body.data ?? {};
      summary.textContent = `lp · ${data.status ?? ''} · objective ${compareNumber(data.objective ?? 0)} · ${data.variables ?? '?'} options`;
      addHead(['Account', 'Period', 'Bound', 'Dual', 'Slack', 'Binding']);
      for (const dual of data.duals ?? []) {
        addRow([
          dual.account ?? '',
          String(dual.period ?? ''),
          dual.bound ?? '',
          compareNumber(dual.dual ?? 0),
          compareNumber(dual.slack ?? 0),
          dual.binding ?? '',
        ]);
      }
      const reduced = document.createElement('div');
      const title = document.createElement('h3');
      title.textContent = 'Option reduced costs';
      reduced.append(title);
      const inner = document.createElement('div');
      inner.className = 'table-wrap';
      const extra = document.createElement('table');
      const extraHead = document.createElement('thead');
      extraHead.innerHTML = '<tr><th>Block</th><th>Treatments</th><th>Value</th><th>Reduced cost</th></tr>';
      const extraBody = document.createElement('tbody');
      for (const cost of data.reduced_costs ?? []) {
        const tr = document.createElement('tr');
        const treatments = (cost.treatments ?? []).map(([name, offset]) => `${name}@${offset}`).join(' → ');
        for (const value of [cost.block, treatments, compareNumber(cost.value ?? 0), compareNumber(cost.reduced_cost ?? 0)]) {
          const td = document.createElement('td');
          td.textContent = String(value);
          tr.append(td);
        }
        extraBody.append(tr);
      }
      extra.append(extraHead, extraBody);
      inner.append(extra);
      reduced.append(inner);
      detail.replaceChildren(reduced);
      detail.hidden = false;
      table.hidden = false;
      return;
    }
    summary.textContent = `${body.kind} artifact ${id}`;
    addHead(['Key', 'Value']);
    for (const [key, value] of Object.entries(body.data ?? {})) {
      addRow([key, typeof value === 'object' ? JSON.stringify(value) : String(value)]);
    }
    table.hidden = false;
  } catch (error) {
    summary.textContent = `artifact unavailable: ${error.message}`;
    table.hidden = true;
  }
}

function scanProduct() {
  return state.portfolioScan.reduce(
    (total, dimension) => total * Math.max(1, dimension.factors.length),
    1
  );
}

function scanDimensionKey(row) {
  const account = String(row.account || '');
  const period = row.period === null || row.period === undefined ? null : Number(row.period);
  return period !== null && Number.isFinite(period) ? `${account}@${period}` : account;
}

function scanDimensionLabel(row) {
  const account = String(row.account || '');
  const period = row.period === null || row.period === undefined ? null : Number(row.period);
  if (period === null || !Number.isFinite(period)) return account;
  const year = row.year === null || row.year === undefined ? null : Number(row.year);
  return `${account} · P${period}${Number.isFinite(year) ? ` (to Y${year})` : ''}`;
}

function scanDimensionsFromTargets() {
  const seen = new Set();
  const dimensions = [];
  for (const row of state.targets || []) {
    const key = scanDimensionKey(row);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    dimensions.push({ key, label: scanDimensionLabel(row), account: String(row.account || ''), period: Number(row.period) });
  }
  return dimensions.sort((left, right) => {
    const account = left.account.localeCompare(right.account);
    if (account !== 0) return account;
    return (left.period || 0) - (right.period || 0);
  });
}

function populateScanAccounts() {
  const select = $('scan-account');
  if (!select) return;
  const previous = select.value;
  const dimensions = scanDimensionsFromTargets();
  select.replaceChildren();
  if (!dimensions.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No targets loaded';
    select.append(option);
    $('scan-add').disabled = true;
    return;
  }
  $('scan-add').disabled = false;
  for (const dimension of dimensions) {
    const option = document.createElement('option');
    option.value = dimension.key;
    option.textContent = dimension.label;
    select.append(option);
  }
  if (dimensions.some((dimension) => dimension.key === previous)) select.value = previous;
}

async function renderPortfolioMemberTargets() {
  const details = $('portfolio-member-targets');
  const body = $('portfolio-member-targets-body');
  const status = $('portfolio-member-targets-status');
  if (!details || !body || !status) return;
  if (!state.runSource) {
    details.hidden = true;
    body.replaceChildren();
    status.textContent = '';
    return;
  }
  details.hidden = false;
  status.textContent = 'loading…';
  try {
    const rows = await api(`api/runs/${encodeURIComponent(state.run)}/target-definitions`);
    body.replaceChildren();
    if (!rows.length) {
      status.textContent = 'the member target file has no rows';
      return;
    }
    const table = document.createElement('table');
    const head = document.createElement('thead');
    const headRow = document.createElement('tr');
    for (const label of ['Account', 'Period', 'Min', 'Max', 'Min W', 'Max W']) {
      const th = document.createElement('th');
      th.textContent = label;
      headRow.append(th);
    }
    head.append(headRow);
    const tbody = document.createElement('tbody');
    for (const row of rows) {
      const tr = document.createElement('tr');
      for (const value of [row.account, row.period ?? row.year ?? '', row.minimum ?? '', row.maximum ?? '', row.min_weight ?? '', row.max_weight ?? '']) {
        const td = document.createElement('td');
        td.textContent = value === null || value === undefined ? '' : String(value);
        tr.append(td);
      }
      tbody.append(tr);
    }
    table.append(head, tbody);
    body.append(table);
    status.textContent = `${rows.length} member target rows · read-only`;
  } catch (error) {
    details.hidden = false;
    body.replaceChildren();
    status.textContent = `member targets unavailable: ${error.message}`;
  }
}

function scaffoldAccounts() {
  const names = new Set([...state.series.keys()]);
  for (const row of state.targets || []) names.add(String(row.account));
  return [...names].filter(Boolean).sort();
}

function populateScaffoldAccounts() {
  const select = $('scaffold-account');
  if (!select) return;
  const previous = select.value;
  const accounts = scaffoldAccounts();
  select.replaceChildren();
  if (!accounts.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No accounts loaded';
    select.append(option);
    $('scaffold-add').disabled = true;
    return;
  }
  $('scaffold-add').disabled = false;
  for (const account of accounts) {
    const option = document.createElement('option');
    option.value = account;
    option.textContent = account;
    select.append(option);
  }
  if (accounts.includes(previous)) select.value = previous;
  const periods = (state.targets || [])
    .map((row) => Number(row.period))
    .filter((period) => Number.isFinite(period) && period > 0);
  if (periods.length && Number($('scaffold-period').value) <= 0) {
    $('scaffold-period').value = String(Math.max(...periods));
  }
}

function scaffoldCurrentValue(account) {
  const series = state.series.get(account);
  if (!series || !series.size) return 0;
  const last = [...series.keys()].sort((left, right) => left - right).pop();
  return Number(series.get(last) || 0);
}

function scaffoldMinimum(account, period) {
  const seriesValue = scaffoldCurrentValue(account);
  if (seriesValue) return seriesValue;
  const candidates = (state.targets || []).filter((row) => String(row.account) === account);
  const exact = candidates.find((row) => Number(row.period) === Number(period));
  const row = exact || candidates[0];
  return row && row.minimum !== null && row.minimum !== undefined ? Number(row.minimum) : 0;
}

function scaffoldFamily(account) {
  return String(account).split('.').slice(0, 3).join('.');
}

function scaffoldWarnings() {
  const rows = state.portfolioTargets || [];
  const warnings = [];
  for (let i = 0; i < rows.length; i += 1) {
    for (let j = i + 1; j < rows.length; j += 1) {
      const left = String(rows[i].account);
      const right = String(rows[j].account);
      if (left.startsWith(`${right}.`) || right.startsWith(`${left}.`)) {
        warnings.push(`nested accounts: ${left} / ${right}`);
      }
    }
  }
  const families = new Map();
  for (const row of rows) {
    const family = scaffoldFamily(row.account);
    families.set(family, (families.get(family) || 0) + 1);
  }
  for (const [family, count] of families) {
    if (count > 2) warnings.push(`${count} accounts share ${family}`);
  }
  return [...new Set(warnings)];
}

function applyDiverseScaffold() {
  const available = new Set(scaffoldAccounts());
  const preferred = [
    'feature.Area.managed',
    'feature.Area.og1.total',
    'feature.Area.og2.total',
    'feature.Yield.managed.Total',
    'feature.SpeciesProp.managed.CW',
    'product.HarvestedVolume.managed.Total.CC',
  ];
  const selected = preferred.filter((account) => available.has(account));
  for (const account of [...available].sort()) {
    if (selected.length >= 6) break;
    if (selected.includes(account)) continue;
    if (selected.some((item) => item.startsWith(`${account}.`) || account.startsWith(`${item}.`))) continue;
    if (selected.filter((item) => scaffoldFamily(item) === scaffoldFamily(account)).length >= 2) continue;
    selected.push(account);
  }
  const period = Number($('scaffold-period').value) || 20;
  const weight = Math.max(0.0001, Number($('scaffold-weight').value) || 1);
  state.portfolioTargets = selected.slice(0, 6).map((account) => ({
    account,
    period,
    minimum: scaffoldMinimum(account, period),
    maximum: null,
    min_weight: weight,
    max_weight: weight,
    period_width: scaffoldPeriodWidth(),
    active: true,
  }));
  renderScaffoldTargets();
}

function scaffoldPeriodWidth() {
  const row = (state.targets || []).find((target) => Number(target.period_width) > 0);
  return row ? Number(row.period_width) : 10;
}

function addScaffoldTarget() {
  const account = $('scaffold-account').value;
  const period = Number($('scaffold-period').value);
  const weight = Math.max(0.0001, Number($('scaffold-weight').value) || 1);
  if (!account || !Number.isFinite(period) || period < 1) {
    $('scaffold-status').textContent = 'Choose an account and a valid period.';
    return;
  }
  const existing = state.portfolioTargets.find(
    (row) => row.account === account && Number(row.period) === period
  );
  const row = {
    account,
    period,
    minimum: existing ? existing.minimum : scaffoldMinimum(account, period),
    maximum: existing ? existing.maximum : null,
    min_weight: weight,
    max_weight: weight,
    period_width: scaffoldPeriodWidth(),
    active: true,
  };
  if (existing) Object.assign(existing, row);
  else state.portfolioTargets.push(row);
  renderScaffoldTargets();
}

function renderScaffoldTargets() {
  const list = $('scaffold-list');
  list.replaceChildren();
  for (const [index, target] of state.portfolioTargets.entries()) {
    const item = document.createElement('li');
    const name = document.createElement('span');
    name.textContent = `${target.account} · P${target.period}`;
    const min = document.createElement('input');
    min.type = 'number';
    min.step = 'any';
    min.value = String(target.minimum ?? '');
    min.addEventListener('change', () => {
      target.minimum = min.value === '' ? null : Number(min.value);
      renderScaffoldTargets();
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'link-button';
    remove.textContent = 'remove';
    remove.addEventListener('click', () => {
      state.portfolioTargets.splice(index, 1);
      renderScaffoldTargets();
    });
    item.append(name, min, remove);
    list.append(item);
  }
  const preview = $('scaffold-preview');
  preview.hidden = !state.portfolioTargets.length;
  preview.textContent = state.portfolioTargets.length
    ? JSON.stringify({ targets: state.portfolioTargets }, null, 2)
    : '';
  const warnings = scaffoldWarnings();
  $('scaffold-status').textContent = state.portfolioTargets.length
    ? `${state.portfolioTargets.length} target rows · live targets unchanged${warnings.length ? ` · warning: ${warnings.join('; ')}` : ''}`
    : 'Add 5-7 accounts for a multi-account front.';
}

function useScaffoldTargets() {
  if (!state.portfolioTargets.length) {
    $('scaffold-status').textContent = 'Add at least one target row first.';
    return;
  }
  const accounts = state.portfolioTargets.map((target) => target.account);
  const factors = $('scan-factors')
    .value.split(',')
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value) && value > 0);
  const levels = factors.length ? factors : [0.5, 1, 2];
  $('portfolio-vary').value = accounts.map((account) => `${account}=${levels.join(',')}`).join(';');
  $('portfolio-metrics').value = accounts.join(',');
  $('portfolio-directions').value = accounts.map((account) => `${account}=max`).join(';');
  if (levels.length ** accounts.length > Number($('portfolio-max-members').value || 64)) {
    $('portfolio-mode').value = 'random';
  }
  const horizon = Math.max(
    Number($('portfolio-years').value) || 50,
    ...state.portfolioTargets.map(
      (target) => Number(target.period || 1) * Number(target.period_width || 10)
    )
  );
  $('portfolio-years').value = String(horizon);
  $('scaffold-status').textContent = `${accounts.length} target rows will be written to the portfolio run; live targets are unchanged.`;
  renderScaffoldTargets();
}

function wireScaffoldTargets() {
  if (!$('scaffold-add')) return;
  $('scaffold-add').addEventListener('click', addScaffoldTarget);
  $('scaffold-diverse').addEventListener('click', applyDiverseScaffold);
  $('scaffold-use').addEventListener('click', useScaffoldTargets);
  $('scaffold-clear').addEventListener('click', () => {
    state.portfolioTargets = [];
    renderScaffoldTargets();
  });
  renderScaffoldTargets();
}

function renderPortfolioScan() {
  const list = $('scan-dimensions');
  list.replaceChildren();
  for (const [index, dimension] of state.portfolioScan.entries()) {
    const item = document.createElement('li');
    const name = document.createElement('span');
    name.textContent = `${dimension.label || dimension.key} = ${dimension.factors.join(', ')}`;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'link-button';
    remove.textContent = 'remove';
    remove.addEventListener('click', () => {
      state.portfolioScan.splice(index, 1);
      renderPortfolioScan();
    });
    item.append(name, remove);
    list.append(item);
  }
  const summary = $('scan-summary');
  if (!state.portfolioScan.length) {
    summary.textContent = 'Add 5-7 target accounts to build a scan.';
    return;
  }
  const product = scanProduct();
  const max = Math.max(1, Number($('portfolio-max-members').value) || 64);
  const mode = $('portfolio-mode').value;
  summary.textContent = `${state.portfolioScan.length} dimensions · ${product} grid members · cap ${max}${product > max && mode === 'grid' ? ' — switch to random or raise the cap' : ''}`;
}

function addPortfolioScanDimension() {
  const key = $('scan-account').value;
  const selected = scanDimensionsFromTargets().find((item) => item.key === key);
  const factors = $('scan-factors')
    .value.split(',')
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (!key || !selected || !factors.length) {
    $('scan-summary').textContent = 'Pick a target dimension and at least one positive factor.';
    return;
  }
  const existing = state.portfolioScan.find((item) => item.key === key);
  if (existing) existing.factors = factors;
  else state.portfolioScan.push({ ...selected, factors });
  renderPortfolioScan();
}

function scaffoldScanPeriods(count) {
  const selected = $('scan-account').value;
  const account = selected.includes('@') ? selected.split('@', 1)[0] : selected;
  const all = scanDimensionsFromTargets();
  let rows = all.filter((item) => item.account === account && item.period > 0);
  if (rows.length < count) rows = all.filter((item) => item.period > 0);
  rows = rows.sort((left, right) => left.period - right.period).slice(0, count);
  if (!rows.length) {
    $('scan-summary').textContent = 'No periodic target rows are available.';
    return;
  }
  const factors = $('scan-factors')
    .value.split(',')
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (!factors.length) {
    $('scan-summary').textContent = 'Enter at least one positive factor first.';
    return;
  }
  state.portfolioScan = rows.map((row) => ({ ...row, factors: [...factors] }));
  renderPortfolioScan();
  const product = scanProduct();
  const max = Math.max(1, Number($('portfolio-max-members').value) || 64);
  if (product > max) $('portfolio-mode').value = 'random';
  renderPortfolioScan();
}

function usePortfolioScan() {
  if (!state.portfolioScan.length) {
    $('scan-summary').textContent = 'Add at least one dimension first.';
    return;
  }
  $('portfolio-vary').value = state.portfolioScan
    .map((item) => `${item.key || item.account}=${item.factors.join(',')}`)
    .join(';');
  const product = scanProduct();
  const max = Math.max(1, Number($('portfolio-max-members').value) || 64);
  if (product > max) $('portfolio-mode').value = 'random';
  renderPortfolioScan();
}

function wirePortfolioScan() {
  if (!$('scan-add')) return;
  $('scan-add').addEventListener('click', addPortfolioScanDimension);
  $('scan-periods-5').addEventListener('click', () => scaffoldScanPeriods(5));
  $('scan-periods-7').addEventListener('click', () => scaffoldScanPeriods(7));
  $('scan-clear').addEventListener('click', () => {
    state.portfolioScan = [];
    renderPortfolioScan();
  });
  $('scan-use').addEventListener('click', usePortfolioScan);
  $('portfolio-max-members').addEventListener('input', renderPortfolioScan);
  $('portfolio-mode').addEventListener('change', renderPortfolioScan);
}

async function waitSearch(id) {
  const status = $('search-run-status');
  for (let attempt = 0; attempt < 900; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 2000));
    const body = await api(`api/search/${encodeURIComponent(id)}/status`);
    if (body.status === 'running') {
      status.textContent = `${id} · running · ${attempt * 2}s`;
      continue;
    }
    if (body.status === 'done') {
      status.textContent = `${id} · done`;
      await loadSearch(id);
      return;
    }
    status.textContent = `${id} · failed${body.log ? `
${String(body.log).slice(-600)}` : ''}`;
    return;
  }
  status.textContent = `${id} · still running; check the artifact later`;
}

async function loadParetoArtifacts(preferred = '') {
  const select = $('pareto-artifact');
  const status = $('pareto-status');
  if (!select) return;
  try {
    const artifacts = await api('api/search');
    const ready = artifacts.filter((item) => !item.status && item.kind === 'portfolio');
    state.pareto.artifacts = ready;
    state.pareto.available = ready.length > 0;
    select.replaceChildren();
    if (!ready.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'No completed portfolios';
      select.append(option);
      status.textContent = 'run a portfolio in Search first';
      clearParetoCloud();
      return;
    }
    for (const artifact of ready) {
      const option = document.createElement('option');
      option.value = artifact.id;
      const details = artifact.kind === 'portfolio'
        ? ` · ${Number(artifact.front_size || 0)} front · ${Number(artifact.members || 0)} members${artifact.failures ? ` · ${artifact.failures} failed` : ''}`
        : '';
      option.textContent = `${artifact.id}${details}`;
      select.append(option);
    }
    const usable = ready.filter((item) => item.kind !== 'portfolio' || item.usable !== false);
    const current = preferred || state.pareto.artifact || usable[0]?.id || ready[0]?.id || select.value;
    if (current && ready.some((item) => item.id === current)) select.value = current;
    state.pareto.artifact = select.value;
    await loadParetoSpace(select.value);
  } catch (error) {
    status.textContent = `portfolios unavailable: ${error.message}`;
    clearParetoCloud();
  }
}

async function loadParetoSpace(id) {
  const status = $('pareto-status');
  if (!id) return;
  status.textContent = 'loading solution space…';
  state.pareto.artifact = id;
  try {
    const data = await api(`api/search/${encodeURIComponent(id)}/space?near_front=1`);
    state.pareto.data = data;
    state.pareto.selected = null;
    state.pareto.pinned = [];
    populateParetoSelects(data);
    $('pareto-info').replaceChildren();
    const hint = document.createElement('p');
    hint.className = 'muted';
    hint.textContent = 'Click a point to inspect it. Dominance is recomputed from every successful member.';
    $('pareto-info').append(hint);
    $('pareto-pin').disabled = true;
    $('pareto-clear-pins').disabled = true;
    $('pareto-open').disabled = true;
    $('pareto-open-run').disabled = true;
    $('pareto-compare-pinned').disabled = true;
    renderParetoCompare();
    drawParetoCloud();
    status.textContent = `${data.points.length} members · ${data.front_size} exact front · ${data.failed} failed`;
  } catch (error) {
    status.textContent = `solution space unavailable: ${error.message}`;
    clearParetoCloud();
  }
}

function paretoOption(select, value, label) {
  const option = document.createElement('option');
  option.value = String(value);
  option.textContent = label;
  select.append(option);
}

function populateParetoSelects(data) {
  const dimensions = Array.isArray(data.dimensions) ? data.dimensions : [];
  const metricNames = Array.isArray(data.metrics) ? data.metrics : [];
  const fill = (id, defaultValue, includeNone = false, noneLabel = 'none') => {
    const select = $(id);
    const previous = select.value;
    select.replaceChildren();
    if (includeNone) paretoOption(select, -1, noneLabel);
    dimensions.forEach((dimension, index) => {
      paretoOption(select, index, dimension);
    });
    if (previous !== '' && [...select.options].some((option) => option.value === previous)) {
      select.value = previous;
    } else {
      select.value = String(defaultValue);
    }
  };
  fill('pareto-x', 0);
  fill('pareto-y', Math.min(1, dimensions.length - 1));
  fill('pareto-z', Math.min(2, dimensions.length - 1));
  fill('pareto-colour', Math.min(3, dimensions.length - 1));
  fill('pareto-size', -1, true, 'uniform');
  fill('pareto-opacity', -1, true, 'fixed');
  fill('pareto-filter-dim', -1, true, 'none');
  const filter = $('pareto-filter');
  filter.value = '0';
  $('pareto-filter-value').textContent = 'all';
  const epsilon = $('pareto-epsilon');
  const previousEpsilon = Number(epsilon.value);
  epsilon.value = String(
    Number.isFinite(previousEpsilon) && previousEpsilon > 0 && previousEpsilon < 1
      ? previousEpsilon
      : 0.08
  );
  if (metricNames.length) {
    $('pareto-legend').dataset.metricCount = String(metricNames.length);
  }
}

function paretoDimensionValue(point, dimension) {
  if (!dimension) return 0;
  const values = point.normalized || {};
  return Number(values[dimension] ?? 0);
}

function paretoLabel(data, dimension) {
  return dimension || '—';
}

function ensureParetoChart() {
  if (state.pareto.chart) return state.pareto.chart;
  const canvas = $('pareto-canvas');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(Math.max(canvas.clientWidth, 1), Math.max(canvas.clientHeight, 1), false);
  renderer.setClearColor(0x000000, 0);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, Math.max(canvas.clientWidth, 1) / Math.max(canvas.clientHeight, 1), 0.1, 100);
  camera.position.set(2.8, 2.2, 2.9);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.target.set(0, 0, 0);
  controls.minDistance = 1.2;
  controls.maxDistance = 8;
  const box = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(3.2, 3.2, 3.2)),
    new THREE.LineBasicMaterial({ color: 0x8fa68a, transparent: true, opacity: 0.55 })
  );
  scene.add(box);
  const axes = buildParetoAxes();
  scene.add(axes);
  const chart = { renderer, scene, camera, controls, canvas, cloud: null, axes, points: [] };
  canvas.addEventListener('click', (event) => {
    if (!state.pareto.screen.length) return;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    let nearest = null;
    let distance = 18;
    for (const item of state.pareto.screen) {
      const candidate = Math.hypot(item.x - x, item.y - y);
      if (candidate < distance) {
        nearest = item;
        distance = candidate;
      }
    }
    if (nearest) selectParetoPoint(nearest.key);
  });
  window.addEventListener('resize', resizeParetoChart);
  state.pareto.chart = chart;
  updateParetoAxes(chart, { x: 'X', y: 'Y', z: 'Z' });
  animatePareto();
  return chart;
}

function resizeParetoChart() {
  const chart = state.pareto.chart;
  if (!chart || !chart.canvas.clientWidth) return;
  const width = Math.max(chart.canvas.clientWidth, 1);
  const height = Math.max(chart.canvas.clientHeight, 1);
  chart.renderer.setSize(width, height, false);
  chart.camera.aspect = width / height;
  chart.camera.updateProjectionMatrix();
}

function buildParetoAxes() {
  const group = new THREE.Group();
  const origin = new THREE.Vector3(0, 0, 0);
  const end = 1.6;
  const entries = [
    [new THREE.Vector3(end, 0, 0), 0xc85555],
    [new THREE.Vector3(0, end, 0), 0x5f9f54],
    [new THREE.Vector3(0, 0, end), 0x4d7fc4],
  ];
  for (const [target, colour] of entries) {
    const geometry = new THREE.BufferGeometry().setFromPoints([origin, target]);
    const material = new THREE.LineBasicMaterial({ color: colour, transparent: true, opacity: 0.9 });
    group.add(new THREE.Line(geometry, material));
    const cone = new THREE.Mesh(
      new THREE.ConeGeometry(0.07, 0.2, 10),
      new THREE.MeshBasicMaterial({ color: colour })
    );
    cone.position.copy(target);
    cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), target.clone().sub(origin).normalize());
    group.add(cone);
  }
  return group;
}

function updateParetoAxes(chart, labels) {
  chart.axisLabelText = labels;
  $('pareto-axis-x').textContent = `X: ${labels.x || 'X'}`;
  $('pareto-axis-y').textContent = `Y: ${labels.y || 'Y'}`;
  $('pareto-axis-z').textContent = `Z: ${labels.z || 'Z'}`;
}

function positionParetoAxisLabels(chart) {
  if (!chart.axisLabelText || state.workspace !== 'pareto') return;
  const endpoints = [[2.08, 0, 0], [0, 2.08, 0], [0, 0, 2.08]];
  const ids = ['pareto-axis-x', 'pareto-axis-y', 'pareto-axis-z'];
  const point = new THREE.Vector3();
  endpoints.forEach((endpoint, index) => {
    point.set(endpoint[0], endpoint[1], endpoint[2]);
    point.project(chart.camera);
    const element = $(ids[index]);
    if (point.z > 1) {
      element.style.display = 'none';
      return;
    }
    element.style.display = '';
    const halfWidth = element.offsetWidth / 2 + 8;
    const halfHeight = element.offsetHeight / 2 + 8;
    const left = Math.max(
      halfWidth,
      Math.min(chart.canvas.clientWidth - halfWidth, (point.x * 0.5 + 0.5) * chart.canvas.clientWidth)
    );
    const top = Math.max(
      halfHeight,
      Math.min(chart.canvas.clientHeight - halfHeight, (-point.y * 0.5 + 0.5) * chart.canvas.clientHeight)
    );
    element.style.left = `${left}px`;
    element.style.top = `${top}px`;
  });
}

function updateParetoScreen(chart) {
  const cloud = chart.cloud;
  const positions = cloud?.geometry?.getAttribute('position');
  const points = cloud?.userData?.points;
  if (!positions || !Array.isArray(points)) {
    state.pareto.screen = [];
    return;
  }
  const projected = new THREE.Vector3();
  const screen = [];
  for (let index = 0; index < Math.min(points.length, positions.count); index += 1) {
    projected.fromBufferAttribute(positions, index);
    projected.project(chart.camera);
    if (projected.z > 1) continue;
    screen.push({
      x: (projected.x * 0.5 + 0.5) * chart.canvas.clientWidth,
      y: (-projected.y * 0.5 + 0.5) * chart.canvas.clientHeight,
      key: points[index].key,
    });
  }
  state.pareto.screen = screen;
}

function animatePareto() {
  const chart = state.pareto.chart;
  if (!chart) return;
  if (state.workspace === 'pareto') {
    chart.controls.update();
    positionParetoAxisLabels(chart);
    updateParetoScreen(chart);
    chart.renderer.render(chart.scene, chart.camera);
  }
  requestAnimationFrame(animatePareto);
}

function clearParetoCloud() {
  const chart = state.pareto.chart;
  if (chart && chart.cloud) {
    chart.scene.remove(chart.cloud);
    chart.cloud.geometry.dispose();
    chart.cloud.material.dispose();
    chart.cloud = null;
  }
  state.pareto.screen = [];
  $('pareto-stats').replaceChildren();
  $('pareto-legend').replaceChildren();
}

function drawParetoCloud() {
  const data = state.pareto.data;
  if (!data) return;
  const chart = ensureParetoChart();
  const dimensions = Array.isArray(data.dimensions) ? data.dimensions : [];
  const xDim = dimensions[Number($('pareto-x').value)];
  const yDim = dimensions[Number($('pareto-y').value)];
  const zDim = dimensions[Number($('pareto-z').value)];
  const colourDim = dimensions[Number($('pareto-colour').value)];
  const sizeIndex = Number($('pareto-size').value);
  const opacityIndex = Number($('pareto-opacity').value);
  const filterIndex = Number($('pareto-filter-dim').value);
  const sizeDim = sizeIndex >= 0 ? dimensions[sizeIndex] : '';
  const opacityDim = opacityIndex >= 0 ? dimensions[opacityIndex] : '';
  const filterDim = filterIndex >= 0 ? dimensions[filterIndex] : '';
  const dominance = $('pareto-dominance').value;
  const epsilon = Math.max(0, Number($('pareto-epsilon').value) || 0);
  const threshold = Number($('pareto-filter').value) / 100;
  const points = (data.points || []).filter((point) => {
    if (dominance === 'front' && !point.front) return false;
    if (dominance === 'near' && !point.front && Number(point.distance_to_front) > epsilon) return false;
    if (filterDim && threshold > 0 && paretoDimensionValue(point, filterDim) < threshold) return false;
    return true;
  });
  clearParetoCloud();
  if (!points.length) {
    $('pareto-info').replaceChildren();
    const hint = document.createElement('p');
    hint.className = 'hint';
    hint.textContent = 'No members match this dominance and filter setting.';
    $('pareto-info').append(hint);
    return;
  }
  const positions = new Float32Array(points.length * 3);
  const colours = new Float32Array(points.length * 3);
  const sizes = new Float32Array(points.length);
  const alphas = new Float32Array(points.length);
  const colour = new THREE.Color();
  points.forEach((point, index) => {
    const x = paretoDimensionValue(point, xDim);
    const y = paretoDimensionValue(point, yDim);
    const z = paretoDimensionValue(point, zDim);
    positions[index * 3] = (x - 0.5) * 3.2;
    positions[index * 3 + 1] = (y - 0.5) * 3.2;
    positions[index * 3 + 2] = (z - 0.5) * 3.2;
    colour.setHSL(0.58 - paretoDimensionValue(point, colourDim) * 0.46, 0.68, 0.5);
    colours[index * 3] = colour.r;
    colours[index * 3 + 1] = colour.g;
    colours[index * 3 + 2] = colour.b;
    const sizeValue = sizeDim ? paretoDimensionValue(point, sizeDim) : 0.5;
    const selected = state.pareto.selected === point.key;
    sizes[index] = (0.7 + sizeValue * 1.3) * (selected ? 1.7 : 1);
    const opacityValue = opacityDim ? 0.2 + paretoDimensionValue(point, opacityDim) * 0.8 : 0.9;
    alphas[index] = opacityValue * (point.front ? 1 : 0.55);
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('pointColor', new THREE.BufferAttribute(colours, 3));
  geometry.setAttribute('pointSize', new THREE.BufferAttribute(sizes, 1));
  geometry.setAttribute('pointAlpha', new THREE.BufferAttribute(alphas, 1));
  const material = new THREE.ShaderMaterial({
    uniforms: { uScale: { value: Math.max(16, chart.canvas.clientHeight * 0.055) } },
    vertexShader: `
      uniform float uScale;
      attribute vec3 pointColor;
      attribute float pointSize;
      attribute float pointAlpha;
      varying vec3 vColor;
      varying float vAlpha;
      void main() {
        vColor = pointColor;
        vAlpha = pointAlpha;
        vec4 view = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = pointSize * uScale / max(0.001, -view.z);
        gl_Position = projectionMatrix * view;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      varying float vAlpha;
      void main() {
        float distance = length(gl_PointCoord - vec2(0.5));
        if (distance > 0.5) discard;
        float edge = smoothstep(0.5, 0.42, distance);
        gl_FragColor = vec4(vColor, vAlpha * edge);
      }
    `,
    transparent: true,
    depthWrite: false,
  });
  const cloud = new THREE.Points(geometry, material);
  cloud.userData.points = points;
  chart.scene.add(cloud);
  chart.cloud = cloud;
  state.pareto.cloud = cloud;
  if (state.pareto.selected && !points.some((point) => point.key === state.pareto.selected)) {
    state.pareto.selected = null;
  }
  const labels = {
    x: paretoLabel(data, xDim),
    y: paretoLabel(data, yDim),
    z: paretoLabel(data, zDim),
  };
  updateParetoAxes(chart, labels);
  renderParetoMemberPicker(points);
  renderParetoStats(data, points, dominance, epsilon);
  renderParetoLegend(data, points, colourDim, filterDim);
  if (state.pareto.selected) {
    const selectedPoint = points.find((point) => point.key === state.pareto.selected);
    if (selectedPoint) renderParetoInfo(selectedPoint);
  }
  chart.renderer.render(chart.scene, chart.camera);
}

function renderParetoMemberPicker(points) {
  const picker = $('pareto-member');
  if (!picker) return;
  const previous = picker.value || state.pareto.selected || '';
  picker.replaceChildren();
  const none = document.createElement('option');
  none.value = '';
  none.textContent = points.length ? '— select a visible member —' : '— no visible members —';
  picker.append(none);
  for (const point of points) {
    const option = document.createElement('option');
    option.value = point.key;
    option.textContent = `${point.key}${point.front ? ' · front' : ` · ε ${Number(point.distance_to_front).toFixed(3)}`}`;
    picker.append(option);
  }
  picker.disabled = points.length === 0;
  if (previous && points.some((point) => point.key === previous)) picker.value = previous;
}

function renderParetoStats(data, points, dominance, epsilon) {
  const stats = $('pareto-stats');
  stats.replaceChildren();
  const nearCount = (data.points || []).filter(
    (point) => point.front || Number(point.distance_to_front) <= epsilon
  ).length;
  const entries = [
    ['Visible', points.length],
    ['Exact front', data.front_size],
    [`Near-front ≤ ${Number(epsilon).toFixed(2)}`, nearCount],
    ['Failed', data.failed],
    ['Mode', dominance],
  ];
  for (const [label, value] of entries) {
    const card = document.createElement('div');
    card.className = 'change-stat';
    const name = document.createElement('span');
    name.textContent = label;
    const number = document.createElement('strong');
    number.textContent = String(value);
    card.append(name, number);
    stats.append(card);
  }
}

function renderParetoLegend(data, points, colourDim, filterDim) {
  const legend = $('pareto-legend');
  legend.replaceChildren();
  const low = document.createElement('span');
  low.textContent = `← low ${colourDim || 'colour'}`;
  const high = document.createElement('span');
  high.textContent = `high ${colourDim || 'colour'} →`;
  const front = document.createElement('span');
  front.textContent = 'bright = exact front · faded = dominated';
  const count = document.createElement('span');
  count.textContent = `${points.length} plotted${filterDim ? ` · filter ${filterDim}` : ''}`;
  legend.append(low, high, front, count);
}

function selectParetoPoint(key) {
  const data = state.pareto.data;
  if (!data) return;
  const point = (data.points || []).find((item) => item.key === key);
  if (!point) return;
  state.pareto.selected = key;
  drawParetoCloud();
  const picker = $('pareto-member');
  if (picker) picker.value = key;
  renderParetoInfo(point);
}

function renderParetoInfo(point) {
  const data = state.pareto.data;
  if (!data) return;
  const info = $('pareto-info');
  info.replaceChildren();
  const title = document.createElement('p');
  title.className = 'pareto-id';
  title.textContent = `${point.key} · ${point.front ? 'exact front' : `dominated (ε ${Number(point.distance_to_front).toFixed(3)})`}`;
  info.append(title);
  const grid = document.createElement('div');
  grid.className = 'mini-grid';
  for (const dimension of data.dimensions || []) {
    const card = document.createElement('div');
    card.className = 'mini-card';
    const label = document.createElement('span');
    label.textContent = dimension;
    const value = document.createElement('strong');
    const raw = dimension === 'objective' ? point.objective : point.metrics?.[dimension];
    value.textContent = compareNumber(raw);
    card.append(label, value);
    grid.append(card);
  }
  info.append(grid);
  const detail = document.createElement('p');
  detail.className = 'hint';
  detail.textContent = `objective ${compareNumber(point.objective)} · seed ${point.seed ?? '—'} · ${Object.entries(point.factors || {}).map(([key, value]) => `${key}=${compareNumber(value)}`).join(' · ') || 'baseline weights'}`;
  info.append(detail);
  $('pareto-pin').disabled = false;
  $('pareto-open').disabled = !point.schedule;
  $('pareto-open-run').disabled = !point.run_dir;
}

function pinParetoPoint() {
  const selected = state.pareto.selected;
  if (!selected) return;
  const point = (state.pareto.data?.points || []).find((item) => item.key === selected);
  if (!point) return;
  if (state.pareto.pinned.some((item) => item.key === point.key)) return;
  if (state.pareto.pinned.length >= 3) state.pareto.pinned.shift();
  state.pareto.pinned.push(point);
  renderParetoCompare();
}

function clearParetoPins() {
  state.pareto.pinned = [];
  renderParetoCompare();
}

function renderParetoCompare() {
  const compare = $('pareto-compare');
  compare.replaceChildren();
  const pinned = state.pareto.pinned || [];
  $('pareto-clear-pins').disabled = pinned.length === 0;
  $('pareto-compare-pinned').disabled = pinned.length < 2;
  if (!pinned.length) {
    const hint = document.createElement('p');
    hint.className = 'hint';
    hint.textContent = 'Pin up to three members to compare their metric vectors.';
    compare.append(hint);
    return;
  }
  const data = state.pareto.data;
  if (!data) return;
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  const first = document.createElement('th');
  first.textContent = 'Dimension';
  headRow.append(first);
  for (const point of pinned) {
    const cell = document.createElement('th');
    cell.textContent = point.key;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement('tbody');
  for (const dimension of data.dimensions || []) {
    const row = document.createElement('tr');
    const label = document.createElement('td');
    label.textContent = dimension;
    row.append(label);
    for (const point of pinned) {
      const cell = document.createElement('td');
      cell.textContent = compareNumber(dimension === 'objective' ? point.objective : point.metrics?.[dimension]);
      row.append(cell);
    }
    body.append(row);
  }
  table.append(head, body);
  compare.append(table);
}

function addPromotedRunOption(runId) {
  const select = $('run');
  if (!select) return;
  if (![...select.options].some((option) => option.value === runId)) {
    const option = document.createElement('option');
    option.value = runId;
    option.textContent = `${runId} (portfolio member)`;
    select.append(option);
  }
  select.value = runId;
}

async function promoteParetoMember(point) {
  const artifact = state.pareto.artifact;
  if (!artifact || !point?.key) throw new Error('no portfolio member is selected');
  const response = await fetch(
    `api/search/${encodeURIComponent(artifact)}/members/${encodeURIComponent(point.key)}/promote`,
    { method: 'POST', headers: { accept: 'application/json' } }
  );
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `promotion failed (${response.status})`);
  return payload;
}

async function openParetoRun() {
  const point = (state.pareto.data?.points || []).find((item) => item.key === state.pareto.selected);
  if (!point) return;
  const button = $('pareto-open-run');
  button.disabled = true;
  $('pareto-status').textContent = 'promoting member…';
  try {
    const body = await promoteParetoMember(point);
    addPromotedRunOption(body.run_id);
    stopRunWatch();
    stopPeriodPlay();
    state.live.active = false;
    state.live.display = 'live';
    state.live.schedule = new Map();
    state.mapTotals = null;
    state.run = body.run_id;
    state.selectedBlock = null;
    state.selectedGeometry = null;
    $('detail').replaceChildren();
    setWorkspace('map', { sync: false, activate: false });
    await loadRunContext();
    await attachLiveRun(body.run_id);
    updateUrl();
    const data = state.pareto.data;
    $('pareto-status').textContent = data
      ? `${data.points.length} members · ${data.front_size} exact front · ${data.failed} failed`
      : 'opened portfolio member';
    showToast(`opened ${body.run_id}`);
  } catch (error) {
    $('pareto-status').textContent = `promotion failed: ${error.message}`;
    showToast(`could not open the member: ${error.message}`, true);
  } finally {
    button.disabled = false;
  }
}

async function compareParetoPinned() {
  const pinned = state.pareto.pinned || [];
  if (pinned.length < 2) return;
  const button = $('pareto-compare-pinned');
  button.disabled = true;
  $('pareto-status').textContent = 'promoting pinned members…';
  try {
    const ids = [];
    for (const point of pinned.slice(0, 2)) {
      const body = await promoteParetoMember(point);
      addPromotedRunOption(body.run_id);
      ids.push(body.run_id);
    }
    state.run = ids[0];
    $('run').value = ids[0];
    state.workspace = 'results';
    state.subview.results = 'comparison';
    syncNavigation();
    syncCompareRuns();
    $('compare-a').value = ids[0];
    $('compare-b').value = ids[1];
    updateUrl();
    activateSubView();
    showToast(`comparing ${ids[0]} and ${ids[1]}`);
  } catch (error) {
    $('pareto-status').textContent = `comparison failed: ${error.message}`;
    showToast(`could not compare the members: ${error.message}`, true);
  } finally {
    button.disabled = false;
  }
}

function openParetoSchedule() {
  const selected = state.pareto.selected;
  if (!selected || !state.pareto.artifact) return;
  const point = (state.pareto.data?.points || []).find((item) => item.key === selected);
  if (!point?.schedule) return;
  window.open(searchFileUrl(state.pareto.artifact, point.schedule), '_blank', 'noopener');
}

function resetParetoView() {
  const chart = state.pareto.chart;
  if (!chart) return;
  chart.camera.position.set(2.8, 2.2, 2.9);
  chart.controls.target.set(0, 0, 0);
  chart.controls.update();
}

function wirePareto() {
  if (!$('pareto-artifact')) return;
  $('pareto-artifact').addEventListener('change', () => loadParetoSpace($('pareto-artifact').value));
  $('pareto-refresh').addEventListener('click', () => loadParetoArtifacts($('pareto-artifact').value));
  $('pareto-reset').addEventListener('click', resetParetoView);
  $('pareto-search').addEventListener('click', () => {
    setWorkspace('results');
    setSubView('results', 'search');
  });
  $('pareto-pin').addEventListener('click', pinParetoPoint);
  $('pareto-clear-pins').addEventListener('click', clearParetoPins);
  $('pareto-open').addEventListener('click', openParetoSchedule);
  $('pareto-open-run').addEventListener('click', openParetoRun);
  $('pareto-compare-pinned').addEventListener('click', compareParetoPinned);
  for (const id of ['pareto-x', 'pareto-y', 'pareto-z', 'pareto-colour', 'pareto-size', 'pareto-opacity', 'pareto-filter-dim', 'pareto-dominance']) {
    $(id).addEventListener('change', drawParetoCloud);
  }
  $('pareto-epsilon').addEventListener('change', drawParetoCloud);
  $('pareto-member').addEventListener('change', () => {
    if ($('pareto-member').value) selectParetoPoint($('pareto-member').value);
  });
  $('pareto-filter').addEventListener('input', () => {
    const value = Number($('pareto-filter').value) / 100;
    $('pareto-filter-value').textContent = value <= 0 ? 'all' : `>= ${value.toFixed(2)}`;
    drawParetoCloud();
  });
}

async function deleteSearchArtifact() {
  const id = $('search-select').value;
  if (!id || !window.confirm(`Delete portfolio artifact ${id}?`)) return;
  $('search-run-status').textContent = `deleting ${id}…`;
  try {
    await api(`api/search/${encodeURIComponent(id)}`, { method: 'DELETE' });
    await loadSearch();
    $('search-run-status').textContent = `deleted ${id}`;
  } catch (error) {
    $('search-run-status').textContent = `delete failed: ${error.message}`;
  }
}

async function cleanFailedArtifacts() {
  try {
    const artifacts = await api('api/search');
    const failed = artifacts.filter(
      (artifact) => artifact.kind === 'portfolio' && artifact.usable === false
    );
    if (!failed.length) {
      $('search-run-status').textContent = 'no failed portfolio artifacts to clean';
      return;
    }
    if (!window.confirm(`Delete ${failed.length} failed portfolio artifact(s)?`)) return;
    for (const artifact of failed) {
      await api(`api/search/${encodeURIComponent(artifact.id)}`, { method: 'DELETE' });
    }
    await loadSearch();
    $('search-run-status').textContent = `deleted ${failed.length} failed artifact(s)`;
  } catch (error) {
    $('search-run-status').textContent = `cleanup failed: ${error.message}`;
  }
}

async function deletePromotedRun() {
  if (!state.runSource || !state.run) return;
  if (!window.confirm(`Delete promoted run ${state.run}?`)) return;
  try {
    await api(`api/runs/${encodeURIComponent(state.run)}`, { method: 'DELETE' });
    window.location.reload();
  } catch (error) {
    showToast(`could not delete promoted run: ${error.message}`, true);
  }
}

async function startPortfolio() {
  const status = $('search-run-status');
  const vary = $('portfolio-vary').value.trim();
  if (!vary) {
    status.textContent = 'portfolio: enter an account and factors';
    return;
  }
  status.textContent = 'portfolio: starting…';
  try {
    const body = await api('api/search/portfolio', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        vary,
        metrics: $('portfolio-metrics').value.trim(),
        directions: $('portfolio-directions').value.trim(),
        mode: $('portfolio-mode').value,
        max_members: Number($('portfolio-max-members').value || 64),
        workers: Number($('portfolio-workers').value || 1),
        sample_seed: Number($('portfolio-sample-seed').value || 1),
        seeds: $('portfolio-seeds').value.trim() || '1',
        iterations: Number($('portfolio-iterations').value || 20),
        years: Number($('portfolio-years').value || 50),
        engine: $('portfolio-engine').value,
        target_mode: $('portfolio-target-mode').value,
        use_initial_schedule: $('portfolio-initial').checked,
        ...(state.portfolioTargets.length ? { targets: state.portfolioTargets } : {}),
      }),
    });
    status.textContent = `portfolio ${body.id} · running`;
    await waitSearch(body.id);
  } catch (error) {
    status.textContent = `portfolio not started: ${error.message}`;
  }
}

async function startTune() {
  const status = $('search-run-status');
  let space;
  try {
    space = JSON.parse($('tune-space').value || '{}');
  } catch (error) {
    status.textContent = `tuner: space is not valid JSON (${error.message})`;
    return;
  }
  status.textContent = 'tuner: starting…';
  try {
    const body = await api('api/search/tune', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        space,
        mode: $('tune-mode').value,
        budget: Number($('tune-budget').value || 8),
        seeds: $('tune-seeds').value.trim() || '1',
        iterations: Number($('tune-iterations').value || 20),
        years: Number($('tune-years').value || 50),
      }),
    });
    status.textContent = `tuner ${body.id} · running`;
    await waitSearch(body.id);
  } catch (error) {
    status.textContent = `tuner not started: ${error.message}`;
  }
}

function snapshotValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.abs(value) >= 1000
      ? value.toLocaleString(undefined, { maximumFractionDigits: 2 })
      : value.toFixed(3).replace(/\.?0+$/, '');
  }
  return String(value);
}

function renderRunSnapshot(summary) {
  const section = $('run-snapshot');
  const host = $('snapshot-cards');
  const empty = $('snapshot-empty');
  if (!section || !host || !empty) return;
  host.replaceChildren();
  if (!summary || typeof summary !== 'object') {
    section.hidden = false;
    empty.hidden = false;
    return;
  }
  const endingAccounts = summary.ending_inventory?.accounts;
  const cards = [
    ['Status', summary.status],
    ['Objective', summary.incumbent_objective ?? summary.objective],
    ['Verified', summary.verified_objective],
    ['Exact replay', summary.exact_match],
    ['Generations', summary.generations],
    ['Evaluations', summary.evaluations],
    ['Wall time', typeof summary.seconds === 'number' ? `${summary.seconds.toFixed(1)} s` : null],
    ['Blocks scheduled', summary.blocks_scheduled],
    ['Seed', summary.seed],
    ['Profile', summary.profile],
    ['Ending accounts', endingAccounts && typeof endingAccounts === 'object' ? Object.keys(endingAccounts).length : null],
  ].filter(([, value]) => value !== null && value !== undefined && value !== '');
  section.hidden = cards.length === 0;
  empty.hidden = cards.length > 0;
  for (const [label, value] of cards) {
    const card = document.createElement('article');
    card.className = 'snapshot-card';
    const name = document.createElement('span');
    name.className = 'snapshot-label';
    name.textContent = label;
    const number = document.createElement('strong');
    number.textContent = snapshotValue(value);
    card.append(name, number);
    host.append(card);
  }
}

function renderEndingSummary(summary, targets) {
  const section = $('ending-summary');
  const ending = summary?.ending_inventory;
  const accounts = ending?.accounts ?? {};
  const names = Object.keys(accounts).sort();
  if (!names.length) {
    section.hidden = true;
    return;
  }
  section.hidden = false;
  const offset = Number(ending.offset);
  $('ending-year').textContent = Number.isFinite(offset) && offset >= 0
    ? `· year ${offset + 1}`
    : '';
  const body = $('ending-table').querySelector('tbody');
  body.replaceChildren();
  for (const name of names) {
    const tr = document.createElement('tr');
    const account = document.createElement('td');
    account.className = 'account';
    account.textContent = name;
    account.title = name;
    const value = document.createElement('td');
    value.className = 'num';
    value.textContent = compareNumber(accounts[name]);
    tr.append(account, value);
    body.append(tr);
  }
  const order = { below: 3, above: 3, met: 2, inactive: 1 };
  const flow = new Map();
  for (const row of targets ?? []) {
    const kind = String(row.kind ?? '');
    if (!kind.startsWith('flow.')) continue;
    const key = `${row.account}|${kind}`;
    const previous = flow.get(key);
    if (!previous || (order[row.status] ?? 0) > (order[previous] ?? 0)) flow.set(key, row.status);
  }
  $('ending-flows').textContent = flow.size
    ? `Flow targets: ${[...flow].map(([key, status]) => `${key.replace('|', ' · ')} · ${status}`).join('; ')}`
    : 'No flow targets configured.';
}

function renderCompareEnding(summaryA, summaryB) {
  const table = $('compare-ending');
  const empty = $('compare-ending-empty');
  const body = table.querySelector('tbody');
  body.replaceChildren();
  const endingA = summaryA?.ending_inventory;
  const endingB = summaryB?.ending_inventory;
  const a = endingA?.accounts ?? {};
  const b = endingB?.accounts ?? {};
  const names = [...new Set([...Object.keys(a), ...Object.keys(b)])].sort();
  if (!names.length) {
    table.hidden = true;
    empty.hidden = false;
    empty.textContent = 'ending inventory is unavailable for these runs';
    $('compare-ending-label').textContent = '';
    return;
  }
  empty.hidden = true;
  table.hidden = false;
  const year = (ending) => {
    const offset = Number(ending?.offset);
    return Number.isFinite(offset) && offset >= 0 ? `year ${offset + 1}` : 'unknown';
  };
  $('compare-ending-label').textContent = `· A ${year(endingA)} · B ${year(endingB)}`;
  for (const name of names) {
    const tr = document.createElement('tr');
    const account = document.createElement('td');
    account.className = 'account';
    account.textContent = name;
    account.title = name;
    tr.append(account);
    for (const value of [a[name], b[name]]) {
      const td = document.createElement('td');
      td.className = 'num';
      td.textContent = value === undefined ? '—' : compareNumber(value);
      tr.append(td);
    }
    const delta = document.createElement('td');
    delta.className = 'num';
    const value = (b[name] ?? 0) - (a[name] ?? 0);
    delta.textContent = `${value > 0 ? '+' : ''}${compareNumber(value)}`;
    if (value > 0) delta.classList.add('compare-delta-positive');
    if (value < 0) delta.classList.add('compare-delta-negative');
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
    const [accountsA, accountsB, targetsA, targetsB, summaryA, summaryB] = await Promise.all([
      api(`api/runs/${encodeURIComponent(runA)}/accounts?year=${state.year}`),
      api(`api/runs/${encodeURIComponent(runB)}/accounts?year=${state.year}`),
      api(`api/runs/${encodeURIComponent(runA)}/targets`),
      api(`api/runs/${encodeURIComponent(runB)}/targets`),
      api(`api/runs/${encodeURIComponent(runA)}/summary`),
      api(`api/runs/${encodeURIComponent(runB)}/summary`),
    ]);
    if (token !== state.compareToken) return;
    // The report tables do not depend on the map, so show them before the slower map request.
    renderCompareTargets(targetsA, targetsB);
    renderCompareEnding(summaryA, summaryB);
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
    $('compare-summary').textContent = 'loading comparison map…';
    const period = currentPeriod();
    const end = period ? Number(period.end) : state.year;
    const query = `year=${end}${period ? `&period_start=${period.start}` : ''}`;
    if (state.mapEngine === 'maplibre' && state.mapLibre) {
      const base = new URL('.', document.baseURI).href;
      const tileUrl = `${base}api/runs/${encodeURIComponent(runA)}/compare-tiles/{z}/{x}/{y}.mvt?against=${encodeURIComponent(runB)}&${query}&v=${TILE_VERSION}`;
      state.vectorActive = true;
      state.features = [];
      state.compare = { a: runA, b: runB, blocks: new Map() };
      ensureVectorSource(tileUrl);
      updateVectorPaint();
      const stats = await api(`api/runs/${encodeURIComponent(runA)}/compare-stats?against=${encodeURIComponent(runB)}&${query}`);
      if (token !== state.compareToken) return;
      $('compare-summary').textContent =
        `period ${state.periodIndex + 1} · A only ${Number(stats.a_only).toLocaleString()} · B only ${Number(stats.b_only).toLocaleString()} · both ${Number(stats.both).toLocaleString()} · neither ${Number(stats.neither).toLocaleString()}`
        + (accountsB.length ? '' : ' · B has no account values at this year');
      $('compare-year').textContent = `period ${state.periodIndex + 1} (${state.year})`;
      statusLine(`${Number(stats.total_features).toLocaleString()} blocks · ${runA} vs ${runB} · period ${state.periodIndex + 1}`);
      return;
    }
    const [mapA, mapB] = await Promise.all([
      api(`api/runs/${encodeURIComponent(runA)}/map?year=${state.year}${periodQuery()}${state.mapEngine === 'maplibre' ? '&format=wgs84' : ''}`),
      api(`api/runs/${encodeURIComponent(runB)}/map?year=${state.year}${periodQuery()}${state.mapEngine === 'maplibre' ? '&format=wgs84' : ''}`),
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
      `period ${state.periodIndex + 1} · A only ${aOnly.toLocaleString()} · B only ${bOnly.toLocaleString()} · both ${both.toLocaleString()} · neither ${neither.toLocaleString()}`
      + (accountsB.length ? '' : ' · B has no account values at this year');
    $('compare-year').textContent = `period ${state.periodIndex + 1} (${state.year})`;
    statusLine(`${state.features.length.toLocaleString()} blocks · ${runA} vs ${runB} · period ${state.periodIndex + 1}`);
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
  if (state.lidarField) {
    const field = lidarFieldInfo(state.lidarField);
    return field ? `LiDAR: ${field.label}` : 'LiDAR';
  }
  if (state.layerMode === 'compartments') return 'Spread compartments';
  if (state.layerMode === 'base' && state.baseAttribute) {
    const info = baseAttributeInfo(state.baseAttribute);
    return `Base: ${info?.label ?? state.baseAttribute}`;
  }
  if (state.compareView && state.compare) return 'Treated in A or B';
  if (state.layerMode === 'cumulative') return 'Treated through the period';
  if (state.layerMode === 'patches') return 'Patches in the year';
  return 'Treated in the period';
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
  const detailsGroup = (title) => {
    const box = document.createElement('details');
    box.className = 'layer-group';
    const heading = document.createElement('summary');
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
  addMode('current', 'Current period', Boolean(info.treatments) && layers.includes('treatments'));
  addMode('cumulative', 'Cumulative through period', Boolean(info.cumulative) && layers.includes('treatments'));
  addMode('patches', 'Patch size class', Boolean(info.patches) && layers.includes('patches'));
  addMode('compartments', 'Spread compartments', Boolean(info.compartments) && layers.includes('compartments'));
  const engineGroup = detailsGroup('Map engine');
  for (const [value, label, enabled] of [
    ['maplibre', 'MapLibre (WebGL)', typeof window.maplibregl !== 'undefined'],
    ['svg', 'SVG (fallback)', true],
  ]) {
    const wrapper = document.createElement('label');
    wrapper.className = `layer-option${enabled ? '' : ' disabled'}`;
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'map-engine';
    input.value = value;
    input.checked = state.mapEngine === value;
    input.disabled = !enabled;
    input.addEventListener('change', () => setMapEngine(value));
    const text = document.createElement('span');
    text.textContent = label;
    wrapper.append(input, text);
    engineGroup.append(wrapper);
  }
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
        if (state.showRoads && !state.roads.length) await loadSourceRoads();
        else renderRoads();
        input.checked = state.showRoads;
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
    const unavailable = detailsGroup('Unavailable layers');
    for (const [label, available, reason] of [
      ['Used roads (run)', info.used_roads, info.used_roads_reason],
      ['Spread compartments', info.compartments, info.compartments_reason],
    ]) {
      if (available) continue;
      const line = document.createElement('p');
      line.className = 'hint layer-unavailable';
      line.textContent = `${label}: ${reason ?? 'not written by this run'}`;
      unavailable.append(line);
    }
  }
  if (!info.treatments && !info.patches) {
    const note = document.createElement('p');
    note.className = 'hint';
    note.textContent = 'only the block geometry is available';
    tree.append(note);
  }
}

function lidarMetaRow(label, value) {
  const row = document.createElement('div');
  row.className = 'lidar-row';
  const key = document.createElement('span');
  key.textContent = label;
  const text = document.createElement('span');
  text.textContent = value === undefined || value === null || value === '' ? '—' : String(value);
  row.append(key, text);
  return row;
}

async function loadLidar() {
  const status = $('lidar-status');
  const meta = $('lidar-meta');
  const select = $('lidar-field');
  if (!status || !meta || !select) return;
  try {
    const info = await api('api/lidar');
    state.lidar = info;
    meta.replaceChildren();
    if (!info.available) {
      state.lidarField = '';
      state.lidarRange = null;
      select.replaceChildren(new Option('Off', ''));
      select.disabled = true;
      status.textContent = 'this dataset has no registered LiDAR fields';
      $('lidar-empty').hidden = false;
      $('lidar-hint').hidden = true;
      $('lidar-field-label').hidden = true;
      renderLidarLegend();
      renderLidarCoverage();
      syncNavigation();
      return;
    }
    select.disabled = false;
    $('lidar-empty').hidden = true;
    $('lidar-hint').hidden = false;
    $('lidar-field-label').hidden = false;
    status.textContent = `${info.fields.length} block fields · ${Number(info.total_blocks ?? info.block_count ?? 0).toLocaleString()} blocks in the dataset`;
    for (const [label, value] of [
      ['Bundle', info.bundle_id],
      ['Version', info.bundle_version],
      ['Source', info.source_id],
      ['Licence', info.licence_id],
      ['CRS', info.native_crs],
      ['Products', (info.products ?? []).join(', ')],
      ['Registered', info.registered_utc],
    ]) {
      meta.append(lidarMetaRow(label, value));
    }
    const current = info.fields.some((field) => field.name === state.lidarField)
      ? state.lidarField
      : '';
    state.lidarField = current;
    select.replaceChildren(new Option('Off', ''));
    for (const field of info.fields) {
      const option = document.createElement('option');
      option.value = field.name;
      option.textContent = `${field.label}${field.unit ? ` (${field.unit})` : ''}`;
      select.append(option);
    }
    select.value = current;
    updateLidarRange();
    renderLidarCoverage();
    syncNavigation();
  } catch (error) {
    state.lidar = null;
    state.lidarField = '';
    select.disabled = true;
    select.replaceChildren(new Option('Off', ''));
    meta.replaceChildren();
    status.textContent = `LiDAR unavailable: ${error.message}`;
    $('lidar-empty').hidden = false;
    $('lidar-empty').textContent = `LiDAR unavailable: ${error.message}`;
    $('lidar-hint').hidden = true;
    $('lidar-field-label').hidden = true;
    renderLidarLegend();
    renderLidarCoverage();
    syncNavigation();
  }
}

const CARBON_ACCOUNT_LABELS = {
  'carbon.biomass.total': 'Biomass carbon',
  'carbon.co2e.ecosystem.total': 'Ecosystem CO₂e',
  'carbon.co2e.flux.net': 'Net ecosystem CO₂e flux',
  'carbon.co2e.products.total': 'Harvested product CO₂e',
  'carbon.dom.total': 'Dead organic matter carbon',
  'carbon.ecosystem.total': 'Ecosystem carbon',
  'carbon.flux.decay': 'Heterotrophic respiration',
  'carbon.flux.disturbance': 'Disturbance emissions',
  'carbon.flux.net': 'Net ecosystem exchange',
  'carbon.flux.npp': 'Net primary production',
  'carbon.products.total': 'Harvested product carbon',
  'carbon.stock.change': 'Carbon stock change',
};
const CARBON_GROUP_COLORS = ['#0072b2', '#e69f00', '#009e73', '#cc79a7', '#56b4e9', '#d55e00', '#f0e442', '#4d4d4d'];

function carbonAccountLabel(name) {
  if (CARBON_ACCOUNT_LABELS[name]) return CARBON_ACCOUNT_LABELS[name];
  const stem = String(name).replace(/^carbon\./, '').replaceAll('.', ' ');
  return stem.charAt(0).toUpperCase() + stem.slice(1);
}

function carbonAccountUnit(name) {
  const flux = String(name).includes('.flux.') || String(name) === 'carbon.stock.change';
  if (String(name).includes('co2e')) return flux ? 'tCO2e/yr' : 'tCO2e';
  return flux ? 'tC/yr' : 'tC';
}

function carbonValue(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function carbonCompact(value) {
  const number = Number(value);
  const abs = Math.abs(number);
  if (abs >= 1e9) return `${(number / 1e9).toFixed(3)}B`;
  if (abs >= 1e6) return `${(number / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(number / 1e3).toFixed(1)}k`;
  return number.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function carbonAxisTick(value, span) {
  const abs = Math.abs(Number(value));
  const divisor = abs >= 1e9 ? 1e9 : abs >= 1e6 ? 1e6 : abs >= 1e3 ? 1e3 : 1;
  const suffix = divisor === 1e9 ? 'B' : divisor === 1e6 ? 'M' : divisor === 1e3 ? 'k' : '';
  const step = Math.abs(Number(span)) / divisor;
  const decimals = step >= 100 ? 0 : step >= 10 ? 1 : step >= 1 ? 2 : 3;
  return `${(Number(value) / divisor).toFixed(decimals)}${suffix}`;
}

function hideCarbonTooltip() {
  const tooltip = $('carbon-tooltip');
  if (tooltip) tooltip.hidden = true;
}

function carbonAccount() {
  return (state.carbon?.accounts ?? []).find((account) => account.account === state.carbonAccount) ?? null;
}

function drawCarbonChart() {
  const svg = $('carbon-chart');
  if (!svg) return;
  const tooltip = $('carbon-tooltip');
  const title = $('carbon-chart-title');
  const current = $('carbon-chart-current');
  const note = $('carbon-chart-note');
  svg.replaceChildren();
  hideCarbonTooltip();
  const account = carbonAccount();
  const points = (account?.values ?? [])
    .map((point) => ({ offset: Number(point.offset), value: Number(point.value) }))
    .filter((point) => Number.isFinite(point.offset) && Number.isFinite(point.value));
  const label = account ? carbonAccountLabel(account.account) : 'Carbon account';
  const unit = account ? carbonAccountUnit(account.account) : '';
  if (title) title.textContent = `${label}${unit ? ` · ${unit}` : ''}`;
  svg.setAttribute('aria-label', `${label}${unit ? ` trend in ${unit}` : ' trend'}`);
  if (!points.length) {
    svg.hidden = true;
    if (current) current.textContent = '';
    if (note) note.textContent = account ? 'No account values in this run.' : 'Choose a carbon account.';
    return;
  }
  svg.hidden = false;
  const width = 480;
  const height = 230;
  const left = 64;
  const right = 18;
  const top = 24;
  const bottom = 38;
  const xs = points.map((point) => point.offset);
  const ys = points.map((point) => point.value);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  let minY = Math.min(...ys);
  let maxY = Math.max(...ys);
  if (minY === maxY) {
    const span = Math.abs(minY) * 0.05 || 1;
    minY -= span;
    maxY += span;
  } else {
    const span = (maxY - minY) * 0.08;
    minY -= span;
    maxY += span;
    if (Math.min(...ys) >= 0 && minY < 0) minY = 0;
    if (Math.max(...ys) <= 0 && maxY > 0) maxY = 0;
  }
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  const x = (value) => left + ((value - minX) / xSpan) * (width - left - right);
  const y = (value) => height - bottom - ((value - minY) / ySpan) * (height - top - bottom);
  const ns = 'http://www.w3.org/2000/svg';
  const add = (name, attrs, text) => {
    const node = document.createElementNS(ns, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (text !== undefined) node.textContent = text;
    svg.append(node);
    return node;
  };
  const ticks = 4;
  for (let index = 0; index <= ticks; index += 1) {
    const value = minY + (ySpan * index) / ticks;
    const yValue = y(value);
    add('line', { x1: left, x2: width - right, y1: yValue, y2: yValue, class: 'chart-grid' });
    add('text', { x: left - 8, y: yValue + 3, 'text-anchor': 'end', class: 'chart-tick' }, carbonAxisTick(value, ySpan));
  }
  add('line', { x1: left, x2: left, y1: top, y2: height - bottom, class: 'chart-axis' });
  add('line', { x1: left, x2: width - right, y1: height - bottom, y2: height - bottom, class: 'chart-axis' });
  add('text', { x: left - 8, y: top - 8, 'text-anchor': 'end', class: 'chart-tick' }, unit);
  const xTicks = [...new Set([minX, Math.round((minX + maxX) / 2), maxX])];
  for (const value of xTicks) {
    const xValue = x(value);
    add('line', { x1: xValue, x2: xValue, y1: height - bottom, y2: height - bottom + 4, class: 'chart-axis' });
    add('text', { x: xValue, y: height - bottom + 18, 'text-anchor': 'middle', class: 'chart-tick' }, `Year ${value}`);
  }
  const linePath = points.map((point, index) => `${index === 0 ? 'M' : 'L'}${x(point.offset).toFixed(1)},${y(point.value).toFixed(1)}`).join(' ');
  if (points.length > 1) {
    const area = `${linePath} L${x(points.at(-1).offset).toFixed(1)},${height - bottom} L${x(points[0].offset).toFixed(1)},${height - bottom} Z`;
    add('path', { d: area, class: 'chart-area' });
  }
  add('path', { d: linePath, class: 'chart-line', fill: 'none' });
  const wrapper = svg.closest('.carbon-chart-wrap');
  const showTip = (point, target) => {
    if (!tooltip || !wrapper) return;
    const rect = target.getBoundingClientRect();
    const box = wrapper.getBoundingClientRect();
    tooltip.textContent = `Year ${point.offset} · ${carbonValue(point.value)} ${unit}`;
    tooltip.style.left = `${rect.left + rect.width / 2 - box.left}px`;
    tooltip.style.top = `${rect.top - box.top}px`;
    tooltip.hidden = false;
  };
  for (const point of points) {
    const dot = add('circle', {
      cx: x(point.offset),
      cy: y(point.value),
      r: 4,
      class: 'chart-point',
      tabindex: 0,
      role: 'button',
      'aria-label': `Year ${point.offset}: ${carbonValue(point.value)} ${unit}`,
    });
    dot.addEventListener('mouseenter', () => showTip(point, dot));
    dot.addEventListener('focus', () => showTip(point, dot));
    dot.addEventListener('click', () => showTip(point, dot));
    dot.addEventListener('mouseleave', hideCarbonTooltip);
    dot.addEventListener('blur', hideCarbonTooltip);
  }
  if (current) current.textContent = `Latest · year ${points.at(-1).offset}: ${carbonCompact(points.at(-1).value)} ${unit}`;
  if (note) note.textContent = `Hover or tap a point for the exact year and value. Values in ${unit}.`;
}

function renderCarbonComposition() {
  const box = $('carbon-composition');
  const note = $('carbon-composition-note');
  if (!box) return;
  box.replaceChildren();
  const pools = state.carbon?.pools;
  if (!pools?.composition?.length) {
    box.hidden = true;
    if (note) note.hidden = true;
    return;
  }
  box.hidden = false;
  const index = Math.max(0, (pools.timesteps?.length ?? 1) - 1);
  if (note) {
    note.hidden = false;
    note.textContent = `Pools at year ${pools.timesteps?.[index] ?? '—'} · tC`;
  }
  const max = Math.max(...pools.composition.map((group) => Number(group.values[index] ?? 0)), 1);
  pools.composition.forEach((group, order) => {
    const value = Number(group.values[index] ?? 0);
    const row = document.createElement('div');
    row.className = 'carbon-bar-row';
    const label = document.createElement('span');
    label.textContent = group.name;
    const track = document.createElement('span');
    track.className = 'carbon-bar';
    track.style.width = `${Math.max(1, (value / max) * 100)}%`;
    track.style.background = CARBON_GROUP_COLORS[order % CARBON_GROUP_COLORS.length];
    const amount = document.createElement('span');
    amount.textContent = `${carbonCompact(value)} tC`;
    row.append(label, track, amount);
    box.append(row);
  });
}

function renderCarbonCompare() {
  const table = $('carbon-compare');
  const empty = $('carbon-compare-empty');
  const block = $('carbon-gcbm-block');
  if (!table || !empty || !block) return;
  const gcbm = state.carbon?.gcbm;
  table.replaceChildren();
  if (!gcbm || !gcbm.rows?.length) {
    table.hidden = true;
    empty.hidden = false;
    block.hidden = true;
    return;
  }
  block.hidden = false;
  empty.hidden = true;
  table.hidden = false;
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const column of gcbm.columns ?? []) {
    const cell = document.createElement('th');
    cell.textContent = column;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement('tbody');
  for (const row of gcbm.rows.slice(0, 100)) {
    const tr = document.createElement('tr');
    for (const column of gcbm.columns ?? []) {
      const cell = document.createElement('td');
      const value = row[column];
      cell.textContent = typeof value === 'number'
        ? value.toLocaleString(undefined, { maximumFractionDigits: 3 })
        : value ?? '';
      tr.append(cell);
    }
    body.append(tr);
  }
  table.append(head, body);
}

function renderCarbonFiles() {
  const list = $('carbon-files');
  const block = $('carbon-files-block');
  if (!list || !block) return;
  list.replaceChildren();
  const files = state.carbon?.files ?? [];
  block.hidden = files.length === 0;
  for (const file of files) {
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.href = `api/runs/${encodeURIComponent(state.run)}/reports/${encodeURIComponent(file.name)}`;
    link.textContent = `${file.name} (${Number(file.bytes).toLocaleString()} B)`;
    item.append(link);
    list.append(item);
  }
  if (!list.children.length) {
    const item = document.createElement('li');
    item.className = 'hint';
    item.textContent = 'no carbon artifacts';
    list.append(item);
  }
}

function carbonMetaRow(label, value) {
  const row = document.createElement('div');
  row.className = 'lidar-row';
  const key = document.createElement('span');
  key.textContent = label;
  const text = document.createElement('span');
  text.textContent = value === undefined || value === null || value === '' ? '—' : String(value);
  row.append(key, text);
  return row;
}


// AU Explorer (SDMD): read the API, draw the yield and density views, edit constraints.
function sdmdNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function sdmdSvg(id) {
  const svg = $(id);
  if (!svg) return null;
  svg.replaceChildren();
  return svg;
}

function sdmdNode(svg, name, attrs = {}, text = '') {
  const node = document.createElementNS('http://www.w3.org/2000/svg', name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text !== '') node.textContent = text;
  svg.append(node);
  return node;
}

function sdmdScale(value, min, max, start, end) {
  if (!(max > min)) return (start + end) / 2;
  return start + ((value - min) / (max - min)) * (end - start);
}

function sdmdLogTicks(min, max) {
  const ticks = [];
  for (let power = Math.floor(min); power <= Math.ceil(max); power += 1) {
    if (power >= min && power <= max) ticks.push(power);
  }
  return ticks;
}

const SDMD_YIELD_METRICS = {
  volume_m3_ha: { label: 'Volume', unit: 'm³/ha' },
  tph: { label: 'Density', unit: 'TPH' },
  ba_m2_ha: { label: 'Basal area', unit: 'm²/ha' },
  qmd_cm: { label: 'QMD', unit: 'cm' },
  top_height_m: { label: 'Top height', unit: 'm' },
};

function renderSdmdLegend() {
  const legend = $('sdmd-diagram-legend');
  if (!legend) return;
  legend.replaceChildren();
  for (const [kind, text] of [
    ['obs', 'Observed plot'],
    ['env', 'Observed envelope'],
    ['cai', 'CAI density range'],
    ['traj', 'Selected regime path'],
    ['height', 'Top-height isopleth'],
    ['qmd', 'QMD isopleth'],
    ['limit', 'Competition / mortality limit'],
  ]) {
    const item = document.createElement('span');
    item.className = kind;
    item.textContent = text;
    legend.append(item);
  }
}

function renderSdmdYield() {
  const svg = sdmdSvg('sdmd-yield-chart');
  const note = $('sdmd-yield-note');
  const readout = $('sdmd-yield-readout');
  if (!svg) return;
  const metric = state.sdmd.yieldMetric ?? 'volume_m3_ha';
  const spec = SDMD_YIELD_METRICS[metric] ?? SDMD_YIELD_METRICS.volume_m3_ha;
  const rows = (state.sdmd.yield ?? []).filter((row) => !state.sdmd.source || row.source === state.sdmd.source);
  if (!rows.length) {
    if (note) note.textContent = 'No stand summaries for this source.';
    if (readout) readout.textContent = '';
    return;
  }
  const width = 720, height = 260, left = 58, right = 18, top = 18, bottom = 38;
  const ages = rows.map((row) => sdmdNumber(row.age)).filter((value) => value > 0);
  const values = rows.map((row) => sdmdNumber(row[metric])).filter((value) => Number.isFinite(value));
  const minAge = Math.min(...ages), maxAge = Math.max(...ages);
  const maxValue = Math.max(...values, 1);
  const x = (age) => sdmdScale(age, minAge, maxAge, left, width - right);
  const y = (value) => sdmdScale(value, 0, maxValue, height - bottom, top);
  for (let index = 0; index <= 4; index += 1) {
    const value = (maxValue * index) / 4;
    const yValue = y(value);
    sdmdNode(svg, 'line', { x1: left, x2: width - right, y1: yValue, y2: yValue, class: 'sdmd-grid-line' });
    sdmdNode(svg, 'text', { x: left - 6, y: yValue + 3, 'text-anchor': 'end', class: 'sdmd-tick' }, carbonAxisTick(value, maxValue));
  }
  const ageTicks = [...new Set(ages)].sort((a, b) => a - b);
  for (const age of ageTicks) {
    const xValue = x(age);
    sdmdNode(svg, 'line', { x1: xValue, x2: xValue, y1: height - bottom, y2: height - bottom + 4, class: 'sdmd-axis' });
    sdmdNode(svg, 'text', { x: xValue, y: height - bottom + 17, 'text-anchor': 'middle', class: 'sdmd-tick' }, age);
  }
  sdmdNode(svg, 'line', { x1: left, x2: left, y1: top, y2: height - bottom, class: 'sdmd-axis' });
  sdmdNode(svg, 'line', { x1: left, x2: width - right, y1: height - bottom, y2: height - bottom, class: 'sdmd-axis' });
  sdmdNode(svg, 'text', { x: left, y: 11, class: 'sdmd-axis-title' }, `${spec.label} (${spec.unit})`);
  sdmdNode(svg, 'text', { x: width - right, y: height - 6, 'text-anchor': 'end', class: 'sdmd-axis-title' }, 'stand age (years)');
  const ordered = rows.slice().sort((a, b) => sdmdNumber(a.age) - sdmdNumber(b.age));
  const path = ordered
    .map((row, index) => `${index ? 'L' : 'M'}${x(sdmdNumber(row.age)).toFixed(1)},${y(sdmdNumber(row[metric])).toFixed(1)}`)
    .join(' ');
  sdmdNode(svg, 'path', { d: path, class: 'sdmd-yield-line' });
  for (const row of rows) {
    const value = sdmdNumber(row[metric]);
    const dot = sdmdNode(svg, 'circle', {
      cx: x(sdmdNumber(row.age)),
      cy: y(value),
      r: 3.6,
      class: 'sdmd-yield-dot',
    });
    dot.addEventListener('mouseenter', () => {
      if (readout) readout.textContent = `Age ${row.age}: ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${spec.unit} · ${row.tph} TPH · ${row.qmd_cm} cm QMD`;
    });
    dot.addEventListener('mouseleave', () => {
      if (readout) readout.textContent = 'Hover a point for its value.';
    });
    sdmdNode(dot, 'title', {}, `Age ${row.age}: ${value} ${spec.unit}`);
  }
  if (note) note.textContent = `${rows.length} stand summaries; ${spec.label.toLowerCase()} from the stand table.`;
}

function renderSdmdDiagram() {
  const svg = sdmdSvg('sdmd-diagram');
  const note = $('sdmd-diagram-note');
  const readout = $('sdmd-diagram-readout');
  if (!svg) return;
  const points = state.sdmd.points?.points ?? [];
  const envelope = state.sdmd.points?.envelope ?? [];
  const isopleths = state.sdmd.points?.diagram?.isopleths ?? [];
  const caiBand = (state.sdmd.points?.diagram?.cai_band ?? [])
    .map((point) => ({ tph: sdmdNumber(point[0]), volume: sdmdNumber(point[1]) }))
    .filter((point) => point.tph > 0 && point.volume > 0);
  const trajectory = state.sdmd.trajectoryData?.points ?? [];
  const width = 720, height = 420, left = 62, right = 22, top = 20, bottom = 42;
  const all = [
    ...points,
    ...trajectory.map((point) => ({ tph: point[0], mean_tree_volume_m3: point[1] })),
    ...caiBand,
  ]
    .map((point) => ({ tph: sdmdNumber(point.tph), volume: sdmdNumber(point.mean_tree_volume_m3 ?? point.volume) }))
    .filter((point) => point.tph > 0 && point.volume > 0);
  if (!all.length) {
    if (note) note.textContent = 'No SDMD points for this AU.';
    if (readout) readout.textContent = '';
    return;
  }
  const logs = all.map((point) => [Math.log10(point.tph), Math.log10(point.volume)]);
  const minX = Math.min(...logs.map((pair) => pair[0])) - 0.08;
  const maxX = Math.max(...logs.map((pair) => pair[0])) + 0.08;
  const minY = Math.min(...logs.map((pair) => pair[1])) - 0.08;
  const maxY = Math.max(...logs.map((pair) => pair[1])) + 0.08;
  const x = (tph) => sdmdScale(Math.log10(tph), minX, maxX, left, width - right);
  const y = (volume) => sdmdScale(Math.log10(volume), minY, maxY, height - bottom, top);
  if (caiBand.length >= 3) {
    const polygon = caiBand.map((point) => `${x(point.tph).toFixed(1)},${y(point.volume).toFixed(1)}`).join(' ');
    sdmdNode(svg, 'polygon', { points: polygon, class: 'sdmd-cai-band' });
  }
  for (const power of sdmdLogTicks(Math.ceil(minX), Math.floor(maxX))) {
    const xValue = x(10 ** power);
    sdmdNode(svg, 'line', { x1: xValue, x2: xValue, y1: top, y2: height - bottom, class: 'sdmd-grid-line' });
    sdmdNode(svg, 'text', { x: xValue, y: height - bottom + 18, 'text-anchor': 'middle', class: 'sdmd-tick' }, `1e${power}`);
  }
  for (const power of sdmdLogTicks(Math.ceil(minY), Math.floor(maxY))) {
    const yValue = y(10 ** power);
    sdmdNode(svg, 'line', { x1: left, x2: width - right, y1: yValue, y2: yValue, class: 'sdmd-grid-line' });
    sdmdNode(svg, 'text', { x: left - 6, y: yValue + 3, 'text-anchor': 'end', class: 'sdmd-tick' }, `1e${power}`);
  }
  const classes = {
    top_height: 'sdmd-iso-height',
    qmd: 'sdmd-iso-qmd',
    crown_closure: 'sdmd-iso-boundary',
    competition: 'sdmd-iso-limit',
    self_thinning: 'sdmd-iso-limit',
  };
  for (const isopleth of isopleths) {
    const visible = (isopleth.points ?? [])
      .map((point) => [Number(point[0]), Number(point[1])])
      .filter((point) => point[0] > 0 && point[1] > 0)
      .filter((point) => Math.log10(point[0]) >= minX && Math.log10(point[0]) <= maxX && Math.log10(point[1]) >= minY && Math.log10(point[1]) <= maxY);
    if (visible.length < 2) continue;
    const d = visible
      .map((point, index) => `${index ? 'L' : 'M'}${x(point[0]).toFixed(1)},${y(point[1]).toFixed(1)}`)
      .join(' ');
    sdmdNode(svg, 'path', { d, class: classes[isopleth.kind] ?? 'sdmd-iso-boundary' });
    const labelPoint = visible[visible.length - 1];
    if (isopleth.kind === 'top_height' || isopleth.kind === 'qmd') {
      sdmdNode(svg, 'text', { x: x(labelPoint[0]) + 3, y: y(labelPoint[1]) - 3, class: 'sdmd-iso-label' }, `${isopleth.value}${isopleth.unit}`);
    } else if (isopleth.kind === 'crown_closure') {
      sdmdNode(svg, 'text', { x: x(labelPoint[0]) + 3, y: y(labelPoint[1]) - 3, class: 'sdmd-iso-label' }, 'closure');
    } else if (isopleth.kind === 'competition') {
      sdmdNode(svg, 'text', { x: x(labelPoint[0]) + 3, y: y(labelPoint[1]) - 3, class: 'sdmd-iso-label' }, 'competition');
    } else {
      sdmdNode(svg, 'text', { x: x(labelPoint[0]) + 3, y: y(labelPoint[1]) - 3, class: 'sdmd-iso-label' }, 'mortality');
    }
  }
  if (envelope.length >= 3) {
    const polygon = envelope.map((point) => `${x(point[0]).toFixed(1)},${y(point[1]).toFixed(1)}`).join(' ');
    sdmdNode(svg, 'polygon', { points: polygon, class: 'sdmd-envelope' });
  }
  sdmdNode(svg, 'line', { x1: left, x2: left, y1: top, y2: height - bottom, class: 'sdmd-axis' });
  sdmdNode(svg, 'line', { x1: left, x2: width - right, y1: height - bottom, y2: height - bottom, class: 'sdmd-axis' });
  sdmdNode(svg, 'text', { x: left, y: 12, class: 'sdmd-axis-title' }, 'mean tree volume (m³, log scale)');
  sdmdNode(svg, 'text', { x: width - right, y: height - 7, 'text-anchor': 'end', class: 'sdmd-axis-title' }, 'trees per hectare (log scale)');
  for (const point of points) {
    const dot = sdmdNode(svg, 'circle', {
      cx: x(sdmdNumber(point.tph)),
      cy: y(sdmdNumber(point.mean_tree_volume_m3)),
      r: 4.2,
      class: 'sdmd-point',
    });
    dot.addEventListener('mouseenter', () => {
      if (readout) readout.textContent = `${point.tph} TPH · ${point.mean_tree_volume_m3} m³/tree · zone ${point.zone ?? 'unknown'} · age ${point.age ?? '—'}`;
    });
    dot.addEventListener('mouseleave', () => {
      if (readout) readout.textContent = 'Hover a point for its density and zone.';
    });
    sdmdNode(dot, 'title', {}, `${point.tph} TPH, ${point.mean_tree_volume_m3} m³/tree, ${point.zone ?? ''}`);
  }
  if (trajectory.length) {
    const d = trajectory
      .map((point, index) => `${index ? 'L' : 'M'}${x(point[0]).toFixed(1)},${y(point[1]).toFixed(1)}`)
      .join(' ');
    sdmdNode(svg, 'path', { d, class: 'sdmd-trajectory' });
    trajectory.forEach((point, index) => {
      sdmdNode(svg, 'circle', {
        cx: x(point[0]),
        cy: y(point[1]),
        r: 3.4,
        class: 'sdmd-trajectory-dot',
      });
      sdmdNode(svg, 'text', {
        x: x(point[0]) + 5,
        y: y(point[1]) - 5,
        class: 'sdmd-iso-label',
      }, String(index + 1));
    });
  }
  if (note) {
    const status = state.sdmd.trajectoryData?.status;
    const caiNote = caiBand.length ? ' Grey band: source CAI density range (display-only, no numeric level).' : '';
    note.textContent = `Black dots: ${points.length} observed plots. Blue polygon: observed envelope (${envelope.length} vertices).${caiNote} ${trajectory.length ? `Orange dashed: selected regime path (${trajectory.length} points, ${status ?? 'loaded'}).` : 'Pick a trajectory above to draw an orange path.'}`;
  }
}

function renderSdmdInterpretation() {
  const host = $('sdmd-interpretation');
  if (!host) return;
  host.replaceChildren();
  const detail = state.sdmd.detail;
  if (!detail) return;
  const points = state.sdmd.points?.points ?? [];
  const regimes = state.sdmd.regimes ?? [];
  const selected = regimes.find((item) => item.regime_id === state.sdmd.trajectory) ?? null;
  const counts = state.sdmd.preview?.counts ?? {};
  const add = (text) => {
    const item = document.createElement('li');
    item.textContent = text;
    list.append(item);
  };
  const paragraph = document.createElement('p');
  paragraph.textContent = 'The density chart uses logarithmic axes. Black dots are observed plots; the blue polygon is their envelope; the orange dashed line is the selected regime path.';
  host.append(paragraph);
  const list = document.createElement('ul');
  add(`Observed support: ${detail.plot_count} plots, ${detail.visit_count} visits, ages ${detail.age_min ?? '—'}–${detail.age_max ?? '—'}, site index ${detail.site_index_min ?? '—'}–${detail.site_index_max ?? '—'}.`);
  if (points.length >= 3) {
    const tph = points.map((point) => sdmdNumber(point.tph));
    const volume = points.map((point) => sdmdNumber(point.mean_tree_volume_m3));
    add(`Observed range: ${Math.min(...tph)}–${Math.max(...tph)} TPH and ${Math.min(...volume)}–${Math.max(...volume)} m³/tree.`);
  } else {
    add('Not enough observed points for an envelope.');
  }
  if (detail.diagram) {
    add(`Diagram: ${detail.diagram.diagram_id} (${detail.diagram.review_status}); ${detail.diagram.source.kind} source.`);
    if (detail.diagram.source.kind === 'synthetic') {
      add('This is an illustrative fixture, not a published digitisation. Use it to test the method, not to make a silvicultural decision.');
    }
  } else {
    add('No diagram is loaded, so placement and zones are unavailable.');
  }
  if (selected) {
    const verdict = selected.allowed ? 'allowed' : 'denied';
    const reason = (selected.findings ?? []).map((finding) => finding.message).join('; ');
    add(`Selected regime ${selected.regime_id}: ${verdict}${reason ? ` — ${reason}` : ''}.`);
    if (!selected.trajectory_available) {
      add('No stored trajectory exists for this regime, so the chart shows only the observed envelope.');
    } else if (state.sdmd.trajectoryData) {
      add(`Stored path: ${state.sdmd.trajectoryData.points?.length ?? 0} points, ${state.sdmd.trajectoryData.status}.`);
    }
  } else {
    add('No regime is selected. The trajectory menu lists only paths that exist; unavailable regimes are disabled.');
  }
  add(`Options: ${counts.regimes_before ?? '—'} → ${counts.regimes_after ?? '—'} regimes and ${counts.entries_before ?? '—'} → ${counts.entries_after ?? '—'} entries.`);
  host.append(list);
  const gaps = detail.data_gaps ?? [];
  if (gaps.length) {
    const heading = document.createElement('p');
    heading.innerHTML = '<strong>Data gaps</strong>';
    host.append(heading);
    const gapList = document.createElement('ul');
    for (const gap of gaps) {
      const item = document.createElement('li');
      item.textContent = gap;
      gapList.append(item);
    }
    host.append(gapList);
  }
}

function renderSdmdRegimePaths() {
  const host = $('sdmd-regime-paths');
  if (!host) return;
  host.replaceChildren();
  const selected = (state.sdmd.regimes ?? []).find((item) => item.regime_id === state.sdmd.trajectory);
  if (!selected) {
    host.textContent = 'Choose a regime in the trajectory menu. Only regimes with a stored path are selectable.';
    return;
  }
  const lines = [
    `Entry type: ${selected.entry_type}`,
    `Entry ages: ${(selected.entry_ages ?? []).join(', ') || 'none'}`,
    `Entries: ${selected.entry_count}`,
    `Removal fraction: ${selected.removal_fraction}`,
    `Even-aged SDMD valid: ${selected.sdmd_valid ? 'yes' : 'no'}`,
  ];
  const list = document.createElement('ul');
  for (const line of lines) {
    const item = document.createElement('li');
    item.textContent = line;
    list.append(item);
  }
  host.append(list);
  const verdict = document.createElement('p');
  const badge = document.createElement('span');
  badge.className = `sdmd-verdict ${selected.allowed ? 'allowed' : 'denied'}`;
  badge.textContent = selected.allowed ? 'Allowed' : 'Denied';
  verdict.append(badge);
  host.append(verdict);
  const findings = selected.findings ?? [];
  if (findings.length) {
    const findingsList = document.createElement('ul');
    for (const finding of findings) {
      const item = document.createElement('li');
      item.textContent = `${finding.code}: ${finding.message}`;
      findingsList.append(item);
    }
    host.append(findingsList);
  }
  const path = document.createElement('p');
  if (selected.trajectory_available && state.sdmd.trajectoryData) {
    const data = state.sdmd.trajectoryData;
    path.textContent = `Stored path: ${data.points?.length ?? 0} points, ${data.status}. The orange dashed line on the chart is this path; “extrapolated” means at least one point lies outside the observed envelope.`;
  } else if (selected.trajectory_available) {
    path.textContent = 'A trajectory file exists; choose it above to draw and assess it.';
  } else {
    path.textContent = 'No stored trajectory for this regime. The chart shows only the observed envelope.';
  }
  host.append(path);
}

function renderSdmdProvenance() {
  const host = $('sdmd-provenance');
  if (!host) return;
  host.replaceChildren();
  const detail = state.sdmd.detail;
  if (!detail) return;
  const list = document.createElement('dl');
  const add = (label, value) => {
    const term = document.createElement('dt');
    term.textContent = label;
    const definition = document.createElement('dd');
    definition.textContent = value;
    list.append(term, definition);
  };
  add('Plots', `${detail.plot_count ?? 0} plots, ${detail.visit_count ?? 0} visits`);
  add('Age support', `${detail.age_min ?? '—'}–${detail.age_max ?? '—'} years`);
  add('Leading species', (detail.leading_species ?? []).join(', ') || '—');
  add('Sources', (detail.sources ?? []).join(', ') || '—');
  const diagram = detail.diagram;
  add('Diagram', diagram ? `${diagram.diagram_id} (${diagram.review_status})` : 'none');
  if (diagram) add('Diagram source', `${diagram.source.citation} · ${diagram.source.version}`);
  host.append(list);
  const gaps = detail.data_gaps ?? [];
  if (gaps.length) {
    const heading = document.createElement('h4');
    heading.textContent = 'Data gaps';
    const ul = document.createElement('ul');
    for (const gap of gaps) {
      const item = document.createElement('li');
      item.textContent = gap;
      ul.append(item);
    }
    host.append(heading, ul);
  }
}

function renderSdmdRegimeEditor() {
  const host = $('sdmd-regime-editor');
  if (!host) return;
  host.replaceChildren();
  const regimes = state.sdmd.regimes ?? [];
  if (!regimes.length) {
    const empty = document.createElement('p');
    empty.className = 'hint';
    empty.textContent = 'No regimes for this AU.';
    host.append(empty);
    return;
  }
  for (const regime of regimes) {
    const constraint = regime.constraint ?? {};
    const row = document.createElement('div');
    row.className = `sdmd-regime-row${constraint.allowed === false ? ' denied' : ''}`;
    row.dataset.regime = regime.regime_id;
    const name = document.createElement('label');
    name.className = 'sdmd-regime-name';
    const enabled = document.createElement('input');
    enabled.type = 'checkbox';
    enabled.dataset.field = 'allowed';
    enabled.checked = constraint.allowed !== false;
    const text = document.createElement('span');
    text.textContent = `${regime.regime_id} · ${regime.entry_type}${regime.sdmd_valid ? '' : ' · outside SDMD'}`;
    name.append(enabled, text);
    row.append(name);
    const fields = [
      ['min_entry_age', 'Min age', constraint.min_entry_age ?? 0],
      ['max_entry_age', 'Max age', constraint.max_entry_age ?? 0],
      ['max_entries', 'Max entries', constraint.max_entries ?? 0],
      ['min_interval_years', 'Min interval', constraint.min_interval_years ?? 0],
      ['max_removal_fraction', 'Max removal', constraint.max_removal_fraction ?? 0],
    ];
    for (const [field, label, value] of fields) {
      const wrapper = document.createElement('label');
      wrapper.textContent = label;
      const input = document.createElement('input');
      input.type = 'number';
      input.step = field === 'max_removal_fraction' ? '0.01' : '1';
      input.min = '0';
      input.value = String(value);
      input.dataset.field = field;
      wrapper.append(input);
      row.append(wrapper);
    }
    const findings = regime.findings ?? [];
    if (findings.length) {
      const message = document.createElement('div');
      message.className = 'sdmd-regime-findings';
      message.textContent = findings.map((finding) => finding.message).join('; ');
      row.append(message);
    }
    host.append(row);
  }
}

function renderSdmdPreview() {
  const preview = state.sdmd.preview;
  const target = $('sdmd-preview');
  const badge = $('sdmd-preview-badge');
  if (!preview) {
    if (target) target.textContent = '';
    if (badge) badge.hidden = true;
    return;
  }
  const counts = preview.counts ?? {};
  const text = `Options: ${counts.regimes_before} → ${counts.regimes_after} regimes; ${counts.entries_before} → ${counts.entries_after} entries.`;
  if (target) target.textContent = text;
  if (badge) {
    badge.hidden = false;
    badge.textContent = `${counts.regimes_after} regimes / ${counts.entries_after} entries`;
  }
}

function renderSdmd() {
  const detail = state.sdmd.detail;
  if (!detail) return;
  $('sdmd-title').textContent = detail.au_id;
  $('sdmd-subtitle').textContent = `${detail.region} · ${detail.plot_count} plots · ages ${detail.age_min ?? '—'}–${detail.age_max ?? '—'} · ${(detail.leading_species ?? []).join(', ') || 'no species'}`;
  $('sdmd-au-meta').textContent = `${detail.regime_count} regimes · ${detail.constraint_count} saved constraints`;
  const sources = new Set();
  for (const row of state.sdmd.plots ?? []) {
    for (const source of String(row.sources ?? '').split(',')) {
      if (source.trim()) sources.add(source.trim());
    }
  }
  const sourceSelect = $('sdmd-source');
  const currentSource = state.sdmd.source;
  sourceSelect.replaceChildren();
  const allOption = document.createElement('option');
  allOption.value = '';
  allOption.textContent = 'All sources';
  sourceSelect.append(allOption);
  for (const source of [...sources].sort()) {
    const option = document.createElement('option');
    option.value = source;
    option.textContent = source;
    sourceSelect.append(option);
  }
  sourceSelect.value = sources.has(currentSource) ? currentSource : '';
  state.sdmd.source = sourceSelect.value;
  const trajectorySelect = $('sdmd-trajectory');
  const currentTrajectory = state.sdmd.trajectory;
  trajectorySelect.replaceChildren();
  const none = document.createElement('option');
  none.value = '';
  none.textContent = 'No trajectory';
  trajectorySelect.append(none);
  for (const regime of state.sdmd.regimes ?? []) {
    const option = document.createElement('option');
    option.value = regime.regime_id;
    option.textContent = regime.trajectory_available ? regime.regime_id : `${regime.regime_id} (no stored path)`;
    option.disabled = !regime.trajectory_available;
    trajectorySelect.append(option);
  }
  trajectorySelect.value = currentTrajectory;
  const metricSelect = $('sdmd-yield-metric');
  if (metricSelect) metricSelect.value = state.sdmd.yieldMetric ?? 'volume_m3_ha';
  renderSdmdLegend();
  renderSdmdYield();
  renderSdmdDiagram();
  renderSdmdInterpretation();
  renderSdmdRegimePaths();
  renderSdmdProvenance();
  renderSdmdRegimeEditor();
  renderSdmdPreview();
}

async function loadSdmdAvailability() {
  try {
    const payload = await api('api/sdmd/regions');
    state.sdmd.available = true;
    state.sdmd.regions = payload.regions ?? [];
    const select = $('sdmd-region');
    select.replaceChildren();
    const all = document.createElement('option');
    all.value = '';
    all.textContent = 'All regions';
    select.append(all);
    for (const region of state.sdmd.regions) {
      const option = document.createElement('option');
      option.value = region;
      option.textContent = region;
      select.append(option);
    }
    $('sdmd-empty').hidden = true;
    $('sdmd-status').textContent = 'choose an AU';
    await loadSdmdAUs();
    await loadSdmdCoverage();
    syncNavigation();
  } catch (error) {
    state.sdmd.available = false;
    $('sdmd-status').textContent = 'SDMD API not served.';
    $('sdmd-empty').hidden = false;
  }
}

async function loadSdmdCoverage() {
  try {
    const payload = await api('api/sdmd/coverage');
    state.sdmd.coverage = payload.rows ?? [];
    const counts = payload.counts ?? {};
    const reviewed = (counts.reviewed_variant ?? 0) + (counts.reviewed_zone ?? 0);
    $('sdmd-coverage-count').textContent = `${payload.count ?? 0} BEC labels · ${reviewed} reviewed · ${counts.mixed_zone ?? 0} mixed · ${counts.no_diagram ?? 0} gaps`;
    const zones = [...new Set(state.sdmd.coverage.map((row) => row.zone))].sort();
    const zoneSelect = $('sdmd-coverage-zone');
    zoneSelect.replaceChildren();
    for (const zone of zones) {
      const option = document.createElement('option');
      option.value = zone;
      option.textContent = zone;
      zoneSelect.append(option);
    }
    const preferred = state.sdmd.coverage.find((row) => row.bec === 'IDFdk3')?.zone ?? zones[0] ?? '';
    zoneSelect.value = preferred;
    fillSdmdCoverageBecs();
  } catch {
    $('sdmd-coverage-panel').hidden = true;
  }
}

function fillSdmdCoverageBecs() {
  const zone = $('sdmd-coverage-zone').value;
  const rows = state.sdmd.coverage.filter((row) => row.zone === zone);
  const select = $('sdmd-coverage-bec');
  select.replaceChildren();
  for (const row of rows) {
    const option = document.createElement('option');
    option.value = row.bec;
    option.textContent = row.bec;
    select.append(option);
  }
  const preferred = rows.some((row) => row.bec === state.sdmd.coverageBec)
    ? state.sdmd.coverageBec
    : rows.find((row) => row.bec === 'IDFdk3')?.bec ?? rows[0]?.bec ?? '';
  select.value = preferred;
  renderSdmdCoverageDetail();
}

function renderSdmdCoverageDetail() {
  const host = $('sdmd-coverage-detail');
  host.replaceChildren();
  const row = state.sdmd.coverage.find((item) => item.bec === $('sdmd-coverage-bec').value);
  if (!row) {
    host.textContent = 'No current BEC label selected.';
    return;
  }
  state.sdmd.coverageBec = row.bec;
  const title = document.createElement('p');
  const name = document.createElement('strong');
  name.textContent = row.bec;
  const status = document.createElement('span');
  status.className = `sdmd-coverage-status ${row.coverage_status}`;
  status.textContent = row.coverage_status;
  title.append(name, status);
  host.append(title);
  const add = (label, value) => {
    const line = document.createElement('p');
    const prefix = document.createElement('strong');
    prefix.textContent = `${label}: `;
    line.append(prefix, document.createTextNode(value));
    host.append(line);
  };
  add('Zone', `${row.zone} · ${row.zone_name || 'unnamed'}`);
  add('Subzone / variant', `${row.subzone || '—'} / ${row.variant || '—'}`);
  add('Diagrams', row.diagram_ids ? row.diagram_ids.split(';').join(', ') : 'None');
  add('Review counts', `${row.reviewed_count || 0} reviewed / ${row.provisional_count || 0} provisional`);
  add('Species / origin', [row.species, row.origins].filter(Boolean).join(' · ') || 'None');
  add('AU evidence', row.au_ids ? row.au_ids.split(';').join(', ') : 'No AU store for this BEC');
  if (row.gap_reason) add('Gap reason', row.gap_reason);
  if (row.gap_action) add('Next action', row.gap_action);
  add('Note', row.note || '');
}

async function loadSdmdAUs() {
  if (!state.sdmd.available) return;
  const region = $('sdmd-region').value;
  state.sdmd.region = region;
  const query = region ? `?region=${encodeURIComponent(region)}` : '';
  try {
    const payload = await api(`api/sdmd/aus${query}`);
    state.sdmd.aus = payload.aus ?? [];
  } catch (error) {
    $('sdmd-status').textContent = `AU list unavailable: ${error.message}`;
    return;
  }
  const select = $('sdmd-au');
  select.replaceChildren();
  if (!state.sdmd.aus.length) {
    $('sdmd-status').textContent = 'no AUs in this region';
    return;
  }
  for (const au of state.sdmd.aus) {
    const option = document.createElement('option');
    option.value = au.au_id;
    option.textContent = au.au_id;
    select.append(option);
  }
  const preferred = state.sdmd.aus.some((au) => au.au_id === state.sdmd.au)
    ? state.sdmd.au
    : state.sdmd.aus[0].au_id;
  select.value = preferred;
  await loadSdmdAu(preferred);
}

async function loadSdmdAu(auId) {
  const encoded = encodeURIComponent(auId);
  try {
    const [detail, plots, yieldPayload, points, regimes, preview] = await Promise.all([
      api(`api/sdmd/au/${encoded}`),
      api(`api/sdmd/au/${encoded}/plots`),
      api(`api/sdmd/au/${encoded}/yield`),
      api(`api/sdmd/au/${encoded}/sdmd`),
      api(`api/sdmd/au/${encoded}/regimes`),
      api(`api/sdmd/au/${encoded}/constraint-preview`),
    ]);
    state.sdmd.au = auId;
    state.sdmd.detail = detail;
    state.sdmd.plots = plots.plots ?? [];
    state.sdmd.yield = yieldPayload.yield ?? [];
    state.sdmd.points = points;
    state.sdmd.regimes = regimes.regimes ?? [];
    state.sdmd.preview = preview;
    state.sdmd.source = '';
    state.sdmd.trajectory = '';
    state.sdmd.trajectoryData = null;
    $('sdmd-status').textContent = '';
    $('sdmd-au').value = auId;
    renderSdmd();
  } catch (error) {
    $('sdmd-status').textContent = `AU unavailable: ${error.message}`;
  }
}

async function loadSdmdTrajectory() {
  const regimeId = $('sdmd-trajectory').value;
  state.sdmd.trajectory = regimeId;
  state.sdmd.trajectoryData = null;
  if (!regimeId || !state.sdmd.au) {
    $('sdmd-trajectory-status').textContent = '';
    renderSdmdDiagram();
    renderSdmdInterpretation();
    renderSdmdRegimePaths();
    return;
  }
  try {
    const payload = await api(`api/sdmd/au/${encodeURIComponent(state.sdmd.au)}/trajectory?regime_id=${encodeURIComponent(regimeId)}`);
    state.sdmd.trajectoryData = payload;
    $('sdmd-trajectory-status').textContent = payload.status;
  } catch (error) {
    $('sdmd-trajectory-status').textContent = error.message;
  }
  renderSdmdDiagram();
  renderSdmdInterpretation();
  renderSdmdRegimePaths();
}

async function saveSdmdConstraints() {
  if (!state.sdmd.au) return;
  const rows = [...$('sdmd-regime-editor').querySelectorAll('.sdmd-regime-row')];
  const constraints = rows.map((row) => {
    const regimeId = row.dataset.regime;
    const current = (state.sdmd.regimes ?? []).find((item) => item.regime_id === regimeId)?.constraint ?? {};
    const field = (name) => row.querySelector(`[data-field="${name}"]`);
    return {
      au_id: state.sdmd.au,
      regime_id: regimeId,
      allowed: Boolean(field('allowed')?.checked),
      min_entry_age: sdmdNumber(field('min_entry_age')?.value),
      max_entry_age: sdmdNumber(field('max_entry_age')?.value),
      max_entries: sdmdNumber(field('max_entries')?.value),
      min_interval_years: sdmdNumber(field('min_interval_years')?.value),
      max_removal_fraction: sdmdNumber(field('max_removal_fraction')?.value),
      required_sdmd_zone: current.required_sdmd_zone ?? null,
      source: current.source ?? 'AU Explorer',
      review_status: current.review_status ?? 'provisional',
    };
  });
  try {
    const response = await fetch(`api/sdmd/au/${encodeURIComponent(state.sdmd.au)}/constraints`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ constraints }),
    });
    if (!response.ok) {
      let detail = response.statusText;
      try { detail = (await response.json()).detail ?? detail; } catch { /* not json */ }
      throw new Error(detail);
    }
    const payload = await response.json();
    state.sdmd.preview = payload.preview;
    const auId = state.sdmd.au;
    await loadSdmdAu(auId);
    $('sdmd-preview').textContent = 'Constraint set saved.';
  } catch (error) {
    $('sdmd-preview').textContent = `Save refused: ${error.message}`;
  }
}

function useSdmdInScenario() {
  if (!state.sdmd.au) return;
  const params = new URLSearchParams(window.location.search);
  params.set('scenario_au', state.sdmd.au);
  window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}${window.location.hash}`);
  $('sdmd-preview').textContent = `AU ${state.sdmd.au} queued for a scenario; the saved constraints are the handoff.`;
}

function wireSdmd() {
  if (!$('sdmd-region')) return;
  $('sdmd-region').addEventListener('change', async () => {
    await loadSdmdAUs();
    if (state.workspace === 'sdmd') updateUrl();
  });
  $('sdmd-coverage-zone').addEventListener('change', fillSdmdCoverageBecs);
  $('sdmd-coverage-bec').addEventListener('change', renderSdmdCoverageDetail);
  $('sdmd-au').addEventListener('change', async () => {
    await loadSdmdAu($('sdmd-au').value);
    if (state.workspace === 'sdmd') updateUrl();
  });
  $('sdmd-source').addEventListener('change', () => {
    state.sdmd.source = $('sdmd-source').value;
    renderSdmdYield();
  });
  $('sdmd-save').addEventListener('click', saveSdmdConstraints);
  $('sdmd-reset').addEventListener('click', () => {
    if (state.sdmd.au) loadSdmdAu(state.sdmd.au);
  });
  $('sdmd-yield-metric').addEventListener('change', () => {
    state.sdmd.yieldMetric = $('sdmd-yield-metric').value;
    renderSdmdYield();
  });
  $('sdmd-trajectory').addEventListener('change', loadSdmdTrajectory);
  $('sdmd-use').addEventListener('click', useSdmdInScenario);
}

async function loadCarbon() {
  const status = $('carbon-status');
  const meta = $('carbon-meta');
  const select = $('carbon-account');
  const content = $('carbon-content');
  const empty = $('carbon-empty');
  const hint = $('carbon-hint');
  if (!status || !meta || !select || !content || !empty || !hint) return;
  try {
    const info = await api(`api/runs/${encodeURIComponent(state.run)}/carbon`);
    state.carbon = info;
    meta.replaceChildren();
    select.replaceChildren();
    if (!info.available) {
      state.carbonAccount = '';
      select.disabled = true;
      status.textContent = 'this run has no carbon artifacts';
      $('carbon-ledger').textContent = '';
      $('carbon-ledger').hidden = true;
      content.hidden = true;
      empty.hidden = false;
      empty.textContent = 'This run has no carbon artifacts. Pick a carbon run to see accounts and pools.';
      hint.hidden = true;
      renderCarbonComposition();
      renderCarbonCompare();
      renderCarbonFiles();
      drawCarbonChart();
      syncNavigation();
      return;
    }
    select.disabled = false;
    content.hidden = false;
    empty.hidden = true;
    hint.hidden = false;
    const accounts = info.accounts ?? [];
    const ledger = info.ledger;
    status.textContent = `${accounts.length} carbon accounts${info.pools ? ' · pools' : ''}${info.flux ? ' · flux' : ''}${ledger ? ' · ledger' : ''}`;
    const manifest = info.manifest ?? {};
    const units = manifest.units ?? {};
    const unitLabel = [units.carbon, units.co2e].filter(Boolean).join(' · ');
    const rows = [
      ['Package', manifest.package_id],
      ['libcbm', manifest.libcbm_version],
      ['Units', unitLabel || units.carbon],
      ['Defaults', manifest.cbm_defaults?.version],
      ['Fingerprint', manifest.package_fingerprint ? String(manifest.package_fingerprint).slice(0, 12) : null],
      ['Schedule hash', manifest.schedule_sha256 ? String(manifest.schedule_sha256).slice(0, 12) : null],
    ].filter(([, value]) => value !== undefined && value !== null && value !== '');
    if (!rows.length && ledger) {
      rows.push(['Ledger package', ledger.package], ['Ledger years', ledger.years]);
    }
    for (const [label, value] of rows) {
      meta.append(carbonMetaRow(label, value));
    }
    const current = accounts.some((account) => account.account === state.carbonAccount)
      ? state.carbonAccount
      : accounts.find((account) => account.account === 'carbon.ecosystem.total')?.account
        ?? accounts[0]?.account
        ?? '';
    state.carbonAccount = current;
    for (const account of accounts) {
      const option = document.createElement('option');
      option.value = account.account;
      option.textContent = `${carbonAccountLabel(account.account)} (${carbonAccountUnit(account.account)})`;
      option.title = account.account;
      select.append(option);
    }
    select.value = current;
    $('carbon-ledger').hidden = !ledger;
    $('carbon-ledger').textContent = ledger
      ? `Ledger: ${ledger.ledger ?? 'present'} · ${ledger.years ?? '—'} years${ledger.package ? ` · ${ledger.package}` : ''}`
      : '';
    renderCarbonComposition();
    renderCarbonCompare();
    renderCarbonFiles();
    drawCarbonChart();
    syncNavigation();
  } catch (error) {
    state.carbon = null;
    state.carbonAccount = '';
    meta.replaceChildren();
    select.replaceChildren();
    select.disabled = true;
    status.textContent = `carbon unavailable: ${error.message}`;
    content.hidden = true;
    empty.hidden = false;
    empty.textContent = `Carbon unavailable: ${error.message}`;
    hint.hidden = true;
    $('carbon-ledger').hidden = true;
    renderCarbonComposition();
    renderCarbonCompare();
    renderCarbonFiles();
    drawCarbonChart();
    syncNavigation();
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

function currentPeriod() {
  return state.periods[state.periodIndex] ?? null;
}

function inCurrentPeriod(year) {
  const period = currentPeriod();
  const start = period ? Number(period.start) : Number(state.year);
  const end = period ? Number(period.end) : Number(state.year);
  return Number(year) >= start && Number(year) <= end;
}

function setPeriod(index) {
  const slider = $('year');
  if (!state.periods.length) {
    state.periodIndex = 0;
    state.year = 0;
    slider.value = '0';
    $('year-label').textContent = 'Period 1';
    return null;
  }
  const next = Math.min(Math.max(0, index), state.periods.length - 1);
  state.periodIndex = next;
  const period = state.periods[next];
  state.year = Number(period.end);
  slider.value = String(next);
  $('year-label').textContent = period.label ?? `Period ${next + 1}`;
  renderRunHealth();
  updateUrl({ push: false });
  if (state.estate3d.open) refreshEstate3d();
  return period;
}

function stopPeriodPlay() {
  if (periodPlayTimer) {
    window.clearInterval(periodPlayTimer);
    periodPlayTimer = null;
  }
  periodPlayBusy = false;
  const button = $('play-periods');
  if (button) {
    button.textContent = '▶ Play';
    button.setAttribute('aria-pressed', 'false');
  }
}

function togglePeriodPlay() {
  const button = $('play-periods');
  if (!button || !state.periods.length) return;
  if (periodPlayTimer) {
    stopPeriodPlay();
    return;
  }
  if (state.periodIndex >= state.periods.length - 1) setPeriod(0);
  button.textContent = '❚❚ Pause';
  button.setAttribute('aria-pressed', 'true');
  periodPlayTimer = window.setInterval(async () => {
    if (periodPlayBusy || state.mapLoading) return;
    if (state.periodIndex >= state.periods.length - 1) {
      stopPeriodPlay();
      return;
    }
    periodPlayBusy = true;
    try {
      setPeriod(state.periodIndex + 1);
      if (state.workspace === 'map') {
        if (state.compareView) await loadComparison();
        else if (state.live.active) render(false);
        else {
          await loadMap(true);
          await new Promise((resolve) => window.setTimeout(resolve, 500));
        }
      }
    } finally {
      periodPlayBusy = false;
    }
  }, 700);
}

function selectPeriodForYear(year) {
  const index = state.periods.findIndex(
    (period) => Number(year) >= Number(period.start) && Number(year) <= Number(period.end),
  );
  return setPeriod(index >= 0 ? index : 0);
}

function periodQuery() {
  const period = currentPeriod();
  return period ? `&period_start=${Number(period.start)}` : '';
}

async function loadPeriods() {
  const body = await api(`api/runs/${encodeURIComponent(state.run)}/periods`);
  let periods = Array.isArray(body.periods) ? body.periods : [];
  if (!periods.length) {
    periods = (body.values ?? []).map((year, index) => ({
      index,
      start: Number(year),
      end: Number(year),
      label: `Period ${index + 1} · year ${year}`,
    }));
  }
  state.periods = periods;
  state.periodWidth = Number(body.period_width ?? 1);
  const slider = $('year');
  slider.min = '0';
  slider.max = String(Math.max(0, periods.length - 1));
  // keep the analyst's year across a run finishing; clamp it into a period of the new horizon
  const wanted = Number.isFinite(state.year) ? state.year : Number(periods[0]?.end ?? 0);
  const index = periods.findIndex(
    (period) => wanted >= Number(period.start) && wanted <= Number(period.end),
  );
  setPeriod(index >= 0 ? index : 0);
}


const WORKSPACE_NAMES = ['map', 'plan', 'results', 'data'];
const SUB_PANELS = {
  results: ['reports', 'timeline', 'comparison', 'search'],
  data: ['dataset', 'lidar', 'carbon'],
};
const SUB_SECTION = {
  reports: 'tab-reports',
  timeline: 'tab-timeline',
  comparison: 'tab-comparison',
  search: 'tab-search',
  dataset: 'tab-dataset',
  lidar: 'tab-lidar',
  carbon: 'tab-carbon',
};

function skinPanels() {
  return new Set(state.skin?.panels ?? [
    'legend', 'dataset', 'lidar', 'carbon', 'targets', 'reports', 'comparison', 'search',
  ]);
}

function workspaceAllowed(workspace) {
  if (workspace === 'map') return true;
  if (workspace === 'sdmd') return Boolean(state.sdmd.available);
  const panels = skinPanels();
  if (workspace === 'fire') return Boolean(state.datasetSummary?.capabilities?.fire);
  if (workspace === 'console') return Boolean(state.datasetSummary?.capabilities?.console);
  if (workspace === 'plan') return panels.has('targets');
  if (workspace === 'pareto') return panels.has('search');
  if (workspace === 'results') {
    return SUB_PANELS.results.some((name) => panels.has(name));
  }
  if (workspace === 'data') {
    if (panels.has('dataset')) return true;
    return Boolean(state.lidar?.available || state.carbon?.available);
  }
  return false;
}

function subAllowed(workspace, sub) {
  const panels = skinPanels();
  if (workspace === 'results') {
    return panels.has(sub) || (sub === 'timeline' && panels.has('reports'));
  }
  if (workspace !== 'data') return true;
  if (sub === 'dataset') return panels.has('dataset');
  if (sub === 'lidar') return panels.has('lidar');
  if (sub === 'carbon') return panels.has('carbon');
  return false;
}

function visibleSubs(workspace) {
  return (SUB_PANELS[workspace] ?? []).filter((sub) => subAllowed(workspace, sub));
}

function currentSub(workspace = state.workspace) {
  return state.subview[workspace] ?? null;
}

function setMapLoading(visible, text = 'Loading map…') {
  const overlay = $('map-loading');
  if (!overlay) return;
  overlay.hidden = !visible;
  if (visible) $('map-loading-text').textContent = text;
}

function setGeometryAvailability(available) {
  state.geometryAvailable = available !== false;
  const notice = $('map-unavailable');
  if (notice) notice.hidden = state.geometryAvailable;
  if (state.geometryAvailable) return;
  setMapLoading(false);
  if ($('map-legend')) $('map-legend').hidden = true;
  statusLine('map unavailable: no geometry layer is configured');
}

function syncNavigation() {
  const panels = skinPanels();
  const workspaces = [...document.querySelectorAll('.workspaces [role="tab"]')];
  for (const button of workspaces) {
    const workspace = button.dataset.workspace;
    button.hidden = !workspaceAllowed(workspace);
    const active = workspace === state.workspace;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
    button.tabIndex = active ? 0 : -1;
  }
  if (!workspaceAllowed(state.workspace)) {
    state.workspace = 'map';
  }
  for (const panel of document.querySelectorAll('.workspace')) {
    panel.hidden = panel.id !== `workspace-${state.workspace}`;
  }
  if (state.workspace === 'map') $('tab-legend').hidden = false;
  if (state.workspace === 'plan') $('tab-targets').hidden = false;
  $('map-wrap').hidden = ['plan', 'sdmd', 'pareto', 'console', 'fire'].includes(state.workspace);
  $('target-canvas').hidden = state.workspace !== 'plan';
  $('sdmd-canvas').hidden = state.workspace !== 'sdmd';
  $('pareto-wrap').hidden = state.workspace !== 'pareto';
  $('fire-wrap').hidden = state.workspace !== 'fire';
  if (state.workspace === 'plan') renderTargetCharts();
  if (state.workspace === 'sdmd') renderSdmd();
  if (state.workspace === 'pareto' && state.pareto.chart) resizeParetoChart();
  for (const workspace of ['results', 'data']) {
    const nav = $(`${workspace}-nav`);
    const buttons = [...(nav?.querySelectorAll('[role="tab"]') ?? [])];
    const available = new Set(visibleSubs(workspace));
    for (const button of buttons) {
      button.hidden = !available.has(button.dataset.sub);
    }
    if (nav) nav.hidden = available.size <= 1;
    if (state.workspace === workspace) {
      if (!available.has(state.subview[workspace])) {
        state.subview[workspace] = available[0] ?? null;
      }
      for (const button of buttons) {
        const active = button.dataset.sub === state.subview[workspace];
        button.classList.toggle('active', active);
        button.setAttribute('aria-selected', active ? 'true' : 'false');
        button.tabIndex = active ? 0 : -1;
      }
      for (const sub of SUB_PANELS[workspace] ?? []) {
        const section = $(SUB_SECTION[sub]);
        if (section) section.hidden = sub !== state.subview[workspace];
      }
    }
  }
  const period = state.periods[state.periodIndex];
  if (period) {
    $('year-label').textContent = period.label ?? `Period ${state.periodIndex + 1}`;
  }
}

function activateSubView() {
  if (state.workspace === 'results') {
    if (state.subview.results === 'comparison') {
      syncCompareRuns();
      loadComparison();
    } else if (state.subview.results === 'search') {
      loadSearch();
    } else if (state.subview.results === 'timeline') {
      loadScheduleTimeline();
      if (state.compareView) clearCompareView();
    } else {
      loadReports();
      if (state.compareView) clearCompareView();
    }
    return;
  }
  if (state.workspace === 'data') {
    if (state.subview.data === 'lidar') loadLidar();
    else if (state.subview.data === 'carbon') loadCarbon();
    else loadDataset();
    return;
  }
  if (state.workspace === 'plan') {
    renderTargetCharts();
    return;
  }
  if (state.workspace === 'sdmd') {
    renderSdmd();
    return;
  }
  if (state.workspace === 'pareto') {
    loadParetoArtifacts();
    return;
  }
  if (state.workspace === 'console') {
    loadConsole();
    return;
  }
  if (state.workspace === 'fire') {
    loadFireWorkspace();
    return;
  }
  if (state.workspace !== 'results' && state.compareView) clearCompareView();
}

function setSubView(workspace, sub, { sync = true } = {}) {
  if (!SUB_PANELS[workspace]) return;
  const available = visibleSubs(workspace);
  state.subview[workspace] = available.includes(sub) ? sub : (available[0] ?? null);
  syncNavigation();
  if (sync) {
    updateUrl();
    activateSubView();
  }
}

function setWorkspace(workspace, { sync = true, activate = true } = {}) {
  const requested = workspaceAllowed(workspace) ? workspace : 'map';
  if (state.workspace !== requested && state.compareView && requested !== 'results') {
    clearCompareView();
  }
  state.workspace = requested;
  document.body.dataset.workspace = requested;
  syncNavigation();
  if (SUB_PANELS[requested]) {
    const sub = currentSub(requested) ?? visibleSubs(requested)[0] ?? null;
    state.subview[requested] = sub;
    syncNavigation();
  }
  if (sync) updateUrl();
  if (requested === 'map' && state.mapLibre) state.mapLibre.resize();
  if (activate) activateSubView();
}

function updateUrl({ push = true } = {}) {
  if (!state.urlReady) return;
  const params = new URLSearchParams(window.location.search);
  if (state.run) params.set('run', state.run);
  else params.delete('run');
  params.set('view', state.workspace);
  const sub = currentSub();
  if (sub) params.set('sub', sub);
  else params.delete('sub');
  params.set('period', String(state.periodIndex));
  if (state.selectedBlock !== null) params.set('block', String(state.selectedBlock));
  else params.delete('block');
  if (state.workspace === 'sdmd' && state.sdmd.au) params.set('au', state.sdmd.au);
  else params.delete('au');
  const url = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
  window.history[push ? 'pushState' : 'replaceState']({}, '', url);
}

function wireTablist(selector) {
  const buttons = [...document.querySelectorAll(selector)];
  for (const button of buttons) {
    button.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      const visible = buttons.filter((candidate) => !candidate.hidden);
      const index = visible.indexOf(button);
      if (index < 0) return;
      event.preventDefault();
      const next = event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? visible.length - 1
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + visible.length) % visible.length;
      visible[next].focus();
      visible[next].click();
    });
  }
}

async function loadDataset() {
  const status = $('dataset-status');
  const meta = $('dataset-meta');
  if (!status || !meta) return;
  try {
    const summary = state.datasetSummary ?? await api('api/summary');
    state.datasetSummary = summary;
    setGeometryAvailability(summary.capabilities?.geometry !== false);
    const manifest = summary.manifest ?? {};
    const metadata = manifest.metadata ?? {};
    const rows = [
      ['Dataset', summary.dataset ?? '—'],
      ['Schema', manifest.schema_version ?? '—'],
      ['Created', manifest.created_utc ?? manifest.created_at ?? '—'],
      ['CRS', manifest.crs ?? '—'],
      ['Sources', Array.isArray(manifest.sources) ? `${manifest.sources.length} source(s)` : '—'],
    ];
    meta.replaceChildren();
    for (const [label, value] of rows) meta.append(lidarMetaRow(label, value));
    const extra = Object.keys(metadata).filter((key) => key !== 'lidar_products' && key !== 'lidar_fields');
    status.textContent = extra.length
      ? `compiled dataset · ${extra.length} metadata block(s)`
      : 'compiled dataset';
    $('dataset-note').textContent = metadata.lidar_products
      ? 'LiDAR provenance is registered; open LiDAR for the pinned bundle and fields.'
      : 'No LiDAR registration in this dataset.';
    const datasetName = summary.dataset ?? 'dataset';
    document.title = `WS4 — ${datasetName}${state.run ? ` — ${state.run}` : ''}`;
    $('dataset-name').textContent = datasetName;
  } catch (error) {
    status.textContent = `dataset unavailable: ${error.message}`;
    meta.replaceChildren();
  }
}

function applySkin(skin) {
  state.skin = skin;
  syncNavigation();
  const layers = skin.layers ?? [];
  $('show-treated').closest('label').hidden = !layers.includes('treatments');
  $('show-untreated').closest('label').hidden = !layers.includes('blocks');
  const readOnly = Boolean(skin.read_only) || !(skin.actions ?? []).includes('edit_targets');
  $('save-targets').hidden = readOnly || !document.querySelector('#targets-table:not([hidden])');
  $('apply-profile').disabled = readOnly;
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

function textInput(value, field, index) {
  const input = document.createElement('input');
  input.type = 'text';
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


function targetChartAccounts() {
  const accounts = [];
  const seen = new Set();
  for (const row of state.targets) {
    if (!state.watched.has(String(row.index))) continue;
    if (seen.has(row.account)) continue;
    seen.add(row.account);
    accounts.push(row.account);
  }
  return accounts;
}

function periodAchieved(account, period) {
  const series = state.series.get(account);
  if (!series || !series.size) return null;
  const start = Number(period.start) + 1;
  const end = Number(period.end) + 1;
  if (String(account).startsWith('product.')) {
    let total = 0;
    let found = false;
    for (let year = start; year <= end; year += 1) {
      if (series.has(year)) {
        total += Number(series.get(year));
        found = true;
      }
    }
    return found ? total : null;
  }
  if (series.has(end)) return Number(series.get(end));
  if (series.has(end - 1)) return Number(series.get(end - 1));
  return null;
}

function compactNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  const absolute = Math.abs(number);
  if (absolute >= 1e9) return `${(number / 1e9).toFixed(2)}B`;
  if (absolute >= 1e6) return `${(number / 1e6).toFixed(2)}M`;
  if (absolute >= 1e3) return `${(number / 1e3).toFixed(1)}k`;
  return number.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fullNumber(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function targetStatus(row, value) {
  if (value === null || value === undefined) return 'unknown';
  if (row.minimum === null || row.minimum === undefined) {
    if (row.maximum === null || row.maximum === undefined) return 'indicator';
  }
  if (row.minimum !== null && row.minimum !== undefined && value < Number(row.minimum)) return 'below';
  if (row.maximum !== null && row.maximum !== undefined && value > Number(row.maximum)) return 'above';
  return 'met';
}

function targetPeriodsFromRows() {
  const width = Number(
    state.targets.find((row) => Number(row.period_width) > 0)?.period_width
      ?? state.periodWidth
      ?? 1,
  ) || 1;
  let count = 1;
  for (const row of state.targets) {
    if (Number(row.period) > count) count = Number(row.period);
    if (row.period === null || row.period === undefined) {
      const year = Number(row.year);
      if (Number.isFinite(year)) count = Math.max(count, Math.ceil(year / width));
    }
  }
  return Array.from({ length: count }, (_unused, index) => ({
    index,
    start: index * width,
    end: (index + 1) * width - 1,
    label: `Years ${index * width}-${(index + 1) * width - 1}`,
  }));
}

function targetCellPeriodIndex(row, periods) {
  if (row.period !== null && row.period !== undefined && Number(row.period) > 0) {
    return Number(row.period) - 1;
  }
  const year = Number(row.year);
  const found = periods.findIndex(
    (period) => Number(period.start) <= year && year <= Number(period.end),
  );
  if (found >= 0) return found;
  return Math.max(0, Math.floor((year - 1) / Math.max(1, Number(row.period_width) || 1)));
}

function chartCell(account, period) {
  const source = state.targetSeries?.accounts?.find((item) => item.account === account);
  const cell = source?.periods?.find((item) => Number(item.index) === Number(period.index));
  if (cell) return cell;
  const periods = targetPeriodsFromRows();
  const rows = state.targets.filter(
    (row) => row.account === account && targetCellPeriodIndex(row, periods) === Number(period.index),
  );
  const levelRows = rows.filter((row) => !row.flow);
  const flowRow = rows.find((row) => row.flow);
  const minimum = levelRows.find((row) => row.minimum !== null && row.minimum !== undefined);
  const maximum = levelRows.find((row) => row.maximum !== null && row.maximum !== undefined);
  return {
    index: Number(period.index),
    start: Number(period.start),
    end: Number(period.end),
    label: period.label,
    minimum: minimum ? Number(minimum.minimum) : null,
    maximum: maximum ? Number(maximum.maximum) : null,
    flow: flowRow ? flowRow.flow : '',
    active: rows.some((row) => row.active !== false),
    target_indices: rows.map((row) => row.index),
  };
}


function targetChartCells(account) {
  const source = state.targetSeries?.accounts?.find((item) => item.account === account);
  const periods = source?.periods?.length
    ? source.periods
    : (state.periods.length ? state.periods : targetPeriodsFromRows());
  return (periods ?? []).map((period) => {
    const value = periodAchieved(account, period);
    return { ...chartCell(account, period), achieved: value };
  });
}

function ensureChartRow(account, cell) {
  const rows = (cell.target_indices ?? [])
    .map((index) => state.targets[index])
    .filter((row) => row && row.account === account && !row.flow);
  if (rows.length) return rows[0];
  const template = state.targets.find((row) => row.account === account) ?? {};
  const width = Number(template.period_width ?? state.periodWidth ?? 1) || 1;
  const row = {
    index: state.targets.length,
    account,
    period: Number(cell.index) + 1,
    year: Number(cell.end) + 1,
    period_width: width,
    flow: '',
    minimum: null,
    maximum: null,
    min_weight: template.min_weight ?? 1,
    max_weight: template.max_weight ?? 1,
    normalization: template.normalization ?? 'none',
    priority: template.priority ?? 1,
    active: template.active !== false,
    kind: 'level',
  };
  state.targets.push(row);
  cell.target_indices = [row.index];
  return row;
}

function setChartBound(account, cell, bound, value) {
  const row = ensureChartRow(account, cell);
  row[bound] = value;
  cell[bound] = value;
  cell.active = state.targets.some((candidate) => candidate.account === account && candidate.active !== false);
  const source = state.targetSeries?.accounts?.find((item) => item.account === account);
  const sourceCell = source?.periods?.find((item) => Number(item.index) === Number(cell.index));
  if (sourceCell) {
    sourceCell[bound] = value;
    sourceCell.active = cell.active;
    sourceCell.target_indices = cell.target_indices;
  }
}

function syncTargetTableInputs() {
  for (const input of document.querySelectorAll('#targets-table [data-field]')) {
    const row = state.targets[Number(input.dataset.index)];
    const field = input.dataset.field;
    if (!row || !field) continue;
    const value = row[field];
    if (field === 'notes' || field === 'normalization') input.value = value ?? '';
    else input.value = value === null || value === undefined ? '' : String(value);
  }
}

function applyChartBound(account, cell, bound, value, scope) {
  const target = value === '' || value === null || value === undefined ? null : Number(value);
  if (target !== null && !Number.isFinite(target)) return;
  const cells = scope === 'all' ? targetChartCells(account) : [cell];
  for (const item of cells) setChartBound(account, item, bound, target);
  syncTargetTableInputs();
  markChartDirty();
  renderTargetCharts();
}

function setChartActive(account, active) {
  for (const row of state.targets.filter((candidate) => candidate.account === account)) {
    row.active = active;
  }
  const source = state.targetSeries?.accounts?.find((item) => item.account === account);
  for (const cell of source?.periods ?? []) cell.active = active;
  markChartDirty();
  renderTargetCharts();
}

function markChartDirty() {
  state.chartDirty = true;
  const button = $('target-chart-save');
  if (button) button.disabled = false;
  const status = $('target-chart-status');
  if (status) status.textContent = 'unsaved chart changes';
}

function setChartStatus(text) {
  const status = $('target-chart-status');
  if (status) status.textContent = text;
  const button = $('target-chart-save');
  if (button) button.disabled = !state.chartDirty;
}

async function saveTargetCharts() {
  if (!state.chartDirty) return;
  const pinned = new Set(targetChartAccounts());
  const rows = state.targets.map(({ kind, ...row }) => ({ ...row }));
  const saved = await postTargets(rows, 'saved target chart changes');
  if (!saved) {
    setChartStatus('chart save failed');
    return;
  }
  state.chartDirty = false;
  const currentRows = state.targets;
  state.watched.clear();
  for (const row of currentRows) {
    if (pinned.has(row.account)) state.watched.add(String(row.index));
  }
  saveWatched();
  setChartStatus('chart changes saved');
  renderTargetCharts();
}

function renderTargetChart(account, periods) {
  const card = document.createElement('article');
  card.className = 'target-chart-card';
  const accountRows = state.targets.filter((row) => row.account === account);
  const active = accountRows.some((row) => row.active !== false);
  if (!active) card.classList.add('inactive');
  const cells = periods.map((period) => {
    const cell = chartCell(account, period);
    const value = periodAchieved(account, period);
    return { ...cell, achieved: value };
  });
  const title = document.createElement('div');
  title.className = 'target-chart-title';
  const name = document.createElement('span');
  name.className = 'name';
  name.textContent = account;
  name.title = account;
  const meta = document.createElement('span');
  meta.className = 'meta';
  const current = cells[Math.min(Math.max(0, state.periodIndex), cells.length - 1)];
  const flow = cells.find((cell) => cell.flow)?.flow ?? '';
  meta.textContent = current && current.achieved !== null
    ? `P${Number(current.index) + 1} · ${compactNumber(current.achieved)} · ${targetStatus(current, current.achieved)}${flow ? ` · ${flow} flow` : ''}${active ? '' : ' · inactive'}`
    : active ? (flow ? `${flow} flow` : 'no value') : 'inactive';
  meta.classList.add(current ? targetStatus(current, current.achieved) : 'unknown');
  title.append(name, meta);
  card.append(title);

  let selectedCell = cells[Math.min(Math.max(0, state.periodIndex), Math.max(0, cells.length - 1))];
  const controls = document.createElement('div');
  controls.className = 'target-chart-controls';
  const activeLabel = document.createElement('label');
  const activeBox = document.createElement('input');
  activeBox.type = 'checkbox';
  activeBox.checked = active;
  activeBox.addEventListener('change', () => setChartActive(account, activeBox.checked));
  activeLabel.append(activeBox, 'Active');
  const boundLabel = document.createElement('label');
  boundLabel.append('Edit ');
  const boundSelect = document.createElement('select');
  for (const [value, text] of [['minimum', 'Minimum'], ['maximum', 'Maximum']]) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = text;
    boundSelect.append(option);
  }
  boundLabel.append(boundSelect);
  const scopeLabel = document.createElement('label');
  scopeLabel.append('Scope ');
  const scopeSelect = document.createElement('select');
  for (const [value, text] of [['period', 'This period'], ['all', 'All periods']]) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = text;
    scopeSelect.append(option);
  }
  scopeLabel.append(scopeSelect);
  const valueLabel = document.createElement('label');
  valueLabel.append('Value ');
  const valueInput = document.createElement('input');
  valueInput.type = 'number';
  valueInput.step = 'any';
  valueLabel.append(valueInput);
  const applyButton = document.createElement('button');
  applyButton.type = 'button';
  applyButton.textContent = 'Apply';
  const clearButton = document.createElement('button');
  clearButton.type = 'button';
  clearButton.textContent = 'Clear';
  const syncValue = () => {
    if (!selectedCell || document.activeElement === valueInput) return;
    const value = selectedCell[boundSelect.value];
    valueInput.value = value === null || value === undefined ? '' : String(value);
  };
  boundSelect.addEventListener('change', syncValue);
  applyButton.addEventListener('click', () => applyChartBound(account, selectedCell, boundSelect.value, valueInput.value, scopeSelect.value));
  clearButton.addEventListener('click', () => applyChartBound(account, selectedCell, boundSelect.value, null, scopeSelect.value));
  controls.append(activeLabel, boundLabel, scopeLabel, valueLabel, applyButton, clearButton);
  card.append(controls);
  syncValue();

  const width = 540;
  const height = 210;
  const left = 48;
  const right = 12;
  const top = 12;
  const bottom = 26;
  const values = [];
  for (const cell of cells) {
    for (const value of [cell.minimum, cell.maximum, cell.achieved]) {
      if (value !== null && value !== undefined && Number.isFinite(Number(value))) values.push(Number(value));
    }
  }
  let low = values.length ? Math.min(...values) : 0;
  let high = values.length ? Math.max(...values) : 1;
  if (values.length && low >= 0) low = 0;
  if (low === high) {
    const pad = Math.max(Math.abs(low) * 0.1, 1);
    low -= pad;
    high += pad;
  }
  const pad = (high - low) * 0.08;
  const domainLow = low >= 0 ? 0 : low - pad;
  const domainHigh = high + pad;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const step = plotWidth / Math.max(periods.length, 1);
  const barWidth = Math.max(2, Math.min(step * 0.86, 34));
  const x = (index) => left + step * index + step / 2;
  const y = (value) => top + (1 - (Number(value) - domainLow) / (domainHigh - domainLow)) * plotHeight;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('class', 'target-chart-svg');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `${account} target chart`);

  for (let index = 0; index < 4; index += 1) {
    const value = domainLow + ((domainHigh - domainLow) * index) / 3;
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', left); line.setAttribute('x2', width - right);
    line.setAttribute('y1', y(value)); line.setAttribute('y2', y(value));
    line.setAttribute('class', 'target-chart-grid-line');
    svg.append(line);
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', left - 5); label.setAttribute('y', y(value) + 3);
    label.setAttribute('text-anchor', 'end');
    label.setAttribute('class', 'target-chart-axis-label');
    label.textContent = compactNumber(value);
    svg.append(label);
  }

  const selectedIndex = Math.min(Math.max(0, state.periodIndex), Math.max(0, cells.length - 1));
  const highlight = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  highlight.setAttribute('x', left + step * selectedIndex);
  highlight.setAttribute('y', top);
  highlight.setAttribute('width', step);
  highlight.setAttribute('height', plotHeight);
  highlight.setAttribute('class', 'target-chart-selected-period');
  svg.append(highlight);

  const readout = document.createElement('div');
  readout.className = 'target-chart-readout';
  const showReadout = (cell) => {
    selectedCell = cell;
    readout.textContent = `${cell.label ?? 'period'} · min ${cell.minimum === null || cell.minimum === undefined ? '—' : fullNumber(cell.minimum)} · max ${cell.maximum === null || cell.maximum === undefined ? '—' : fullNumber(cell.maximum)} · achieved ${cell.achieved === null || cell.achieved === undefined ? '—' : fullNumber(cell.achieved)} · ${targetStatus(cell, cell.achieved)}`;
    syncValue();
  };
  if (cells.length) showReadout(cells[Math.min(state.periodIndex, cells.length - 1)]);
  cells.forEach((cell, index) => {
    const center = x(index);
    const minValue = cell.minimum === null || cell.minimum === undefined ? null : Number(cell.minimum);
    const maxValue = cell.maximum === null || cell.maximum === undefined ? null : Number(cell.maximum);
    if (minValue !== null || maxValue !== null) {
      if (minValue !== null) {
        const minRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        minRect.setAttribute('x', center - barWidth / 2);
        minRect.setAttribute('y', y(minValue));
        minRect.setAttribute('width', barWidth);
        minRect.setAttribute('height', Math.max(1, height - bottom - y(minValue)));
        minRect.setAttribute('class', 'target-min-zone');
        svg.append(minRect);
      }
      if (maxValue !== null) {
        const maxRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        maxRect.setAttribute('x', center - barWidth / 2);
        maxRect.setAttribute('y', top);
        maxRect.setAttribute('width', barWidth);
        maxRect.setAttribute('height', Math.max(1, y(maxValue) - top));
        maxRect.setAttribute('class', 'target-max-zone');
        svg.append(maxRect);
      }
      if (minValue !== null && maxValue !== null && maxValue > minValue) {
        const okRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        okRect.setAttribute('x', center - barWidth / 2);
        okRect.setAttribute('y', y(maxValue));
        okRect.setAttribute('width', barWidth);
        okRect.setAttribute('height', Math.max(1, y(minValue) - y(maxValue)));
        okRect.setAttribute('class', 'target-ok-zone');
        svg.append(okRect);
      }
    }
    const hit = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    hit.setAttribute('x', left + step * index);
    hit.setAttribute('y', top);
    hit.setAttribute('width', step);
    hit.setAttribute('height', plotHeight);
    hit.setAttribute('class', 'target-chart-period');
    hit.setAttribute('fill', 'transparent');
    hit.dataset.period = String(index);
    const tip = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    tip.textContent = `${cell.label ?? `Period ${index + 1}`}: min ${minValue === null ? '—' : fullNumber(minValue)}, max ${maxValue === null ? '—' : fullNumber(maxValue)}, achieved ${cell.achieved === null ? '—' : fullNumber(cell.achieved)}`;
    hit.append(tip);
    hit.addEventListener('mouseenter', () => showReadout(cell));
    hit.addEventListener('focus', () => showReadout(cell));
    hit.addEventListener('click', () => {
      showReadout(cell);
      setPeriod(Number(cell.index));
      syncNavigation();
    });
    hit.setAttribute('tabindex', '0');
    svg.append(hit);
  });

  let drag = null;
  const valueFromEvent = (event) => {
    const rect = svg.getBoundingClientRect();
    const py = ((event.clientY - rect.top) / Math.max(rect.height, 1)) * height;
    const ratio = (py - top) / plotHeight;
    const raw = domainHigh - ratio * (domainHigh - domainLow);
    return Math.min(domainHigh, Math.max(domainLow, raw));
  };
  svg.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    const hit = event.target?.closest?.('.target-chart-period');
    let index = hit ? Number(hit.dataset.period) : -1;
    if (!Number.isInteger(index) || index < 0 || index >= cells.length) {
      const rect = svg.getBoundingClientRect();
      const px = ((event.clientX - rect.left) / Math.max(rect.width, 1)) * width;
      index = Math.floor((px - left) / step);
    }
    if (index < 0 || index >= cells.length) return;
    drag = { cell: cells[index], index, startY: event.clientY, moved: false };
    showReadout(drag.cell);
    svg.setPointerCapture?.(event.pointerId);
  });
  svg.addEventListener('pointermove', (event) => {
    if (!drag) return;
    if (Math.abs(event.clientY - drag.startY) > 3) drag.moved = true;
    if (!drag.moved) return;
    const value = valueFromEvent(event);
    if (document.activeElement !== valueInput) valueInput.value = value.toFixed(2);
    readout.textContent = `${drag.cell.label ?? 'period'} · drag ${boundSelect.value} to ${fullNumber(value)} · achieved ${drag.cell.achieved === null ? '—' : fullNumber(drag.cell.achieved)}`;
  });
  svg.addEventListener('pointerup', (event) => {
    if (!drag) return;
    const finished = drag;
    drag = null;
    svg.releasePointerCapture?.(event.pointerId);
    if (finished.moved) {
      applyChartBound(account, finished.cell, boundSelect.value, valueFromEvent(event), scopeSelect.value);
    } else {
      showReadout(finished.cell);
      setPeriod(Number(finished.cell.index));
      syncNavigation();
    }
  });
  svg.addEventListener('pointercancel', () => { drag = null; });

  const points = cells
    .map((cell, index) => ({ cell, index }))
    .filter(({ cell }) => cell.achieved !== null && cell.achieved !== undefined);
  if (points.length > 1) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    line.setAttribute('points', points.map(({ cell, index }) => `${x(index)},${y(cell.achieved)}`).join(' '));
    line.setAttribute('class', 'target-chart-line');
    svg.append(line);
  }
  for (const { cell, index } of points) {
    const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    dot.setAttribute('cx', x(index));
    dot.setAttribute('cy', y(cell.achieved));
    dot.setAttribute('r', periods.length > 40 ? 2 : 3);
    dot.setAttribute('class', `target-chart-dot ${targetStatus(cell, cell.achieved)}`);
    const tip = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    tip.textContent = `achieved ${fullNumber(cell.achieved)}`;
    dot.append(tip);
    svg.append(dot);
  }
  const labelEvery = Math.max(1, Math.ceil(periods.length / 8));
  periods.forEach((period, index) => {
    if (index % labelEvery && index !== periods.length - 1) return;
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', x(index));
    label.setAttribute('y', height - 7);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('class', 'target-chart-axis-label');
    label.textContent = `P${index + 1}`;
    svg.append(label);
  });
  card.append(svg);
  card.append(readout);

  const legend = document.createElement('div');
  legend.className = 'target-chart-legend';
  for (const [klass, text] of [['min', 'minimum'], ['max', 'maximum'], ['achieved', 'achieved']]) {
    const item = document.createElement('span');
    item.className = klass;
    item.textContent = text;
    legend.append(item);
  }
  card.append(legend);
  const details = document.createElement('details');
  details.className = 'target-chart-table';
  const summary = document.createElement('summary');
  summary.textContent = 'All period values';
  details.append(summary);
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const text of ['Period', 'Min', 'Max', 'Achieved', 'Status']) {
    const th = document.createElement('th');
    th.textContent = text;
    headRow.append(th);
  }
  head.append(headRow);
  const body = document.createElement('tbody');
  for (const cell of cells) {
    const row = document.createElement('tr');
    const status = targetStatus(cell, cell.achieved);
    for (const [text, klass] of [
      [cell.label ?? `P${Number(cell.index) + 1}`, ''],
      [cell.minimum === null || cell.minimum === undefined ? '—' : fullNumber(cell.minimum), 'num'],
      [cell.maximum === null || cell.maximum === undefined ? '—' : fullNumber(cell.maximum), 'num'],
      [cell.achieved === null || cell.achieved === undefined ? '—' : fullNumber(cell.achieved), 'num'],
      [status, status],
    ]) {
      const td = document.createElement('td');
      td.textContent = text;
      if (klass) td.className = klass;
      row.append(td);
    }
    body.append(row);
  }
  table.append(head, body);
  details.append(table);
  card.append(details);
  const foot = document.createElement('div');
  foot.className = 'target-chart-foot';
  foot.textContent = `${active ? 'active target' : 'inactive indicator'} · ${cells.filter((cell) => cell.minimum !== null || cell.maximum !== null).length} bounded period(s)`;
  card.append(foot);
  return card;
}

function renderTargetCharts() {
  const grid = $('target-chart-grid');
  const empty = $('target-chart-empty');
  const count = $('target-chart-count');
  if (!grid || !empty) return;
  const accounts = targetChartAccounts();
  const periods = state.targetSeries?.periods?.length
    ? state.targetSeries.periods
    : (state.periods.length ? state.periods : targetPeriodsFromRows());
  grid.replaceChildren();
  if (!accounts.length || !periods.length) {
    empty.hidden = false;
    grid.hidden = true;
    if (count) count.textContent = '';
    return;
  }
  empty.hidden = true;
  grid.hidden = false;
  for (const account of accounts) grid.append(renderTargetChart(account, periods));
  if (count) count.textContent = `${accounts.length} chart${accounts.length === 1 ? '' : 's'} · ${periods.length} periods`;
}

function renderWatchPanel() {
  const panel = $('watch-panel');
  panel.replaceChildren();
  const watched = state.targets.filter(
    (row) => !row.flow && state.watched.has(String(row.index)),
  );
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
  const fmt = (value) => (value === null || value === undefined
    ? '—'
    : Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 }));
  for (const [account, rows] of groups) {
    rows.sort((left, right) => Number(left.year) - Number(right.year));
    const points = rows.map((row) => ({
      row,
      value: state.targetCells.get(String(row.index))?.value,
    }));
    const latest = points[points.length - 1];
    const card = document.createElement('div');
    card.className = 'window-card';
    const title = document.createElement('div');
    title.className = 'window-title';
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = account;
    name.title = account;
    const badge = document.createElement('span');
    badge.className = 'window-badge';
    if (latest && latest.value !== undefined && latest.value !== null) {
      const status = statusOf(latest.row, latest.value);
      badge.textContent = `${fmt(latest.value)}${status ? ` · ${status}` : ''}`;
      if (status) badge.classList.add(status);
    } else {
      badge.textContent = '—';
    }
    title.append(name, badge);
    card.append(title);

    const width = 320, height = 92, left = 34, right = 8, top = 8, bottom = 22;
    let low = Infinity, high = -Infinity;
    for (const point of points) {
      for (const bound of [point.row.minimum, point.row.maximum]) {
        if (bound !== null && bound !== undefined && Number.isFinite(Number(bound))) {
          low = Math.min(low, Number(bound));
          high = Math.max(high, Number(bound));
        }
      }
      if (point.value !== undefined && point.value !== null && Number.isFinite(Number(point.value))) {
        low = Math.min(low, Number(point.value));
        high = Math.max(high, Number(point.value));
      }
    }
    if (!Number.isFinite(low) || !Number.isFinite(high)) { low = 0; high = 1; }
    if (low === high) { low -= 0.5; high += 0.5; }
    const pad = (high - low) * 0.12;
    const domainLow = low - pad, domainHigh = high + pad;
    const step = points.length > 1 ? (width - left - right) / (points.length - 1) : 0;
    const x = (index) => (points.length === 1
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
    const bandWidth = Math.max(6, Math.min(22, step * 0.6 || 12));
    points.forEach((point, index) => {
      const row = point.row;
      if (row.minimum !== null && row.maximum !== null) {
        const band = document.createElementNS(svgNS, 'rect');
        band.setAttribute('x', x(index) - bandWidth / 2);
        band.setAttribute('y', y(Number(row.maximum)));
        band.setAttribute('width', bandWidth);
        band.setAttribute('height', Math.max(1, y(Number(row.minimum)) - y(Number(row.maximum))));
        band.setAttribute('class', 'window-band');
        svg.append(band);
      } else if (row.minimum !== null || row.maximum !== null) {
        const bound = row.minimum ?? row.maximum;
        const line = document.createElementNS(svgNS, 'line');
        line.setAttribute('x1', x(index) - bandWidth / 2); line.setAttribute('x2', x(index) + bandWidth / 2);
        line.setAttribute('y1', y(Number(bound))); line.setAttribute('y2', y(Number(bound)));
        line.setAttribute('class', 'window-bound');
        svg.append(line);
      }
    });
    const defined = points
      .map((point, index) => ({ ...point, index }))
      .filter((point) => point.value !== undefined && point.value !== null);
    if (defined.length > 1) {
      const line = document.createElementNS(svgNS, 'polyline');
      line.setAttribute('points', defined.map((point) => `${x(point.index)},${y(Number(point.value))}`).join(' '));
      line.setAttribute('class', 'window-line');
      svg.append(line);
    }
    for (const point of defined) {
      const dot = document.createElementNS(svgNS, 'circle');
      dot.setAttribute('cx', x(point.index));
      dot.setAttribute('cy', y(Number(point.value)));
      dot.setAttribute('r', points.length > 40 ? 1.4 : 2.2);
      dot.setAttribute('class', `window-dot ${statusOf(point.row, point.value)}`);
      const tip = document.createElementNS(svgNS, 'title');
      tip.textContent = `period ${point.row.period ?? point.row.year}: ${fmt(point.value)} (${statusOf(point.row, point.value)})`;
      dot.append(tip);
      svg.append(dot);
    }
    const labelEvery = Math.max(1, Math.ceil(points.length / 6));
    points.forEach((point, index) => {
      if (index % labelEvery && index !== points.length - 1) return;
      const label = document.createElementNS(svgNS, 'text');
      label.setAttribute('x', x(index));
      label.setAttribute('y', height - 6);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('class', 'window-label');
      label.textContent = String(point.row.year);
      svg.append(label);
    });
    card.append(svg);

    const table = document.createElement('div');
    table.className = 'window-table';
    const header = document.createElement('div');
    header.className = 'window-row header';
    for (const text of ['Period', 'Min', 'Max', 'Achieved', 'Status']) {
      const cell = document.createElement('span');
      cell.textContent = text;
      header.append(cell);
    }
    table.append(header);
    for (const point of points) {
      const row = document.createElement('div');
      row.className = 'window-row';
      const values = [
        String(point.row.period ?? point.row.year),
        fmt(point.row.minimum),
        fmt(point.row.maximum),
        fmt(point.value),
        statusOf(point.row, point.value),
      ];
      for (const [index, text] of values.entries()) {
        const cell = document.createElement('span');
        cell.textContent = text;
        if (index === 4) cell.className = text;
        row.append(cell);
      }
      table.append(row);
    }
    card.append(table);
    panel.append(card);
  }
}

function setTargetStatus(entry, status) {
  if (!entry.status) return;
  entry.status.className = `target-status ${status}`;
  entry.status.textContent = targetStatusLabel(status);
  entry.status.title = status === 'unknown'
    ? 'no achieved value for this run'
    : status === 'off'
      ? 'target is inactive'
      : `achieved value is ${status}`;
  if (entry.tr) entry.tr.dataset.status = status;
}

function paintTarget(entry, value) {
  entry.value = value;
  const row = entry.row;
  const status = statusOf(row, value);
  setTargetStatus(entry, status);
  if (status === 'off') {
    entry.text.textContent = value === undefined || value === null ? '—' : formatAccountValue(value);
    if (entry.band) entry.band.style.display = 'none';
    if (entry.marker) entry.marker.style.display = 'none';
    return;
  }
  if (status === 'unknown') {
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
  entry.text.textContent = formatAccountValue(value);
}

const TARGET_STATUS_RANK = { met: 0, below: 1, above: 2, off: 3, unknown: 4 };

function targetSortValue(row, key) {
  if (key === 'account') return String(row.dataset.account ?? '').toLowerCase();
  if (key === 'active') return row.dataset.active === '1' ? 0 : 1;
  if (key === 'period') return row.dataset.period === '' ? -1 : Number(row.dataset.period);
  if (key === 'minimum' || key === 'maximum') {
    const value = Number(row.dataset[key]);
    return Number.isFinite(value) ? value : Number.POSITIVE_INFINITY;
  }
  if (key === 'status') return TARGET_STATUS_RANK[row.dataset.status] ?? 99;
  return Number(row.dataset.index);
}

function applyTargetSort() {
  const table = $('targets-table');
  const body = table?.querySelector('tbody');
  if (!table || !body) return;
  const { key, direction } = state.targetSort;
  const rows = [...body.querySelectorAll('tr:not(.target-detail)')];
  const sortKey = key ?? 'index';
  const ordered = rows.sort((left, right) => {
    const a = targetSortValue(left, sortKey);
    const b = targetSortValue(right, sortKey);
    if (a < b) return -1 * direction;
    if (a > b) return 1 * direction;
    return Number(left.dataset.index) - Number(right.dataset.index);
  });
  for (const row of ordered) {
    const detail = row.nextElementSibling;
    body.append(row);
    if (detail?.classList.contains('target-detail')) body.append(detail);
  }
  for (const button of document.querySelectorAll('#targets-table thead .sort-button')) {
    const th = button.closest('th');
    const active = button.dataset.sort === key;
    const sortDirection = active ? (direction > 0 ? 'ascending' : 'descending') : 'none';
    th?.setAttribute('aria-sort', sortDirection);
    button.dataset.direction = sortDirection;
  }
  const bar = $('target-sort-bar');
  const status = $('target-sort-status');
  if (bar) bar.hidden = table.hidden || !rows.length;
  if (status) {
    status.textContent = key
      ? `${key === 'minimum' ? 'Min' : key === 'maximum' ? 'Max' : key.charAt(0).toUpperCase() + key.slice(1)} ${direction > 0 ? 'ascending' : 'descending'}`
      : 'file order';
  }
  applyTargetFilter();
}

function sortTargetTable(key) {
  const same = state.targetSort.key === key;
  state.targetSort = {
    key,
    direction: same ? -state.targetSort.direction : 1,
  };
  applyTargetSort();
}

function targetRows() {
  return [...document.querySelectorAll('#targets-table tbody tr:not(.target-detail)')];
}

function targetRowStatus(row) {
  return row.dataset.status || 'unknown';
}

function targetStatusCounts() {
  const counts = { met: 0, below: 0, above: 0, off: 0, unknown: 0 };
  for (const row of targetRows()) {
    const status = targetRowStatus(row);
    if (status in counts) counts[status] += 1;
  }
  return counts;
}

function updateTargetSummary() {
  const summary = $('target-summary');
  const chartSummary = $('target-chart-summary');
  const rows = targetRows();
  if (!summary) return;
  if (!rows.length) {
    summary.hidden = true;
    if (chartSummary) chartSummary.textContent = '';
    renderRunHealth();
    return;
  }
  const counts = targetStatusCounts();
  const failing = counts.below + counts.above;
  summary.hidden = false;
  summary.replaceChildren();
  const part = (text, className = '') => {
    const span = document.createElement('span');
    if (className) span.className = className;
    span.textContent = text;
    summary.append(span);
  };
  part(`${rows.length} targets`);
  summary.append(document.createTextNode(' · '));
  part(`${failing} failing`, failing ? 'target-summary-failing' : '');
  summary.append(document.createTextNode(' · '));
  part(`${counts.met} met`);
  summary.append(document.createTextNode(' · '));
  part(`${counts.off} off`);
  if (counts.unknown) {
    summary.append(document.createTextNode(' · '));
    part(`${counts.unknown} no value`);
  }
  if (chartSummary) {
    chartSummary.textContent = failing
      ? `${failing} failing · ${counts.met} met`
      : `${counts.met} met · 0 failing`;
  }
  renderRunHealth();
}

function runHealthCounts() {
  const counts = { met: 0, below: 0, above: 0, off: 0, unknown: 0 };
  for (const row of state.targets) {
    const entry = state.targetCells.get(String(row.index));
    const status = statusOf(row, entry?.value);
    if (status in counts) counts[status] += 1;
  }
  return counts;
}

function renderRunHealth() {
  const card = $('run-health');
  if (!card) return;
  const liveBadge = $('target-chart-live');
  if (liveBadge) liveBadge.hidden = !state.live.active;
  const counts = runHealthCounts();
  const total = state.targets.length;
  const failing = counts.below + counts.above;
  const charts = targetChartAccounts().length;
  const runInfo = (state.datasetSummary?.runs ?? []).find((run) => run.id === state.run);
  const period = currentPeriod();
  card.hidden = false;
  $('run-health-run').textContent = state.run ?? 'no run';
  $('run-health-meta').textContent = [
    runInfo?.kind ?? 'run',
    state.live.active ? 'live' : '',
    period?.label ?? 'no periods',
  ].filter(Boolean).join(' · ');
  const badges = $('run-health-badges');
  badges.replaceChildren();
  const badge = (text, className = '') => {
    const span = document.createElement('span');
    if (className) span.className = className;
    span.textContent = text;
    badges.append(span);
  };
  badge(`${total} targets`);
  badge(`${failing} failing`, failing ? 'failing' : '');
  badge(`${counts.met} met`);
  badge(`${counts.off} off`);
  badge(`${charts} chart${charts === 1 ? '' : 's'}`);
  if (state.runSource) {
    badge(`portfolio member${state.runSource.member ? ` ${state.runSource.member}` : ''}`);
    badge('member targets');
  }
  if (typeof state.runSummary?.exact_match === 'boolean') {
    badge(
      `exact replay ${state.runSummary.exact_match ? 'yes' : 'NO'}`,
      state.runSummary.exact_match ? 'available' : 'failing'
    );
  }
  badge(`LiDAR ${state.lidar?.available ? 'available' : '—'}`, state.lidar?.available ? 'available' : 'unavailable');
  badge(`Carbon ${state.carbon?.available ? 'available' : '—'}`, state.carbon?.available ? 'available' : 'unavailable');
  const fireScene = state.fire.scenes.find((scene) => scene.run === state.run);
  $('run-health-fire').hidden = !fireScene;
  $('run-health-failing').disabled = failing === 0;
}

function openPlanForAccount(account) {
  setWorkspace('plan');
  const search = $('target-filter-search');
  search.value = account;
  $('target-filter-status').value = '';
  applyTargetFilter();
  search.focus();
}

function showFailingTargets() {
  setWorkspace('plan');
  $('target-filter-search').value = '';
  $('target-filter-status').value = 'failing';
  applyTargetFilter();
  $('target-filter-search').focus();
}

function targetFilterMatches(row) {
  const search = $('target-filter-search')?.value.trim().toLowerCase() ?? '';
  const status = $('target-filter-status')?.value ?? '';
  const account = String(row.dataset.account ?? '').toLowerCase();
  const rowStatus = targetRowStatus(row);
  if (search && !account.includes(search)) return false;
  if (status === 'failing') return rowStatus === 'below' || rowStatus === 'above';
  if (status) return rowStatus === status;
  return true;
}

function applyTargetFilter() {
  const table = $('targets-table');
  const bar = $('target-filter-bar');
  const count = $('target-filter-count');
  if (!table || !bar || !count) return;
  if (table.hidden) {
    bar.hidden = true;
    return;
  }
  const rows = targetRows();
  let visible = 0;
  let visibleFailing = 0;
  let visibleTotal = 0;
  for (const row of rows) {
    const show = targetFilterMatches(row);
    row.hidden = !show;
    const detail = row.nextElementSibling;
    if (detail?.classList.contains('target-detail')) detail.hidden = !show;
    if (show) {
      visible += 1;
      if (['below', 'above'].includes(targetRowStatus(row))) visibleFailing += 1;
    }
    visibleTotal += 1;
  }
  bar.hidden = false;
  count.textContent = visible === visibleTotal
    ? `${visible} visible`
    : `${visible} of ${visibleTotal} visible`;
  const pin = $('target-pin-failing');
  const unpin = $('target-unpin-visible');
  if (pin) pin.disabled = visibleFailing === 0;
  if (unpin) unpin.disabled = visible === 0;
}

function clearTargetFilters() {
  $('target-filter-search').value = '';
  $('target-filter-status').value = '';
  applyTargetFilter();
  $('target-filter-search').focus();
}

function setRowPinned(row, pinned) {
  const box = row.querySelector('td.account input[type="checkbox"]');
  if (box) box.checked = pinned;
  const index = String(row.dataset.index);
  if (pinned) state.watched.add(index); else state.watched.delete(index);
}

function pinVisibleFailing() {
  let changed = false;
  for (const row of targetRows()) {
    if (row.hidden) continue;
    if (!['below', 'above'].includes(targetRowStatus(row))) continue;
    const index = String(row.dataset.index);
    if (!state.watched.has(index)) {
      state.watched.add(index);
      changed = true;
    }
    setRowPinned(row, true);
  }
  if (!changed) return;
  saveWatched();
  renderWatchPanel();
  renderTargetCharts();
  renderRunHealth();
  applyTargetFilter();
}

function unpinVisibleTargets() {
  let changed = false;
  for (const row of targetRows()) {
    if (row.hidden) continue;
    const index = String(row.dataset.index);
    if (state.watched.delete(index)) changed = true;
    setRowPinned(row, false);
  }
  if (!changed) return;
  saveWatched();
  renderWatchPanel();
  renderTargetCharts();
  renderRunHealth();
  applyTargetFilter();
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
    const indexKey = String(item.index);
    const valueKey = `${item.year}|${item.account}`;
    const value = Number(item.value);
    if (state.watched.has(indexKey)) { state.windowValues.set(valueKey, value); painted += 1; }
    const entry = state.targetCells.get(indexKey);
    if (entry) paintTarget(entry, value);
  }
  if (painted) {
    updateTargetSummary();
    applyTargetFilter();
    renderWatchPanel();
  }
  if (targetChartAccounts().some((account) => liveSeries.has(account))) renderTargetCharts();
  if (painted && iteration !== undefined) {
    $('run-status').textContent = `live target state at iteration ${iteration} (${painted} cells)`;
  }
}


function accountKind(account) {
  return String(account).startsWith('product.') ? 'flow' : 'level';
}

const ACCOUNT_TERMS = {
  conif: 'Conifer',
  dec: 'Deciduous',
  dom: 'DOM',
  ndy: 'NDY',
  even: 'Even flow',
  managed: 'managed',
  unmanaged: 'unmanaged',
};

function accountTableLabel(account) {
  const parts = String(account).split('.');
  if (parts.length < 2) return { root: '', label: String(account) };
  const root = parts.shift();
  const label = parts.map((part) => {
    const key = part.toLowerCase();
    if (ACCOUNT_TERMS[key]) return ACCOUNT_TERMS[key];
    return part
      .split('_')
      .map((word) => (word.length <= 3 ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1)))
      .join(' ');
  }).join(' · ');
  return { root, label };
}

function accountUnit(account, flow = false) {
  if (flow) return '%';
  const path = String(account).toLowerCase();
  if (path.includes('co2e')) return 'tCO2e';
  if (path.startsWith('carbon.')) return 'tC';
  if (path.startsWith('patch.') && path.endsWith('.size')) return '%';
  if (path.includes('.area.') || path.endsWith('.area')) return 'ha';
  if (path.includes('.yield.') || path.includes('.volume.') || path.endsWith('.volume')) return 'm³';
  return '';
}

function targetPeriodLabel(row) {
  if (row.period === null || row.period === undefined) {
    return { label: 'All', title: `whole horizon, ending year ${row.year ?? '—'}` };
  }
  return { label: `P${row.period}`, title: `period ${row.period}, ending year ${row.year ?? '—'}` };
}

function targetStatusLabel(status) {
  return {
    met: 'met',
    below: 'below min',
    above: 'above max',
    off: 'off',
    unknown: '—',
  }[status] ?? status;
}

function accountLastValue(account) {
  const years = state.series.get(account);
  if (!years || !years.size) return null;
  let lastYear = -Infinity;
  let lastValue = null;
  for (const [year, value] of years) {
    if (year > lastYear) { lastYear = year; lastValue = Number(value); }
  }
  return lastValue;
}

function formatAccountValue(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function accountIsTarget(account) {
  return state.targets.some((row) => row.account === account);
}

function renderAccountTree() {
  const tree = $('account-tree');
  if (!tree) return;
  const query = String($('account-search')?.value ?? '').trim().toLowerCase();
  const accounts = [...state.series.keys()].sort((a, b) => a.localeCompare(b));
  const matched = query ? accounts.filter((account) => account.toLowerCase().includes(query)) : accounts;
  tree.replaceChildren();
  $('account-count').textContent = `${matched.length} / ${accounts.length} accounts`;
  if (!matched.length) {
    const empty = document.createElement('p');
    empty.className = 'hint';
    empty.textContent = state.run ? 'no accounts match this search' : 'select a run to browse accounts';
    tree.append(empty);
    return;
  }
  const root = { children: new Map(), leaves: [] };
  for (const account of matched) {
    const parts = account.split('.');
    let node = root;
    for (const part of parts) {
      if (!node.children.has(part)) node.children.set(part, { children: new Map(), leaves: [] });
      node = node.children.get(part);
    }
    node.leaves.push(account);
  }
  const build = (node, depth) => {
    const fragment = document.createDocumentFragment();
    const children = [...node.children.keys()].sort((a, b) => a.localeCompare(b));
    for (const part of children) {
      const child = node.children.get(part);
      const group = document.createElement('details');
      group.open = query.length > 0 || depth === 0;
      const summary = document.createElement('summary');
      summary.textContent = part;
      group.append(summary, build(child, depth + 1));
      fragment.append(group);
    }
    for (const account of node.leaves) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'account-leaf';
      button.dataset.account = account;
      button.title = account;
      button.classList.toggle('selected', state.selectedAccounts.has(account));
      const name = document.createElement('span');
      name.className = 'name';
      name.textContent = account;
      const kind = document.createElement('span');
      kind.className = 'kind';
      kind.textContent = accountKind(account);
      kind.title = `${accountKind(account)} account`;
      const value = document.createElement('span');
      value.className = 'value';
      value.textContent = formatAccountValue(accountLastValue(account));
      button.append(name, kind, value);
      if (accountIsTarget(account)) {
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = 'target';
        button.append(badge);
      }
      button.addEventListener('click', () => {
        if ($('account-multi').checked) toggleSelection(account); else selectAccount(account);
      });
      fragment.append(button);
    }
    return fragment;
  };
  tree.append(build(root, 0));
}

function resetTargetForm() {
  $('new-target-period').value = '1';
  const width = state.targets.find((row) => Number(row.period_width) > 0)?.period_width ?? 10;
  $('new-target-width').value = String(width);
  $('new-target-min').value = '';
  $('new-target-max').value = '';
  $('new-target-min-weight').value = '1';
  $('new-target-max-weight').value = '1';
}

function renderSelection(reset = false) {
  const accounts = [...state.selectedAccounts].sort((a, b) => a.localeCompare(b));
  const picker = $('account-picker');
  if (!accounts.length) {
    state.pickedAccount = null;
    picker.hidden = true;
    $('new-target-status').textContent = '';
    return;
  }
  const wasHidden = picker.hidden;
  picker.hidden = false;
  state.pickedAccount = accounts.length === 1 ? accounts[0] : null;
  $('picked-account-name').textContent = accounts.length === 1
    ? accounts[0]
    : `${accounts.length} accounts selected`;
  const kinds = new Set(accounts.map(accountKind));
  $('picked-account-kind').textContent = kinds.size === 1 ? [...kinds][0] : 'mixed';
  $('picked-account-value').textContent = accounts.length === 1
    ? (accountLastValue(accounts[0]) === null
      ? 'no value'
      : `last value ${formatAccountValue(accountLastValue(accounts[0]))}`)
    : accounts.join(', ');
  if (reset || wasHidden) resetTargetForm();
  if (accounts.length === 1) {
    const existing = state.targets.filter((row) => row.account === accounts[0]).length;
    $('new-target-status').textContent = existing
      ? `${existing} existing target${existing === 1 ? '' : 's'} for this account`
      : '';
  } else {
    $('new-target-status').textContent = `${accounts.length} accounts selected; one target will be added for each`;
  }
}

function selectAccount(account) {
  state.selectedAccounts = new Set([account]);
  renderAccountTree();
  renderSelection(true);
}

function toggleSelection(account) {
  if (state.selectedAccounts.has(account)) state.selectedAccounts.delete(account);
  else state.selectedAccounts.add(account);
  renderAccountTree();
  renderSelection(false);
}

function clearSelection() {
  state.selectedAccounts.clear();
  $('account-multi').checked = false;
  renderAccountTree();
  renderSelection(false);
}

function targetKey(row) {
  return `${row.account}|${row.period ?? ''}|${row.year ?? ''}|${row.period_width ?? ''}|${row.flow ?? ''}`;
}

function validateTargetRows(rows) {
  const seen = new Map();
  for (const row of rows) {
    const account = String(row.account ?? '');
    if (!account) return 'every target needs an account';
    if ((row.minimum === null || row.minimum === undefined)
      && (row.maximum === null || row.maximum === undefined)) {
      return `${account}: enter a minimum, a maximum, or both`;
    }
    if (row.minimum !== null && row.minimum !== undefined
      && row.maximum !== null && row.maximum !== undefined
      && Number(row.minimum) > Number(row.maximum)) {
      return `${account}: minimum is above maximum`;
    }
    if (row.priority !== undefined && (!Number.isInteger(Number(row.priority))
      || Number(row.priority) < 1)) {
      return `${account}: priority must be a positive integer`;
    }
    if (row.normalization !== undefined
      && !['none', 'auto'].includes(String(row.normalization))) {
      return `${account}: normalization must be none or auto`;
    }
    const key = targetKey(row);
    if (seen.has(key)) return `duplicate target for ${account} in the same period`;
    seen.set(key, true);
  }
  return '';
}

function collectTargets() {
  const rows = state.targets.map(({ kind, ...row }) => ({ ...row }));
  for (const input of document.querySelectorAll('#targets-table [data-field]')) {
    const index = Number(input.dataset.index);
    const field = input.dataset.field;
    if (!rows[index] || !field) continue;
    rows[index][field] = field === 'notes' || field === 'normalization'
      ? input.value
      : input.value === '' ? null : Number(input.value);
  }
  return rows;
}

async function postTargets(rows, message) {
  const problem = validateTargetRows(rows);
  if (problem) {
    $('targets-status').textContent = `not saved: ${problem}`;
    return false;
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
    $('targets-status').textContent = message ?? `saved ${rows.length} targets`;
    showToast(message ?? `saved ${rows.length} targets`);
    await loadPeriods();
    await loadTargets();
    return true;
  } catch (error) {
    $('targets-status').textContent = `not saved: ${error.message}`;
    showToast('targets not saved', true);
    return false;
  }
}

async function addTarget() {
  const accounts = state.selectedAccounts.size
    ? [...state.selectedAccounts]
    : state.pickedAccount ? [state.pickedAccount] : [];
  const status = $('new-target-status');
  if (!accounts.length) { status.textContent = 'pick an account first'; return; }
  const period = Number($('new-target-period').value);
  const width = Number($('new-target-width').value);
  const minText = $('new-target-min').value;
  const maxText = $('new-target-max').value;
  const minimum = minText === '' ? null : Number(minText);
  const maximum = maxText === '' ? null : Number(maxText);
  const minWeight = Number($('new-target-min-weight').value);
  const maxWeight = Number($('new-target-max-weight').value);
  if (!Number.isInteger(period) || period < 0) { status.textContent = 'period must be a whole number of at least 0'; return; }
  if (!Number.isInteger(width) || width < 1) { status.textContent = 'width must be a whole number of at least 1'; return; }
  if (minimum === null && maximum === null) { status.textContent = 'enter a minimum, a maximum, or both'; return; }
  if (minimum !== null && !Number.isFinite(minimum)) { status.textContent = 'minimum must be a number'; return; }
  if (maximum !== null && !Number.isFinite(maximum)) { status.textContent = 'maximum must be a number'; return; }
  if (minimum !== null && maximum !== null && minimum > maximum) { status.textContent = 'minimum is above maximum'; return; }
  if (!Number.isFinite(minWeight) || minWeight < 0) { status.textContent = 'minimum weight must be zero or more'; return; }
  if (!Number.isFinite(maxWeight) || maxWeight < 0) { status.textContent = 'maximum weight must be zero or more'; return; }
  const rows = collectTargets();
  for (const account of accounts) {
    rows.push({
      index: rows.length,
      account,
      period,
      year: period * width,
      period_width: width,
      flow: '',
      shape: 'linear',
      minimum,
      maximum,
      min_weight: minWeight,
      max_weight: maxWeight,
      active: true,
    });
  }
  const label = accounts.length === 1 ? accounts[0] : `${accounts.length} accounts`;
  if (await postTargets(rows, `added target for ${label}`)) {
    status.textContent = `added ${label}`;
    clearSelection();
  }
}

async function removeTarget(index) {
  if (state.targets.length <= 1) {
    $('targets-status').textContent = 'the targets file cannot be empty; edit it directly to remove the last target';
    return;
  }
  const rows = collectTargets()
    .filter((_row, rowIndex) => rowIndex !== index)
    .map((row, rowIndex) => ({ ...row, index: rowIndex }));
  await postTargets(rows, 'removed target');
}

async function loadTargets() {
  const empty = $('targets-empty');
  const table = $('targets-table');
  const button = $('save-targets');
  try {
    state.chartDirty = false;
    setChartStatus('');
    state.targetCells = new Map();
    state.windowValues = new Map();
    const rows = await api('api/targets.json');
    rows.forEach((row) => { row.active = row.active !== false; });
    state.targets = rows;
    populateScanAccounts();
    renderPortfolioScan();
    const portfolioNote = $('portfolio-target-note');
    if (portfolioNote) {
      portfolioNote.hidden = !state.runSource;
      portfolioNote.textContent = state.runSource
        ? 'This run is a portfolio member. Its target status uses the member target file; this Plan editor still edits the live target file.'
        : '';
    }
    const deleteRun = $('delete-promoted-run');
    if (deleteRun) deleteRun.hidden = !state.runSource;
    await renderPortfolioMemberTargets();
    state.targetSeries = null;
    state.series = new Map();
    try {
      const catalog = await api(`api/runs/${encodeURIComponent(state.run)}/accounts`);
      for (const item of catalog) {
        const account = String(item.account);
        if (!state.series.has(account)) state.series.set(account, new Map());
        state.series.get(account).set(Number(item.year), Number(item.value));
      }
    } catch { /* the account tree is optional when a run has no values */ }
    populateScaffoldAccounts();
    try {
      state.targetSeries = await api(`api/runs/${encodeURIComponent(state.run)}/target-series`);
    } catch { /* the chart can still fall back to the target rows */ }
    renderAccountTree();
    const signature = rows
      .map((row) => `${row.index}|${row.account}|${row.period}|${row.year}|${row.period_width}`)
      .join(";");
    const targetsChanged = signature !== state.targetSignature;
    state.targetSignature = signature;
    if (!rows.length) {
      empty.hidden = false;
      table.hidden = true;
      button.hidden = true;
      $('target-sort-bar').hidden = true;
      $('target-filter-bar').hidden = true;
      $('target-summary').hidden = true;
      renderRunHealth();
      return;
    }
    empty.hidden = true;
    table.hidden = false;
    button.hidden = false;
    $('target-filter-bar').hidden = false;
    $('target-summary').hidden = false;
    if (!state.yearChosen) {
      selectPeriodForYear(Number(rows[0].year));
    }
    const body = table.querySelector('tbody');
    body.replaceChildren();
    const keys = rows.filter((row) => !row.flow).map((row) => String(row.index));
    if (targetsChanged || ![...state.watched].some((key) => keys.includes(key))) {
      state.watched.clear();
      const seen = new Set();
      for (const row of rows) {
        if (row.flow || seen.has(row.account)) continue;
        seen.add(row.account);
        state.watched.add(String(row.index));
        if (seen.size >= 3) break;
      }
      saveWatched();
    }
    const values = {};
    try {
      const realized = await api(`api/runs/${encodeURIComponent(state.run)}/targets`);
      for (const item of realized) {
        values[item.index] = item.value;
      }
    } catch { /* no realized values for this run */ }
    rows.forEach((row, index) => {
      const tr = document.createElement('tr');
      tr.classList.toggle('inactive', row.active === false);
      tr.dataset.index = String(index);
      tr.dataset.account = row.account;
      tr.dataset.period = row.period ?? '';
      tr.dataset.minimum = row.minimum ?? '';
      tr.dataset.maximum = row.maximum ?? '';
      tr.dataset.active = row.active === false ? '0' : '1';
      tr.dataset.status = 'unknown';
      const key = String(row.index);
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
        renderTargetCharts();
        updateTargetSummary();
        applyTargetFilter();
      });
      on.append(onBox);
      tr.append(on);
      const account = document.createElement('td');
      account.className = 'account';
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.checked = state.watched.has(key);
      box.title = 'pin this target chart';
      box.addEventListener('change', () => {
        if (box.checked) state.watched.add(key); else state.watched.delete(key);
        saveWatched();
        renderWatchPanel();
        renderTargetCharts();
        renderRunHealth();
      });
      const accountLine = document.createElement('span');
      accountLine.className = 'target-account-line';
      const labelInfo = accountTableLabel(row.account);
      if (labelInfo.root) {
        const root = document.createElement('span');
        root.className = 'account-root';
        root.textContent = labelInfo.root;
        root.title = `account root: ${labelInfo.root}`;
        accountLine.append(root);
      }
      const label = document.createElement('span');
      label.className = 'target-account-label';
      label.textContent = labelInfo.label;
      label.title = row.account;
      accountLine.append(label);
      const unit = accountUnit(row.account, Boolean(row.flow));
      if (unit) {
        const unitBadge = document.createElement('span');
        unitBadge.className = 'account-unit';
        unitBadge.textContent = unit;
        unitBadge.title = 'unit inferred from the account name';
        accountLine.append(unitBadge);
      }
      const valueLine = document.createElement('div');
      valueLine.className = 'account-value';
      account.append(box, accountLine, valueLine);
      tr.append(account);
      const year = document.createElement('td');
      year.className = 'target-period';
      const period = targetPeriodLabel(row);
      const periodLabel = document.createElement('span');
      periodLabel.className = 'target-period-label';
      periodLabel.textContent = period.label;
      const periodYear = document.createElement('span');
      periodYear.className = 'target-period-year';
      periodYear.textContent = `year ${row.year ?? '—'}`;
      year.title = period.title;
      year.append(periodLabel, periodYear);
      tr.append(year);
      for (const field of ['minimum', 'maximum']) {
        const td = document.createElement('td');
        td.append(numberInput(row[field], field, index));
        tr.append(td);
      }
      const statusCell = document.createElement('td');
      statusCell.className = 'target-status-cell';
      const statusBadge = document.createElement('span');
      statusBadge.className = 'target-status unknown';
      statusBadge.textContent = '—';
      statusCell.append(statusBadge);
      tr.append(statusCell);
      const actions = document.createElement('td');
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'remove-target';
      remove.textContent = '×';
      remove.title = `remove target for ${row.account}`;
      remove.setAttribute('aria-label', `remove target for ${row.account}`);
      remove.disabled = rows.length <= 1;
      remove.addEventListener('click', () => removeTarget(index));
      actions.append(remove);
      tr.append(actions);
      state.targetCells.set(String(row.index), {
        row, tr, text: valueLine, status: statusBadge, band: null, marker: null,
        value: values[row.index],
      });
      body.append(tr);
      const detail = document.createElement('tr');
      detail.className = 'target-detail';
      const detailCell = document.createElement('td');
      detailCell.colSpan = 7;
      const inner = document.createElement('div');
      inner.className = 'target-detail-inner';
      const minWeightLabel = document.createElement('label');
      minWeightLabel.append('Min w');
      const minWeight = numberInput(row.min_weight ?? 1, 'min_weight', index);
      minWeight.min = '0';
      minWeightLabel.append(minWeight);
      const maxWeightLabel = document.createElement('label');
      maxWeightLabel.append('Max w');
      const maxWeight = numberInput(row.max_weight ?? 1, 'max_weight', index);
      maxWeight.min = '0';
      maxWeightLabel.append(maxWeight);
      const normLabel = document.createElement('label');
      normLabel.append('Normalize');
      const norm = document.createElement('select');
      norm.dataset.index = String(index);
      norm.dataset.field = 'normalization';
      for (const optionValue of ['none', 'auto']) {
        const option = document.createElement('option');
        option.value = optionValue;
        option.textContent = optionValue;
        option.selected = (row.normalization || 'none') === optionValue;
        norm.append(option);
      }
      normLabel.append(norm);
      const priorityLabel = document.createElement('label');
      priorityLabel.append('Priority');
      const priority = document.createElement('input');
      priority.type = 'number';
      priority.min = '1';
      priority.step = '1';
      priority.value = row.priority ?? 1;
      priority.dataset.index = String(index);
      priority.dataset.field = 'priority';
      priorityLabel.append(priority);
      const kindLabel = document.createElement('label');
      kindLabel.append('Kind');
      const kind = document.createElement('span');
      kind.className = 'badge';
      kind.textContent = row.kind || (row.flow ? `flow.${row.flow}` : 'level');
      kindLabel.append(kind);
      const notesLabel = document.createElement('label');
      notesLabel.append('Notes');
      notesLabel.append(textInput(row.notes ?? '', 'notes', index));
      inner.append(minWeightLabel, maxWeightLabel, normLabel, priorityLabel, kindLabel, notesLabel);
      detailCell.append(inner);
      detail.append(detailCell);
      body.append(detail);
    });
    for (const entry of state.targetCells.values()) paintTarget(entry, entry.value);
    updateTargetSummary();
    applyTargetSort();
    for (const row of rows) {
      if (row.flow) continue;
      const value = values[row.index];
      if (value !== undefined) state.windowValues.set(`${row.year}|${row.account}`, Number(value));
    }
    renderWatchPanel();
    renderTargetCharts();
    renderAccountTree();
    if (state.skin) applySkin(state.skin);
  } catch (error) {
    empty.hidden = false;
    empty.textContent = `targets unavailable: ${error.message}`;
    table.hidden = true;
    button.hidden = true;
    $('target-sort-bar').hidden = true;
  }
}

async function saveTargets() {
  return postTargets(collectTargets());
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
let periodPlayTimer = null;
let periodPlayBusy = false;
let mapLoadSequence = 0;
let toastTimer = null;

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
  state.live.display = 'live';
  $('start-run').textContent = 'Solve';
  $('stop-run').hidden = true;
  state.runPaused = false;
  showRun(`run ${id} · done`, false);
  $('run-status').textContent = '';
  try {
    const summary = await api('api/summary');
    if (await fillRuns(summary, id)) {
      await loadPeriods(); await loadLayers(); await loadLidar(); await loadCarbon(); await loadDataset(); await loadTargets(); await loadProfiles(); await loadReports(); await loadMap();
    }
  } catch { /* the run is done; a refresh failure is not fatal */ }
  window.setTimeout(() => { $('run-panel').hidden = true; }, 6000);
}

function stepDetail(step) {
  if (!step) return '';
  const parts = [];
  if (step.current !== undefined && step.current !== null) {
    parts.push(`current ${Number(step.current).toFixed(2)}`);
  }
  if (step.accepted !== undefined && step.accepted !== null) {
    parts.push(`accepted ${Number(step.accepted).toLocaleString()}`);
  }
  return parts.length ? ` · ${parts.join(' · ')}` : '';
}

async function pollRun(id) {
  if (id !== runWatch.id) return;
  try {
    const status = await api(`api/runs/${encodeURIComponent(id)}/status`);
    state.runPaused = Boolean(status.paused);
    $('start-run').textContent = state.runPaused ? 'Resume' : 'Pause';
    if (status.status === 'failed') {
      stopRunWatch();
      $('start-run').textContent = 'Solve';
      $('stop-run').hidden = true;
      showRun(`run ${id} · the search exited without a summary — see console.log`, false);
      return;
    }
    if (!status.running) { await finishRun(id); return; }
    const step = status.last_step;
    const shown = state.live.total || step?.total || step?.iteration;
    const island = step?.island ? ` · ${step.island}` : '';
    const progress = step
      ? `${Number(shown).toLocaleString()} iterations · best ${Number(step.objective).toFixed(2)}${stepDetail(step)}${island}`
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
    $('start-run').textContent = state.runPaused ? 'Resume' : 'Pause';
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

function openRunStream(runId, islands = 1) {
  const events = new EventSource(`api/runs/${encodeURIComponent(runId)}/events`);
  runWatch.source = events;
  events.addEventListener('started', () => showRun(
    `run ${runId} · ${islands} island${Number(islands) === 1 ? '' : 's'} · connected · ${elapsed()}`,
    true,
  ));
  events.addEventListener('schedule', (event) => {
    const payload = JSON.parse(event.data);
    if (payload.reset) state.live.schedule = new Map();
    for (const [block, chain] of payload.changed ?? []) {
      state.live.schedule.set(String(block), chain);
    }
    updateLiveBlocks((payload.changed ?? []).map(([block]) => block), Boolean(payload.reset));
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
        `run ${runId} · ${Number(shown).toLocaleString()} iterations · best ${Number(step.objective).toFixed(2)}${stepDetail(step)}${island} · ${elapsed()}`,
        true,
      );
    }
  });
  events.addEventListener('targets', (event) => {
    const payload = JSON.parse(event.data);
    updateLiveTargets(payload.values ?? [], payload.iteration, payload.series ?? []);
  });
  events.addEventListener('done', () => finishRun(runId));
  events.addEventListener('error', () => {
    if (state.live.active) showRun(`run ${runId} · reconnecting…`, true);
  });
}

async function attachLiveRun(runId) {
  if (!runId) return false;
  if (runWatch.id === runId && runWatch.source && state.live.active) return true;
  let status;
  try {
    status = await api(`api/runs/${encodeURIComponent(runId)}/status`);
  } catch {
    return false;
  }
  if (!status.running) return false;
  stopRunWatch();
  runWatch = { id: runId, timer: null, source: null, started: Date.now(), done: false, islands: 1 };
  state.live = { active: true, schedule: new Map(), total: 0, display: 'live' };
  state.layerMode = 'current';
  state.mapTotals = null;
  state.runPaused = Boolean(status.paused);
  state.history = [];
  drawSpark();
  renderLayerTree();
  resetLiveMap();
  if (state.mapEngine === 'maplibre' && !state.lidarField) loadMap(true);
  $('start-run').disabled = false;
  $('start-run').textContent = state.runPaused ? 'Resume' : 'Pause';
  $('stop-run').hidden = false;
  pollRun(runId);
  runWatch.timer = setInterval(() => pollRun(runId), 2000);
  openRunStream(runId, 1);
  renderRunHealth();
  return true;
}

async function findLiveRun(runs) {
  const candidates = runs
    .filter((run) => run.kind === 'search' || String(run.id).startsWith('web-'))
    .sort((left, right) => String(right.id).localeCompare(String(left.id)))
    .slice(0, 10);
  for (const run of candidates) {
    try {
      const status = await api(`api/runs/${encodeURIComponent(run.id)}/status`);
      if (status.running) return run.id;
    } catch { /* a finished or missing run is not live */ }
  }
  return null;
}

async function startRun() {
  const profile = $('profile-select')?.value || '';
  const profileBar = $('profile-bar');
  if (profile && profileBar && !profileBar.hidden) {
    await startProfileRun();
    return;
  }
  stopRunWatch();
  const status = $('run-status');
  $('start-run').disabled = true;
  showRun('saving targets…', true);
  let saved = false;
  try { saved = await saveTargets(); } catch (error) { saved = false; }
  if (!saved) {
    $('start-run').disabled = false;
    $('start-run').textContent = 'Solve';
    const reason = $('targets-status').textContent || 'no reason given';
    showRun(`targets not saved: ${reason}`, false);
    return;
  }
  const iterations = Number($('run-iterations')?.value || 0);
  const patience = Number($('run-patience')?.value || 0);
  const timeLimit = ($('run-time-limit')?.value || '').trim();
  const seed = Number($('run-seed')?.value || 1);
  const years = Number($('run-years')?.value || 50);
  const islands = Number($('run-islands')?.value || 1);
  status.textContent = '';
  runWatch = { id: null, timer: null, source: null, started: Date.now(), done: false, islands: 1 };
  state.live = { active: true, schedule: new Map(), total: 0, display: 'live' };
  // a live search always has a schedule; the map must follow it, not a previous patch/cumulative view
  state.layerMode = 'current';
  state.mapTotals = null;
  renderLayerTree();
  resetLiveMap();
  if (state.mapEngine === 'maplibre' && !state.lidarField) loadMap(true);
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
      body: JSON.stringify({ iterations, patience, time_limit: timeLimit, seed, years, islands }),
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
    $('start-run').textContent = 'Pause';
    $('stop-run').hidden = false;
    showToast('run started');
    pollRun(run.id);
    runWatch.timer = setInterval(() => pollRun(run.id), 2000);
    openRunStream(run.id, runWatch.islands);
  } catch (error) {
    window.clearTimeout(timer);
    state.live.active = false;
    state.mapTotals = null;
    $('start-run').disabled = false;
    $('start-run').textContent = 'Solve';
    $('stop-run').hidden = true;
    if (state.mapEngine === 'maplibre' && !state.lidarField) loadMap();
    const reason = error.name === 'AbortError' ? 'the request timed out after 20 s' : error.message;
    showToast('run not started', true);
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

function timelinePeriodIndex(offset, periods = state.periods) {
  if (!periods.length) return -1;
  for (let index = 0; index < periods.length; index += 1) {
    if (offset >= Number(periods[index].start) && offset <= Number(periods[index].end)) return index;
  }
  return offset < Number(periods[0].start) ? 0 : periods.length - 1;
}

function timelineColor(label) {
  let hash = 0;
  for (let index = 0; index < label.length; index += 1) {
    hash = (hash * 31 + label.charCodeAt(index)) % 360;
  }
  return `hsl(${hash} 58% 43%)`;
}

function renderScheduleTimeline(rows) {
  const host = $('schedule-timeline');
  const status = $('timeline-status');
  const empty = $('timeline-empty');
  if (!host || !status || !empty) return;
  host.replaceChildren();
  if (!rows.length) {
    status.textContent = '';
    empty.hidden = false;
    return;
  }
  const header = rows[0].map((name) => String(name).trim().toLowerCase());
  const blockIndex = header.indexOf('block_id');
  const treatmentIndex = header.indexOf('treatment');
  const offsetIndex = header.indexOf('offset');
  if (blockIndex < 0 || treatmentIndex < 0 || offsetIndex < 0) {
    status.textContent = 'schedule.csv needs block_id, treatment, and offset columns';
    empty.hidden = true;
    return;
  }
  const periods = state.periods.length
    ? state.periods
    : [...new Set(rows.slice(1).map((row) => Number(row[offsetIndex])))].sort((a, b) => a - b)
        .map((offset, index) => ({ start: offset, end: offset, label: `P${index + 1}` }));
  const byTreatment = new Map();
  let events = 0;
  for (const row of rows.slice(1)) {
    const offset = Number(row[offsetIndex]);
    const treatment = String(row[treatmentIndex] ?? '').trim() || 'unspecified';
    const periodIndex = timelinePeriodIndex(offset, periods);
    if (periodIndex < 0) continue;
    const counts = byTreatment.get(treatment) ?? new Map();
    counts.set(periodIndex, (counts.get(periodIndex) ?? 0) + 1);
    byTreatment.set(treatment, counts);
    events += 1;
  }
  if (!byTreatment.size) {
    status.textContent = '';
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  const axis = document.createElement('div');
  axis.className = 'timeline-axis';
  const corner = document.createElement('span');
  corner.className = 'timeline-axis-corner';
  corner.textContent = 'treatment';
  axis.append(corner);
  const axisTrack = document.createElement('div');
  axisTrack.className = 'timeline-axis-track';
  for (let index = 0; index < periods.length; index += 1) {
    const tick = document.createElement('span');
    tick.textContent = periods[index].label ?? `P${index + 1}`;
    tick.title = periods[index].label ?? `Period ${index + 1}`;
    axisTrack.append(tick);
  }
  axis.append(axisTrack);
  host.append(axis);
  for (const [treatment, counts] of [...byTreatment].sort(([left], [right]) => left.localeCompare(right))) {
    const row = document.createElement('div');
    row.className = 'timeline-row';
    const label = document.createElement('span');
    label.className = 'timeline-label';
    label.textContent = treatment;
    label.title = treatment;
    const track = document.createElement('div');
    track.className = 'timeline-track';
    for (const [periodIndex, count] of counts) {
      const bar = document.createElement('button');
      bar.type = 'button';
      bar.className = 'timeline-bar';
      bar.style.left = `${(periodIndex / periods.length) * 100}%`;
      bar.style.width = `${100 / periods.length}%`;
      bar.style.background = timelineColor(treatment);
      bar.title = `${treatment} · ${periods[periodIndex]?.label ?? `Period ${periodIndex + 1}`} · ${count} block${count === 1 ? '' : 's'}`;
      bar.addEventListener('click', () => {
        stopPeriodPlay();
        state.yearChosen = true;
        setPeriod(periodIndex);
        status.textContent = `${treatment} · ${periods[periodIndex]?.label ?? `period ${periodIndex + 1}`} · ${count} block${count === 1 ? '' : 's'}`;
        if (state.workspace === 'map') loadMap(true);
      });
      track.append(bar);
    }
    row.append(label, track);
    host.append(row);
  }
  status.textContent = `${byTreatment.size} treatment${byTreatment.size === 1 ? '' : 's'} · ${events.toLocaleString()} scheduled block event${events === 1 ? '' : 's'} · click a bar to select its period`;
}

async function loadScheduleTimeline() {
  const status = $('timeline-status');
  const empty = $('timeline-empty');
  const host = $('schedule-timeline');
  if (!status || !empty || !host) return;
  if (!state.run) {
    status.textContent = 'select a run first';
    empty.hidden = true;
    host.replaceChildren();
    return;
  }
  status.textContent = 'loading schedule…';
  empty.hidden = true;
  host.replaceChildren();
  try {
    const response = await fetch(`api/runs/${encodeURIComponent(state.run)}/reports/schedule.csv`);
    if (!response.ok) throw new Error(response.statusText);
    renderScheduleTimeline(parseCsv(await response.text()));
  } catch (error) {
    status.textContent = `schedule unavailable: ${error.message}`;
    empty.hidden = false;
  }
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
  ['ending_inventory.csv', 'Ending inventory'],
];

function csvCell(value) {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function renderReportProvenance(provenance) {
  const host = $('report-provenance');
  const badge = $('report-provenance-badge');
  const detail = $('report-provenance-detail');
  const links = $('report-provenance-links');
  host.hidden = true;
  badge.textContent = '';
  badge.title = '';
  detail.textContent = '';
  links.replaceChildren();
  if (!provenance || typeof provenance !== 'object') return;
  const uncertainty = provenance.uncertainty && typeof provenance.uncertainty === 'object'
    ? provenance.uncertainty : {};
  const status = String(uncertainty.status || 'not_stated');
  const reports = Array.isArray(provenance.reports) ? provenance.reports : [];
  const sources = Array.isArray(provenance.sources) ? provenance.sources : [];
  badge.textContent = `provenance · uncertainty: ${status}`;
  badge.title = status === 'not_stated'
    ? 'no uncertainty metadata was supplied'
    : 'uncertainty status recorded by a source metadata file';
  detail.textContent = `${reports.length} report(s) hashed · ${sources.length} source metadata file(s)`;
  const addLink = (name, label) => {
    const link = document.createElement('a');
    link.href = `api/runs/${encodeURIComponent(state.run)}/reports/${encodeURIComponent(name)}`;
    link.textContent = label;
    link.addEventListener('click', (event) => { event.preventDefault(); showReport(name); });
    links.append(link);
  };
  addLink('report_provenance.json', 'provenance sidecar');
  for (const source of sources) {
    if (source && typeof source.name === 'string') addLink(source.name, source.name);
  }
  host.hidden = false;
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
  $('condition-card').replaceChildren();
  $('condition-card').hidden = true;
  $('condition-card-status').textContent = '';
  $('report-provenance').hidden = true;
  $('report-provenance-badge').textContent = '';
  $('report-provenance-detail').textContent = '';
  $('report-provenance-links').replaceChildren();
  try {
    const body = await api(`api/runs/${encodeURIComponent(state.run)}/reports`);
    const byName = new Map(body.map((report) => [report.name, report]));
    const sidecar = byName.get('report_provenance.json');
    renderReportProvenance(
      sidecar && sidecar.provenance && typeof sidecar.provenance === 'object'
        ? sidecar.provenance : null,
    );
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
    const firstPeriod = state.periods[0];
    const lastPeriod = state.periods[state.periods.length - 1];
    $('report-from').value = firstPeriod?.start ?? 0;
    $('report-to').value = lastPeriod?.end ?? 0;
    const accounts = await api(`api/runs/${encodeURIComponent(state.run)}/accounts`);
    let endingSummary = null;
    let targetRows = [];
    try {
      [endingSummary, targetRows] = await Promise.all([
        api(`api/runs/${encodeURIComponent(state.run)}/summary`),
        api(`api/runs/${encodeURIComponent(state.run)}/targets`),
      ]);
    } catch { /* an older run may not have either artifact */ }
    renderRunSnapshot(endingSummary);
    renderEndingSummary(endingSummary, targetRows);
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

function renderConditionCard(card) {
  const target = $('condition-card');
  const status = $('condition-card-status');
  target.replaceChildren();
  const summary = document.createElement('p');
  summary.textContent = `${card.report_id} · ${card.scenario_id} · review: ${card.review_status}`;
  target.append(summary);
  const indicators = Array.isArray(card.indicators) ? card.indicators : [];
  if (!indicators.length) {
    const empty = document.createElement('p');
    empty.className = 'hint';
    empty.textContent = 'No indicators were supplied.';
    target.append(empty);
  } else {
    const wrap = document.createElement('div');
    wrap.className = 'table-wrap';
    const table = document.createElement('table');
    const head = document.createElement('thead');
    const headRow = document.createElement('tr');
    for (const label of ['Indicator', 'Value', 'Source', 'Status', 'Uncertainty', 'Applicability']) {
      const th = document.createElement('th');
      th.textContent = label;
      headRow.append(th);
    }
    head.append(headRow);
    const body = document.createElement('tbody');
    for (const item of indicators) {
      const row = document.createElement('tr');
      const values = [
        item.name,
        `${item.value} ${item.unit}`,
        `${item.source} (${item.source_version})`,
        item.status,
        item.uncertainty == null
          ? 'not stated'
          : `${item.uncertainty} ${item.unit}${item.uncertainty_kind ? ` (${item.uncertainty_kind})` : ''}`,
        item.applicability ?? 'not stated',
      ];
      for (const value of values) {
        const cell = document.createElement('td');
        cell.textContent = String(value ?? '—');
        row.append(cell);
      }
      body.append(row);
    }
    table.append(head, body);
    wrap.append(table);
    target.append(wrap);
  }
  const alerts = Array.isArray(card.alerts) ? card.alerts : [];
  if (alerts.length) {
    const heading = document.createElement('p');
    heading.textContent = 'Advisory alerts';
    target.append(heading);
    const list = document.createElement('ul');
    for (const alert of alerts) {
      const item = document.createElement('li');
      item.textContent = `${alert.code} · ${alert.severity}: ${alert.message}`;
      list.append(item);
    }
    target.append(list);
  }
  const provenance = card.provenance && typeof card.provenance === 'object' ? card.provenance : {};
  const provenanceEntries = Object.entries(provenance);
  if (provenanceEntries.length) {
    const heading = document.createElement('p');
    heading.textContent = 'Provenance';
    target.append(heading);
    const list = document.createElement('ul');
    for (const [key, value] of provenanceEntries) {
      const item = document.createElement('li');
      item.textContent = `${key}: ${value}`;
      list.append(item);
    }
    target.append(list);
  }
  const limits = document.createElement('p');
  limits.className = 'hint';
  limits.textContent = 'Report-only. Alerts are advisory; not operational early warning.';
  target.append(limits);
  target.hidden = false;
  status.textContent = `${indicators.length} indicator(s) loaded`;
}

async function loadConditionCard() {
  const status = $('condition-card-status');
  const target = $('condition-card');
  target.replaceChildren();
  target.hidden = true;
  if (!state.run) { status.textContent = 'select a run first'; return; }
  status.textContent = 'loading condition card…';
  try {
    const card = await api(`api/runs/${encodeURIComponent(state.run)}/condition-card`);
    renderConditionCard(card);
  } catch (error) {
    status.textContent = `condition card unavailable: ${error.message}`;
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

function estate3dHeight(properties) {
  const treated = Boolean(properties?.treated);
  let height = treated ? 20 : 7;
  const age = properties?.age;
  if (age !== null && age !== undefined && Number.isFinite(Number(age))) {
    height += Math.min(Math.max(Number(age), 0), 200) * 0.10;
  }
  if (properties?.current) height += 5;
  return Math.max(4, Math.min(48, height));
}

function estate3dProject(x, y, transform) {
  const dx = x - transform.cx;
  const dy = y - transform.cy;
  const rx = dx * Math.cos(transform.yaw) - dy * Math.sin(transform.yaw);
  const ry = dx * Math.sin(transform.yaw) + dy * Math.cos(transform.yaw);
  return [
    transform.width / 2 + rx * transform.scale,
    transform.height / 2 + ry * transform.scale * transform.flatten,
  ];
}

function estate3dRings(feature) {
  const geometry = feature?.geometry;
  if (geometry?.type === 'Polygon') return geometry.coordinates;
  if (geometry?.type === 'MultiPolygon') return geometry.coordinates.flat();
  return [];
}

function estate3dColor(properties, selected) {
  if (selected) return '#d9822b';
  if (properties?.treated) return properties.current ? '#2f7d4f' : '#7aa36b';
  return '#b7b7a8';
}

function estate3dExtract(features) {
  const blocks = [];
  for (const feature of features) {
    const rings = estate3dRings(feature).filter((ring) => Array.isArray(ring) && ring.length >= 3);
    if (!rings.length) continue;
    const properties = feature.properties ?? {};
    blocks.push({
      block: properties.block_id,
      properties,
      rings,
      height: estate3dHeight(properties),
    });
  }
  return blocks;
}

function estate3dBounds(blocks) {
  const box = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
  for (const block of blocks) {
    for (const ring of block.rings) {
      for (const point of ring) {
        const x = Number(point[0]);
        const y = Number(point[1]);
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
        box.minX = Math.min(box.minX, x);
        box.minY = Math.min(box.minY, y);
        box.maxX = Math.max(box.maxX, x);
        box.maxY = Math.max(box.maxY, y);
      }
    }
  }
  return box;
}

function estate3dPointInRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    if (((yi > y) !== (yj > y)) && (x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)) inside = !inside;
  }
  return inside;
}

function estate3dPick(x, y) {
  for (let index = estate3dPick.hits.length - 1; index >= 0; index -= 1) {
    const hit = estate3dPick.hits[index];
    if (estate3dPointInRing(x, y, hit.ring)) return hit;
  }
  return null;
}
estate3dPick.hits = [];

function renderEstate3d() {
  if (!state.estate3d.open) return;
  const canvas = $('estate-3d-canvas');
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  const context = canvas.getContext('2d');
  if (!context) return;
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, rect.width, rect.height);
  const blocks = estate3dExtract(state.estate3d.features);
  if (blocks.length > ESTATE_3D_LIMIT) {
    $('estate-3d-status').textContent = `3D refused: ${blocks.length.toLocaleString()} blocks exceeds the ${ESTATE_3D_LIMIT.toLocaleString()} block budget`;
    return;
  }
  if (!blocks.length) {
    $('estate-3d-status').textContent = 'No polygon blocks available for the 3D replay';
    return;
  }
  const box = estate3dBounds(blocks);
  const dx = Math.max(box.maxX - box.minX, 1e-9);
  const dy = Math.max(box.maxY - box.minY, 1e-9);
  const scale = Math.min((rect.width - 80) / dx, (rect.height - 80) / dy) * 0.9 * state.estate3d.zoom;
  const transform = {
    cx: (box.minX + box.maxX) / 2,
    cy: (box.minY + box.maxY) / 2,
    scale: Math.max(scale, 1e-6),
    yaw: state.estate3d.yaw,
    width: rect.width,
    height: rect.height,
    flatten: 0.58,
  };
  const drawable = blocks.map((block) => {
    const rings = block.rings.map((ring) => ring.map((point) => estate3dProject(Number(point[0]), Number(point[1]), transform)));
    const depth = rings.reduce((sum, ring) => sum + ring.reduce((total, point) => total + point[1], 0), 0)
      / Math.max(1, rings.reduce((count, ring) => count + ring.length, 0));
    return { ...block, rings, depth };
  }).sort((a, b) => a.depth - b.depth);
  estate3dPick.hits = [];
  const selected = String(state.selectedBlock);
  for (const block of drawable) {
    const selectedBlock = String(block.block) === selected;
    const color = estate3dColor(block.properties, selectedBlock);
    const height = block.height * state.estate3d.exaggeration;
    for (const ring of block.rings) {
      for (let index = 0; index < ring.length; index += 1) {
        const current = ring[index];
        const next = ring[(index + 1) % ring.length];
        context.beginPath();
        context.moveTo(current[0], current[1]);
        context.lineTo(next[0], next[1]);
        context.lineTo(next[0], next[1] - height);
        context.lineTo(current[0], current[1] - height);
        context.closePath();
        context.fillStyle = selectedBlock ? 'rgba(217,130,43,.82)' : 'rgba(55,78,66,.55)';
        context.fill();
      }
    }
    for (const ring of block.rings) {
      context.beginPath();
      ring.forEach((point, index) => {
        if (index === 0) context.moveTo(point[0], point[1] - height);
        else context.lineTo(point[0], point[1] - height);
      });
      context.closePath();
      context.fillStyle = color;
      context.fill();
      context.strokeStyle = selectedBlock ? '#7a3f10' : 'rgba(24,42,34,.45)';
      context.lineWidth = selectedBlock ? 2 : 0.6;
      context.stroke();
      estate3dPick.hits.push({
        block: block.block,
        properties: block.properties,
        ring: ring.map((point) => [point[0], point[1] - height]),
      });
    }
  }
  const period = currentPeriod();
  $('estate-3d-status').textContent = `${blocks.length.toLocaleString()} blocks${period ? ` · ${period.label ?? `period ${state.periodIndex + 1}`}` : ''} · drag to orbit`;
}

async function loadEstate3dFeatures() {
  const local = state.features.filter((feature) => estate3dRings(feature).length);
  if (local.length && state.mapEngine !== 'maplibre') return local;
  const period = currentPeriod();
  const year = period ? Number(period.end) : Number(state.year);
  const layer = state.live.active ? 'treatments' : mapLayerName();
  let query = `api/runs/${encodeURIComponent(state.run)}/map?year=${year}&layer=${layer}`;
  if (layer === 'treatments' || layer === 'cumulative') query += periodQuery();
  if (layer === 'compartments' && state.compartmentAccount) {
    query += `&account=${encodeURIComponent(state.compartmentAccount)}`;
  }
  const body = await api(query);
  return body.features ?? [];
}

async function refreshEstate3d() {
  if (!state.estate3d.open) return;
  $('estate-3d-status').textContent = 'loading 3D geometry…';
  try {
    state.estate3d.features = await loadEstate3dFeatures();
    renderEstate3d();
  } catch (error) {
    $('estate-3d-status').textContent = `3D unavailable: ${error.message}`;
  }
}

function openEstate3d() {
  if (!state.run) { showToast('load a run before opening 3D', true); return; }
  state.estate3d.open = true;
  $('estate-3d').hidden = false;
  $('map-3d-toggle').setAttribute('aria-expanded', 'true');
  $('estate-3d').focus?.();
  refreshEstate3d();
}

function closeEstate3d() {
  state.estate3d.open = false;
  $('estate-3d').hidden = true;
  $('map-3d-toggle').setAttribute('aria-expanded', 'false');
  $('estate-3d-status').textContent = 'Experimental coarse view';
}

function showDetail(block, supplied = null, geometry = null) {
  const feature = state.features.find((candidate) => String(candidate.properties?.block_id) === String(block));
  const properties = supplied ?? feature?.properties;
  if (!properties) return;
  state.selectedBlock = block;
  $('map-wrap').dataset.selectedBlock = String(block);
  if (state.estate3d.open) renderEstate3d();
  if (state.mapEngine === 'maplibre') {
    state.selectedGeometry = geometry ?? feature?.geometry ?? null;
  }
  for (const [id, element] of state.blockElements) {
    element.classList.toggle('selected', String(id) === String(block));
  }
  if (state.mapEngine === 'maplibre') {
    if (!state.vectorActive) renderMapLibre(false);
    updateSelectedOverlay();
  }
  updateUrl({ push: false });
  if (state.compareView && state.compare) {
    const compare = supplied?.compare;
    const flags = compare
      ? { a: compare === 'a' || compare === 'both', b: compare === 'b' || compare === 'both' }
      : state.compare.blocks.get(String(block)) ?? { a: false, b: false };
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
  for (const field of state.lidar?.fields ?? []) {
    const value = properties[field.name];
    if (value === undefined || value === null || value === '') continue;
    const line = document.createElement('div');
    const number = Number(value);
    const text = Number.isFinite(number)
      ? number.toLocaleString(undefined, { maximumFractionDigits: 2 })
      : String(value);
    line.textContent = `${field.label}${field.unit ? ` (${field.unit})` : ''}: ${text}`;
    $('detail').append(line);
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

function wireChatSplitter() {
  const splitter = $('chat-splitter');
  const chat = $('chat-panel');
  const sidebar = $('sidebar');
  if (!splitter || !chat || !sidebar) return;
  const root = document.documentElement;
  const defaultHeight = 240;
  try {
    const saved = window.localStorage.getItem('ws4.chat-height');
    if (saved) root.style.setProperty('--chat-height', saved);
  } catch { /* ignore */ }
  let drag = null;
  splitter.addEventListener('pointerdown', (event) => {
    drag = { y: event.clientY, height: chat.getBoundingClientRect().height };
    splitter.setPointerCapture(event.pointerId);
    splitter.classList.add('dragging');
    event.preventDefault();
  });
  splitter.addEventListener('pointermove', (event) => {
    if (!drag) return;
    const available = sidebar.getBoundingClientRect().height - 160;
    const height = Math.max(128, Math.min(Math.max(128, available), drag.height - (event.clientY - drag.y)));
    root.style.setProperty('--chat-height', `${Math.round(height)}px`);
  });
  splitter.addEventListener('pointerup', () => {
    if (!drag) return;
    drag = null;
    splitter.classList.remove('dragging');
    try { window.localStorage.setItem('ws4.chat-height', root.style.getPropertyValue('--chat-height')); } catch { /* ignore */ }
  });
  splitter.addEventListener('pointercancel', () => {
    drag = null;
    splitter.classList.remove('dragging');
  });
  splitter.addEventListener('dblclick', () => {
    root.style.setProperty('--chat-height', `${defaultHeight}px`);
    try { window.localStorage.setItem('ws4.chat-height', `${defaultHeight}px`); } catch { /* ignore */ }
  });
  const clamp = () => {
    const available = Math.max(128, sidebar.getBoundingClientRect().height - 160);
    if (chat.getBoundingClientRect().height > available) {
      root.style.setProperty('--chat-height', `${Math.round(available)}px`);
    }
  };
  window.addEventListener('resize', clamp);
  clamp();
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

function chatContext() {
  const period = currentPeriod();
  const search = $('target-filter-search');
  const status = $('target-filter-status');
  const profile = $('profile-select');
  return {
    run: state.run || null,
    workspace: state.workspace,
    subview: currentSub(),
    period: period
      ? { index: state.periodIndex, label: period.label ?? null, year: Number(state.year) }
      : { index: state.periodIndex, year: Number(state.year) },
    selected_block: state.selectedBlock === null || state.selectedBlock === undefined
      ? null : String(state.selectedBlock),
    profile: profile?.value || null,
    target_filter: {
      search: search?.value?.trim() || null,
      status: status?.value || null,
    },
    account: state.pickedAccount || [...state.selectedAccounts][0] || null,
  };
}

function applyChatChip(chip) {
  const action = chip?.action;
  const target = chip?.target;
  if (action === 'open_workspace' && typeof target === 'string') {
    setWorkspace(target);
    return;
  }
  if (action === 'open_subview' && typeof target === 'string') {
    const [workspace, subview] = target.split(':');
    if (!workspace || !subview) return;
    setWorkspace(workspace);
    setSubView(workspace, subview);
    return;
  }
  if (action === 'set_period') {
    const index = Number(target);
    if (Number.isInteger(index) && index >= 0) setPeriod(index);
    return;
  }
  if (action === 'select_block' && typeof target === 'string') {
    const feature = state.features.find(
      (candidate) => String(candidate.properties?.block_id) === target,
    );
    if (!feature) {
      showToast(`block ${target} is not in this run`, true);
      return;
    }
    setWorkspace('map');
    showDetail(target);
    return;
  }
  if (action === 'stage_script' && typeof target === 'string') {
    if (!state.console.schema?.python?.enabled) {
      showToast('sandboxed Python is not enabled on this service', true);
      return;
    }
    setWorkspace('console');
    $('console-python-script').value = target;
    $('console-python-reviewed').checked = false;
    $('console-python-status').textContent =
      'assistant script staged — review the code and tick confirmation before running';
    $('console-python-script').focus();
    return;
  }
  if (action === 'ask' && typeof target === 'string') {
    const input = $('chat-input');
    if (!input) return;
    input.value = target;
    input.focus();
  }
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
    const request = () => fetch('api/chat', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        message,
        session: state.chatSession || null,
        run: state.run || null,
        year: state.year,
        async: true,
        context: chatContext(),
      }),
    });
    let response = await request();
    if ([502, 503, 504].includes(response.status)) {
      // The first turn can hit a cold reverse-proxy/agent timeout; one delayed retry recovers it.
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      response = await request();
    }
    let payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `chat failed (${response.status})`);
    if (payload.job) {
      // The agent turn runs in the background; short status polls keep proxy
      // timeouts from cutting off long tool-using turns.
      while (payload.status === 'running') {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const poll = await fetch(`api/chat/${encodeURIComponent(payload.job)}`);
        payload = await poll.json().catch(() => ({}));
        if (!poll.ok) throw new Error(payload.detail || `chat failed (${poll.status})`);
      }
      if (payload.status === 'error') throw new Error(payload.detail || 'chat failed');
    }
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
    if (Array.isArray(payload.chips) && payload.chips.length) {
      const row = document.createElement('div');
      row.className = 'chat-actions';
      for (const chip of payload.chips) {
        if (!chip || typeof chip.label !== 'string') continue;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'chat-chip';
        button.textContent = chip.label;
        button.title = chip.label;
        button.dataset.chatAction = chip.action || '';
        button.addEventListener('click', () => applyChatChip(chip));
        row.append(button);
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

function openHelp() {
  const dialog = $('help-dialog');
  if (!dialog) return;
  if (typeof dialog.showModal === 'function') dialog.showModal();
  else dialog.hidden = false;
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

function setAssistantVisible(visible) {
  const toggle = $('chat-toggle');
  if (toggle) toggle.hidden = !visible;
  if (!visible) {
    const panel = $('chat-panel');
    if (panel) panel.hidden = true;
  }
}

function openChat() {
  const panel = $('chat-panel');
  const toggle = $('chat-toggle');
  if (!panel || !toggle || toggle.hidden) return;
  panel.hidden = false;
  toggle.setAttribute('aria-expanded', 'true');
  $('chat-input').focus();
}

function closeChat() {
  const panel = $('chat-panel');
  const toggle = $('chat-toggle');
  if (panel) panel.hidden = true;
  if (toggle) toggle.setAttribute('aria-expanded', 'false');
}

async function loadAgent() {
  try {
    const info = await api('api/agent');
    const available = Boolean(info.enabled) && Boolean(info.available);
    setAssistantVisible(available);
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
    setAssistantVisible(false);
    $('chat-model').textContent = 'unavailable';
  }
}

const CONSOLE_TOKEN_KEY = 'ws4-console-token';

function consoleAuthHeaders() {
  return state.console.token ? { Authorization: `Bearer ${state.console.token}` } : {};
}

async function consoleApi(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      accept: 'application/json',
      ...consoleAuthHeaders(),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail ?? detail; } catch { /* not json */ }
    throw new Error(detail);
  }
  return response.json();
}

function readToken() {
  try { return sessionStorage.getItem(CONSOLE_TOKEN_KEY) || ''; } catch { return ''; }
}

function rememberConsoleToken(token) {
  try {
    if (token) sessionStorage.setItem(CONSOLE_TOKEN_KEY, token);
    else sessionStorage.removeItem(CONSOLE_TOKEN_KEY);
  } catch { /* session storage is optional */ }
}

async function loadConsole() {
  const tokenInput = $('console-token');
  const status = $('console-status');
  if (!state.console.token) state.console.token = readToken();
  if (tokenInput && state.console.token) tokenInput.value = state.console.token;
  if (!state.console.token) {
    status.textContent = 'enter the collaborator token';
    return;
  }
  status.textContent = 'connecting…';
  try {
    state.console.schema = await consoleApi('api/console');
    status.textContent = `connected · ${state.console.schema.workspace}`;
    renderConsoleCommands();
    $('console-run').disabled = false;
    const python = state.console.schema.python;
    $('console-python').hidden = !python?.enabled;
    $('console-python-run').disabled = !python?.enabled;
  } catch (error) {
    state.console.schema = null;
    status.textContent = `console unavailable: ${error.message}`;
    $('console-run').disabled = true;
  }
}

function renderConsoleCommands() {
  const select = $('console-command');
  if (!select) return;
  const previous = select.value;
  select.replaceChildren();
  for (const command of state.console.schema?.commands ?? []) {
    const option = document.createElement('option');
    option.value = command.name;
    option.textContent = command.name;
    option.title = command.description ?? '';
    select.appendChild(option);
  }
  if (previous && [...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  }
  renderConsoleFields();
}

function renderConsoleFields() {
  const container = $('console-fields');
  const select = $('console-command');
  if (!container || !select) return;
  container.replaceChildren();
  const command = (state.console.schema?.commands ?? []).find((item) => item.name === select.value);
  if (!command) return;
  const note = document.createElement('p');
  note.className = 'hint';
  note.textContent = `${command.description} Outputs are written to the job scratch directory.`;
  container.appendChild(note);
  for (const field of command.fields ?? []) {
    const label = document.createElement('label');
    label.className = 'console-field';
    label.textContent = field.required ? `${field.label} *` : field.label;
    const input = document.createElement('input');
    input.id = `console-field-${field.name}`;
    input.type = field.kind === 'number' ? 'number' : 'text';
    if (field.kind === 'number') input.step = 'any';
    input.spellcheck = false;
    input.value = field.default ?? '';
    input.placeholder = field.kind === 'dir' ? 'absolute directory path' : 'absolute file path';
    label.appendChild(input);
    container.appendChild(label);
  }
}

function consoleRequestBody() {
  const select = $('console-command');
  const command = (state.console.schema?.commands ?? []).find((item) => item.name === select.value);
  if (!command) throw new Error('select a console command');
  const body = { command: command.name };
  for (const field of command.fields ?? []) {
    const input = $(`console-field-${field.name}`);
    const value = input?.value?.trim() ?? '';
    if (!value) continue;
    body[field.name] = field.kind === 'number' ? Number(value) : value;
  }
  return body;
}

async function startConsoleJob() {
  const output = $('console-output');
  const status = $('console-job-status');
  const runButton = $('console-run');
  const cancelButton = $('console-cancel');
  output.textContent = '';
  state.console.offset = 0;
  state.console.job = null;
  runButton.disabled = true;
  $('console-python-run').disabled = true;
  cancelButton.disabled = true;
  status.textContent = 'starting…';
  try {
    const job = await consoleApi('api/console/jobs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(consoleRequestBody()),
    });
    state.console.job = job;
    status.textContent = `${job.command} · ${job.id} · ${job.status}`;
    cancelButton.disabled = false;
    pollConsoleJob(job.id);
  } catch (error) {
    status.textContent = `job rejected: ${error.message}`;
    runButton.disabled = false;
  }
}

function pollConsoleJob(id) {
  if (state.console.timer) window.clearInterval(state.console.timer);
  state.console.timer = window.setInterval(() => refreshConsoleJob(id), 700);
  refreshConsoleJob(id);
}

async function refreshConsoleJob(id) {
  if (state.console.busy) return;
  state.console.busy = true;
  try {
    const job = await consoleApi(`api/console/jobs/${encodeURIComponent(id)}`);
    state.console.job = job;
    const chunk = await consoleApi(
      `api/console/jobs/${encodeURIComponent(id)}/output?offset=${state.console.offset}`
    );
    if (chunk.text) {
      const output = $('console-output');
      output.textContent += chunk.text;
      state.console.offset = chunk.next_offset;
      output.scrollTop = output.scrollHeight;
    }
    $('console-job-status').textContent = `${job.command} · ${job.id} · ${job.status}`;
    if (['completed', 'failed', 'cancelled'].includes(job.status)) {
      let guard = 0;
      while (chunk.text.length >= 65536 && guard < 32) {
        const extra = await consoleApi(
          `api/console/jobs/${encodeURIComponent(id)}/output?offset=${state.console.offset}`
        );
        if (!extra.text) break;
        $('console-output').textContent += extra.text;
        state.console.offset = extra.next_offset;
        guard += 1;
      }
      if (state.console.timer) window.clearInterval(state.console.timer);
      state.console.timer = null;
      $('console-run').disabled = false;
      $('console-python-run').disabled = !state.console.schema?.python?.enabled;
      $('console-cancel').disabled = true;
      $('console-job-status').textContent = `${job.command} · ${job.id} · ${job.status}${job.error ? ` · ${job.error}` : ''}`;
      await loadConsoleArtifacts(id);
    }
  } catch (error) {
    $('console-job-status').textContent = `job status failed: ${error.message}`;
  } finally {
    state.console.busy = false;
  }
}

async function cancelConsoleJob() {
  if (!state.console.job) return;
  $('console-cancel').disabled = true;
  try {
    state.console.job = await consoleApi(
      `api/console/jobs/${encodeURIComponent(state.console.job.id)}/cancel`,
      { method: 'POST' }
    );
    $('console-job-status').textContent = `${state.console.job.command} · cancelling…`;
  } catch (error) {
    $('console-job-status').textContent = `cancel failed: ${error.message}`;
  }
}

async function loadConsoleArtifacts(id) {
  const container = $('console-artifacts');
  if (!container) return;
  container.replaceChildren();
  try {
    const artifacts = await consoleApi(`api/console/jobs/${encodeURIComponent(id)}/artifacts`);
    if (!artifacts.length) return;
    const title = document.createElement('p');
    title.className = 'hint';
    title.textContent = `${artifacts.length} artifact${artifacts.length === 1 ? '' : 's'}`;
    container.appendChild(title);
    for (const artifact of artifacts) {
      const row = document.createElement('div');
      row.className = 'console-artifact';
      const name = document.createElement('code');
      name.textContent = artifact.name;
      const download = document.createElement('button');
      download.type = 'button';
      download.textContent = 'Download';
      download.addEventListener('click', () => downloadConsoleArtifact(id, artifact.name));
      row.append(name, document.createTextNode(` ${relativeBytes(artifact.bytes)} `), download);
      container.appendChild(row);
    }
  } catch (error) {
    const note = document.createElement('p');
    note.className = 'hint';
    note.textContent = `artifacts unavailable: ${error.message}`;
    container.appendChild(note);
  }
}

async function downloadConsoleArtifact(id, name) {
  try {
    const response = await fetch(
      `api/console/jobs/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(name)}`,
      { headers: consoleAuthHeaders() }
    );
    if (!response.ok) throw new Error(response.statusText);
    const blob = await response.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = name.split('/').pop();
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  } catch (error) {
    showToast(`download failed: ${error.message}`, true);
  }
}

function relativeBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

async function startPythonJob() {
  const output = $('console-output');
  const status = $('console-python-status');
  const runButton = $('console-python-run');
  if (!state.console.schema?.python?.enabled) {
    status.textContent = 'sandboxed Python is disabled';
    return;
  }
  if (!$('console-python-reviewed').checked) {
    status.textContent = 'review the script and tick the confirmation first';
    return;
  }
  const script = $('console-python-script').value;
  if (!script.trim()) {
    status.textContent = 'enter a script';
    return;
  }
  const inputs = $('console-python-inputs').value
    .split('\n')
    .map((value) => value.trim())
    .filter(Boolean);
  output.textContent = '';
  state.console.offset = 0;
  state.console.job = null;
  runButton.disabled = true;
  $('console-run').disabled = true;
  $('console-cancel').disabled = true;
  status.textContent = 'starting sandbox…';
  try {
    const job = await consoleApi('api/console/python/jobs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ script, inputs, reviewed: true }),
    });
    state.console.job = job;
    status.textContent = `python · ${job.id} · ${job.status}`;
    $('console-cancel').disabled = false;
    pollConsoleJob(job.id);
  } catch (error) {
    status.textContent = `script rejected: ${error.message}`;
    runButton.disabled = false;
    $('console-run').disabled = false;
  }
}

function wireConsole() {
  if (!$('console-connect')) return;
  $('console-connect').addEventListener('click', () => {
    state.console.token = $('console-token').value.trim();
    rememberConsoleToken(state.console.token);
    loadConsole();
  });
  $('console-token').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      state.console.token = $('console-token').value.trim();
      rememberConsoleToken(state.console.token);
      loadConsole();
    }
  });
  $('console-command').addEventListener('change', renderConsoleFields);
  $('console-run').addEventListener('click', startConsoleJob);
  $('console-python-run').addEventListener('click', startPythonJob);
  $('console-cancel').addEventListener('click', cancelConsoleJob);
}

function fireSceneByRun(run) {
  return state.fire.scenes.find((scene) => scene.run === run) ?? null;
}

function fireSceneLabel(scene) {
  const manifest = scene.manifest ?? {};
  return `${scene.run} · ${manifest.scene_id ?? scene.scene}`;
}

async function loadFireScenes({ run = null } = {}) {
  const status = $('fire-status');
  status.textContent = 'loading scenes…';
  try {
    const scenes = await api('api/fire/scenes');
    state.fire.scenes = Array.isArray(scenes) ? scenes : [];
  } catch (error) {
    state.fire.scenes = [];
    status.textContent = `fire scenes unavailable: ${error.message}`;
  }
  const selectA = $('fire-scene-a');
  const selectB = $('fire-scene-b');
  selectA.replaceChildren();
  selectB.replaceChildren();
  for (const scene of state.fire.scenes) {
    for (const select of [selectA, selectB]) {
      const option = document.createElement('option');
      option.value = scene.run;
      option.textContent = fireSceneLabel(scene);
      select.appendChild(option);
    }
  }
  const preferred = fireSceneByRun(run ?? state.run)
    ?? fireSceneByRun(state.fire.selected)
    ?? state.fire.scenes[0]
    ?? null;
  selectB.disabled = state.fire.scenes.length < 2;
  $('fire-compare').disabled = state.fire.scenes.length < 2;
  if (!preferred) {
    $('fire-frame-a').removeAttribute('src');
    $('fire-summary').replaceChildren();
    status.textContent = 'no fire scenes found in the run directory';
    return;
  }
  selectA.value = preferred.run;
  await setFireScene('a', preferred.run);
  status.textContent = `${state.fire.scenes.length} scene${state.fire.scenes.length === 1 ? '' : 's'}`;
}

async function setFireScene(which, run) {
  const scene = fireSceneByRun(run);
  if (!scene) return;
  if (which === 'a') state.fire.selected = run;
  else state.fire.selectedB = run;
  const frame = $(which === 'a' ? 'fire-frame-a' : 'fire-frame-b');
  const label = $(which === 'a' ? 'fire-label-a' : 'fire-label-b');
  frame.src = `${scene.viewer}?embedded=1&bloom=0`;
  label.textContent = `${which.toUpperCase()} · ${fireSceneLabel(scene)}`;
  if (which === 'a') {
    state.fire.playing = false;
    $('fire-play').textContent = 'Play';
    state.fire.activePayload = await loadFirePayload(scene);
    renderFireSummary(scene, state.fire.activePayload);
    renderFireTreeOptions();
    renderFireFragmentOptions();
  }
}

async function loadFirePayload(scene) {
  if (state.fire.payloads.has(scene.run)) return state.fire.payloads.get(scene.run);
  const payload = await api(scene.payload);
  state.fire.payloads.set(scene.run, payload);
  return payload;
}

function fireSummaryRow(label, value) {
  const row = document.createElement('div');
  const key = document.createElement('span');
  key.textContent = label;
  const strong = document.createElement('strong');
  strong.textContent = String(value ?? '—');
  row.append(key, strong);
  return row;
}

function renderFireSummary(scene, payload) {
  const container = $('fire-summary');
  const manifest = payload?.manifest ?? scene.manifest ?? {};
  const timeline = payload?.timeline ?? {};
  container.replaceChildren(
    fireSummaryRow('Run', scene.run),
    fireSummaryRow('Scene', manifest.scene_id),
    fireSummaryRow('Trees', manifest.tree_count),
    fireSummaryRow('Fragments', manifest.fragment_count),
    fireSummaryRow('Synthetic layer', manifest.synthetic_trees ? 'yes' : 'no'),
    fireSummaryRow('Timeline end', `${Number(timeline.end ?? 0).toFixed(1)} ${timeline.unit ?? ''}`),
    fireSummaryRow('Replay token', manifest.run_replay_token)
  );
}

function renderFireTreeOptions() {
  const select = $('fire-tree');
  const query = $('fire-tree-search').value.trim().toLowerCase();
  const trees = state.fire.activePayload?.trees ?? [];
  const matches = trees.filter((tree) => {
    if (!query) return true;
    return `${tree.tree_id} ${tree.species} ${tree.fragment_id}`.toLowerCase().includes(query);
  });
  select.replaceChildren();
  for (const tree of matches.slice(0, 1000)) {
    const option = document.createElement('option');
    option.value = String(tree.tree_id);
    option.textContent = `${tree.tree_id} · ${tree.species} · fragment ${tree.fragment_id}`;
    select.appendChild(option);
  }
  $('fire-tree-detail').textContent = matches.length
    ? `${matches.length} matching tree${matches.length === 1 ? '' : 's'}`
    : 'no matching trees';
  if (matches.length) renderFireTreeDetail(matches[0]);
}

function renderFireTreeDetail(tree) {
  if (!tree) return;
  const detail = $('fire-tree-detail');
  detail.replaceChildren(
    fireSummaryRow('Species', tree.species),
    fireSummaryRow('Fragment', tree.fragment_id),
    fireSummaryRow('DBH cm', Number(tree.dbh_cm).toFixed(1)),
    fireSummaryRow('Height m', Number(tree.height_m).toFixed(1)),
    fireSummaryRow('Crown ratio', Number(tree.crown_ratio).toFixed(2)),
    fireSummaryRow('Crown fuel t', Number(tree.crown_fuel_t).toFixed(2)),
    fireSummaryRow('Surface fuel t/ha', Number(tree.surface_fuel_t_ha).toFixed(2)),
    fireSummaryRow('Ignition', tree.burn_time === null ? 'unburned' : `${Number(tree.burn_time).toFixed(1)} ${state.fire.activePayload?.timeline?.unit ?? ''}`),
    fireSummaryRow('Flame intensity', Number(tree.flame_intensity).toFixed(2)),
    fireSummaryRow('Post-fire', tree.post_fire_state)
  );
}

function renderFireFragmentOptions() {
  const select = $('fire-fragment');
  const stands = state.fire.activePayload?.stands ?? [];
  select.replaceChildren();
  for (const stand of stands) {
    const option = document.createElement('option');
    option.value = String(stand.fragment_id);
    option.textContent = `fragment ${stand.fragment_id} · ${Number(stand.area_ha).toFixed(1)} ha`;
    select.appendChild(option);
  }
  if (stands.length) renderFireFragmentDetail(stands[0]);
  else $('fire-fragment-detail').textContent = 'no fragments in this scene';
}

function renderFireFragmentDetail(stand) {
  if (!stand) return;
  const unit = state.fire.activePayload?.timeline?.unit ?? '';
  $('fire-fragment-detail').replaceChildren(
    fireSummaryRow('Fragment', stand.fragment_id),
    fireSummaryRow('Area ha', Number(stand.area_ha).toFixed(1)),
    fireSummaryRow('Burn time', stand.burn_time === null ? 'unburned' : `${Number(stand.burn_time).toFixed(1)} ${unit}`)
  );
}

function firePost(action, extra = {}) {
  const message = { type: 'ws4-fire', action, ...extra };
  for (const id of ['fire-frame-a', 'fire-frame-b']) {
    const frame = $(id);
    if (frame?.contentWindow) frame.contentWindow.postMessage(message, '*');
  }
}

async function openFireForRun(run) {
  await loadFireScenes({ run });
  if (fireSceneByRun(run)) setWorkspace('fire');
}

async function loadFireWorkspace() {
  if (!state.fire.scenes.length) await loadFireScenes();
  else if (state.fire.selected) await setFireScene('a', state.fire.selected);
}

function wireFire() {
  if (!$('fire-scene-a')) return;
  $('fire-refresh').addEventListener('click', () => loadFireScenes());
  $('fire-scene-a').addEventListener('change', () => setFireScene('a', $('fire-scene-a').value));
  $('fire-scene-b').addEventListener('change', () => setFireScene('b', $('fire-scene-b').value));
  $('fire-compare').addEventListener('change', async () => {
    const enabled = $('fire-compare').checked;
    $('fire-frame-card-b').hidden = !enabled;
    $('fire-wrap').classList.toggle('compare', enabled);
    if (enabled) {
      const fallback = state.fire.scenes.find((scene) => scene.run !== state.fire.selected);
      const run = $('fire-scene-b').value || fallback?.run;
      if (run) {
        $('fire-scene-b').value = run;
        await setFireScene('b', run);
      }
    }
  });
  $('fire-play').addEventListener('click', () => {
    state.fire.playing = !state.fire.playing;
    $('fire-play').textContent = state.fire.playing ? 'Pause' : 'Play';
    firePost(state.fire.playing ? 'play' : 'pause');
  });
  $('fire-reset').addEventListener('click', () => {
    state.fire.playing = false;
    $('fire-play').textContent = 'Play';
    $('fire-time').value = '0';
    firePost('reset');
  });
  $('fire-ignition').addEventListener('click', () => {
    state.fire.playing = true;
    $('fire-play').textContent = 'Pause';
    $('fire-time').value = '0';
    firePost('reset');
    firePost('play');
  });
  $('fire-jump').addEventListener('click', () => {
    const end = Number($('fire-time').max) || 1;
    const time = end * 0.25;
    state.fire.playing = true;
    $('fire-play').textContent = 'Pause';
    $('fire-time').value = String(time);
    firePost('setTime', { time });
    firePost('focus');
    firePost('play');
  });
  $('fire-fullscreen').addEventListener('click', () => {
    const wrap = $('fire-wrap');
    if (document.fullscreenElement) document.exitFullscreen();
    else wrap.requestFullscreen?.();
  });
  $('fire-time').addEventListener('input', () => {
    state.fire.playing = false;
    $('fire-play').textContent = 'Play';
    firePost('setTime', { time: Number($('fire-time').value) });
  });
  $('fire-speed').addEventListener('change', () => {
    firePost('speed', { speed: Number($('fire-speed').value) });
  });
  $('fire-tree-search').addEventListener('input', renderFireTreeOptions);
  $('fire-tree').addEventListener('change', () => {
    const tree = (state.fire.activePayload?.trees ?? []).find(
      (candidate) => String(candidate.tree_id) === $('fire-tree').value
    );
    renderFireTreeDetail(tree);
    if (tree) firePost('focusTree', { tree_id: tree.tree_id });
  });
  $('fire-fragment').addEventListener('change', () => {
    const stand = (state.fire.activePayload?.stands ?? []).find(
      (candidate) => String(candidate.fragment_id) === $('fire-fragment').value
    );
    renderFireFragmentDetail(stand);
  });
  window.addEventListener('message', (event) => {
    const data = event.data;
    if (!data || data.type !== 'ws4-fire-state') return;
    if (event.source !== $('fire-frame-a')?.contentWindow) return;
    const end = Number(data.end ?? 1);
    $('fire-time').max = String(end);
    $('fire-time').value = String(data.time ?? 0);
    $('fire-clock').textContent = `${Number(data.time ?? 0).toFixed(1)} ${data.unit ?? ''}`;
    state.fire.playing = Boolean(data.playing);
    $('fire-play').textContent = state.fire.playing ? 'Pause' : 'Play';
    $('fire-status').textContent =
      `${data.burning ?? 0} burning · ${data.burnt ?? 0} burnt trees`;
  });
}

function wireControls() {
  wireSplitter();
  wireChatSplitter();
  $('start-run').addEventListener('click', () => {
    if (state.live.active) togglePause(); else startRun();
  });
  $('stop-run').addEventListener('click', stopRun);
  $('play-periods').addEventListener('click', togglePeriodPlay);
  $('help-toggle').addEventListener('click', openHelp);
  $('help-close').addEventListener('click', () => $('help-dialog').close());
  $('map-3d-toggle').addEventListener('click', openEstate3d);
  $('estate-3d-close').addEventListener('click', closeEstate3d);
  $('estate-3d-reset').addEventListener('click', () => {
    state.estate3d.yaw = -0.55;
    state.estate3d.zoom = 1;
    renderEstate3d();
  });
  $('estate-3d-exaggeration').addEventListener('input', (event) => {
    state.estate3d.exaggeration = Number(event.target.value) || 1;
    renderEstate3d();
  });
  {
    const canvas = $('estate-3d-canvas');
    let drag = null;
    canvas.addEventListener('pointerdown', (event) => {
      drag = { x: event.clientX, y: event.clientY, yaw: state.estate3d.yaw, moved: false };
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener('pointermove', (event) => {
      if (!drag) return;
      if (Math.abs(event.clientX - drag.x) + Math.abs(event.clientY - drag.y) > 3) drag.moved = true;
      state.estate3d.yaw = drag.yaw + (event.clientX - drag.x) * 0.008;
      renderEstate3d();
    });
    canvas.addEventListener('pointerup', (event) => {
      if (!drag) return;
      const moved = drag.moved;
      drag = null;
      if (moved) return;
      const rect = canvas.getBoundingClientRect();
      const hit = estate3dPick(event.clientX - rect.left, event.clientY - rect.top);
      if (hit) showDetail(hit.block, hit.properties);
    });
    canvas.addEventListener('wheel', (event) => {
      event.preventDefault();
      state.estate3d.zoom = Math.min(3, Math.max(0.4, state.estate3d.zoom * Math.exp(-event.deltaY * 0.001)));
      renderEstate3d();
    }, { passive: false });
  }
  window.addEventListener('resize', () => {
    if (state.estate3d.open) renderEstate3d();
  });
  for (const button of document.querySelectorAll('#targets-table thead .sort-button')) {
    button.addEventListener('click', () => sortTargetTable(button.dataset.sort));
  }
  $('target-sort-reset').addEventListener('click', () => {
    state.targetSort = { key: null, direction: 1 };
    applyTargetSort();
  });
  $('target-filter-search').addEventListener('input', applyTargetFilter);
  $('target-filter-status').addEventListener('change', applyTargetFilter);
  $('target-filter-clear').addEventListener('click', clearTargetFilters);
  $('target-pin-failing').addEventListener('click', pinVisibleFailing);
  $('target-unpin-visible').addEventListener('click', unpinVisibleTargets);
  $('run-health-plan').addEventListener('click', () => setWorkspace('plan'));
  $('run-health-fire').addEventListener('click', () => openFireForRun(state.run));
  $('run-health-failing').addEventListener('click', showFailingTargets);
  for (const button of document.querySelectorAll('.workspaces [data-workspace]')) {
    button.addEventListener('click', () => setWorkspace(button.dataset.workspace));
  }
  for (const button of document.querySelectorAll('#results-nav [data-sub], #data-nav [data-sub]')) {
    button.addEventListener('click', () => {
      const workspace = button.closest('.workspace')?.id.replace('workspace-', '');
      if (workspace) setSubView(workspace, button.dataset.sub);
    });
  }
  wireTablist('.workspaces [role="tab"]');
  wireTablist('#results-nav [role="tab"]');
  wireTablist('#data-nav [role="tab"]');
  $('lidar-field').addEventListener('change', (event) => {
    state.lidarField = event.target.value;
    updateLidarRange();
    loadMap();
  });
  $('carbon-account').addEventListener('change', (event) => {
    state.carbonAccount = event.target.value;
    drawCarbonChart();
  });
  $('run').addEventListener('change', async (event) => {
    stopRunWatch();
    stopPeriodPlay();
    state.live.active = false;
    state.live.display = 'live';
    state.live.schedule = new Map();
    state.mapTotals = null;
    state.run = event.target.value;
    state.selectedBlock = null;
    state.selectedGeometry = null;
    delete $('map-wrap').dataset.selectedBlock;
    updateSelectedOverlay();
    $('detail').replaceChildren();
    await loadRunContext();
    await attachLiveRun(state.run);
    updateUrl();
  });
  $('year').addEventListener('input', (event) => {
    stopPeriodPlay();
    state.yearChosen = true;
    setPeriod(Number(event.target.value));
  });
  $('year').addEventListener('change', () => {
    if (state.compareView) { loadComparison(); return; }
    if (state.live.active) render(false); else loadMap(true);
    if (state.showUsedRoads) loadUsedRoads();
  });
  document.addEventListener('keydown', (event) => {
    const active = document.activeElement;
    const tag = active?.tagName;
    const typing = tag === 'TEXTAREA' || tag === 'SELECT' || active?.isContentEditable
      || (tag === 'INPUT' && active.type !== 'range');
    if (event.key === 'Escape') {
      if (!$('estate-3d').hidden) {
        closeEstate3d();
        return;
      }
      if ($('help-dialog').open) {
        $('help-dialog').close();
        return;
      }
      if (!$('chat-panel').hidden) {
        closeChat();
        return;
      }
    }
    if (typing || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === '?') {
      event.preventDefault();
      openHelp();
      return;
    }
    if (event.key === '/') {
      event.preventDefault();
      const accountSearch = $('account-search');
      if (accountSearch && !accountSearch.closest('[hidden]')) accountSearch.focus();
      else $('target-filter-search').focus();
      return;
    }
    if (event.key.toLowerCase() === 'm') {
      event.preventDefault();
      setWorkspace('map');
      return;
    }
    if (event.key.toLowerCase() === 'j' || event.key.toLowerCase() === 'k') {
      const rows = [...document.querySelectorAll('#targets-table tbody tr')];
      if (!rows.length) return;
      event.preventDefault();
      const current = rows.indexOf(document.activeElement);
      const next = event.key.toLowerCase() === 'j'
        ? Math.min(rows.length - 1, current < 0 ? 0 : current + 1)
        : Math.max(0, current < 0 ? 0 : current - 1);
      rows[next].tabIndex = -1;
      rows[next].focus({ preventScroll: true });
      rows[next].scrollIntoView({ block: 'nearest' });
      return;
    }
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    if (event.shiftKey) return;
    if (!state.periods.length) return;
    const next = state.periodIndex + (event.key === 'ArrowRight' ? 1 : -1);
    if (next < 0 || next >= state.periods.length) return;
    event.preventDefault();
    state.yearChosen = true;
    setPeriod(next);
    if (state.compareView) loadComparison();
    else if (state.live.active) render(false);
    else loadMap(true);
    if (state.showUsedRoads) loadUsedRoads();
  });
  $('skin').addEventListener('change', async (event) => {
    const skins = await api('api/skins');
    const skin = skins.find((candidate) => candidate.id === event.target.value);
    if (skin) { applySkin(skin); await loadTargets(); }
  });
  $('save-targets').addEventListener('click', saveTargets);
  $('apply-profile').addEventListener('click', applyProfile);
  $('run-profile').addEventListener('click', startProfileRun);
  $('target-chart-save').addEventListener('click', saveTargetCharts);
  $('account-search').addEventListener('input', renderAccountTree);
  $('account-multi').addEventListener('change', (event) => {
    if (!event.target.checked && state.selectedAccounts.size > 1) {
      const keep = [...state.selectedAccounts][0];
      state.selectedAccounts = new Set([keep]);
      renderSelection(false);
    }
    renderAccountTree();
  });
  $('clear-target-selection').addEventListener('click', clearSelection);
  $('account-search').addEventListener('keydown', (event) => {
    const leaves = [...document.querySelectorAll('.account-leaf')];
    if (!leaves.length) return;
    if (event.key === 'Enter') {
      event.preventDefault();
      leaves[0].click();
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      leaves[0].focus();
    }
  });
  $('account-tree').addEventListener('keydown', (event) => {
    const leaves = [...document.querySelectorAll('.account-leaf')];
    const index = leaves.indexOf(document.activeElement);
    if (index < 0) return;
    if (event.key === 'ArrowDown' && index + 1 < leaves.length) {
      event.preventDefault();
      leaves[index + 1].focus();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      (leaves[index - 1] ?? $('account-search')).focus();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      $('account-search').focus();
    }
  });
  $('add-target').addEventListener('click', addTarget);
  $('build-report').addEventListener('click', buildReport);
  $('load-condition-card').addEventListener('click', loadConditionCard);
  $('compare-a').addEventListener('change', loadComparison);
  $('compare-b').addEventListener('change', loadComparison);
  $('compare-filter').addEventListener('input', renderCompareAccounts);
  $('search-select').addEventListener('change', (event) => renderSearchArtifact(event.target.value));
  $('run-portfolio').addEventListener('click', startPortfolio);
  $('search-delete').addEventListener('click', deleteSearchArtifact);
  $('search-clean-failed').addEventListener('click', cleanFailedArtifacts);
  $('delete-promoted-run').addEventListener('click', deletePromotedRun);
  $('search-explore').addEventListener('click', () => {
    const id = $('search-select').value;
    if (!id) return;
    state.pareto.artifact = id;
    setWorkspace('pareto');
  });
  $('run-tune').addEventListener('click', startTune);
  $('chat-toggle').addEventListener('click', openChat);
  $('chat-close').addEventListener('click', closeChat);
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

async function loadRunContext() {
  setMapLoading(true, 'Loading run…');
  try {
    await loadSkins();
    await loadAgent();
    try {
      const runSummary = await api(`api/runs/${encodeURIComponent(state.run)}/summary`);
      state.runSummary = runSummary;
      state.runSource = runSummary.portfolio_source ?? null;
    } catch {
      state.runSummary = null;
      state.runSource = null;
    }
    await loadPeriods();
    if (state.pendingPeriod !== null) {
      setPeriod(Number(state.pendingPeriod));
      state.pendingPeriod = null;
    }
    await loadLayers();
    await loadLidar();
    await loadCarbon();
    await loadDataset();
    await loadTargets();
    await loadProfiles();
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
    if (state.pendingBlock !== null) {
      showDetail(state.pendingBlock);
      state.pendingBlock = null;
    }
    document.title = `WS4 — ${state.datasetSummary?.dataset ?? 'dataset'} — ${state.run}`;
  } finally {
    setMapLoading(false);
  }
}

async function start() {
  if (!$('run-years') || !$('start-run') || !$('watch-panel')) {
    statusLine('this page is an older build — hard-reload (Ctrl-Shift-R) once');
    return;
  }
  wireControls();
  wireSdmd();
  wirePareto();
  wireConsole();
  wireFire();
  wirePortfolioScan();
  wireScaffoldTargets();
  loadWatched();
  try {
    const summary = await api('api/summary');
    state.datasetSummary = summary;
    syncNavigation();
    $('dataset-name').textContent = summary.dataset ?? '';
    const select = $('run');
    for (const run of summary.runs ?? []) {
      const option = document.createElement('option');
      option.value = run.id;
      option.textContent = `${run.id} (${run.kind ?? 'run'})`;
      select.append(option);
    }
    await loadSdmdAvailability();
    const params = new URLSearchParams(window.location.search);
    const requestedRun = params.get('run');
    const liveRun = requestedRun ? null : await findLiveRun(summary.runs ?? []);
    const preferred = (summary.runs ?? []).find((run) => run.id === requestedRun)
      ?? (liveRun ? (summary.runs ?? []).find((run) => run.id === liveRun) : null)
      ?? (summary.runs ?? []).find((run) => run.id === 'reference')
      ?? (summary.runs ?? []).find((run) => run.id === 'run-dated3')
      ?? (summary.runs ?? [])[0];
    if (!preferred) { statusLine('no runs found'); return; }
    select.value = preferred.id;
    state.run = preferred.id;
    await loadFireScenes({ run: preferred.id });
    const requestedPeriod = Number(params.get('period'));
    if (Number.isFinite(requestedPeriod) && requestedPeriod >= 0) {
      state.pendingPeriod = requestedPeriod;
    }
    const requestedBlock = params.get('block');
    if (requestedBlock !== null) state.pendingBlock = requestedBlock;
    await loadRunContext();
    const requestedView = params.get('view') ?? 'map';
    setWorkspace(requestedView, { sync: false, activate: false });
    const requestedSub = params.get('sub');
    if (requestedSub && SUB_PANELS[state.workspace]) {
      setSubView(state.workspace, requestedSub, { sync: false });
    }
    state.urlReady = true;
    activateSubView();
    updateUrl({ push: false });
    await attachLiveRun(state.run);
  } catch (error) {
    statusLine(`service unavailable: ${error.message}`);
  }
}

window.addEventListener('popstate', async () => {
  state.urlReady = false;
  try {
    const params = new URLSearchParams(window.location.search);
    const requestedRun = params.get('run');
    if (requestedRun && requestedRun !== state.run && $('run').querySelector(`option[value="${requestedRun}"]`)) {
      state.run = requestedRun;
      $('run').value = requestedRun;
      stopRunWatch();
      state.live.active = false;
      state.live.display = 'live';
      state.live.schedule = new Map();
      await loadRunContext();
      await attachLiveRun(state.run);
    }
    const requestedPeriod = Number(params.get('period'));
    if (Number.isFinite(requestedPeriod) && requestedPeriod >= 0) {
      setPeriod(requestedPeriod);
    }
    const requestedView = params.get('view') ?? 'map';
    const requestedAu = params.get('au');
    if (requestedAu && state.sdmd.available && requestedAu !== state.sdmd.au) {
      await loadSdmdAu(requestedAu);
    }
    setWorkspace(requestedView, { sync: false });
    const requestedSub = params.get('sub');
    if (requestedSub && SUB_PANELS[state.workspace]) {
      setSubView(state.workspace, requestedSub, { sync: false });
      activateSubView();
    }
    const requestedBlock = params.get('block');
    if (requestedBlock !== null) showDetail(requestedBlock);
    else {
      state.selectedBlock = null;
      $('detail').replaceChildren();
    }
  } finally {
    state.urlReady = true;
    updateUrl({ push: false });
  }
});

start();
