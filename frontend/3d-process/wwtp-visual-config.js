const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

export const visualMetricOrder = ["risk", "do", "nh4", "mlss", "cod", "flow"];

export const visualMetricConfigs = {
  risk: {
    buttonLabel: "综合",
    label: "综合风险",
    boostable: false,
    stops: [
      { value: 0, color: 0x37c8da, label: "正常" },
      { value: 0.45, color: 0xf1c45c, label: "关注" },
      { value: 1, color: 0xed7d73, label: "报警" }
    ],
    value: (unit) => Math.max(
      clamp(unit.nh4 / 12, 0, 1),
      clamp((1.2 - unit.do) / 1.2, 0, 1),
      clamp((unit.cod - 45) / 95, 0, 1)
    ),
    alert: (unit) => Math.max(
      clamp(unit.nh4 / 12, 0, 1),
      clamp((1.2 - unit.do) / 1.2, 0, 1),
      clamp((unit.cod - 45) / 95, 0, 1)
    )
  },
  do: {
    buttonLabel: "DO",
    label: "DO mg/L",
    boostable: false,
    stops: [
      { value: 0, color: 0xed7d73, label: "0 缺氧" },
      { value: 1, color: 0xf1c45c, label: "1 偏低" },
      { value: 2, color: 0x37c8da, label: "2 适宜" },
      { value: 4, color: 0x72e3f2, label: "4 高" }
    ],
    value: (unit) => unit.do,
    alert: (unit) => clamp((1.2 - unit.do) / 1.2, 0, 1)
  },
  nh4: {
    buttonLabel: "NH4-N",
    label: "NH4-N mg/L",
    boostable: true,
    stops: [
      { value: 0, color: 0x37c8da, label: "0 低" },
      { value: 5, color: 0xf1c45c, label: "5 偏高" },
      { value: 10, color: 0xed7d73, label: "10 高" }
    ],
    value: (unit) => unit.nh4
  },
  mlss: {
    buttonLabel: "MLSS",
    label: "MLSS/TSS mg/L",
    boostable: true,
    stops: [
      { value: 0, color: 0x72e3f2, label: "清" },
      { value: 3000, color: 0x7a5f3c, label: "3000" },
      { value: 8500, color: 0x24160f, label: "8500" }
    ],
    value: (unit) => unit.mlss
  },
  cod: {
    buttonLabel: "COD",
    label: "COD mg/L",
    boostable: true,
    stops: [
      { value: 30, color: 0x37c8da, label: "30" },
      { value: 80, color: 0xf1c45c, label: "80" },
      { value: 180, color: 0xed7d73, label: "180" }
    ],
    value: (unit) => unit.cod
  },
  flow: {
    buttonLabel: "流量",
    label: "流量 m3/d",
    boostable: true,
    stops: [
      { value: 6000, color: 0x6aa4d8, label: "低" },
      { value: 10000, color: 0x37c8da, label: "设计" },
      { value: 18000, color: 0xf1c45c, label: "高" },
      { value: 30000, color: 0xed7d73, label: "冲击" }
    ],
    value: (unit) => unit.flow
  }
};
