const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const mappingFieldLabels = {
  "boundaries.q": "进水/出水流量 q",
  "boundaries.rasQ": "外回流流量 rasQ",
  "boundaries.irQ": "内回流流量 irQ",
  aerobicDo: "好氧池 DO 兼容字段",
  aerobicMlss: "好氧池 MLSS 兼容字段",
  rasMlss: "外回流 MLSS 兼容字段",
  effTss: "出水 TSS 兼容字段",
  effNh4: "出水 NH4-N 兼容字段",
  effNo3: "出水 NO3-N 兼容字段",
  effCod: "出水 COD 兼容字段",
  "clarifier.effluentTss": "二沉池出水 TSS"
};

function fieldLabel(path, unitMeta) {
  if (mappingFieldLabels[path]) return mappingFieldLabels[path];
  const match = path.match(/^units\.([^.]+)\.([^.]+)$/);
  if (match) {
    const unitName = unitMeta?.[match[1]]?.name || match[1];
    const metricName = { DO: "DO", TSS: "MLSS/TSS", NH4: "NH4-N", NO3: "NO3-N", COD: "COD" }[match[2]] || match[2];
    return `${unitName} ${metricName}`;
  }
  return path;
}

function createMappingReport(unitMeta) {
  return { fallbackCount: 0, fields: new Map(), unitMeta };
}

function recordMappingFallback(report, path) {
  if (!report || !path) return;
  report.fallbackCount += 1;
  report.fields.set(path, (report.fields.get(path) || 0) + 1);
}

function finiteAt(values, index, fallback, report, path = "") {
  const value = Array.isArray(values) ? Number(values[index]) : Number.NaN;
  if (Number.isFinite(value)) return value;
  recordMappingFallback(report, path);
  return fallback;
}

function firstFiniteAt(index, fallback, sources, report) {
  for (const source of sources) {
    const value = Array.isArray(source.values) ? Number(source.values[index]) : Number.NaN;
    if (Number.isFinite(value)) return value;
  }
  sources.forEach((source) => recordMappingFallback(report, source.path));
  return fallback;
}

function unitMetric(result, unit, metric, index, fallback, report) {
  return finiteAt(result?.units?.[unit]?.[metric], index, fallback, report, `units.${unit}.${metric}`);
}

function boundaryMetric(result, metric, index, fallback, report) {
  return finiteAt(result?.boundaries?.[metric], index, fallback, report, `boundaries.${metric}`);
}

function stateFromSimulationResult(result, index, fallback, report) {
  const q = boundaryMetric(result, "q", index, fallback.effluent.flow, report);
  const rasQ = boundaryMetric(result, "rasQ", index, fallback.ras.flow, report);
  const irQ = boundaryMetric(result, "irQ", index, fallback.internalRecycle.flow, report);
  const aerobicDo = firstFiniteAt(index, fallback.aerobic.do, [
    { values: result?.units?.aerobic?.DO, path: "units.aerobic.DO" },
    { values: result?.aerobicDo, path: "aerobicDo" }
  ], report);
  const aerobicMlss = firstFiniteAt(index, fallback.aerobic.mlss, [
    { values: result?.units?.aerobic?.TSS, path: "units.aerobic.TSS" },
    { values: result?.aerobicMlss, path: "aerobicMlss" }
  ], report);
  const rasMlss = firstFiniteAt(index, fallback.ras.mlss, [
    { values: result?.units?.ras?.TSS, path: "units.ras.TSS" },
    { values: result?.rasMlss, path: "rasMlss" }
  ], report);
  const airFactor = clamp(aerobicDo / 2.1, 0, 1.6);
  const airFlow = 4200 * airFactor;
  const blowerPower = 72 * airFactor;
  const blowerSpeed = 31500 * airFactor;
  const blowerLift = 68 * airFactor;

  return {
    anaerobic: {
      do: unitMetric(result, "anaerobic", "DO", index, fallback.anaerobic.do, report),
      mlss: unitMetric(result, "anaerobic", "TSS", index, fallback.anaerobic.mlss, report),
      nh4: unitMetric(result, "anaerobic", "NH4", index, fallback.anaerobic.nh4, report),
      no3: unitMetric(result, "anaerobic", "NO3", index, fallback.anaerobic.no3, report),
      cod: unitMetric(result, "anaerobic", "COD", index, fallback.anaerobic.cod, report),
      flow: q + rasQ
    },
    anoxic: {
      do: unitMetric(result, "anoxic", "DO", index, fallback.anoxic.do, report),
      mlss: unitMetric(result, "anoxic", "TSS", index, fallback.anoxic.mlss, report),
      nh4: unitMetric(result, "anoxic", "NH4", index, fallback.anoxic.nh4, report),
      no3: unitMetric(result, "anoxic", "NO3", index, fallback.anoxic.no3, report),
      cod: unitMetric(result, "anoxic", "COD", index, fallback.anoxic.cod, report),
      flow: q + rasQ + irQ
    },
    aerobic: {
      do: aerobicDo,
      mlss: aerobicMlss,
      nh4: unitMetric(result, "aerobic", "NH4", index, fallback.aerobic.nh4, report),
      no3: unitMetric(result, "aerobic", "NO3", index, fallback.aerobic.no3, report),
      cod: unitMetric(result, "aerobic", "COD", index, fallback.aerobic.cod, report),
      flow: q + rasQ + irQ
    },
    clarifier: {
      do: unitMetric(result, "clarifier", "DO", index, fallback.clarifier.do, report),
      mlss: firstFiniteAt(index, fallback.clarifier.mlss, [
        { values: result?.clarifier?.effluentTss, path: "clarifier.effluentTss" },
        { values: result?.units?.clarifier?.TSS, path: "units.clarifier.TSS" }
      ], report),
      nh4: unitMetric(result, "clarifier", "NH4", index, fallback.clarifier.nh4, report),
      no3: unitMetric(result, "clarifier", "NO3", index, fallback.clarifier.no3, report),
      cod: unitMetric(result, "clarifier", "COD", index, fallback.clarifier.cod, report),
      flow: q
    },
    ras: {
      do: unitMetric(result, "ras", "DO", index, fallback.ras.do, report),
      mlss: rasMlss,
      nh4: unitMetric(result, "ras", "NH4", index, fallback.ras.nh4, report),
      no3: unitMetric(result, "ras", "NO3", index, fallback.ras.no3, report),
      cod: unitMetric(result, "ras", "COD", index, fallback.ras.cod, report),
      flow: rasQ,
      ratio: q ? rasQ / q : fallback.ras.ratio
    },
    internalRecycle: {
      do: aerobicDo,
      mlss: aerobicMlss,
      nh4: unitMetric(result, "aerobic", "NH4", index, fallback.internalRecycle.nh4, report),
      no3: unitMetric(result, "aerobic", "NO3", index, fallback.internalRecycle.no3, report),
      cod: unitMetric(result, "aerobic", "COD", index, fallback.internalRecycle.cod, report),
      flow: irQ,
      ratio: q ? irQ / q : fallback.internalRecycle.ratio
    },
    effluent: {
      do: unitMetric(result, "effluent", "DO", index, fallback.effluent.do, report),
      mlss: firstFiniteAt(index, fallback.effluent.mlss, [
        { values: result?.units?.effluent?.TSS, path: "units.effluent.TSS" },
        { values: result?.effTss, path: "effTss" }
      ], report),
      nh4: firstFiniteAt(index, fallback.effluent.nh4, [
        { values: result?.units?.effluent?.NH4, path: "units.effluent.NH4" },
        { values: result?.effNh4, path: "effNh4" }
      ], report),
      no3: firstFiniteAt(index, fallback.effluent.no3, [
        { values: result?.units?.effluent?.NO3, path: "units.effluent.NO3" },
        { values: result?.effNo3, path: "effNo3" }
      ], report),
      cod: firstFiniteAt(index, fallback.effluent.cod, [
        { values: result?.units?.effluent?.COD, path: "units.effluent.COD" },
        { values: result?.effCod, path: "effCod" }
      ], report),
      flow: q
    },
    blower1: { do: aerobicDo, mlss: 0, nh4: 0, no3: 0, cod: 0, flow: airFlow, power: blowerPower, speed: blowerSpeed, lift: blowerLift },
    blower2: { do: aerobicDo, mlss: 0, nh4: 0, no3: 0, cod: 0, flow: airFlow * 0.93, power: blowerPower * 0.92, speed: blowerSpeed * 0.94, lift: blowerLift * 0.96 },
    blower3: { do: aerobicDo, mlss: 0, nh4: 0, no3: 0, cod: 0, flow: Math.max(0, airFlow - 3000), power: Math.max(0, blowerPower - 50), speed: Math.max(0, blowerSpeed - 22000), lift: Math.max(0, blowerLift - 42) }
  };
}

export function framesFromSimulationResult(result, { fallbackState, unitMeta } = {}) {
  const times = Array.isArray(result?.time) ? result.time : [];
  if (!fallbackState) return null;
  const mappingReport = createMappingReport(unitMeta);
  const frames = times
    .map((day, index) => ({ hour: Number(day) * 24, index }))
    .filter((item) => Number.isFinite(item.hour))
    .map((item) => ({
      hour: item.hour,
      label: `仿真 ${item.hour.toFixed(item.hour >= 10 ? 1 : 2)}h`,
      scenario: "simulation",
      state: stateFromSimulationResult(result, item.index, fallbackState, mappingReport)
    }));
  if (frames.length < 2) return null;
  frames.mappingReport = mappingReport;
  return frames;
}

export function summarizeMappingReport(report) {
  if (!report || report.fallbackCount === 0) {
    return { ok: true, text: "字段映射：主要指标完整，风机状态由好氧池 DO 推导。" };
  }
  const topFields = Array.from(report.fields.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([path]) => fieldLabel(path, report.unitMeta));
  const suffix = report.fields.size > 3 ? `等 ${report.fields.size} 类字段` : topFields.join("、");
  return {
    ok: false,
    text: `字段映射：${suffix} 缺失，已用默认值补齐 ${report.fallbackCount} 处。`
  };
}
