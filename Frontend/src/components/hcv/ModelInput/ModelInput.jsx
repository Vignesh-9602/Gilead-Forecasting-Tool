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
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from "@mui/material";
import Plot from "react-plotly.js";
const PlotComponent = Plot.default || Plot;
import { GlobalContext } from "../../../context/Provider";
import {
  getLiverFilters,
  applyLiverFilters,
  recalculateLiver,
  saveLiverScenario,
  refreshLiverTable,
  getMetricFilters,
  applyMetricFilters,
  recalculateMetrics,
  saveScenario,
  updateScenario,
  getConfigurationByTherapyAreaHCV,
} from "../../../services/apiService";
import { useSnackbarStore, useLoadingStore } from "../../../stores";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import DownloadIcon from "@mui/icons-material/Download";
import RefreshIcon from "@mui/icons-material/Refresh";
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
  payer_dist: "market_distribution",
  payer_prod: "market_product",
  prod_payer: "product_market",
};

const COMPARE_OPTIONS = ["ETS 13M", "ETS 26M", "Exponential"];
const DATE_INPUT_FORMATS = [
  "MMM-YY",
  "YYYY-MM",
  "YYYY-MM-DD",
  "YYYY-MM-DDTHH:mm:ssZ",
];
const CHART_COLORS = [
  "#4F46E5",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#0ea5e9",
  "#84cc16",
];

// ─── ForecastChart ────────────────────────────────────────────────────────────
const ForecastChart = ({
  chartData,
  productFilter,
  payerFilter,
  appliedBrand,
  activeTab,
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

  const allMonths = months.map((m) => {
    const parsed = dayjs(m, DATE_INPUT_FORMATS, true);
    return parsed.isValid()
      ? parsed.format("MMM-YY")
      : new Date(m).toLocaleDateString("en-US", {
          month: "short",
          year: "2-digit",
        });
  });

  const filteredSeries = useMemo(() => {
    const brandLower = (productFilter || appliedBrand || "").toLowerCase();
    const payerLower = (payerFilter || "").toLowerCase();

    if (
      (activeTab === "payer_prod" || activeTab === "prod_payer") &&
      brandLower &&
      payerLower
    ) {
      return series.filter((s) => {
        const lbl = (s.label || "").toLowerCase();
        return lbl.includes(brandLower) && lbl.includes(payerLower);
      });
    }
    return series;
  }, [series, activeTab, productFilter, payerFilter, appliedBrand]);

  const traces = filteredSeries.flatMap((s, idx) => {
    const currentBrand = (productFilter || appliedBrand || "").toLowerCase();
    const currentPayer = (payerFilter || "").toLowerCase();
    const seriesLabel = (s.label || "").toLowerCase();

    let isSelectedTrace = false;
    if (activeTab === "prod_dist" && currentBrand) {
      isSelectedTrace = seriesLabel === currentBrand;
    } else if (activeTab === "payer_dist" && currentPayer) {
      isSelectedTrace = seriesLabel === currentPayer;
    } else if (
      (activeTab === "payer_prod" || activeTab === "prod_payer") &&
      currentPayer &&
      currentBrand
    ) {
      isSelectedTrace =
        seriesLabel.includes(currentPayer) &&
        seriesLabel.includes(currentBrand);
    } else if (activeTab === "total_market") {
      isSelectedTrace = true;
    } else {
      isSelectedTrace =
        (currentBrand && seriesLabel.includes(currentBrand)) ||
        (currentPayer && seriesLabel.includes(currentPayer));
    }

    const color = isSelectedTrace
      ? CHART_COLORS[idx % CHART_COLORS.length]
      : "#e2e8f0";
    const width = isSelectedTrace ? 3.5 : 1.5;

    const trainX = allMonths.slice(0, fsi);
    const trainY = Array.isArray(s.train_values)
      ? s.train_values.slice(0, fsi)
      : [];
    const forecastX =
      fsi > 0
        ? [allMonths[fsi - 1], ...allMonths.slice(fsi)]
        : allMonths.slice(fsi);
    const lastTrain = s.train_values?.length
      ? s.train_values[s.train_values.length - 1]
      : null;
    const forecastY =
      fsi > 0
        ? [
            lastTrain ?? null,
            ...(Array.isArray(s.forecast_values) ? s.forecast_values : []),
          ]
        : Array.isArray(s.forecast_values)
          ? s.forecast_values
          : [];

    return [
      {
        x: trainX,
        y: trainY,
        type: "scatter",
        mode: "lines",
        name: s.label,
        legendgroup: s.label,
        line: { color, width },
      },
      {
        x: forecastX,
        y: forecastY,
        type: "scatter",
        mode: "lines",
        name: s.label,
        legendgroup: s.label,
        showlegend: false,
        line: { color, width, dash: "dot" },
      },
    ];
  });

  return (
    <Box sx={{ width: "100%", height: 300 }}>
      <PlotComponent
        data={traces}
        layout={{
          autosize: true,
          height: 300,
          margin: { l: 50, r: 30, t: 8, b: 60 },
          legend: { orientation: "h", x: 0.35, y: -0.2 },
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
  const [showScenariosDropdown, setShowScenariosDropdown] = useState(false);
  // All scenario names from the API — shown in the Compare Scenarios dropdown
  const [compareScenarioOptions, setCompareScenarioOptions] = useState([]);
  // Subset the user has chosen to display; empty = show all
  const [selectedCompareScenarios, setSelectedCompareScenarios] = useState([]);
  const [tentativeRadioSelectedScenario, setTentativeRadioSelectedScenario] =
    useState("");
  const [currentlyAppliedScenario, setCurrentlyAppliedScenario] = useState("");
  const [expandedBrands, setExpandedBrands] = useState({});
  // Table edit tracking — for refresh-table API
  const [tableEditing, setTableEditing] = useState(false);
  const [tableSnapshot, setTableSnapshot] = useState([]);
  const [editedHierarchies, setEditedHierarchies] = useState({});
  const [savingTable, setSavingTable] = useState(false);

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
    if (!ma) return { months: [], forecast_start_index: 0, tabs: {} };

    const parseNumber = (x, asPercent = false) => {
      if (x == null || x === "") return null;
      const n = Number(x);
      if (Number.isNaN(n)) return null;
      if (asPercent && Math.abs(n) <= 1) return n * 100;
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

    const firstTab = ma.total_market_volume || ma[Object.keys(ma)[0]];
    const firstMetric =
      firstTab &&
      (firstTab.market_volume ||
        firstTab.market_share ||
        Object.values(firstTab)[0]);
    const months =
      (firstMetric && firstMetric.chart && firstMetric.chart.months) || [];
    const fsi =
      (firstMetric &&
        firstMetric.chart &&
        firstMetric.chart.forecast_start_index) ||
      0;

    const selectMetricForTab = (tabKey, tabObj) => {
      // Force "market_volume" if the context tab is total_market_volume
      if (tabKey === "total_market_volume") {
        return tabObj.market_volume || Object.values(tabObj)[0];
      }

      if (currentMetric && tabObj[currentMetric]) {
        return tabObj[currentMetric];
      }
      const isVolumeTab =
        tabKey === "market_product" || tabKey === "product_market";
      const isDefaultShareTab =
        tabKey === "product_distribution" || tabKey === "market_distribution";

      if (isVolumeTab)
        return (
          tabObj.market_volume ||
          tabObj.market_share ||
          Object.values(tabObj)[0]
        );
      if (isDefaultShareTab)
        return (
          tabObj.market_share ||
          tabObj.market_volume ||
          Object.values(tabObj)[0]
        );
      return (
        tabObj.market_volume || tabObj.market_share || Object.values(tabObj)[0]
      );
    };

    const tabs = {};
    Object.keys(ma).forEach((tabKey) => {
      const tabObj = ma[tabKey] || {};
      const selectedMetric = selectMetricForTab(tabKey, tabObj);
      const chartMetric = selectedMetric;
      const tableMetric = selectedMetric;
      const isTabPercent = selectedMetric === tabObj.market_share;

      const chart =
        chartMetric && chartMetric.chart
          ? {
              months: chartMetric.chart.months || months,
              forecast_start_index:
                chartMetric.chart.forecast_start_index || fsi,
              series: (chartMetric.chart.series || []).map((s) => ({
                label: s.label || "",
                train_values: parseValues(
                  s.history || s.train_values,
                  isTabPercent,
                ),
                forecast_values: parseValues(
                  s.forecast || s.forecast_values,
                  isTabPercent,
                ),
                lot: s.lot || s.label || "",
              })),
            }
          : { months, forecast_start_index: fsi, series: [] };

      const table =
        tableMetric && tableMetric.table
          ? {
              type: tableMetric.table.type,
              headers: tableMetric.table.headers || chart.months,
              rows: (tableMetric.table.rows || []).map((r) => ({
                hierarchy: r.hierarchy || r.label || "",
                label: r.label || r.hierarchy || "",
                total: Array.isArray(r.total)
                  ? parseValues(r.total, isTabPercent)
                  : undefined,
                values: parseValues(r.values, isTabPercent),
                children: (r.children || []).map((c) => ({
                  label: c.label,
                  values: parseValues(c.values, isTabPercent),
                })),
              })),
            }
          : { type: "flat", headers: chart.months, rows: [] };

      tabs[tabKey] = { chart, table };
    });

    // ── Multi-scenario table rows for Total Market Volume ──────────────────
    // The active scenario's market_analysis only gives us one row ("Base").
    // We need one row per scenario so the table can show/filter them all.
    // For every scenario in the response, pull its total_market_volume
    // market_volume table and add a row keyed by the scenario name.
    if (data.scenarios && Object.keys(data.scenarios).length > 0) {
      const tmvTab = tabs["total_market_volume"];
      if (tmvTab) {
        const scenarioRows = [];
        Object.entries(data.scenarios).forEach(([scenarioName, scenarioData]) => {
          const tmv = scenarioData?.market_analysis?.total_market_volume;
          if (!tmv) return;
          // pick market_volume first, fall back to market_share
          const metricObj =
            tmv.market_volume || tmv.market_share || Object.values(tmv)[0];
          if (!metricObj) return;
          const rawRows = metricObj?.table?.rows || [];
          const firstRow = rawRows[0];
          if (!firstRow) return;
          scenarioRows.push({
            hierarchy: scenarioName,
            label: scenarioName,
            total: undefined,
            values: parseValues(firstRow.values, false),
            children: [],
          });
        });
        if (scenarioRows.length) {
          tabs["total_market_volume"] = {
            ...tmvTab,
            table: {
              ...tmvTab.table,
              rows: scenarioRows,
            },
          };
        }
      }
    }

    return { months, forecast_start_index: fsi, tabs };
  }

  // Maps the response of refresh-table (POST /api/liver/refresh-table) into
  // { chart, table } for the currently active tab. This response shape is
  // flat: { chart: { months, forecast_start_index, series: [{label, history, forecast}] },
  //         table: { type: "flat", rows: [{label, values}] } }
  // where `values` is history concatenated with forecast (one entry per month).
  const mapRefreshTableResponse = (data) => {
    if (!data) return { chart: null, table: [] };
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

  const mapLiverTabToView = (tabsPayload, uiTabKey) => {
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
        "product_wise_payer",
        "payer_wise_product",
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

    const headers = tab.table?.headers || months;
    const mkMonthly = (vals, hdrs) => {
      const obj = {};
      hdrs.forEach((m, i) => {
        const v = vals[i];
        obj[m] = v == null ? null : Number(v);
      });
      return obj;
    };

    const table = [];
    (tab.table?.rows || []).forEach((r) => {
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

    return { chart: { months, forecast_start_index: fsi, series }, table };
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
    scenario_name: scenarioSelector || "Base",
    model_type: modelSelection,
    factors: buildFullFactors(),
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
    scenario: scenarioSelector || "Base",
  });

  // Build payload for the refresh-table API based on current (edited) table state
  const buildRefreshTablePayload = (hierarchyKey) => ({
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
    metric: metric || "market_volume",
    from_date: resolveFromDate(),
    scenario: scenarioSelector || "Base",
    tab_key: TAB_KEY_MAP[activeTab] || activeTab,
    edited_hierarchy: hierarchyKey || "",
    table: tableData.map((row) => ({
      hierarchy: row.hierarchy,
      values: (chartData?.months || []).map((m) => {
        const v = row.monthly_data?.[m];
        return v == null ? 0 : Number(v);
      }),
    })),
  });

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

    // Apply per-tab model defaults only when switching tabs (not on every
    // render). We never override a model the user/backend explicitly set —
    // we only set the default for a tab the first time it's visited.
    //   total_market → default ets
    //   all others   → default linear (ets is still selectable)
    if (activeTab === "total_market") {
      if (!modelSelection || modelSelection === "linear") setModelSelection("ets");
    } else {
      if (!modelSelection || modelSelection === "ets") setModelSelection("linear");
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
    const { chart, table } = mapLiverTabToView(liverTabsRaw, activeTab);
    setChartData(chart);
    setTableData(table);
    setExpandedBrands({});
  }, [activeTab, liverTabsRaw]);

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

  useEffect(() => {
    const fn = () => setShowScenariosDropdown(false);
    window.addEventListener("click", fn);
    return () => window.removeEventListener("click", fn);
  }, []);

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
            filtersData?.markets?.length
              ? filtersData.markets
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
            sfInitial.market ||
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
            scenario: "Base",
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
            initializeCompareScenarios(data);
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
          // The chart's month list doubles as the set of selectable dates
          // for the FROM/TO DATE dropdowns — no separate endpoint needed.
          if (normalized?.months?.length) setAvailableDates(normalized.months);
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
      if (Array.isArray(resData?.markets) && resData.markets.length) {
        setPayerOptions(resData.markets);
      }
      if (Array.isArray(resData?.products) && resData.products.length) {
        setProductOptions(resData.products);
      }

      // Update FROM/TO DATE values from the backend's resolved selection.
      if (sf.start_date) setFromDate(sf.start_date);
      if (sf.end_date) setToDate(sf.end_date);

      // Sync payer/product to whatever the backend resolved (in case it
      // snapped to a valid combination), falling back to what was picked.
      setPayerFilter(sf.market || payerVal || "");
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
      return activeTab === "total_market" ? "ets" : "linear";
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
        const resp = await saveLiverScenario({
          scenario_name: scenarioNameFromDialog,
          ta: therapyArea || "HCV",
          payer: payerFilter ? [payerFilter] : [],
          brand: productFilter ? [productFilter] : [],
          metric: metric || "market_volume",
          from_date: resolveFromDate(),
          factors: buildFullFactors(),
          chart_data: { chart: chartData, table: tableData },
          editable_table: tableData.map((row) => ({
            hierarchy: row.hierarchy,
            values: (chartData?.months || []).map((m) => {
              const v = row.monthly_data?.[m];
              return v == null ? 0 : Number(v);
            }),
          })),
        });

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
            initializeCompareScenarios(respData);
            // mapLiverTabToView will re-run via the liverTabsRaw effect,
            // which updates chartData and tableData automatically.
          }
        }

        setTentativeRadioSelectedScenario(scenarioNameFromDialog);
        setCurrentlyAppliedScenario(scenarioNameFromDialog);
        // Remove from savedScenarioRows if it got real data (the actual
        // row will now appear in groupedTableHierarchy from the response).
        setSavedScenarioRows((prev) => {
          const hasRealData =
            resp?.data &&
            Object.keys(resp.data).length &&
            normalizeLiverResponse(resp.data, metric)?.tabs &&
            Object.keys(normalizeLiverResponse(resp.data, metric).tabs).length;
          if (hasRealData) return prev.filter((n) => n !== scenarioNameFromDialog);
          return prev.includes(scenarioNameFromDialog)
            ? prev
            : [...prev, scenarioNameFromDialog];
        });
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
      showSnackbar("Failed to save scenario", "error");
    } finally {
      setLoading(false);
    }
  };

  // ── Table edit / refresh handlers ────────────────────────────────────────
  const handleEnterTableEdit = () => {
    setTableSnapshot(tableData.map((r) => ({ ...r, monthly_data: { ...r.monthly_data } })));
    setEditedHierarchies({});
    setTableEditing(true);
    setEditable(true);
  };

  const handleCancelTableEdit = () => {
    setTableData(tableSnapshot);
    setEditedHierarchies({});
    setTableEditing(false);
    setEditable(false);
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
      let lastData = null;
      for (const hierarchyKey of editedKeys) {
        const response = await refreshLiverTable(
          buildRefreshTablePayload(hierarchyKey),
        );
        lastData = response?.data || {};
      }
      if (lastData) {
        const { chart, table } = mapRefreshTableResponse(lastData);
        setChartData(chart);
        setTableData(table);

        // Keep liverTabsRaw in sync so switching tabs and back still shows
        // the saved values for this tab.
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
      setEditedHierarchies({});
      setTableEditing(false);
      setEditable(false);
      showSnackbar("Table updated successfully", "success");
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
  const toggleScenariosDropdown = (e) => {
    if (e?.stopPropagation) e.stopPropagation();
    setShowScenariosDropdown((s) => !s);
  };

  // Seed Compare Scenarios dropdown from the API response's available_scenarios.
  // Called after every apply-filters / save-scenario / initial load response.
  const initializeCompareScenarios = (response) => {
    const scenarios =
      response?.available_scenarios ||
      (response?.scenarios ? Object.keys(response.scenarios) : []);
    if (!scenarios.length) return;
    setCompareScenarioOptions(scenarios);
    // On first init (empty selection) show all; preserve any prior selection.
    setSelectedCompareScenarios((prev) =>
      prev.length ? prev.filter((s) => scenarios.includes(s)) : scenarios,
    );
  };

  const handleScenarioSelectionChange = (s) => {
    setSelectedCompareScenarios((prev) => {
      const updated = prev.includes(s)
        ? prev.filter((x) => x !== s)
        : [...prev, s];
      // If the user deselects everything, restore all options.
      return updated.length ? updated : compareScenarioOptions;
    });
  };
  const handleActiveScenarioRadioChange = (name) => {
    setTentativeRadioSelectedScenario(name);
  };
  const clickTableEdit = () => setEditable(true);
  const applySelectedScenario = () => {
    setCurrentlyAppliedScenario(tentativeRadioSelectedScenario);
    showSnackbar(
      `Applied ${tentativeRadioSelectedScenario} successfully across all tabs!`,
      "success",
    );
    setEditable(false);
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
    if (metricUnit === "%") return `${num.toFixed(1)}%`;
    return num.toLocaleString(undefined, { maximumFractionDigits: 1 });
  };

  const toggleBrandExpand = (name) => {
    setExpandedBrands((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  const handleCellChange = (hierarchyKey, colName, value) => {
    const numericValue = value === "" ? null : Number(value);
    if (numericValue !== null && Number.isNaN(numericValue)) return;

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

  // ── Hierarchy grouping ────────────────────────────────────────────────────
  const groupedTableHierarchy = useMemo(() => {
    const map = {};
    tableData.forEach((row) => {
      const raw = row.hierarchy || "";
      if (raw.includes(" - ")) {
        const parts = raw.split(" - ");
        const brandKey = parts[0].trim();
        const payerKey = parts.slice(1).join(" - ").trim();
        if (!map[brandKey]) map[brandKey] = { mainRow: null, children: [] };
        map[brandKey].children.push({ ...row, cleanLabel: payerKey });
      } else {
        const brandKey = raw.trim();
        if (!map[brandKey]) map[brandKey] = { mainRow: null, children: [] };
        map[brandKey].mainRow = row;
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
          monthly_data[m] = any ? sum : null;
        });
        mainRow = {
          hierarchy: brandKey,
          monthly_data,
          is_applied: children.some((c) => c.is_applied),
        };
      } else {
        mainRow.monthly_data = mainRow.monthly_data || {};
      }
      return { brandName: brandKey, mainRow, children: entry.children };
    });
  }, [tableData, chartData]);

  // ── Monthly / Yearly toggle helpers ──────────────────────────────────────
  // displayColumns are the column keys actually rendered in the table header
  // and used to look up cell values. In monthly mode these are just the raw
  // month strings from chartData.months; in yearly mode they're the unique
  // years derived from those months, in chronological order.
  const displayColumns = useMemo(() => {
    const months = chartData?.months || [];
    if (totalMarketViewMode !== "yearly") return months;
    const years = [];
    months.forEach((m) => {
      const y = String(m).slice(0, 4);
      if (y && !years.includes(y)) years.push(y);
    });
    return years;
  }, [chartData, totalMarketViewMode]);

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

  // Looks up a row's value for a given display column. In monthly mode this
  // is a direct lookup; in yearly mode it aggregates the months belonging to
  // that year — summed for volume metrics, averaged for percentage metrics
  // (market share), skipping any null/missing months.
  const getColumnValue = (row, col) => {
    if (totalMarketViewMode !== "yearly") {
      return row?.monthly_data?.[col];
    }
    const monthsInYear = yearToMonthsMap[col] || [];
    let sum = 0;
    let count = 0;
    monthsInYear.forEach((m) => {
      const v = row?.monthly_data?.[m];
      if (v != null && !Number.isNaN(Number(v))) {
        sum += Number(v);
        count += 1;
      }
    });
    if (count === 0) return null;
    return metricUnit === "%" ? sum / count : sum;
  };

  // A column counts as "forecast" if any of its underlying months are in the
  // forecast period (monthly mode checks the single month directly).
  const isForecastColumn = (col) => {
    if (totalMarketViewMode !== "yearly") return isForecastMonth(col);
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
                  height: 34,
                  px: 2,
                  display: "flex",
                  alignItems: "center",
                  borderRadius: "6px",
                  backgroundColor: "#10b981",
                  minWidth: "100px",
                }}
              >
                <Typography
                  sx={{ fontSize: "13px", fontWeight: 600, color: "white" }}
                >
                  {therapyArea}
                </Typography>
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

          <Button
            variant="contained"
            onClick={() => {
              setNewScenarioName("");
              setSaveScenarioDialogOpen(true);
            }}
            sx={{
              textTransform: "none",
              borderRadius: "6px",
              backgroundColor: "#10b981",
              height: "34px",
              fontSize: "12px",
              fontWeight: 700,
              flexShrink: 0,
            }}
          >
            Save Scenario
          </Button>
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
            alignLayout="center"
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
                      disabled={!editable}
                      displayEmpty
                      renderValue={(sel) => {
                        if (!sel) return "Select";
                        const d = new Date(sel);
                        return isNaN(d)
                          ? sel
                          : d.toLocaleDateString("en-US", {
                              month: "short",
                              year: "2-digit",
                            });
                      }}
                    >
                      {(() => {
                        // Build option list from all months (not just forecast)
                        // so the backend default (which may point to any month)
                        // always has a matching MenuItem. If the current value
                        // still isn't in the list (e.g. a month the chart
                        // doesn't cover), append it so the Select can display
                        // it rather than showing blank.
                        const allMonths = chartData?.months || [];
                        const opts =
                          allMonths.length > 0
                            ? allMonths
                            : trajectoryMonthOptions;
                        const withCurrent =
                          trajectoryStart && !opts.includes(trajectoryStart)
                            ? [...opts, trajectoryStart]
                            : opts;
                        return withCurrent.map((m) => (
                          <MenuItem key={m} value={m}>
                            {new Date(m).toLocaleDateString("en-US", {
                              month: "short",
                              year: "2-digit",
                            })}
                          </MenuItem>
                        ));
                      })()}
                    </Select>
                  </FormControl>
                </Box>
              </>
            )}

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
          {/* Chart */}
          <Paper
            sx={{
              p: 2,
              borderRadius: "12px",
              border: "1px solid #D8DEE8",
              boxShadow: "none",
              minHeight: "300px",
              mb: 3,
            }}
          >
            <ForecastChart
              chartData={chartData}
              metricUnit={isPercentTab ? "%" : metricUnit}
              productFilter={appliedProductFilter}
              payerFilter={appliedPayerFilter}
              appliedBrand={appliedBrand}
              activeTab={activeTab}
            />
          </Paper>

          {/* ── MARKET METRICS TABLE ── */}
          <Box id="volumeSection">
            {/* Table controls row */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                mb: 1.5,
                flexWrap: "wrap",
                gap: 1,
              }}
            >
              <Typography
                sx={{
                  fontSize: "16px",
                  fontWeight: 700,
                  color: "#1e293b",
                  textTransform: "uppercase",
                }}
              >
                {activeTabLabel}
              </Typography>

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
                  <FormControl size="small" sx={{ minWidth: 160 }}>
                    <Select
                      value={metric}
                      onChange={async (e) => {
                        const nm = e.target.value;
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
                      sx={{
                        height: 32,
                        borderRadius: "6px",
                        fontSize: "12px",
                        fontWeight: 600,
                        backgroundColor: "white",
                        "& .MuiOutlinedInput-notchedOutline": {
                          borderColor: "#e2e8f0",
                        },
                      }}
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

                {/* Monthly / Yearly toggle */}
                <ToggleButtonGroup
                  value={totalMarketViewMode}
                  exclusive
                  size="small"
                  onChange={(e, val) => {
                    if (!val) return;
                    setTotalMarketViewMode(val);
                    if (val === "yearly" && tableEditing) {
                      handleCancelTableEdit();
                    }
                  }}
                  sx={{
                    border: "1px solid #e2e8f0",
                    borderRadius: "6px",
                    overflow: "hidden",
                    "& .MuiToggleButton-root": {
                      border: "none",
                      borderRadius: 0,
                      textTransform: "none",
                      fontSize: "12px",
                      fontWeight: 600,
                      px: 2,
                      py: 0.5,
                      color: "#64748b",
                      "&.Mui-selected": {
                        backgroundColor: "#4F46E5",
                        color: "white",
                        "&:hover": { backgroundColor: "#4338ca" },
                      },
                    },
                  }}
                >
                  <ToggleButton value="monthly">Monthly</ToggleButton>
                  <ToggleButton value="yearly">Yearly</ToggleButton>
                </ToggleButtonGroup>

                {/* Download / Save / Edit Changes / Cancel — table edit toolbar */}
                <Tooltip title="Download table as CSV">
                  <IconButton
                    size="small"
                    onClick={handleDownloadTable}
                    sx={{
                      border: "1px solid #e2e8f0",
                      borderRadius: "6px",
                      width: 32,
                      height: 32,
                      color: "#64748b",
                      "&:hover": { backgroundColor: "#f8fafc" },
                    }}
                  >
                    <DownloadIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </Tooltip>

                {tableEditing && (
                  <Button
                    size="small"
                    variant="contained"
                    disabled={savingTable}
                    onClick={handleSaveTableChanges}
                    startIcon={<RefreshIcon sx={{ fontSize: 16 }} />}
                    sx={{
                      textTransform: "none",
                      fontSize: "12px",
                      fontWeight: 700,
                      borderRadius: "6px",
                      backgroundColor: "#4F46E5",
                      px: 2,
                      "&:hover": { backgroundColor: "#4338ca" },
                    }}
                  >
                    {savingTable ? "Refreshing..." : "Refresh"}
                  </Button>
                )}

                <Button
                  size="small"
                  variant="outlined"
                  onClick={tableEditing ? handleCancelTableEdit : handleEnterTableEdit}
                  sx={{
                    textTransform: "none",
                    fontSize: "12px",
                    fontWeight: 600,
                    borderRadius: "6px",
                    borderColor: tableEditing ? "#4F46E5" : "#e2e8f0",
                    color: tableEditing ? "#4F46E5" : "#3d89f3",
                    px: 1.5,
                    "&:hover": {
                      borderColor: "#cbd5e1",
                      backgroundColor: "#f8fafc",
                    },
                  }}
                >
                  Edit Changes
                </Button>

                {tableEditing && (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={handleCancelTableEdit}
                    sx={{
                      textTransform: "none",
                      fontSize: "12px",
                      fontWeight: 600,
                      borderRadius: "6px",
                      borderColor: "#e2e8f0",
                      color: "#64748b",
                      px: 1.5,
                      "&:hover": {
                        borderColor: "#cbd5e1",
                        backgroundColor: "#f8fafc",
                      },
                    }}
                  >
                    Cancel
                  </Button>
                )}

                {/* Apply Selected Scenario — total_market only */}
                {showScenarioControls && (
                  <Button
                    size="small"
                    variant="contained"
                    onClick={applySelectedScenario}
                    sx={{
                      textTransform: "none",
                      fontSize: "12px",
                      fontWeight: 600,
                      borderRadius: "6px",
                      backgroundColor: "#4F46E5",
                      px: 1.5,
                      "&:hover": { backgroundColor: "#4338ca" },
                    }}
                  >
                    Apply Selected Scenario
                  </Button>
                )}

                {/* Compare Scenarios — total_market only */}
                {showScenarioControls && (
                  <Box sx={{ position: "relative" }}>
                    <Box
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleScenariosDropdown(e);
                      }}
                      sx={{
                        height: 32,
                        px: 1.5,
                        display: "flex",
                        alignItems: "center",
                        border: "1px solid #e2e8f0",
                        borderRadius: "6px",
                        cursor: "pointer",
                        fontSize: "12px",
                        fontWeight: 600,
                        color: "#64748b",
                        minWidth: 160,
                        userSelect: "none",
                        "&:hover": { backgroundColor: "#f8fafc" },
                      }}
                    >
                      Compare Scenarios ▼
                    </Box>
                    {showScenariosDropdown && (
                      <Box
                        onClick={(e) => e.stopPropagation()}
                        sx={{
                          position: "absolute",
                          top: 36,
                          right: 0,
                          backgroundColor: "white",
                          border: "1px solid #e2e8f0",
                          borderRadius: "8px",
                          boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
                          zIndex: 200,
                          p: 1,
                          minWidth: 200,
                        }}
                      >
                        {compareScenarioOptions.map((s) => (
                          <Box
                            key={s}
                            component="label"
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 1,
                              px: 1,
                              py: 0.75,
                              cursor: "pointer",
                              borderRadius: "4px",
                              "&:hover": { backgroundColor: "#f8fafc" },
                            }}
                          >
                            <input
                              type="checkbox"
                              value={s}
                              checked={selectedCompareScenarios.includes(s)}
                              onChange={() => handleScenarioSelectionChange(s)}
                            />
                            <Typography
                              sx={{
                                fontSize: "13px",
                                fontWeight: 500,
                                color: "#1e293b",
                              }}
                            >
                              {s}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    )}
                  </Box>
                )}
              </Box>
            </Box>

            {/* ── TABLE ── */}
            <Box
              sx={{
                backgroundColor: "white",
                borderRadius: "8px",
                border: "1px solid #e2e8f0",
                overflowX: "auto",
              }}
            >
              <Box
                component="table"
                sx={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "12px",
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
                        zIndex: 2,
                        backgroundColor: "#f8fafc",
                        color: "#0f172a",
                        fontWeight: 700,
                        fontSize: "13px",
                        textAlign: "left",
                        p: "12px 16px",
                        minWidth: 220,
                        borderRight: "1px solid #e2e8f0",
                        borderBottom: "1px solid #e2e8f0",
                      }}
                    >
                      Scenario
                    </Box>
                    {displayColumns.map((col) => (
                      <Box
                        component="th"
                        key={col}
                        sx={{
                          backgroundColor: "#f8fafc",
                          color: "#475569",
                          fontWeight: 700,
                          fontSize: "12px",
                          textAlign: "center",
                          p: "12px 8px",
                          minWidth: 85,
                          whiteSpace: "nowrap",
                          borderBottom: "1px solid #e2e8f0",
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
                                fontSize: "13px",
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
                                fontSize: "13px",
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
                                    fontSize: "13px",
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
                                    fontSize: "13px",
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
                        // On total_market tab: only filter by selected
                        // compare scenarios (always keep the applied one).
                        // On other tabs: show all rows regardless.
                        if (activeTab !== "total_market") return true;
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
                      ).toLowerCase();

                      let isAppliedParent = false;

                      if (activeTab === "prod_dist") {
                        isAppliedParent = targetParentLabel === currentBrand;
                      } else if (activeTab === "payer_dist") {
                        isAppliedParent = targetParentLabel === currentPayer;
                      } else if (activeTab === "payer_prod") {
                        isAppliedParent = targetParentLabel === currentPayer;
                      } else if (activeTab === "prod_payer") {
                        isAppliedParent = targetParentLabel === currentBrand;
                      }

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

                              backgroundColor: hasChildren ? "#f8fafc" : "white",

                              "&:hover": {
                                backgroundColor: hasChildren ? "#f1f5f9" : "#f8fafc",
                              },
                            }}
                          >
                            <Box
                              component="td"
                              sx={{
                                position: "sticky",
                                left: 0,
                                zIndex: 1,

                                backgroundColor: isAppliedParent
                                  ? "#fffbeb"
                                  : hasChildren
                                    ? "#f8fafc"
                                    : "white",

                                borderRight: "1px solid #e2e8f0",

                                borderBottom: hasChildren
                                    ? "1px solid #cbd5e1"
                                    : "1px solid #f1f5f9",

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
                                  />
                                )}

                                {hasChildren && (
                                  <Typography
                                    component="span"
                                    sx={{
                                      fontSize: "10px",
                                      width: "12px",
                                    }}
                                  >
                                    {isExpanded ? "▼" : "▶"}
                                  </Typography>
                                )}

                                <Typography
                                  sx={{
                                    fontSize: "13px",

                                    fontWeight: hasChildren ? 700 : 400,

                                    color: isAppliedParent
                                      ? "#f59e0b"
                                      : "#0f172a",
                                  }}
                                >
                                  {group.brandName}
                                </Typography>

                                {(mainRowApplied ||
                                  currentlyAppliedScenario ===
                                    group.brandName) && (
                                  <Typography
                                    sx={{
                                      fontSize: "11px",
                                      fontWeight: 600,
                                      color: "#10b981",
                                    }}
                                  >
                                    (Applied)
                                  </Typography>
                                )}
                              </Box>
                            </Box>

                            {displayColumns.map((col) => {
                              const val = getColumnValue(group.mainRow, col);

                              const isF = isForecastColumn(col);

                              return tableEditing &&
                                !hasChildren &&
                                totalMarketViewMode === "monthly" ? (
                                <Box
                                  component="td"
                                  key={col}
                                  sx={{
                                    p: "6px 6px",
                                    textAlign: "center",
                                  }}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <TextField
                                    size="small"
                                    type="number"
                                    value={val ?? ""}
                                    onChange={(e) =>
                                      handleCellChange(
                                        group.brandName,
                                        col,
                                        e.target.value,
                                      )
                                    }
                                    sx={{
                                      width: 85,
                                      "& .MuiOutlinedInput-root": {
                                        height: 30,
                                        fontSize: "12px",
                                      },
                                    }}
                                  />
                                </Box>
                              ) : (
                                <Box
                                  component="td"
                                  key={col}
                                  sx={{
                                    p: "10px 8px",
                                    textAlign: "center",

                                    fontSize: "13px",

                                    fontWeight: hasChildren ? 700 : 400,

                                    backgroundColor:
                                      (isAppliedParent || activeTab === "total_market") && isF
                                        ? "#fffbeb"
                                        : isF
                                          ? "#ffffff"
                                          : "#eef2f7",

                                    color:
                                      (isAppliedParent || activeTab === "total_market") && isF
                                        ? "#f59e0b"
                                        : "#1e3a5f",
                                  }}
                                >
                                  {formatCellValue(val)}
                                </Box>
                              );
                            })}
                          </Box>

                          {showChildren &&
                            group.children.map((childRow, idx) => {
                              const childLabel = (
                                childRow.cleanLabel || ""
                              ).toLowerCase();

                              // For payer_prod / prod_payer tabs, highlight only
                              // the specific child whose label matches the
                              // complementary filter (product under the
                              // matching payer parent, or vice versa).
                              let isAppliedChild = false;
                              if (activeTab === "payer_prod") {
                                isAppliedChild =
                                  targetParentLabel === currentPayer &&
                                  childLabel === currentBrand;
                              } else if (activeTab === "prod_payer") {
                                isAppliedChild =
                                  targetParentLabel === currentBrand &&
                                  childLabel === currentPayer;
                              }

                              const isHighlightedChild = isAppliedChild;

                              return (
                              <Box component="tr" key={idx} sx={{ position: "relative", isolation: "isolate" }}>
                                <Box
                                  component="td"
                                  sx={{
                                    position: "sticky",
                                    left: 0,
                                    zIndex: 1,
                                    backgroundColor: isHighlightedChild
                                      ? "#fffbeb"
                                      : "white",
                                    borderRight: "1px solid #e2e8f0",
                                    pl: "40px",
                                    p: "10px 16px",
                                  }}
                                >
                                  <Typography
                                    sx={{
                                      fontSize: "13px",

                                      fontWeight: 500,

                                      color: isHighlightedChild
                                        ? "#f59e0b"
                                        : "#0f172a",
                                    }}
                                  >
                                    {childRow.cleanLabel}
                                  </Typography>
                                </Box>

                                {displayColumns.map((col) => {
                                  const isFChild = isForecastColumn(col);
                                  return tableEditing && totalMarketViewMode === "monthly" ? (
                                    <Box
                                      component="td"
                                      key={col}
                                      sx={{ p: "6px 6px", textAlign: "center" }}
                                    >
                                      <TextField
                                        size="small"
                                        type="number"
                                        value={childRow?.monthly_data?.[col] ?? ""}
                                        onChange={(e) =>
                                          handleCellChange(
                                            childRow.hierarchy,
                                            col,
                                            e.target.value,
                                          )
                                        }
                                        sx={{
                                          width: 85,
                                          "& .MuiOutlinedInput-root": {
                                            height: 30,
                                            fontSize: "12px",
                                          },
                                        }}
                                      />
                                    </Box>
                                  ) : (
                                    <Box
                                      component="td"
                                      key={col}
                                      sx={{
                                        p: "10px 8px",
                                        textAlign: "center",

                                        backgroundColor:
                                          isHighlightedChild && isFChild
                                            ? "#fffbeb"
                                            : isFChild
                                              ? "#ffffff"
                                              : "#eef2f7",

                                        color:
                                          isHighlightedChild && isFChild
                                            ? "#f59e0b"
                                            : "#1e3a5f",
                                      }}
                                    >
                                      {formatCellValue(
                                        getColumnValue(childRow, col),
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
                                    fontSize: "13px",
                                    fontWeight: 600,
                                    color: "#0f172a",
                                  }}
                                >
                                  {name}
                                </Typography>
                                <Typography
                                  component="span"
                                  sx={{
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    color: "#10b981",
                                  }}
                                >
                                  {currentlyAppliedScenario === name ? "(Applied)" : "(Saved)"}
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
                                    fontSize: "13px",
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
          </Box>
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
          Save Scenario
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: "13px", color: "#64748b", mb: 2 }}>
            Enter a name for this scenario. It will appear in the table as a
            selectable row — click "Apply Selected Scenario" to load its data.
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