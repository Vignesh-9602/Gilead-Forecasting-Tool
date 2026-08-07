import React, { useMemo } from "react";
import { Box } from "@mui/material";
import Plot from "react-plotly.js";
const PlotComponent = Plot.default || Plot;
import dayjs from "dayjs";

// ─── Constants ────────────────────────────────────────────────────────────────
const DATE_INPUT_FORMATS = [
  "MMM-YY",
  "YYYY-MM",
  "YYYY-MM-DD",
  "YYYY-MM-DDTHH:mm:ssZ",
];

const getScenarioColor = (index) =>
  `hsl(${(index * 137.508) % 360}, 70%, 50%)`;

// Palette used to color individual breakdown lines (payment type / product /
// etc.) on non-Total-Market tabs, so each line is visually distinct.
const CHART_PALETTE = ["#4F46E5", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4"];

// ─── ForecastChart ────────────────────────────────────────────────────────────
// NOTE: This component is only ever rendered for the "standard" tabs
// (total_market, prod_dist, payer_dist, payer_prod, prod_payer) — ModelInput
// renders PaymentPayerProductTable (with its own real-data chart) for the
// "payment_payer_prod" tab instead, so no 3-level-hierarchy handling belongs
// here.
const ForecastChart = React.memo(function ForecastChart({
  chartData,
  productFilter,
  payerFilter,
  appliedBrand,
  activeTab,
  appliedScenario,
  selectedCompareScenarios = [],
  compareScenarioOptions = [],
  rawScenariosData,
  activeMetricKey,
  filterFromYM,
  filterToYM,
  viewMode = "monthly",
}) {
  // ══════════════════════════════════════════════════════════════════════════
  // ALL HOOKS MUST BE CALLED UNCONDITIONALLY — no early returns before here.
  // ══════════════════════════════════════════════════════════════════════════

  const months = chartData?.months || [];
  const fsi = chartData?.forecast_start_index || 0;
  const series = chartData?.series || [];

  const formatMonths = (rawMonths) =>
    (rawMonths || []).map((m) => {
      if (typeof m === "string" && /^\d{4}$/.test(m.trim())) return m.trim();
      const parsed = dayjs(m, DATE_INPUT_FORMATS, true);
      if (!parsed.isValid()) {
        if (typeof m === "string" && /^\d{4}-\d{2}$/.test(m.trim())) return m.trim();
        return new Date(m).toLocaleDateString("en-US", { month: "short", year: "2-digit" });
      }
      return viewMode === "yearly" ? parsed.format("YYYY") : parsed.format("MMM-YY");
    });

  const allMonths = formatMonths(months);
  const isTotalMarket = activeTab === "total_market";
  const currentBrand = (productFilter || appliedBrand || "").toLowerCase();
  const currentPayer = (payerFilter || "").toLowerCase();

  const scenarioNamesToShow = selectedCompareScenarios.length
    ? selectedCompareScenarios
    : (compareScenarioOptions.length
      ? compareScenarioOptions
      : (appliedScenario ? [appliedScenario] : []));

  // ── Scenario color map (MUST be called unconditionally as a hook) ──────
  const scenarioNamesForColoring = Array.from(
    new Set([
      ...(compareScenarioOptions.length ? compareScenarioOptions : []),
      ...scenarioNamesToShow,
      ...(appliedScenario ? [appliedScenario] : []),
    ].filter(Boolean)),
  );

  const scenarioColorMap = useMemo(() => {
    const map = {};
    let index = 0;
    scenarioNamesForColoring.forEach((name) => {
      if (!map[name]) {
        map[name] = getScenarioColor(index++);
      }
    });
    return map;
  }, [scenarioNamesForColoring]);

  // ═══════════════════════════════════════════════════════════════════════
  // ALL HOOKS ABOVE — conditional logic and early returns safe from here.
  // ═══════════════════════════════════════════════════════════════════════

  if (!months.length || !series.length) {
    return (
      <Box sx={{ p: 4, textAlign: "center", color: "#94a3b8", fontSize: "14px" }}>
        No chart data available. Please select filters and apply.
      </Box>
    );
  }

  let filteredSeries;
  if (isTotalMarket) {
    const tmvFiltered = series.filter((s) =>
      scenarioNamesToShow.includes(s.label || ""),
    );
    filteredSeries = (tmvFiltered.length ? tmvFiltered : series).map((s) => ({
      ...s,
      scenario: s.label,
    }));
  } else {
    // Non-Total-Market tabs (Product Distribution, Payment Type
    // Distribution, Payment Type / Product) must always show the currently
    // active scenario's own breakdown — one line per payment type / product
    // / hierarchy leaf — never a per-scenario "Compare Scenarios" overlay.
    // `series` here is already the correctly clipped/normalized data for
    // this tab and scenario (see ModelInput's normalizeLiverResponse +
    // mapLiverTabToView), so use it directly instead of re-fetching from
    // rawScenariosData. Re-deriving from rawScenariosData per selected
    // scenario was the source of two bugs: (1) it replaced the normal
    // payment-type/product lines with scenario-tagged ones, and went
    // completely blank whenever the Compare Scenarios selection excluded
    // the scenario whose raw key happened to match; (2) it depended on this
    // component's own separate, easily-stale TAB_KEY_MAP copy.
    filteredSeries = (series || []).map((s) => ({ ...s, scenario: s.scenario || "" }));
  }

  const isFilterFocusMode = !isTotalMarket && (!!currentBrand || !!currentPayer);
  if (isFilterFocusMode) {
    filteredSeries = filteredSeries.filter((s) => {
      const label = (s.label || "").toLowerCase();
      if (activeTab === "prod_dist") return currentBrand && label === currentBrand;
      if (activeTab === "payer_dist") return currentPayer && label === currentPayer;
      if (activeTab === "payer_prod" || activeTab === "prod_payer") {
        return (
          (!currentPayer || label.includes(currentPayer)) &&
          (!currentBrand || label.includes(currentBrand))
        );
      }
      return true;
    });
  }

  const getSeriesColor = (item, index) => {
    if (activeTab === "total_market") {
      const scenarioName = item?.scenario || item?.label || "";
      if (scenarioName && scenarioColorMap[scenarioName]) {
        return scenarioColorMap[scenarioName];
      }
      return getScenarioColor(index);
    }
    // Payment type / product / other breakdown lines each get their own
    // distinct color from the shared palette — never grouped/colored by
    // scenario on these tabs.
    return CHART_PALETTE[index % CHART_PALETTE.length];
  };

  const traces = filteredSeries.flatMap((s, idx) => {
    const seriesLabel = (s.label || "").toLowerCase();

    let isSelectedTrace = s.scenario ? s.scenario === appliedScenario : true;

    if (activeTab === "prod_dist" && currentBrand) {
      isSelectedTrace = isSelectedTrace && seriesLabel === currentBrand;
    } else if (activeTab === "payer_dist" && currentPayer) {
      isSelectedTrace = isSelectedTrace && seriesLabel === currentPayer;
    } else if (
      (activeTab === "payer_prod" || activeTab === "prod_payer") &&
      currentPayer &&
      currentBrand
    ) {
      isSelectedTrace =
        isSelectedTrace &&
        seriesLabel.includes(currentPayer) &&
        seriesLabel.includes(currentBrand);
    } else if (!isTotalMarket && !s.scenario) {
      isSelectedTrace =
        (currentBrand && seriesLabel.includes(currentBrand)) ||
        (currentPayer && seriesLabel.includes(currentPayer));
    }

    const width = isSelectedTrace ? 3.5 : 1.5;
    const color = isSelectedTrace ? "#f59e0b" : getSeriesColor(s, idx);

    const name =
      s.scenario && s.scenario !== s.label
        ? `${s.label} (${s.scenario})`
        : s.label;

    const itemMonths = s.months && s.months.length ? formatMonths(s.months) : allMonths;
    const itemFsi = s.forecastStartIndex != null ? s.forecastStartIndex : fsi;

    const forecastX =
      itemFsi > 0
        ? [itemMonths[itemFsi - 1], ...itemMonths.slice(itemFsi)]
        : itemMonths.slice(itemFsi);
    const lastTrain = s.train_values?.length
      ? s.train_values[s.train_values.length - 1]
      : null;
    const forecastY =
      itemFsi > 0
        ? [
          lastTrain ?? null,
          ...(Array.isArray(s.forecast_values) ? s.forecast_values : []),
        ]
        : Array.isArray(s.forecast_values)
          ? s.forecast_values
          : [];

    const trainX = itemMonths.slice(0, itemFsi);
    const trainY = Array.isArray(s.train_values)
      ? s.train_values.slice(0, itemFsi)
      : [];

    return [
      {
        x: trainX,
        y: trainY,
        type: "scatter",
        mode: "lines",
        name,
        legendgroup: name,
        line: { color, width },
      },
      {
        x: forecastX,
        y: forecastY,
        type: "scatter",
        mode: "lines",
        name,
        legendgroup: name,
        showlegend: false,
        line: { color, width, dash: "dot" },
      },
    ];
  });

  return (
    <Box sx={{ width: "100%", height: 380 }}>
      <PlotComponent
        data={traces}
        layout={{
          autosize: true,
          height: 380,
          margin: { l: 50, r: 30, t: 8, b: 120 },
          hoverlabel: { namelength: -1 },
          legend: {
            orientation: "h",
            x: 0.5,
            xanchor: "center",
            y: -0.45,
            yanchor: "top",
            traceorder: "normal",
            itemwidth: 10,
          },
          showlegend: true,
          xaxis: { tickangle: -45, showgrid: true },
          yaxis: { showgrid: false },
          paper_bgcolor: "white",
          plot_bgcolor: "white",
        }}
        style={{ width: "100%", height: "100%" }}
        config={{ responsive: true, displayModeBar: false }}
      />
    </Box>
  );
});

export default ForecastChart;