​import React, { useState, useEffect, useContext, useMemo, useRef } from "react";
import {
  Box,
  Paper,
  Typography,
  FormControl,
  Select,
  MenuItem,
  Checkbox,
  ListItemText,
  OutlinedInput,
  TextField,
  Button,
  ToggleButton,
  ToggleButtonGroup,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
import Plot from "react-plotly.js";
const PlotComponent = Plot.default || Plot;
import { GlobalContext } from "../../../context/Provider";
import {
  getLiverFilters,
  applyLiverFilters,
  recalculateLiver,
  saveLiverScenario,
  updateLiverScenario,
  refreshLiverTable,
  getMetricFilters,
  applyMetricFilters,
  recalculateMetrics,
  saveScenario,
  updateScenario,
  getConfigurationByTherapyAreaHCV,
  activateLiverScenario,
} from "../../../services/apiService";
import { useSnackbarStore, useLoadingStore } from "../../../stores";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import DownloadIcon from "@mui/icons-material/Download";
import RefreshIcon from "@mui/icons-material/Refresh";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import Tooltip from "@mui/material/Tooltip";
import dayjs from "dayjs";

// ─── Constants ────────────────────────────────────────────────────────────────
const TABS = [
  { label: "Total Market Volume", value: "total_market" },
  { label: "Product Distribution (%)", value: "prod_dist" },
  { label: "Payer Distribution (%)", value: "payer_dist" },
  { label: "Payer-Product", value: "payer_prod" },
  { label: "Product-Payer", value: "prod_payer" },
];

const TAB_KEY_MAP = {
  total_market: "total_market_volume",
  prod_dist: "product_distribution",
  payer_dist: "payer_distribution",
  payer_prod: "payer_product",
  prod_payer: "product_payer",
};

const COMPARE_OPTIONS = ["ETS 13M", "ETS 26M", "Exponential"];
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
  userHasCustomizedCompare = false,
  compareScenarioOptions = [],
  rawScenariosData,
  activeMetricKey,
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

    const overlaySeries = rawScenariosData
      ? scenarioNamesToShow.flatMap((name) => {
        const tabObj = rawScenariosData[name]?.market_analysis?.[backendTabKey];
        if (!tabObj) return [];
        const metricObj =
          tabObj[activeMetricKey] ||
          tabObj.payer_volume ||
          tabObj.payer_share ||
          Object.values(tabObj)[0];
        const rawChart = metricObj?.monthly?.chart || metricObj?.chart;
        if (!rawChart?.series?.length) return [];
        return rawChart.series.map((s) => ({
          label: s.label || "",
          train_values: toNums(s.history || s.train_values),
          forecast_values: toNums(s.forecast || s.forecast_values),
          scenario: name,
          // This scenario's OWN months/forecast start — a newly created
          // scenario can have a different date range than the currently
          // active one, so its values must be plotted against its own
          // dates, not blanket-applied to the active scenario's x-axis.
          months: rawChart.months || null,
          forecastStartIndex:
            rawChart.forecast_start_index != null ? rawChart.forecast_start_index : null,
        }));
      })
      : null;
    filteredSeries = overlaySeries && overlaySeries.length ? overlaySeries : series;
  }

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
    // index-based color scheme above.
    const color = isSelectedTrace ? "#f59e0b" : getSeriesColor(s, idx);

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

// ─── Main Component ───────────────────────────────────────────────────────────
export default function PBCModelInput() {
  const { showSnackbar } = useSnackbarStore();
  const { setLoading } = useLoadingStore();
  const { favState } = useContext(GlobalContext);
  const therapyArea = favState?.selectedTherapyArea;
  const isHCV = therapyArea && therapyArea.toLowerCase() === "hcv";

  // ── State ─────────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState("total_market");
  const [scenarioSelector, setScenarioSelector] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [payerFilter, setPayerFilter] = useState("");
  const [productFilter, setProductFilter] = useState("");
  const [metric, setMetric] = useState("market_volume");
  const [availableDates, setAvailableDates] = useState([]);
  const [chartData, setChartData] = useState(null);
  const [tableData, setTableData] = useState([]);
  const [allMetricsData, setAllMetricsData] = useState({});
  const [appliedLot, setAppliedLot] = useState("");
  const [appliedBrand, setAppliedBrand] = useState("");
  // Separate "applied" payer/product — only updated when the user
  // explicitly clicks Apply Filter. These drive the table highlighting so
  // changing the dropdown alone doesn't visually shift which row is amber.
  const [appliedPayerFilter, setAppliedPayerFilter] = useState("");
  const [appliedProductFilter, setAppliedProductFilter] = useState("");
  // Save Scenario modal
  const [saveScenarioDialogOpen, setSaveScenarioDialogOpen] = useState(false);
  const [newScenarioName, setNewScenarioName] = useState("");
  // Scenarios saved this session — shown as selectable rows in the table
  // below the live data rows. Radio becomes active immediately on save,
  // but chart/table data only reloads when Apply Selected Scenario is clicked.
  const [savedScenarioRows, setSavedScenarioRows] = useState([]);
  const [liverTabsRaw, setLiverTabsRaw] = useState(null);
  // Raw, untransformed backend response (the one passed into
  // normalizeLiverResponse). Cached so switching tabs/metric can re-derive
  // liverTabsRaw locally instead of re-hitting the API every time.
  const [liverRawData, setLiverRawData] = useState(null);
  const [editable, setEditable] = useState(false);
  const [modelSelection, setModelSelection] = useState("ets");
  const [allFactors, setAllFactors] = useState({});
  const [alpha, setAlpha] = useState(0);
  const [beta, setBeta] = useState(0);
  const [gamma, setGamma] = useState(0);
  const [totalGrowth, setTotalGrowth] = useState(10);
  const [duration, setDuration] = useState(12);
  const [kValue, setKValue] = useState(1);
  const [windowSize, setWindowSize] = useState(6);
  const [multiplier, setMultiplier] = useState(1.0);
  const [multiplierHorizon, setMultiplierHorizon] = useState("Forecast");
  const [trajectoryStart, setTrajectoryStart] = useState("");
  const [mappingData, setMappingData] = useState({});
  const [filterOptions, setFilterOptions] = useState({
    indications: [],
    metric_filters: [],
    scenario_names: [],
  });
  const [filtersLoaded, setFiltersLoaded] = useState(false);
  const [autoAppliedOnMount, setAutoAppliedOnMount] = useState(false);
  const [payerOptions, setPayerOptions] = useState([]);
  const [productOptions, setProductOptions] = useState([]);
  const [indication, setIndication] = useState("");
  const [lot, setLot] = useState("");
  const [brand, setBrand] = useState("");
  const [totalMarketViewMode, setTotalMarketViewMode] = useState("monthly");
  // All scenario names from the API — shown in the Compare Scenarios dropdown
  const [compareScenarioOptions, setCompareScenarioOptions] = useState([]);
  // Subset the user has chosen to display; empty = show all
  const [selectedCompareScenarios, setSelectedCompareScenarios] = useState([]);
  // True only after the user has manually toggled a checkbox in the Compare
  // Scenarios dropdown. Until then, ALL rows in tableData are shown regardless
  // of selectedCompareScenarios so that initial load / apply-filter always
  // shows every scenario without waiting for state to settle.
  const [userHasCustomizedCompare, setUserHasCustomizedCompare] = useState(false);
  const [tentativeRadioSelectedScenario, setTentativeRadioSelectedScenario] =
    useState("");
  const [currentlyAppliedScenario, setCurrentlyAppliedScenario] = useState("");
  const [expandedBrands, setExpandedBrands] = useState({});
  // Table edit tracking — for refresh-table API
  const [tableEditing, setTableEditing] = useState(false);
  const [tableSnapshot, setTableSnapshot] = useState([]);
  const [editedHierarchies, setEditedHierarchies] = useState({});
  const [savingTable, setSavingTable] = useState(false);
  const [isSavingEditChanges, setIsSavingEditChanges] = useState(false);
  // true only after Refresh succeeds — gates the Save button
  const [isRefreshed, setIsRefreshed] = useState(false);

  // ── Derived ───────────────────────────────────────────────────────────────
  const metricUnit = useMemo(() => {
    if (activeTab === "total_market") return "";
    if (metric === "market_share") return "%";
    if (metric === "market_volume") return "";
    return allMetricsData?.[metric]?.unit || "";
  }, [metric, allMetricsData, activeTab]);

  const isPercentTab = metric === "market_share";
  const activeTabLabel =
    TABS.find((t) => t.value === activeTab)?.label || "Total Market Volume";
  const showScenarioControls = activeTab === "total_market";
  // Compare Scenarios (chart-only comparison) is useful on every tab now
  // that the API sends per-scenario chart data for all of them — gated
  // only on there being more than one scenario to compare, not the tab.
  const showCompareScenarios = compareScenarioOptions.length > 1;
  const showMetricFilter = activeTab !== "total_market";
  const trajectoryMonthOptions =
    chartData?.months?.slice(chartData?.forecast_start_index) || [];

  // ── Styles ────────────────────────────────────────────────────────────────
  const inputStyle = {
    bgcolor: "#fcfcfd",
    borderRadius: "8px",
    minWidth: "160px",
    "& .MuiOutlinedInput-root": {
      borderRadius: "8px",
      height: "35px",
      backgroundColor: "#fcfcfd",
    },
  };
  const recalculateInputStyle = {
    bgcolor: "#fcfcfd",
    borderRadius: "8px",
    minWidth: "100px",
    "& .MuiOutlinedInput-root": {
      borderRadius: "8px",
      height: "35px",
      backgroundColor: "#fcfcfd",
    },
  };

  // ── Date helpers ──────────────────────────────────────────────────────────
  const parseDateString = (s) => {
    if (!s) return dayjs.invalid();
    const strict = dayjs(s, DATE_INPUT_FORMATS, true);
    if (strict.isValid()) return strict;
    const relaxed = dayjs(s);
    return relaxed.isValid() ? relaxed : dayjs.invalid();
  };
  const formatDateLabel = (s) => {
    const p = parseDateString(s);
    return p.isValid() ? p.format("MMM-YY") : s || "";
  };
  const toYearMonth = (s) => {
    const p = parseDateString(s);
    return p.isValid() ? p.format("YYYY-MM") : s || "";
  };
  const resolveFromDate = () => {
    if (fromDate) return toYearMonth(fromDate);
    if (availableDates?.length) return toYearMonth(availableDates[0]);
    return "";
  };

  // ── Factor sync ───────────────────────────────────────────────────────────
  const syncFactors = (factors, activeModel) => {
    setAllFactors(factors);
    setMultiplier(factors?.multiplier ?? 1);
    setMultiplierHorizon(factors?.multiplier_horizon ?? "Forecast");
    if (activeModel === "ets") {
      const ets = factors?.ets || {};
      setAlpha(ets.alpha ?? 0);
      setBeta(ets.beta ?? 0);
      setGamma(ets.gamma ?? 0);
    } else {
      const traj = factors?.growth || factors?.[activeModel] || {};
      setTotalGrowth(traj?.total_growth ?? traj?.total_growth_pct ?? 0);
      setDuration(traj?.duration ?? 12);
      setTrajectoryStart(traj?.trajectory_start || "");
      setKValue(traj?.k_value ?? traj?.k ?? 1);
    }
  };

  const syncMetrics = (metricsData, metricKey) => {
    setAllMetricsData(metricsData || {});
    const selected = metricsData?.[metricKey];
    setChartData(selected?.chart || null);
    setTableData(selected?.table || []);
  };

  // The API nests each tab's data under "payer_volume" / "payer_share"
  // (previously "market_volume" / "market_share"). The UI's internal
  // `metric` state still uses the old "market_volume"/"market_share"
  // values (for labels/units), so translate before indexing into
  // anything that came from or is going back to the backend.
  const toApiMetricKey = (m) => (m === "market_share" ? "payer_share" : "payer_volume");

  // ── HCV tab mapper ────────────────────────────────────────────────────────
  function normalizeLiverResponse(data, currentMetric) {
    if (!data) return { months: [], forecast_start_index: 0, tabs: {} };
    if (!currentMetric) currentMetric = metric;

    if (data.months || data.tabs) {
      return {
        months: data.months || [],
        forecast_start_index: data.forecast_start_index || 0,
        tabs: data.tabs || {},
      };
    }

    const active =
      data.active_scenario ||
      (data.scenarios && Object.keys(data.scenarios || {})[0]);
    const sc = data.scenarios && data.scenarios[active];
    const ma = sc && sc.market_analysis;

    // The active scenario (e.g. a newly saved one) may only carry table data
    // and no chart. Fall back to the first scenario that has chart data so
    // the chart is never left empty after a save-scenario response.
    const hasChart = (scenarioData) => {
      const tmv = scenarioData?.market_analysis?.total_market_volume;
      const mv = tmv?.payer_volume || tmv?.payer_share || Object.values(tmv || {})[0];
      // Support both old shape (mv.chart) and new shape (mv.monthly.chart)
      return !!(mv?.monthly?.chart?.months?.length || mv?.chart?.months?.length);
    };
    let chartMa = ma; // preferred: active scenario
    if (!hasChart(sc) && data.scenarios) {
      // Try Base first, then any other scenario that has chart data
      const fallbackKey =
        (data.scenarios["Base"] && hasChart(data.scenarios["Base"]) ? "Base" : null) ||
        Object.keys(data.scenarios).find((k) => hasChart(data.scenarios[k]));
      if (fallbackKey) {
        chartMa = data.scenarios[fallbackKey]?.market_analysis;
      }
    }

    if (!ma && !chartMa) return { months: [], forecast_start_index: 0, tabs: {} };

    const parseNumber = (x, asPercent = false) => {
      if (x == null || x === "") return null;
      const n = Number(x);
      if (Number.isNaN(n)) return null;
      
      return n;
    };
    const parseValues = (v, asPercent = false) => {
      if (v == null) return [];
      if (Array.isArray(v))
        return v.map((x) => (x === null ? null : parseNumber(x, asPercent)));
      if (typeof v === "string")
        return v
          .split(/\s+/)
          .filter(Boolean)
          .map((x) => parseNumber(x, asPercent));
      return [];
    };

    // Use chartMa (the scenario with actual chart data) to derive months and
    // forecast_start_index. Use ma (active scenario) for table data when available.
    // New API structure: metric.monthly.chart / metric.monthly.table / metric.yearly.*
    const effectiveMa = ma || chartMa;
    const firstTab = chartMa
      ? (chartMa.total_market_volume || chartMa[Object.keys(chartMa)[0]])
      : (effectiveMa.total_market_volume || effectiveMa[Object.keys(effectiveMa)[0]]);
    const firstMetric =
      firstTab &&
      (firstTab.payer_volume ||
        firstTab.payer_share ||
        Object.values(firstTab)[0]);

    // Support both old shape (metric.chart) and new shape (metric.monthly.chart)
    const getMonthlyChart = (metric) => metric?.monthly?.chart || metric?.chart || null;
    const getMonthlyTable = (metric) => metric?.monthly?.table || metric?.table || null;
    const getYearlyChart = (metric) => metric?.yearly?.chart || null;
    const getYearlyTable = (metric) => metric?.yearly?.table || null;

    const months =
      (firstMetric && getMonthlyChart(firstMetric)?.months) || [];
    const fsi =
      (firstMetric && getMonthlyChart(firstMetric)?.forecast_start_index) || 0;

    const selectMetricForTab = (tabKey, tabObj) => {
      // Force "payer_volume" if the context tab is total_market_volume
      if (tabKey === "total_market_volume") {
        return tabObj.payer_volume || Object.values(tabObj)[0];
      }

      const apiMetricKey = currentMetric ? toApiMetricKey(currentMetric) : null;
      if (apiMetricKey && tabObj[apiMetricKey]) {
        return tabObj[apiMetricKey];
      }
      const isVolumeTab =
        tabKey === "payer_product" || tabKey === "product_payer";
      const isDefaultShareTab =
        tabKey === "product_distribution" || tabKey === "payer_distribution";

      if (isVolumeTab)
        return (
          tabObj.payer_volume ||
          tabObj.payer_share ||
          Object.values(tabObj)[0]
        );
      if (isDefaultShareTab)
        return (
          tabObj.payer_share ||
          tabObj.payer_volume ||
          Object.values(tabObj)[0]
        );
      return (
        tabObj.payer_volume || tabObj.payer_share || Object.values(tabObj)[0]
      );
    };

    // Helper to parse a chart object (monthly or yearly) into our internal format
    const parseChartObj = (rawChart, fallbackMonths, fallbackFsi, asPercent) => {
      if (!rawChart) return { months: fallbackMonths, forecast_start_index: fallbackFsi, series: [] };
      return {
        months: rawChart.months || fallbackMonths,
        forecast_start_index: rawChart.forecast_start_index ?? fallbackFsi,
        series: (rawChart.series || []).map((s) => ({
          label: s.label || "",
          train_values: parseValues(s.history || s.train_values, asPercent),
          forecast_values: parseValues(s.forecast || s.forecast_values, asPercent),
          lot: s.lot || s.label || "",
        })),
      };
    };

    // Helper to parse a table object into our internal format
    const parseTableObj = (rawTable, fallbackMonths, asPercent) => {
      if (!rawTable) return { type: "flat", headers: fallbackMonths, rows: [] };
      return {
        type: rawTable.type,
        headers: rawTable.headers || fallbackMonths,
        rows: (rawTable.rows || []).map((r) => ({
          hierarchy: r.hierarchy || r.label || "",
          label: r.label || r.hierarchy || "",
          total: Array.isArray(r.total) ? parseValues(r.total, asPercent) : undefined,
          values: parseValues(r.values, asPercent),
          children: (r.children || []).map((c) => ({
            label: c.label,
            values: parseValues(c.values, asPercent),
          })),
        })),
      };
    };

    // Build tabs using chart data from chartMa and table data from ma.
    // The union of keys from both ensures we cover all tabs.
    const allTabKeys = new Set([
      ...Object.keys(chartMa || {}),
      ...Object.keys(ma || {}),
    ]);
    const tabs = {};
    allTabKeys.forEach((tabKey) => {
      // Chart source: prefer chartMa (scenario with full chart data)
      const chartTabObj = (chartMa || {})[tabKey] || {};
      const chartSelectedMetric = selectMetricForTab(tabKey, chartTabObj);
      const isTabPercent = chartSelectedMetric === chartTabObj.payer_share;

      // Table source: prefer active scenario (ma), fall back to chartMa
      const tableTabObj = (ma || {})[tabKey] || chartTabObj;
      const tableSelectedMetric = selectMetricForTab(tabKey, tableTabObj);

      // Monthly data (used for chart and monthly table)
      const rawMonthlyChart = getMonthlyChart(chartSelectedMetric);
      const rawMonthlyTable = getMonthlyTable(tableSelectedMetric);

      // Yearly data (pre-computed by backend, used for yearly table/chart)
      const rawYearlyChart = getYearlyChart(chartSelectedMetric);
      const rawYearlyTable = getYearlyTable(tableSelectedMetric);

      const chart = parseChartObj(rawMonthlyChart, months, fsi, isTabPercent);
      const table = parseTableObj(rawMonthlyTable, chart.months, isTabPercent);
      const yearlyChart = rawYearlyChart ? parseChartObj(rawYearlyChart, [], 0, isTabPercent) : null;
      const yearlyTable = rawYearlyTable ? parseTableObj(rawYearlyTable, yearlyChart?.months || [], isTabPercent) : null;

      tabs[tabKey] = { chart, table, yearlyChart, yearlyTable };

      // Per-scenario series map for this tab — powers Compare Scenarios on
      // the chart for every tab. Each entry is the full series list (e.g.
      // one entry per product/payer) as it appears in that scenario's own
      // chart data, so the chart can show the same product/payer line
      // across multiple scenarios instead of only the active one.
      if (data.scenarios) {
        const scenarioSeries = {};
        Object.keys(data.scenarios).forEach((scenarioName) => {
          const scenarioTabObj =
            data.scenarios[scenarioName]?.market_analysis?.[tabKey];
          if (!scenarioTabObj) return;
          const scenarioSelectedMetric = selectMetricForTab(tabKey, scenarioTabObj);
          const scenarioIsPercent =
            scenarioSelectedMetric === scenarioTabObj.payer_share;
          const scenarioRawChart = getMonthlyChart(scenarioSelectedMetric);
          if (!scenarioRawChart) return;
          const scenarioParsed = parseChartObj(
            scenarioRawChart,
            months,
            fsi,
            scenarioIsPercent,
          );
          if (scenarioParsed.series?.length) {
            scenarioSeries[scenarioName] = scenarioParsed.series;
          }
        });
        if (Object.keys(scenarioSeries).length) {
          tabs[tabKey].scenarioSeries = scenarioSeries;
        }
      }
    });

    // ── Multi-scenario table rows for Total Market Volume ──────────────────
    // Only include scenarios that have real table values. Scenarios like s03/s02
    // that return empty market_analysis are skipped — they have no data to show.
    // The hierarchy key is always the scenario name (not the row label inside
    // the response, which may say "Base" for all of them).
    if (data.scenarios && Object.keys(data.scenarios).length > 0) {
      const tmvTab = tabs["total_market_volume"];
      if (tmvTab) {
        // Use available_scenarios ordering when present, fall back to object keys
        const allScenarioNames =
          Array.isArray(data.available_scenarios) && data.available_scenarios.length
            ? data.available_scenarios
            : Object.keys(data.scenarios);

        const scenarioRows = [];
        allScenarioNames.forEach((scenarioName) => {
          const scenarioData = data.scenarios[scenarioName];
          const tmv = scenarioData?.market_analysis?.total_market_volume;
          const metricObj = tmv
            ? (tmv.payer_volume || tmv.payer_share || Object.values(tmv)[0])
            : null;
          if (!metricObj) return; // no data at all — skip this scenario
          // Support both old shape (metricObj.table) and new shape (metricObj.monthly.table)
          const rawRows = metricObj?.monthly?.table?.rows || metricObj?.table?.rows || [];
          const firstRow = rawRows[0];
          if (!firstRow) return; // empty table — skip this scenario
          const vals = parseValues(firstRow.values, false);
          if (!vals.length) return; // no actual values — skip
          scenarioRows.push({
            hierarchy: scenarioName,
            label: scenarioName,
            total: undefined,
            values: vals,
            children: [],
          });
        });

        if (scenarioRows.length) {
          const tmvChart = tmvTab.chart || { months, forecast_start_index: fsi, series: [] };
          const chartFsi = tmvChart.forecast_start_index ?? fsi;

          // Build yearly scenario rows — only for scenarios that have yearly data.
          const yearlyScenarioRows = [];
          allScenarioNames.forEach((scenarioName) => {
            const scenarioData = data.scenarios[scenarioName];
            const tmv = scenarioData?.market_analysis?.total_market_volume;
            const metricObj = tmv
              ? (tmv.payer_volume || tmv.payer_share || Object.values(tmv)[0])
              : null;
            if (!metricObj) return;
            const yearlyRows = metricObj?.yearly?.table?.rows || [];
            const firstYearlyRow = yearlyRows[0];
            if (!firstYearlyRow) return;
            const yearlyVals = parseValues(firstYearlyRow.values, false);
            if (!yearlyVals.length) return;
            yearlyScenarioRows.push({
              hierarchy: scenarioName,
              label: scenarioName,
              total: undefined,
              values: yearlyVals,
              children: [],
            });
          });

          // Yearly chart months (for building yearly table headers)
          const yearlyChartMonths = tmvTab.yearlyChart?.months || [];

          // Chart shows one line per scenario so the Compare Scenarios
          // dropdown can render multiple scenarios at once. Filtering to
          // only the checked scenarios (and highlighting the currently
          // applied one) happens at render time in ForecastChart — mirrors
          // how the table filters scenarioRows via selectedCompareScenarios.
          const allScenarioChartSeries = scenarioRows.map((row) => ({
            label: row.hierarchy || row.label || "",
            lot: row.hierarchy || row.label || "",
            train_values: (row.values || []).slice(0, chartFsi),
            forecast_values: (row.values || []).slice(chartFsi),
          }));

          const singleChartSeries = allScenarioChartSeries.length
            ? allScenarioChartSeries
            : tmvChart.series;

          tabs["total_market_volume"] = {
            ...tmvTab,
            chart: {
              ...tmvChart,
              series: singleChartSeries,
            },
            table: {
              ...tmvTab.table,
              rows: scenarioRows,
            },
            // Replace yearlyTable rows with all-scenario yearly rows so the
            // yearly view also shows every scenario, not just the active one.
            yearlyTable: yearlyScenarioRows.length
              ? {
                ...(tmvTab.yearlyTable || { type: "flat", headers: yearlyChartMonths }),
                rows: yearlyScenarioRows,
              }
              : tmvTab.yearlyTable,
          };
        }
      }
    }

    return { months, forecast_start_index: fsi, tabs };
  }

  // Maps the response of POST /api/liver/refresh into chart + table for the
  // currently active tab. The refresh API returns the same full scenarios
  // payload as apply-filters, so we reuse normalizeLiverResponse + mapLiverTabToView.
  // Falls back to a flat-shape parser if the response doesn't include scenarios.
  const mapRefreshTableResponse = (data) => {
    if (!data) return { chart: null, table: [] };

    // Full scenarios payload (same shape as apply-filters response)
    if (data.scenarios || data.active_scenario) {
      const normalized = normalizeLiverResponse(data, metric);
      // Update liverRawData so subsequent tab switches use the refreshed data
      setLiverRawData(data);
      return mapLiverTabToView(normalized, activeTab, totalMarketViewMode);
    }

    // Fallback: flat shape { chart, table } — handle gracefully
    const months = data?.chart?.months || chartData?.months || [];
    const fsi =
      data?.chart?.forecast_start_index ??
      chartData?.forecast_start_index ??
      0;

    const series = (data?.chart?.series || []).map((s) => ({
      label: s.label || "",
      lot: s.label || "",
      train_values: Array.isArray(s.history) ? s.history : [],
      forecast_values: Array.isArray(s.forecast) ? s.forecast : [],
    }));

    const table = (data?.table?.rows || []).map((r) => {
      const monthly_data = {};
      months.forEach((m, i) => {
        const v = r.values?.[i];
        monthly_data[m] = v == null ? null : Number(v);
      });
      return {
        hierarchy: r.label || r.hierarchy || "",
        monthly_data,
        is_applied: !!r.is_applied,
      };
    });

    return {
      chart: { months, forecast_start_index: fsi, series },
      table,
    };
  };

  const mapLiverTabToView = (tabsPayload, uiTabKey, viewMode = "monthly") => {
    if (!tabsPayload) return { chart: null, table: [] };
    const {
      months = [],
      forecast_start_index: fsi = 0,
      tabs = {},
    } = tabsPayload;
    const backendKey = TAB_KEY_MAP[uiTabKey] || uiTabKey;
    const tab = tabs[backendKey] || tabs[Object.keys(tabs)[0]] || null;
    if (!tab)
      return {
        chart: { months, forecast_start_index: fsi, series: [] },
        table: [],
      };

    // Chart always uses monthly data (time-series visualization).
    // Table uses yearly backend data when in yearly mode (pre-computed by API).
    const activeTableData = (viewMode === "yearly" && tab.yearlyTable) ? tab.yearlyTable : tab.table;

    const series = (tab.chart?.series || [])
      .filter((s) => {
        const lbl = (s.label || "").toLowerCase();
        return (
          !lbl.includes("total") &&
          !lbl.includes("market volume") &&
          !lbl.includes("market share")
        );
      })
      .map((s) => ({
        label: s.label || "",
        lot: s.lot || s.label || "",
        train_values: Array.isArray(s.train_values) ? s.train_values : [],
        forecast_values: Array.isArray(s.forecast_values)
          ? s.forecast_values
          : [],
      }));

    const isAllZeroSeries = (arr) => {
      if (!arr?.length) return true;
      return arr.every((s) => {
        const t = Array.isArray(s.train_values) ? s.train_values : [];
        const f = Array.isArray(s.forecast_values) ? s.forecast_values : [];
        return !(
          t.some((v) => v != null && Number(v) !== 0) ||
          f.some((v) => v != null && Number(v) !== 0)
        );
      });
    };

    if (isAllZeroSeries(series)) {
      const ck = [
        "product_distribution",
        "payer_product",
        "product_payer",
        "payer_distribution",
      ];
      let candidate = null;
      for (const k of ck) {
        if (tabs[k]?.chart?.series?.length) {
          candidate = tabs[k].chart.series;
          break;
        }
      }
      if (candidate) {
        const filteredCandidate = candidate.filter((s) => {
          const lbl = (s.label || "").toLowerCase();
          return (
            !lbl.includes("total") &&
            !lbl.includes("market volume") &&
            !lbl.includes("market share")
          );
        });

        if (filteredCandidate.length) {
          const maxTL = Math.max(
            ...filteredCandidate.map((s) => s.train_values?.length || 0),
            0,
          );
          const maxFL = Math.max(
            ...filteredCandidate.map((s) => s.forecast_values?.length || 0),
            0,
          );
          const sumT = Array.from({ length: maxTL }, (_, i) =>
            filteredCandidate.reduce(
              (a, s) => a + (Number((s.train_values || [])[i]) || 0),
              0,
            ),
          );
          const sumF = Array.from({ length: maxFL }, (_, i) =>
            filteredCandidate.reduce(
              (a, s) => a + (Number((s.forecast_values || [])[i]) || 0),
              0,
            ),
          );
          const lbl = tab.chart?.series?.[0]?.label || "Summary Metrics";
          series.length = 0;
          series.push({
            label: lbl,
            lot: lbl,
            train_values: sumT,
            forecast_values: sumF,
          });
        }
      }
    }

    const headers = activeTableData?.headers || months;
    const mkMonthly = (vals, hdrs) => {
      const obj = {};
      hdrs.forEach((m, i) => {
        const v = vals[i];
        obj[m] = v == null ? null : Number(v);
      });
      return obj;
    };

    const table = [];
    (activeTableData?.rows || []).forEach((r) => {
      if (r && Array.isArray(r.total)) {
        table.push({
          hierarchy: r.hierarchy,
          monthly_data: mkMonthly(r.total, headers),
          is_applied: !!r.is_applied,
        });
        (r.children || []).forEach((c) => {
          table.push({
            hierarchy: `${r.hierarchy} - ${c.label}`,
            monthly_data: mkMonthly(c.values || [], headers),
            is_applied: false,
          });
        });
      } else {
        table.push({
          hierarchy: r.hierarchy,
          monthly_data: mkMonthly(r.values || [], headers),
          is_applied: !!r.is_applied,
        });
        (r.children || []).forEach((c) => {
          table.push({
            hierarchy: `${r.hierarchy} - ${c.label}`,
            monthly_data: mkMonthly(c.values || [], headers),
            is_applied: false,
          });
        });
      }
    });

    return {
      chart: { months, forecast_start_index: fsi, series, scenarioSeries: tab.scenarioSeries || null },
      table,
    };
  };

  // ── Payload builders ──────────────────────────────────────────────────────
  const buildBasePayload = () => ({
    ta_name: therapyArea,
    scenario_name: scenarioSelector,
    indications: indication ? [indication] : [],
    lots: lot ? [lot] : [],
    metric_filter: metric,
    product: metric === "market_share" ? brand : "",
    from_date: fromDate,
    to_date: toDate,
    payer: payerFilter || "",
    product_filter: productFilter || "",
  });

  const buildFullFactors = () => ({
    multiplier,
    multiplier_horizon: multiplierHorizon,
    ets: { alpha, beta, gamma },
    linear: {
      total_growth: totalGrowth,
      duration,
      trajectory_start: trajectoryStart,
      k_value: Number(kValue),
    },
    exponential: {
      total_growth: totalGrowth,
      duration,
      trajectory_start: trajectoryStart,
      k_value: Number(kValue),
    },
    logarithmic: {
      total_growth: totalGrowth,
      duration,
      trajectory_start: trajectoryStart,
      k_value: Number(kValue),
    },
    scurve: {
      total_growth: totalGrowth,
      duration,
      trajectory_start: trajectoryStart,
      k_value: Number(kValue),
    },
    growth: {
      total_growth: totalGrowth,
      duration,
      trajectory_start: trajectoryStart,
      k_value: Number(kValue),
    },
    moving_average: {
      window: Math.max(3, Number(windowSize)),
    },
    active_model: modelSelection,
  });

  const buildLiverRecalculatePayload = () => ({
    ta_name: therapyArea || "HCV",
    selected_filter: {
      market: payerFilter || getFirstOption(payerOptions),
      product: productFilter || getFirstOption(productOptions),
      start_date: resolveFromDate(),
      end_date: toDate || "",
    },
    scenario_name:currentlyAppliedScenario || scenarioSelector || "Base",
    model_type: modelSelection,
    factors: buildFullFactors(),
    selected_tab: TAB_KEY_MAP[activeTab] || activeTab,
  });

  const getFirstOption = (opts) => {
    if (!opts?.length) return "";
    const first = opts[0];
    return typeof first === "string"
      ? first
      : first?.value || first?.name || "";
  };

  const buildLiverBasePayload = () => ({
    ta: therapyArea || "HCV",
    payer: payerFilter
      ? [payerFilter]
      : payerOptions?.length
        ? [getFirstOption(payerOptions)]
        : [],
    brand: productFilter
      ? [productFilter]
      : productOptions?.length
        ? [getFirstOption(productOptions)]
        : [],
    product: productFilter || getFirstOption(productOptions),
    metric: metric || "market_volume",
    from_date: resolveFromDate(),
    to_date: toDate || "",
    scenario_name: currentlyAppliedScenario || scenarioSelector || "Base",
  });

  // Build payload for the refresh-table API based on current (edited) table state.
  // Expected shape:
  // {
  //   ta_name, selected_filter: { market, product, start_date, end_date },
  //   scenario_name, selected_tab, selected_metric, edited_hierarchy,
  //   factors, market_analysis
  // }
  const buildRefreshTablePayload = (hierarchyKey) => {
    const sourceScenario =
      currentlyAppliedScenario ||
      scenarioSelector ||
      liverRawData?.active_scenario ||
      (liverRawData?.scenarios ? Object.keys(liverRawData.scenarios)[0] : "Base") ||
      "Base";

    // Resolve full market_analysis for the active scenario
    let fullMarketAnalysis = liverRawData?.scenarios?.[sourceScenario]?.market_analysis || {};
    if (!fullMarketAnalysis && liverRawData?.scenarios) {
      const matchedKey = Object.keys(liverRawData.scenarios).find(
        (k) => k.toLowerCase() === sourceScenario.toLowerCase()
      );
      fullMarketAnalysis = matchedKey
        ? liverRawData.scenarios[matchedKey]?.market_analysis
        : Object.values(liverRawData.scenarios)[0]?.market_analysis;
    }
    fullMarketAnalysis = fullMarketAnalysis || {};

    // The backend expects ALL tabs in market_analysis.
    // Spread fullMarketAnalysis (all tabs) and patch only the active tab's rows.
    const backendTabKey = TAB_KEY_MAP[activeTab] || activeTab;

    // Build the current table values to send as the edited market_analysis.
    // The backend expects the SAME hierarchical structure as the original
    // market_analysis, with edited values patched in.
    //
    // For hierarchical tabs (payer_product, product_payer): rows have children[].
    //   tableData stores these as flat rows: "Payer - Product" hierarchy strings.
    //   We rebuild the hierarchy by looking up the original raw table structure
    //   and patching each row's values from tableData's monthly_data.
    //
    // For flat tabs (total_market_volume, product_distribution, payer_distribution):
    //   rows are flat — we emit them as-is from tableData.
    const months = chartData?.months || [];
    const activeMetric = toApiMetricKey(metric);

    // Helper: extract values array from a row's monthly_data in month order
    const rowToValues = (row) =>
      months.map((m) => {
        const v = row?.monthly_data?.[m];
        return v == null ? 0 : Number(v);
      });

    // Build a lookup map from hierarchy key -> tableData row (for fast access)
    const tableDataMap = {};
    tableData.forEach((row) => {
      tableDataMap[row.hierarchy] = row;
    });

    // Determine if the active tab uses a hierarchical table structure.
    const isHierarchicalTab =
      backendTabKey === "payer_product" || backendTabKey === "product_payer";

    let tableRows;
    if (isHierarchicalTab) {
      // Rebuild hierarchical rows from the original raw table structure,
      // patching in edited values from tableData.
      // The original rows are in liverRawData -> scenarios -> activeScenario
      // -> market_analysis -> [tab] -> [metric] -> monthly -> table -> rows
      const origRows =
        fullMarketAnalysis?.[backendTabKey]?.[activeMetric]?.monthly?.table?.rows ||
        fullMarketAnalysis?.[backendTabKey]?.[activeMetric]?.table?.rows ||
        [];

      tableRows = origRows.map((origRow) => {
        const parentLabel = origRow.label || origRow.hierarchy || "";
        // Parent row: look up edited values from tableData (keyed by parentLabel)
        const parentTableRow = tableDataMap[parentLabel];
        const parentValues = parentTableRow
          ? rowToValues(parentTableRow)
          : (origRow.values || origRow.total || []);

        // Child rows: look up edited values using "Parent - Child" key
        const children = (origRow.children || []).map((origChild) => {
          const childKey = `${parentLabel} - ${origChild.label}`;
          const childTableRow = tableDataMap[childKey];
          return {
            label: origChild.label,
            values: childTableRow
              ? rowToValues(childTableRow)
              : (origChild.values || []),
          };
        });

        const rebuilt = {
          label: parentLabel,
          values: parentValues,
        };
        if (children.length) rebuilt.children = children;
        return rebuilt;
      });
    } else {
      // Flat tabs: emit rows directly from tableData
      tableRows = tableData.map((row) => ({
        label: row.hierarchy,
        values: rowToValues(row),
      }));
    }

    const tableType = isHierarchicalTab ? "hierarchical" : "flat";

    // All tabs in market_analysis; only active tab's monthly table rows patched.
    const mergedMarketAnalysis = {
      ...fullMarketAnalysis,
      [backendTabKey]: {
        ...(fullMarketAnalysis[backendTabKey] || {}),
        [activeMetric]: {
          ...(fullMarketAnalysis[backendTabKey]?.[activeMetric] || {}),
          monthly: {
            ...(fullMarketAnalysis[backendTabKey]?.[activeMetric]?.monthly || {}),
            table: {
              type: tableType,
              rows: tableRows,
            },
          },
        },
      },
    };

    // Send only the active model's factors to keep the payload lean
    const activeFactors = {
      multiplier,
      multiplier_horizon: multiplierHorizon,
      active_model: modelSelection,
      ...(modelSelection === "ets"
        ? { ets: { alpha, beta, gamma } }
        : {
          [modelSelection]: {
            total_growth: totalGrowth,
            duration,
            trajectory_start: trajectoryStart,
            k_value: Number(kValue),
          },
        }),
    };

    // Use the backend's own resolved selected_filter when available —
    // it has the correct train_start_date and end_date that _resolve_forecast_periods needs.
    const backendSf = liverRawData?.selected_filter || {};

    const endDate = backendSf.end_date || toDate || "";
    const startDate = backendSf.start_date || resolveFromDate();
    const forecastPeriods = chartData?.months?.length
      ? chartData.months.length - (chartData.forecast_start_index ?? 0)
      : 0;

    return {
      ta_name: therapyArea || "HCV",
      selected_filter: {
        market: backendSf.payer || appliedPayerFilter || payerFilter || getFirstOption(payerOptions) || "",
        product: backendSf.product || appliedProductFilter || productFilter || getFirstOption(productOptions) || "",
        start_date: startDate,
        end_date: endDate,
      },
      // Provide the exact positional arg names that _resolve_forecast_periods() expects
      train_end_month: endDate,
      cfg_periods: forecastPeriods,
      // Also keep forecast_periods for backward compat
      forecast_periods: forecastPeriods,
      scenario_name: sourceScenario,
      selected_tab: backendTabKey,
      selected_metric: activeMetric,
      edited_hierarchy: Array.isArray(hierarchyKey)
        ? hierarchyKey.join(", ")
        : (hierarchyKey || ""),
      factors: activeFactors,
      market_analysis: mergedMarketAnalysis,
    };
  };

  // ── Effects ───────────────────────────────────────────────────────────────
  // Guards against firing fetchMetricFilters more than once for the same
  // therapyArea (e.g. a parent re-render passing an equal-but-new context
  // object, or any effect re-trigger that doesn't represent an actual TA
  // change) — this was contributing to the duplicate "filters"/"HCV
  // config"/"apply-filters" calls seen on load.
  const fetchedTaRef = useRef(null);
  useEffect(() => {
    if (!therapyArea) return;
    if (fetchedTaRef.current === therapyArea) return;
    fetchedTaRef.current = therapyArea;
    fetchMetricFilters();
  }, [therapyArea]);

  useEffect(() => {
    if (!filtersLoaded) return;

    let targetMetric = "market_volume";
    if (activeTab === "total_market") {
      targetMetric = "market_volume";
    } else if (activeTab === "prod_dist" || activeTab === "payer_dist") {
      targetMetric = "market_share";
    } else if (activeTab === "payer_prod" || activeTab === "prod_payer") {
      targetMetric = "market_volume";
    }

    // Set per-tab model default only when the model is at the other tab's
    // default (i.e. the user hasn't explicitly chosen a non-default model).
    // We do NOT call setModelSelection on initial load when syncFactors has
    // already set the correct model from the backend — only change it when
    // the user switches tabs and the current model is clearly a "wrong default".
    const isDefaultForOtherTab =
      activeTab === "total_market"
        ? modelSelection === "moving_average"  // switching TO total_market, was moving_average
        : modelSelection === "ets";            // switching AWAY from total_market, was ets
    if (isDefaultForOtherTab && modelSelection) {
      const newDefault = activeTab === "total_market" ? "ets" : "moving_average";
      setModelSelection(newDefault);
    }

    if (metric !== targetMetric) {
      setMetric(targetMetric);
      if (targetMetric !== "market_share") setBrand("");

      if (isHCV && liverRawData) {
        setLiverTabsRaw(normalizeLiverResponse(liverRawData, targetMetric));
      } else {
        handleApplyFilterWithMetric(targetMetric);
      }
    }
  }, [activeTab, filtersLoaded]);



  useEffect(() => {
    // For HCV, fetchMetricFilters already fully populates the initial view
    // (GET /liver/filters, and a single cfg-driven apply call when a saved
    // config exists). A second, separate handleApplyFilter() call here was
    // firing an extra duplicate apply-filters request on every load — skip
    // it entirely for HCV; non-HCV therapy areas still need it since they
    // don't get pre-populated by fetchMetricFilters in the same way.
    if (!filtersLoaded || autoAppliedOnMount || isHCV) return;
    (async () => {
      try {
        await handleApplyFilter();
        setAutoAppliedOnMount(true);
      } catch (e) {
        console.warn("Auto-apply failed", e);
      }
    })();
  }, [filtersLoaded, autoAppliedOnMount, isHCV]);

  useEffect(() => {
    if (!allFactors || !Object.keys(allFactors).length) return;
    if (modelSelection === "ets") {
      const ets = allFactors?.ets || {};
      setAlpha(ets?.alpha ?? 0);
      setBeta(ets?.beta ?? 0);
      setGamma(ets?.gamma ?? 0);
    } else {
      const traj = allFactors?.[modelSelection] || {};
      setTotalGrowth(traj?.total_growth ?? 0);
      setDuration(traj?.duration ?? 12);
      setTrajectoryStart(traj?.trajectory_start || "");
      setKValue(traj?.k_value ?? 1);
    }
  }, [modelSelection, allFactors]);

  useEffect(() => {
    if (!liverTabsRaw) return;
    const { chart, table } = mapLiverTabToView(liverTabsRaw, activeTab, totalMarketViewMode);
    setChartData(chart);
    setTableData(table);
    // Auto-expand the applied/filtered parent row on hierarchical tabs.
    if (activeTab === "payer_prod") {
      const key = appliedPayerFilter || payerFilter;
      setExpandedBrands(key ? { [key]: true } : {});
    } else if (activeTab === "prod_payer") {
      const key = appliedProductFilter || productFilter;
      setExpandedBrands(key ? { [key]: true } : {});
    } else {
      setExpandedBrands({});
    }
  }, [activeTab, liverTabsRaw, totalMarketViewMode]);

  useEffect(() => {
    if (filterOptions?.scenario_names?.length) {
      const names = filterOptions.scenario_names;
      if (!currentlyAppliedScenario) setCurrentlyAppliedScenario(names[0]);
      if (!tentativeRadioSelectedScenario)
        setTentativeRadioSelectedScenario(names[0]);
      // compareScenarioOptions / selectedCompareScenarios are managed by
      // initializeCompareScenarios which is called with the raw API response —
      // no override here.
    }
  }, [filterOptions.scenario_names]);

  // Exit table edit mode whenever the user switches tabs.
  useEffect(() => {
    if (tableEditing) {
      // setTableData(tableSnapshot);
      setEditedHierarchies({});
      setIsRefreshed(false);
      setTableEditing(false);
      setEditable(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // ── API ───────────────────────────────────────────────────────────────────
  const fetchMetricFilters = async () => {
    try {
      setLoading(true);
      if (isHCV) {
        let cfg = null;

        let localFrom = fromDate || "",
          localTo = toDate || "";
        let localPayer = payerFilter || "",
          localProduct = productFilter || "";

        try {
          const cfgRes = await getConfigurationByTherapyAreaHCV(therapyArea);
          const cfgData = cfgRes?.data;
          if (cfgData?.exists && cfgData?.config) {
            cfg = cfgData.config;
            if (cfg.train_start_date) localFrom = cfg.train_start_date;
            if (cfg.forecast_periods) {
              localTo = cfg.forecast_periods;
            } else if (cfg.train_end_date) localTo = cfg.train_end_date;
          }
        } catch (err) {
          console.warn("Failed to load HCV config", err);
        }

        // GET /api/liver/filters — called once on initial load (no
        // payer/brand params) to seed the Payer/Product dropdown options
        // and the available FROM/TO DATE range. Response shape:
        // { ta_name, markets: [...], products: [...], available_months: [...],
        //   selected_filter: { market, product, start_date, end_date } }
        const fallbackPayers = ["Commercial", "Medicare", "Medicaid"];
        const fallbackProducts = ["GILD", "ASGA", "others"];
        let filtersData = null;
        try {
          const filtersResp = await getLiverFilters({ ta: therapyArea || "HCV" });
          filtersData = filtersResp?.data || null;
        } catch (err) {
          console.warn("Failed to load liver filters", err);
        }

        const norm = {
          payers:
            filtersData?.payers?.length
              ? filtersData.payers
              : cfg?.payer && cfg.payer.length
                ? cfg.payer
                : fallbackPayers,
          products:
            filtersData?.products?.length
              ? filtersData.products
              : cfg?.brand && cfg.brand.length
                ? cfg.brand
                : fallbackProducts,
        };

        setPayerOptions(norm.payers || []);
        setProductOptions(norm.products || []);

        const availMonths = filtersData?.available_months || [];
        if (availMonths.length) setAvailableDates(availMonths);

        const sfInitial = filtersData?.selected_filter || {};
        // Priority for defaults: explicit saved global config first, then
        // whatever the filters endpoint resolved as its own default.
        if (!localPayer)
          localPayer =
            sfInitial.payer ||
            (norm.payers?.length ? getFirstOption(norm.payers) : "");
        if (!localProduct)
          localProduct =
            sfInitial.product ||
            (norm.products?.length ? getFirstOption(norm.products) : "");
        if (!cfg?.train_start_date && sfInitial.start_date)
          localFrom = sfInitial.start_date;
        if (!cfg?.forecast_periods && !cfg?.train_end_date && sfInitial.end_date)
          localTo = sfInitial.end_date;

        setFromDate(localFrom);
        setToDate(localTo);
        setPayerFilter(localPayer);
        setProductFilter(localProduct);
        // Stamp the applied values immediately so the default highlight
        // shows on first load without waiting for an explicit Apply click.
        setAppliedPayerFilter(localPayer);
        setAppliedProductFilter(localProduct);

        const defaultMetricOptions = [
          { label: "Market Volume", value: "market_volume" },
          { label: "Market Share", value: "market_share" },
        ];
        if (!metric) setMetric(defaultMetricOptions[0].value);
        setFilterOptions({
          indications: [],
          metric_filters: defaultMetricOptions,
          scenario_names: [],
        });

        try {
          const applyPayload = {
            ta: therapyArea || "HCV",
            payer: localPayer ? [localPayer] : [],
            brand: localProduct ? [localProduct] : [],
            product: localProduct || "",
            metric: metric || defaultMetricOptions[0].value,
            from_date: cfg?.train_start_date || localFrom || "",
            scenario_name: "Base",
          };
          const applyResp = await applyLiverFilters(applyPayload);
          const data = applyResp?.data || {};

          const availScenarios = (() => {
            if (Array.isArray(data?.available_scenarios))
              return data.available_scenarios;
            if (
              data?.scenarios &&
              typeof data.scenarios === "object" &&
              !Array.isArray(data.scenarios)
            )
              return Object.keys(data.scenarios);
            return [];
          })();
          if (availScenarios.length) {
            setFilterOptions((prev) => ({
              ...prev,
              scenario_names: availScenarios,
            }));
          }
          const activeScenarioKey =
            data?.active_scenario || availScenarios[0] || "Base";
          setScenarioSelector(activeScenarioKey);

          // Dates resolved by the backend for this payer/product/scenario
          const sf = data?.selected_filter || {};
          if (sf.start_date) setFromDate(sf.start_date);
          if (sf.end_date) setToDate(sf.end_date);

          const applyScenarioObj =
            (data?.scenarios && data.scenarios[activeScenarioKey]) || null;
          const f = applyScenarioObj?.factors || data?.factors || {};
          if (Object.keys(f).length) {
            let am = f?.active_model || "ets";
            am = resolveModelForTab(am);
            setModelSelection(am);
            syncFactors(f, am);
          }

          const normalized = normalizeLiverResponse(data, metric);
          setLiverTabsRaw(normalized);
          setLiverRawData(data);
          initializeCompareScenarios(data);
          // Prefer the backend's full available_months (DB start → forecast end)
          // over the chart's month list, which only covers the model range.
          if (data?.available_months?.length) setAvailableDates(data.available_months);
          else if (normalized?.months?.length) setAvailableDates(normalized.months);
          setEditable(false);
        } catch (err) {
          console.warn("Failed to apply HCV filters on load", err);
        }
        return;
      }

      const response = await getMetricFilters(therapyArea);
      const resData = response?.data;
      setMappingData(resData?.data || {});
      const avail = resData?.available_dates || [];
      setAvailableDates(avail);
      const df = resData?.selected_filter;
      if (!df) {
        setFilterOptions({
          indications: [],
          metric_filters: (resData?.metric_filters || []).map((m) =>
            typeof m === "string"
              ? { label: m, value: m }
              : { label: m.label, value: m.value },
          ),
          scenario_names: resData?.scenario_names || [],
        });
        return;
      }

      setScenarioSelector(df.scenario_name);
      setIndication(df.indication);
      setLot(df.lot);
      setMetric(df.metric);
      setBrand(df.product || "");
      setFromDate(
        df.from_date && avail.includes(df.from_date) ? df.from_date : "",
      );
      setToDate(
        df.to_date && avail.includes(df.to_date)
          ? df.to_date
          : avail[avail.length - 1] || "",
      );
      setPayerFilter(
        Array.isArray(df.payer) ? df.payer[0] || "" : df.payer || "",
      );
      setProductFilter(
        Array.isArray(df.product_filter)
          ? df.product_filter[0] || ""
          : df.product_filter || "",
      );
      setFilterOptions({
        indications: Object.keys(resData?.data?.[df.scenario_name] || {}),
        metric_filters: (resData?.metric_filters || []).map((m) =>
          typeof m === "string"
            ? { label: m, value: m }
            : { label: m.label, value: m.value },
        ),
        scenario_names: resData?.scenario_names || [],
      });

      if (therapyArea?.toLowerCase() === "hcv") {
        try {
          const cfgRes = await getConfigurationByTherapyAreaHCV(therapyArea);
          const cfg = cfgRes?.data?.config || null;
          if (cfg?.forecast_periods && avail.includes(cfg.forecast_periods))
            setToDate(cfg.forecast_periods);
        } catch (err) {
          console.warn("TO DATE override failed", err);
        }
      }

      const applyResp = await applyMetricFilters({
        ...buildBasePayload(),
        scenario_name: df.scenario_name,
        indications: df.indication ? [df.indication] : [],
        lots: df.lot ? [df.lot] : [],
        metric_filter: df.metric,
        product: df.metric === "market_share" ? df.product || "" : "",
        from_date: df.from_date || "",
        to_date: df.to_date || "",
        payer: df.payer || "",
        product_filter: df.product_filter || "",
      });
      const data = applyResp?.data;
      setAppliedLot(df.lot);
      setAppliedBrand(df.product || "");
      setAppliedPayerFilter(df.payer || "");
      setAppliedProductFilter(df.product_filter || "");
      const factors = data?.factors || {};
      let am = factors?.active_model || "ets";
      am = resolveModelForTab(am);
      setModelSelection(am);
      syncFactors(factors, am);
      syncMetrics(data?.metrics_data, df.metric);
    } catch (error) {
      console.error("fetchMetricFilters failed", error);
      showSnackbar("Failed to fetch metric filters", "error");
    } finally {
      setLoading(false);
      setFiltersLoaded(true);
    }
  };

  // Called whenever the PAYER FILTER or PRODUCT FILTER dropdown changes.
  // Hits GET /api/liver/filters with the newly selected payer/product and
  // repopulates from-date, to-date, available scenarios, the projection
  // factors, and the chart/table directly from the backend response —
  // matching the same response shape used on initial load.
  const refreshLiverFilters = async (payerVal, productVal) => {
    if (!isHCV) return;
    try {
      setLoading(true);
      const response = await getLiverFilters({
        ta: therapyArea || "HCV",
        payer: payerVal || undefined,
        brand: productVal || undefined,
      });
      const resData = response?.data || {};
      const sf = resData?.selected_filter || {};

      // Refresh FROM/TO DATE options for this payer/product combination.
      if (
        Array.isArray(resData?.available_months) &&
        resData.available_months.length
      ) {
        setAvailableDates(resData.available_months);
      }
      // Keep the Payer/Product dropdown lists in sync too.
      if (Array.isArray(resData?.payers) && resData.payers.length) {
        setPayerOptions(resData.payers);
      }
      if (Array.isArray(resData?.products) && resData.products.length) {
        setProductOptions(resData.products);
      }

      // Update FROM/TO DATE values from the backend's resolved selection.
      if (sf.start_date) setFromDate(sf.start_date);
      if (sf.end_date) setToDate(sf.end_date);

      // Sync payer/product to whatever the backend resolved (in case it
      // snapped to a valid combination), falling back to what was picked.
      setPayerFilter(sf.payer || payerVal || "");
      setProductFilter(sf.product || productVal || "");

      // NOTE: chart/table and factors are intentionally NOT updated here.
      // The user must click "Apply Filter" to reload the data for the new
      // payer/product selection. This avoids an extra apply-filters API
      // call on every dropdown change.
    } catch (error) {
      console.error("Failed to refresh liver filters", error);
      showSnackbar("Failed to load filter data", "error");
    } finally {
      setLoading(false);
    }
  };

  // Resolves the model to use from a backend active_model value.
  // Rules:
  //   - total_market tab default is "ets" if the backend sent nothing/null.
  //   - All other tabs default to "linear" if the backend sent "ets" or nothing
  //     (ETS is now allowed on any tab, but "ets" is only the default on
  //     total_market).
  //   - A concrete non-null value from the backend is always respected.
  const resolveModelForTab = (backendModel) => {
    if (!backendModel) {
      return activeTab === "total_market" ? "ets" : "moving_average";
    }
    // If we're NOT on total_market and the backend explicitly returned "ets",
    // honour it — the user may have saved an ETS scenario on another tab.
    return backendModel;
  };

  const handleApplyFilterWithMetric = async (newMetric) => {
    try {
      setLoading(true);
      if (isHCV) {
        const effectiveMetric = newMetric || "market_volume";
        setMetric(effectiveMetric);
        const response = await applyLiverFilters({
          ...buildLiverBasePayload(),
          metric: effectiveMetric,
        });
        const data = response?.data || {};
        setAppliedLot(lot);
        setAppliedBrand(productFilter || brand);
        setAppliedPayerFilter(payerFilter);
        setAppliedProductFilter(productFilter);
        const dataActiveScenario = data?.active_scenario || scenarioSelector;
        const dataScenarioObj =
          (data?.scenarios && data.scenarios[dataActiveScenario]) || null;
        const f = dataScenarioObj?.factors || data?.factors || {};
        if (Object.keys(f).length) {
          let am = f?.active_model || "ets";
          am = resolveModelForTab(am);
          setModelSelection(am);
          syncFactors(f, am);
        }
        setLiverTabsRaw(normalizeLiverResponse(data, effectiveMetric));
        setLiverRawData(data);
        initializeCompareScenarios(data);
        setAllMetricsData({
          [effectiveMetric]: {
            unit: effectiveMetric === "market_share" ? "%" : "",
          },
        });
        setEditable(false);
        return;
      }
      const response = await applyMetricFilters({
        ...buildBasePayload(),
        metric_filter: newMetric,
      });
      const data = response?.data;
      setAppliedLot(lot);
      setAppliedBrand(brand);
      const factors = data?.factors || {};
      let am = factors?.active_model || "ets";
      am = resolveModelForTab(am);
      setModelSelection(am);
      syncFactors(factors, am);
      syncMetrics(data?.metrics_data, newMetric);
      setEditable(false);
    } catch (error) {
      const msg = error?.response?.data || error?.message || "Unknown error";
      showSnackbar(
        typeof msg === "string" ? msg : JSON.stringify(msg),
        "error",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleApplyFilter = async () => {
    if (!resolveFromDate()) {
      showSnackbar("Please select a From Date before applying filters", "error");
      return;
    }
    if (!toDate) {
      showSnackbar("Please select a To Date before applying filters", "error");
      return;
    }
    try {
      setLoading(true);
      if (isHCV) {
        const response = await applyLiverFilters(buildLiverBasePayload());
        const data = response?.data || {};
        setAppliedLot(lot);
        setAppliedBrand(productFilter || brand);
        setAppliedPayerFilter(payerFilter);
        setAppliedProductFilter(productFilter);
        const dataActiveScenario = data?.active_scenario || scenarioSelector;
        const dataScenarioObj =
          (data?.scenarios && data.scenarios[dataActiveScenario]) || null;
        const f = dataScenarioObj?.factors || data?.factors || {};
        if (Object.keys(f).length) {
          let am = f?.active_model || "ets";
          am = resolveModelForTab(am);
          setModelSelection(am);
          syncFactors(f, am);
        }
        setLiverTabsRaw(normalizeLiverResponse(data, metric));
        setLiverRawData(data);
        initializeCompareScenarios(data);
        setEditable(false);
        showSnackbar("Filters applied successfully", "success");
        return;
      }
      const response = await applyMetricFilters(buildBasePayload());
      const data = response?.data;
      setAppliedLot(lot);
      setAppliedBrand(brand);
      const factors = data?.factors || {};
      let am = factors?.active_model || "ets";
      am = resolveModelForTab(am);
      setModelSelection(am);
      syncFactors(factors, am);
      syncMetrics(data?.metrics_data, metric);
      setEditable(false);
      showSnackbar("Filters applied successfully", "success");
    } catch (error) {
      const msg = error?.response?.data || error?.message || "Unknown error";
      showSnackbar(
        typeof msg === "string" ? msg : JSON.stringify(msg),
        "error",
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRecalculate = async () => {
    try {
      setLoading(true);
      if (isHCV) {
        const response = await recalculateLiver(buildLiverRecalculatePayload());
        const data = response?.data || {};
        const activeScenarioKey =
          data?.active_scenario ||
          (data?.scenarios && Object.keys(data.scenarios || {})[0]);
        const scenarioObj =
          (data?.scenarios && data.scenarios[activeScenarioKey]) || {};
        const factors = scenarioObj?.factors || data?.factors || {};
        let am = factors?.active_model || modelSelection;
        am = resolveModelForTab(am);
        setModelSelection(am);
        syncFactors(factors, am);
        setLiverTabsRaw(normalizeLiverResponse(data, metric));
        setLiverRawData(data);
        initializeCompareScenarios(data);
        showSnackbar("Recalculated successfully", "success");
        return;
      }
      const mf =
        modelSelection === "ets"
          ? { ets: { alpha, beta, gamma } }
          : {
            growth: {
              total_growth: totalGrowth,
              duration,
              trajectory_start: trajectoryStart,
              ...(modelSelection !== "linear" && { k_value: Number(kValue) }),
            },
          };
      const response = await recalculateMetrics({
        ...buildBasePayload(),
        model_type: modelSelection,
        factors: { multiplier, multiplier_horizon: multiplierHorizon, ...mf },
      });
      const data = response?.data;
      syncFactors(data?.factors || {}, data?.factors?.active_model);
      syncMetrics(data?.metrics_data, metric);
      showSnackbar("Metrics recalculated successfully", "success");
    } catch (error) {
      console.error("Recalculate failed", error);
      showSnackbar("Failed to recalculate metrics", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateScenario = async () => {
    if (!scenarioSelector) {
      showSnackbar("Please select a scenario", "error");
      return;
    }
    if (!chartData || !tableData.length) {
      showSnackbar("No data to update", "error");
      return;
    }
    try {
      setLoading(true);
      const res = await updateScenario({
        ...buildBasePayload(),
        lot,
        indication,
        metric,
        product: brand || null,
        model_type: modelSelection,
        factors: buildFullFactors(),
        metrics_data: allMetricsData,
      });
      const data = res?.data;
      const factors = data?.factors || {};
      let am = factors?.active_model || "ets";
      am = resolveModelForTab(am);
      setModelSelection(am);
      syncFactors(factors, am);
      syncMetrics(data?.metrics_data, metric);
      setEditable(false);
      showSnackbar("Scenario updated successfully", "success");
    } catch (error) {
      showSnackbar("Failed to update scenario", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveScenario = async (scenarioNameFromDialog) => {
    if (!scenarioNameFromDialog) {
      showSnackbar("Please enter the scenario name", "error");
      return;
    }
    if (!chartData || !tableData.length) {
      showSnackbar("No data to save", "error");
      return;
    }
    try {
      setLoading(true);
      if (isHCV) {
        // Resolve source scenario robustly
        const sourceScenario =
          currentlyAppliedScenario ||
          scenarioSelector ||
          liverRawData?.active_scenario ||
          (liverRawData?.scenarios ? Object.keys(liverRawData.scenarios)[0] : "Base") ||
          "Base";

        // Resolve market_analysis — try exact key match first, then case-insensitive,
        // then fall back to the first available scenario's market_analysis.
        let marketAnalysis = liverRawData?.scenarios?.[sourceScenario]?.market_analysis;
        if (!marketAnalysis && liverRawData?.scenarios) {
          const matchedKey = Object.keys(liverRawData.scenarios).find(
            (k) => k.toLowerCase() === sourceScenario.toLowerCase()
          );
          marketAnalysis = matchedKey
            ? liverRawData.scenarios[matchedKey]?.market_analysis
            : Object.values(liverRawData.scenarios)[0]?.market_analysis;
        }
        marketAnalysis = marketAnalysis || {};

        const payload = {
          ta_name: therapyArea || "HCV",
          scenario_name: scenarioNameFromDialog,
          selected_filter: {
            market: appliedPayerFilter || payerFilter || getFirstOption(payerOptions) || "",
            product: appliedProductFilter || productFilter || getFirstOption(productOptions) || "",
            start_date: resolveFromDate(),
            end_date: toDate || "",
          },
          source_scenario: sourceScenario,
          factors: buildFullFactors(),
          market_analysis: marketAnalysis,
        };

        console.log("[SaveScenario] payload:", JSON.stringify(payload, null, 2));

        const resp = await saveLiverScenario(payload);

        showSnackbar("Scenario saved successfully", "success");

        // Add to scenario list if not already present.
        setFilterOptions((prev) => {
          const names = prev.scenario_names || [];
          if (names.includes(scenarioNameFromDialog)) return prev;
          return { ...prev, scenario_names: [...names, scenarioNameFromDialog] };
        });

        // If the save response includes updated chart/table data, load it
        // directly into the view so the new scenario row shows real values.
        const respData = resp?.data || {};
        if (respData && Object.keys(respData).length) {
          const activeScenarioKey =
            respData?.active_scenario ||
            scenarioNameFromDialog;
          const applyScenarioObj =
            (respData?.scenarios && respData.scenarios[activeScenarioKey]) ||
            null;
          const f = applyScenarioObj?.factors || respData?.factors || {};
          if (Object.keys(f).length) {
            let am = f?.active_model || modelSelection;
            am = resolveModelForTab(am);
            setModelSelection(am);
            syncFactors(f, am);
          }
          const normalized = normalizeLiverResponse(respData, metric);
          if (normalized?.tabs && Object.keys(normalized.tabs).length) {
            setLiverTabsRaw(normalized);
            setLiverRawData(respData);
            initializeCompareScenarios(respData, scenarioNameFromDialog);
            // mapLiverTabToView will re-run via the liverTabsRaw effect,
            // which updates chartData and tableData automatically.
          }
        }

        setTentativeRadioSelectedScenario(scenarioNameFromDialog);
        setCurrentlyAppliedScenario(scenarioNameFromDialog);

        // Add to savedScenarioRows so it appears in the table immediately.
        // Only skip adding it if the API response already includes it as a
        // scenario with its own table data in groupedTableHierarchy.
        setSavedScenarioRows((prev) => {
          const scenarioInResponse =
            respData?.scenarios?.[scenarioNameFromDialog] ||
            respData?.available_scenarios?.includes(scenarioNameFromDialog);
          if (scenarioInResponse) return prev.filter((n) => n !== scenarioNameFromDialog);
          return prev.includes(scenarioNameFromDialog)
            ? prev
            : [...prev, scenarioNameFromDialog];
        });

        // Match handleConfirmSave: a successful save always exits edit mode.
        setEditedHierarchies({});
        setIsRefreshed(false);
        setTableEditing(false);
        setEditable(false);
        return;
      }
      await saveScenario({
        ...buildBasePayload(),
        scenario_name: scenarioNameFromDialog,
        lot,
        indication,
        metric,
        product: brand || null,
        model_type: modelSelection,
        factors: buildFullFactors(),
        metrics_data: allMetricsData,
      });
      showSnackbar("Scenario created successfully", "success");
      const response = await getMetricFilters(therapyArea);
      const resData = response?.data;
      const nm = resData?.data || {};
      setMappingData(nm);
      setFilterOptions({
        indications: Object.keys(nm?.[scenarioNameFromDialog] || {}),
        metric_filters: resData?.metric_filters || [],
        scenario_names: resData?.scenario_names || [],
      });
      setScenarioSelector(scenarioNameFromDialog);
    } catch (err) {
      console.error("[SaveScenario] error:", err?.response?.data || err);
      showSnackbar("Failed to save scenario", "error");
    } finally {
      setLoading(false);
    }
  };

  // ── Table edit / refresh handlers ────────────────────────────────────────
  const handleEnterTableEdit = () => {
    setTableSnapshot(tableData.map((r) => ({ ...r, monthly_data: { ...r.monthly_data } })));
    setEditedHierarchies({});
    setIsRefreshed(false);
    setTableEditing(true);
    setEditable(true);
  };

  const handleCancelTableEdit = () => {
    setTableData(tableSnapshot);
    setEditedHierarchies({});
    setIsRefreshed(false);
    setTableEditing(false);
    setEditable(false);
  };

  // Called by the Save button after Refresh has already synced data with the backend.
  // Just closes edit mode — no additional API call needed.
  // Base scenario → POST /api/liver/save-scenario (save as new via modal).
  // Other scenario → PUT /api/liver/update-scenario (update in place).
  const handleConfirmSave = async () => {
    const activeScenario = currentlyAppliedScenario || scenarioSelector || "";
    const isBase = activeScenario.toLowerCase() === "base";

    // Resolve full market_analysis for the active scenario
    let marketAnalysis = liverRawData?.scenarios?.[activeScenario]?.market_analysis;
    if (!marketAnalysis && liverRawData?.scenarios) {
      const matchedKey = Object.keys(liverRawData.scenarios).find(
        (k) => k.toLowerCase() === activeScenario.toLowerCase()
      );
      marketAnalysis = matchedKey
        ? liverRawData.scenarios[matchedKey]?.market_analysis
        : Object.values(liverRawData.scenarios)[0]?.market_analysis;
    }
    marketAnalysis = marketAnalysis || {};

    if (isBase) {
      // Base is read-only — prompt user to name a new scenario (POST flow)
      setNewScenarioName("");
      setSaveScenarioDialogOpen(true);
      return;
    }

    // Non-Base → PUT /api/liver/update-scenario
    const backendSf = liverRawData?.selected_filter || {};
    const updatePayload = {
      ta_name: therapyArea || "HCV",
      selected_filter: {
        start_date: backendSf.start_date || resolveFromDate(),
        end_date: backendSf.end_date || toDate || "",
        payer: backendSf.payer || appliedPayerFilter || payerFilter || getFirstOption(payerOptions) || "",
        product: backendSf.product || appliedProductFilter || productFilter || getFirstOption(productOptions) || "",
      },
      scenario_name: activeScenario,
      factors: buildFullFactors(),
      market_analysis: marketAnalysis,
    };

    try {
      setIsSavingEditChanges(true);
      setLoading(true);
      const resp = await updateLiverScenario(updatePayload);
      const respData = resp?.data || {};
      if (respData && Object.keys(respData).length) {
        const normalized = normalizeLiverResponse(respData, metric);
        if (normalized?.tabs && Object.keys(normalized.tabs).length) {
          setLiverTabsRaw(normalized);
          setLiverRawData(respData);
          initializeCompareScenarios(respData);
        }
      }
      setIsRefreshed(false);
      setTableEditing(false);
      setEditable(false);
      showSnackbar(`Scenario "${activeScenario}" updated successfully`, "success");
    } catch (err) {
      console.error("[UpdateScenario] error:", err?.response?.data || err);
      showSnackbar("Failed to update scenario", "error");
    } finally {
      setIsSavingEditChanges(false);
      setLoading(false);
    }
  };

  const handleSaveTableChanges = async () => {
    const editedKeys = Object.keys(editedHierarchies);
    if (!editedKeys.length) {
      showSnackbar("No changes to save", "info");
      setTableEditing(false);
      setEditable(false);
      return;
    }
    try {
      setSavingTable(true);
      setLoading(true);
      // Previously this looped once per edited row, firing N near-identical
      // requests (each call already carries every current edit baked into
      // tableData) and keeping only the last response. That both wasted
      // calls and risked the backend treating each call as "only this one
      // row changed," reverting earlier edits made in the same session.
      // Send everything in a single call instead.
      const payload = buildRefreshTablePayload(editedKeys);
      console.log("[RefreshTable] calling refreshLiverTable with payload:", JSON.stringify(payload, null, 2));
      const response = await refreshLiverTable(payload);
      const lastRawData = response?.data || {};
      if (lastRawData) {
        // mapRefreshTableResponse handles both the new full-scenarios shape
        // and the legacy flat shape. For the full-scenarios shape it also
        // calls setLiverRawData internally so all tabs stay in sync.
        const { chart, table } = mapRefreshTableResponse(lastRawData);
        setChartData(chart);
        setTableData(table);

        // If the response was a full scenarios payload, normalizeLiverResponse
        // already ran inside mapRefreshTableResponse; update liverTabsRaw so
        // that switching tabs re-derives the correct view from fresh data.
        if (lastRawData.scenarios || lastRawData.active_scenario) {
          const normalized = normalizeLiverResponse(lastRawData, metric);
          setLiverTabsRaw(normalized);
        } else {
          // Legacy flat response: patch only the current tab in liverTabsRaw.
          const backendKey = TAB_KEY_MAP[activeTab] || activeTab;
          setLiverTabsRaw((prev) => {
            const base = prev || { months: chart?.months || [], forecast_start_index: chart?.forecast_start_index || 0, tabs: {} };
            return {
              ...base,
              tabs: {
                ...base.tabs,
                [backendKey]: {
                  chart,
                  table: {
                    type: "flat",
                    headers: chart?.months || [],
                    rows: table.map((r) => ({
                      hierarchy: r.hierarchy,
                      label: r.hierarchy,
                      values: (chart?.months || []).map(
                        (m) => r.monthly_data?.[m] ?? null,
                      ),
                    })),
                  },
                },
              },
            };
          });
        }
      }
      setEditedHierarchies({});
      setIsRefreshed(true);
      showSnackbar("Table refreshed successfully. You can now Save.", "success");
    } catch (error) {
      const msg = error?.response?.data || error?.message || "Unknown error";
      showSnackbar(
        typeof msg === "string" ? msg : JSON.stringify(msg),
        "error",
      );
    } finally {
      setSavingTable(false);
      setLoading(false);
    }
  };

  const handleDownloadTable = () => {
    try {
      const months = chartData?.months || [];
      const headerRow = ["Product / LOT", ...months.map((m) => formatDateLabel(m))];
      const rows = tableData.map((r) => [
        r.hierarchy,
        ...months.map((m) => {
          const v = r.monthly_data?.[m];
          return v == null ? "" : v;
        }),
      ]);
      const csv = [headerRow, ...rows]
        .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))
        .join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${activeTabLabel.replace(/\s+/g, "_")}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      showSnackbar("Failed to download table", "error");
    }
  };

  // ── UI handlers ───────────────────────────────────────────────────────────

  // Seed Compare Scenarios dropdown from the API response's available_scenarios.
  // Called after every apply-filters / save-scenario / initial load response.
  const initializeCompareScenarios = (response, appliedScenario) => {
    const scenarios =
      response?.available_scenarios ||
      (response?.scenarios ? Object.keys(response.scenarios) : []);

    // Always include the newly saved/applied scenario even if the API
    // response doesn't list it in available_scenarios / scenarios keys.
    const toAdd = appliedScenario || currentlyAppliedScenario || "";
    const merged = toAdd && !scenarios.includes(toAdd)
      ? [...scenarios, toAdd]
      : scenarios;

    if (!merged.length) return;
    setCompareScenarioOptions(merged);
    // Only default to "select all" on first load (nothing chosen yet) or
    // before the user has ever touched the dropdown. Once the user has
    // customized their selection, preserve it across apply-filter /
    // save-scenario / refresh calls — just drop any scenario names that no
    // longer exist in the new list. Previously this ran unconditionally on
    // every call, silently re-checking scenarios the user had unchecked.
    setSelectedCompareScenarios((prev) => {
      if (!userHasCustomizedCompare || !prev.length) return merged;
      const stillValid = prev.filter((name) => merged.includes(name));
      return stillValid.length ? stillValid : merged;
    });
  };

  // Mirrors HIV's Compare Scenarios <Select multiple> onChange: the
  // currently applied scenario is always force-included in the selection
  // (its MenuItem/Checkbox are also disabled below so it can't be
  // unchecked directly).
  const handleCompareScenarioChange = (e) => {
    let value = e.target.value;
    if (currentlyAppliedScenario && !value.includes(currentlyAppliedScenario)) {
      value = [...value, currentlyAppliedScenario];
    }
    setUserHasCustomizedCompare(true);
    setSelectedCompareScenarios(value);
  };
  const handleActiveScenarioRadioChange = (name) => {
    setTentativeRadioSelectedScenario(name);
  };
  const clickTableEdit = () => setEditable(true);
 const applySelectedScenario = async () => {
    const chosenScenario = tentativeRadioSelectedScenario;
    if (!chosenScenario) {
      showSnackbar("Please select a scenario to apply", "error");
      return;
    }

    try {
      setLoading(true);
      const backendSf = liverRawData?.selected_filter || {};

      const payload = {
        ta_name: therapyArea || "HCV",
        selected_filter: {
          start_date: backendSf.start_date || resolveFromDate(),
          end_date: backendSf.end_date || toDate || "",
          payer: backendSf.payer || appliedPayerFilter || payerFilter || getFirstOption(payerOptions) || "",
          product: backendSf.product || appliedProductFilter || productFilter || getFirstOption(productOptions) || "",
        },
        scenario_name: chosenScenario,
      };

      // Hit the new activation endpoint
      const response = await activateLiverScenario(payload);
      const respData = response?.data;

      // Update UI configurations
      setCurrentlyAppliedScenario(chosenScenario);

      // Keep the newly applied scenario checked in the Compare dropdown
      setSelectedCompareScenarios((prev) => {
        if (prev.includes(chosenScenario)) return prev;
        return [...prev, chosenScenario];
      });

      // If the backend returns updated full scenario data layout, process it.
      // Otherwise, fall back to manipulating local cache state.
      if (respData && (respData.scenarios || respData.active_scenario)) {
        const normalized = normalizeLiverResponse(respData, metric);
        setLiverTabsRaw(normalized);
        setLiverRawData(respData);
      } else if (liverRawData) {
        const patched = { ...liverRawData, active_scenario: chosenScenario };
        const normalized = normalizeLiverResponse(patched, metric);
        setLiverTabsRaw(normalized);
      }

      showSnackbar(`Applied ${chosenScenario} successfully across all tabs!`, "success");
      setEditable(false);
    } catch (error) {
      console.error("Failed to activate scenario:", error);
      const msg = error?.response?.data || error?.message || "Unknown error";
      showSnackbar(typeof msg === "string" ? msg : "Failed to activate scenario", "error");
    } finally {
      setLoading(false);
    }
  };

  // ── Forecast helper ───────────────────────────────────────────────────────
  const isForecastMonth = (col) => {
    if (!chartData?.months?.length || chartData?.forecast_start_index == null)
      return false;
    return chartData.months.slice(chartData.forecast_start_index).includes(col);
  };

  // ── Cell formatter ────────────────────────────────────────────────────────
  const formatCellValue = (val) => {
    if (val == null) return "—";
    const num = Number(val);
    if (metricUnit === "%") {
      // Whole numbers: no decimals (100%); fractional: up to 2dp (64.79%)
      const formatted = Number.isInteger(num) ? num : parseFloat(num.toFixed(2));
      return `${formatted}%`;
    }
    return num.toLocaleString(undefined, { maximumFractionDigits: 0 });
  };

  const toggleBrandExpand = (name) => {
    setExpandedBrands((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  // Bulk expand/collapse for hierarchical tabs (payer_prod / prod_payer),
  // matches HIV's "Expand All" / "Collapse All" toolbar icons.
  const handleExpandAllRows = () => {
    const all = {};
    groupedTableHierarchy.forEach((g) => {
      if (g.children?.length) all[g.brandName] = true;
    });
    setExpandedBrands(all);
  };

  const handleCollapseAllRows = () => {
    setExpandedBrands({});
  };

  const handleCellChange = (hierarchyKey, colName, value) => {
    const numericValue = value === "" ? null : Number(value);
    if (numericValue !== null && Number.isNaN(numericValue)) return;
    // Any new edit invalidates the previous refresh — user must Refresh again
    setIsRefreshed(false);
    setTableData((prevTable) =>
      prevTable.map((row) => {
        if (row.hierarchy === hierarchyKey) {
          return {
            ...row,
            monthly_data: {
              ...row.monthly_data,
              [colName]: numericValue,
            },
          };
        }
        return row;
      }),
    );
    setEditedHierarchies((prev) => ({ ...prev, [hierarchyKey]: true }));
  };

  // Payer-Product / Product-Payer group by scenario at the top level
  // (see groupedTableHierarchy); Product/Payer Distribution stay flat with
  // inline "(ScenarioName)" tags — see scenarioOverlayTableRows below.
  const isComboTab = activeTab === "payer_prod" || activeTab === "prod_payer";
  const isScenarioGroupedTab = isComboTab;

  // Extra table rows for every OTHER selected Compare Scenario, on tabs
  // besides Total Market Volume (which already gets one row per scenario
  // from its own bespoke handling upstream in normalizeLiverResponse).
  // Mirrors HIV's mergedRows/appendScenario: pull each scenario's own rows
  // for the active tab/metric directly from the raw per-scenario API data,
  // tag the top-level label with "(ScenarioName)" so it renders as its own
  // distinguishable group instead of merging into the active scenario's.
  const scenarioOverlayTableRows = useMemo(() => {
    if (activeTab === "total_market") return [];
    if (!liverRawData?.scenarios) return [];
    const backendTabKey = TAB_KEY_MAP[activeTab] || activeTab;
    const activeMetricKey = toApiMetricKey(metric);
    const fallbackMonths = chartData?.months || [];
    const scenarioNames = selectedCompareScenarios || [];

    const toMonthly = (values, monthsForThisScenario) => {
      const obj = {};
      monthsForThisScenario.forEach((m, i) => {
        const v = values?.[i];
        obj[m] = v == null ? null : Number(v);
      });
      return obj;
    };

    const out = [];
    scenarioNames.forEach((scenarioName) => {
      // The currently applied scenario's rows already come through as the
      // base tableData — don't duplicate them here.
      if (scenarioName === currentlyAppliedScenario) return;

      const tabObj =
        liverRawData.scenarios[scenarioName]?.market_analysis?.[backendTabKey];
      if (!tabObj) return;
      const metricObj =
        tabObj[activeMetricKey] ||
        tabObj.payer_volume ||
        tabObj.payer_share ||
        Object.values(tabObj)[0];
      // Each scenario carries its own months list (e.g. a newly created
      // scenario can have a different date range than whatever's currently
      // displayed) — use THIS scenario's own months to zip its values,
      // rather than assuming every scenario shares the active one's dates.
      const months =
        metricObj?.monthly?.chart?.months || metricObj?.chart?.months || fallbackMonths;
      const rows =
        metricObj?.monthly?.table?.rows || metricObj?.table?.rows || [];

      rows.forEach((r) => {
        const parentLabel = r.label || r.hierarchy || "";
        if (!parentLabel) return;
        // Payer-Product / Product-Payer regroup by scenario at the top
        // level (see groupedTableHierarchy), so keep their combo labels
        // clean — the scenario is tracked via the `scenario` field instead
        // of a "(ScenarioName)" suffix. Product/Payer Distribution stay
        // flat: each scenario's row sits alongside the applied scenario's,
        // tagged inline as e.g. "Cash (High Growth)".
        const taggedParent = isComboTab ? parentLabel : `${parentLabel} (${scenarioName})`;
        out.push({
          hierarchy: taggedParent,
          monthly_data: toMonthly(r.values || r.total || [], months),
          is_applied: false,
          is_scenario_overlay: true,
          scenario: scenarioName,
        });
        (r.children || []).forEach((c) => {
          out.push({
            hierarchy: `${taggedParent} - ${c.label}`,
            monthly_data: toMonthly(c.values || [], months),
            is_applied: false,
            is_scenario_overlay: true,
            scenario: scenarioName,
          });
        });
      });
    });
    return out;
  }, [
    activeTab,
    liverRawData,
    metric,
    chartData,
    selectedCompareScenarios,
    currentlyAppliedScenario,
  ]);

  // ── Hierarchy grouping ────────────────────────────────────────────────────
  const groupedTableHierarchy = useMemo(() => {
    if (isScenarioGroupedTab) {
      // Group by SCENARIO at the top level: expanding a scenario reveals
      // every product/payer (or payer-product combination, on the two
      // cross tabs) as a flat child row. The applied scenario's own rows
      // come from `tableData` (untagged); comparison scenarios come from
      // scenarioOverlayTableRows, tracked via their `scenario` field
      // rather than a label suffix.
      const byScenario = {};
      const belongsToThisTab = (hierarchy) => {
        const hasCombo = (hierarchy || "").includes(" - ");
        // Combo tabs (Payer-Product/Product-Payer) want the flat combo
        // rows; Distribution tabs (Product/Payer) are single-entity and
        // never have a " - " separator, so exclude any that do (the base
        // pipeline also emits a parent-only aggregate row alongside combo
        // rows, which combo tabs need to skip here too).
        return isComboTab ? hasCombo : !hasCombo;
      };
      tableData.forEach((row) => {
        if (!belongsToThisTab(row.hierarchy)) return;
        const name = currentlyAppliedScenario || "Applied Scenario";
        if (!byScenario[name]) byScenario[name] = { rows: [], isScenarioOverlay: false };
        byScenario[name].rows.push(row);
      });
      scenarioOverlayTableRows.forEach((row) => {
        if (!belongsToThisTab(row.hierarchy)) return;
        const name = row.scenario || "Unknown Scenario";
        if (!byScenario[name]) byScenario[name] = { rows: [], isScenarioOverlay: true };
        byScenario[name].rows.push(row);
      });

      return Object.keys(byScenario).map((scenarioName) => {
        const entry = byScenario[scenarioName];
        const children = entry.rows.map((row) => ({
          ...row,
          cleanLabel: row.hierarchy,
        }));
        const months =
          chartData?.months ||
          (children[0] ? Object.keys(children[0].monthly_data || {}) : []);
        const monthly_data = {};
        months.forEach((m) => {
          let sum = 0,
            any = false;
          children.forEach((c) => {
            const v = c.monthly_data?.[m];
            if (v != null && !Number.isNaN(Number(v))) {
              sum += Number(v);
              any = true;
            }
          });
          // A full market-share breakdown always sums to 100% by
          // definition. Each payer's (or product's) own combos already sum
          // to 100% within that payer, so summing across every payer as
          // well inflates the raw total to e.g. 400% for 4 payers — show
          // the correct 100% instead (whenever there's actually data for
          // this month), rather than that inflated raw sum.
          monthly_data[m] = !any ? null : isPercentTab ? 100 : sum;
        });
        return {
          brandName: scenarioName,
          mainRow: {
            hierarchy: scenarioName,
            monthly_data,
            is_applied: !entry.isScenarioOverlay,
          },
          children,
          isScenarioOverlay: entry.isScenarioOverlay,
          isScenarioGroup: true,
        };
      });
    }

    const map = {};
    [...tableData, ...scenarioOverlayTableRows].forEach((row) => {
      const raw = row.hierarchy || "";
      if (raw.includes(" - ")) {
        const parts = raw.split(" - ");
        const brandKey = parts[0].trim();
        const payerKey = parts.slice(1).join(" - ").trim();
        if (!map[brandKey]) map[brandKey] = { mainRow: null, children: [], isScenarioOverlay: row.is_scenario_overlay };
        map[brandKey].children.push({ ...row, cleanLabel: payerKey });
      } else {
        const brandKey = raw.trim();
        if (!map[brandKey]) map[brandKey] = { mainRow: null, children: [], isScenarioOverlay: row.is_scenario_overlay };
        map[brandKey].mainRow = row;
        if (row.is_scenario_overlay) map[brandKey].isScenarioOverlay = true;
      }
    });

    return Object.keys(map).map((brandKey) => {
      const entry = map[brandKey];
      let mainRow = entry.mainRow;
      if (!mainRow) {
        const children = entry.children || [];
        const months =
          chartData?.months ||
          (children[0] ? Object.keys(children[0].monthly_data || {}) : []);
        const monthly_data = {};
        months.forEach((m) => {
          let sum = 0,
            any = false;
          children.forEach((c) => {
            const v = c.monthly_data?.[m];
            if (v != null && !Number.isNaN(Number(v))) {
              sum += Number(v);
              any = true;
            }
          });
          monthly_data[m] = !any ? null : isPercentTab ? 100 : sum;
        });
        mainRow = {
          hierarchy: brandKey,
          monthly_data,
          is_applied: children.some((c) => c.is_applied),
        };
      } else {
        mainRow.monthly_data = mainRow.monthly_data || {};
      }
      return {
        brandName: brandKey,
        mainRow,
        children: entry.children,
        isScenarioOverlay: !!entry.isScenarioOverlay,
      };
    });
  }, [isScenarioGroupedTab, isComboTab, tableData, scenarioOverlayTableRows, chartData, currentlyAppliedScenario]);

  // ── Monthly / Yearly toggle helpers ──────────────────────────────────────
  // displayColumns are the column keys actually rendered in the table header.
  // In monthly mode: raw month strings from chartData.months.
  // In yearly mode: use the yearly months from the backend (pre-computed),
  //                  falling back to extracting unique years from monthly months.
  const displayColumns = useMemo(() => {
    const months = chartData?.months || [];
    if (totalMarketViewMode !== "yearly") return months;
    // Try backend yearly chart months from liverTabsRaw
    const backendKey = TAB_KEY_MAP[activeTab] || activeTab;
    const yearlyMonths = liverTabsRaw?.tabs?.[backendKey]?.yearlyChart?.months;
    if (yearlyMonths?.length) return yearlyMonths;
    // Fallback: extract unique years from monthly months
    const years = [];
    months.forEach((m) => {
      const y = String(m).slice(0, 4);
      if (y && !years.includes(y)) years.push(y);
    });
    return years;
  }, [chartData, totalMarketViewMode, liverTabsRaw, activeTab]);

  // Map of year -> array of underlying month keys, used for aggregation and
  // for forecast-period detection in yearly mode.
  const yearToMonthsMap = useMemo(() => {
    const months = chartData?.months || [];
    const map = {};
    months.forEach((m) => {
      const y = String(m).slice(0, 4);
      if (!map[y]) map[y] = [];
      map[y].push(m);
    });
    return map;
  }, [chartData]);

  const formatColumnLabel = (col) => {
    if (totalMarketViewMode === "yearly") return col;
    return formatDateLabel(col);
  };

  // Looks up a row's value for a given display column.
  // In monthly mode: direct lookup by month key.
  // In yearly mode: backend provides yearly table data so monthly_data is keyed
  //                 by year strings like "2020". Direct lookup works.
  //                 Fallback: aggregate monthly values (for tabs without yearly data).
  const getColumnValue = (row, col) => {
    if (totalMarketViewMode !== "yearly") {
      return row?.monthly_data?.[col];
    }
    // Yearly mode — try direct lookup first (backend yearly table)
    const direct = row?.monthly_data?.[col];
    if (direct != null) return direct;
    // Fallback: sum monthly values that belong to this year
    const monthsInYear = yearToMonthsMap[col] || [];
    let sum = 0, count = 0;
    monthsInYear.forEach((m) => {
      const v = row?.monthly_data?.[m];
      if (v != null && !Number.isNaN(Number(v))) { sum += Number(v); count += 1; }
    });
    if (count === 0) return null;
    return metricUnit === "%" ? sum / count : sum;
  };

  // A column is "forecast" if it falls in the forecast period.
  // Monthly mode: check against chartData.forecast_start_index directly.
  // Yearly mode: check against the yearly chart's forecast_start_index from backend.
  const isForecastColumn = (col) => {
    if (totalMarketViewMode !== "yearly") return isForecastMonth(col);
    const backendKey = TAB_KEY_MAP[activeTab] || activeTab;
    const yearlyChart = liverTabsRaw?.tabs?.[backendKey]?.yearlyChart;
    if (yearlyChart?.months?.length && yearlyChart?.forecast_start_index != null) {
      const fcastYears = yearlyChart.months.slice(yearlyChart.forecast_start_index);
      return fcastYears.includes(col);
    }
    // Fallback: any month in the year is forecast
    const monthsInYear = yearToMonthsMap[col] || [];
    return monthsInYear.some((m) => isForecastMonth(m));
  };

  const safeFrom = (availableDates || []).includes(fromDate) ? fromDate : "";
  const safeTo = toDate;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <Box sx={{ p: 3 }}>
      <Paper
        sx={{
          p: 3,
          borderRadius: "16px",
          border: "1px solid #D8DEE8",
          boxShadow: "none",
          overflow: "hidden",
        }}
      >
        {/* ── TOP FILTER BAR ── */}
        <Box
          sx={{
            p: 3,
            borderBottom: "1px solid #D8DEE8",
            display: "flex",
            alignItems: "end",
            gap: 3,
            flexWrap: "wrap",
            justifyContent: "space-between",
          }}
        >
          <Box
            sx={{
              display: "flex",
              gap: 3,
              flexWrap: "wrap",
              alignItems: "end",
            }}
          >
            <Box>
              <Typography
                sx={{
                  mb: 1,
                  fontSize: "14px",
                  fontWeight: 700,
                  color: "#64748b",
                }}
              >
                THERAPEUTIC AREA
              </Typography>
              <Box
                sx={{
                  height: 35,
                  px: 2,
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                  border: "1px solid #D8DEE8",
                  borderRadius: "8px",
                  backgroundColor: "#d7dde6",
                  minWidth: "150px",
                }}
              >
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    backgroundColor: "#22c55e",
                  }}
                />
                <Typography>{therapyArea}</Typography>
              </Box>
            </Box>

            <Box>
              <Typography
                sx={{
                  mb: 1,
                  fontSize: "14px",
                  fontWeight: 700,
                  color: "#64748b",
                }}
              >
                FROM DATE
              </Typography>
              <FormControl sx={inputStyle}>
                <Select
                  value={safeFrom}
                  onChange={(e) => {
                    setFromDate(e.target.value);
                    setToDate("");
                  }}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        maxHeight: 300,
                        width: 130,
                        "& .MuiMenuItem-root": {
                          minHeight: 32,
                          fontSize: "15px",
                          py: 0.5,
                        },
                      },
                    },
                  }}
                  displayEmpty
                >
                  <MenuItem value="" disabled>
                    Select
                  </MenuItem>
                  {availableDates.map((d) => (
                    <MenuItem key={d} value={d}>
                      {formatDateLabel(d)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            <Box>
              <Typography
                sx={{
                  mb: 1,
                  fontSize: "14px",
                  fontWeight: 700,
                  color: "#64748b",
                }}
              >
                TO DATE
              </Typography>
              <FormControl sx={inputStyle}>
                <Select
                  value={safeTo}
                  onChange={(e) => setToDate(e.target.value)}
                  displayEmpty
                  disabled={!fromDate}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        maxHeight: 300,
                        width: 130,
                        "& .MuiMenuItem-root": {
                          minHeight: 32,
                          fontSize: "15px",
                          py: 0.5,
                        },
                      },
                    },
                  }}
                >
                  <MenuItem value="" disabled>
                    Select
                  </MenuItem>
                  {(() => {
                    const filtered = availableDates.filter((d) => {
                      const pd = parseDateString(d),
                        fd = parseDateString(fromDate);
                      if (!pd.isValid()) return false;
                      if (!fd.isValid()) return true;
                      return pd.isAfter(fd);
                    });
                    const dates =
                      toDate && !filtered.includes(toDate)
                        ? [...filtered, toDate].sort()
                        : filtered;
                    return dates.map((d) => (
                      <MenuItem key={d} value={d}>
                        {formatDateLabel(d)}
                      </MenuItem>
                    ));
                  })()}
                </Select>
              </FormControl>
            </Box>

            <Box>
              <Typography
                sx={{
                  mb: 1,
                  fontSize: "14px",
                  fontWeight: 700,
                  color: "#64748b",
                }}
              >
                PAYER FILTER
              </Typography>
              <FormControl sx={inputStyle}>
                <Select
                  value={payerFilter}
                  onChange={(e) => {
                    const val = e.target.value;
                    setPayerFilter(val);
                    refreshLiverFilters(val, productFilter);
                  }}
                  displayEmpty
                  renderValue={(sel) => {
                    if (!sel) return "Select";
                    const opts = payerOptions?.length
                      ? payerOptions
                      : ["Commercial", "Medicare", "Medicaid"];
                    const found = opts.find((p) =>
                      typeof p === "string"
                        ? p === sel
                        : p.value === sel || p.name === sel,
                    );
                    if (!found) return String(sel);
                    return typeof found === "string"
                      ? found
                      : found.label || found.name || found.value || "";
                  }}
                >
                  {(payerOptions?.length
                    ? payerOptions
                    : ["Commercial", "Medicare", "Medicaid"]
                  ).map((p) => {
                    const val =
                      typeof p === "string" ? p : p.value || p.name || "";
                    const lbl =
                      typeof p === "string"
                        ? p
                        : p.label || p.name || p.value || "";
                    return (
                      <MenuItem key={val} value={val}>
                        {lbl}
                      </MenuItem>
                    );
                  })}
                </Select>
              </FormControl>
            </Box>

            <Box>
              <Typography
                sx={{
                  mb: 1,
                  fontSize: "14px",
                  fontWeight: 700,
                  color: "#64748b",
                }}
              >
                PRODUCT FILTER
              </Typography>
              <FormControl sx={inputStyle}>
                <Select
                  value={productFilter}
                  onChange={(e) => {
                    const val = e.target.value;
                    setProductFilter(val);
                    refreshLiverFilters(payerFilter, val);
                  }}
                  displayEmpty
                  renderValue={(sel) => {
                    if (!sel) return "Select";
                    const opts = productOptions?.length
                      ? productOptions
                      : ["GILD", "ASGA", "others"];
                    const found = opts.find((p) =>
                      typeof p === "string"
                        ? p === sel
                        : p.value === sel || p.name === sel,
                    );
                    if (!found) return String(sel);
                    return typeof found === "string"
                      ? found
                      : found.label || found.name || found.value || "";
                  }}
                >
                  {(productOptions?.length
                    ? productOptions
                    : ["GILD", "ASGA", "others"]
                  ).map((p) => {
                    const val =
                      typeof p === "string" ? p : p.value || p.name || "";
                    const lbl =
                      typeof p === "string"
                        ? p
                        : p.label || p.name || p.value || "";
                    return (
                      <MenuItem key={val} value={val}>
                        {lbl}
                      </MenuItem>
                    );
                  })}
                </Select>
              </FormControl>
            </Box>

            <Button
              variant="contained"
              onClick={handleApplyFilter}
              disabled={!resolveFromDate() || !toDate}
              sx={{
                textTransform: "none",
                borderRadius: "6px",
                backgroundColor: "#4F46E5",
                height: "34px",
                fontSize: "13px",
              }}
            >
              Apply Filter
            </Button>
          </Box>
        </Box>

        {/* ── STATISTICAL PROJECTION ENGINE ── */}
        <Paper
          sx={{
            mt: 3,
            p: 3,
            borderRadius: "16px",
            border: "1px solid #D8DEE8",
            boxShadow: "none",
            backgroundColor: editable ? "#fff" : "#eff6ff",
          }}
        >
          <Box
            display="flex"
            justifyContent="space-between"
            alignItems="center"
            mb={3}
          >
            <Typography
              sx={{
                fontSize: "14px",
                fontWeight: 700,
                color: "#1d4ed8",
                textTransform: "uppercase",
              }}
            >
              STATISTICAL PROJECTION ENGINE
            </Typography>
            <Button
              variant="outlined"
              size="small"
              onClick={() => setEditable(!editable)}
              sx={{ textTransform: "none", borderRadius: "8px" }}
            >
              {editable ? "Lock Factors" : "Edit Factors"}
            </Button>
          </Box>

          <Box
            sx={{
              display: "flex",
              gap: 3,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <Box>
              <Typography
                sx={{
                  mb: 1,
                  fontSize: "14px",
                  fontWeight: 700,
                  color: "#64748b",
                }}
              >
                BASE MODEL
              </Typography>
              <FormControl sx={inputStyle}>
                <Select
                  value={modelSelection}
                  onChange={(e) => setModelSelection(e.target.value)}
                  disabled={!editable}
                >
                  <MenuItem value="ets">Exponential Smoothing (ETS)</MenuItem>
                  <MenuItem value="linear">Linear</MenuItem>
                  <MenuItem value="moving_average">Moving Average</MenuItem>
                  <MenuItem value="exponential">Exponential</MenuItem>
                  <MenuItem value="logarithmic">Logarithmic</MenuItem>
                  <MenuItem value="scurve">S-Curve</MenuItem>
                </Select>
              </FormControl>
            </Box>

            {modelSelection === "ets" && (
              <>
                <Box>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 0.5,
                      mb: 1,
                    }}
                  >
                    <Typography sx={{ fontSize: "14px" }}>LEVEL (α)</Typography>
                    <Tooltip
                      title="Please enter value from 0 to 1"
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{
                          fontSize: 16,
                          color: "#64748b",
                          cursor: "pointer",
                        }}
                      />
                    </Tooltip>
                  </Box>
                  <TextField
                    type="number"
                    value={alpha}
                    disabled={!editable}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === "" || (Number(v) >= 0 && Number(v) <= 1))
                        setAlpha(v);
                    }}
                    inputProps={{ min: 0, max: 1, step: 0.01 }}
                    sx={recalculateInputStyle}
                  />
                </Box>
                <Box>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 0.5,
                      mb: 1,
                    }}
                  >
                    <Typography sx={{ fontSize: "14px" }}>TREND (β)</Typography>
                    <Tooltip
                      title="Please enter value from 0 to 1"
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{
                          fontSize: 16,
                          color: "#64748b",
                          cursor: "pointer",
                        }}
                      />
                    </Tooltip>
                  </Box>
                  <TextField
                    type="number"
                    value={beta}
                    disabled={!editable}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === "" || (Number(v) >= 0 && Number(v) <= 1))
                        setBeta(v);
                    }}
                    inputProps={{ min: 0, max: 1, step: 0.01 }}
                    sx={recalculateInputStyle}
                  />
                </Box>
                <Box>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 0.5,
                      mb: 1,
                    }}
                  >
                    <Typography sx={{ fontSize: "14px" }}>
                      DAMPING (φ)
                    </Typography>
                    <Tooltip
                      title="Please enter value from 0 to 1"
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{
                          fontSize: 16,
                          color: "#64748b",
                          cursor: "pointer",
                        }}
                      />
                    </Tooltip>
                  </Box>
                  <TextField
                    type="number"
                    value={gamma}
                    disabled={!editable}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === "" || (Number(v) >= 0 && Number(v) <= 1))
                        setGamma(v);
                    }}
                    inputProps={{ min: 0, max: 1, step: 0.01 }}
                    sx={recalculateInputStyle}
                  />
                </Box>
              </>
            )}

            {modelSelection === "moving_average" && (
              <>
                <Box>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 0.5,
                      mb: 1,
                    }}
                  >
                    <Typography sx={{ fontSize: "14px" }}>WINDOW</Typography>
                    <Tooltip
                      title="Number of periods to average (e.g. 3 = 3-month rolling average)"
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{
                          fontSize: 16,
                          color: "#64748b",
                          cursor: "pointer",
                        }}
                      />
                    </Tooltip>
                  </Box>
                  <TextField
                    type="number"
                    value={windowSize}
                    disabled={!editable}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === "" || (Number(v) >= 3 && Number(v) <= 24))
                        setWindowSize(v);
                    }}
                    inputProps={{ min: 3, max: 24, step: 1 }}
                    sx={recalculateInputStyle}
                  />
                </Box>
                <Box>
                  <Box
                    sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}
                  >
                    <Typography sx={{ fontSize: "14px" }}>MULTIPLIER</Typography>
                    <Tooltip
                      title="Please enter value from 1 to 5"
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{ fontSize: 16, color: "#64748b", cursor: "pointer" }}
                      />
                    </Tooltip>
                  </Box>
                  <TextField
                    type="number"
                    value={multiplier}
                    disabled={!editable}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === "" || (Number(v) >= 1 && Number(v) <= 5))
                        setMultiplier(v);
                    }}
                    inputProps={{ min: 1, max: 5, step: 0.01 }}
                    sx={recalculateInputStyle}
                  />
                </Box>
                <Box>
                  <Typography sx={{ mb: 1, fontSize: "14px" }}>
                    MULTIPLIER HORIZON
                  </Typography>
                  <FormControl sx={inputStyle}>
                    <Select
                      value={multiplierHorizon}
                      onChange={(e) => setMultiplierHorizon(e.target.value)}
                      disabled={!editable}
                    >
                      <MenuItem value="History">History</MenuItem>
                      <MenuItem value="Forecast">Forecast</MenuItem>
                      <MenuItem value="Both History & Forecast">
                        Both History &amp; Forecast
                      </MenuItem>
                    </Select>
                  </FormControl>
                </Box>
              </>
            )}

            {["linear", "exponential", "logarithmic", "scurve"].includes(
              modelSelection,
            ) && (
                <>
                  <Box>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                        mb: 1,
                      }}
                    >
                      <Typography sx={{ fontSize: "14px" }}>GROWTH %</Typography>
                      <Tooltip
                        title="Please enter the total growth%"
                        arrow
                        placement="top"
                      >
                        <InfoOutlinedIcon
                          sx={{
                            fontSize: 16,
                            color: "#64748b",
                            cursor: "pointer",
                          }}
                        />
                      </Tooltip>
                    </Box>
                    <TextField
                      type="number"
                      value={totalGrowth}
                      disabled={!editable}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v === "" || (Number(v) >= -100 && Number(v) <= 100))
                          setTotalGrowth(v);
                      }}
                      inputProps={{ min: 0, max: 100, step: 0.1 }}
                      sx={recalculateInputStyle}
                    />
                  </Box>
                  <Box>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                        mb: 1,
                      }}
                    >
                      <Typography sx={{ fontSize: "14px" }}>DURATION</Typography>
                      <Tooltip
                        title="Please enter the months"
                        arrow
                        placement="top"
                      >
                        <InfoOutlinedIcon
                          sx={{
                            fontSize: 16,
                            color: "#64748b",
                            cursor: "pointer",
                          }}
                        />
                      </Tooltip>
                    </Box>
                    <TextField
                      type="number"
                      value={duration}
                      disabled={!editable}
                      onChange={(e) => setDuration(Number(e.target.value))}
                      inputProps={{ min: 0, max: 100, step: 1 }}
                      sx={recalculateInputStyle}
                    />
                  </Box>
                  {modelSelection !== "linear" && (
                    <Box>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 0.5,
                          mb: 1,
                        }}
                      >
                        <Typography sx={{ fontSize: "14px" }}>K VALUE</Typography>
                        <Tooltip
                          title="Please enter value from 0 to 3"
                          arrow
                          placement="top"
                        >
                          <InfoOutlinedIcon
                            sx={{
                              fontSize: 16,
                              color: "#64748b",
                              cursor: "pointer",
                            }}
                          />
                        </Tooltip>
                      </Box>
                      <TextField
                        type="number"
                        value={kValue}
                        disabled={!editable}
                        onChange={(e) => {
                          const v = e.target.value;
                          if (v === "" || (Number(v) >= 0 && Number(v) <= 3))
                            setKValue(v);
                        }}
                        inputProps={{ min: 0, max: 3, step: 0.01 }}
                        sx={recalculateInputStyle}
                      />
                    </Box>
                  )}
                  <Box>
                    <Typography sx={{ mb: 1, fontSize: "14px" }}>
                      TRAJECTORY START
                    </Typography>
                    <FormControl sx={recalculateInputStyle}>
                      <Select
                        value={trajectoryStart}
                        onChange={(e) => setTrajectoryStart(e.target.value)}
                        MenuProps={{
                          PaperProps: {
                            sx: {
                              maxHeight: 300,
                              width: 130,
                              "& .MuiMenuItem-root": {
                                minHeight: 32,
                                fontSize: "15px",
                                py: 0.5,
                              },
                            },
                          },
                        }}
                        disabled={!editable}
                        displayEmpty
                        renderValue={(sel) => {
                          // Use dayjs to avoid the UTC-midnight timezone shift
                          // that makes new Date("YYYY-MM-DD") display one day off.
                          if (!sel) return "Select";
                          const p = parseDateString(sel);
                          return p.isValid() ? p.format("MMM-YY") : sel;
                        }}
                      >
                        {(() => {
                          const forecastMonths =
                            chartData?.months && chartData?.forecast_start_index != null
                              ? chartData.months.slice(chartData.forecast_start_index)
                              : trajectoryMonthOptions;

                          // Dropdown shows only months STRICTLY AFTER the
                          // current trajectoryStart — the default value itself
                          // is displayed via renderValue above and acts as the
                          // "current" selection; the list lets the user pick a
                          // later start date.
                          const dropdownOptions = trajectoryStart
                            ? forecastMonths.filter((m) => m > trajectoryStart)
                            : forecastMonths;

                          // Fallback: if nothing passes the filter, show all.
                          const opts = dropdownOptions.length ? dropdownOptions : forecastMonths;

                          return opts.map((m) => (
                            <MenuItem key={m} value={m}>
                              {parseDateString(m).isValid()
                                ? parseDateString(m).format("MMM-YY")
                                : m}
                            </MenuItem>
                          ));
                        })()}
                      </Select>
                    </FormControl>
                  </Box>
                </>
              )}

            {modelSelection !== "moving_average" && (
              <>
                <Box>
                  <Box
                    sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}
                  >
                    <Typography sx={{ fontSize: "14px" }}>MULTIPLIER</Typography>
                    <Tooltip
                      title="Please enter value from 1 to 5"
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{ fontSize: 16, color: "#64748b", cursor: "pointer" }}
                      />
                    </Tooltip>
                  </Box>
                  <TextField
                    type="number"
                    value={multiplier}
                    disabled={!editable}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === "" || (Number(v) >= 1 && Number(v) <= 5))
                        setMultiplier(v);
                    }}
                    inputProps={{ min: 1, max: 5, step: 0.01 }}
                    sx={recalculateInputStyle}
                  />
                </Box>

                <Box>
                  <Typography sx={{ mb: 1, fontSize: "14px" }}>
                    MULTIPLIER HORIZON
                  </Typography>
                  <FormControl sx={inputStyle}>
                    <Select
                      value={multiplierHorizon}
                      onChange={(e) => setMultiplierHorizon(e.target.value)}
                      disabled={!editable}
                    >
                      <MenuItem value="History">History</MenuItem>
                      <MenuItem value="Forecast">Forecast</MenuItem>
                      <MenuItem value="Both History & Forecast">
                        Both History & Forecast
                      </MenuItem>
                    </Select>
                  </FormControl>
                </Box>
              </>
            )}

            <Button
              variant="contained"
              disabled={!editable}
              onClick={handleRecalculate}
              sx={{
                height: "35px",
                mt: 3,
                textTransform: "none",
                backgroundColor: "#4F46E5",
                borderRadius: "8px",
              }}
            >
              Recalculate
            </Button>
          </Box>
        </Paper>

        {/* ── SUB TABS ── */}
        <Box
          sx={{
            mt: 2,
            backgroundColor: "#e2e8f0",
            borderBottom: "1px solid #D8DEE8",
            px: 0.5,
            pt: 0.5,
            display: "flex",
            gap: 0.5,
          }}
        >
          {TABS.map((tab) => (
            <Box
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              sx={{
                px: 2,
                py: 1,
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: 600,
                borderRadius: "6px 6px 0 0",
                color: activeTab === tab.value ? "#4F46E5" : "#64748b",
                backgroundColor:
                  activeTab === tab.value ? "white" : "transparent",
                border:
                  activeTab === tab.value
                    ? "1px solid #D8DEE8"
                    : "1px solid transparent",
                borderBottom:
                  activeTab === tab.value
                    ? "1px solid white"
                    : "1px solid transparent",
                mb: activeTab === tab.value ? "-1px" : 0,
                userSelect: "none",
                "&:hover": {
                  backgroundColor:
                    activeTab === tab.value ? "white" : "#f1f5f9",
                },
              }}
            >
              {tab.label}
            </Box>
          ))}
        </Box>

        {/* ── TAB CONTENT ── */}
        <Box sx={{ p: 3 }}>
          {/* Chart — collapsible, matches HIV's Market Analysis Chart accordion */}
          <Accordion
            defaultExpanded
            disableGutters
            sx={{
              mb: 3,
              borderRadius: "12px !important",
              border: "1px solid #D8DEE8",
              boxShadow: "none",
              overflow: "hidden",
              "&:before": { display: "none" },
            }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography sx={{ fontWeight: 700, fontSize: "16px" }}>
                Market Analysis Chart
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0, pb: 1, px: 1 }}>
              <ForecastChart
                chartData={chartData}
                metricUnit={isPercentTab ? "%" : metricUnit}
                productFilter={appliedProductFilter}
                payerFilter={appliedPayerFilter}
                appliedBrand={appliedBrand}
                activeTab={activeTab}
                appliedScenario={currentlyAppliedScenario}
                selectedCompareScenarios={selectedCompareScenarios}
                userHasCustomizedCompare={userHasCustomizedCompare}
                compareScenarioOptions={compareScenarioOptions}
                rawScenariosData={liverRawData?.scenarios}
                activeMetricKey={toApiMetricKey(metric)}
              />
            </AccordionDetails>
          </Accordion>

          {/* ── MARKET METRICS TABLE ── */}
          <Paper
            id="volumeSection"
            sx={{
              borderRadius: "12px",
              border: "1px solid #D8DEE8",
              boxShadow: "none",
              overflow: "hidden",
            }}
          >
            {/* Table controls row */}
            {/* Shared button/input styling — matches HIV's primaryButtonStyle /
                secondaryButtonStyle / inputStyle in HIVMarketTable.jsx exactly:
                35px height, 8px border radius, and one uniform indigo for
                every "primary" action (Save Scenario, Apply Selected
                Scenario, Save, Refresh all share this — previously Save was
                a one-off green button, which HIV doesn't do). */}
            {(() => {
              const primaryButtonStyle = {
                height: "35px",
                borderRadius: "8px",
                textTransform: "none",
                fontSize: "13px",
                fontWeight: 600,
                backgroundColor: "#4F46E5",
                "&:hover": { backgroundColor: "#4338ca" },
              };
              const secondaryButtonStyle = {
                height: "35px",
                borderRadius: "8px",
                textTransform: "none",
                fontSize: "13px",
                fontWeight: 600,
                borderColor: "#e2e8f0",
                color: "#64748b",
                "&:hover": { borderColor: "#cbd5e1", backgroundColor: "#f8fafc" },
              };
              const tableInputStyle = {
                bgcolor: "#fcfcfd",
                borderRadius: "8px",
                minWidth: "200px",
                "& .MuiOutlinedInput-root": {
                  borderRadius: "8px",
                  height: "35px",
                  backgroundColor: "#fcfcfd",
                },
              };
              return (
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                px: 2,
                py: 2,
                borderBottom: "1px solid #E2E8F0",
                flexWrap: "wrap",
                gap: 1,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                <Typography
                  sx={{
                    fontSize: "16px",
                    fontWeight: 700,
                    color: "#1e293b",
                  }}
                >
                  {activeTabLabel}
                </Typography>

                <Button
                  variant="contained"
                  onClick={() => {
                    setNewScenarioName("");
                    setSaveScenarioDialogOpen(true);
                  }}
                  sx={primaryButtonStyle}
                >
                  Save Scenario
                </Button>

                {groupedTableHierarchy.some((g) => g.children?.length > 0) && (
                  <>
                    <Tooltip title="Expand All">
                      <IconButton size="small" onClick={handleExpandAllRows}>
                        <UnfoldMoreIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Collapse All">
                      <IconButton size="small" onClick={handleCollapseAllRows}>
                        <UnfoldLessIcon />
                      </IconButton>
                    </Tooltip>
                  </>
                )}
              </Box>

              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 1.5,
                  flexWrap: "wrap",
                }}
              >
                {/* Metric filter — non-total_market tabs only */}
                {showMetricFilter && (
                  <FormControl sx={{ ...tableInputStyle, minWidth: "160px" }}>
                    <Select
                      value={metric}
                      onChange={async (e) => {
                        const nm = e.target.value;
                        // Exit edit mode before switching metric so tableSnapshot
                        // is never stale and cancel always restores correct data.
                        if (tableEditing) {
                          setTableData(tableSnapshot);
                          setEditedHierarchies({});
                          setTableEditing(false);
                          setEditable(false);
                        }
                        setMetric(nm);
                        if (nm !== "market_share") setBrand("");
                        if (isHCV && liverRawData) {
                          setLiverTabsRaw(
                            normalizeLiverResponse(liverRawData, nm),
                          );
                        } else {
                          await handleApplyFilterWithMetric(nm);
                        }
                      }}
                      sx={{ fontSize: "13px", fontWeight: 600 }}
                    >
                      {filterOptions.metric_filters.map((item) => (
                        <MenuItem
                          key={item.value}
                          value={item.value}
                          sx={{ fontSize: "13px" }}
                        >
                          {item.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )}

                {/* Monthly / Yearly switch */}
                <Box
                  sx={{
                    display: "flex",
                    bgcolor: "#E2E8F0",
                    borderRadius: "10px",
                    p: "2px",
                  }}
                >
                  {["monthly", "yearly"].map((mode) => (
                    <Button
                      key={mode}
                      onClick={() => {
                        if (mode === totalMarketViewMode) return;
                        setTotalMarketViewMode(mode);
                        if (mode === "yearly" && tableEditing) handleCancelTableEdit();
                      }}
                      sx={{
                        minWidth: 80,
                        height: 30,
                        px: 1.5,
                        py: 0.25,
                        textTransform: "none",
                        borderRadius: "8px",
                        bgcolor: totalMarketViewMode === mode ? "#fff" : "transparent",
                        color: totalMarketViewMode === mode ? "#4F46E5" : "#64748B",
                        boxShadow: totalMarketViewMode === mode ? 1 : "none",
                        "&:hover": {
                          bgcolor: totalMarketViewMode === mode ? "#fff" : "transparent",
                        },
                      }}
                    >
                      {mode.charAt(0).toUpperCase() + mode.slice(1)}
                    </Button>
                  ))}
                </Box>

                {/* Download / Save / Edit Changes / Refresh / Cancel — table edit
                    toolbar, ordered and gated to match HIV's exact layout:
                    Save and Cancel are always visible (not hidden behind
                    tableEditing like before), Save sits before Edit, and
                    Refresh only appears while actively editing, after Edit —
                    see HIVMarketTable.jsx's header row. */}
                <Tooltip title="Download table as CSV">
                  <IconButton
                    size="small"
                    onClick={handleDownloadTable}
                    sx={{
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      width: 32,
                      height: 32,
                      color: "#64748b",
                      "&:hover": { backgroundColor: "#f8fafc" },
                    }}
                  >
                    <DownloadIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </Tooltip>

                <Button
                  variant="contained"
                  disabled={(tableEditing && !isRefreshed) || isSavingEditChanges}
                  onClick={handleConfirmSave}
                  sx={primaryButtonStyle}
                >
                  {isSavingEditChanges ? "Saving..." : "Save"}
                </Button>

                <Button
                  variant="outlined"
                  onClick={handleEnterTableEdit}
                  disabled={
                    tableEditing ||
                    (activeTab !== "total_market" && metric === "market_volume")
                  }
                  sx={secondaryButtonStyle}
                >
                  {tableEditing ? "Editing..." : "Edit Changes"}
                </Button>

                {tableEditing && (
                  <Button
                    variant="contained"
                    disabled={savingTable || Object.keys(editedHierarchies).length === 0}
                    onClick={handleSaveTableChanges}
                    sx={primaryButtonStyle}
                  >
                    {savingTable ? "Refreshing..." : "Refresh"}
                  </Button>
                )}

                <Button
                  variant="outlined"
                  onClick={handleCancelTableEdit}
                  disabled={!tableEditing || totalMarketViewMode === "yearly"}
                  sx={secondaryButtonStyle}
                >
                  Cancel
                </Button>

                {/* Apply Selected Scenario — total_market only */}
                {showScenarioControls && (
                  <Button
                    variant="contained"
                    onClick={applySelectedScenario}
                    sx={primaryButtonStyle}
                  >
                    Apply Selected Scenario
                  </Button>
                )}

                {/* Compare Scenarios — available on every tab. Overlays every
                    checked scenario's line(s)/row(s) on the chart and table,
                    regardless of which tab is active or whether a
                    product/payer is focused. Matches HIV's Compare
                    Scenarios dropdown: a standard MUI multi-select with the
                    applied scenario always checked and locked. */}
                {showCompareScenarios && (
                  <FormControl sx={tableInputStyle}>
                    <Select
                      multiple
                      displayEmpty
                      value={selectedCompareScenarios}
                      onChange={handleCompareScenarioChange}
                      input={<OutlinedInput />}
                      sx={{ fontSize: "13px" }}
                      MenuProps={{ PaperProps: { sx: { maxHeight: 260 } } }}
                      renderValue={(selected) => {
                        if (!selected.length) return "Compare Scenarios";
                        if (selected.length === compareScenarioOptions.length)
                          return "All Scenarios";
                        return selected.join(", ");
                      }}
                    >
                      {compareScenarioOptions.map((option) => {
                        const isActive = option === currentlyAppliedScenario;
                        return (
                          <MenuItem key={option} value={option} disabled={isActive}>
                            <Checkbox
                              size="small"
                              checked={selectedCompareScenarios.includes(option)}
                              disabled={isActive}
                            />
                            <ListItemText
                              primary={isActive ? `${option} (Active)` : option}
                            />
                          </MenuItem>
                        );
                      })}
                    </Select>
                  </FormControl>
                )}
              </Box>
            </Box>
              );
            })()}

            {/* ── TABLE ── */}
            <Box
              sx={{
                backgroundColor: "white",
                maxHeight: 500,
                overflow: "auto",
              }}
            >
              <Box
                component="table"
                sx={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "14px",
                }}
              >
                {/* THEAD */}
                <Box component="thead">
                  <Box component="tr" sx={{ position: "relative", isolation: "isolate" }}>
                    <Box
                      component="th"
                      sx={{
                        position: "sticky",
                        left: 0,
                        top: 0,
                        zIndex: 3,
                        backgroundColor: "#f8fafc",
                        color: "#64748b",
                        fontWeight: 700,
                        fontSize: "14px",
                        textAlign: "left",
                        p: "12px 16px",
                        minWidth: 220,
                        maxWidth: 220,
                        borderRight: "2px solid #e2e8f0",
                        borderBottom: "2px solid #e2e8f0",
                      }}
                    >
                      Scenario
                    </Box>
                    {displayColumns.map((col) => (
                      <Box
                        component="th"
                        key={col}
                        sx={{
                          position: "sticky",
                          top: 0,
                          zIndex: 2,
                          backgroundColor: "#f8fafc",
                          color: "#64748b",
                          fontWeight: 700,
                          fontSize: "14px",
                          textAlign: "center",
                          p: "12px 8px",
                          minWidth: 90,
                          whiteSpace: "nowrap",
                          borderRight: "1px solid #e2e8f0",
                          borderBottom: "2px solid #e2e8f0",
                        }}
                      >
                        {formatColumnLabel(col)}
                      </Box>
                    ))}
                  </Box>
                </Box>

                {/* TBODY */}
                <Box component="tbody">
                  {tableData.length === 0 ? (
                    <>
                      {/* Empty state – Live Engine row */}
                      <Box
                        component="tr"
                        sx={{
                          position: "relative",
                          isolation: "isolate",
                          "&:hover": { backgroundColor: "#f8fafc" },
                        }}
                      >
                        <Box
                          component="td"
                          sx={{
                            position: "sticky",
                            left: 0,
                            zIndex: 1,
                            backgroundColor: "white",
                            borderRight: "1px solid #e2e8f0",
                            borderBottom: "1px solid #f1f5f9",
                            p: "10px 16px",
                          }}
                        >
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 1.5,
                            }}
                          >
                            <input
                              type="radio"
                              name="activeScenarioRadio"
                              value={
                                currentlyAppliedScenario || "Engine Forecast"
                              }
                              checked={
                                tentativeRadioSelectedScenario ===
                                (currentlyAppliedScenario || "Engine Forecast")
                              }
                              onChange={() =>
                                handleActiveScenarioRadioChange(
                                  currentlyAppliedScenario || "Engine Forecast",
                                )
                              }
                              style={{
                                accentColor: "#4F46E5",
                                width: 14,
                                height: 14,
                                margin: 0,
                              }}
                            />
                            <Typography
                              sx={{
                                fontSize: "14px",
                                fontWeight: 700,
                                color: "#0f172a",
                              }}
                            >
                              {currentlyAppliedScenario || "Engine Forecast"}
                            </Typography>
                          </Box>
                        </Box>
                        {displayColumns.map((col, i) => {
                          const isF = isForecastColumn(col);
                          return (
                            <Box
                              component="td"
                              key={i}
                              sx={{
                                p: "10px 8px",
                                textAlign: "center",
                                fontSize: "14px",
                                fontWeight: 700,
                                backgroundColor: isF ? "#ffffff" : "#f8fafc",
                                color: "#0f172a",
                                borderBottom: "1px solid #f1f5f9",
                              }}
                            >
                              —
                            </Box>
                          );
                        })}
                      </Box>

                      {/* Empty state – Compare rows */}
                      {selectedCompareScenarios.map((scen) => {
                        const isApplied = currentlyAppliedScenario === scen;
                        return (
                          <Box
                            component="tr"
                            key={scen}
                            sx={{
                              position: "relative",
                              isolation: "isolate",
                              "&:hover": { backgroundColor: "#f8fafc" },
                            }}
                          >
                            <Box
                              component="td"
                              sx={{
                                position: "sticky",
                                left: 0,
                                zIndex: 1,
                                backgroundColor: "white",
                                borderRight: "1px solid #e2e8f0",
                                borderBottom: "1px solid #f1f5f9",
                                p: "10px 16px",
                              }}
                            >
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 1.5,
                                }}
                              >
                                <input
                                  type="radio"
                                  name="activeScenarioRadio"
                                  value={scen}
                                  checked={
                                    tentativeRadioSelectedScenario === scen
                                  }
                                  onChange={() =>
                                    handleActiveScenarioRadioChange(scen)
                                  }
                                  style={{
                                    accentColor: "#4F46E5",
                                    width: 14,
                                    height: 14,
                                    margin: 0,
                                  }}
                                />
                                <Typography
                                  sx={{
                                    fontSize: "14px",
                                    fontWeight: 600,
                                    color: "#0f172a",
                                  }}
                                >
                                  {scen}
                                </Typography>
                                {isApplied && (
                                  <Typography
                                    component="span"
                                    sx={{
                                      fontSize: "12px",
                                      fontWeight: 600,
                                      color: "#10b981",
                                    }}
                                  >
                                    (Applied)
                                  </Typography>
                                )}
                              </Box>
                            </Box>
                            {displayColumns.map((col, i) => {
                              const isF = isForecastColumn(col);
                              return (
                                <Box
                                  component="td"
                                  key={i}
                                  sx={{
                                    p: "10px 8px",
                                    textAlign: "center",
                                    fontSize: "14px",
                                    fontWeight: 400,
                                    backgroundColor: isF
                                      ? "#ffffff"
                                      : "#f8fafc",
                                    color: "#475569",
                                    borderBottom: "1px solid #f1f5f9",
                                  }}
                                >
                                  —
                                </Box>
                              );
                            })}
                          </Box>
                        );
                      })}
                    </>
                  ) : (
                    <>
                      {groupedTableHierarchy
                        .filter((group) => {
                          // On tabs NOT grouped by scenario: always show all rows.
                          if (activeTab !== "total_market" && !group.isScenarioGroup) return true;
                          // On scenario-grouped tabs (total_market, and now
                          // Payer-Product/Product-Payer): only filter once the
                          // user has explicitly toggled the Compare Scenarios
                          // checkboxes. Before that, show every scenario so
                          // they're all visible on initial load / apply-filter.
                          if (!userHasCustomizedCompare) return true;
                          if (!selectedCompareScenarios.length) return true;
                          return (
                            group.brandName === currentlyAppliedScenario ||
                            selectedCompareScenarios.includes(group.brandName)
                          );
                        })
                        .map((group) => {
                          const isExpanded = !!expandedBrands[group.brandName];
                          const hasChildren = group.children.length > 0;
                          const showChildren = isExpanded;

                          const mainRowApplied = group.mainRow?.is_applied;
                          const isSelected =
                            tentativeRadioSelectedScenario === group.brandName;

                          const currentBrand = (
                            appliedProductFilter ||
                            appliedBrand ||
                            ""
                          ).toLowerCase();

                          const currentPayer = (appliedPayerFilter || "").toLowerCase();

                          const targetParentLabel = (
                            group.brandName || ""
                          )
                            .split(" (")[0]
                            .trim()
                            .toLowerCase();

                          let isAppliedParent = false;

                          if (activeTab === "prod_dist") {
                            isAppliedParent = targetParentLabel === currentBrand;
                          } else if (activeTab === "payer_dist") {
                            isAppliedParent = targetParentLabel === currentPayer;
                          } else if (group.isScenarioGroup) {
                            // Parent rows are scenario names here (combo
                            // tabs only) — highlight the applied scenario's
                            // group instead of trying to match the focused
                            // payer/product filter against it (that
                            // matching happens at the child level).
                            isAppliedParent = !group.isScenarioOverlay;
                          }

                          // Rows whose label starts with "Total" are always
                          // aggregates and must never be editable, even if they
                          // have no children in the grouped structure.
                          const isTotalRow =
                            (group.brandName || "").trim().toLowerCase().startsWith("total");

                          // On Product/Payer Distribution, comparison-scenario
                          // rows already show "(ScenarioName)" in the label
                          // (baked in via scenarioOverlayTableRows), but the
                          // applied/base scenario's own rows didn't show
                          // anything — inconsistent, and ambiguous once more
                          // than one scenario is being compared. Add the same
                          // bracket to the applied scenario's rows too, for
                          // display only (group.brandName itself stays clean,
                          // since it's also used as the edit/save key).
                          const showsAppliedScenarioTag =
                            (activeTab === "prod_dist" || activeTab === "payer_dist") &&
                            !group.isScenarioOverlay &&
                            !isTotalRow &&
                            compareScenarioOptions.length > 1;
                          const displayBrandName = showsAppliedScenarioTag
                            ? `${group.brandName} (${currentlyAppliedScenario || "Base"})`
                            : group.brandName;

                          // total_market tab: only the radio-selected scenario row
                          // is editable. Other tabs: only leaf rows (no children,
                          // not a Total row) are editable.
                          const isEditEligible = (() => {
                            if (!tableEditing) return false;
                            if (totalMarketViewMode !== "monthly") return false;
                            if (isTotalRow) return false;
                            if (group.isScenarioOverlay) return false;
                            if (activeTab === "total_market") {
                              return isSelected && !hasChildren;
                            }
                            return !hasChildren;
                          })();

                          return (
                            <React.Fragment key={group.brandName}>
                              {/* Parent */}
                              <Box
                                component="tr"
                                onClick={() => {
                                  if (hasChildren) {
                                    toggleBrandExpand(group.brandName);
                                  }
                                }}
                                sx={{
                                  cursor: hasChildren ? "pointer" : "default",

                                  position: "relative",
                                  isolation: "isolate",

                                  backgroundColor:
                                    (isSelected && activeTab === "total_market")
                                      ? "#fffbeb"
                                      : hasChildren
                                        ? "#f8fafc"
                                        : "white",

                                  "&:hover": {
                                    backgroundColor:
                                      (isSelected && activeTab === "total_market")
                                        ? "#fff3c4"
                                        : hasChildren
                                          ? "#f1f5f9"
                                          : "#f8fafc",
                                  },
                                }}
                              >
                                <Box
                                  component="td"
                                  sx={{
                                    position: "sticky",
                                    left: 0,
                                    zIndex: 1,
                                    minWidth: 220,
                                    maxWidth: 220,

                                    backgroundColor: isAppliedParent
                                      ? "#fffbeb"
                                      : (isSelected && activeTab === "total_market")
                                        ? "#fffbeb"
                                        : isTotalRow
                                          ? "#f1f5f9"
                                          : hasChildren
                                            ? "#f8fafc"
                                            : "white",

                                    borderRight: "2px solid #e2e8f0",

                                    borderBottom: isTotalRow
                                      ? "2px solid #e2e8f0"
                                      : "1px solid #e2e8f0",

                                    p: "10px 16px",
                                  }}
                                >
                                  <Box
                                    sx={{
                                      display: "flex",
                                      alignItems: "center",
                                      gap: 1,
                                    }}
                                  >
                                    {activeTab === "total_market" && (
                                      <input
                                        type="radio"
                                        checked={isSelected}
                                        value={group.brandName}
                                        onChange={(e) => {
                                          e.stopPropagation();
                                          handleActiveScenarioRadioChange(
                                            group.brandName,
                                          );
                                        }}
                                        style={{
                                          accentColor: "#4F46E5",
                                          width: 14,
                                          height: 14,
                                          margin: 0,
                                        }}
                                      />
                                    )}

                                    {hasChildren && (
                                      <Typography
                                        component="span"
                                        sx={{
                                          fontSize: "9px",
                                          fontWeight: 700,
                                          width: "14px",
                                          flexShrink: 0,
                                          color: (isAppliedParent || (isSelected && activeTab === "total_market"))
                                            ? "#f59e0b"
                                            : "#64748b",
                                        }}
                                      >
                                        {isExpanded ? "▼" : "▶"}
                                      </Typography>
                                    )}

                                    <Typography
                                      sx={{
                                        fontSize: "14px",
                                        fontWeight: isTotalRow
                                          ? 800
                                          : hasChildren
                                            ? 700
                                            : (isSelected && activeTab === "total_market")
                                              ? 700
                                              : 500,
                                        color: isAppliedParent
                                          ? "#f59e0b"
                                          : (isSelected && activeTab === "total_market")
                                            ? "#f59e0b"
                                            : isTotalRow
                                              ? "#1e293b"
                                              : "#334155",
                                      }}
                                    >
                                      {displayBrandName}
                                    </Typography>

                                  </Box>
                                </Box>

                                {displayColumns.map((col) => {
                                  const val = getColumnValue(group.mainRow, col);
                                  const isF = isForecastColumn(col);
                                  const isEditableCell = isEditEligible;

                                  return (
                                    <Box
                                      component='td'
                                      key={col}
                                      onClick={(e) => isEditableCell && e.stopPropagation()}
                                      sx={{
                                        p: isEditableCell ? '4px 3px' : '10px 8px',
                                        textAlign: 'center',
                                        fontSize: '14px',
                                        minWidth: 90,
                                        fontWeight: isTotalRow ? 800 : hasChildren ? 700 : 500,
                                        backgroundColor: isEditableCell
                                          ? isF ? '#eff6ff' : '#f8fafc'
                                          : (isAppliedParent || (activeTab === 'total_market' && isSelected)) && isF
                                            ? '#fffbeb'
                                            : isF ? '#ffffff' : '#F1F5F9',
                                        color: !isEditableCell && (isAppliedParent || (activeTab === 'total_market' && isSelected)) && isF
                                          ? '#f59e0b'
                                          : '#334155',
                                        borderRight: '1px solid #e2e8f0',
                                      }}
                                    >
                                      {isEditableCell ? (
                                        <input
                                          value={val == null ? '' : metricUnit === '%'
                                            ? (Number.isInteger(Number(val)) ? String(Number(val)) : parseFloat(Number(val).toFixed(2)).toString())
                                            : String(Math.round(Number(val)))}
                                          onChange={(e) => {
                                            if (/^-?\d*\.?\d*$/.test(e.target.value)) {
                                              handleCellChange(group.brandName, col, e.target.value);
                                            }
                                          }}
                                          style={{
                                            width: '72px',
                                            height: '22px',
                                            boxSizing: 'border-box',
                                            border: '1px solid #93c5fd',
                                            borderRadius: '4px',
                                            outline: 'none',
                                            background: '#eff6ff',
                                            color: '#1e293b',
                                            textAlign: 'center',
                                            fontSize: '12px',
                                            padding: '1px 4px',
                                          }}
                                        />
                                      ) : (
                                        formatCellValue(val)
                                      )}
                                    </Box>
                                  );
                                })}
                              </Box>

                          {showChildren &&
                            group.children.map((childRow, idx) => {
                              const childLabel = (childRow.cleanLabel || "").toLowerCase();
                              let isAppliedChild = false;
                              if (group.isScenarioGroup && !group.isScenarioOverlay) {
                                if (activeTab === "prod_dist") {
                                  isAppliedChild = !!currentBrand && childLabel === currentBrand;
                                } else if (activeTab === "payer_dist") {
                                  isAppliedChild = !!currentPayer && childLabel === currentPayer;
                                } else if (currentBrand || currentPayer) {
                                  // Payer-Product / Product-Payer: children
                                  // are full "Payer - Product" combo rows —
                                  // match against whichever of payer/product
                                  // is currently focused.
                                  const matchesBrand = !currentBrand || childLabel.includes(currentBrand);
                                  const matchesPayer = !currentPayer || childLabel.includes(currentPayer);
                                  isAppliedChild = matchesBrand && matchesPayer;
                                }
                              }
                              const isHighlightedChild = isAppliedChild;

                                  return (
                                    <Box component="tr" key={idx} sx={{ position: "relative", isolation: "isolate" }}>
                                      {/* Sticky label cell */}
                                      <Box
                                        component="td"
                                        sx={{
                                          position: "sticky",
                                          left: 0,
                                          zIndex: 1,
                                          minWidth: 220,
                                          maxWidth: 220,
                                          backgroundColor: isHighlightedChild ? "#fffbeb" : "white",
                                          borderRight: "2px solid #e2e8f0",
                                          pl: "32px",
                                          p: "10px 16px",
                                        }}
                                      >
                                        <Typography
                                          sx={{
                                            fontSize: "14px",
                                            fontWeight: 500,
                                            color: isHighlightedChild ? "#f59e0b" : "#334155",
                                          }}
                                        >
                                          {childRow.cleanLabel}
                                        </Typography>
                                      </Box>

                                      {/* Data cells */}
                                      {displayColumns.map((col) => {
                                        const isFChild = isForecastColumn(col);
                                        const childVal = childRow?.monthly_data?.[col];
                                        const isEditableChild =
                                          tableEditing &&
                                          totalMarketViewMode === "monthly" &&
                                          activeTab !== "total_market" &&
                                          !isTotalRow &&
                                          !group.isScenarioOverlay;

                                        return (
                                          <Box
                                            component='td'
                                            key={col}
                                            sx={{
                                              p: isEditableChild ? '4px 3px' : '10px 8px',
                                              textAlign: 'center',
                                              fontSize: '14px',
                                              minWidth: 90,
                                              fontWeight: 500,
                                              backgroundColor: isEditableChild
                                                ? isFChild ? '#eff6ff' : '#f8fafc'
                                                : isHighlightedChild && isFChild ? '#fffbeb' : isFChild ? '#ffffff' : '#F1F5F9',
                                              color: !isEditableChild && isHighlightedChild && isFChild ? '#f59e0b' : '#334155',
                                              borderRight: '1px solid #e2e8f0',
                                            }}
                                          >
                                            {isEditableChild ? (
                                              <input
                                                value={childVal == null ? '' : metricUnit === '%'
                                                  ? (Number.isInteger(Number(childVal)) ? String(Number(childVal)) : parseFloat(Number(childVal).toFixed(2)).toString())
                                                  : String(Math.round(Number(childVal)))}
                                                onChange={(e) => {
                                                  if (/^-?\d*\.?\d*$/.test(e.target.value)) {
                                                    handleCellChange(childRow.hierarchy, col, e.target.value);
                                                  }
                                                }}
                                                style={{
                                                  width: '72px',
                                                  height: '22px',
                                                  boxSizing: 'border-box',
                                                  border: '1px solid #93c5fd',
                                                  borderRadius: '4px',
                                                  outline: 'none',
                                                  background: '#eff6ff',
                                                  color: '#1e293b',
                                                  textAlign: 'center',
                                                  fontSize: '12px',
                                                  padding: '1px 4px',
                                                }}
                                              />
                                            ) : (
                                              formatCellValue(getColumnValue(childRow, col))
                                            )}
                                          </Box>
                                        );
                                      })}
                                    </Box>
                                  );
                                })}
                            </React.Fragment>
                          );
                        })}

                      {/* Saved-scenario rows — appear immediately after Save
                        Scenario without reloading chart/table data. Radio is
                        active so the user can click Apply Selected Scenario. */}
                      {activeTab === "total_market" && savedScenarioRows
                        .filter(
                          (name) =>
                            !groupedTableHierarchy.some(
                              (g) => g.brandName === name,
                            ),
                        )
                        .map((name) => {
                          const isSelected =
                            tentativeRadioSelectedScenario === name;
                          return (
                            <Box
                              component="tr"
                              key={`saved-${name}`}
                              sx={{
                                position: "relative",
                                isolation: "isolate",
                                backgroundColor: isSelected ? "#fffbeb" : "white",
                                "&:hover": { backgroundColor: isSelected ? "#fff3c4" : "#f8fafc" },
                              }}
                            >
                              <Box
                                component="td"
                                sx={{
                                  position: "sticky",
                                  left: 0,
                                  zIndex: 1,
                                  backgroundColor: isSelected ? "#fffbeb" : "white",
                                  borderRight: "1px solid #e2e8f0",
                                  borderBottom: "1px solid #f1f5f9",
                                  p: "10px 16px",
                                }}
                              >
                                <Box
                                  sx={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 1.5,
                                  }}
                                >
                                  <input
                                    type="radio"
                                    name="activeScenarioRadio"
                                    value={name}
                                    checked={isSelected}
                                    onChange={() =>
                                      handleActiveScenarioRadioChange(name)
                                    }
                                    style={{
                                      accentColor: "#4F46E5",
                                      width: 14,
                                      height: 14,
                                      margin: 0,
                                    }}
                                  />
                                  <Typography
                                    sx={{
                                      fontSize: "14px",
                                      fontWeight: isSelected ? 700 : 600,
                                      color: isSelected ? "#f59e0b" : "#0f172a",
                                    }}
                                  >
                                    {name}
                                  </Typography>
                                </Box>
                              </Box>
                              {displayColumns.map((col, i) => {
                                const isF = isForecastColumn(col);
                                return (
                                  <Box
                                    component="td"
                                    key={i}
                                    sx={{
                                      p: "10px 8px",
                                      textAlign: "center",
                                      fontSize: "14px",
                                      backgroundColor: isF ? "#ffffff" : "#f8fafc",
                                      color: "#94a3b8",
                                      borderBottom: "1px solid #f1f5f9",
                                    }}
                                  >
                                    —
                                  </Box>
                                );
                              })}
                            </Box>
                          );
                        })}
                    </>
                  )}
                </Box>
              </Box>
            </Box>
          </Paper>
        </Box>
      </Paper>

      {/* ── Save Scenario Dialog ── */}
      <Dialog
        open={saveScenarioDialogOpen}
        onClose={() => setSaveScenarioDialogOpen(false)}
        maxWidth="xs"
        fullWidth
        PaperProps={{ sx: { borderRadius: "12px" } }}
      >
        <DialogTitle sx={{ fontWeight: 700, fontSize: "16px", color: "#0f172a", pb: 1 }}>
          Save as New Scenario
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: "13px", color: "#64748b", mb: 2 }}>
            {(currentlyAppliedScenario || scenarioSelector || "").toLowerCase() === "base"
              ? "The Base scenario cannot be modified. Enter a name to save your changes as a new scenario."
              : "Enter a name for this scenario. It will appear in the table as a selectable row — click \"Apply Selected Scenario\" to load its data."}
          </Typography>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label="Scenario name"
            value={newScenarioName}
            onChange={(e) => setNewScenarioName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && newScenarioName.trim()) {
                setSaveScenarioDialogOpen(false);
                handleSaveScenario(newScenarioName.trim());
              }
            }}
            sx={{ "& .MuiOutlinedInput-root": { borderRadius: "8px" } }}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
          <Button
            variant="outlined"
            onClick={() => setSaveScenarioDialogOpen(false)}
            sx={{ textTransform: "none", borderRadius: "8px", color: "#64748b", borderColor: "#e2e8f0" }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={!newScenarioName.trim()}
            onClick={() => {
              setSaveScenarioDialogOpen(false);
              handleSaveScenario(newScenarioName.trim());
            }}
            sx={{ textTransform: "none", borderRadius: "8px", backgroundColor: "#4F46E5" }}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}