const state = { cache: {}, page: 1, charts: [], maps: {} };
const API_BASE = window.location.protocol === "file:" || window.location.port !== "8000"
  ? "http://127.0.0.1:8000"
  : "";
const categoryMeta = {
  Atmosphere: { icon: "cloud", text: "Pune weather", color: "#18aeca" },
  Hydrosphere: { icon: "drop", text: "India freshwater", color: "#368de2" },
  Biosphere: { icon: "leaf", text: "India forest area", color: "#4caa69" },
  Lithosphere: { icon: "mountain", text: "India agricultural land", color: "#da8f4f" },
  "Anthroposphere  Human Activity": { icon: "people", text: "India urban population", color: "#d67b51" },
  "Carbon & Climate": { icon: "share", text: "India CO2 indicators", color: "#7964d8" },
  Cryosphere: { icon: "snow", text: "Arctic September sea ice", color: "#1b9bc4" },
};
const $ = (selector) => document.querySelector(selector);
function icon(name, className = "svg-icon") {
  const paths = {
    catalogue: '<path d="M5 4h10v16H5zM8 8h4M8 12h4M8 16h3"/><path d="M8 2h8v16"/>',
    indicators: '<circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="m8 11 8-4M8 13l8 4"/>',
    categories: '<circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c3 3 3 13 0 16M12 4c-3 3-3 13 0 16"/>',
    range: '<path d="M5 5v14h14M8 15l3-4 3 2 3-6"/>',
    temperature: '<path d="M12 4a2 2 0 0 0-2 2v7.2a4 4 0 1 0 4 0V6a2 2 0 0 0-2-2Z"/><path d="M12 9v6"/>',
    carbon: '<path d="M4 18V6M4 18h16"/><path d="m7 15 3-3 3 2 5-7"/>',
    cloud: '<path d="M6 18h10a4 4 0 0 0 0-8 5 5 0 0 0-9.7 1A3.5 3.5 0 0 0 6 18Z"/>',
    drop: '<path d="M12 3S6 10 6 14a6 6 0 0 0 12 0c0-4-6-11-6-11Z"/>',
    leaf: '<path d="M19 4C9 4 5 8 5 14c0 3 2 5 5 5 6 0 9-5 9-15Z"/><path d="M5 19c3-5 6-7 11-10"/>',
    mountain: '<path d="m3 19 6-9 3 4 3-5 6 10H3Z"/><path d="m14 9 1-2 2 3"/>',
    people: '<circle cx="9" cy="9" r="3"/><circle cx="17" cy="10" r="2"/><path d="M3 19c0-3 3-5 6-5s6 2 6 5M15 15c3 0 5 1 6 4"/>',
    share: '<circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="m8 11 8-4M8 13l8 4"/>',
    snow: '<path d="M12 3v18M5 7l14 10M19 7 5 17M8 3l4 3 4-3M8 21l4-3 4 3"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  };
  return `<svg class="${className}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name] || paths.categories}</svg>`;
}
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]));

async function api(path) {
  const key = `${API_BASE}${path}`;
  if (state.cache[key]) return state.cache[key];
  const response = await fetch(key);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${response.status})`);
  }
  const data = await response.json();
  state.cache[key] = data;
  return data;
}

function clearCharts() {
  state.charts.forEach((chartInstance) => chartInstance.destroy());
  state.charts = [];
}

function chart(id, labels, datasets, options = {}) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  state.charts.push(new Chart(canvas, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: datasets.length > 1, labels: { boxWidth: 10, font: { size: 11 } } },
        tooltip: { padding: 10 },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxTicksLimit: 8 } },
        y: { grid: { color: "#e8eef0" }, ticks: { font: { size: 10 } } },
      },
      ...options,
    },
  }));
}

function lineDataset(label, records, key, color) {
  return {
    label,
    data: records.map((record) => record[key]),
    borderColor: color,
    backgroundColor: `${color}20`,
    pointRadius: 2,
    pointHoverRadius: 5,
    borderWidth: 2,
    tension: 0.25,
    spanGaps: false,
    fill: true,
  };
}

function observationRange(records, field) {
  const valid = records.filter((record) => record[field] !== null && record[field] !== undefined);
  if (!valid.length) return "No valid observations";
  return `${valid[0][field]}-${valid[valid.length - 1][field]}`;
}

function mapLayerStatus(mapId, message, kind = "") {
  const element = document.querySelector(`[data-map-status="${mapId}"]`);
  if (element) {
    element.textContent = message;
    element.className = `map-status ${kind}`;
  }
}

function createEarthMap(mapId, mapElementId) {
  const mapElement = document.getElementById(mapElementId);
  if (!mapElement || typeof L === "undefined") return;
  const map = L.map(mapElementId, { zoomControl: true }).setView([20.5937, 78.9629], 4);
  const base = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);
  const satellite = L.tileLayer(
    "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/2025-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg",
    { attribution: "NASA GIBS", maxZoom: 8, opacity: 0.78 },
  );
  let satelliteLoaded = false;
  satellite.on("tileload", () => {
    if (!satelliteLoaded) {
      satelliteLoaded = true;
      mapLayerStatus(mapId, "Satellite imagery loaded  -  NASA GIBS  -  2025-01-01", "success");
    }
  });
  satellite.on("tileerror", () => mapLayerStatus(mapId, "Satellite tiles unavailable for this view/date; base map remains available.", "error"));
  satellite.addTo(map);
  state.maps[mapId] = { map, base, satellite };
  document.querySelectorAll(`[data-map="${mapId}"] [data-lat]`).forEach((button) => {
    button.addEventListener("click", () => map.setView([Number(button.dataset.lat), Number(button.dataset.lon)], Number(button.dataset.zoom)));
  });
  const opacity = document.querySelector(`[data-map="${mapId}"] [data-opacity]`);
  if (opacity) opacity.addEventListener("input", (event) => satellite.setOpacity(event.target.value));
  const imagery = document.querySelector(`[data-map="${mapId}"] [data-layer="imagery"]`);
  const baseButton = document.querySelector(`[data-map="${mapId}"] [data-layer="base"]`);
  if (imagery) imagery.addEventListener("click", () => satellite.addTo(map));
  if (baseButton) baseButton.addEventListener("click", () => map.removeLayer(satellite));
  setTimeout(() => map.invalidateSize(), 50);
  return map;
}

function mapMarkup(mapId, mapElementId, compact = false) {
  return `<article class="glass-card map-card ${compact ? "map-card-compact" : ""}">
    <div class="map-toolbar" data-map="${mapId}">
      <div class="map-controls"><button data-lat="18.5204" data-lon="73.8567" data-zoom="8">Pune</button><button data-lat="20.5937" data-lon="78.9629" data-zoom="5">India</button><button data-lat="30.2" data-lon="79" data-zoom="6">Himalayas</button></div>
      <div class="map-controls"><button data-layer="imagery">Satellite</button><button data-layer="base">Base map</button><button class="disabled-control" disabled title="3D globe requires a separate globe renderer and imagery projection">Globe pending</button><label>Opacity <input data-opacity type="range" min=".25" max="1" step=".05" value=".78"></label></div>
    </div>
    <div id="${mapElementId}" class="map"></div>
    <div class="map-footer"><span class="map-status" data-map-status="${mapId}">Loading verified map tiles...</span><span>OpenStreetMap  -  NASA GIBS attribution</span></div>
  </article>`;
}

async function renderOverview() {
  clearCharts();
  const [categories, monthly, countryIndicators, carbon, co2Details, ice] = await Promise.all([
    api("/categories"), api("/environment/monthly"), api("/environment/country-indicators"), api("/environment/carbon"), api("/environment/carbon/co2"), api("/environment/cryosphere"),
  ]);
  const integratedIndicators = 1 + countryIndicators.total + carbon.total;
  const longestAvailableRange = observationRange(co2Details.records, "year");
  $("#view-overview").innerHTML = `
    <div class="overview-stat-row">
      <div class="overview-stat"><span class="stat-icon">${icon("catalogue")}</span><strong>${categories.total_datasets}</strong><span>catalogue entries</span></div>
      <div class="overview-stat"><span class="stat-icon teal">${icon("indicators")}</span><strong>${integratedIndicators}</strong><span>integrated indicators</span></div>
      <div class="overview-stat"><span class="stat-icon green">${icon("categories")}</span><strong>${categories.total_categories}</strong><span>connected categories</span></div>
      <div class="overview-stat"><span class="stat-icon violet">${icon("range")}</span><strong>${longestAvailableRange}</strong><span>longest valid range</span></div>
      <div class="snapshot-note"><span class="mode-dot"></span> Saved historical data<br><small>not a live feed</small></div>
    </div>
    <div class="overview-grid">
      <div class="overview-map-column">${mapMarkup("overview", "overview-map")}</div>
      <section class="analytics-column">
        <div class="panel-heading"><div><p class="eyebrow">CLIMATE ANALYTICS</p><h2>Measurements with context</h2></div><span class="panel-caption">Real returned values</span></div>
        <article class="glass-card mini-chart-card"><div class="card-title"><div><h3>Pune - temperature</h3><p>Monthly mean - degrees C - ${observationRange(monthly.records, "month")}</p></div><span class="chart-accent">${icon("temperature")}</span></div><div class="mini-chart"><canvas id="overview-temperature"></canvas></div></article>
        <article class="glass-card mini-chart-card"><div class="card-title"><div><h3>India - CO2 emissions</h3><p>Annual - million tonnes - ${observationRange(co2Details.records, "year")}</p></div><span class="chart-accent violet">${icon("carbon")}</span></div><div class="mini-chart"><canvas id="overview-carbon"></canvas></div></article>
      </section>
    </div>
    <div class="overview-lower-grid">
      <article class="glass-card lower-chart-card"><div class="card-title"><div><h3>Arctic sea ice</h3><p>September mean extent - ${observationRange(ice.records, "year")} - million km2</p></div><span class="chart-accent">${icon("snow")}</span></div><div class="lower-chart"><canvas id="overview-ice"></canvas></div><p class="caution">Not annual minimum extent, glacier area or Himalayan ice.</p></article>
      <article class="glass-card category-panel"><div class="card-title"><div><h3>Explore seven spheres</h3><p>Choose a connected data view.</p></div><span class="chart-accent green">${icon("globe")}</span></div><div class="category-buttons">${categories.categories.map((category) => { const meta = categoryMeta[category.name] || { icon: "categories", text: "Category", color: "#60758d" }; return `<button class="category-button" data-category="${esc(category.name)}"><span style="color:${meta.color}">${icon(meta.icon, "svg-icon category-icon")}</span><strong>${esc(category.name.replace("  ", "  -  "))}</strong><small>${meta.text}</small></button>`; }).join("")}</div></article>
      <article class="glass-card sdg-card"><div class="card-title"><div><p class="eyebrow">PROJECT ALIGNMENT</p><h3>SDG 13  -  Climate Action</h3></div><span class="chart-accent green">${icon("leaf")}</span></div><p>Charts, source explanations and dated Earth imagery are intended contributions to climate understanding. This is not a measured SDG achievement score.</p><button class="text-button" data-open-view="sdg">View target evidence -&gt;</button></article>
    </div>`;
  chart("overview-temperature", monthly.records.map((record) => record.month.slice(5)), [lineDataset("Temperature ? deg C", monthly.records, "T2M", "#18aeca")]);
  chart("overview-carbon", co2Details.records.map((record) => record.year), [lineDataset("CO2 million tonnes", co2Details.records, "value", "#7964d8")]);
  chart("overview-ice", ice.records.map((record) => record.year), [lineDataset("Extent million km2", ice.records, "value", "#368de2")]);
  createEarthMap("overview", "overview-map");
  document.querySelectorAll(".category-button").forEach((button) => button.addEventListener("click", () => openExplorer(button.dataset.category)));
  document.querySelectorAll("[data-open-view]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.openView)));
}

async function renderExplorer(category = "Atmosphere") {
  clearCharts();
  const [monthly, country, carbon, ice] = await Promise.all([api("/environment/monthly"), api("/environment/country-indicators"), api("/environment/carbon"), api("/environment/cryosphere")]);
  const options = Object.keys(categoryMeta).map((name) => `<option ${name === category ? "selected" : ""}>${esc(name)}</option>`).join("");
  let html = `<div class="section-heading"><div><p class="eyebrow">CATEGORY EXPLORER</p><h2>${esc(category.replace("  ", "  -  "))}</h2><p>Source geography, units and available years stay visible.</p></div><select id="category-select">${options}</select></div>`;
  if (category === "Atmosphere") {
    html += `<div class="charts-grid">${[["temperature", "Temperature", "T2M", "? deg C", "#18aeca"], ["humidity", "Relative humidity", "RH2M", "%", "#7964d8"], ["wind", "Wind speed", "WS2M", "m/s", "#4caa69"], ["precip", "Precipitation", "PRECTOTCORR", "mm/month", "#368de2"]].map((item) => `<article class="glass-card chart-card"><h3>${item[1]}</h3><p>Pune  -  monthly summary  -  ${observationRange(monthly.records, "month")}  -  ${item[3]}</p><div class="chart-wrap"><canvas id="ex-${item[0]}"></canvas></div></article>`).join("")}</div>`;
    $("#view-explorer").innerHTML = html;
    [["temperature", "T2M", "#18aeca"], ["humidity", "RH2M", "#7964d8"], ["wind", "WS2M", "#4caa69"], ["precip", "PRECTOTCORR", "#368de2"]].forEach((item) => chart(`ex-${item[0]}`, monthly.records.map((record) => record.month.slice(5)), [lineDataset(item[1], monthly.records, item[1], item[2])]));
  } else {
    let records; let title; let unit; let note;
    if (category === "Cryosphere") { records = ice.records; title = ice.name; unit = ice.unit; note = ice.interpretation; }
    else if (category === "Carbon & Climate") { const carbonSeries = await api("/environment/carbon/co2"); records = carbonSeries.records; title = carbonSeries.name; unit = carbonSeries.unit; note = "India national CO2 series; land-use-change emissions are excluded. This is not a personal carbon-footprint calculation."; }
    else { const item = country.items.find((entry) => entry.category === category) || country.items[0]; const details = await api(`/environment/country-indicators/${item.indicator_code}`); records = details.records; title = details.name; unit = details.unit; note = details.definition; }
    html += `<article class="glass-card full-card"><h3>${esc(title)}</h3><p class="chart-note">${esc(note)}  -  ${esc(unit)}  -  available observations: ${observationRange(records, records[0]?.year !== undefined ? "year" : "value")}</p><div class="chart-wrap"><canvas id="single-chart"></canvas></div></article>`;
    $("#view-explorer").innerHTML = html;
    chart("single-chart", records.map((record) => record.year), [lineDataset(unit, records, "value", category === "Cryosphere" ? "#368de2" : "#7964d8")]);
  }
  $("#category-select").onchange = (event) => renderExplorer(event.target.value);
}

async function renderAnalytics() {
  clearCharts();
  const [country] = await Promise.all([api("/environment/country-indicators"), api("/environment/carbon")]);
  $("#view-analytics").innerHTML = `<div class="section-heading"><div><p class="eyebrow">ANALYTICS</p><h2>Compare connected indicators</h2><p>Country statistics stay fixed to India; map movement never changes these values.</p></div></div><div class="charts-grid"><article class="glass-card chart-card"><h3>India  -  CO2 emissions</h3><p>Annual  -  million tonnes  -  land-use-change exclusions retained</p><div class="chart-wrap"><canvas id="co2-chart"></canvas></div></article><article class="glass-card chart-card"><h3>India  -  country context</h3><p>Annual percentages  -  each source keeps its own definition</p><div class="chart-wrap"><canvas id="context-chart"></canvas></div></article></div>`;
  const co2 = await api("/environment/carbon/co2");
  chart("co2-chart", co2.records.map((record) => record.year), [lineDataset("CO2 million tonnes", co2.records, "value", "#7964d8")]);
  const records = await Promise.all(country.items.map((item) => api(`/environment/country-indicators/${item.indicator_code}`)));
  chart("context-chart", records[0].records.map((record) => record.year), records.map((record, index) => lineDataset(record.name, record.records, "value", ["#18aeca", "#4caa69", "#da8f4f", "#d67b51"][index])), { scales: { y: { title: { display: true, text: "Percent; series retain separate definitions" } } } });
}

function renderEarthExplorer() {
  clearCharts();
  $("#view-explorer").innerHTML = `<div class="section-heading"><div><p class="eyebrow">EARTH OBSERVATION</p><h2>Earth explorer</h2><p>Satellite imagery is remote and date-limited. Snow cover, Arctic sea ice and glacier outlines are separate concepts.</p></div></div>${mapMarkup("explorer", "explorer-map")}<div class="map-notes"><span><strong>Satellite imagery</strong> NASA GIBS dated Blue Marble layer.</span><span><strong>Snow cover</strong> Not enabled until a supported layer/date is verified.</span><span><strong>Glacier outlines</strong> Pending an official Himalayan subset with verified CRS and alignment.</span></div>`;
  createEarthMap("explorer", "explorer-map");
}

async function renderCatalogue() {
  const categories = await api("/categories");
  $("#view-catalogue").innerHTML = `<div class="section-heading"><div><p class="eyebrow">DATASET LIBRARY</p><h2>105 catalogue entries</h2><p>Integrated means a verified mapping to a working endpoint, not merely a source link.</p></div></div><article class="glass-card full-card"><div class="toolbar"><input id="search" placeholder="Search datasets, indicators or organizations"><select id="filter-category"><option value="">All categories</option>${categories.categories.map((item) => `<option>${esc(item.name)}</option>`).join("")}</select><select id="filter-priority"><option value="">All priorities</option><option>High</option><option>Medium</option><option>Low</option></select><button class="link-button" id="catalogue-search">Search</button></div><div id="catalogue-table"></div></article>`;
  const load = async () => {
    const params = new URLSearchParams({ page: state.page, page_size: 10 });
    [["search", "#search"], ["category", "#filter-category"], ["priority", "#filter-priority"]].forEach(([key, selector]) => { const value = $(selector).value; if (value) params.set(key, value); });
    const data = await api(`/datasets?${params}`);
    $("#catalogue-table").innerHTML = `<div class="table-wrap"><table class="data-table"><thead><tr><th>Dataset</th><th>Category</th><th>Organization</th><th>Period</th><th>Status</th></tr></thead><tbody>${data.items.map((item) => `<tr><td><a href="${esc(item.source_url)}" target="_blank" rel="noreferrer">${esc(item.name)}</a><br><small>${esc(item.indicator)}</small></td><td>${esc(item.category)}</td><td>${esc(item.organization)}</td><td>${esc(item.time_period)}</td><td><span class="tag">${esc(item.status)}</span></td></tr>`).join("")}</tbody></table></div><div class="pager"><span>${data.total} matching entries  -  page ${data.page} of ${Math.max(data.total_pages, 1)}</span><button id="next-page" ${data.page >= data.total_pages ? "disabled" : ""}>Next ...</button></div>`;
    $("#next-page").onclick = () => { state.page += 1; state.cache = {}; load(); };
  };
  $("#catalogue-search").onclick = () => { state.page = 1; state.cache = {}; load(); };
  load();
}

function renderSdg() {
  const checklist = [["Catalogue of 105 entries", "Implemented and verified", "verified"], ["Seven-category saved data coverage", "Implemented and verified", "verified"], ["Charts and source framing", "Implemented and verified", "verified"], ["Earth map controls", "Implemented but not yet verified", "planned"], ["NASA GIBS imagery validation", "Implemented but not yet verified", "planned"], ["SDG 13 alignment evidence", "Implemented and verified", "verified"], ["AI integration", "Planned", "planned"], ["Presentation demo checks", "Implemented but not yet verified", "planned"], ["Himalayan glacier outlines", "Blocked / pending official subset", "blocked"]];
  $("#view-sdg").innerHTML = `<div class="sdg-grid"><article class="sdg-intro"><p class="eyebrow">SDG 13  -  CLIMATE ACTION</p><h2>Alignment with evidence, not overclaiming.</h2><p>Gaia Goal is a prototype for understanding environmental information. Project implementation progress is separate from real-world SDG achievement, and this view does not imply UN endorsement.</p><a class="tag" href="https://sdgs.un.org/goals/goal13" target="_blank" rel="noreferrer">Official UN Goal 13 -></a></article><article class="glass-card full-card"><h3>Prototype checklist progress</h3><p class="chart-note">Fixed list of ${checklist.length} equally weighted items. This is not SDG completion.</p><div class="status-list">${checklist.map((item) => `<div class="status-row"><span>${item[0]}</span><span class="status ${item[2]}">${item[1]}</span></div>`).join("")}</div></article></div><div class="section-heading"><div><h2>Relevant targets</h2><p>Each relationship states what is intended and what is not measured.</p></div></div><div class="target-card glass-card"><h3>13.3  -  Climate education and awareness</h3><p>Charts, source explanations and dated Earth imagery are intended contributions to understandable climate information. The app does not measure demonstrated learning outcomes.</p><a href="#" data-open="explorer">Working feature: charts</a><a href="https://sdgs.un.org/goals/goal13" target="_blank" rel="noreferrer">UN definition -></a></div><div class="target-card glass-card"><h3>13.1  -  Climate-related hazards and resilience</h3><p>Environmental observations are relevant context for understanding hazards. The app does not provide validated hazard prediction, early warning or measured resilience.</p><a href="#" data-open="explorer">Working feature: data explorer</a><a href="https://power.larc.nasa.gov/" target="_blank" rel="noreferrer">NASA POWER source -></a></div><div class="target-card glass-card"><h3>13.2  -  Mitigation and planning</h3><p>India CO2 information can support understanding of mitigation context. It does not measure policy implementation, and the OWID CO2 series excludes land-use-change emissions.</p><a href="#" data-open="analytics">Working feature: carbon analytics</a><a href="https://ourworldindata.org/co2-and-greenhouse-gas-emissions" target="_blank" rel="noreferrer">OWID source -></a></div>`;
  document.querySelectorAll("[data-open]").forEach((link) => link.onclick = (event) => { event.preventDefault(); showView(link.dataset.open); });
}

function renderSources() {
  const sources = [["NASA POWER", "Pune, India grid point  -  daily 2025 and derived monthly summaries  -  T2M, humidity, wind and corrected precipitation", "https://power.larc.nasa.gov/"], ["World Bank WDI", "India country indicators  -  annual records requested 1990...2025  -  withdrawals, forest, agricultural land and urban population", "https://data.worldbank.org/"], ["Our World in Data", "India annual CO2 and per-capita CO2  -  saved historical snapshot  -  land-use-change exclusions retained", "https://ourworldindata.org/co2-and-greenhouse-gas-emissions"], ["NSIDC Sea Ice Index v4", "Arctic polar region  -  one September monthly mean per year  -  not glacier area or annual minimum", "https://nsidc.org/data/g02135/versions/4"], ["NASA GIBS", "Remote dated satellite tiles used by the map; availability depends on selected layer/date and is not offline data", "https://www.earthdata.nasa.gov/data/tools/gibs"]];
  $("#view-sources").innerHTML = `<div class="section-heading"><div><p class="eyebrow">SOURCES & METHODOLOGY</p><h2>Know what each number means</h2><p>Saved retrieval dates and source links travel with the integrated data.</p></div></div><div class="source-list">${sources.map((source) => `<article class="glass-card source-item"><h3>${source[0]}</h3><p>${source[1]}</p><a href="${source[2]}" target="_blank" rel="noreferrer">Open official source -></a></article>`).join("")}</div><article class="glass-card full-card source-method"><h3>Method notes</h3><p class="chart-note">Missing values remain missing and incomplete months are not summarized. Observation date, retrieval date and geography are separate concepts. The frontend does not run importers or fetch source data on ordinary page loads. Atlas mode is used when configured; otherwise the app uses explicitly labelled local snapshots.</p></article>`;
}

function showView(view) {
  document.querySelectorAll(".view").forEach((element) => element.classList.remove("active-view"));
  document.querySelectorAll(".nav-item").forEach((element) => element.classList.toggle("active", element.dataset.view === view));
  const viewElement = $(`#view-${view}`);
  if (viewElement) viewElement.classList.add("active-view");
  $("#page-title").textContent = { overview: "Explore our planet. Understand its change.", explorer: "Earth observation with real source dates.", analytics: "Compare indicators without losing context.", catalogue: "Find the dataset behind the signal.", sdg: "Climate action alignment and project progress.", sources: "Sources, methods and limitations." }[view];
  if (view === "overview") renderOverview().catch(showError);
  if (view === "explorer") renderEarthExplorer();
  if (view === "analytics") renderAnalytics().catch(showError);
  if (view === "catalogue") renderCatalogue().catch(showError);
  if (view === "sdg") renderSdg();
  if (view === "sources") renderSources();
}

function openExplorer(category) {
  showView("explorer");
  renderExplorer(category).catch(showError);
}

function showError(error) {
  $("#connection-banner").textContent = `Could not load this view: ${error.message}. Start FastAPI on port 8000, then retry.`;
  $("#connection-banner").classList.remove("hidden");
}

document.querySelectorAll(".nav-item").forEach((navItem) => navItem.onclick = () => showView(navItem.dataset.view));
$("#retry-button").onclick = () => { state.cache = {}; $("#connection-banner").classList.add("hidden"); showView(document.querySelector(".nav-item.active").dataset.view); };

(async () => {
  try {
    const health = await api("/health");
    $("#mode-pill").textContent = health.mode === "saved-data" ? "Saved snapshot mode" : "Atlas connected";
    showView("overview");
  } catch (error) {
    $("#mode-pill").textContent = "Connection unavailable";
    showError(error);
  }
})();




