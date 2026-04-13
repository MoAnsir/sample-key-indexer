const state = {
  samples: [],
  filtered: [],
  stats: [],
  sortKey: "name",
  sortDirection: "asc",
  audioContext: null,
};

const els = {
  search: document.querySelector("#searchInput"),
  category: document.querySelector("#categoryFilter"),
  type: document.querySelector("#typeFilter"),
  key: document.querySelector("#keyFilter"),
  source: document.querySelector("#sourceFilter"),
  brightness: document.querySelector("#brightnessFilter"),
  warmth: document.querySelector("#warmthFilter"),
  bpmMin: document.querySelector("#bpmMinFilter"),
  bpmMax: document.querySelector("#bpmMaxFilter"),
  confidence: document.querySelector("#confidenceFilter"),
  confidenceValue: document.querySelector("#confidenceValue"),
  unsortedOnly: document.querySelector("#unsortedOnly"),
  visibleCount: document.querySelector("#visibleCount"),
  totalCount: document.querySelector("#totalCount"),
  list: document.querySelector("#sampleList"),
  chart: document.querySelector("#typeChart"),
  pieChart: document.querySelector("#pieChart"),
  pieLegend: document.querySelector("#pieLegend"),
  player: document.querySelector("#audioPlayer"),
  waveform: document.querySelector("#waveformCanvas"),
  frequency: document.querySelector("#frequencyCanvas"),
  mfcc: document.querySelector("#mfccCanvas"),
  piano: document.querySelector("#pianoView"),
  suggestions: document.querySelector("#suggestionView"),
  nowPlaying: document.querySelector("#nowPlaying"),
  nowPlayingDetails: document.querySelector("#nowPlayingDetails"),
};

const NOTE_ORDER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const BLACK_KEYS = new Set(["C#", "D#", "F#", "G#", "A#"]);

async function boot() {
  const response = await fetch("/api/samples");
  const data = await response.json();
  state.samples = data.samples;
  state.stats = data.stats;
  populateFilters();
  bindEvents();
  applyFilters();
}

function bindEvents() {
  [els.search, els.category, els.type, els.key, els.source, els.brightness, els.warmth, els.bpmMin, els.bpmMax, els.confidence, els.unsortedOnly].forEach((element) => {
    element.addEventListener("input", applyFilters);
  });
  document.querySelectorAll("[data-sort]").forEach((button) => {
    button.addEventListener("click", () => setSort(button.dataset.sort));
  });
}

function populateFilters() {
  setOptions(els.category, ["All categories", ...uniqueValues("category")]);
  setOptions(els.type, ["All types", ...uniqueValues("type")]);
  setOptions(els.key, ["All keys", ...uniqueKeys()]);
  setOptions(els.source, ["All sources", ...uniqueValues("source")]);
  setOptions(els.brightness, ["Any brightness", ...uniqueValues("brightness")]);
  setOptions(els.warmth, ["Any warmth", ...uniqueValues("warmth")]);
}

function setOptions(select, values) {
  select.innerHTML = "";
  values.forEach((value, index) => {
    const option = document.createElement("option");
    option.value = index === 0 ? "" : value;
    option.textContent = value || "Unknown";
    select.appendChild(option);
  });
}

function uniqueValues(key) {
  return [...new Set(state.samples.map((sample) => sample[key] || "Unknown"))].sort();
}

function uniqueKeys() {
  return [...new Set(state.samples.map((sample) => sample.key || sample.root_note || "Unsorted"))].sort();
}

function applyFilters() {
  const search = els.search.value.trim().toLowerCase();
  const minConfidence = Number(els.confidence.value);
  const bpmMin = Number(els.bpmMin.value || 0);
  const bpmMax = Number(els.bpmMax.value || Number.MAX_SAFE_INTEGER);
  els.confidenceValue.textContent = minConfidence.toFixed(2);

  state.filtered = state.samples.filter((sample) => {
    const keyOrRoot = sample.key || sample.root_note || "Unsorted";
    const haystack = [
      sample.file_path,
      sample.destination,
      sample.category,
      sample.type,
      sample.root_note,
      sample.key,
      sample.error,
      sample.source,
      sample.brightness,
      sample.warmth,
      sample.bpm,
      Array.isArray(sample.notes) ? sample.notes.join(" ") : "",
      Array.isArray(sample.chords) ? sample.chords.join(" ") : "",
    ].join(" ").toLowerCase();
    const bpm = Number(sample.bpm || 0);
    const bpmMatches = !sample.bpm ? !els.bpmMin.value && !els.bpmMax.value : bpm >= bpmMin && bpm <= bpmMax;

    return (!search || haystack.includes(search)) &&
      (!els.category.value || (sample.category || "Unknown") === els.category.value) &&
      (!els.type.value || (sample.type || "Unknown") === els.type.value) &&
      (!els.key.value || keyOrRoot === els.key.value) &&
      (!els.source.value || (sample.source || "Unknown") === els.source.value) &&
      (!els.brightness.value || (sample.brightness || "Unknown") === els.brightness.value) &&
      (!els.warmth.value || (sample.warmth || "Unknown") === els.warmth.value) &&
      bpmMatches &&
      (!els.unsortedOnly.checked || !sample.root_note && !sample.key) &&
      (Number(sample.confidence || 0) >= minConfidence);
  });

  sortFiltered();
  render();
}

function setSort(key) {
  if (state.sortKey === key) {
    state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
  } else {
    state.sortKey = key;
    state.sortDirection = "asc";
  }
  sortFiltered();
  render();
}

function sortFiltered() {
  const direction = state.sortDirection === "asc" ? 1 : -1;
  state.filtered.sort((a, b) => compareValues(sortValue(a, state.sortKey), sortValue(b, state.sortKey)) * direction);
}

function sortValue(sample, key) {
  if (key === "name") return fileName(sample);
  if (key === "path") return sample.playable_path || sample.file_path || "";
  if (key === "key") return sample.key || sample.root_note || "Unsorted";
  if (key === "bpm") return Number(sample.bpm || -1);
  if (key === "confidence") return Number(sample.confidence || 0);
  return sample[key] || "";
}

function compareValues(a, b) {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

function render() {
  els.visibleCount.textContent = state.filtered.length.toLocaleString();
  els.totalCount.textContent = `of ${state.samples.length.toLocaleString()} samples`;
  renderChart();
  renderPieChart();
  renderSortHeaders();
  renderList();
}

function renderSortHeaders() {
  document.querySelectorAll("[data-sort]").forEach((button) => {
    button.classList.toggle("sorted-asc", button.dataset.sort === state.sortKey && state.sortDirection === "asc");
    button.classList.toggle("sorted-desc", button.dataset.sort === state.sortKey && state.sortDirection === "desc");
  });
}

function renderChart() {
  const canvas = els.chart;
  const ctx = canvas.getContext("2d");
  const stats = statsFor(state.filtered, state.samples.length);
  const rowHeight = 22;
  canvas.height = Math.max(320, 60 + stats.length * rowHeight);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#17211f";
  ctx.font = "700 18px system-ui";
  ctx.fillText("Sample Types", 20, 28);

  if (!stats.length) {
    ctx.font = "600 16px system-ui";
    ctx.fillText("No samples match the current filters.", 20, 72);
    return;
  }

  const maxCount = Math.max(...stats.map((item) => item.count), 1);
  const left = 150;
  const top = 54;
  const barHeight = 14;
  const gap = rowHeight - barHeight;
  const width = canvas.width - left - 210;

  stats.forEach((item, index) => {
    const y = top + index * (barHeight + gap);
    const barWidth = Math.max(2, (item.count / maxCount) * width);
    ctx.fillStyle = "#60706b";
    ctx.font = "700 13px system-ui";
    ctx.textAlign = "right";
    ctx.fillText(item.type, left - 12, y + 12);
    ctx.fillStyle = colorForIndex(index);
    ctx.fillRect(left, y, barWidth, barHeight);
    ctx.fillStyle = "#17211f";
    ctx.textAlign = "left";
    ctx.fillText(`${item.count.toLocaleString()} (${item.percentage.toFixed(1)}%)`, left + barWidth + 10, y + 12);
  });
}

function renderPieChart() {
  const canvas = els.pieChart;
  const ctx = canvas.getContext("2d");
  const stats = statsFor(state.filtered, state.samples.length);
  canvas.height = 240;
  const visibleTotal = Math.max(1, state.filtered.length);
  let angle = -Math.PI / 2;
  const centerX = canvas.width / 2;
  const centerY = 104;
  const radius = 78;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#17211f";
  ctx.font = "700 16px system-ui";
  ctx.textAlign = "left";
  ctx.fillText("Type Share", 12, 22);

  if (!stats.length) {
    ctx.font = "600 14px system-ui";
    ctx.fillText("No matching samples.", 12, 62);
    els.pieLegend.innerHTML = "";
    return;
  }

  stats.forEach((item, index) => {
    const slice = (item.count / visibleTotal) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.arc(centerX, centerY, radius, angle, angle + slice);
    ctx.closePath();
    ctx.fillStyle = colorForIndex(index);
    ctx.fill();
    angle += slice;
  });

  ctx.beginPath();
  ctx.arc(centerX, centerY, 38, 0, Math.PI * 2);
  ctx.fillStyle = "#ffffff";
  ctx.fill();
  ctx.fillStyle = "#17211f";
  ctx.textAlign = "center";
  ctx.font = "800 18px system-ui";
  ctx.fillText(state.filtered.length.toLocaleString(), centerX, centerY);
  ctx.font = "700 11px system-ui";
  ctx.fillText("visible", centerX, centerY + 16);

  els.pieLegend.innerHTML = stats.map((item, index) => `
    <div class="legend-item" title="${escapeHtml(item.type)}: ${item.count.toLocaleString()} samples, ${item.percentage.toFixed(1)}% of total pool">
      <span class="legend-swatch" style="background:${colorForIndex(index)}"></span>
      <span class="legend-label">${escapeHtml(item.type)} · ${item.count.toLocaleString()} · ${item.percentage.toFixed(1)}%</span>
    </div>
  `).join("");
}

function renderList() {
  els.list.innerHTML = "";
  state.filtered.slice(0, 500).forEach((sample) => {
    const row = document.createElement("article");
    row.className = "sample-row";
    const keyOrRoot = sample.key || sample.root_note || "Unsorted";
    const confidence = Number(sample.confidence || 0);
    const playablePath = sample.playable_path || sample.file_path || "";
    row.innerHTML = `
      <button class="play-button" type="button">Play</button>
      <span class="sample-name" title="${escapeHtml(fileName(sample))}">${escapeHtml(fileName(sample))}</span>
      <span class="sample-path sample-meta" title="${escapeHtml(playablePath)}">${escapeHtml(playablePath)}</span>
      <span class="sample-cell" title="${escapeHtml(keyOrRoot)}">${escapeHtml(keyOrRoot)}</span>
      <span class="sample-cell" title="${escapeHtml(sample.category || "Unknown")}">${escapeHtml(sample.category || "Unknown")}</span>
      <span class="sample-cell" title="${escapeHtml(sample.type || "Unknown")}">${escapeHtml(sample.type || "Unknown")}</span>
      <span class="sample-cell" title="${escapeHtml(sample.source || "Unknown")}">${escapeHtml(sample.source || "-")}</span>
      <span class="sample-cell" title="${escapeHtml(sample.brightness || "Unknown")}">${escapeHtml(sample.brightness || "-")}</span>
      <span class="sample-cell" title="${escapeHtml(sample.bpm ? `${sample.bpm} BPM` : "Unknown")}">${sample.bpm ? `${escapeHtml(sample.bpm)} BPM` : "-"}</span>
      <span class="sample-cell ${confidence < 0.35 ? "low" : ""}" title="${confidence.toFixed(2)}">${confidence.toFixed(2)}</span>
    `;
    row.querySelector("button").addEventListener("click", () => playSample(sample));
    els.list.appendChild(row);
  });

  if (state.filtered.length > 500) {
    const note = document.createElement("p");
    note.className = "sample-meta";
    note.textContent = `Showing first 500 of ${state.filtered.length.toLocaleString()} matching samples. Use filters to narrow the list.`;
    els.list.appendChild(note);
  }
}

function playSample(sample) {
  els.nowPlaying.textContent = fileName(sample);
  els.nowPlaying.title = fileName(sample);
  renderNowPlayingDetails(sample);
  els.player.src = `/api/audio?id=${sample.id}`;
  els.player.play();
  drawWaveform(sample);
}

function renderNowPlayingDetails(sample) {
  const details = [
    ["Key", sample.key || sample.root_note || "Unsorted"],
    ["Notes", Array.isArray(sample.notes) && sample.notes.length ? sample.notes.join(", ") : "-"],
    ["Chords", Array.isArray(sample.chords) && sample.chords.length ? sample.chords.join(", ") : "-"],
    ["BPM", hasValue(sample.bpm) ? `${sample.bpm}` : "-"],
    ["Loudness", hasValue(sample.rms_db) ? `${sample.rms_db} dB RMS` : "-"],
    ["Peak", hasValue(sample.peak_db) ? `${sample.peak_db} dB` : "-"],
    ["Range", hasValue(sample.dynamic_range_db) ? `${sample.dynamic_range_db} dB` : "-"],
    ["Centroid", hasValue(sample.spectral_centroid) ? `${Math.round(sample.spectral_centroid)} Hz` : "-"],
    ["Fundamental", hasValue(sample.fundamental_freq) ? `${sample.fundamental_freq} Hz` : "-"],
    ["Timbre", [sample.brightness, sample.warmth, sample.roughness].filter(Boolean).join(" / ") || "-"],
    ["Source", sample.source || "-"],
    ["Confidence", hasValue(sample.confidence) ? Number(sample.confidence).toFixed(2) : "-"],
  ];

  els.nowPlayingDetails.innerHTML = details.map(([label, value]) => `
    <div class="detail-chip" title="${escapeHtml(label)}: ${escapeHtml(value)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `).join("");
  renderPiano(sample);
  renderSuggestions(sample);
  renderFrequencyChart(sample);
  renderMfccChart(sample);
}

function hasValue(value) {
  return value !== undefined && value !== null && value !== "";
}

function renderPiano(sample) {
  const root = normalizeNote(sample.root_note || noteFromKey(sample.key));
  const notes = Array.isArray(sample.notes) ? sample.notes.map(normalizeNote).filter(Boolean) : [];
  const activeNotes = new Set(notes);
  if (root) activeNotes.add(root);

  els.piano.innerHTML = NOTE_ORDER.map((note) => {
    const order = notes.indexOf(note);
    const classes = [
      "piano-key",
      BLACK_KEYS.has(note) ? "black" : "",
      activeNotes.has(note) ? "active" : "",
      note === root ? "root" : "",
    ].filter(Boolean).join(" ");
    const orderText = order >= 0 ? `<span class="note-order">${order + 1}</span>` : "";
    const title = note === root ? `${note} root / center` : activeNotes.has(note) ? `${note} detected note ${order + 1}` : note;
    return `<div class="${classes}" title="${escapeHtml(title)}">${escapeHtml(note)}${orderText}</div>`;
  }).join("");
}

function renderSuggestions(sample) {
  const root = normalizeNote(sample.root_note || noteFromKey(sample.key));
  const mode = modeFromKey(sample.key);
  if (!root) {
    els.suggestions.innerHTML = `<div class="suggestion-row">No key suggestion yet</div>`;
    return;
  }

  const suggestions = relatedKeys(root, mode);
  els.suggestions.innerHTML = suggestions.map((item) => `
    <div class="suggestion-row" title="${escapeHtml(item.label)}: ${escapeHtml(item.notes.join(", "))}">
      ${escapeHtml(item.label)} · ${escapeHtml(item.notes.join(" "))} · ${escapeHtml(item.chords.join(" / "))}
    </div>
  `).join("");
}

function renderFrequencyChart(sample) {
  const canvas = els.frequency;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const features = [
    ["Fundamental", sample.fundamental_freq, "#0f8b8d"],
    ["Centroid", sample.spectral_centroid, "#c74343"],
    ["Bandwidth", sample.spectral_bandwidth, "#5d7c2f"],
    ["Rolloff", sample.rolloff, "#d39b28"],
  ].filter((item) => hasValue(item[1]));
  const maxHz = Math.max(8000, ...features.map((item) => Number(item[1]) || 0));

  ctx.clearRect(0, 0, width, height);
  drawCanvasTitle(ctx, "Frequency Features", 14, 20);
  drawAxis(ctx, 16, 130, width - 28, "0 Hz", `${Math.round(maxHz).toLocaleString()} Hz`);

  features.forEach(([label, value, color], index) => {
    const x = 16 + (Number(value) / maxHz) * (width - 44);
    const labelColumnWidth = Math.floor((width - 36) / Math.max(1, features.length));
    const labelX = 18 + index * labelColumnWidth;
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(x, 60);
    ctx.lineTo(x, 126);
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.fillRect(labelX, 36, 8, 8);
    ctx.fillStyle = "#17211f";
    ctx.font = "700 11px system-ui";
    ctx.fillText(label, labelX + 12, 42);
    ctx.fillText(`${Math.round(Number(value)).toLocaleString()} Hz`, labelX + 12, 56);
  });

  if (!features.length) {
    ctx.fillStyle = "#60706b";
    ctx.font = "700 13px system-ui";
    ctx.fillText("No frequency features available.", 18, 64);
  }
}

function renderMfccChart(sample) {
  const canvas = els.mfcc;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const values = Array.isArray(sample.mfcc) ? sample.mfcc.map(Number).filter((value) => Number.isFinite(value)) : [];

  ctx.clearRect(0, 0, width, height);
  drawCanvasTitle(ctx, "MFCC Timbre Shape", 14, 20);
  if (!values.length) {
    ctx.fillStyle = "#60706b";
    ctx.font = "700 13px system-ui";
    ctx.fillText("No MFCC values available.", 18, 52);
    return;
  }

  const maxAbs = Math.max(1, ...values.map((value) => Math.abs(value)));
  const left = 18;
  const baseY = 72;
  const barWidth = Math.max(8, (width - 36) / values.length - 4);
  ctx.strokeStyle = "#d7dfdc";
  ctx.beginPath();
  ctx.moveTo(left, baseY);
  ctx.lineTo(width - 18, baseY);
  ctx.stroke();

  values.forEach((value, index) => {
    const x = left + index * (barWidth + 4);
    const barHeight = (Math.abs(value) / maxAbs) * 36;
    ctx.fillStyle = value >= 0 ? "#0f8b8d" : "#c74343";
    ctx.fillRect(x, value >= 0 ? baseY - barHeight : baseY, barWidth, barHeight);
    ctx.fillStyle = "#60706b";
    ctx.font = "700 9px system-ui";
    ctx.fillText(String(index + 1), x + 1, 112);
  });
}

async function drawWaveform(sample) {
  const canvas = els.waveform;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#60706b";
  ctx.font = "700 13px system-ui";
  ctx.fillText("Loading waveform...", 16, 28);

  try {
    const response = await fetch(`/api/audio?id=${sample.id}`);
    const buffer = await response.arrayBuffer();
    const audioContext = state.audioContext || new (window.AudioContext || window.webkitAudioContext)();
    state.audioContext = audioContext;
    const audioBuffer = await audioContext.decodeAudioData(buffer.slice(0));
    const channel = audioBuffer.getChannelData(0);
    renderWaveform(channel);
  } catch (error) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#c74343";
    ctx.fillText("Waveform unavailable", 16, 28);
  }
}

function renderWaveform(channel) {
  const canvas = els.waveform;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const middle = height / 2;
  const step = Math.max(1, Math.floor(channel.length / width));

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "#d7dfdc";
  ctx.beginPath();
  ctx.moveTo(0, middle);
  ctx.lineTo(width, middle);
  ctx.stroke();

  ctx.strokeStyle = "#0f8b8d";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = 0; x < width; x += 1) {
    let min = 1;
    let max = -1;
    const start = x * step;
    for (let i = 0; i < step && start + i < channel.length; i += 1) {
      const value = channel[start + i];
      if (value < min) min = value;
      if (value > max) max = value;
    }
    ctx.moveTo(x, middle + min * middle * 0.85);
    ctx.lineTo(x, middle + max * middle * 0.85);
  }
  ctx.stroke();
}

function statsFor(samples, denominator = samples.length) {
  const counts = new Map();
  samples.forEach((sample) => {
    const type = sample.type || "Unknown";
    counts.set(type, (counts.get(type) || 0) + 1);
  });
  const total = Math.max(1, denominator);
  return [...counts.entries()]
    .map(([type, count]) => ({ type, count, percentage: (count / total) * 100 }))
    .sort((a, b) => b.count - a.count || a.type.localeCompare(b.type));
}

function fileName(sample) {
  const path = sample.playable_path || sample.destination || sample.file_path || "Unknown";
  return path.split("/").pop();
}

function colorForIndex(index) {
  return ["#0f8b8d", "#c74343", "#5d7c2f", "#d39b28", "#2f7d4f", "#8a5a2b"][index % 6];
}

function normalizeNote(note) {
  if (!note) return "";
  const aliases = {
    Db: "C#",
    Eb: "D#",
    Gb: "F#",
    Ab: "G#",
    Bb: "A#",
  };
  const cleaned = String(note).trim().replace("♭", "b").replace("♯", "#");
  const normalized = cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
  return aliases[normalized] || (NOTE_ORDER.includes(normalized) ? normalized : "");
}

function noteFromKey(key) {
  return key ? String(key).split("_")[0] : "";
}

function modeFromKey(key) {
  if (!key || !String(key).includes("_")) return "";
  return String(key).split("_")[1];
}

function relatedKeys(root, mode) {
  const rootIndex = NOTE_ORDER.indexOf(root);
  const primaryMode = mode === "major" ? "major" : "minor";
  const relative = primaryMode === "minor"
    ? NOTE_ORDER[(rootIndex + 3) % 12]
    : NOTE_ORDER[(rootIndex + 9) % 12];
  const fifth = NOTE_ORDER[(rootIndex + 7) % 12];
  const fourth = NOTE_ORDER[(rootIndex + 5) % 12];
  const parallelMode = primaryMode === "minor" ? "major" : "minor";
  return [
    buildKeySuggestion(root, primaryMode, "Same key"),
    buildKeySuggestion(relative, primaryMode === "minor" ? "major" : "minor", "Relative key"),
    buildKeySuggestion(fifth, primaryMode, "Dominant move"),
    buildKeySuggestion(fourth, primaryMode, "Subdominant move"),
    buildKeySuggestion(root, parallelMode, "Parallel color"),
  ];
}

function buildKeySuggestion(root, mode, prefix) {
  const scale = scaleNotes(root, mode);
  return {
    label: `${prefix}: ${root}_${mode}`,
    notes: scale,
    chords: diatonicChords(root, mode),
  };
}

function scaleNotes(root, mode) {
  const pattern = mode === "major" ? [0, 2, 4, 5, 7, 9, 11] : [0, 2, 3, 5, 7, 8, 10];
  const start = NOTE_ORDER.indexOf(root);
  return pattern.map((step) => NOTE_ORDER[(start + step) % 12]);
}

function diatonicChords(root, mode) {
  const notes = scaleNotes(root, mode);
  if (mode === "major") {
    return [notes[0], `${notes[1]}m`, `${notes[2]}m`, notes[3], notes[4], `${notes[5]}m`];
  }
  return [`${notes[0]}m`, `${notes[2]}`, `${notes[3]}m`, `${notes[4]}m`, `${notes[5]}`];
}

function drawCanvasTitle(ctx, text, x, y) {
  ctx.fillStyle = "#17211f";
  ctx.font = "800 14px system-ui";
  ctx.textAlign = "left";
  ctx.fillText(text, x, y);
}

function drawAxis(ctx, x1, y, x2, leftLabel, rightLabel) {
  ctx.strokeStyle = "#d7dfdc";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x1, y);
  ctx.lineTo(x2, y);
  ctx.stroke();
  ctx.fillStyle = "#60706b";
  ctx.font = "700 11px system-ui";
  ctx.textAlign = "left";
  ctx.fillText(leftLabel, x1, y + 18);
  ctx.textAlign = "right";
  ctx.fillText(rightLabel, x2, y + 18);
  ctx.textAlign = "left";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

boot();
