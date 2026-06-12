const apiBaseInput = document.getElementById("apiBaseInput");
const engineSelect = document.getElementById("engineSelect");
const includeLongHorizon = document.getElementById("includeLongHorizon");
const refreshCatalog = document.getElementById("refreshCatalog");
const runEvaluation = document.getElementById("runEvaluation");
const exportJson = document.getElementById("exportJson");
const clearLog = document.getElementById("clearLog");
const runLog = document.getElementById("runLog");
const settingsToggle = document.getElementById("settingsToggle");
const settingsPanel = document.getElementById("settingsPanel");
const sessionId = document.getElementById("sessionId");
const sessionStarted = document.getElementById("sessionStarted");
const runHistory = document.getElementById("runHistory");
const reliabilityStatus = document.getElementById("reliabilityStatus");
const reliabilityDetail = document.getElementById("reliabilityDetail");
const stabilityStatus = document.getElementById("stabilityStatus");
const stabilityDetail = document.getElementById("stabilityDetail");
const generalityStatus = document.getElementById("generalityStatus");
const generalityDetail = document.getElementById("generalityDetail");
const runtimeStatus = document.getElementById("runtimeStatus");
const runtimeDetail = document.getElementById("runtimeDetail");
const lastRunTime = document.getElementById("lastRunTime");
const lastRunStatus = document.getElementById("lastRunStatus");
const catalogStatus = document.getElementById("catalogStatus");
const engineCatalog = document.getElementById("engineCatalog");
const scenarioRows = document.getElementById("scenarioRows");
const scenarioPassRate = document.getElementById("scenarioPassRate");
const stabilityChecks = document.getElementById("stabilityChecks");
const referenceGates = document.getElementById("referenceGates");
const contractEngineId = document.getElementById("contractEngineId");
const contractStatus = document.getElementById("contractStatus");
const contractUpdated = document.getElementById("contractUpdated");
const matrixEngineLabel = document.getElementById("matrixEngineLabel");
const testLayers = document.getElementById("testLayers");

let lastEvaluationReport = null;
let historyItems = [];

const fallbackEngines = [
  {
    id: "v1",
    modelId: "AAO-ASM1",
    modelFamily: "ASM",
    componentCount: 13,
    status: "current",
    resultContract: "frontend_series_v1",
    notes: ["AAO 工艺边界 + ASM1 反应内核 + 沉淀池与回流假设。"],
  },
];

const scenarioMeta = {
  baseline: { label: "基准工况", desc: "常规进水、默认池容与回流", icon: "O" },
  load: { label: "高负荷工况", desc: "进水有机负荷与氨氮负荷提高", icon: "^" },
  temperature: { label: "低温工况", desc: "进水温度降低，反应速率受限", icon: "*" },
  hydraulics: { label: "水力冲击工况", desc: "进水流量波动，HRT 被压缩", icon: "H" },
  oxygen: { label: "低 DO 工况", desc: "好氧段 DO 边界降低", icon: "D" },
};

function nowText() {
  return new Date().toLocaleString("zh-CN", { hour12: false });
}

function timeOnly() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function apiBase() {
  return apiBaseInput.value.replace(/\/+$/, "");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatValue(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return number.toFixed(digits);
}

function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${number.toFixed(1)}%`;
}

function statusText(status) {
  const labels = {
    current: "当前",
    pass: "通过",
    fail: "失败",
    needs_review: "需复核",
    not_implemented: "待接入",
    ok: "通过",
  };
  return labels[status] || status || "--";
}

function statusClass(status) {
  if (status === "pass" || status === "ok" || status === "current") return "status-pass";
  if (status === "fail") return "status-fail";
  return "status-review";
}

function layerClass(status) {
  if (status === "pass") return "layer-active";
  if (status === "needs_review") return "layer-review";
  return "layer-pending";
}

function scoreFromStatus(status, passed, total) {
  if (total > 0) return (passed / total) * 100;
  if (status === "pass") return 100;
  if (status === "needs_review") return 75;
  if (status === "fail") return 0;
  return NaN;
}

function log(message, level = "INFO") {
  runLog.textContent = `${runLog.textContent.trim()}\n[${timeOnly()}] ${level.padEnd(5, " ")} ${message}`.trim();
  runLog.scrollTop = runLog.scrollHeight;
}

async function requestJson(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || response.statusText || "请求失败");
  }
  return payload;
}

function renderCatalog(engines, source = "api") {
  const safeEngines = engines.length ? engines : fallbackEngines;
  const current = safeEngines[0];
  catalogStatus.textContent = source === "api" ? `${safeEngines.length} 个场景` : "本地合同占位";
  contractEngineId.textContent = current.modelId === "ASM1" ? "AAO-ASM1" : current.modelId || current.id || "--";
  contractStatus.innerHTML = `<span class="dot"></span>${source === "api" ? "注册成功" : "本地占位"}`;
  contractStatus.className = source === "api" ? "status-pass" : "status-review";
  contractUpdated.textContent = nowText();
  matrixEngineLabel.textContent = `（AAO-ASM1 ${current.id || "v1"}）`;
  engineSelect.innerHTML = safeEngines
    .map((engine) => `<option value="${escapeHtml(engine.id)}">${escapeHtml(engine.modelId === "ASM1" ? "AAO-ASM1" : engine.modelId)} ${escapeHtml(engine.id)}</option>`)
    .join("");
  engineCatalog.innerHTML = `
    <article>
      <strong>工艺边界场景包 v1.0</strong>
      <span>覆盖进水负荷、温度、水力停留、DO 与回流假设下的鲁棒性。</span>
      <em>5 个场景</em>
    </article>
    <article>
      <strong>AAO-ASM1 Process Engine</strong>
      <span>ASM1 内核 · ${current.componentCount || 0} 组分 · ${escapeHtml(current.resultContract || "--")}</span>
      <em>${statusText(current.status)}</em>
    </article>
  `;
}

async function refreshEngineCatalog() {
  try {
    log(`读取引擎注册表：${apiBase()}/api/engines`);
    const payload = await requestJson("/api/engines");
    renderCatalog(payload.engines || [], "api");
    log(`注册表读取完成：${payload.engines?.length || 0} 个引擎。`);
  } catch (error) {
    renderCatalog(fallbackEngines, "fallback");
    log(`注册表读取失败：${error.message}。已显示本地 AAO-ASM1 工艺引擎占位。`, "WARN");
  }
}

function renderMetricCards(report) {
  const reliability = report.reliability || {};
  const stability = report.stability || {};
  const generality = report.generality || {};
  const runs = reliability.runs || [];
  const checks = stability.checks || [];
  const passedRuns = runs.filter((run) => run.status === "pass").length;
  const passedChecks = checks.filter((check) => check.status === "pass").length;
  const totalDurationMs = runs.reduce((sum, row) => sum + Number(row.durationMs || 0), 0);
  const avgDurationMs = runs.length ? totalDurationMs / runs.length : 0;

  reliabilityStatus.textContent = formatPercent(scoreFromStatus(reliability.status, passedRuns, runs.length));
  reliabilityDetail.innerHTML = `${statusText(reliability.status)}<br />${passedRuns}/${runs.length || 0} 场景通过`;
  reliabilityStatus.className = statusClass(reliability.status);

  stabilityStatus.textContent = formatPercent(scoreFromStatus(stability.status, passedChecks, checks.length));
  stabilityDetail.innerHTML = `${statusText(stability.status)}<br />${passedChecks}/${checks.length || 0} 检查通过`;
  stabilityStatus.className = statusClass(stability.status);

  const expectedAxes = 5;
  const coveredAxes = generality.coveredAxes || [];
  generalityStatus.textContent = formatPercent(scoreFromStatus(generality.status, coveredAxes.length, expectedAxes));
  generalityDetail.innerHTML = `${statusText(generality.status)}<br />${coveredAxes.length}/${expectedAxes} 工况轴覆盖`;
  generalityStatus.className = statusClass(generality.status);

  runtimeStatus.textContent = `${formatValue(totalDurationMs / 1000, 2)} s`;
  runtimeDetail.innerHTML = `总耗时<br />平均 ${formatValue(avgDurationMs / 1000, 2)} s/场景`;
}

function renderTestLayers(report) {
  const layers = report.testLayers || [
    {
      layerId: "model_kernel",
      name: "模型内核测试",
      target: "ASM1 Reaction Kernel",
      status: "not_implemented",
      scope: "只测反应速率、状态变量、单位、质量守恒、数值稳定性。",
      boundary: "不包含池容、工艺流程、沉淀池或回流。",
    },
    {
      layerId: "process_engine",
      name: "工艺引擎测试",
      target: "AAO + ASM1 + Clarifier + Recycle",
      status: report.status || "needs_review",
      scope: "测试合同完整性、数值稳定性、工况鲁棒性和输出序列一致性。",
      boundary: "包含进水、池容、HRT/SRT、DO、回流比和沉淀池假设。",
    },
    {
      layerId: "engineering_reference",
      name: "工程参考验证",
      target: "BSM1 / 实测数据 / 历史项目",
      status: "needs_review",
      scope: "与参考案例或实测数据对比，评估工程合理性。",
      boundary: "当前 BSM1 只是 reference-only。",
    },
  ];
  testLayers.innerHTML = layers
    .map((layer, index) => {
      const label = `L${index + 1} · ${layer.name}`;
      return `
        <article class="layer-card ${layerClass(layer.status)}">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(layer.target)}</strong>
          <p>${escapeHtml(layer.scope)} ${escapeHtml(layer.boundary)}</p>
          <em>${statusText(layer.status)}</em>
        </article>
      `;
    })
    .join("");
}

function renderScenarioRows(report) {
  const runs = report.reliability?.runs || [];
  const passed = runs.filter((run) => run.status === "pass").length;
  scenarioPassRate.textContent = `总体通过率：${passed}/${runs.length || 0}`;
  scenarioRows.innerHTML = runs.length
    ? runs
        .map((row) => {
          const meta = scenarioMeta[row.axis] || { label: row.title || row.name, desc: row.axis || "--", icon: "M" };
          const maxRelativeError = row.status === "pass" ? 0 : 100;
          return `
            <tr>
              <td>
                <span class="scenario-name">
                  <span class="scenario-icon scenario-axis-${escapeHtml(row.axis)}">${escapeHtml(meta.icon)}</span>
                  ${escapeHtml(meta.label)}
                </span>
              </td>
              <td>${escapeHtml(meta.desc)}</td>
              <td class="${statusClass(row.status)}">${statusText(row.status)}</td>
              <td>${row.pointCount ?? "--"}</td>
              <td>${formatValue(row.summary?.effNh4, 2)}</td>
              <td>${formatValue(row.summary?.effTn, 2)}</td>
              <td>${formatValue(row.summary?.effTss, 2)}</td>
              <td class="${statusClass(row.status)}">${formatPercent(maxRelativeError)}</td>
            </tr>
          `;
        })
        .join("")
    : `<tr><td colspan="8">评估报告没有返回场景矩阵。</td></tr>`;
}

function renderStability(report) {
  const checks = report.stability?.checks || [];
  stabilityChecks.innerHTML = checks.length
    ? checks
        .map(
          (check) => `
            <article>
              <span>${escapeHtml(check.name)}</span>
              <strong class="${statusClass(check.status)}">${statusText(check.status)} · ${formatPercent(Number(check.maxRelError || 0) * 100)}</strong>
            </article>
          `,
        )
        .join("")
    : "<article><span>评估报告没有返回稳定性检查。</span><strong>--</strong></article>";
}

function renderReferenceGates(report) {
  const gates = report.referenceGates || [];
  referenceGates.innerHTML = gates.length
    ? gates
        .map(
          (gate) => `
            <article>
              <span>${escapeHtml(gate.caseName || gate.gateId)}<br />${escapeHtml(gate.comparisonStatus || "--")} · ${(gate.rows || []).length} 个参考指标</span>
              <strong class="${statusClass(gate.status)}">${statusText(gate.status)}</strong>
            </article>
          `,
        )
        .join("")
    : "<p>评估报告没有返回参考案例门禁。</p>";
}

function renderHistory(report) {
  historyItems = [
    {
      time: nowText(),
      model: `AAO-ASM1 ${report.engine?.id || "v1"}`,
      status: report.status,
    },
    ...historyItems,
  ].slice(0, 4);

  runHistory.innerHTML = historyItems
    .map(
      (item) => `
        <article>
          <span class="mini-check"></span>
          <div>
            <strong>${escapeHtml(item.time)}</strong>
            <small>${escapeHtml(item.model)}</small>
          </div>
          <em>${statusText(item.status)}</em>
        </article>
      `,
    )
    .join("");
}

function renderEvaluation(report) {
  lastEvaluationReport = report;
  exportJson.disabled = false;
  renderTestLayers(report);
  renderMetricCards(report);
  renderScenarioRows(report);
  renderStability(report);
  renderReferenceGates(report);
  renderHistory(report);
  const finishedAt = nowText();
  lastRunTime.textContent = finishedAt;
  lastRunStatus.innerHTML = `<span class="dot"></span>${statusText(report.status)}`;
  lastRunStatus.className = statusClass(report.status);
  contractUpdated.textContent = finishedAt;
}

async function runEngineEvaluation() {
  const engineId = engineSelect.value || "v1";
  try {
    runEvaluation.disabled = true;
    const longFlag = includeLongHorizon.checked;
    log(`会话 ${sessionId.textContent} 创建`);
    log(`引擎选择：AAO-ASM1 工艺仿真引擎（${engineId}）`);
    log(`边界声明：当前测试包含 AAO 池容/流量/DO/回流/沉淀池假设，不是裸 ASM1 内核认证。`);
    log(`场景包：工艺边界场景包 v1.0${longFlag ? "，包含长周期检查" : ""}`);
    log("开始评估合同、数值稳定性与工况鲁棒性...");
    const report = await requestJson(`/api/engines/${encodeURIComponent(engineId)}/evaluate?includeLongHorizon=${longFlag ? "true" : "false"}`, { method: "POST" });
    renderEvaluation(report);
    log(`评估完成：${statusText(report.status)}，runId ${report.runId || "--"}。`);
  } catch (error) {
    lastRunStatus.innerHTML = `<span class="dot"></span>失败`;
    lastRunStatus.className = "status-fail";
    log(`评估失败：${error.message}`, "ERROR");
  } finally {
    runEvaluation.disabled = false;
  }
}

function exportLatestJsonReport() {
  if (!lastEvaluationReport) return;
  const payload = JSON.stringify(lastEvaluationReport, null, 2);
  const blob = new Blob([payload], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const runId = lastEvaluationReport.runId || "engine-evaluation";
  anchor.href = url;
  anchor.download = `${runId}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  log(`已导出 JSON 报告：${anchor.download}`);
}

settingsToggle.addEventListener("click", () => {
  settingsPanel.hidden = !settingsPanel.hidden;
});
refreshCatalog.addEventListener("click", refreshEngineCatalog);
runEvaluation.addEventListener("click", runEngineEvaluation);
exportJson.addEventListener("click", exportLatestJsonReport);
clearLog.addEventListener("click", () => {
  runLog.textContent = "日志已清空。";
});

const sessionSuffix = new Date().toISOString().slice(0, 10).replaceAll("-", "");
sessionId.textContent = `sess_${sessionSuffix}_001`;
sessionStarted.textContent = nowText();
renderCatalog(fallbackEngines, "fallback");
renderTestLayers({ status: "needs_review" });
log("已加载本地 AAO-ASM1 工艺引擎占位。点击设置可切换 API 或刷新注册表。");
