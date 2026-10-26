// WS4 browser shell: reads the service's artefacts, no build step, relative URLs so it works
// under a proxy prefix as well as at the root.

const state = { run: null, year: 0, features: [], view: { s: 1, x: 0, y: 0 }, base: null, skin: null, targets: [], pickedAccount: null, selectedAccounts: new Set(), targetCells: new Map(), watched: new Set(), targetSignature: "", windowValues: new Map(), series: new Map(), runPaused: false, live: { active: false, schedule: new Map(), total: 0 }, history: [], periods: [], periodIndex: 0, periodWidth: 1, yearChosen: false, chatSession: null, chatBusy: false, compareView: false, compare: null, compareAccounts: [], compareToken: 0, compareInitialized: false, layers: null, layerMode: 'current', patchClasses: new Set(), patchCatalog: [], compartmentAccounts: [], compartmentClasses: [], compartmentAccount: '', selectedCompartments: new Set(), baseAttributes: [], baseAttribute: '', roads: [], showRoads: false, usedRoads: [], showUsedRoads: false, blockElements: new Map(), mapEngine: (typeof window.maplibregl !== 'undefined' ? 'maplibre' : 'svg'), mapLibre: null, mapLibreReady: false, mapLoading: false, suppressViewportReload: false, mapTotals: null, mapFitted: false, lidar: null, lidarField: '', lidarRange: null, carbon: null, carbonAccount: '', workspace: 'map', subview: { results: 'reports', data: 'dataset' }, datasetSummary: null, selectedBlock: null, pendingBlock: null, pendingPeriod: null, urlReady: false, targetSeries: null, chartDirty: false };

const $ = (id) => document.getElementById(id);
const TILE_VERSION = 'v8';
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

function lidarColor(value) {
  const range = state.lidarRange;
  if (!range || !Number.isFinite(value)) return '#c9d2da';
  const span = range[1] - range[0];
  const t = span > 0 ? Math.max(0, Math.min(1, (value - range[0]) / span)) : 0.5;
  return `hsl(${Math.round(220 - 220 * t)} 72% 52%)`;
}

function lidarFieldInfo(name) {
  return (state.lidar?.fields ?? []).find((field) => field.name === name) ?? null;
}

function updateLidarRange() {
  const field = state.lidarField;
  if (!field) {
    state.lidarRange = null;
    renderLidarLegend();
    return;
  }
  const values = [];
  for (const feature of state.features) {
    const value = Number(feature.properties?.[field]);
    if (Number.isFinite(value)) values.push(value);
  }
  state.lidarRange = values.length
    ? [Math.min(...values), Math.max(...values)]
    : null;
  renderLidarLegend();
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
      fill: Number.isFinite(value) ? lidarColor(value) : '#c9d2da',
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
  if (!fill) fill = treated ? '#c0392b' : '#2f7d4f';
  if (!treated && !(state.layerMode === 'base' && state.baseAttribute)) opacity = 0.55;
  const visible = treated ? $('show-treated').checked : $('show-untreated').checked;
  return { treated, fill, opacity: visible ? opacity : 0 };
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
      for (const interactive of ['blocks-fill', 'blocks-points']) {
        map.on('click', interactive, (event) => {
          const feature = event.features?.[0];
          if (feature) showDetail(feature.properties.block_id);
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
      properties: { ...properties, _fill: style.fill, _opacity: style.opacity },
    };
  });
  const source = map.getSource('blocks');
  if (source) source.setData({ type: 'FeatureCollection', features });
  setMapLibreRoads();
  let treated = 0;
  for (const feature of state.features) {
    if (featureStyle(feature.properties ?? {}).treated) treated += 1;
  }
  const treatedTotal = state.mapTotals ? state.mapTotals.treated : treated;
  const untreatedTotal = state.mapTotals ? state.mapTotals.untreated : state.features.length - treated;
  $('n-treated').textContent = treatedTotal.toLocaleString();
  $('n-untreated').textContent = untreatedTotal.toLocaleString();
  const baseMode = state.layerMode === 'base' && Boolean(state.baseAttribute);
  $('treated-label').textContent = layerLabel();
  const skinHasTreatments = state.skin?.layers ? state.skin.layers.includes('treatments') : true;
  $('treated-label').closest('label').hidden = baseMode || !skinHasTreatments;
  $('untreated-label').textContent = baseMode ? 'Blocks' : 'Untreated';
  const period = currentPeriod();
  $('scale').textContent = `period ${state.periodIndex + 1}${period ? ` · years ${period.start}-${period.end}` : ''} · MapLibre`;
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
      fill = Number.isFinite(value) ? lidarColor(value) : '#c9d2da';
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
    return;
  }
  const showTreated = $('show-treated').checked;
  const showUntreated = $('show-untreated').checked;
  for (const element of document.querySelectorAll('#viewport .treated')) element.style.display = showTreated ? '' : 'none';
  for (const element of document.querySelectorAll('#viewport .untreated')) element.style.display = showUntreated ? '' : 'none';
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

function updateLiveBlocks(blocks) {
  if (state.mapEngine === 'maplibre') {
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
    ? ['interpolate', ['linear'], ['coalesce', ['get', 'treated_share'], 0], 0, '#2f7d4f', 1, '#2f7d4f']
    : ['interpolate', ['linear'], ['coalesce', ['get', 'treated_share'], 0],
      0, '#f4a261', 0.02, '#e76f51', 0.05, '#d62828', 0.15, '#8b0000'];
  if (state.layerMode === 'cumulative' && state.layers?.cumulative) {
    return ['case',
      ['has', 'treated_share'], grid,
      ['all', ['==', ['get', 'treated'], true], ['==', ['get', 'current'], false]], '#f0d2b0',
      ['==', ['get', 'treated'], true], '#c0392b',
      '#2f7d4f'];
  }
  return ['case', ['has', 'treated_share'], grid, ['==', ['get', 'treated'], true], '#c0392b', '#2f7d4f'];
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
    showUntreated ? 0.55 : 0];
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
        'fill-color': '#2f7d4f',
        'fill-opacity': 0.55,
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
        'circle-color': '#2f7d4f',
        'circle-opacity': 0.55,
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
        if (feature) showDetail(feature.properties.block_id, feature.properties);
      });
      map.on('mouseenter', interactive, () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', interactive, () => { map.getCanvas().style.cursor = ''; });
    }
    state.vectorUrl = url;
  }
  state.vectorActive = true;
  for (const id of ['blocks-vector-fill', 'blocks-vector-points']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'visible');
  }
  for (const id of ['blocks-fill', 'blocks-points']) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'none');
  }
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
}

async function loadMap(preserveView = false) {
  if (!state.run) return;
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
  setMapLoading(true, 'Loading map…');
  const lidarField = state.lidarField ? lidarFieldInfo(state.lidarField) : null;
  const layer = state.lidarField ? 'blocks' : mapLayerName();
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
      let stats = `api/runs/${encodeURIComponent(state.run)}/map-stats?year=${end}&layer=${layer}`;
      if (period) stats += `&period_start=${period.start}`;
      try {
        const body = await api(stats);
        state.mapTotals = {
          treated: body.total_treated ?? 0,
          untreated: body.total_untreated ?? 0,
        };
        $('n-treated').textContent = Number(state.mapTotals.treated).toLocaleString();
        $('n-untreated').textContent = Number(state.mapTotals.untreated).toLocaleString();
        statusLine(`${state.mapTotals.treated.toLocaleString()} treated blocks · ${layer} · MVT · period ${state.periodIndex + 1}${span}`);
      } catch {
        state.mapTotals = null;
        statusLine(`MVT · ${layer} · period ${state.periodIndex + 1}${span}`);
      }
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
    state.features = body.features ?? [];
    state.mapTotals = body.overview
      ? { treated: body.total_treated ?? 0, untreated: body.total_untreated ?? 0 }
      : null;
    updateLidarRange();
    render(!preserveView);
    const place = state.mapEngine === 'maplibre' ? 'in view' : '';
    const noun = body.overview_mode === 'treated' ? 'treated blocks' : 'blocks';
    const sourceLabel = lidarField ? `LiDAR: ${lidarField.label}` : layer;
    statusLine(`${state.features.length.toLocaleString()} ${noun} ${place} · ${sourceLabel} · period ${state.periodIndex + 1}${span}`);
    if (state.showUsedRoads) loadUsedRoads();
  } catch (error) {
    statusLine(`map unavailable: ${error.message}`);
  } finally {
    state.mapLoading = false;
    setMapLoading(false);
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
    account.className = 'account';
    account.textContent = a?.account ?? b?.account ?? '';
    account.title = account.textContent;
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
      return;
    }
    empty.hidden = true;
    for (const artifact of ready) {
      const option = document.createElement('option');
      option.value = artifact.id;
      option.textContent = `${artifact.id} (${artifact.kind})`;
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
      const data = body.data ?? {};
      const metrics = Array.isArray(data.metrics) ? data.metrics : [];
      const front = new Set(data.front ?? []);
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
        seeds: $('portfolio-seeds').value.trim() || '1',
        iterations: Number($('portfolio-iterations').value || 20),
        years: Number($('portfolio-years').value || 50),
        engine: $('portfolio-engine').value,
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
  const engineGroup = group('Map engine');
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
      renderLidarLegend();
      syncNavigation();
      return;
    }
    select.disabled = false;
    status.textContent = `${info.fields.length} block fields · ${Number(info.block_count ?? 0).toLocaleString()} block${Number(info.block_count ?? 0) === 1 ? '' : 's'}`;
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
    renderLidarLegend();
    syncNavigation();
  } catch (error) {
    state.lidar = null;
    state.lidarField = '';
    select.disabled = true;
    select.replaceChildren(new Option('Off', ''));
    meta.replaceChildren();
    status.textContent = `LiDAR unavailable: ${error.message}`;
    renderLidarLegend();
    syncNavigation();
  }
}

function carbonAccount() {
  return (state.carbon?.accounts ?? []).find((account) => account.account === state.carbonAccount) ?? null;
}

function drawCarbonChart() {
  const svg = $('carbon-chart');
  if (!svg) return;
  svg.replaceChildren();
  const account = carbonAccount();
  const points = account?.values ?? [];
  if (points.length < 1) return;
  const width = 320;
  const height = 140;
  const pad = 22;
  const xs = points.map((point) => Number(point.offset));
  const ys = points.map((point) => Number(point.value));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys, 0);
  const maxY = Math.max(...ys);
  const ySpan = maxY - minY || 1;
  const xSpan = maxX - minX || 1;
  const x = (value) => pad + ((value - minX) / xSpan) * (width - pad * 2);
  const y = (value) => height - pad - ((value - minY) / ySpan) * (height - pad * 2);
  const axis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  axis.setAttribute('x1', pad);
  axis.setAttribute('x2', width - pad);
  axis.setAttribute('y1', height - pad);
  axis.setAttribute('y2', height - pad);
  axis.setAttribute('stroke', '#d9e2ec');
  svg.append(axis);
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  line.setAttribute('points', points.map((point) => `${x(point.offset).toFixed(1)},${y(point.value).toFixed(1)}`).join(' '));
  line.setAttribute('fill', 'none');
  line.setAttribute('stroke', '#2f7d4f');
  line.setAttribute('stroke-width', '2');
  svg.append(line);
  for (const [label, value] of [[minX, minY], [maxX, maxY]]) {
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', label === minX ? pad : width - pad);
    text.setAttribute('y', height - 5);
    text.setAttribute('text-anchor', label === minX ? 'start' : 'end');
    text.setAttribute('font-size', '9');
    text.setAttribute('fill', '#616e7c');
    text.textContent = `${label}: ${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    svg.append(text);
  }
}

function renderCarbonComposition() {
  const box = $('carbon-composition');
  if (!box) return;
  box.replaceChildren();
  const pools = state.carbon?.pools;
  if (!pools?.composition?.length) return;
  const index = Math.max(0, (pools.timesteps?.length ?? 1) - 1);
  const max = Math.max(...pools.composition.map((group) => Number(group.values[index] ?? 0)), 1);
  for (const group of pools.composition) {
    const value = Number(group.values[index] ?? 0);
    const row = document.createElement('div');
    row.className = 'carbon-bar-row';
    const label = document.createElement('span');
    label.textContent = group.name;
    const track = document.createElement('span');
    track.className = 'carbon-bar';
    track.style.width = `${Math.max(1, (value / max) * 100)}%`;
    const amount = document.createElement('span');
    amount.textContent = value.toLocaleString(undefined, { maximumFractionDigits: 1 });
    row.append(label, track, amount);
    box.append(row);
  }
}

function renderCarbonCompare() {
  const table = $('carbon-compare');
  const empty = $('carbon-compare-empty');
  if (!table || !empty) return;
  const gcbm = state.carbon?.gcbm;
  table.replaceChildren();
  if (!gcbm || !gcbm.rows?.length) {
    table.hidden = true;
    empty.hidden = false;
    return;
  }
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
  if (!list) return;
  list.replaceChildren();
  for (const file of state.carbon?.files ?? []) {
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

async function loadCarbon() {
  const status = $('carbon-status');
  const meta = $('carbon-meta');
  const select = $('carbon-account');
  if (!status || !meta || !select) return;
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
      renderCarbonComposition();
      renderCarbonCompare();
      renderCarbonFiles();
      drawCarbonChart();
      syncNavigation();
      return;
    }
    select.disabled = false;
    const accounts = info.accounts ?? [];
    const ledger = info.ledger;
    status.textContent = `${accounts.length} carbon accounts${info.pools ? ' · pools' : ''}${info.flux ? ' · flux' : ''}${ledger ? ' · ledger' : ''}`;
    const manifest = info.manifest ?? {};
    const units = manifest.units ?? {};
    const rows = [
      ['Package', manifest.package_id],
      ['libcbm', manifest.libcbm_version],
      ['Units', units.carbon],
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
      option.textContent = account.account;
      select.append(option);
    }
    select.value = current;
    $('carbon-ledger').textContent = ledger
      ? `Ledger: ${ledger.ledger ?? 'present'} · ${ledger.years ?? '—'} years${ledger.package ? ` · ${ledger.package}` : ''}`
      : 'No carbon ledger recorded for this run.';
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
  updateUrl({ push: false });
  return period;
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
  results: ['reports', 'comparison', 'search'],
  data: ['dataset', 'lidar', 'carbon'],
};
const SUB_SECTION = {
  reports: 'tab-reports',
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
  const panels = skinPanels();
  if (workspace === 'plan') return panels.has('targets');
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
  if (workspace === 'results') return panels.has(sub);
  if (workspace !== 'data') return true;
  if (sub === 'dataset') return panels.has('dataset');
  if (sub === 'lidar') return panels.has('lidar') && Boolean(state.lidar?.available);
  if (sub === 'carbon') return panels.has('carbon') && Boolean(state.carbon?.available);
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
  $('map-wrap').hidden = state.workspace === 'plan';
  $('target-canvas').hidden = state.workspace !== 'plan';
  if (state.workspace === 'plan') renderTargetCharts();
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

function chartCell(account, period) {
  const source = state.targetSeries?.accounts?.find((item) => item.account === account);
  const cell = source?.periods?.find((item) => Number(item.index) === Number(period.index));
  return cell ?? {
    index: Number(period.index),
    start: Number(period.start),
    end: Number(period.end),
    label: period.label,
    minimum: null,
    maximum: null,
    active: false,
    target_indices: [],
  };
}


function targetChartCells(account) {
  const source = state.targetSeries?.accounts?.find((item) => item.account === account);
  const periods = source?.periods?.length ? source.periods : state.periods;
  return (periods ?? []).map((period) => {
    const value = periodAchieved(account, period);
    return { ...chartCell(account, period), achieved: value };
  });
}

function ensureChartRow(account, cell) {
  const rows = (cell.target_indices ?? [])
    .map((index) => state.targets[index])
    .filter((row) => row && row.account === account);
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

function applyChartBound(account, cell, bound, value, scope) {
  const target = value === '' || value === null || value === undefined ? null : Number(value);
  if (target !== null && !Number.isFinite(target)) return;
  const cells = scope === 'all' ? targetChartCells(account) : [cell];
  for (const item of cells) setChartBound(account, item, bound, target);
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
  meta.textContent = current && current.achieved !== null
    ? `P${Number(current.index) + 1} · ${compactNumber(current.achieved)} · ${targetStatus(current, current.achieved)}${active ? '' : ' · inactive'}`
    : active ? 'no value' : 'inactive';
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
    const rect = svg.getBoundingClientRect();
    const px = ((event.clientX - rect.left) / Math.max(rect.width, 1)) * width;
    const index = Math.floor((px - left) / step);
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
    : state.periods;
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
    const indexKey = String(item.index);
    const valueKey = `${item.year}|${item.account}`;
    const value = Number(item.value);
    if (state.watched.has(indexKey)) { state.windowValues.set(valueKey, value); painted += 1; }
    const entry = state.targetCells.get(indexKey);
    if (entry) paintTarget(entry, value);
  }
  if (painted) renderWatchPanel();
  if (targetChartAccounts().some((account) => liveSeries.has(account))) renderTargetCharts();
  if (painted && iteration !== undefined) {
    $('run-status').textContent = `live target state at iteration ${iteration} (${painted} cells)`;
  }
}


function accountKind(account) {
  return String(account).startsWith('product.') ? 'flow' : 'level';
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
    await loadPeriods();
    await loadTargets();
    return true;
  } catch (error) {
    $('targets-status').textContent = `not saved: ${error.message}`;
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
      return;
    }
    empty.hidden = true;
    table.hidden = false;
    button.hidden = false;
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
      });
      const label = document.createElement('span');
      label.textContent = row.account;
      label.title = row.account;
      const valueLine = document.createElement('div');
      valueLine.className = 'account-value';
      account.append(box, label, valueLine);
      tr.append(account);
      const year = document.createElement('td');
      year.textContent = row.period ?? row.year;
      tr.append(year);
      for (const field of ['minimum', 'maximum', 'min_weight', 'max_weight']) {
        const td = document.createElement('td');
        td.append(numberInput(row[field], field, index));
        tr.append(td);
      }
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
        row, text: valueLine, band: null, marker: null, value: values[row.index],
      });
      body.append(tr);
      const detail = document.createElement('tr');
      detail.className = 'target-detail';
      const detailCell = document.createElement('td');
      detailCell.colSpan = 8;
      const inner = document.createElement('div');
      inner.className = 'target-detail-inner';
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
      inner.append(normLabel, priorityLabel, kindLabel, notesLabel);
      detailCell.append(inner);
      detail.append(detailCell);
      body.append(detail);
    });
    for (const entry of state.targetCells.values()) paintTarget(entry, entry.value);
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
  $('start-run').textContent = 'Solve';
  $('stop-run').hidden = true;
  state.runPaused = false;
  showRun(`run ${id} · done`, false);
  $('run-status').textContent = '';
  try {
    const summary = await api('api/summary');
    if (await fillRuns(summary, id)) {
      await loadPeriods(); await loadLayers(); await loadLidar(); await loadCarbon(); await loadDataset(); await loadTargets(); await loadReports(); await loadMap();
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

async function startRun() {
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
          `run ${run.id} · ${Number(shown).toLocaleString()} iterations · best ${Number(step.objective).toFixed(2)}${stepDetail(step)}${island} · ${elapsed()}`,
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
    $('start-run').textContent = 'Solve';
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
  ['ending_inventory.csv', 'Ending inventory'],
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

function showDetail(block, supplied = null) {
  const feature = state.features.find((candidate) => String(candidate.properties?.block_id) === String(block));
  const properties = supplied ?? feature?.properties;
  if (!properties) return;
  state.selectedBlock = block;
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
      }),
    });
    let response = await request();
    if ([502, 503, 504].includes(response.status)) {
      // The first turn can hit a cold reverse-proxy/agent timeout; one delayed retry recovers it.
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      response = await request();
    }
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
  wireChatSplitter();
  $('start-run').addEventListener('click', () => {
    if (state.live.active) togglePause(); else startRun();
  });
  $('stop-run').addEventListener('click', stopRun);
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
    state.run = event.target.value;
    state.selectedBlock = null;
    $('detail').replaceChildren();
    await loadRunContext();
    updateUrl();
  });
  $('year').addEventListener('input', (event) => {
    state.yearChosen = true;
    setPeriod(Number(event.target.value));
  });
  $('year').addEventListener('change', () => {
    if (state.compareView) { loadComparison(); return; }
    if (state.live.active) render(false); else loadMap(true);
    if (state.showUsedRoads) loadUsedRoads();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const active = document.activeElement;
    const tag = active?.tagName;
    if (tag === 'TEXTAREA' || tag === 'SELECT' || active?.isContentEditable) return;
    if (tag === 'INPUT' && active.type !== 'range') return;
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
  $('compare-a').addEventListener('change', loadComparison);
  $('compare-b').addEventListener('change', loadComparison);
  $('compare-filter').addEventListener('input', renderCompareAccounts);
  $('search-select').addEventListener('change', (event) => renderSearchArtifact(event.target.value));
  $('run-portfolio').addEventListener('click', startPortfolio);
  $('run-tune').addEventListener('click', startTune);
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
  loadWatched();
  try {
    const summary = await api('api/summary');
    state.datasetSummary = summary;
    $('dataset-name').textContent = summary.dataset ?? '';
    const select = $('run');
    for (const run of summary.runs ?? []) {
      const option = document.createElement('option');
      option.value = run.id;
      option.textContent = `${run.id} (${run.kind ?? 'run'})`;
      select.append(option);
    }
    const params = new URLSearchParams(window.location.search);
    const requestedRun = params.get('run');
    const preferred = (summary.runs ?? []).find((run) => run.id === requestedRun)
      ?? (summary.runs ?? []).find((run) => run.id === 'reference')
      ?? (summary.runs ?? []).find((run) => run.id === 'run-dated3')
      ?? (summary.runs ?? [])[0];
    if (!preferred) { statusLine('no runs found'); return; }
    select.value = preferred.id;
    state.run = preferred.id;
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
      await loadRunContext();
    }
    const requestedPeriod = Number(params.get('period'));
    if (Number.isFinite(requestedPeriod) && requestedPeriod >= 0) {
      setPeriod(requestedPeriod);
    }
    const requestedView = params.get('view') ?? 'map';
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
