import React from "react";
import { Box } from "@mui/material";
import Plot from "react-plotly.js";
const PlotComponent = Plot.default || Plot;
import dayjs from "dayjs";

// ─── Constants ────────────────────────────────────────────────────────────────
// Defined locally (matching the codebase convention — HIV's HIVMarketChart and
// the Output/MarketEvent siblings each declare their own constants rather than
// sharing a constants module).
const TAB_KEY_MAP = {
  total_market: "total_market_volume",
  prod_dist: "product_distribution",
  payer_dist: "payer_distribution",
  payer_prod: "payer_product",
  prod_payer: "product_payer",
};

const DATE_INPUT_FORMATS = [
  "MMM-YY",
  "YYYY-MM",
  "YYYY-MM-DD",
  "YYYY-MM-DDTHH:mm:ssZ",
];

// Same palette as HIV's SCENARIO_COLORS (HIVMarketChart.jsx), used for
// index-based coloring on Total Market Volume, and cycled per distinct
// product/payer identity on the other tabs (see getSeriesColor below).
const SCENARIO_COLORS = [
  "#2563EB", // Blue
  "#F59E0B", // Orange
  "#16A34A", // Green
  "#9333EA", // Purple
  "#DC2626", // Red
  "#0891B2", // Cyan
  "#D97706", // Amber
  "#4F46E5", // Indigo
];
const NEUTRAL_COLOR = "#64748B"; // HIV's fallback for an unmatched label

// ─── ForecastChart ────────────────────────────────────────────────────────────
const ForecastChart = ({
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
}) => {
  if (!chartData?.months?.length || !chartData?.series?.length) {
    return (
      <Box
        sx={{ p: 4, textAlign: "center", color: "#94a3b8", fontSize: "14px" }}
      >
        No chart data available. Please select filters and apply.
      </Box>
    );
  }

  const months = chartData.months || [];
  const fsi = chartData.forecast_start_index || 0;
  const series = chartData.series || [];

  const formatMonths = (rawMonths) =>
    (rawMonths || []).map((m) => {
      const parsed = dayjs(m, DATE_INPUT_FORMATS, true);
      return parsed.isValid()
        ? parsed.format("MMM-YY")
        : new Date(m).toLocaleDateString("en-US", {
          month: "short",
          year: "2-digit",
        });
    });

  const allMonths = formatMonths(months);

  const isTotalMarket = activeTab === "total_market";
  const currentBrand = (productFilter || appliedBrand || "").toLowerCase();
  const currentPayer = (payerFilter || "").toLowerCase();

  // Which scenarios to overlay on the chart. Mirrors the Compare Scenarios
  // dropdown, which starts fully checked (every available scenario) and is
  // narrowed only once the user unchecks something. Falls back to just the
  // applied scenario if the dropdown is somehow empty.
  const scenarioNamesToShow = selectedCompareScenarios.length
    ? selectedCompareScenarios
    : (appliedScenario ? [appliedScenario] : []);

  let filteredSeries;
  if (isTotalMarket) {
    // Total Market Volume's `series` is built differently upstream
    // (normalizeLiverResponse): it already contains one entry PER SCENARIO,
    // where each item's `label` IS the scenario name — there's no separate
    // product/payer dimension on this tab. So filter it directly against
    // the Compare Scenarios selection here, rather than going through
    // chartData.scenarioSeries (which is shaped for per-product/payer
    // overlay on the other tabs and can come back empty/mismatched for
    // this tab, silently falling back to showing every scenario
    // regardless of what's checked).
    const tmvFiltered = series.filter((s) =>
      scenarioNamesToShow.includes(s.label || ""),
    );
    filteredSeries = (tmvFiltered.length ? tmvFiltered : series).map((s) => ({
      ...s,
      scenario: s.label,
    }));
  } else {
    // Overlay every selected scenario's own series for the CURRENT tab,
    // read directly from the raw per-scenario API data — the same pattern
    // used for the table's scenario overlay. This mirrors HIV's Market
    // Analysis chart, which always overlays the selected scenarios
    // regardless of which tab is active, instead of requiring a
    // product/payer to be focused first.
    const backendTabKey = TAB_KEY_MAP[activeTab] || activeTab;
    const toNums = (v) => (Array.isArray(v) ? v.map((x) => (x == null ? null : Number(x))) : []);

    // Comparison scenarios are pulled from raw, unfiltered per-scenario API
    // data — clip them down to the currently selected From/To date window
    // so they don't extend beyond what the user actually filtered to. The
    // applied scenario's own chartData.series is already date-filtered by
    // the backend from the same apply-filters request, so it needs no
    // clipping.
    const clipToFilterRange = (rawMonths, rawFsi, rawTrain, rawForecast) => {
      if (!filterFromYM && !filterToYM) {
        return { months: rawMonths, fsi: rawFsi, train: rawTrain, forecast: rawForecast };
      }
      const normYM = (m) => {
        const d = dayjs(m, DATE_INPUT_FORMATS, true);
        return d.isValid() ? d.format("YYYY-MM") : m;
      };
      const combined = rawMonths.map((m, i) => (i < rawFsi ? rawTrain[i] : rawForecast[i - rawFsi]));
      const keptIdx = [];
      rawMonths.forEach((m, i) => {
        const ym = normYM(m);
        if (filterFromYM && ym < filterFromYM) return;
        if (filterToYM && ym > filterToYM) return;
        keptIdx.push(i);
      });
      const months = keptIdx.map((i) => rawMonths[i]);
      const combinedClipped = keptIdx.map((i) => combined[i]);
      const fsi = keptIdx.filter((i) => i < rawFsi).length;
      return {
        months,
        fsi,
        train: combinedClipped.slice(0, fsi),
        forecast: combinedClipped.slice(fsi),
      };
    };

    const overlaySeries = rawScenariosData
      ? scenarioNamesToShow.flatMap((name) => {
        const tabObj = rawScenariosData[name]?.market_analysis?.[backendTabKey];
        if (!tabObj) return [];
        const metricObj =
          tabObj[activeMetricKey] ||
          tabObj.payer_volume ||
          tabObj.payer_share ||
          Object.values(tabObj)[0];
        const rawChart =
          viewMode === "yearly"
            ? (metricObj?.yearly?.chart || metricObj?.monthly?.chart || metricObj?.chart)
            : (metricObj?.monthly?.chart || metricObj?.chart);
        let seriesList = rawChart?.series;
        let seriesMonths = rawChart?.months || [];
        let seriesFsi = rawChart?.forecast_start_index != null ? rawChart.forecast_start_index : 0;

        // The backend's chart.series can exist but be only PARTIALLY
        // populated — some entities get real history/forecast arrays,
        // others come back as empty stub entries (e.g. only one
        // payer/product combo has real numbers, its siblings are blank).
        // Drop those empty entries, then fill in whatever's missing — by
        // label — from the table's own rows/children, which reliably has
        // complete data for every entity (same source the table view
        // already renders correctly).
        const hasRealValues = (s) => {
          const h = s?.history || s?.train_values || [];
          const f = s?.forecast || s?.forecast_values || [];
          return h.some((v) => v != null) || f.some((v) => v != null);
        };
        seriesList = (seriesList || []).filter(hasRealValues);

        const rawTable =
          viewMode === "yearly"
            ? (metricObj?.yearly?.table || metricObj?.monthly?.table || metricObj?.table)
            : (metricObj?.monthly?.table || metricObj?.table);
        const tableRows = rawTable?.rows || [];
        if (tableRows.length) {
          seriesMonths = seriesMonths.length ? seriesMonths : rawTable?.headers || [];
          const existingLabels = new Set(seriesList.map((s) => s.label));
          tableRows.forEach((r) => {
            const parentLabel = r.label || r.hierarchy || "";
            if (r.children?.length) {
              r.children.forEach((c) => {
                const label = `${parentLabel} - ${c.label || ""}`;
                if (existingLabels.has(label)) return;
                seriesList.push({
                  label,
                  history: (c.values || []).slice(0, seriesFsi),
                  forecast: (c.values || []).slice(seriesFsi),
                });
              });
            } else if (parentLabel && !existingLabels.has(parentLabel)) {
              const vals = r.values || r.total || [];
              seriesList.push({
                label: parentLabel,
                history: vals.slice(0, seriesFsi),
                forecast: vals.slice(seriesFsi),
              });
            }
          });
        }

        if (!seriesList?.length) return [];
        return seriesList.map((s) => {
          const rawTrain = toNums(s.history || s.train_values);
          const rawForecast = toNums(s.forecast || s.forecast_values);
          const clipped = clipToFilterRange(seriesMonths, seriesFsi, rawTrain, rawForecast);
          return {
            label: s.label || "",
            train_values: clipped.train,
            forecast_values: clipped.forecast,
            scenario: name,
            // This scenario's OWN months/forecast start, clipped to the
            // current filter — a comparison scenario can have a wider raw
            // date range than what's currently selected.
            months: clipped.months.length ? clipped.months : null,
            forecastStartIndex: clipped.months.length ? clipped.fsi : null,
          };
        });
      })
      : null;
    filteredSeries = overlaySeries && overlaySeries.length ? overlaySeries : series;
  }

  // When a specific product/payer is focused via the page filters, narrow
  // the chart down to ONLY that entity's comparison across the selected
  // scenarios — hiding every other, unrelated entity's line. Doesn't apply
  // to Total Market Volume, which has no product/payer dimension.
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

  // Stable per-scenario color map for filter-focus mode: built from the
  // full scenario list (not the narrowed filteredSeries), so a given
  // scenario keeps the same color regardless of which product/payer is
  // currently focused.
  const focusModeScenarioColorMap = {};
  (compareScenarioOptions.length ? compareScenarioOptions : scenarioNamesToShow).forEach(
    (name, i) => {
      focusModeScenarioColorMap[name] = SCENARIO_COLORS[i % SCENARIO_COLORS.length];
    },
  );

  // Mirrors HIV's getSeriesColor (HIVMarketChart.jsx): Total Market colors
  // by index into the SCENARIO_COLORS palette; the other tabs color by
  // identity instead of array position, so the same product/payer always
  // gets the same color. On the two cross tabs (Payer-Product,
  // Product-Payer) HIV colors by the CHILD dimension specifically
  // (market_product colors by product, product_market colors by market) —
  // mirrored here the same way. HIV hardcodes a small known set of names
  // (Biktarvy, Retail, ...); HCV's products/payers are dynamic, so instead
  // of a hardcoded map, colors are assigned to whichever distinct
  // identities are actually present, in order of first appearance.
  const buildIdentityColorMap = (labels) => {
    const map = {};
    let i = 0;
    labels.forEach((label) => {
      if (!label || map[label] != null) return;
      map[label] = SCENARIO_COLORS[i % SCENARIO_COLORS.length];
      i += 1;
    });
    return map;
  };
  const childLabelOf = (label) =>
    label.includes(" - ") ? label.split(" - ").slice(1).join(" - ").trim() : label;

  const flatLabelColorMap = buildIdentityColorMap(series.map((s) => s.label || ""));
  const childLabelColorMap = buildIdentityColorMap(
    series.map((s) => childLabelOf(s.label || "")),
  );

  const getSeriesColor = (item, index) => {
    const label = item.label || "";
    switch (activeTab) {
      case "total_market":
        return SCENARIO_COLORS[index % SCENARIO_COLORS.length];
      case "prod_dist":
      case "payer_dist":
        return flatLabelColorMap[label] || NEUTRAL_COLOR;
      case "payer_prod":
      case "prod_payer":
        return childLabelColorMap[childLabelOf(label)] || NEUTRAL_COLOR;
      default:
        return "#2563EB";
    }
  };

  const traces = filteredSeries.flatMap((s, idx) => {
    const seriesLabel = (s.label || "").toLowerCase();

    // Highlight the line(s) belonging to the currently applied scenario;
    // when a specific product/payer is focused, only highlight that one.
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

    // Selected trace stays amber; every other trace uses HIV's identity/
    // index-based color scheme above. In filter-focus mode, every visible
    // trace already matches the focused product/payer (everything else was
    // filtered out above) — color each one by its own scenario instead, so
    // the different scenarios being compared are distinguishable, while
    // still keeping the applied scenario's line amber.
    const color = isFilterFocusMode
      ? isSelectedTrace
        ? "#f59e0b"
        : focusModeScenarioColorMap[s.scenario] || SCENARIO_COLORS[idx % SCENARIO_COLORS.length]
      : isSelectedTrace
        ? "#f59e0b"
        : getSeriesColor(s, idx);

    // Suffix the scenario name onto the legend label when overlaying more
    // than one scenario, so e.g. "Biktarvy (Base Case)" vs "Biktarvy (High
    // Growth)" are distinguishable — same convention as HIV's chart.
    const name =
      s.scenario && s.scenario !== s.label
        ? `${s.label} (${s.scenario})`
        : s.label;

    // Use this trace's own months/forecast-start if it carries them (a
    // comparison scenario with a different date range than the currently
    // active one) — otherwise fall back to the shared active-scenario axis.
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

  const allTraces = traces;

  return (
    <Box sx={{ width: "100%", height: 380 }}>
      <PlotComponent
        data={allTraces}
        layout={{
          autosize: true,
          height: 380,
          margin: { l: 50, r: 30, t: 8, b: 120 },
          // Plotly truncates hover trace names to 15 characters by
          // default (hoverlabel.namelength) — long names like "PayerA -
          // ProductB (Scenario Name)" on the combo tabs were getting cut
          // off. -1 disables truncation entirely.
          hoverlabel: {
            namelength: -1,
          },
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
};

export default ForecastChart;
