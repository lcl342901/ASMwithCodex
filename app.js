const canvas = document.getElementById("flowCanvas");
const edgeLayer = document.getElementById("edgeLayer");
const parameterForm = document.getElementById("parameterForm");
const activeNodeLabel = document.getElementById("activeNodeLabel");
const statusBadge = document.getElementById("statusBadge");
const progressBar = document.getElementById("progressBar");
const progressPercent = document.getElementById("progressPercent");
const resultChart = document.getElementById("resultChart");
const legend = document.getElementById("legend");
const unitMetricSelect = document.getElementById("unitMetricSelect");
const chartTooltip = document.getElementById("chartTooltip");
const paramTabs = document.getElementById("paramTabs");
const dataTools = document.getElementById("dataTools");
const realtimeTools = document.getElementById("realtimeTools");
const logTools = document.getElementById("logTools");
const csvFileInput = document.getElementById("csvFileInput");
const clearCsvData = document.getElementById("clearCsvData");
const csvStatus = document.getElementById("csvStatus");
const realtimeStatus = document.getElementById("realtimeStatus");
const realtimeSummary = document.getElementById("realtimeSummary");
const mockSummary = document.getElementById("mockSummary");
const ingestRealtimeSample = document.getElementById("ingestRealtimeSample");
const stepRealtime = document.getElementById("stepRealtime");
const refreshRealtime = document.getElementById("refreshRealtime");
const resetRealtime = document.getElementById("resetRealtime");
const startMockRealtime = document.getElementById("startMockRealtime");
const stopMockRealtime = document.getElementById("stopMockRealtime");
const refreshMockRealtime = document.getElementById("refreshMockRealtime");
const warningPanel = document.getElementById("warningPanel");
const exportResultsCsv = document.getElementById("exportResultsCsv");
const exportBoundariesCsv = document.getElementById("exportBoundariesCsv");
const exportUnitsCsv = document.getElementById("exportUnitsCsv");
const exportConfigJson = document.getElementById("exportConfigJson");
const importConfigJson = document.getElementById("importConfigJson");
const metricPicker = document.getElementById("metricPicker");
const exportMenuButton = document.getElementById("exportMenuButton");
const exportMenu = document.getElementById("exportMenu");
const saveParams = document.getElementById("saveParams");
const resetParams = document.getElementById("resetParams");
const paramStorageStatus = document.getElementById("paramStorageStatus");
const refreshLogs = document.getElementById("refreshLogs");
const clearLogs = document.getElementById("clearLogs");
const logStatus = document.getElementById("logStatus");
const logList = document.getElementById("logList");
const SIMULATION_API_URL = "http://127.0.0.1:8000/api/simulate";
const REALTIME_API_URL = "http://127.0.0.1:8000/api/realtime";
const PARAM_CONFIG_API_URL = "http://127.0.0.1:8000/api/config/params";
const LOG_API_URL = "http://127.0.0.1:8000/api/logs";
const MAX_SOLVER_STEP_DAYS = 0.0005;
const EPSILON_DAYS = 1e-12;

const nodes = [
  { id: "influent", title: "进水", subtitle: "Q, COD, NH4-N", icon: "IN", type: "source", x: 30, y: 150 },
  { id: "anaerobic", title: "厌氧池", subtitle: "释磷/选择区", icon: "AN", type: "reactor", x: 210, y: 88 },
  { id: "anoxic", title: "缺氧池", subtitle: "反硝化", icon: "AX", type: "reactor", x: 390, y: 88 },
  { id: "aerobic", title: "好氧池", subtitle: "硝化/曝气", icon: "OX", type: "reactor", x: 570, y: 88 },
  { id: "clarifier", title: "二沉池", subtitle: "固液分离", icon: "SC", type: "clarifier", x: 750, y: 88 },
  { id: "effluent", title: "出水", subtitle: "水质指标", icon: "OUT", type: "sink", x: 930, y: 88 },
  { id: "ras", title: "RAS 回流", subtitle: "污泥回流", icon: "↩", type: "pump", x: 480, y: 280 },
  { id: "was", title: "WAS 排泥", subtitle: "控制 SRT", icon: "W", type: "pump", x: 760, y: 280 },
];

const edges = [
  ["influent", "anaerobic", "main"],
  ["anaerobic", "anoxic", "main"],
  ["anoxic", "aerobic", "main"],
  ["aerobic", "clarifier", "main"],
  ["clarifier", "effluent", "main"],
  ["clarifier", "ras", "recycle"],
  ["ras", "anaerobic", "recycle"],
  ["aerobic", "anoxic", "recycle"],
  ["clarifier", "was", "recycle"],
];

const params = {
  influentQ: 10000,
  influentCod: 420,
  influentNh4: 32,
  influentNo3: 0.5,
  influentTss: 220,
  solubleCodFraction: 38,
  inertSolubleFraction: 25,
  inertParticulateFraction: 25,
  influentXbh: 25,
  influentXba: 1,
  influentOrganicNFactor: 0.2,
  influentAlkalinity: 7,
  anaerobicVolume: 1200,
  anoxicVolume: 1800,
  aerobicVolume: 3500,
  clarifierArea: 1500,
  rasRatio: 0.75,
  internalRecycleRatio: 2.0,
  wasQ: 350,
  aerobicDo: 2.0,
  simulationDays: 20,
  timeStepHours: 0.5,
  outputIntervalHours: 6,
  solverMethod: "RK4",
  solverRtol: 1e-4,
  solverAtol: 1e-6,
  maxSolverStepHours: 0.05,
  muH: 6,
  muA: 0.8,
  bH: 0.62,
  bA: 0.15,
  kH: 3,
  kA: 0.08,
  kS: 20,
  kX: 0.03,
  kOH: 0.2,
  kOA: 0.4,
  kNO: 0.5,
  kNH: 1,
  yH: 0.67,
  yA: 0.24,
  etaG: 0.8,
  etaH: 0.4,
  fp: 0.08,
  temp: 15,
  clarifierHeight: 4,
  clarifierLayers: 10,
  clarifierFeedLayer: 5,
  captureEfficiency: 99.5,
  takacsRH: 0.00019,
  takacsRP: 0.00286,
  takacsV0: 474,
  takacsV0Max: 250,
  maxLayerTss: 30000,
};

const defaultParams = Object.freeze({ ...params });

const fields = {
  influent: [
    ["influentQ", "进水流量", "m3/d", 100, 100000],
    ["influentCod", "进水 COD", "g/m3", 20, 1200],
    ["influentNh4", "进水 NH4-N", "gN/m3", 0, 120],
    ["influentNo3", "进水 NO3-N", "gN/m3", 0, 50],
    ["influentTss", "进水 TSS", "g/m3", 0, 800],
    ["solubleCodFraction", "溶解性 COD 比例", "% COD", 5, 95],
    ["inertSolubleFraction", "溶解惰性比例", "% soluble COD", 0, 90],
    ["inertParticulateFraction", "颗粒惰性比例", "% particulate COD", 0, 90],
    ["influentXbh", "进水 X_BH", "gCOD/m3", 0, 300],
    ["influentXba", "进水 X_BA", "gCOD/m3", 0, 80],
    ["influentOrganicNFactor", "有机氮比例", "fraction of NH4-N", 0, 1],
    ["influentAlkalinity", "进水碱度 S_ALK", "mol/m3", 0, 30],
  ],
  process: [
    ["anaerobicVolume", "厌氧池体积", "m3", 100, 20000],
    ["anoxicVolume", "缺氧池体积", "m3", 100, 20000],
    ["aerobicVolume", "好氧池体积", "m3", 100, 40000],
    ["clarifierArea", "二沉池表面积", "m2", 100, 20000],
  ],
  operation: [
    ["rasRatio", "RAS 回流比", "Qras / Qin", 0, 3],
    ["internalRecycleRatio", "内回流比", "Qir / Qin", 0, 6],
    ["wasQ", "剩余污泥流量", "m3/d", 0, 2000],
    ["aerobicDo", "好氧池 DO 设定", "gO2/m3", 0.2, 5],
    ["simulationDays", "仿真天数", "d", 1, 80],
    ["timeStepHours", "计算步长", "h", 0.05, 6],
    ["outputIntervalHours", "结果输出间隔", "h", 0.1, 24],
  ],
  solver: [
    ["solverMethod", "解算器方法", "LSODA / RK4", null, null, ["LSODA", "RK4"]],
    ["solverRtol", "相对误差 rtol", "-", 1e-8, 1e-2],
    ["solverAtol", "绝对误差 atol", "-", 1e-10, 1e-2],
    ["maxSolverStepHours", "最大耦合步长", "h", 0.001, 24],
  ],
  asm1: [
    ["muH", "mu_H 异养菌最大生长速率", "1/d", 0.1, 20],
    ["muA", "mu_A 自养菌最大生长速率", "1/d", 0.05, 5],
    ["bH", "b_H 异养菌衰减系数", "1/d", 0.01, 3],
    ["bA", "b_A 自养菌衰减系数", "1/d", 0.01, 2],
    ["kH", "k_h 水解速率", "1/d", 0.05, 25],
    ["kA", "k_a 氨化速率", "m3/(gCOD d)", 0.001, 0.25],
    ["kS", "K_S 易降解 COD 半饱和", "gCOD/m3", 1, 200],
    ["kX", "K_X 水解半饱和", "gCOD/gCOD", 0.001, 1],
    ["kOH", "K_OH 异养菌氧半饱和", "gO2/m3", 0.01, 5],
    ["kOA", "K_OA 自养菌氧半饱和", "gO2/m3", 0.01, 5],
    ["kNO", "K_NO 硝酸盐半饱和", "gN/m3", 0.01, 5],
    ["kNH", "K_NH 氨氮半饱和", "gN/m3", 0.01, 10],
    ["yH", "Y_H 异养菌产率", "gCOD/gCOD", 0.1, 1],
    ["yA", "Y_A 自养菌产率", "gCOD/gN", 0.05, 0.6],
    ["etaG", "eta_g 缺氧生长修正", "-", 0, 1],
    ["etaH", "eta_h 缺氧水解修正", "-", 0, 1],
    ["fp", "f_P 衰减惰性产物比例", "-", 0, 0.5],
    ["temp", "温度", "degC", 5, 35],
  ],
  clarifier: [
    ["clarifierHeight", "二沉池水深", "m", 1, 8],
    ["clarifierLayers", "二沉池层数", "layers", 4, 20],
    ["clarifierFeedLayer", "进水层序号", "1 = 顶层", 1, 20],
    ["captureEfficiency", "不可沉降 TSS 修正", "% settleable", 80, 99.95],
    ["takacsRH", "Takacs r_H", "m3/g", 0.00001, 0.002],
    ["takacsRP", "Takacs r_P", "m3/g", 0.0001, 0.02],
    ["takacsV0", "Takacs v0", "m/d", 10, 1000],
    ["takacsV0Max", "Takacs v0 max", "m/d", 10, 1000],
    ["maxLayerTss", "层浓度上限", "g/m3", 5000, 60000],
  ],
};

let activePanel = "params";
let activeTab = "influent";
let selectedNode = null;
let lastResult = null;
let activeChart = "boundaries";
let selectedMetric = "COD";
let currentChartState = null;
let hoverPoint = null;
let csvRecords = [];
let csvFileName = "";
let csvText = "";
let progressTimer = null;
let progressValue = 0;
const hiddenDatasets = new Set();

const C = {
  S_I: 0,
  S_S: 1,
  S_O: 2,
  S_NO: 3,
  S_NH: 4,
  S_ND: 5,
  S_ALK: 6,
  X_I: 7,
  X_S: 8,
  X_BH: 9,
  X_BA: 10,
  X_P: 11,
  X_ND: 12,
};

const soluble = [C.S_I, C.S_S, C.S_O, C.S_NO, C.S_NH, C.S_ND, C.S_ALK];
const particulate = [C.X_I, C.X_S, C.X_BH, C.X_BA, C.X_P, C.X_ND];

const metricDefinitions = [
  ["COD", "COD", "gCOD/m3"],
  ["BOD5", "BOD5", "g/m3"],
  ["DO", "DO", "gO2/m3"],
  ["NH4", "NH4-N", "gN/m3"],
  ["NO3", "NO3-N", "gN/m3"],
  ["TN", "TN", "gN/m3"],
  ["TKN", "TKN", "gN/m3"],
  ["TSS", "TSS", "g/m3"],
  ["S_I", "S_I 惰性溶解 COD", "gCOD/m3"],
  ["S_S", "S_S 易降解 COD", "gCOD/m3"],
  ["S_O", "S_O 溶解氧", "gO2/m3"],
  ["S_NO", "S_NO 硝酸盐/亚硝酸盐氮", "gN/m3"],
  ["S_NH", "S_NH 氨氮", "gN/m3"],
  ["S_ND", "S_ND 溶解有机氮", "gN/m3"],
  ["S_ALK", "S_ALK 碱度", "mol/m3"],
  ["X_I", "X_I 惰性颗粒 COD", "gCOD/m3"],
  ["X_S", "X_S 慢速可降解 COD", "gCOD/m3"],
  ["X_BH", "X_BH 异养菌", "gCOD/m3"],
  ["X_BA", "X_BA 自养菌", "gCOD/m3"],
  ["X_P", "X_P 衰减产物", "gCOD/m3"],
  ["X_ND", "X_ND 颗粒有机氮", "gN/m3"],
];

const metricById = Object.fromEntries(metricDefinitions.map((metric) => [metric[0], metric]));

const asm1 = {
  Y_A: 0.24,
  Y_H: 0.67,
  f_P: 0.08,
  i_N_S_I: 0,
  i_X_B: 0.086,
  i_X_P: 0.06,
  K_NH: 1,
  K_NH_H: 0.05,
  K_NO: 0.5,
  K_OA: 0.4,
  K_OH: 0.2,
  K_S: 20,
  K_X: 0.03,
  b_A: 0.15,
  b_H: 0.62,
  k_a: 0.08,
  k_h: 3,
  mu_A: 0.8,
  mu_H: 6,
  n_g: 0.8,
  n_h: 0.4,
  F_TSS_COD: 0.75,
  temp: 15,
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function nodeCenter(node) {
  return { x: node.x + 66, y: node.y + 42 };
}

function drawNodes() {
  canvas.querySelectorAll(".node").forEach((item) => item.remove());
  nodes.forEach((node) => {
    const element = document.createElement("button");
    element.className = `node ${node.type}${selectedNode === node.id ? " selected" : ""}`;
    element.style.left = `${node.x}px`;
    element.style.top = `${node.y}px`;
    element.dataset.id = node.id;
    element.innerHTML = `
      <span class="icon">${node.icon}</span>
      <h3>${node.title}</h3>
      <p>${node.subtitle}</p>
    `;
    element.addEventListener("pointerdown", startDrag);
    element.addEventListener("click", () => selectNode(node.id));
    canvas.appendChild(element);
  });
  drawEdges();
}

function drawEdges() {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  edgeLayer.setAttribute("viewBox", `0 0 ${width} ${height}`);
  edgeLayer.innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
        <path d="M0,0 L0,6 L9,3 z" fill="#51635a"></path>
      </marker>
      <marker id="arrowRecycle" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
        <path d="M0,0 L0,6 L9,3 z" fill="#2767b1"></path>
      </marker>
    </defs>
  `;
  edges.forEach(([fromId, toId, kind]) => {
    const from = nodes.find((node) => node.id === fromId);
    const to = nodes.find((node) => node.id === toId);
    const a = nodeCenter(from);
    const b = nodeCenter(to);
    const curve = kind === "recycle" ? 75 : 28;
    const midX = (a.x + b.x) / 2;
    const midY = (a.y + b.y) / 2 + (a.y > b.y ? curve : -curve);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${a.x} ${a.y} Q ${midX} ${midY} ${b.x} ${b.y}`);
    path.setAttribute("class", `edge ${kind}`);
    path.setAttribute("marker-end", kind === "recycle" ? "url(#arrowRecycle)" : "url(#arrow)");
    edgeLayer.appendChild(path);
  });
}

function startDrag(event) {
  const id = event.currentTarget.dataset.id;
  const node = nodes.find((item) => item.id === id);
  const startX = event.clientX;
  const startY = event.clientY;
  const baseX = node.x;
  const baseY = node.y;
  event.currentTarget.setPointerCapture(event.pointerId);

  function move(moveEvent) {
    const rect = canvas.getBoundingClientRect();
    node.x = clamp(baseX + moveEvent.clientX - startX, 8, rect.width - 140);
    node.y = clamp(baseY + moveEvent.clientY - startY, 8, rect.height - 96);
    const element = canvas.querySelector(`[data-id="${id}"]`);
    element.style.left = `${node.x}px`;
    element.style.top = `${node.y}px`;
    drawEdges();
  }

  function stop() {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", stop);
  }

  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", stop);
}

function selectNode(id) {
  selectedNode = id;
  const node = nodes.find((item) => item.id === id);
  activeNodeLabel.textContent = node ? node.title : "全局参数";
  drawNodes();
  setActiveChart("unit");
  if (lastResult) drawChart(lastResult, activeChart);
}

function setActiveChart(chartName) {
  activeChart = chartName;
  metricPicker.hidden = chartName !== "unit";
  document.querySelectorAll(".chart-toggle").forEach((item) => {
    item.classList.toggle("active", item.dataset.chart === chartName);
  });
}

function renderMetricOptions() {
  unitMetricSelect.innerHTML = metricDefinitions
    .map(([id, label, unit]) => `<option value="${id}">${label} (${unit})</option>`)
    .join("");
  unitMetricSelect.value = selectedMetric;
}

function updateParamStorageStatus(message, isError = false) {
  paramStorageStatus.textContent = message;
  paramStorageStatus.classList.toggle("error", isError);
}

function updateLogStatus(message, isError = false) {
  logStatus.textContent = message;
  logStatus.classList.toggle("error", isError);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function applyParamValues(values) {
  Object.entries(values).forEach(([key, value]) => {
    if (key === "solverMethod" && key in params) {
      params[key] = String(value).toUpperCase() === "RK4" ? "RK4" : "LSODA";
      return;
    }
    const parsed = Number(value);
    if (key in params && Number.isFinite(parsed)) {
      params[key] = key === "clarifierLayers" || key === "clarifierFeedLayer" ? Math.round(parsed) : parsed;
    }
  });
  params.clarifierLayers = clamp(Math.round(params.clarifierLayers), 4, 20);
  params.clarifierFeedLayer = clamp(Math.round(params.clarifierFeedLayer), 1, params.clarifierLayers);
  syncAsm1Params();
}

async function paramConfigRequest(path = "", options = {}) {
  const response = await fetch(`${PARAM_CONFIG_API_URL}${path}`, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || response.statusText || "参数配置请求失败。");
  }
  return payload;
}

async function loadSavedParams() {
  try {
    const payload = await paramConfigRequest();
    applyParamValues(payload.params || defaultParams);
    updateParamStorageStatus(payload.source === "database" ? "已加载数据库参数" : "使用默认参数");
  } catch (error) {
    updateParamStorageStatus(`参数读取失败：${error.message}`, true);
  }
}

async function saveCurrentParams() {
  try {
    const payload = await paramConfigRequest("", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ params }),
    });
    applyParamValues(payload.params || params);
    renderForm();
    updateParamStorageStatus(`已保存 ${new Date().toLocaleTimeString()}`);
  } catch (error) {
    updateParamStorageStatus(`保存失败：${error.message}`, true);
  }
}

async function resetToDefaultParams() {
  try {
    const payload = await paramConfigRequest("", { method: "DELETE" });
    applyParamValues(payload.params || defaultParams);
    renderForm();
    updateParamStorageStatus("已重置为默认参数");
  } catch (error) {
    updateParamStorageStatus(`重置失败：${error.message}`, true);
  }
}

async function logRequest(path = "", options = {}) {
  const response = await fetch(`${LOG_API_URL}${path}`, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || response.statusText || "日志请求失败。");
  }
  return payload;
}

function renderLogs(logs) {
  if (!logs.length) {
    logList.innerHTML = `<div class="log-item"><div class="log-message">暂无计算日志。</div></div>`;
    return;
  }
  logList.innerHTML = logs
    .map((log) => {
      const detail = log.detail && Object.keys(log.detail).length ? JSON.stringify(log.detail, null, 2) : "";
      const duration = Number.isFinite(log.durationMs) ? ` · ${Math.round(log.durationMs)} ms` : "";
      return `
        <article class="log-item ${log.status === "failed" ? "failed" : ""}">
          <div class="log-item-header">
            <span class="log-status">${escapeHtml(log.status)}</span>
            <span class="log-event">${escapeHtml(log.event)}</span>
            <span class="log-time">#${log.id} · ${escapeHtml(log.createdAt)}${duration}</span>
          </div>
          <div class="log-message">${escapeHtml(log.message)}</div>
          ${detail ? `<pre class="log-detail">${escapeHtml(detail)}</pre>` : ""}
        </article>
      `;
    })
    .join("");
}

async function refreshCalculationLogs() {
  try {
    const payload = await logRequest("?limit=100");
    renderLogs(payload.logs || []);
    updateLogStatus(`已加载 ${payload.logs?.length || 0} 条日志。`);
  } catch (error) {
    updateLogStatus(`日志加载失败：${error.message}`, true);
  }
}

async function clearCalculationLogs() {
  try {
    const payload = await logRequest("", { method: "DELETE" });
    renderLogs([]);
    updateLogStatus(`已清空 ${payload.deleted || 0} 条日志。`);
  } catch (error) {
    updateLogStatus(`日志清空失败：${error.message}`, true);
  }
}

function renderForm() {
  const showingParams = activePanel === "params";
  dataTools.hidden = activePanel !== "data";
  realtimeTools.hidden = activePanel !== "realtime";
  logTools.hidden = activePanel !== "logs";
  paramTabs.hidden = !showingParams;
  parameterForm.hidden = !showingParams;
  parameterForm.innerHTML = "";
  if (!showingParams) return;
  if (activeTab === "clarifier") {
    params.clarifierLayers = clamp(Math.round(params.clarifierLayers), 4, 20);
    params.clarifierFeedLayer = clamp(Math.round(params.clarifierFeedLayer), 1, params.clarifierLayers);
  }
  fields[activeTab].forEach(([key, label, unit, min, max, options]) => {
    const fieldMax = key === "clarifierFeedLayer" ? params.clarifierLayers : max;
    const field = document.createElement("div");
    field.className = "field";
    field.innerHTML = `
      <label for="${key}">
        <span>${label}</span>
        <small>${unit}</small>
      </label>
      ${
        options
          ? `<select id="${key}">${options.map((option) => `<option value="${option}"${params[key] === option ? " selected" : ""}>${option}</option>`).join("")}</select>`
          : `<input id="${key}" type="number" value="${params[key]}" min="${min}" max="${fieldMax}" step="any" />`
      }
    `;
    const input = field.querySelector("input, select");
    input.addEventListener("input", () => {
      if (options) {
        params[key] = input.value;
        updateParamStorageStatus("有未保存修改");
        if (lastResult?.mode === "boundaryPreview") {
          showDefaultBoundaryPreview();
        }
        return;
      }
      const parsed = Number(input.value);
      if (Number.isFinite(parsed)) {
        params[key] = key === "clarifierLayers" || key === "clarifierFeedLayer" ? Math.round(parsed) : parsed;
        if (key === "clarifierLayers") {
          params.clarifierFeedLayer = clamp(Math.round(params.clarifierFeedLayer), 1, params.clarifierLayers);
          renderForm();
        }
        syncAsm1Params();
        updateParamStorageStatus("有未保存修改");
        if (lastResult?.mode === "boundaryPreview") {
          showDefaultBoundaryPreview();
        }
      }
    });
    parameterForm.appendChild(field);
  });
}

function safe(value, floor = 1e-9) {
  return Math.max(value, floor);
}

function zeros() {
  return Array(13).fill(0);
}

function syncAsm1Params() {
  asm1.Y_A = params.yA;
  asm1.Y_H = params.yH;
  asm1.f_P = params.fp;
  asm1.K_NH = params.kNH;
  asm1.K_NO = params.kNO;
  asm1.K_OA = params.kOA;
  asm1.K_OH = params.kOH;
  asm1.K_S = params.kS;
  asm1.K_X = params.kX;
  asm1.b_A = params.bA;
  asm1.b_H = params.bH;
  asm1.k_a = params.kA;
  asm1.k_h = params.kH;
  asm1.mu_A = params.muA;
  asm1.mu_H = params.muH;
  asm1.n_g = params.etaG;
  asm1.n_h = params.etaH;
  asm1.temp = params.temp;
}

function addScaled(base, delta, scale) {
  return base.map((value, index) => Math.max(0, value + delta[index] * scale));
}

function mixVectors(streams) {
  const totalQ = streams.reduce((sum, item) => sum + item.q, 0);
  const out = zeros();
  if (totalQ <= 0) return out;
  streams.forEach((item) => {
    item.c.forEach((value, index) => {
      out[index] += (item.q * value) / totalQ;
    });
  });
  return out;
}

function influentVector() {
  const solubleFraction = clamp(params.solubleCodFraction / 100, 0.05, 0.95);
  const xCod = Math.min(params.influentCod * (1 - solubleFraction), params.influentTss / asm1.F_TSS_COD);
  const sCod = Math.max(0, params.influentCod - xCod);
  const siFraction = clamp(params.inertSolubleFraction / 100, 0, 0.9);
  const xiFraction = clamp(params.inertParticulateFraction / 100, 0, 0.9);
  const organicN = params.influentNh4 * clamp(params.influentOrganicNFactor, 0, 1);
  const c = zeros();
  c[C.S_I] = sCod * siFraction;
  c[C.S_S] = sCod * (1 - siFraction);
  c[C.S_O] = 0.2;
  c[C.S_NO] = params.influentNo3;
  c[C.S_NH] = params.influentNh4;
  c[C.S_ND] = organicN * 0.4;
  c[C.S_ALK] = params.influentAlkalinity;
  c[C.X_I] = xCod * xiFraction;
  c[C.X_S] = xCod * (1 - xiFraction);
  c[C.X_BH] = params.influentXbh;
  c[C.X_BA] = params.influentXba;
  c[C.X_P] = 0;
  c[C.X_ND] = organicN * 0.6;
  return c;
}

function oxygenSaturation(temp) {
  return 290326 * Math.exp(-66.7354 + 87.4755 / ((temp + 273.15) / 100) + 24.4526 * Math.log((temp + 273.15) / 100));
}

function temperatureCorrected() {
  const temp = asm1.temp;
  return {
    K_X: asm1.K_X * 1.116 ** (temp - 20),
    b_A: asm1.b_A * 1.116 ** (temp - 20),
    b_H: asm1.b_H * 1.12 ** (temp - 20),
    k_a: asm1.k_a * 1.072 ** (temp - 20),
    k_h: asm1.k_h * 1.116 ** (temp - 20),
    mu_A: asm1.mu_A * 1.103 ** (temp - 20),
    mu_H: asm1.mu_H * 1.072 ** (temp - 20),
  };
}

function asm1Conversion(c, kla) {
  const p = temperatureCorrected();
  const soSat = oxygenSaturation(asm1.temp);
  const conv = zeros();
  const sto = Array.from({ length: 9 }, () => zeros());

  sto[0][C.S_ALK] = -(asm1.i_X_B / 14) - 1 / (7 * asm1.Y_A);
  sto[0][C.S_NH] = -asm1.i_X_B - 1 / asm1.Y_A;
  sto[0][C.S_NO] = 1 / asm1.Y_A;
  sto[0][C.S_O] = -(4.57 - asm1.Y_A) / asm1.Y_A;
  sto[0][C.X_BA] = 1;

  sto[1][C.S_ALK] = -asm1.i_X_B / 14;
  sto[1][C.S_NH] = -asm1.i_X_B;
  sto[1][C.S_O] = -(1 - asm1.Y_H) / asm1.Y_H;
  sto[1][C.S_S] = -1 / asm1.Y_H;
  sto[1][C.X_BH] = 1;

  sto[2][C.S_O] = 1;

  sto[3][C.S_ALK] = 1 / 14;
  sto[3][C.S_ND] = -1;
  sto[3][C.S_NH] = 1;

  sto[4][C.S_ALK] = (1 - asm1.Y_H) / (14 * 2.86 * asm1.Y_H) - asm1.i_X_B / 14;
  sto[4][C.S_NH] = -asm1.i_X_B;
  sto[4][C.S_NO] = -(1 - asm1.Y_H) / (2.86 * asm1.Y_H);
  sto[4][C.S_S] = -1 / asm1.Y_H;
  sto[4][C.X_BH] = 1;

  sto[5][C.X_BA] = -1;
  sto[5][C.X_ND] = asm1.i_X_B - asm1.f_P * asm1.i_X_P;
  sto[5][C.X_P] = asm1.f_P;
  sto[5][C.X_S] = 1 - asm1.f_P;

  sto[6][C.X_BH] = -1;
  sto[6][C.X_ND] = asm1.i_X_B - asm1.f_P * asm1.i_X_P;
  sto[6][C.X_P] = asm1.f_P;
  sto[6][C.X_S] = 1 - asm1.f_P;

  sto[7][C.S_S] = 1;
  sto[7][C.X_S] = -1;
  sto[8][C.S_ND] = 1;
  sto[8][C.X_ND] = -1;

  const xRatio = c[C.X_S] / safe(c[C.X_BH]);
  const hydrolysisSwitch =
    c[C.S_O] / (asm1.K_OH + c[C.S_O]) +
    asm1.n_h * (asm1.K_OH / (asm1.K_OH + c[C.S_O])) * (c[C.S_NO] / (asm1.K_NO + c[C.S_NO]));
  const hydrolysis = p.k_h * (xRatio / (p.K_X + xRatio)) * hydrolysisSwitch * c[C.X_BH];

  const rates = [
    p.mu_A * (c[C.S_NH] / (asm1.K_NH + c[C.S_NH])) * (c[C.S_O] / (asm1.K_OA + c[C.S_O])) * c[C.X_BA],
    p.mu_H * (c[C.S_S] / (asm1.K_S + c[C.S_S])) * (c[C.S_O] / (asm1.K_OH + c[C.S_O])) * (c[C.S_NH] / (asm1.K_NH_H + c[C.S_NH])) * c[C.X_BH],
    kla * (soSat - c[C.S_O]),
    p.k_a * c[C.S_ND] * c[C.X_BH],
    p.mu_H *
      (c[C.S_S] / (asm1.K_S + c[C.S_S])) *
      (asm1.K_OH / (asm1.K_OH + c[C.S_O])) *
      (c[C.S_NO] / (asm1.K_NO + c[C.S_NO])) *
      (c[C.S_NH] / (asm1.K_NH_H + c[C.S_NH])) *
      asm1.n_g *
      c[C.X_BH],
    p.b_A * c[C.X_BA],
    p.b_H * c[C.X_BH],
    hydrolysis,
    hydrolysis * (c[C.X_ND] / safe(c[C.X_S])),
  ];

  sto.forEach((row, processIndex) => {
    row.forEach((coefficient, componentIndex) => {
      conv[componentIndex] += coefficient * rates[processIndex];
    });
  });

  return conv;
}

function reactorDerivative(state, input, qIn, volume, kla) {
  const reaction = asm1Conversion(state, kla);
  return state.map((value, index) => (qIn / volume) * (input[index] - value) + reaction[index]);
}

function rk4Reactor(state, input, qIn, volume, kla, dt) {
  const k1 = reactorDerivative(state, input, qIn, volume, kla);
  const k2 = reactorDerivative(addScaled(state, k1, dt / 2), input, qIn, volume, kla);
  const k3 = reactorDerivative(addScaled(state, k2, dt / 2), input, qIn, volume, kla);
  const k4 = reactorDerivative(addScaled(state, k3, dt), input, qIn, volume, kla);
  return state.map((value, index) =>
    Math.max(0, value + (dt / 6) * (k1[index] + 2 * k2[index] + 2 * k3[index] + k4[index])),
  );
}

function cod(c) {
  return c[C.S_I] + c[C.S_S] + c[C.X_I] + c[C.X_S] + c[C.X_BH] + c[C.X_BA] + c[C.X_P];
}

function bod5(c) {
  return 0.65 * (c[C.S_S] + c[C.X_S] + (1 - asm1.f_P) * (c[C.X_BH] + c[C.X_BA]));
}

function tss(c) {
  return (c[C.X_BH] + c[C.X_BA] + c[C.X_I] + c[C.X_S] + c[C.X_P]) * asm1.F_TSS_COD;
}

function tkn(c) {
  return (
    c[C.S_NH] +
    c[C.S_ND] +
    c[C.X_ND] +
    asm1.i_X_B * (c[C.X_BH] + c[C.X_BA]) +
    asm1.i_X_P * (c[C.X_P] + c[C.X_I]) +
    asm1.i_N_S_I * c[C.S_I]
  );
}

function tn(c) {
  return (
    c[C.S_NO] +
    tkn(c)
  );
}

function metricsFromVector(c) {
  return {
    COD: cod(c),
    BOD5: bod5(c),
    DO: c[C.S_O],
    NH4: c[C.S_NH],
    NO3: c[C.S_NO],
    TN: tn(c),
    TKN: tkn(c),
    TSS: tss(c),
    S_I: c[C.S_I],
    S_S: c[C.S_S],
    S_O: c[C.S_O],
    S_NO: c[C.S_NO],
    S_NH: c[C.S_NH],
    S_ND: c[C.S_ND],
    S_ALK: c[C.S_ALK],
    X_I: c[C.X_I],
    X_S: c[C.X_S],
    X_BH: c[C.X_BH],
    X_BA: c[C.X_BA],
    X_P: c[C.X_P],
    X_ND: c[C.X_ND],
  };
}

function createUnitSeries() {
  const ids = ["influent", "anaerobic", "anoxic", "aerobic", "clarifier", "effluent", "ras", "was"];
  return Object.fromEntries(
    ids.map((id) => [
      id,
      Object.fromEntries(metricDefinitions.map(([metricId]) => [metricId, []])),
    ]),
  );
}

function pushUnitMetrics(unitSeries, unitId, metricValues) {
  metricDefinitions.forEach(([metricId]) => {
    unitSeries[unitId][metricId].push(metricValues[metricId] ?? 0);
  });
}

function createResultSeries() {
  return {
    time: [],
    effCod: [],
    effNh4: [],
    effNo3: [],
    effTn: [],
    effTss: [],
    anaerobicNo3: [],
    anoxicNo3: [],
    aerobicNo3: [],
    aerobicDo: [],
    aerobicMlss: [],
    rasMlss: [],
    mode: csvRecords.length ? "csv" : "manual",
    sourceName: csvFileName,
    boundaries: {
      q: [],
      cod: [],
      nh4: [],
      no3: [],
      tss: [],
      do: [],
      rasQ: [],
      irQ: [],
      wasQ: [],
    },
    units: createUnitSeries(),
    clarifier: {
      topTss: [],
      middleTss: [],
      bottomTss: [],
      effluentTss: [],
      underflowTss: [],
    },
  };
}

function boundarySnapshot(influent) {
  const q = params.influentQ;
  return {
    q,
    cod: cod(influent),
    nh4: influent[C.S_NH],
    no3: influent[C.S_NO],
    tss: tss(influent),
    do: params.aerobicDo,
    rasQ: q * params.rasRatio,
    irQ: q * params.internalRecycleRatio,
    wasQ: Math.min(params.wasQ, q * 0.8),
  };
}

function pushSnapshot(series, time, influent, anaerobic, anoxic, aerobic, split, ras, clarifierLayers) {
  series.time.push(Number(time.toFixed(4)));
  const boundaries = boundarySnapshot(influent);
  Object.entries(boundaries).forEach(([key, value]) => {
    series.boundaries[key].push(value);
  });
  series.effCod.push(cod(split.eff));
  series.effNh4.push(split.eff[C.S_NH]);
  series.effNo3.push(split.eff[C.S_NO]);
  series.effTn.push(tn(split.eff));
  series.effTss.push(tss(split.eff));
  series.anaerobicNo3.push(anaerobic[C.S_NO]);
  series.anoxicNo3.push(anoxic[C.S_NO]);
  series.aerobicNo3.push(aerobic[C.S_NO]);
  series.aerobicDo.push(aerobic[C.S_O]);
  series.aerobicMlss.push(tss(aerobic));
  series.rasMlss.push(tss(ras));

  pushUnitMetrics(series.units, "influent", metricsFromVector(influent));
  pushUnitMetrics(series.units, "anaerobic", metricsFromVector(anaerobic));
  pushUnitMetrics(series.units, "anoxic", metricsFromVector(anoxic));
  pushUnitMetrics(series.units, "aerobic", metricsFromVector(aerobic));
  pushUnitMetrics(series.units, "clarifier", metricsFromVector(split.eff));
  pushUnitMetrics(series.units, "effluent", metricsFromVector(split.eff));
  pushUnitMetrics(series.units, "ras", metricsFromVector(ras));
  pushUnitMetrics(series.units, "was", metricsFromVector(split.under));
  series.clarifier.topTss.push(clarifierLayers[0]);
  series.clarifier.middleTss.push(clarifierLayers[Math.floor(clarifierLayers.length / 2)]);
  series.clarifier.bottomTss.push(clarifierLayers[clarifierLayers.length - 1]);
  series.clarifier.effluentTss.push(tss(split.eff));
  series.clarifier.underflowTss.push(tss(split.under));
}

function clarify(c, qClarifier, rasQ, wasQ, capture) {
  const qUnder = Math.max(rasQ + wasQ, 1e-6);
  const qEff = Math.max(qClarifier - qUnder, 1e-6);
  const eff = [...c];
  const under = [...c];
  soluble.forEach((index) => {
    eff[index] = c[index];
    under[index] = c[index];
  });
  particulate.forEach((index) => {
    eff[index] = c[index] * (1 - capture);
    under[index] = Math.max(0, (qClarifier * c[index] - qEff * eff[index]) / qUnder);
  });
  return { eff, under, qEff, qUnder };
}

function settlingVelocity(x, xMin) {
  const rH = params.takacsRH;
  const rP = params.takacsRP;
  const v0 = params.takacsV0;
  const v0Max = params.takacsV0Max;
  const effectiveX = Math.max(0, x - xMin);
  return clamp(v0 * (Math.exp(-rH * effectiveX) - Math.exp(-rP * effectiveX)), 0, v0Max);
}

function takacsClarifierStep(layers, inlet, qClarifier, rasQ, wasQ, dt, capture) {
  const n = layers.length;
  const area = Math.max(params.clarifierArea, 1);
  const height = Math.max(params.clarifierHeight, 0.1);
  const hLayer = height / n;
  const vLayer = area * hLayer;
  const feedLayer = clamp(Math.round(params.clarifierFeedLayer) - 1, 0, n - 1);
  const qUnder = Math.max(rasQ + wasQ, 1e-6);
  const qEff = Math.max(qClarifier - qUnder, 1e-6);
  const xIn = Math.max(tss(inlet), 1e-6);
  const xMin = (1 - capture) * xIn;
  const d = Array(n).fill(0);

  d[feedLayer] += (qClarifier * xIn) / vLayer;

  for (let i = 0; i <= feedLayer; i += 1) {
    const flux = qEff * layers[i];
    d[i] -= flux / vLayer;
    if (i > 0) d[i - 1] += flux / vLayer;
  }

  for (let i = feedLayer; i < n; i += 1) {
    const flux = qUnder * layers[i];
    d[i] -= flux / vLayer;
    if (i < n - 1) d[i + 1] += flux / vLayer;
  }

  for (let i = 0; i < n - 1; i += 1) {
    const upperFlux = settlingVelocity(layers[i], xMin) * layers[i];
    const lowerFlux = settlingVelocity(layers[i + 1], xMin) * layers[i + 1];
    const gravityFlux = Math.min(upperFlux, lowerFlux);
    d[i] -= gravityFlux / hLayer;
    d[i + 1] += gravityFlux / hLayer;
  }

  const nextLayers = layers.map((x, index) => clamp(x + dt * d[index], 0, params.maxLayerTss));
  const effTss = Math.max(xMin, nextLayers[0]);
  const underTss = Math.max(effTss, nextLayers[n - 1]);
  const effRatio = clamp(effTss / xIn, 0, 1.2);
  const underRatio = clamp(underTss / xIn, 0, Math.max(1, params.maxLayerTss / xIn));
  const eff = [...inlet];
  const under = [...inlet];

  soluble.forEach((index) => {
    eff[index] = inlet[index];
    under[index] = inlet[index];
  });
  particulate.forEach((index) => {
    eff[index] = inlet[index] * effRatio;
    under[index] = inlet[index] * underRatio;
  });

  return { layers: nextLayers, eff, under, qEff, qUnder };
}

function initialReactorState(kind) {
  const c = zeros();
  c[C.S_I] = 30;
  c[C.S_S] = kind === "anaerobic" ? 75 : kind === "anoxic" ? 45 : 20;
  c[C.S_O] = kind === "aerobic" ? params.aerobicDo : 0.05;
  c[C.S_NO] = kind === "anaerobic" ? 0.2 : kind === "anoxic" ? 4 : 10;
  c[C.S_NH] = kind === "aerobic" ? 8 : 24;
  c[C.S_ND] = 2;
  c[C.S_ALK] = 7;
  c[C.X_I] = 120;
  c[C.X_S] = 160;
  c[C.X_BH] = 2600;
  c[C.X_BA] = 180;
  c[C.X_P] = 80;
  c[C.X_ND] = 15;
  return c;
}

function createSimulationState() {
  const layerCount = clamp(Math.round(params.clarifierLayers), 4, 20);
  params.clarifierFeedLayer = clamp(Math.round(params.clarifierFeedLayer), 1, layerCount);
  const aerobic = initialReactorState("aerobic");
  return {
    anaerobic: initialReactorState("anaerobic"),
    anoxic: initialReactorState("anoxic"),
    aerobic,
    ras: [...aerobic],
    clarifierLayers: Array(layerCount).fill(tss(aerobic)),
  };
}

function stepSimulationState(state, influent, dt) {
  const q = params.influentQ;
  const rasQ = q * params.rasRatio;
  const irQ = q * params.internalRecycleRatio;
  const wasQ = Math.min(params.wasQ, q * 0.8);
  const capture = clamp(params.captureEfficiency / 100, 0.8, 0.9995);

  const anaerobicIn = mixVectors([
    { q, c: influent },
    { q: rasQ, c: state.ras },
  ]);
  state.anaerobic = rk4Reactor(state.anaerobic, anaerobicIn, q + rasQ, params.anaerobicVolume, 0, dt);

  const anoxicIn = mixVectors([
    { q: q + rasQ, c: state.anaerobic },
    { q: irQ, c: state.aerobic },
  ]);
  state.anoxic = rk4Reactor(state.anoxic, anoxicIn, q + rasQ + irQ, params.anoxicVolume, 0, dt);

  state.aerobic = rk4Reactor(state.aerobic, state.anoxic, q + rasQ + irQ, params.aerobicVolume, 60 * params.aerobicDo, dt);

  const split = takacsClarifierStep(state.clarifierLayers, state.aerobic, q + rasQ, rasQ, wasQ, dt, capture);
  state.clarifierLayers = split.layers;
  state.ras = split.under;
  return split;
}

function previewClarifierSplit(state) {
  const q = params.influentQ;
  const rasQ = q * params.rasRatio;
  const wasQ = Math.min(params.wasQ, q * 0.8);
  const capture = clamp(params.captureEfficiency / 100, 0.8, 0.9995);
  return takacsClarifierStep(state.clarifierLayers, state.aerobic, q + rasQ, rasQ, wasQ, 0, capture);
}

function runAsm1Simulation() {
  syncAsm1Params();
  const solverDt = solverStepDays();
  const endTime = params.simulationDays;
  const outputInterval = outputIntervalDays();
  const influent = influentVector();
  const state = createSimulationState();
  const series = createResultSeries();
  let split = getCurrentClarifierSplit(state);
  pushSnapshot(series, 0, influent, state.anaerobic, state.anoxic, state.aerobic, split, state.ras, state.clarifierLayers);

  let currentTime = 0;
  let nextOutput = outputInterval;
  while (currentTime < endTime - EPSILON_DAYS) {
    const targetTime = Math.min(endTime, nextOutput);
    const dt = Math.min(solverDt, targetTime - currentTime);
    split = stepSimulationState(state, influent, dt);
    currentTime += dt;
    if (currentTime >= nextOutput - EPSILON_DAYS || currentTime >= endTime - EPSILON_DAYS) {
      pushSnapshot(series, currentTime, influent, state.anaerobic, state.anoxic, state.aerobic, split, state.ras, state.clarifierLayers);
      while (nextOutput <= currentTime + EPSILON_DAYS) {
        nextOutput += outputInterval;
      }
    }
  }

  return series;
}

function parseCsvRows(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell.trim());
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(cell.trim());
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  row.push(cell.trim());
  if (row.some((value) => value !== "")) rows.push(row);
  return rows;
}

function normalizeHeader(value) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function parseMaybeNumber(value) {
  if (value === undefined || value === null || value === "") return null;
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function getCsvNumber(row, aliases, fallback = null) {
  for (const alias of aliases) {
    const key = normalizeHeader(alias);
    if (row[key] !== undefined) {
      const parsed = parseMaybeNumber(row[key]);
      if (parsed !== null) return parsed;
    }
  }
  return fallback;
}

function parseCsvTime(value, index, firstTimestamp) {
  const numeric = parseMaybeNumber(value);
  if (numeric !== null) return numeric;
  const timestamp = Date.parse(value);
  if (Number.isFinite(timestamp)) return (timestamp - firstTimestamp) / 86400000;
  return index * requestedStepDays();
}

function normalizeCsvRecords(text) {
  const rows = parseCsvRows(text);
  if (rows.length < 2) throw new Error("CSV 至少需要表头和一行数据。");
  const headers = rows[0].map(normalizeHeader);
  const rawRows = rows.slice(1).map((values) => {
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? "";
    });
    return row;
  });
  const timeAliases = ["time", "timestamp", "datetime", "date", "day", "days", "t"];
  const firstTimeValue = timeAliases.map((alias) => rawRows[0][normalizeHeader(alias)]).find(Boolean);
  const parsedFirstTimestamp = firstTimeValue && !Number.isFinite(Number(firstTimeValue)) ? Date.parse(firstTimeValue) : 0;
  const firstTimestamp = Number.isFinite(parsedFirstTimestamp) ? parsedFirstTimestamp : 0;

  const records = rawRows.map((row, index) => {
    const timeValue = timeAliases.map((alias) => row[normalizeHeader(alias)]).find((value) => value !== undefined && value !== "");
    const values = {};
    const mapping = [
      ["influentQ", ["q", "qin", "q in", "flow", "flowrate", "influentq"]],
      ["influentCod", ["cod", "influentcod", "tcod"]],
      ["influentNh4", ["nh4", "snh", "ammonium", "ammonia", "nh4n"]],
      ["influentNo3", ["no3", "sno", "nitrate", "no3n"]],
      ["influentTss", ["tss", "influenttss", "sst"]],
      ["aerobicDo", ["do", "doset", "aerobicdo", "so", "setdo"]],
      ["rasRatio", ["rasratio", "rasr", "qrasqin"]],
      ["internalRecycleRatio", ["irratio", "internalrecycleratio", "qirqin"]],
      ["wasQ", ["wasq", "qwas", "wasflow"]],
      ["solubleCodFraction", ["solublecodfraction", "scodfraction", "scodpercent"]],
      ["temp", ["temp", "temperature"]],
    ];
    mapping.forEach(([target, aliases]) => {
      const value = getCsvNumber(row, aliases);
      if (value !== null) values[target] = value;
    });
    const rasQ = getCsvNumber(row, ["rasq", "qras", "rasflow"]);
    if (rasQ !== null && values.influentQ) values.rasRatio = rasQ / values.influentQ;
    const irQ = getCsvNumber(row, ["irq", "qir", "internalrecycleq", "internalrecycleflow"]);
    if (irQ !== null && values.influentQ) values.internalRecycleRatio = irQ / values.influentQ;
    return {
      time: parseCsvTime(timeValue, index, firstTimestamp),
      values,
    };
  });

  return records
    .filter((record) => Number.isFinite(record.time))
    .sort((a, b) => a.time - b.time);
}

function interpolateValues(previous, next, time) {
  if (!previous) return next?.values || {};
  if (!next) return previous.values;
  const span = next.time - previous.time;
  if (span <= 0) return previous.values;
  const ratio = clamp((time - previous.time) / span, 0, 1);
  const keys = new Set([...Object.keys(previous.values), ...Object.keys(next.values)]);
  const values = {};
  keys.forEach((key) => {
    const a = previous.values[key];
    const b = next.values[key];
    if (a !== undefined && b !== undefined) values[key] = a + (b - a) * ratio;
    else if (a !== undefined) values[key] = a;
    else if (b !== undefined) values[key] = b;
  });
  return values;
}

function csvValuesAt(records, time, cursor) {
  while (cursor.index < records.length - 2 && records[cursor.index + 1].time <= time) {
    cursor.index += 1;
  }
  const previous = records[cursor.index];
  const next = records[cursor.index + 1];
  if (time <= records[0].time) return records[0].values;
  if (!next) return previous.values;
  return interpolateValues(previous, next, time);
}

function runHistoricalSimulation(records) {
  if (!records.length) return runAsm1Simulation();
  const savedParams = { ...params };
  const state = createSimulationState();
  const series = createResultSeries();
  series.mode = "csv";
  series.sourceName = csvFileName;
  const solverDt = solverStepDays();
  const endTime = params.simulationDays;
  const outputInterval = outputIntervalDays();
  const cursor = { index: 0 };

  try {
    let currentTime = 0;
    Object.assign(params, csvValuesAt(records, currentTime, cursor));
    syncAsm1Params();
    let influent = influentVector();
    let split = getCurrentClarifierSplit(state);
    pushSnapshot(series, currentTime, influent, state.anaerobic, state.anoxic, state.aerobic, split, state.ras, state.clarifierLayers);

    let nextOutput = outputInterval;
    while (currentTime < endTime - EPSILON_DAYS) {
      Object.assign(params, csvValuesAt(records, currentTime, cursor));
      syncAsm1Params();
      influent = influentVector();
      const targetTime = Math.min(endTime, nextOutput);
      const dt = Math.min(solverDt, targetTime - currentTime);
      split = stepSimulationState(state, influent, dt);
      currentTime += dt;
      if (currentTime >= nextOutput - EPSILON_DAYS || currentTime >= endTime - EPSILON_DAYS) {
        pushSnapshot(series, currentTime, influent, state.anaerobic, state.anoxic, state.aerobic, split, state.ras, state.clarifierLayers);
        while (nextOutput <= currentTime + EPSILON_DAYS) {
          nextOutput += outputInterval;
        }
      }
    }
  } finally {
    Object.assign(params, savedParams);
    syncAsm1Params();
  }

  return series;
}

function updateCsvStatus(message, isError = false) {
  csvStatus.textContent = message;
  csvStatus.classList.toggle("error", isError);
}

function requestedStepDays() {
  return Math.max(0.001 / 24, params.timeStepHours / 24);
}

function solverStepDays() {
  return Math.min(requestedStepDays(), MAX_SOLVER_STEP_DAYS);
}

function outputIntervalDays() {
  return Math.max(solverStepDays(), params.outputIntervalHours / 24);
}

function createDefaultBoundaryPreview() {
  const stepDays = 5 / 60 / 24;
  const totalDays = 2;
  const points = Math.round(totalDays / stepDays) + 1;
  const time = Array.from({ length: points }, (_, index) => Number((index * stepDays).toFixed(8)));
  const base = boundarySnapshot(influentVector());
  const boundaries = Object.fromEntries(Object.keys(base).map((key) => [key, []]));

  time.forEach((day) => {
    const phase = (day / 1) * Math.PI * 2;
    const halfDayPhase = (day / 0.5) * Math.PI * 2;
    boundaries.q.push(base.q * (1 + 0.08 * Math.sin(phase)));
    boundaries.cod.push(base.cod * (1 + 0.12 * Math.sin(phase - 0.5)));
    boundaries.nh4.push(base.nh4 * (1 + 0.1 * Math.sin(phase - 0.2)));
    boundaries.no3.push(Math.max(0, base.no3 * (1 + 0.08 * Math.sin(halfDayPhase))));
    boundaries.tss.push(base.tss * (1 + 0.15 * Math.sin(phase - 0.9)));
    boundaries.do.push(Math.max(0.2, base.do + 0.2 * Math.sin(phase + 0.8)));
    boundaries.rasQ.push(base.rasQ);
    boundaries.irQ.push(base.irQ);
    boundaries.wasQ.push(base.wasQ);
  });

  return {
    time,
    mode: "boundaryPreview",
    sourceName: "default-48h-boundaries",
    boundaries,
    units: {},
    clarifier: {},
    warnings: [],
    validation: { ok: true, warningCount: 0, warnings: [] },
  };
}

function showDefaultBoundaryPreview() {
  lastResult = createDefaultBoundaryPreview();
  setActiveChart("boundaries");
  document.getElementById("metricNh4").textContent = "--";
  document.getElementById("metricTn").textContent = "--";
  document.getElementById("metricTss").textContent = "--";
  document.getElementById("resultSummary").textContent =
    "默认展示最近 48 h 边界输入预览，频率 5 分钟。点击运行后替换为真实仿真结果。";
  renderWarnings(lastResult);
  drawChart(lastResult, activeChart);
}

function setProgress(value, failed = false) {
  progressValue = clamp(value, 0, 100);
  progressBar.style.width = `${progressValue.toFixed(0)}%`;
  progressPercent.textContent = `${progressValue.toFixed(0)}%`;
  progressBar.closest(".simulation-status").classList.toggle("failed", failed);
}

function startProgress() {
  if (progressTimer) window.clearInterval(progressTimer);
  progressTimer = null;
  setProgress(0);
}

function finishProgress(failed = false) {
  if (progressTimer) {
    window.clearInterval(progressTimer);
    progressTimer = null;
  }
  setProgress(failed ? Math.max(progressValue, 100) : 100, failed);
}

async function runBackendSimulation() {
  const job = await createSimulationJob();
  const jobId = job.jobId;
  while (true) {
    await delay(500);
    const status = await getSimulationJob(jobId);
    setProgress(status.progressPercent || 0);
    if (Number.isFinite(status.currentTime) && Number.isFinite(status.totalTime)) {
      statusBadge.textContent = `${status.currentTime.toFixed(2)} / ${status.totalTime.toFixed(2)} d`;
    } else {
      statusBadge.textContent = status.status === "queued" ? "排队中" : "计算中";
    }
    if (status.status === "success") {
      setProgress(100);
      const result = await getSimulationJobResult(jobId);
      result.durationMs = status.durationMs;
      return result;
    }
    if (status.status === "failed") {
      throw new Error(status.error || status.message || "仿真任务失败。");
    }
  }
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function createSimulationJob() {
  let response;
  try {
    response = await fetch(`${SIMULATION_API_URL}/jobs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        params,
        csvText: csvText || "",
        csvFileName,
      }),
    });
  } catch (error) {
    throw new Error("无法连接 Python 后端。请先启动 FastAPI：source .venv/bin/activate && uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000");
  }

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const error = await response.json();
      message = error.detail || message;
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }

  return response.json();
}

async function getSimulationJob(jobId) {
  const response = await fetch(`${SIMULATION_API_URL}/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(`任务状态读取失败：HTTP ${response.status}`);
  }
  return response.json();
}

async function getSimulationJobResult(jobId) {
  const response = await fetch(`${SIMULATION_API_URL}/jobs/${jobId}/result`);
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const error = await response.json();
      message = error.detail || message;
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json();
}

async function realtimeRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${REALTIME_API_URL}${path}`, options);
  } catch (error) {
    throw new Error("无法连接实时后端服务。");
  }
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const error = await response.json();
      message = error.detail || message;
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json();
}

function realtimeBoundaryValues() {
  return {
    Q: params.influentQ,
    COD: params.influentCod,
    NH4: params.influentNh4,
    NO3: params.influentNo3,
    TSS: params.influentTss,
    DO: params.aerobicDo,
  };
}

function updateRealtimeStatus(message, isError = false) {
  realtimeStatus.textContent = message;
  realtimeStatus.classList.toggle("error", isError);
}

function renderRealtimeSummary(payload) {
  const latestResult = payload?.result?.result || payload?.result;
  if (!latestResult) {
    realtimeSummary.innerHTML = "";
    return;
  }
  realtimeSummary.innerHTML = `
    <div><span>时间戳</span><strong>${latestResult.timestamp || payload.result.timestamp || "--"}</strong></div>
    <div><span>输入 ID</span><strong>${latestResult.inputId ?? payload.result.inputId ?? "--"}</strong></div>
    <div><span>出水 COD</span><strong>${formatChartValue(latestResult.effCod)} g/m3</strong></div>
    <div><span>出水 NH4-N</span><strong>${formatChartValue(latestResult.effNh4)} g/m3</strong></div>
    <div><span>出水 TN</span><strong>${formatChartValue(latestResult.effTn)} g/m3</strong></div>
    <div><span>出水 TSS</span><strong>${formatChartValue(latestResult.effTss)} g/m3</strong></div>
  `;
}

function renderMockSummary(status) {
  if (!status) {
    mockSummary.innerHTML = "";
    return;
  }
  mockSummary.innerHTML = `
    <div><span>状态</span><strong>${status.running ? "运行中" : "已停止"}</strong></div>
    <div><span>间隔</span><strong>${status.intervalSeconds || 300} s</strong></div>
    <div><span>最近结果</span><strong>${status.lastResultId ?? "--"}</strong></div>
    <div><span>最近错误</span><strong>${status.lastError || "无"}</strong></div>
  `;
}

async function ingestCurrentRealtimeBoundary() {
  const payload = await realtimeRequest("/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ timestamp: new Date().toISOString(), values: realtimeBoundaryValues() }),
  });
  updateRealtimeStatus(`已推送实时边界输入 #${payload.id}。`);
  await refreshRealtimeLatest();
}

async function stepRealtimeModel() {
  const payload = await realtimeRequest("/step", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      timestamp: new Date().toISOString(),
      values: realtimeBoundaryValues(),
      params,
      stepHours: params.timeStepHours,
    }),
  });
  updateRealtimeStatus(`已完成实时推进，结果 #${payload.resultId}。`);
  renderRealtimeSummary(payload);
}

async function refreshRealtimeLatest() {
  const payload = await realtimeRequest("/latest");
  if (!payload.result) {
    updateRealtimeStatus("暂无实时计算结果。");
    renderRealtimeSummary(payload);
    return;
  }
  updateRealtimeStatus(`已刷新最新实时结果 #${payload.result.id}。`);
  renderRealtimeSummary(payload);
}

async function resetRealtimeState() {
  await realtimeRequest("/reset", { method: "POST" });
  updateRealtimeStatus("已重置实时输入、状态和结果。");
  renderRealtimeSummary(null);
}

async function startRealtimeMock() {
  const status = await realtimeRequest("/mock/start", { method: "POST" });
  updateRealtimeStatus("Mock 实时数据已启动，每 5 分钟自动推进一次。");
  renderMockSummary(status);
}

async function stopRealtimeMock() {
  const status = await realtimeRequest("/mock/stop", { method: "POST" });
  updateRealtimeStatus("Mock 实时数据已停止。");
  renderMockSummary(status);
}

async function refreshRealtimeMockStatus() {
  const status = await realtimeRequest("/mock/status");
  renderMockSummary(status);
  updateRealtimeStatus(status.running ? "Mock 正在运行。" : "Mock 未运行。");
}

function csvCell(value) {
  if (value === undefined || value === null) return "";
  const text = String(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function toCsv(rows) {
  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}

function downloadText(filename, text, mimeType) {
  const blob = new Blob([text], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function timestampForFile() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function exportResultCsv() {
  if (!lastResult) return;
  const rows = [
    ["time_d", "effCod", "effNh4", "effNo3", "effTn", "effTss", "anaerobicNo3", "anoxicNo3", "aerobicNo3", "aerobicDo", "aerobicMlss", "rasMlss"],
  ];
  lastResult.time.forEach((time, index) => {
    rows.push([
      time,
      lastResult.effCod[index],
      lastResult.effNh4[index],
      lastResult.effNo3[index],
      lastResult.effTn[index],
      lastResult.effTss[index],
      lastResult.anaerobicNo3[index],
      lastResult.anoxicNo3[index],
      lastResult.aerobicNo3[index],
      lastResult.aerobicDo[index],
      lastResult.aerobicMlss[index],
      lastResult.rasMlss[index],
    ]);
  });
  downloadText(`aao-results-${timestampForFile()}.csv`, toCsv(rows), "text/csv;charset=utf-8");
}

function exportBoundaryCsv() {
  if (!lastResult) return;
  const keys = Object.keys(lastResult.boundaries || {});
  const rows = [["time_d", ...keys]];
  lastResult.time.forEach((time, index) => {
    rows.push([time, ...keys.map((key) => lastResult.boundaries[key]?.[index] ?? "")]);
  });
  downloadText(`aao-boundaries-${timestampForFile()}.csv`, toCsv(rows), "text/csv;charset=utf-8");
}

function exportUnitCsv() {
  if (!lastResult) return;
  const unitIds = Object.keys(lastResult.units || {});
  const rows = [["time_d"]];
  unitIds.forEach((unitId) => {
    metricDefinitions.forEach(([metricId]) => rows[0].push(`${unitId}.${metricId}`));
  });
  lastResult.time.forEach((time, index) => {
    const row = [time];
    unitIds.forEach((unitId) => {
      metricDefinitions.forEach(([metricId]) => {
        row.push(lastResult.units[unitId]?.[metricId]?.[index] ?? "");
      });
    });
    rows.push(row);
  });
  downloadText(`aao-units-${timestampForFile()}.csv`, toCsv(rows), "text/csv;charset=utf-8");
}

function exportConfig() {
  const config = {
    version: 1,
    exportedAt: new Date().toISOString(),
    params,
    csvFileName,
    csvText,
  };
  downloadText(`aao-config-${timestampForFile()}.json`, JSON.stringify(config, null, 2), "application/json;charset=utf-8");
}

function applyImportedConfig(config) {
  if (!config || typeof config !== "object" || !config.params || typeof config.params !== "object") {
    throw new Error("配置文件缺少 params。");
  }
  applyParamValues(config.params);
  csvText = typeof config.csvText === "string" ? config.csvText : "";
  csvFileName = typeof config.csvFileName === "string" ? config.csvFileName : "";
  if (csvText) {
    csvRecords = normalizeCsvRecords(csvText);
    updateCsvStatus(`已导入配置与 ${csvRecords.length} 条 CSV 边界记录。`);
  } else {
    csvRecords = [];
    updateCsvStatus("已导入配置。当前使用手动参数。");
  }
  csvFileInput.value = "";
  renderForm();
  updateParamStorageStatus("配置已导入，尚未保存");
}

function renderWarnings(result) {
  const warnings = result?.warnings || result?.validation?.warnings || [];
  if (!warnings.length) {
    warningPanel.hidden = true;
    warningPanel.innerHTML = "";
    return;
  }
  warningPanel.hidden = false;
  warningPanel.innerHTML = `
    <strong>模型校验提示 (${warnings.length})</strong>
    <ul>${warnings.map((warning) => `<li>${warning}</li>`).join("")}</ul>
  `;
}

function niceMax(values) {
  const max = Math.max(...values, 1);
  const pow = 10 ** Math.floor(Math.log10(max));
  return Math.ceil(max / pow) * pow;
}

function niceYDomain(values) {
  const finiteValues = values.filter((value) => Number.isFinite(value));
  if (!finiteValues.length) return { min: 0, max: 1 };
  let min = Math.min(...finiteValues);
  let max = Math.max(...finiteValues);
  if (min === max) {
    const pad = Math.max(Math.abs(max) * 0.08, 1);
    min -= pad;
    max += pad;
  } else {
    const pad = (max - min) * 0.08;
    min -= pad;
    max += pad;
  }
  const span = max - min;
  const step = 10 ** Math.floor(Math.log10(span / 5 || 1));
  const niceStep = [1, 2, 5, 10].find((candidate) => candidate * step >= span / 5) * step;
  return {
    min: Math.floor(min / niceStep) * niceStep,
    max: Math.ceil(max / niceStep) * niceStep,
  };
}

function yToPixel(value, yMin, yMax, pad, plotH) {
  return pad.top + plotH - ((value - yMin) / Math.max(yMax - yMin, 1e-9)) * plotH;
}

function formatChartValue(value) {
  const abs = Math.abs(value);
  if (abs >= 1000) return value.toFixed(0);
  if (abs >= 100) return value.toFixed(1);
  if (abs >= 10) return value.toFixed(2);
  return value.toFixed(3);
}

function datasetKey(chartName, dataset) {
  return `${chartName}:${dataset.key || dataset.name}`;
}

function visibleDatasets(chartName, datasets) {
  return datasets.filter((dataset) => !hiddenDatasets.has(datasetKey(chartName, dataset)));
}

function toggleDataset(chartName, key) {
  if (hiddenDatasets.has(key)) hiddenDatasets.delete(key);
  else hiddenDatasets.add(key);
  hideChartTooltip();
  if (lastResult) drawChart(lastResult, chartName);
}

function drawChart(result, chartName) {
  const ctx = resultChart.getContext("2d");
  const rect = resultChart.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  resultChart.width = Math.round(rect.width * scale);
  resultChart.height = Math.round(rect.height * scale);
  ctx.setTransform(scale, 0, 0, scale, 0, 0);

  const width = rect.width;
  const height = rect.height;
  const pad = { left: 54, right: 24, top: 22, bottom: 42 };
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  const charts = {
    boundaries: [
      ["boundaries.q", "Q 进水流量 (m3/d)", "#1f7a4f"],
      ["boundaries.cod", "COD 边界 (g/m3)", "#7b5795"],
      ["boundaries.nh4", "NH4-N 边界 (g/m3)", "#b64242"],
      ["boundaries.no3", "NO3-N 边界 (g/m3)", "#2767b1"],
      ["boundaries.tss", "TSS 边界 (g/m3)", "#b56b16"],
      ["boundaries.do", "DO 设定 (g/m3)", "#24939a"],
      ["boundaries.rasQ", "RAS_Q (m3/d)", "#5d7c33"],
      ["boundaries.irQ", "IR_Q (m3/d)", "#6b63b5"],
      ["boundaries.wasQ", "WAS_Q (m3/d)", "#8b5a2b"],
    ],
    effluent: [
      ["effCod", "COD", "#1f7a4f"],
      ["effNh4", "NH4-N", "#b64242"],
      ["effTn", "TN", "#2767b1"],
      ["effTss", "TSS", "#b56b16"],
    ],
    nitrogen: [
      ["anaerobicNo3", "厌氧 NO3-N", "#7b5795"],
      ["anoxicNo3", "缺氧 NO3-N", "#2767b1"],
      ["aerobicNo3", "好氧 NO3-N", "#1f7a4f"],
      ["effNh4", "出水 NH4-N", "#b64242"],
    ],
    solids: [
      ["aerobicMlss", "好氧池 MLSS", "#1f7a4f"],
      ["rasMlss", "RAS MLSS", "#b56b16"],
      ["aerobicDo", "好氧池 DO", "#2767b1"],
    ],
  };
  const unitNodeId = selectedNode || "effluent";
  const unitNode = nodes.find((node) => node.id === unitNodeId);
  let datasets;
  if (chartName === "unit") {
    const [, metricLabel, metricUnit] = metricById[selectedMetric];
    if (unitNodeId === "clarifier" && selectedMetric === "TSS") {
      datasets = [
        { key: "clarifier.topTss", name: "二沉池顶层 TSS", color: "#2767b1", values: result.clarifier.topTss },
        { key: "clarifier.middleTss", name: "二沉池中层 TSS", color: "#1f7a4f", values: result.clarifier.middleTss },
        { key: "clarifier.bottomTss", name: "二沉池底层 TSS", color: "#b56b16", values: result.clarifier.bottomTss },
      ];
    } else if (unitNodeId === "clarifier") {
      datasets = [
        { key: `clarifier.effluent.${selectedMetric}`, name: `二沉池出水 ${metricLabel}`, color: "#2767b1", values: result.units.effluent[selectedMetric] },
        { key: `clarifier.underflow.${selectedMetric}`, name: `二沉池底流 ${metricLabel}`, color: "#b56b16", values: result.units.was[selectedMetric] },
      ];
    } else {
      datasets = [
        {
          key: `unit.${unitNodeId}.${selectedMetric}`,
          name: `${unitNode ? unitNode.title : "出水"} ${metricLabel} (${metricUnit})`,
          color: "#1f7a4f",
          values: result.units[unitNodeId]?.[selectedMetric] || result.units.effluent[selectedMetric],
        },
      ];
    }
  } else {
    datasets = charts[chartName].map(([key, name, color]) => ({
      key,
      name,
      color,
      values: key.includes(".") ? key.split(".").reduce((target, part) => target?.[part], result) || [] : result[key] || [],
    }));
  }
  const activeDatasets = visibleDatasets(chartName, datasets);

  const xMin = result.time[0];
  const xMax = result.time[result.time.length - 1] || 1;
  const yDomain = niceYDomain(activeDatasets.flatMap((dataset) => dataset.values));
  const yMin = yDomain.min;
  const yMax = yDomain.max;
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  currentChartState = {
    datasets: activeDatasets,
    height,
    pad,
    plotH,
    plotW,
    time: result.time,
    width,
    xMax,
    xMin,
    yMax,
    yMin,
  };

  ctx.strokeStyle = "#d7dfd8";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i <= 5; i += 1) {
    const y = pad.top + (plotH * i) / 5;
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
  }
  ctx.stroke();

  ctx.fillStyle = "#637168";
  ctx.font = "12px system-ui";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let i = 0; i <= 5; i += 1) {
    const value = yMax - ((yMax - yMin) * i) / 5;
    const y = pad.top + (plotH * i) / 5;
    ctx.fillText(formatChartValue(value), pad.left - 8, y);
  }

  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (let i = 0; i <= 4; i += 1) {
    const x = pad.left + (plotW * i) / 4;
    const value = xMin + ((xMax - xMin) * i) / 4;
    const label = xMax - xMin <= 3 ? `${(value * 24).toFixed(0)} h` : `${value.toFixed(0)} d`;
    ctx.fillText(label, x, height - pad.bottom + 14);
  }

  activeDatasets.forEach((dataset) => {
    ctx.strokeStyle = dataset.color;
    ctx.lineWidth = 2.6;
    ctx.beginPath();
    let started = false;
    dataset.values.forEach((value, index) => {
      if (!Number.isFinite(value)) return;
      const x = pad.left + ((result.time[index] - xMin) / Math.max(xMax - xMin, 0.001)) * plotW;
      const y = yToPixel(value, yMin, yMax, pad, plotH);
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      }
      else ctx.lineTo(x, y);
    });
    if (started) ctx.stroke();
  });

  if (hoverPoint) {
    drawHoverOverlay(ctx, hoverPoint.index);
  }

  legend.innerHTML = datasets
    .map(
      (dataset) => {
        const key = datasetKey(chartName, dataset);
        const hidden = hiddenDatasets.has(key);
        return `
        <button class="legend-item${hidden ? " muted" : ""}" type="button" data-dataset-key="${key}">
          <span class="legend-swatch" style="background:${dataset.color}"></span>
          ${dataset.name}
        </button>
      `;
      },
    )
    .join("");
  legend.querySelectorAll("[data-dataset-key]").forEach((item) => {
    item.addEventListener("click", () => toggleDataset(chartName, item.dataset.datasetKey));
  });
}

function drawHoverOverlay(ctx, index) {
  if (!currentChartState) return;
  const { datasets, height, pad, plotH, plotW, time, xMax, xMin, yMax, yMin } = currentChartState;
  if (time[index] === undefined) return;
  const x = pad.left + ((time[index] - xMin) / Math.max(xMax - xMin, 0.001)) * plotW;

  ctx.save();
  ctx.strokeStyle = "rgba(23, 33, 27, 0.34)";
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(x, pad.top);
  ctx.lineTo(x, height - pad.bottom);
  ctx.stroke();
  ctx.setLineDash([]);

  datasets.forEach((dataset) => {
    const value = dataset.values[index];
    if (!Number.isFinite(value)) return;
    const y = yToPixel(value, yMin, yMax, pad, plotH);
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = dataset.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  });
  ctx.restore();
}

function updateChartTooltip(event) {
  if (!currentChartState || !lastResult) return;
  const rect = resultChart.getBoundingClientRect();
  const localX = event.clientX - rect.left;
  const { datasets, pad, plotW, time, xMax, xMin } = currentChartState;
  if (localX < pad.left || localX > pad.left + plotW) {
    hideChartTooltip();
    return;
  }
  const ratio = (localX - pad.left) / plotW;
  const xValue = xMin + ratio * (xMax - xMin);
  let index = 0;
  let bestDistance = Infinity;
  time.forEach((value, idx) => {
    const distance = Math.abs(value - xValue);
    if (distance < bestDistance) {
      bestDistance = distance;
      index = idx;
    }
  });
  hoverPoint = { index };
  drawChart(lastResult, activeChart);

  const rows = datasets
    .filter((dataset) => Number.isFinite(dataset.values[index]))
    .map((dataset) => {
      const value = dataset.values[index];
      return `
        <div class="tooltip-row">
          <span class="tooltip-dot" style="background:${dataset.color}"></span>
          <span>${dataset.name}</span>
          <span class="tooltip-value">${formatChartValue(value)}</span>
        </div>
      `;
    })
    .join("");
  const timeLabel = xMax - xMin <= 3 ? `${(time[index] * 24).toFixed(2)} h` : `${time[index].toFixed(2)} d`;
  chartTooltip.innerHTML = `<strong>${timeLabel}</strong>${rows}`;
  chartTooltip.hidden = false;

  const tooltipRect = chartTooltip.getBoundingClientRect();
  const chartWidth = rect.width;
  const left = localX + tooltipRect.width + 18 > chartWidth ? localX - tooltipRect.width - 14 : localX + 14;
  const top = Math.max(10, Math.min(event.clientY - rect.top - 18, rect.height - tooltipRect.height - 10));
  chartTooltip.style.left = `${left}px`;
  chartTooltip.style.top = `${top}px`;
}

function hideChartTooltip() {
  if (!hoverPoint && chartTooltip.hidden) return;
  hoverPoint = null;
  chartTooltip.hidden = true;
  if (lastResult) drawChart(lastResult, activeChart);
}

function updateMetrics(result) {
  const last = result.time.length - 1;
  document.getElementById("metricNh4").textContent = `${result.effNh4[last].toFixed(1)} g/m3`;
  document.getElementById("metricTn").textContent = `${result.effTn[last].toFixed(1)} g/m3`;
  document.getElementById("metricTss").textContent = `${result.effTss[last].toFixed(1)} g/m3`;
  const sourceText = result.mode === "csv" ? `历史数据 ${result.sourceName}` : "手动参数";
  const warningText = result.warnings?.length ? `，含 ${result.warnings.length} 条校验提示` : "";
  const solverText = result.solverMethod ? `，解算器 ${result.solverMethod}` : "";
  const durationText = Number.isFinite(result.durationMs) ? `，耗时 ${(result.durationMs / 1000).toFixed(2)} s` : "";
  document.getElementById("resultSummary").textContent =
    `已完成 ${sourceText} 仿真${solverText}${durationText}${warningText}。可点击任一单体并在下拉框选择 WEST 风格指标查看过程浓度。`;
  renderWarnings(result);
}

document.querySelectorAll(".panel-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".panel-tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    activePanel = tab.dataset.panel;
    renderForm();
    if (activePanel === "logs") {
      refreshCalculationLogs();
    }
  });
});

document.querySelectorAll(".param-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".param-tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    activeTab = tab.dataset.tab;
    renderForm();
  });
});

document.querySelectorAll(".chart-toggle").forEach((toggle) => {
  toggle.addEventListener("click", () => {
    hideChartTooltip();
    setActiveChart(toggle.dataset.chart);
    if (lastResult) drawChart(lastResult, activeChart);
  });
});

unitMetricSelect.addEventListener("change", () => {
  hideChartTooltip();
  selectedMetric = unitMetricSelect.value;
  setActiveChart("unit");
  if (lastResult) drawChart(lastResult, activeChart);
});

exportResultsCsv.addEventListener("click", exportResultCsv);
exportBoundariesCsv.addEventListener("click", exportBoundaryCsv);
exportUnitsCsv.addEventListener("click", exportUnitCsv);
exportConfigJson.addEventListener("click", exportConfig);

saveParams.addEventListener("click", async () => {
  await saveCurrentParams();
});
resetParams.addEventListener("click", async () => {
  await resetToDefaultParams();
});
refreshLogs.addEventListener("click", async () => {
  await refreshCalculationLogs();
});
clearLogs.addEventListener("click", async () => {
  await clearCalculationLogs();
});

function setExportMenu(open) {
  exportMenu.hidden = !open;
  exportMenuButton.setAttribute("aria-expanded", String(open));
}

exportMenuButton.addEventListener("click", (event) => {
  event.stopPropagation();
  setExportMenu(exportMenu.hidden);
});

[exportResultsCsv, exportBoundariesCsv, exportUnitsCsv, exportConfigJson].forEach((button) => {
  button.addEventListener("click", () => setExportMenu(false));
});

document.addEventListener("click", (event) => {
  if (!exportMenu.hidden && !event.target.closest(".export-menu")) {
    setExportMenu(false);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setExportMenu(false);
});

importConfigJson.addEventListener("change", async () => {
  const file = importConfigJson.files?.[0];
  if (!file) return;
  try {
    const config = JSON.parse(await file.text());
    applyImportedConfig(config);
  } catch (error) {
    updateCsvStatus(`配置导入失败：${error.message}`, true);
  } finally {
    importConfigJson.value = "";
    setExportMenu(false);
  }
});

ingestRealtimeSample.addEventListener("click", async () => {
  try {
    await ingestCurrentRealtimeBoundary();
  } catch (error) {
    updateRealtimeStatus(`实时数据推送失败：${error.message}`, true);
  }
});

stepRealtime.addEventListener("click", async () => {
  try {
    await stepRealtimeModel();
  } catch (error) {
    updateRealtimeStatus(`实时推进失败：${error.message}`, true);
  }
});

refreshRealtime.addEventListener("click", async () => {
  try {
    await refreshRealtimeLatest();
  } catch (error) {
    updateRealtimeStatus(`刷新实时结果失败：${error.message}`, true);
  }
});

resetRealtime.addEventListener("click", async () => {
  try {
    await resetRealtimeState();
  } catch (error) {
    updateRealtimeStatus(`重置实时状态失败：${error.message}`, true);
  }
});

startMockRealtime.addEventListener("click", async () => {
  try {
    await startRealtimeMock();
  } catch (error) {
    updateRealtimeStatus(`启动 Mock 失败：${error.message}`, true);
  }
});

stopMockRealtime.addEventListener("click", async () => {
  try {
    await stopRealtimeMock();
  } catch (error) {
    updateRealtimeStatus(`停止 Mock 失败：${error.message}`, true);
  }
});

refreshMockRealtime.addEventListener("click", async () => {
  try {
    await refreshRealtimeMockStatus();
  } catch (error) {
    updateRealtimeStatus(`刷新 Mock 状态失败：${error.message}`, true);
  }
});

resultChart.addEventListener("mousemove", updateChartTooltip);
resultChart.addEventListener("mouseleave", hideChartTooltip);

csvFileInput.addEventListener("change", async () => {
  const file = csvFileInput.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    const records = normalizeCsvRecords(text);
    if (!records.length) throw new Error("没有读到有效数据行。");
    csvRecords = records;
    csvFileName = file.name;
    csvText = text;
    const start = records[0].time.toFixed(2);
    const end = records[records.length - 1].time.toFixed(2);
    updateCsvStatus(`已加载 ${file.name}：${records.length} 条记录，数据范围 ${start} - ${end} d。仿真会按“运行”页的仿真天数和计算步长推进，超出数据范围后保持最后一条边界条件。`);
  } catch (error) {
    csvRecords = [];
    csvFileName = "";
    csvText = "";
    updateCsvStatus(`CSV 解析失败：${error.message}`, true);
  }
});

clearCsvData.addEventListener("click", () => {
  csvRecords = [];
  csvFileName = "";
  csvText = "";
  csvFileInput.value = "";
  updateCsvStatus("已清除历史数据。再次运行将使用手动参数。");
});

document.getElementById("runSimulation").addEventListener("click", async () => {
  statusBadge.textContent = "计算中";
  startProgress();
  hideChartTooltip();
  try {
    lastResult = await runBackendSimulation();
    statusBadge.textContent = "已完成";
    finishProgress();
    updateMetrics(lastResult);
    drawChart(lastResult, activeChart);
  } catch (error) {
    statusBadge.textContent = "计算失败";
    finishProgress(true);
    updateCsvStatus(`后端计算失败：${error.message}`, true);
  }
});

document.getElementById("resetLayout").addEventListener("click", () => {
  const layout = {
    influent: [30, 150],
    anaerobic: [210, 88],
    anoxic: [390, 88],
    aerobic: [570, 88],
    clarifier: [750, 88],
    effluent: [930, 88],
    ras: [480, 280],
    was: [760, 280],
  };
  nodes.forEach((node) => {
    [node.x, node.y] = layout[node.id];
  });
  drawNodes();
});

window.addEventListener("resize", () => {
  drawEdges();
  if (lastResult) drawChart(lastResult, activeChart);
});

async function initializeApp() {
  await loadSavedParams();
  renderForm();
  renderMetricOptions();
  drawNodes();
  showDefaultBoundaryPreview();
}

initializeApp();
