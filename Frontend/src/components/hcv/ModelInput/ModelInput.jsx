import React, { useState, useEffect, useContext, useMemo, useRef } from "react";
import {
  Box,
  Paper,
  Typography,
  FormControl,
  Select,
  MenuItem,
  TextField,
  Button,
  ToggleButton,
  ToggleButtonGroup,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
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
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import Tooltip from "@mui/material/Tooltip";
import dayjs from "dayjs";
import ModelInputChart from "./ModelInputChart";
import ModelInputTable from "./ModelInputTable";

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
  // Same pattern for From/To Date — the chart clips comparison scenarios
  // to this range, so it must only change on Apply Filter, not while the
  // user is still picking dates.
  const [appliedFromDate, setAppliedFromDate] = useState("");
  const [appliedToDate, setAppliedToDate] = useState("");
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
    if (!s) return dayjs(NaN);
    const strict = dayjs(s, DATE_INPUT_FORMATS, true);
    if (strict.isValid()) return strict;
    const relaxed = dayjs(s);
    return relaxed.isValid() ? relaxed : dayjs(NaN);
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
      // Prioritize the active model's own bucket (e.g. "linear",
      // "exponential", "scurve") over the generic "growth" bucket. The
      // outgoing payload always sends both, so a response that also
      // contains both was previously read growth-first — silently
      // discarding whatever trajectory_start/total_growth/duration/k_value
      // the user had just applied for the actually-selected model and
      // replacing it with growth's (often stale/default) values.
      const traj = factors?.[activeModel] || factors?.growth || {};
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
      let yearlyChart = rawYearlyChart ? parseChartObj(rawYearlyChart, [], 0, isTabPercent) : null;
      const yearlyTable = rawYearlyTable ? parseTableObj(rawYearlyTable, yearlyChart?.months || [], isTabPercent) : null;

      // The backend's yearly.chart.series can be present but only
      // PARTIALLY populated — some entities get real history/forecast
      // arrays, others get empty placeholder arrays (e.g. only the
      // currently focused payer/product combo has real yearly numbers,
      // its siblings come back as empty stubs). The yearly TABLE reliably
      // has complete data for every entity (same rows/children the table
      // view already renders correctly), so: drop any chart series entries
      // that are entirely empty, then fill in whatever's missing — by
      // label — from the table's own rows/children.
      const hasRealValues = (s) =>
        (s?.train_values || []).some((v) => v != null) ||
        (s?.forecast_values || []).some((v) => v != null);

      if (yearlyChart) {
        yearlyChart = { ...yearlyChart, series: (yearlyChart.series || []).filter(hasRealValues) };
      }

      // Skip the trivial single-row case (Total Market Volume, "Base") —
      // it already gets complete data directly from the backend and has
      // its own separate per-scenario rebuild further below.
      if (yearlyTable?.rows?.length && (yearlyTable.rows.length > 1 || yearlyTable.type === "hierarchy")) {
        const yearlyHeaders = yearlyTable.headers || yearlyChart?.months || [];
        const yearlyFsi = yearlyChart?.forecast_start_index ?? (() => {
          // Only estimate when the backend gave us no yearly chart at all
          // (no forecast_start_index to trust) — otherwise use its own value.
          const firstForecastMonth = chart.months?.[chart.forecast_start_index];
          if (!firstForecastMonth) return yearlyHeaders.length;
          const cutoffYear = String(firstForecastMonth).slice(0, 4);
          const idx = yearlyHeaders.findIndex((h) => String(h || "").startsWith(cutoffYear));
          return idx !== -1 ? idx : yearlyHeaders.length;
        })();

        // Flattens table rows (and their children, for hierarchy tabs) into
        // the same "Parent - Child" label convention the chart's own series
        // already use (e.g. "Cash - ASGA").
        const flattenTableRows = (rows) => {
          const out = [];
          (rows || []).forEach((r) => {
            const label = r.label || r.hierarchy || "";
            if (r.children?.length) {
              r.children.forEach((c) => {
                out.push({ label: `${label} - ${c.label}`, values: c.values || [] });
              });
            } else if (label) {
              out.push({ label, values: Array.isArray(r.total) ? r.total : r.values || [] });
            }
          });
          return out;
        };

        const existingLabels = new Set((yearlyChart?.series || []).map((s) => s.label));
        const missingSeries = flattenTableRows(yearlyTable.rows)
          .filter((r) => !existingLabels.has(r.label))
          .map((r) => ({
            label: r.label,
            lot: r.label,
            train_values: r.values.slice(0, yearlyFsi),
            forecast_values: r.values.slice(yearlyFsi),
          }));

        if (missingSeries.length) {
          yearlyChart = {
            months: yearlyChart?.months?.length ? yearlyChart.months : yearlyHeaders,
            forecast_start_index: yearlyFsi,
            series: [...(yearlyChart?.series || []), ...missingSeries],
          };
        }
      }

      tabs[tabKey] = { chart, table, yearlyChart, yearlyTable };

      // Diagnostic: confirms whether yearlyChart is actually built with
      // real series data at this point, for tabs where the raw API
      // response has proven to contain complete yearly.chart data. If
      // this logs "series: 0" or similar, the gap is in this build step;
      // if it logs real series counts here but the chart still doesn't
      // switch, the gap is downstream (in the render, or in how the
      // Monthly/Yearly toggle reaches the chart component).
      if (
        ["product_distribution", "payer_distribution", "payer_product", "product_payer"].includes(
          tabKey,
        )
      ) {
        console.log(`[ModelInput yearlyChart debug] tab="${tabKey}"`, {
          rawYearlyChartPresent: !!rawYearlyChart,
          rawYearlyChartSeriesCount: rawYearlyChart?.series?.length ?? "n/a",
          builtYearlyChartSeriesCount: yearlyChart?.series?.length ?? 0,
          builtYearlyChartMonths: yearlyChart?.months,
          builtYearlyChartSeriesLabels: (yearlyChart?.series || []).map((s) => s.label),
        });
      }

      // Diagnostic: if Payer Volume table rows are empty/all-null while
      // Payer Share has real data for the same tab, that confirms the gap
      // is in the backend response (payer_volume missing/empty) rather
      // than a frontend rendering bug — check this tab's payer_volume key
      // in the Network tab's apply-filters response if this logs.
      if (tabKey !== "total_market_volume") {
        const volRows = tableTabObj?.payer_volume?.monthly?.table?.rows || [];
        const shareRows = tableTabObj?.payer_share?.monthly?.table?.rows || [];
        const hasAnyVolumeValue = volRows.some(
          (r) =>
            (r.values || []).some((v) => v != null) ||
            (r.children || []).some((c) => (c.values || []).some((v) => v != null)),
        );
        const hasAnyShareValue = shareRows.some(
          (r) =>
            (r.values || []).some((v) => v != null) ||
            (r.children || []).some((c) => (c.values || []).some((v) => v != null)),
        );
        if (shareRows.length && hasAnyShareValue && (!volRows.length || !hasAnyVolumeValue)) {
          console.warn(
            `[ModelInput] "${tabKey}": payer_volume rows are empty/all-null while payer_share has data — this is a backend data gap, not a frontend rendering issue.`,
            { payer_volume: tableTabObj?.payer_volume, payer_share: tableTabObj?.payer_share },
          );
        }
      }

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
          let vals = parseValues(firstRow.values, false);
          if (!vals.length) return; // no actual values — skip

          // Align scenario values to the chart month axis (months = active scenario's
          // months for the current date filter). A saved scenario may have been
          // persisted with a wider or narrower date window, so its values array can be
          // a different length. Without alignment, value[i] is plotted at chart
          // position i regardless of the actual month, causing values to appear to
          // "change" whenever the date filter shifts the month axis.
          const scenarioMonths = metricObj?.monthly?.chart?.months || [];
          if (scenarioMonths.length > 0 && months.length > 0 && scenarioMonths.length !== months.length) {
            const monthToVal = {};
            scenarioMonths.forEach((m, i) => {
              monthToVal[(m || "").substring(0, 7)] = vals[i];
            });
            vals = months.map((m) => monthToVal[(m || "").substring(0, 7)] ?? null);
          }

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
          const yearlyChartMonthsRef = tmvTab.yearlyChart?.months || [];
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
            let yearlyVals = parseValues(firstYearlyRow.values, false);
            if (!yearlyVals.length) return;

            // Align yearly values to the active scenario's yearly month axis
            const scenarioYearlyMonths = metricObj?.yearly?.chart?.months || [];
            if (scenarioYearlyMonths.length > 0 && yearlyChartMonthsRef.length > 0 && scenarioYearlyMonths.length !== yearlyChartMonthsRef.length) {
              const yearToVal = {};
              scenarioYearlyMonths.forEach((m, i) => {
                yearToVal[(m || "").substring(0, 4)] = yearlyVals[i];
              });
              yearlyVals = yearlyChartMonthsRef.map((m) => yearToVal[(m || "").substring(0, 4)] ?? null);
            }

            yearlyScenarioRows.push({
              hierarchy: scenarioName,
              label: scenarioName,
              total: undefined,
              values: yearlyVals,
              children: [],
            });
          });

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
                ...(tmvTab.yearlyTable || { type: "flat", headers: yearlyChartMonthsRef }),
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

    // Chart and table both switch to yearly backend data (pre-computed by
    // the API) when in yearly mode — previously only the table did this;
    // the chart always stayed on monthly data regardless of view mode.
    const activeTableData = (viewMode === "yearly" && tab.yearlyTable) ? tab.yearlyTable : tab.table;
    const activeChartData = (viewMode === "yearly" && tab.yearlyChart) ? tab.yearlyChart : tab.chart;
    // Sliced to a new array (not just referenced) so nothing downstream can
    // ever mutate liverTabsRaw's own month arrays in place — see the note
    // on displayColumns for why that class of bug matters here.
    const activeMonths = (viewMode === "yearly" && tab.yearlyChart) ? (tab.yearlyChart.months || []).slice() : months.slice();
    const activeFsi = (viewMode === "yearly" && tab.yearlyChart)
      ? (tab.yearlyChart.forecast_start_index || 0)
      : fsi;

    const series = (activeChartData?.series || [])
      .filter((s) => {
        const lbl = (s.label || "").toLowerCase();
        if (
          lbl.includes("total") ||
          lbl.includes("market volume") ||
          lbl.includes("market share")
        ) return false;
        // Scenario-labeled series (TMV compare): only show if checked in the dropdown
        if (compareScenarioOptions.includes(s.label)) {
          return selectedCompareScenarios.includes(s.label);
        }
        return true;
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
        const candidateTabChart =
          (viewMode === "yearly" && tabs[k]?.yearlyChart) ? tabs[k].yearlyChart : tabs[k]?.chart;
        if (candidateTabChart?.series?.length) {
          candidate = candidateTabChart.series;
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
          const lbl = activeChartData?.series?.[0]?.label || "Summary Metrics";
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

    const headers = activeTableData?.headers || activeMonths;
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
      chart: { months: activeMonths, forecast_start_index: activeFsi, series, scenarioSeries: tab.scenarioSeries || null },
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
    console.log("[ModelInput chartData debug]", {
      activeTab,
      totalMarketViewMode,
      chartMonths: chart?.months,
      chartSeriesCount: chart?.series?.length ?? 0,
      chartSeriesLabels: (chart?.series || []).map((s) => s.label),
    });
    setChartData(chart);
    setTableData(table);
    // Auto-expand the applied/filtered parent row so it doesn't collapse
    // back to nothing on every data change (tab switch, apply filter,
    // refresh, etc.) — the user shouldn't have to manually re-open it
    // each time.
    if (activeTab === "payer_prod") {
      const key = appliedPayerFilter || payerFilter;
      // Parent labels are always scenario-tagged now, even for the applied
      // scenario (e.g. "PayerA (Base Case)") — match that format.
      const taggedKey = key && currentlyAppliedScenario ? `${key} (${currentlyAppliedScenario})` : key;
      setExpandedBrands(taggedKey ? { [taggedKey]: true } : {});
    } else if (activeTab === "prod_payer") {
      const key = appliedProductFilter || productFilter;
      const taggedKey = key && currentlyAppliedScenario ? `${key} (${currentlyAppliedScenario})` : key;
      setExpandedBrands(taggedKey ? { [taggedKey]: true } : {});
    } else if (activeTab === "prod_dist" || activeTab === "payer_dist") {
      // These group by scenario (collapsible) — auto-expand whichever
      // scenario is currently applied.
      setExpandedBrands(currentlyAppliedScenario ? { [currentlyAppliedScenario]: true } : {});
    } else {
      setExpandedBrands({});
    }
  }, [activeTab, liverTabsRaw, totalMarketViewMode, currentlyAppliedScenario]);

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
        // Saved filter (sfInitial) takes priority: it reflects the user's last
        // explicit apply. Fall back to config dates only when there is no saved state.
        if (!localPayer)
          localPayer =
            sfInitial.payer ||
            (norm.payers?.length ? getFirstOption(norm.payers) : "");
        if (!localProduct)
          localProduct =
            sfInitial.product ||
            (norm.products?.length ? getFirstOption(norm.products) : "");
        // Saved filter overrides config: the user's last explicit apply is the source of truth.
        // fromDate must match an availableDates entry exactly (Mon-YY format) for safeFrom to work.
        if (sfInitial.start_date) {
          const sfStartParsed = parseDateString(sfInitial.start_date);
          const matchedFrom = sfStartParsed.isValid()
            ? availMonths.find((d) => {
                const pd = parseDateString(d);
                return pd.isValid() && pd.year() === sfStartParsed.year() && pd.month() === sfStartParsed.month();
              })
            : null;
          localFrom = matchedFrom || sfInitial.start_date;
        }
        if (sfInitial.end_date) localTo = sfInitial.end_date;

        setFromDate(localFrom);
        setToDate(localTo);
        setPayerFilter(localPayer);
        setProductFilter(localProduct);
        // Stamp the applied values immediately so the default highlight
        // shows on first load without waiting for an explicit Apply click.
        setAppliedPayerFilter(localPayer);
        setAppliedProductFilter(localProduct);
        setAppliedFromDate(localFrom);
        setAppliedToDate(localTo);

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
            from_date: toYearMonth(localFrom || cfg?.train_start_date || ""),
            to_date: sfInitial.end_date || undefined,
            scenario: sfInitial.scenario || "Base",
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

          // Dates resolved by the backend — normalise start_date to Mon-YY format
          // so it matches an availableDates entry and safeFrom resolves correctly.
          const sf = data?.selected_filter || {};
          if (sf.start_date) {
            const sfP = parseDateString(sf.start_date);
            const matchedSfFrom = sfP.isValid()
              ? availMonths.find((d) => {
                  const pd = parseDateString(d);
                  return pd.isValid() && pd.year() === sfP.year() && pd.month() === sfP.month();
                })
              : null;
            setFromDate(matchedSfFrom || sf.start_date);
          }
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
      setAppliedFromDate(df.from_date || "");
      setAppliedToDate(df.to_date || "");
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
  // NOTE: Payer/Product filter changes are pure local state — no API call
  // fires until the user explicitly clicks "Apply Filter". (Previously a
  // refreshLiverFilters() call fired on every dropdown change to keep the
  // From/To Date options in sync with the new payer/product; removed since
  // that's still an API call happening before Apply Filter is clicked.)

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
        setAppliedFromDate(fromDate);
        setAppliedToDate(toDate);
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
        const _p = buildLiverBasePayload();
        const response = await applyLiverFilters(_p);
        const data = response?.data || {};
        setAppliedLot(lot);
        setAppliedBrand(productFilter || brand);
        setAppliedPayerFilter(payerFilter);
        setAppliedProductFilter(productFilter);
        setAppliedFromDate(fromDate);
        setAppliedToDate(toDate);
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

  // Switches the active metric (Market Volume / Market Share) for the table.
  // Exits table edit mode first so the snapshot is never stale, then either
  // re-derives locally from cached raw data (HCV) or re-applies filters.
  const handleMetricChange = async (nm) => {
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
      setLiverTabsRaw(normalizeLiverResponse(liverRawData, nm));
    } else {
      await handleApplyFilterWithMetric(nm);
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
              <ModelInputChart
                chartData={chartData}
                metricUnit={isPercentTab ? "%" : metricUnit}
                productFilter={appliedProductFilter}
                payerFilter={appliedPayerFilter}
                appliedBrand={appliedBrand}
                activeTab={activeTab}
                appliedScenario={currentlyAppliedScenario}
                selectedCompareScenarios={selectedCompareScenarios}
                compareScenarioOptions={compareScenarioOptions}
                rawScenariosData={liverRawData?.scenarios}
                activeMetricKey={toApiMetricKey(metric)}
                filterFromYM={appliedFromDate ? toYearMonth(appliedFromDate) : ""}
                filterToYM={appliedToDate ? toYearMonth(appliedToDate) : ""}
                viewMode={totalMarketViewMode}
              />
            </AccordionDetails>
          </Accordion>

          {/* ── MARKET METRICS TABLE ── */}
          <ModelInputTable
            activeTab={activeTab}
            activeTabLabel={activeTabLabel}
            tableData={tableData}
            chartData={chartData}
            liverRawData={liverRawData}
            liverTabsRaw={liverTabsRaw}
            metric={metric}
            metricUnit={metricUnit}
            totalMarketViewMode={totalMarketViewMode}
            selectedCompareScenarios={selectedCompareScenarios}
            compareScenarioOptions={compareScenarioOptions}
            currentlyAppliedScenario={currentlyAppliedScenario}
            tentativeRadioSelectedScenario={tentativeRadioSelectedScenario}
            userHasCustomizedCompare={userHasCustomizedCompare}
            savedScenarioRows={savedScenarioRows}
            appliedProductFilter={appliedProductFilter}
            appliedPayerFilter={appliedPayerFilter}
            appliedBrand={appliedBrand}
            appliedFromDate={appliedFromDate}
            appliedToDate={appliedToDate}
            expandedBrands={expandedBrands}
            filterOptions={filterOptions}
            tableEditing={tableEditing}
            isRefreshed={isRefreshed}
            savingTable={savingTable}
            isSavingEditChanges={isSavingEditChanges}
            editedHierarchies={editedHierarchies}
            showMetricFilter={showMetricFilter}
            showScenarioControls={showScenarioControls}
            showCompareScenarios={showCompareScenarios}
            setExpandedBrands={setExpandedBrands}
            setNewScenarioName={setNewScenarioName}
            setSaveScenarioDialogOpen={setSaveScenarioDialogOpen}
            handleMetricChange={handleMetricChange}
            setTotalMarketViewMode={setTotalMarketViewMode}
            handleCancelTableEdit={handleCancelTableEdit}
            handleDownloadTable={handleDownloadTable}
            handleConfirmSave={handleConfirmSave}
            handleEnterTableEdit={handleEnterTableEdit}
            handleSaveTableChanges={handleSaveTableChanges}
            applySelectedScenario={applySelectedScenario}
            handleCompareScenarioChange={handleCompareScenarioChange}
            handleActiveScenarioRadioChange={handleActiveScenarioRadioChange}
            handleCellChange={handleCellChange}
          />
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