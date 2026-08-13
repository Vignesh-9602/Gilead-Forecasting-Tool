import React, { useState, useEffect, useLayoutEffect, useContext, useMemo, useRef } from "react";
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
  deleteLiverScenario,
  addLiverMarketEventsProduct,
  saveLiverMarketEventsConfig,
  deleteLiverMarketEvent,
  getLiverMarketEventsFilters,
  getLiverMarketEventsList,
  runLiverMarketEventsCalculation,
} from "../../../services/apiService";
import { useSnackbarStore, useLoadingStore } from "../../../stores";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import Tooltip from "@mui/material/Tooltip";
import dayjs from "dayjs";
import ModelInputChart from "./ModelInputChart";
import ModelInputTable from "./ModelInputTable";
import MarketEventsPanel from "./MarketEventsPanel";
import PaymentPayerProductTable from "./PaymentPayerProductTable";

const TABS = [
  { label: "Total Market Volume", value: "total_market" },
  { label: "Product Distribution (%)", value: "prod_dist" },
  { label: "Payment Type Distribution (%)", value: "payer_dist" },
  { label: "Payment type-Payer-Product", value: "payment_payer_prod" },
  { label: "Events Management", value: "manage_events" },
];

const HIERARCHY_TAB_VALUES = ["payer_prod", "prod_payer"];

const TAB_KEY_MAP = {
  total_market: "total_market_volume",
  prod_dist: "product_distribution",
  payer_dist: "payment_type_distribution",
  payer_prod: "payer_product",
  prod_payer: "product_payer",
  payment_payer_prod: "payment_type_payer_product",
};

const DATE_INPUT_FORMATS = [
  "MMM-YY",
  "YYYY-MM",
  "YYYY-MM-DD",
  "YYYY-MM-DDTHH:mm:ssZ",
];

export default function PBCModelInput() {
  const { showSnackbar } = useSnackbarStore();
  const { setLoading } = useLoadingStore();
  const { favState } = useContext(GlobalContext);
  const therapyArea = favState?.selectedTherapyArea;
  const isHCV = therapyArea && therapyArea.toLowerCase() === "hcv";

  // ── REFS ──
  const userSelectedMetricRef = useRef(false);
  const fetchedTaRef = useRef(null);
  const fetchedMarketEventsTaRef = useRef(null);
  const prevActiveTabRef = useRef("");
  const tableScrollPositionsRef = useRef({});

  // ── STATE ──
  const [activeTab, setActiveTab] = useState("total_market");
  const [scenarioSelector, setScenarioSelector] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [payerFilter, setPayerFilter] = useState("");
  const [subPayerFilter, setSubPayerFilter] = useState("");
  const [productFilter, setProductFilter] = useState("");

  const [tabMetrics, setTabMetrics] = useState({
    total_market: "market_volume",
    prod_dist: "market_share",
    payer_dist: "market_share",
    payment_payer_prod: "market_share",
    payer_prod: "market_volume",
    prod_payer: "market_volume",
  });

  const metric = tabMetrics[activeTab] || "market_volume";

  const [availableDates, setAvailableDates] = useState([]);
  const [chartData, setChartData] = useState(null);
  const [tableData, setTableData] = useState([]);
  const [allMetricsData, setAllMetricsData] = useState({});
  const [appliedLot, setAppliedLot] = useState("");
  const [appliedBrand, setAppliedBrand] = useState("");
  const [appliedPayerFilter, setAppliedPayerFilter] = useState("");
  const [appliedProductFilter, setAppliedProductFilter] = useState("");
  const [appliedSubPayerFilter, setAppliedSubPayerFilter] = useState("");
  const [appliedFromDate, setAppliedFromDate] = useState("");
  const [appliedToDate, setAppliedToDate] = useState("");
  const [saveScenarioDialogOpen, setSaveScenarioDialogOpen] = useState(false);
  const [newScenarioName, setNewScenarioName] = useState("");
  const [savedScenarioRows, setSavedScenarioRows] = useState([]);
  const [liverTabsRaw, setLiverTabsRaw] = useState(null);
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
  const [marketEvents, setMarketEvents] = useState([]);
  const [indication, setIndication] = useState("");
  const [lot, setLot] = useState("");
  const [brand, setBrand] = useState("");

  const [totalMarketViewMode, setTotalMarketViewMode] = useState("monthly");

  const [compareScenarioOptions, setCompareScenarioOptions] = useState([]);
  const [selectedCompareScenarios, setSelectedCompareScenarios] = useState([]);
  const [userHasCustomizedCompare, setUserHasCustomizedCompare] = useState(false);
  const [tentativeRadioSelectedScenario, setTentativeRadioSelectedScenario] = useState("");
  const [currentlyAppliedScenario, setCurrentlyAppliedScenario] = useState("");
  // Different endpoints have returned the same scenario with different
  // casing (e.g. Run Calculation's "BASE" vs elsewhere's "Base"). Compare
  // scenario names case-insensitively everywhere, not just ===.
  const sameScenario = (a, b) =>
    String(a || "").trim().toLowerCase() === String(b || "").trim().toLowerCase();

  const [expandedBrands, setExpandedBrands] = useState({});
  const [threeLevelExpandedRows, setThreeLevelExpandedRows] = useState({});
  const [hierarchyOrder, setHierarchyOrder] = useState("pt-payer-product");

  const [tableEditing, setTableEditing] = useState(false);
  const [tableSnapshot, setTableSnapshot] = useState([]);
  const [editedHierarchies, setEditedHierarchies] = useState({});
  const [savingTable, setSavingTable] = useState(false);
  const [isSavingEditChanges, setIsSavingEditChanges] = useState(false);
  const [savingMarketEvents, setSavingMarketEvents] = useState(false);
  const [runningMarketEventsCalculation, setRunningMarketEventsCalculation] = useState(false);
  const [isRefreshed, setIsRefreshed] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [scenarioToDelete, setScenarioToDelete] = useState("");

  const metricUnit = useMemo(() => {
    if (activeTab === "total_market") return "";
    if (metric === "market_share") return "%";
    if (metric === "market_volume") return "";
    return allMetricsData?.[metric]?.unit || "";
  }, [metric, allMetricsData, activeTab]);

  const isPercentTab = metric === "market_share";
  const activeTabLabel =
    TABS.find((t) => t.value === activeTab)?.label ||
    (HIERARCHY_TAB_VALUES.includes(activeTab) ? "Payment Type / Product" : "Total Market Volume");
  const showScenarioControls = activeTab === "total_market";
  const showCompareScenarios = compareScenarioOptions.length > 1;
  const showMetricFilter = activeTab !== "total_market";
  const trajectoryMonthOptions =
    chartData?.months?.slice(chartData?.forecast_start_index) || [];

  const handleTableScroll = (pos) => {
    tableScrollPositionsRef.current[activeTab] = pos;
  };

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

  const toApiMetricKey = (m) => (m === "market_share" ? "payer_share" : "payer_volume");

  function normalizeLiverResponse(data, currentMetric) {
    if (!data) return { months: [], forecast_start_index: 0, tabs: {} };
    const resolvedMetric = currentMetric || metric;

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
    // Apply Filter responses nest market_analysis under scenarios[active].
    // Run Calculation / Refresh responses put market_analysis directly on
    // the root object with no `scenarios` wrapper at all — fall back to
    // treating `data` itself as the scenario object in that case, otherwise
    // ma/chartMa stay undefined and this function bails out with empty tabs
    // even though the response is full of data.
    const sc = data.scenarios
      ? data.scenarios[active]
      : (data.market_analysis ? data : undefined);
    let ma = sc && sc.market_analysis;

    const hasChart = (scenarioData) => {
      const tmv = scenarioData?.market_analysis?.total_market_volume;
      const mv = tmv?.payer_volume || tmv?.payer_share || Object.values(tmv || {})[0];
      return !!(mv?.monthly?.chart?.months?.length || mv?.chart?.months?.length);
    };
    let chartMa = ma;
    if (!hasChart(sc) && data.scenarios) {
      const fallbackKey =
        (data.scenarios["Base"] && hasChart(data.scenarios["Base"]) ? "Base" : null) ||
        Object.keys(data.scenarios).find((k) => hasChart(data.scenarios[k]));
      if (fallbackKey) {
        chartMa = data.scenarios[fallbackKey]?.market_analysis;
      }
    }

    if (!ma && !chartMa) return { months: [], forecast_start_index: 0, tabs: {} };

    const reconcileMarketAnalysisShape = (maObj) => {
      if (!maObj) return maObj;
      const out = { ...maObj };

      if (
        out.payment_type_product &&
        !out.payment_type_product.payer_volume &&
        !out.payment_type_product.payer_share
      ) {
        const container = out.payment_type_product;
        const ptToProduct = container.payment_type_product;
        const productToPt = container.product_payment_type;
        if (ptToProduct && !out.payer_product) out.payer_product = ptToProduct;
        if (productToPt && !out.product_payer) out.product_payer = productToPt;
        out.payment_type_product = ptToProduct || productToPt || container;
      }

      if (!out.payment_type_distribution && out.payer_distribution) {
        out.payment_type_distribution = out.payer_distribution;
      }
      if (!out.payer_distribution && out.payment_type_distribution) {
        out.payer_distribution = out.payment_type_distribution;
      }

      if (out.payer_product && !out.product_payer) out.product_payer = out.payer_product;
      if (out.product_payer && !out.payer_product) out.product_payer = out.payer_product;

      return out;
    };

    ma = reconcileMarketAnalysisShape(ma);
    chartMa = reconcileMarketAnalysisShape(chartMa);

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

    const effectiveMa = ma || chartMa;
    const firstTab = chartMa
      ? (chartMa.total_market_volume || chartMa[Object.keys(chartMa)[0]])
      : (effectiveMa.total_market_volume || effectiveMa[Object.keys(effectiveMa)[0]]);
    const firstMetric =
      firstTab &&
      (firstTab.payer_volume ||
        firstTab.payer_share ||
        Object.values(firstTab)[0]);

    const getMonthlyChart = (metric) => metric?.monthly?.chart || metric?.chart || null;
    const getMonthlyTable = (metric) => metric?.monthly?.table || metric?.table || null;
    const getYearlyChart = (metric) => metric?.yearly?.chart || null;
    const getYearlyTable = (metric) => metric?.yearly?.table || null;

    const months =
      (firstMetric && getMonthlyChart(firstMetric)?.months) || [];
    const fsi =
      (firstMetric && getMonthlyChart(firstMetric)?.forecast_start_index) || 0;

    const selectMetricForTab = (tabKey, tabObj) => {
      if (tabKey === "total_market_volume") {
        return tabObj.payer_volume || Object.values(tabObj)[0];
      }

      const apiMetricKey = resolvedMetric ? toApiMetricKey(resolvedMetric) : null;
      if (apiMetricKey && tabObj[apiMetricKey]) {
        return tabObj[apiMetricKey];
      }
      const isVolumeTab =
        tabKey === "payer_product" || tabKey === "product_payer";
      const isDefaultShareTab =
        tabKey === "product_distribution" ||
        tabKey === "payer_distribution" ||
        tabKey === "payment_type_distribution";

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
          scenario: s.scenario || "",
        })),
      };
    };

    const parseRow = (r, asPercent) => ({
      hierarchy: r.hierarchy || r.label || "",
      label: r.label || r.hierarchy || "",
      total: Array.isArray(r.total) ? parseValues(r.total, asPercent) : undefined,
      values: parseValues(r.values, asPercent),
      children: (r.children || []).map((c) => parseRow(c, asPercent)),
    });
    const parseTableObj = (rawTable, fallbackMonths, asPercent) => {
      if (!rawTable) return { type: "flat", headers: fallbackMonths, rows: [] };
      return {
        type: rawTable.type,
        headers: rawTable.headers || fallbackMonths,
        rows: (rawTable.rows || []).map((r) => parseRow(r, asPercent)),
      };
    };

    const allTabKeys = new Set([
      ...Object.keys(chartMa || {}),
      ...Object.keys(ma || {}),
    ]);
    const tabs = {};

    const mergeYearlyDuplicateBuckets = (chartObj, tableObj) => {
      const months = chartObj?.months;
      if (!months?.length) return { chart: chartObj, table: tableObj };

      const groups = [];
      const groupIndexOfLabel = new Map();
      months.forEach((m, i) => {
        if (groupIndexOfLabel.has(m)) {
          groups[groupIndexOfLabel.get(m)].push(i);
        } else {
          groupIndexOfLabel.set(m, groups.length);
          groups.push([i]);
        }
      });
      if (!groups.some((g) => g.length > 1)) return { chart: chartObj, table: tableObj };

      const mergedMonths = groups.map((g) => months[g[0]]);
      const sumGroups = (arr) =>
        groups.map((g) => g.reduce((total, i) => total + (Number(arr?.[i]) || 0), 0));

      const fsi = chartObj.forecast_start_index || 0;
      const firstForecastGroup = groups.findIndex((g) => g.some((i) => i >= fsi));
      const newFsi = firstForecastGroup === -1 ? groups.length : firstForecastGroup;

      const newChart = {
        ...chartObj,
        months: mergedMonths,
        forecast_start_index: newFsi,
        series: (chartObj.series || []).map((s) => {
          const combined = months.map((_, i) =>
            i < fsi ? s.train_values?.[i] : s.forecast_values?.[i - fsi],
          );
          const merged = sumGroups(combined);
          return {
            ...s,
            train_values: merged.slice(0, newFsi),
            forecast_values: merged.slice(newFsi),
          };
        }),
      };

      const mergeRow = (r) => ({
        ...r,
        total: Array.isArray(r.total) ? sumGroups(r.total) : r.total,
        values: Array.isArray(r.values) ? sumGroups(r.values) : r.values,
        children: (r.children || []).map(mergeRow),
      });
      const newTable = tableObj
        ? { ...tableObj, headers: mergedMonths, rows: (tableObj.rows || []).map(mergeRow) }
        : tableObj;

      return { chart: newChart, table: newTable };
    };

    const buildHierarchyOrderTab = () => {
      const chartOrdersObj = (chartMa || {}).payment_type_payer_product || {};
      const tableOrdersObj = (ma || {}).payment_type_payer_product || chartOrdersObj;
      const orderKeys = new Set([
        ...Object.keys(chartOrdersObj),
        ...Object.keys(tableOrdersObj),
      ]);

      const defaultOrderKeys = ["payment_type_payer_product", "payment_type_product_payer", "product_payment_type_payer"];
      const effectiveOrderKeys = orderKeys.size ? orderKeys : new Set(defaultOrderKeys);

      const orders = {};
      effectiveOrderKeys.forEach((orderKey) => {
        const chartOrderObj = chartOrdersObj[orderKey] || chartOrdersObj;
        const tableOrderObj = tableOrdersObj[orderKey] || chartOrderObj;

        const chartMetric = selectMetricForTab("payment_type_payer_product", chartOrderObj);
        const tableMetric = selectMetricForTab("payment_type_payer_product", tableOrderObj);
        const isPct = chartMetric === chartOrderObj.payer_share;

        const rawMChart = getMonthlyChart(chartMetric);
        const rawMTable = getMonthlyTable(tableMetric);
        const rawYChart = getYearlyChart(chartMetric);
        const rawYTable = getYearlyTable(tableMetric);

        const chart = parseChartObj(rawMChart, months, fsi, isPct);
        const table = parseTableObj(rawMTable, chart.months, isPct);
        let yearlyChart = rawYChart ? parseChartObj(rawYChart, [], 0, isPct) : null;
        let yearlyTable = rawYTable
          ? parseTableObj(rawYTable, yearlyChart?.months || [], isPct)
          : null;
        ({ chart: yearlyChart, table: yearlyTable } = mergeYearlyDuplicateBuckets(yearlyChart, yearlyTable));

        orders[orderKey] = { chart, table, yearlyChart, yearlyTable };
      });

      return { orders };
    };

    allTabKeys.forEach((tabKey) => {
      if (tabKey === "payment_type_payer_product") {
        const built = buildHierarchyOrderTab();
        if (built) tabs[tabKey] = built;
        return;
      }
      if (tabKey === "event_management") return;

      const chartTabObj = (chartMa || {})[tabKey] || {};
      const chartSelectedMetric = selectMetricForTab(tabKey, chartTabObj);
      const isTabPercent = chartSelectedMetric === chartTabObj.payer_share;

      const tableTabObj = (ma || {})[tabKey] || chartTabObj;
      const tableSelectedMetric = selectMetricForTab(tabKey, tableTabObj);

      const rawMonthlyChart = getMonthlyChart(chartSelectedMetric);
      const rawMonthlyTable = getMonthlyTable(tableSelectedMetric);

      const rawYearlyChart = getYearlyChart(chartSelectedMetric);
      const rawYearlyTable = getYearlyTable(tableSelectedMetric);

      const chart = parseChartObj(rawMonthlyChart, months, fsi, isTabPercent);
      const table = parseTableObj(rawMonthlyTable, chart.months, isTabPercent);
      let yearlyChart = rawYearlyChart ? parseChartObj(rawYearlyChart, [], 0, isTabPercent) : null;
      const yearlyTable = rawYearlyTable ? parseTableObj(rawYearlyTable, yearlyChart?.months || [], isTabPercent) : null;

      const hasRealValues = (s) =>
        (s?.train_values || []).some((v) => v != null) ||
        (s?.forecast_values || []).some((v) => v != null);

      if (yearlyChart) {
        yearlyChart = { ...yearlyChart, series: (yearlyChart.series || []).filter(hasRealValues) };
      }

      if (yearlyTable?.rows?.length && (yearlyTable.rows.length > 1 || yearlyTable.type === "hierarchy")) {
        const yearlyHeaders = yearlyTable.headers || yearlyChart?.months || [];
        const yearlyFsi = yearlyChart?.forecast_start_index ?? (() => {
          const firstForecastMonth = chart.months?.[chart.forecast_start_index];
          if (!firstForecastMonth) return yearlyHeaders.length;
          const cutoffYear = String(firstForecastMonth).slice(0, 4);
          const idx = yearlyHeaders.findIndex((h) => String(h || "").startsWith(cutoffYear));
          return idx !== -1 ? idx : yearlyHeaders.length;
        })();

        const flattenTableRows = (rows) => {
          const out = [];
          (rows || []).forEach((r) => {
            const label = r.label || r.hierarchy || "";
            if (label.trim().toLowerCase() === "total") return;
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

      tabs[tabKey] = (() => {
        const merged = mergeYearlyDuplicateBuckets(yearlyChart, yearlyTable);
        return { chart, table, yearlyChart: merged.chart, yearlyTable: merged.table };
      })();

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
            scenarioSeries[scenarioName] = scenarioParsed.series.map((seriesItem) => ({
              ...seriesItem,
              scenario: scenarioName,
            }));
          }
        });
        if (Object.keys(scenarioSeries).length) {
          tabs[tabKey].scenarioSeries = scenarioSeries;
        }
      }
    });

    if (data.scenarios && Object.keys(data.scenarios).length > 0) {
      const tmvTab = tabs["total_market_volume"];
      if (tmvTab) {
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
          if (!metricObj) return;
          const rawRows = metricObj?.monthly?.table?.rows || metricObj?.table?.rows || [];
          const firstRow = rawRows[0];
          if (!firstRow) return;
          let vals = parseValues(firstRow.values, false);
          if (!vals.length) return;

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

            const scenarioYearlyMonths = metricObj?.yearly?.chart?.months || [];
            if (scenarioYearlyMonths.length > 0 && yearlyChartMonthsRef.length > 0 && scenarioYearlyMonths.length !== yearlyChartMonthsRef.length) {
              const yearToVal = {};
              scenarioYearlyMonths.forEach((m, i) => {
                yearToVal[(m || "").substring(0, 4)] = yearlyVals[i];
              });
              yearlyVals = yearlyChartMonthsRef.map((m) => yearToVal[(m || "").substring(0, 4)] ?? null);
            }

            const yearlyMonthlyData = {};
            yearlyChartMonthsRef.forEach((m, i) => {
              const val = yearlyVals[i];
              yearlyMonthlyData[m] = val == null ? null : Number(val);
            });

            yearlyScenarioRows.push({
              hierarchy: scenarioName,
              label: scenarioName,
              total: undefined,
              values: yearlyVals,
              monthly_data: yearlyMonthlyData,
              children: [],
            });
          });

          const allScenarioChartSeries = scenarioRows.map((row) => {
            const scName = row.hierarchy || row.label || "";
            const scMetricObj = (() => {
              const scTmv = data.scenarios?.[scName]?.market_analysis?.total_market_volume;
              return scTmv ? (scTmv.payer_volume || scTmv.payer_share || Object.values(scTmv)[0]) : null;
            })();
            const scChartMonths = scMetricObj?.monthly?.chart?.months || [];
            const scFsiRaw = scMetricObj?.monthly?.chart?.forecast_start_index ?? chartFsi;
            const scForecastMonth = scChartMonths[scFsiRaw];
            const effectiveFsi = scForecastMonth
              ? months.findIndex((m) => (m || "").substring(0, 7) === (scForecastMonth || "").substring(0, 7))
              : -1;
            const splitFsi = effectiveFsi >= 0 ? effectiveFsi : chartFsi;
            return {
              label: scName,
              lot: scName,
              train_values: (row.values || []).slice(0, splitFsi),
              forecast_values: (row.values || []).slice(splitFsi),
            };
          });

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

  const mapRefreshTableResponse = (data) => {
    if (!data) return { chart: null, table: [] };

    if (data.scenarios || data.active_scenario) {
      const normalized = normalizeLiverResponse(data, metric);
      setLiverRawData(data);
      return mapLiverTabToView(normalized, activeTab, totalMarketViewMode);
    }

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

  const mapLiverTabToView = (tabsPayload, uiTabKey, viewMode = "monthly", metricKey = metric) => {
    if (!tabsPayload) return { chart: null, table: [] };
    const {
      months = [],
      forecast_start_index: fsi = 0,
      tabs = {},
    } = tabsPayload;
    const backendKey = TAB_KEY_MAP[uiTabKey] || uiTabKey;
    // Only use this tab's own data. Falling back to Object.keys(tabs)[0]
    // (some other, unrelated tab) when this one is missing silently shows
    // the wrong data instead of an honest "no data" state — e.g. Run
    // Calculation omits payer_product/product_payer entirely, and that
    // fallback was displaying Total Market's scenario chart in their place.
    const tab = tabs[backendKey] || null;
    const activeMetricKey = toApiMetricKey(metricKey);
    if (!tab)
      return {
        chart: { months, forecast_start_index: fsi, series: [] },
        table: [],
      };

    const activeTableData = (viewMode === "yearly" && tab.yearlyTable) ? tab.yearlyTable : tab.table;
    const activeChartData = (viewMode === "yearly" && tab.yearlyChart) ? tab.yearlyChart : tab.chart;
    const activeMonths = (viewMode === "yearly" && tab.yearlyChart) ? (tab.yearlyChart.months || []).slice() : months.slice();
    const activeFsi = (viewMode === "yearly" && tab.yearlyChart)
      ? (tab.yearlyChart.forecast_start_index || 0)
      : fsi;

    const buildSeriesFromTableRows = (rows = []) => {
      const out = [];
      (rows || []).forEach((row) => {
        const rowLabel = row?.hierarchy || row?.label || "";
        if (!rowLabel) return;

        const rowValues = Array.isArray(row?.total)
          ? row.total
          : (Array.isArray(row?.values) ? row.values : []);
        if (rowValues.length) {
          out.push({
            label: rowLabel,
            lot: rowLabel,
            train_values: rowValues.slice(0, activeFsi),
            forecast_values: rowValues.slice(activeFsi),
          });
        }

        (row?.children || []).forEach((child) => {
          const childLabel = `${rowLabel} - ${child?.label || ""}`;
          const childValues = Array.isArray(child?.values) ? child.values : [];
          if (!childValues.length) return;
          out.push({
            label: childLabel,
            lot: childLabel,
            train_values: childValues.slice(0, activeFsi),
            forecast_values: childValues.slice(activeFsi),
          });
        });
      });
      return out;
    };

    let series = (activeChartData?.series || [])
      .filter((s) => {
        const lbl = (s.label || "").toLowerCase();
        if (
          lbl.includes("total") ||
          lbl.includes("market volume") ||
          lbl.includes("market share")
        ) return false;
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

    if (!series.length && (activeTableData?.rows || []).length) {
      series = buildSeriesFromTableRows(activeTableData.rows);
    }

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
    payer: subPayerFilter ? [subPayerFilter] : [],
    brand: productFilter
      ? [productFilter]
      : productOptions?.length
        ? [getFirstOption(productOptions)]
        : [],
    payment_type: payerFilter
      ? [payerFilter]
      : payerOptions?.length
        ? [getFirstOption(payerOptions)]
        : [],
    metric: toApiMetricKey(metric),
    from_date: resolveFromDate(),
    to_date: toDate || "",
    scenario: currentlyAppliedScenario || scenarioSelector || "Base",
  });

  const buildRefreshTablePayload = (hierarchyKey) => {
    const sourceScenario =
      currentlyAppliedScenario ||
      scenarioSelector ||
      liverRawData?.active_scenario ||
      (liverRawData?.scenarios ? Object.keys(liverRawData.scenarios)[0] : "Base") ||
      "Base";

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

    const backendTabKey = TAB_KEY_MAP[activeTab] || activeTab;

    const months = chartData?.months || [];
    const activeMetric = toApiMetricKey(metric);

    const rowToValues = (row) =>
      months.map((m) => {
        const v = row?.monthly_data?.[m];
        return v == null ? 0 : Number(v);
      });

    const tableDataMap = {};
    tableData.forEach((row) => {
      tableDataMap[row.hierarchy] = row;
    });

    const isHierarchicalTab =
      backendTabKey === "payer_product" || backendTabKey === "product_payer";

    let tableRows;
    if (isHierarchicalTab) {
      const origRows =
        fullMarketAnalysis?.[backendTabKey]?.[activeMetric]?.monthly?.table?.rows ||
        fullMarketAnalysis?.[backendTabKey]?.[activeMetric]?.table?.rows ||
        [];

      tableRows = origRows.map((origRow) => {
        const parentLabel = origRow.label || origRow.hierarchy || "";
        const parentTableRow = tableDataMap[parentLabel];
        const parentValues = parentTableRow
          ? rowToValues(parentTableRow)
          : (origRow.values || origRow.total || []);

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
      tableRows = tableData.map((row) => ({
        label: row.hierarchy,
        values: rowToValues(row),
      }));
    }

    const tableType = isHierarchicalTab ? "hierarchical" : "flat";

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
      train_end_month: endDate,
      cfg_periods: forecastPeriods,
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

  useEffect(() => {
    if (!therapyArea) return;
    if (fetchedTaRef.current === therapyArea) return;
    fetchedTaRef.current = therapyArea;
    fetchMetricFilters();
  }, [therapyArea]);

  useEffect(() => {
    const resolvedTa = therapyArea || "HCV";
    if (fetchedMarketEventsTaRef.current === resolvedTa) return;
    fetchedMarketEventsTaRef.current = resolvedTa;
    fetchSavedMarketEvents();
  }, [therapyArea]);

  useEffect(() => {
    const enteredManageEvents =
      activeTab === "manage_events" && prevActiveTabRef.current !== "manage_events";
    prevActiveTabRef.current = activeTab;
    if (enteredManageEvents) {
      fetchSavedMarketEvents();
    }
  }, [activeTab]);

  useLayoutEffect(() => {
    if (!filtersLoaded) return;
    if (activeTab === "manage_events") return;

    let targetMetric = metric;
    if (!userSelectedMetricRef.current) {
      if (activeTab === "total_market") {
        targetMetric = "market_volume";
      } else if (activeTab === "prod_dist" || activeTab === "payer_dist" || activeTab === "payment_payer_prod") {
        targetMetric = "market_share";
      } else if (activeTab === "payer_prod" || activeTab === "prod_payer") {
        targetMetric = "market_volume";
      }
    }

    const isDefaultForOtherTab =
      activeTab === "total_market"
        ? modelSelection === "moving_average"
        : modelSelection === "ets";
    if (isDefaultForOtherTab && modelSelection) {
      const newDefault = activeTab === "total_market" ? "ets" : "moving_average";
      setModelSelection(newDefault);
    }

    if (metric !== targetMetric) {
      setMetric(targetMetric);
      if (targetMetric !== "market_share") setBrand("");
    }

    if (isHCV && liverRawData) {
      const nextLiverTabsRaw = normalizeLiverResponse(liverRawData, targetMetric);

      // Don't blindly overwrite: if this normalization run came up short on
      // the hierarchy orders (e.g. a stale/edge-case response shape), keep
      // whatever orders were already in state instead of wiping them out.
      setLiverTabsRaw((prev) => {
        if (prev?.tabs?.payment_type_payer_product?.orders && !nextLiverTabsRaw?.tabs?.payment_type_payer_product?.orders) {
          return {
            ...nextLiverTabsRaw,
            tabs: {
              ...(nextLiverTabsRaw?.tabs || {}),
              payment_type_payer_product: {
                ...(nextLiverTabsRaw?.tabs?.payment_type_payer_product || {}),
                orders: prev.tabs.payment_type_payer_product.orders,
              },
            },
          };
        }
        return nextLiverTabsRaw;
      });

      if (activeTab === "payment_payer_prod") return;

      const { chart, table } = mapLiverTabToView(
        nextLiverTabsRaw,
        activeTab,
        totalMarketViewMode,
        targetMetric,
      );
      setChartData(chart);
      setTableData(table);
    } else if (metric !== targetMetric && activeTab !== "payment_payer_prod") {
      handleApplyFilterWithMetric(targetMetric);
    }
  }, [activeTab, filtersLoaded, isHCV, liverRawData, totalMarketViewMode]);

  useEffect(() => {
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
    if (activeTab === "manage_events" || activeTab === "payment_payer_prod") return;

    const { chart, table } = mapLiverTabToView(liverTabsRaw, activeTab, totalMarketViewMode, metric);
    setChartData(chart);
    setTableData(table);

    if (Object.keys(expandedBrands).length === 0) {
      let nextExpandedBrands = {};
      if (activeTab === "payer_prod" || activeTab === "prod_payer") {
        const parentNames = Array.from(
          new Set(table.filter((r) => !(r.hierarchy || "").includes(" - ")).map((r) => r.hierarchy)),
        );
        parentNames.forEach((name) => {
          nextExpandedBrands[name] = true;
          if (currentlyAppliedScenario) nextExpandedBrands[`${name} (${currentlyAppliedScenario})`] = true;
        });
      } else if (activeTab === "prod_dist" || activeTab === "payer_dist") {
        nextExpandedBrands = currentlyAppliedScenario ? { [currentlyAppliedScenario]: true } : {};
      }
      if (Object.keys(nextExpandedBrands).length > 0) {
        setExpandedBrands(nextExpandedBrands);
      }
    }
  }, [activeTab, liverTabsRaw, totalMarketViewMode, currentlyAppliedScenario, appliedPayerFilter, appliedProductFilter, payerFilter, productFilter]);

  const resolveScenarioKey = (scenariosObj, name) => {
    if (!scenariosObj || !name) return undefined;
    if (scenariosObj[name]) return name;
    return Object.keys(scenariosObj).find((k) => sameScenario(k, name));
  };

  const otherScenarioChartSeries = useMemo(() => {
    if (activeTab === "total_market" || activeTab === "manage_events" || activeTab === "payment_payer_prod") return [];
    if (!liverRawData?.scenarios) return [];
    const otherNames = (selectedCompareScenarios || []).filter(
      (name) => name && !sameScenario(name, currentlyAppliedScenario),
    );
    if (!otherNames.length) return [];

    const out = [];
    otherNames.forEach((name) => {
      const resolvedKey = resolveScenarioKey(liverRawData.scenarios, name);
      if (!resolvedKey) return;
      const scenarioTabs = normalizeLiverResponse({ ...liverRawData, active_scenario: resolvedKey }, metric);
      const { chart } = mapLiverTabToView(scenarioTabs, activeTab, totalMarketViewMode, metric);
      (chart?.series || []).forEach((s) => {
        out.push({ ...s, scenario: name });
      });
    });
    return out;
  }, [activeTab, liverRawData, selectedCompareScenarios, currentlyAppliedScenario, totalMarketViewMode, metric]);

  const otherScenarioHierarchyData = useMemo(() => {
    if (activeTab !== "payment_payer_prod") return {};
    if (!liverRawData?.scenarios) return {};
    const otherNames = (selectedCompareScenarios || []).filter(
      (name) => name && !sameScenario(name, currentlyAppliedScenario),
    );
    if (!otherNames.length) return {};

    const out = {};
    otherNames.forEach((name) => {
      const resolvedKey = resolveScenarioKey(liverRawData.scenarios, name);
      if (!resolvedKey) return;
      const scenarioTabs = normalizeLiverResponse({ ...liverRawData, active_scenario: resolvedKey }, metric);
      const orders = scenarioTabs?.tabs?.payment_type_payer_product?.orders;
      if (orders) out[name] = orders;
    });
    return out;
  }, [activeTab, liverRawData, selectedCompareScenarios, currentlyAppliedScenario, metric]);

  useEffect(() => {
    if (filterOptions?.scenario_names?.length) {
      const names = filterOptions.scenario_names;
      if (!currentlyAppliedScenario) setCurrentlyAppliedScenario(names[0]);
      if (!tentativeRadioSelectedScenario)
        setTentativeRadioSelectedScenario(names[0]);
    }
  }, [filterOptions.scenario_names]);

  useEffect(() => {
    if (tableEditing) {
      setEditedHierarchies({});
      setIsRefreshed(false);
      setTableEditing(false);
      setEditable(false);
    }
  }, [activeTab]);

  const fetchMetricFilters = async () => {
    try {
      setLoading(true);
      if (isHCV) {
        let cfg = null;

        let localFrom = fromDate || "",
          localTo = toDate || "";
        let localPayer = payerFilter || "",
          localProduct = productFilter || "";
        let localSubPayer = subPayerFilter || "";

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
        if (!localPayer)
          localPayer =
            sfInitial.payment_type ||
            (norm.payers?.length ? getFirstOption(norm.payers) : "");
        if (!localSubPayer) {
          localSubPayer = ["CVS", "Non CVS"].includes(sfInitial.payer) ? sfInitial.payer : "";
        }
        if (!localProduct)
          localProduct =
            sfInitial.product ||
            (norm.products?.length ? getFirstOption(norm.products) : "");
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
        setSubPayerFilter(localSubPayer);
        setAppliedPayerFilter(localPayer);
        setAppliedProductFilter(localProduct);
        setAppliedSubPayerFilter(localPayer === "Cash" ? "" : localSubPayer);
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

  const resolveModelForTab = (backendModel) => {
    if (!backendModel) {
      return activeTab === "total_market" ? "ets" : "moving_average";
    }
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
          metric: toApiMetricKey(effectiveMetric),
        });
        const data = response?.data || {};
        setAppliedLot(lot);
        setAppliedBrand(productFilter || brand);
        setAppliedPayerFilter(payerFilter);
        setAppliedProductFilter(productFilter);
        setAppliedSubPayerFilter(payerFilter === "Cash" ? "" : subPayerFilter);
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
        setAppliedSubPayerFilter(payerFilter === "Cash" ? "" : subPayerFilter);
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
        const sourceScenario =
          currentlyAppliedScenario ||
          scenarioSelector ||
          liverRawData?.active_scenario ||
          (liverRawData?.scenarios ? Object.keys(liverRawData.scenarios)[0] : "Base") ||
          "Base";

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
            payer: appliedSubPayerFilter || subPayerFilter || "",
            product: appliedProductFilter || productFilter || getFirstOption(productOptions) || "",
            start_date: resolveFromDate(),
            end_date: toDate || "",
          },
          source_scenario: sourceScenario,
          factors: buildFullFactors(),
          market_analysis: marketAnalysis,
        };

        const resp = await saveLiverScenario(payload);

        showSnackbar("Scenario saved successfully", "success");

        setFilterOptions((prev) => {
          const names = prev.scenario_names || [];
          if (names.includes(scenarioNameFromDialog)) return prev;
          return { ...prev, scenario_names: [...names, scenarioNameFromDialog] };
        });

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
            // Keep whatever scenario was already applied/selected instead of
            // switching to the newly saved one — saving a scenario should not
            // auto-select or auto-apply it.
            initializeCompareScenarios(respData);
          }
        }

        setSavedScenarioRows((prev) => {
          const scenarioInResponse =
            respData?.scenarios?.[scenarioNameFromDialog] ||
            respData?.available_scenarios?.includes(scenarioNameFromDialog);
          if (scenarioInResponse) return prev.filter((n) => n !== scenarioNameFromDialog);
          return prev.includes(scenarioNameFromDialog)
            ? prev
            : [...prev, scenarioNameFromDialog];
        });

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
      // Do not auto-select the newly saved scenario — leave the current
      // scenarioSelector as-is so the user has to pick it explicitly.
    } catch (err) {
      console.error("[SaveScenario] error:", err?.response?.data || err);
      showSnackbar("Failed to save scenario", "error");
    } finally {
      setLoading(false);
    }
  };

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

  const handleConfirmSave = async () => {
    const activeScenario = currentlyAppliedScenario || scenarioSelector || "";
    const isBase = activeScenario.toLowerCase() === "base";

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
      setNewScenarioName("");
      setSaveScenarioDialogOpen(true);
      return;
    }

    const backendSf = liverRawData?.selected_filter || {};
    const updatePayload = {
      ta_name: therapyArea || "HCV",
      selected_filter: {
        start_date: backendSf.start_date || resolveFromDate(),
        end_date: backendSf.end_date || toDate || "",
        payment_type: backendSf.payment_type || appliedPayerFilter || payerFilter || getFirstOption(payerOptions) || "",
        payer: backendSf.payer || appliedSubPayerFilter || subPayerFilter || "",
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
      const payload = buildRefreshTablePayload(editedKeys);
      const response = await refreshLiverTable(payload);
      const lastRawData = response?.data || {};
      if (lastRawData) {
        const { chart, table } = mapRefreshTableResponse(lastRawData);
        setChartData(chart);
        setTableData(table);

        if (lastRawData.scenarios || lastRawData.active_scenario) {
          const normalized = normalizeLiverResponse(lastRawData, metric);
          setLiverTabsRaw(normalized);
        } else {
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
      setIsRefreshed(false);
      setTableEditing(false);
      setEditable(false);
      showSnackbar("Table refreshed successfully.", "success");
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

  // SAFE RECONCILIATION FIX: Preserves nested `orders` mapping to prevent blank page crashes
  const handleSaveHierarchyTableChanges = async ({ editedCells, backendOrderKey, columns, rows }) => {
    const editedKeys = Object.keys(editedCells || {});
    if (!editedKeys.length) {
      showSnackbar("No changes to save", "info");
      setTableEditing(false);
      setEditable(false);
      return;
    }
    try {
      setSavingTable(true);
      setLoading(true);

      const sourceScenario =
        currentlyAppliedScenario ||
        scenarioSelector ||
        liverRawData?.active_scenario ||
        (liverRawData?.scenarios ? Object.keys(liverRawData.scenarios)[0] : "Base") ||
        "Base";

      // liverRawData may come from either Apply Filter (market_analysis nested
      // under scenarios[name]) or Run Calculation (market_analysis at the
      // root, no `scenarios` wrapper). Reading only the nested shape silently
      // produced an empty market_analysis whenever liverRawData had the
      // Run Calculation shape, which sent a gutted payload to refreshLiverTable
      // and made "Refresh" fail. Fall back to the root object in that case.
      let fullMarketAnalysis = liverRawData?.scenarios
        ? liverRawData.scenarios[sourceScenario]?.market_analysis
        : liverRawData?.market_analysis;

      if (!fullMarketAnalysis && liverRawData?.scenarios) {
        const matchedKey = Object.keys(liverRawData.scenarios).find(
          (k) => k.toLowerCase() === sourceScenario.toLowerCase()
        );
        fullMarketAnalysis = matchedKey
          ? liverRawData.scenarios[matchedKey]?.market_analysis
          : Object.values(liverRawData.scenarios)[0]?.market_analysis;
      }
      fullMarketAnalysis = fullMarketAnalysis || {};

      const activeMetric = toApiMetricKey(metric);
      const container = fullMarketAnalysis.payment_type_payer_product || {};
      const orderObj = container[backendOrderKey] || {};
      const origRows = orderObj?.[activeMetric]?.monthly?.table?.rows || [];

      const editsByRowKey = {};
      editedKeys.forEach((cellKey) => {
        const sep = cellKey.lastIndexOf("::");
        if (sep === -1) return;
        const rowKey = cellKey.slice(0, sep);
        const colKey = cellKey.slice(sep + 2);
        const col = (columns || []).find((c) => c.key === colKey);
        if (!col) return;
        if (!editsByRowKey[rowKey]) editsByRowKey[rowKey] = {};
        editsByRowKey[rowKey][col.indices[0]] = Number(editedCells[cellKey]) || 0;
      });

      const patchedValuesByRowKey = {};
      Object.keys(editsByRowKey).forEach((rowKey) => {
        const row = (rows || []).find((r) => r.key === rowKey);
        const base = row ? [...(row.values || [])] : [];
        Object.entries(editsByRowKey[rowKey]).forEach(([idx, val]) => {
          base[Number(idx)] = val;
        });
        patchedValuesByRowKey[rowKey] = base;
      });

      // Track every ancestor path of an edited row, so their aggregate
      // totals can be recalculated as well, not just the exact edited row.
      const touchedAncestorPaths = new Set();
      Object.keys(patchedValuesByRowKey).forEach((path) => {
        const parts = path.split(" > ");
        for (let i = 1; i < parts.length; i++) {
          touchedAncestorPaths.add(parts.slice(0, i).join(" > "));
        }
      });
      const sumArrays = (arrs) => {
        const length = arrs.reduce((max, a) => Math.max(max, (a || []).length), 0);
        return Array.from({ length }, (_, i) =>
          arrs.reduce((sum, a) => sum + (Number(a?.[i]) || 0), 0)
        );
      };

      const patchTree = (nodes, ancestorPath) =>
        (nodes || []).map((n) => {
          const label = n.label || n.hierarchy || "";
          const path = ancestorPath ? `${ancestorPath} > ${label}` : label;
          const next = { ...n };
          if (n.children?.length) next.children = patchTree(n.children, path);
          if (patchedValuesByRowKey[path]) {
            // This exact row was edited — use the typed value directly.
            const newVals = patchedValuesByRowKey[path];
            if (Array.isArray(next.total)) next.total = newVals;
            else next.values = newVals;
          } else if (touchedAncestorPaths.has(path) && next.children?.length) {
            // Not edited directly, but a descendant was — roll the
            // aggregate up from the (already patched) children instead of
            // sending the stale pre-edit total for this row.
            const childArrays = next.children.map(
              (c) => (Array.isArray(c.total) ? c.total : c.values) || []
            );
            const rolledUp = sumArrays(childArrays);
            if (Array.isArray(next.total)) next.total = rolledUp;
            else next.values = rolledUp;
          }
          return next;
        });
      const patchedRows = patchTree(origRows, "");

      // The chart's own series (history/forecast) is a separate, coarser
      // (max 2-level) representation of the same tree. It was never being
      // patched, so it kept pointing at pre-edit numbers even though
      // table.rows was patched — if the backend uses chart series as the
      // source of truth for recompute, the edit would be invisible to it.
      // Derive matching series values from the same patched/rolled-up tree.
      const rawChart = orderObj?.[activeMetric]?.monthly?.chart;
      const chartFsiForPatch = rawChart?.forecast_start_index ?? 0;
      const patchedSeriesByLabel = {};
      patchedRows.forEach((r) => {
        const rLabel = r.label || r.hierarchy || "";
        if (r.children?.length) {
          r.children.forEach((c) => {
            const cLabel = c.label || c.hierarchy || "";
            patchedSeriesByLabel[`${rLabel} - ${cLabel}`] =
              (Array.isArray(c.total) ? c.total : c.values) || [];
          });
        } else {
          patchedSeriesByLabel[rLabel] = (Array.isArray(r.total) ? r.total : r.values) || [];
        }
      });
      const patchedChartSeries = (rawChart?.series || []).map((s) => {
        const patched = patchedSeriesByLabel[s.label];
        if (!patched) return s;
        return {
          ...s,
          history: patched.slice(0, chartFsiForPatch),
          forecast: patched.slice(chartFsiForPatch),
        };
      });

      const mergedMarketAnalysis = {
        ...fullMarketAnalysis,
        payment_type_payer_product: {
          ...container,
          [backendOrderKey]: {
            ...orderObj,
            [activeMetric]: {
              ...(orderObj?.[activeMetric] || {}),
              monthly: {
                ...(orderObj?.[activeMetric]?.monthly || {}),
                table: { type: "hierarchical", rows: patchedRows },
                chart: rawChart ? { ...rawChart, series: patchedChartSeries } : rawChart,
              },
            },
          },
        },
      };

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

      const backendSf = liverRawData?.selected_filter || {};
      const endDate = backendSf.end_date || toDate || "";
      const startDate = backendSf.start_date || resolveFromDate();
      const forecastPeriods = chartData?.months?.length
        ? chartData.months.length - (chartData.forecast_start_index ?? 0)
        : 0;

      const payload = {
        ta_name: therapyArea || "HCV",
        selected_filter: {
          market: backendSf.payer || appliedPayerFilter || payerFilter || getFirstOption(payerOptions) || "",
          product: backendSf.product || appliedProductFilter || productFilter || getFirstOption(productOptions) || "",
          start_date: startDate,
          end_date: endDate,
        },
        train_end_month: endDate,
        cfg_periods: forecastPeriods,
        forecast_periods: forecastPeriods,
        scenario_name: sourceScenario,
        selected_tab: TAB_KEY_MAP.payment_payer_prod,
        selected_metric: activeMetric,
        edited_hierarchy: Object.keys(patchedValuesByRowKey).join(", "),
        factors: activeFactors,
        market_analysis: mergedMarketAnalysis,
      };

      const response = await refreshLiverTable(payload);
      const respData = response?.data || {};
      if (respData && Object.keys(respData).length) {
        setLiverRawData(respData);
        const normalized = normalizeLiverResponse(respData, metric);
        
        // Preserve nested hierarchy orders mapping to prevent empty state rendering
        setLiverTabsRaw((prev) => {
          const updatedTabs = { ...(normalized?.tabs || {}) };
          if (prev?.tabs?.payment_type_payer_product?.orders) {
            updatedTabs.payment_type_payer_product = {
              ...(updatedTabs.payment_type_payer_product || {}),
              orders: {
                ...prev.tabs.payment_type_payer_product.orders,
                ...(updatedTabs.payment_type_payer_product?.orders || {}),
              },
            };
          }
          return {
            ...(normalized || {}),
            tabs: updatedTabs,
          };
        });

        initializeCompareScenarios(respData);

        // Keep FE scenario state in sync with what the backend actually
        // returned — different endpoints have used different casing for the
        // same scenario (e.g. Run Calculation's "BASE" vs this endpoint's
        // "Base"). Without this, currentlyAppliedScenario goes stale after
        // Refresh and later lookups keyed by scenario name silently miss.
        if (respData.active_scenario) {
          setCurrentlyAppliedScenario(respData.active_scenario);
          setTentativeRadioSelectedScenario(respData.active_scenario);
        }
      }

      setIsRefreshed(false);
      setTableEditing(false);
      setEditable(false);
      showSnackbar("Table refreshed successfully.", "success");
    } catch (error) {
      console.error("Failed to refresh hierarchy table:", error);
      const msg = error?.response?.data || error?.message || "Unknown error";
      showSnackbar(typeof msg === "string" ? msg : "Failed to refresh table", "error");
    } finally {
      setSavingTable(false);
      setLoading(false);
    }
  };

  const handleMetricChange = async (nm) => {
    userSelectedMetricRef.current = true;
    setTabMetrics((prev) => ({
      ...prev,
      [activeTab]: nm,
    }));

    if (tableEditing) {
      setTableData(tableSnapshot);
      setEditedHierarchies({});
      setTableEditing(false);
      setEditable(false);
    }
    if (nm !== "market_share") setBrand("");
    if (isHCV && liverRawData) {
      setLiverTabsRaw(normalizeLiverResponse(liverRawData, nm));
    } else {
      await handleApplyFilterWithMetric(nm);
    }
  };

  const handleDownloadTable = () => {
    try {
      const isYearly = totalMarketViewMode === "yearly";

      if (activeTab === "payment_payer_prod") {
        const activeOrderKey = TAB_KEY_MAP[activeTab];
        const realOrder = liverTabsRaw?.tabs?.[activeOrderKey]?.orders?.[ORDER_TO_BACKEND_KEY?.["pt-payer-product"] || "payment_type_payer_product"];
        const realTable = isYearly ? realOrder?.yearlyTable : realOrder?.table;

        const headers = realTable?.headers?.length
          ? realTable.headers
          : availableDates || [];
        const formattedHeaders = isYearly
          ? headers
          : headers.map((h) => formatDateLabel(h));

        const headerRow = ["Hierarchy Path", ...formattedHeaders];
        const csvRows = [headerRow];

        const extractHierarchyRows = (nodes, ancestorLabels = []) => {
          (nodes || []).forEach((node) => {
            const currentPath = [...ancestorLabels, node.label || node.hierarchy || ""].join(" > ");
            const vals = Array.isArray(node.total) ? node.total : node.values || [];

            const rowValues = headers.map((_, idx) => {
              const v = vals[idx];
              if (v == null) return "";
              return metric === "market_share"
                ? `${Number(v).toFixed(1)}%`
                : Math.round(Number(v)).toString();
            });

            csvRows.push([currentPath, ...rowValues]);

            if (node.children?.length) {
              extractHierarchyRows(node.children, [...ancestorLabels, node.label || node.hierarchy || ""]);
            }
          });
        };

        if (realTable?.rows?.length) {
          extractHierarchyRows(realTable.rows);
        }

        const csvContent = csvRows
          .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))
          .join("\n");

        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${activeTabLabel.replace(/\s+/g, "_")}_Full_Hierarchy.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        return;
      }

      const months = chartData?.months || [];
      const formattedHeaders = months.map((m) => (isYearly ? m : formatDateLabel(m)));
      const headerRow = ["Product / Scenario", ...formattedHeaders];

      const rows = tableData.map((r) => [
        r.hierarchy,
        ...months.map((m) => {
          const v = r.monthly_data?.[m];
          if (v == null) return "";
          return metricUnit === "%" ? `${Number(v).toFixed(1)}%` : Math.round(Number(v));
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
      console.error("Failed to download CSV:", e);
      showSnackbar("Failed to download table", "error");
    }
  };

  const initializeCompareScenarios = (response, appliedScenario) => {
    const scenarios =
      response?.available_scenarios ||
      (response?.scenarios ? Object.keys(response.scenarios) : []);

    // Different endpoints have returned different casing for the same
    // scenario (e.g. Run Calculation's "BASE" vs Refresh's "Base"). A plain
    // `.includes` check treats those as two different scenarios and adds a
    // bogus duplicate that silently fails to load if ever selected. Compare
    // case-insensitively instead.
    const toAdd = appliedScenario || currentlyAppliedScenario || "";
    const alreadyPresent = toAdd && scenarios.some((s) => s.toLowerCase() === toAdd.toLowerCase());
    const merged = toAdd && !alreadyPresent
      ? [...scenarios, toAdd]
      : scenarios;

    if (!merged.length) return;
    setCompareScenarioOptions(merged);
    setSelectedCompareScenarios((prev) => {
      if (!userHasCustomizedCompare || !prev.length) return merged;
      const stillValid = prev.filter((name) => merged.includes(name));
      return stillValid.length ? stillValid : merged;
    });
  };

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

  const handleDeleteScenarioClick = (scenarioName) => {
    setScenarioToDelete(scenarioName);
    setDeleteDialogOpen(true);
  };

  const EVENT_TYPE_TO_API = {
    Product: "product_event",
    Payer: "payment_type_event",
    PaymentType_Payer_Product: "payment_type_payer_product_event",
  };
  const EVENT_TYPE_FROM_API = Object.fromEntries(
    Object.entries(EVENT_TYPE_TO_API).map(([feType, beType]) => [beType, feType]),
  );

  const CURVE_TYPE_FROM_API = {
    linear: "Linear",
    exponential: "Exponential",
    logarithmic: "Logarithmic",
    scurve: "S-Curve",
  };
  const toArray = (val) => {
    if (Array.isArray(val)) return val.filter((v) => v !== null && v !== undefined && v !== "");
    if (typeof val === "string") {
      return val
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    }
    if (val === null || val === undefined) return [];
    return [val];
  };

  const mapApiRowToLocalEvent = (row, fallbackEventType) => {
    const apiEventType = row.event_type || fallbackEventType || "product_event";
    const feEventType = EVENT_TYPE_FROM_API[apiEventType] || "Product";
    const isPPPRow = feEventType === "PaymentType_Payer_Product";
    return {
      id: row.event_id ?? row.event_name ?? `evt_${Math.random().toString(36).slice(2)}`,
      eventType: feEventType,
      name: row.event_name || "",
      paymentTypes: isPPPRow ? toArray(row.payment_types) : [],
      products: toArray(row.products),
      payers: isPPPRow ? toArray(row.payers) : toArray(row.payment_types),
      impactedItems: toArray(
        row.impacted_products ??
          row.impacted_payment_types ??
          row.impacted_payers ??
          row.impacted_items,
      ),
      sourcePercentages: row.source_percentages || {},
      startDate: row.start_date || "",
      peakPercent: Number(row.peak_percent) || 0,
      months: Number(row.months) || 0,
      curveType: CURVE_TYPE_FROM_API[row.curve_type] || "Linear",
      factor: Number(row.factor) || 0,
      persisted: true,
    };
  };

  const fetchSavedMarketEvents = async () => {
    try {
      const res = await getLiverMarketEventsList(therapyArea || "HCV");
      const data = res?.data || {};
      const eventsManagement = data?.events_management;

      let rawRows = [];
      if (eventsManagement) {
        rawRows = [
          "product_event",
          "payment_type_event",
          "payment_type_payer_product_event",
        ].flatMap((eventType) => {
          const rows = eventsManagement?.[eventType]?.impact_curve_configuration?.rows || [];
          return rows.map((r) => ({ ...r, event_type: r.event_type || eventType }));
        });
      }

      setMarketEvents(
        Array.isArray(rawRows) ? rawRows.map((r) => mapApiRowToLocalEvent(r, r.event_type)) : []
      );
    } catch (error) {
      console.error("Failed to fetch saved market events:", error);
    }
  };

  const buildMarketEventRow = (evt) => {
    const isPPPEvt = evt.eventType === "PaymentType_Payer_Product";
    const isPayerEvt = evt.eventType === "Payer";

    return {
      event_id: typeof evt.id === "number" ? evt.id : 0,
      event_name: evt.name,
      start_date: evt.startDate,
      peak_percent: Number(evt.peakPercent) || 0,
      months: Number(evt.months) || 0,
      curve_type: CURVE_TYPE_TO_API[evt.curveType] || String(evt.curveType || "").toLowerCase(),
      factor: evt.curveType === "Linear" ? 0 : Number(evt.factor) || 0,
      payment_types: (isPPPEvt ? evt.paymentTypes : evt.payers) || [],
      payers: isPPPEvt ? (evt.payers || []) : [],
      products: evt.products || [],
      source_percentages: evt.sourcePercentages || {},
      impacted_products: isPayerEvt ? [] : (evt.impactedItems || []),
      impacted_payment_types: isPayerEvt ? (evt.impactedItems || []) : [],
    };
  };

  const handleSaveMarketEvent = async (event) => {
    const idx = marketEvents.findIndex((e) => e.id === event.id);
    const nextEvents =
      idx === -1
        ? [...marketEvents, event]
        : marketEvents.map((e, i) => (i === idx ? event : e));
    setMarketEvents(nextEvents);
    await handleSaveMarketEventsToServer(nextEvents);
  };

  const CURVE_TYPE_TO_API = {
    Linear: "linear",
    Exponential: "exponential",
    Logarithmic: "logarithmic",
    "S-Curve": "scurve",
  };

  const handleDeleteMarketEvent = async (evt) => {
    if (!evt || !evt.name) return;

    try {
      setLoading(true);
      const apiEventType = EVENT_TYPE_TO_API[evt.eventType] || "product_event";

      await deleteLiverMarketEvent(evt.name, {
        ta_name: therapyArea || "HCV",
        event_type: apiEventType,
      });

      await fetchSavedMarketEvents();
      showSnackbar("Market event deleted successfully", "success");
    } catch (error) {
      console.error("Failed to delete market event:", error);
      const status = error?.response?.status;
      if (status === 404) {
        setMarketEvents((prev) => prev.filter((e) => e.id !== evt.id));
        showSnackbar("Event removed (it was never saved to the server)", "success");
      } else {
        const msg = error?.response?.data || error?.message || "Failed to delete market event";
        showSnackbar(typeof msg === "string" ? msg : "Failed to delete market event", "error");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSaveMarketEventsToServer = async (eventsOverride) => {
    const eventsToSave = eventsOverride || marketEvents;
    if (!eventsToSave.length) {
      showSnackbar("No market events to save", "error");
      return;
    }
    try {
      setSavingMarketEvents(true);
      setLoading(true);

      const selectedFilter = {
        payment_types: payerOptions || [],
        payers: [],
        products: productOptions || [],
        start_date: resolveFromDate() || liverRawData?.selected_filter?.start_date || "",
        end_date: toDate || liverRawData?.selected_filter?.end_date || "",
      };

      const groupsByType = eventsToSave.reduce((acc, evt) => {
        (acc[evt.eventType] ||= []).push(evt);
        return acc;
      }, {});

      await Promise.all(
        Object.entries(groupsByType).map(([evtType, evts]) =>
          saveLiverMarketEventsConfig({
            ta_name: therapyArea || "HCV",
            selected_filter: selectedFilter,
            selected_tab: EVENT_TYPE_TO_API[evtType] || "product_event",
            impact_curve_configuration: { rows: evts.map(buildMarketEventRow) },
          })
        )
      );

      await fetchSavedMarketEvents();
      showSnackbar("Market event saved successfully", "success");
    } catch (error) {
      console.error("Failed to save market events:", error);
      const msg = error?.response?.data || error?.message || "Unknown error";
      showSnackbar(typeof msg === "string" ? msg : "Failed to save market events", "error");
    } finally {
      setSavingMarketEvents(false);
      setLoading(false);
    }
  };

  const handleRunMarketEventsCalculation = async (selectedEventIdsFromPanel) => {
    try {
      setRunningMarketEventsCalculation(true);
      setLoading(true);

      const formattedStartDate = resolveFromDate()
        ? dayjs(resolveFromDate(), DATE_INPUT_FORMATS).format("YYYY-MM-01")
        : "2020-04-01";

      const formattedEndDate = toDate
        ? dayjs(toDate, DATE_INPUT_FORMATS).format("YYYY-MM-01")
        : "2027-09-01";

      const currentScenario = currentlyAppliedScenario || scenarioSelector || "BASE";
      const normalizedScenario = currentScenario.toLowerCase() === "base"
        ? "BASE"
        : currentScenario;

      const activeSelectedIds = Array.isArray(selectedEventIdsFromPanel) && selectedEventIdsFromPanel.length > 0
        ? selectedEventIdsFromPanel
        : marketEvents.map((e) => e.id);

      const filteredEvents = marketEvents
        .filter((evt) => activeSelectedIds.includes(evt.id))
        .map((evt) => ({
          event_name: evt.name,
          event_type: EVENT_TYPE_TO_API[evt.eventType] || "product_event",
        }));

      const payload = {
        ta_name: therapyArea || "HCV",
        selected_filter: {
          scenario_name: normalizedScenario,
          payment_type: payerFilter
            ? [payerFilter]
            : payerOptions?.length
              ? [payerOptions[0]]
              : ["Commercial"],
          products: productFilter
            ? [productFilter]
            : productOptions?.length
              ? [productOptions[0]]
              : ["ASGA"],
          start_date: formattedStartDate,
          end_date: formattedEndDate,
        },
        events: filteredEvents,
      };

      const response = await runLiverMarketEventsCalculation(payload);
      const respData = response?.data || {};

      if (respData && Object.keys(respData).length) {
        setLiverRawData(respData);
        const normalized = normalizeLiverResponse(respData, metric);
        setLiverTabsRaw(normalized);

        const { chart, table } = mapLiverTabToView(normalized, activeTab, totalMarketViewMode, metric);
        setChartData(chart);
        setTableData(table);

        if (respData.available_months?.length) setAvailableDates(respData.available_months);
        initializeCompareScenarios(respData);

        // Keep FE scenario state in sync with what the backend returned.
        // Without this, currentlyAppliedScenario stays stale/empty after
        // Run Calculation, and otherScenarioChartSeries's "exclude the
        // applied scenario" filter fails to exclude it — producing a
        // duplicate trace (e.g. "Cash" and "Cash (BASE)" both showing the
        // same data) alongside the genuine comparison scenario's trace.
        if (respData.active_scenario) {
          setCurrentlyAppliedScenario(respData.active_scenario);
          setTentativeRadioSelectedScenario(respData.active_scenario);
        }
      }

      showSnackbar("Market events calculation completed successfully!", "success");
    } catch (error) {
      console.error("Failed to run market events calculation:", error);
      const msg = error?.response?.data?.detail || error?.response?.data || error?.message || "Unknown error";
      showSnackbar(typeof msg === "string" ? msg : JSON.stringify(msg), "error");
    } finally {
      setRunningMarketEventsCalculation(false);
      setLoading(false);
    }
  };

  const handleAddMarketEventProduct = async (productName) => {
    await addLiverMarketEventsProduct({ product_name: productName });
    setProductOptions((prev) => (prev.includes(productName) ? prev : [...prev, productName]));
  };

  const handleDeleteScenario = async (scenarioName) => {
    if (!scenarioName) return;

    try {
      setLoading(true);
      const payload = {
        ta_name: therapyArea || "HCV",
        selected_filter: {
          start_date: resolveFromDate() || liverRawData?.selected_filter?.start_date || "",
          end_date: toDate || liverRawData?.selected_filter?.end_date || "",
          payment_type: appliedPayerFilter || payerFilter || liverRawData?.selected_filter?.payment_type || getFirstOption(payerOptions) || "",
          payer: appliedSubPayerFilter || subPayerFilter || liverRawData?.selected_filter?.payer || "",
          product: appliedProductFilter || productFilter || liverRawData?.selected_filter?.product || getFirstOption(productOptions) || "",
        },
        scenario_name: scenarioName,
      };

      const response = await deleteLiverScenario(payload);
      const respData = response?.data || {};

      if (respData && Object.keys(respData).length) {
        const normalized = normalizeLiverResponse(respData, metric);
        setLiverTabsRaw(normalized);
        setLiverRawData(respData);
        initializeCompareScenarios(respData, respData?.active_scenario || "Base");
        setCurrentlyAppliedScenario(respData?.active_scenario || "Base");
        setTentativeRadioSelectedScenario(respData?.active_scenario || "Base");
        setSavedScenarioRows((prev) => prev.filter((name) => name !== scenarioName));
      }

      showSnackbar("Scenario deleted successfully", "success");
    } catch (error) {
      console.error("Failed to delete scenario:", error);
      const msg = error?.response?.data || error?.message || "Unknown error";
      showSnackbar(typeof msg === "string" ? msg : "Failed to delete scenario", "error");
    } finally {
      setLoading(false);
      setDeleteDialogOpen(false);
      setScenarioToDelete("");
    }
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
          start_date: resolveFromDate() || backendSf.start_date,
          end_date: toDate || backendSf.end_date || "",
          payment_type: appliedPayerFilter || payerFilter || backendSf.payment_type || getFirstOption(payerOptions) || "",
          payer: appliedSubPayerFilter || subPayerFilter || backendSf.payer || "",
          product: appliedProductFilter || productFilter || backendSf.product || getFirstOption(productOptions) || "",
        },
        scenario_name: chosenScenario,
      };

      const response = await activateLiverScenario(payload);
      const respData = response?.data;

      setCurrentlyAppliedScenario(chosenScenario);

      setSelectedCompareScenarios((prev) => {
        if (prev.includes(chosenScenario)) return prev;
        return [...prev, chosenScenario];
      });

      if (respData && (respData.scenarios || respData.active_scenario)) {
        const normalized = normalizeLiverResponse(respData, metric);
        setLiverTabsRaw(normalized);
        setLiverRawData(respData);

        const activatedScenarioObj = respData.scenarios?.[chosenScenario] || null;
        const f = activatedScenarioObj?.factors || {};
        if (Object.keys(f).length) {
          let am = f?.active_model || modelSelection;
          am = resolveModelForTab(am);
          setModelSelection(am);
          syncFactors(f, am);
        }
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
                PAYMENT TYPE
              </Typography>
              <FormControl sx={inputStyle}>
                <Select
                  value={payerFilter}
                  onChange={(e) => {
                    const val = e.target.value;
                    setPayerFilter(val);
                    if (val === "Cash") setSubPayerFilter("");
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
                PAYER FILTER
              </Typography>
              <FormControl sx={inputStyle} disabled={payerFilter === "Cash"}>
                <Select
                  value={subPayerFilter}
                  onChange={(e) => setSubPayerFilter(e.target.value)}
                  displayEmpty
                  disabled={payerFilter === "Cash"}
                  renderValue={(sel) => (["CVS", "Non CVS"].includes(sel) ? sel : "Select")}
                >
                  {["CVS", "Non CVS"].map((p) => (
                    <MenuItem key={p} value={p}>
                      {p}
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
              disabled={
                !resolveFromDate() ||
                !toDate ||
                !payerFilter ||
                (payerFilter !== "Cash" && !subPayerFilter)
              }
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

                          const opts = forecastMonths.length ? forecastMonths : trajectoryMonthOptions;

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
          {TABS.map((tab) => {
            const isActive =
              tab.value === "payer_prod"
                ? HIERARCHY_TAB_VALUES.includes(activeTab)
                : activeTab === tab.value;
            return (
              <Box
                key={tab.value}
                onClick={() => {
                  if (tab.value === "payer_prod" && HIERARCHY_TAB_VALUES.includes(activeTab)) return;
                  setActiveTab(tab.value);
                }}
                sx={{
                  px: 2,
                  py: 1,
                  cursor: "pointer",
                  fontSize: "12px",
                  fontWeight: 600,
                  borderRadius: "6px 6px 0 0",
                  color: isActive ? "#4F46E5" : "#64748b",
                  backgroundColor: isActive ? "white" : "transparent",
                  border: isActive
                    ? "1px solid #D8DEE8"
                    : "1px solid transparent",
                  borderBottom: isActive
                    ? "1px solid white"
                    : "1px solid transparent",
                  mb: isActive ? "-1px" : 0,
                  userSelect: "none",
                  "&:hover": {
                    backgroundColor: isActive ? "white" : "#f1f5f9",
                  },
                }}
              >
                {tab.label}
              </Box>
            );
          })}
        </Box>

        {/* ── TAB CONTENT ── */}
        <Box sx={{ p: 3 }}>
          {activeTab !== "manage_events" && (
            <MarketEventsPanel
              variant="compact"
              events={marketEvents}
              onSave={handleSaveMarketEvent}
              onDelete={handleDeleteMarketEvent}
              productOptions={productOptions}
              payerOptions={payerOptions}
              availableDates={availableDates}
              onRunCalculation={handleRunMarketEventsCalculation}
              runningCalculation={runningMarketEventsCalculation}
            />
          )}

          {activeTab === "manage_events" ? (
            <MarketEventsPanel
              variant="table"
              events={marketEvents}
              onSave={handleSaveMarketEvent}
              onDelete={handleDeleteMarketEvent}
              productOptions={productOptions}
              payerOptions={payerOptions}
              availableDates={availableDates}
            />
          ) : activeTab === "payment_payer_prod" ? (
            <PaymentPayerProductTable
              activeTabLabel={activeTabLabel}
              payerOptions={payerOptions}
              productOptions={productOptions}
              months={availableDates}
              metric={metric}
              metricUnit={metricUnit}
              filterOptions={filterOptions}
              handleMetricChange={handleMetricChange}
              totalMarketViewMode={totalMarketViewMode}
              setTotalMarketViewMode={setTotalMarketViewMode}
              appliedPayerFilter={appliedPayerFilter}
              appliedProductFilter={appliedProductFilter}
              appliedSubPayerFilter={appliedSubPayerFilter}
              hierarchyData={liverTabsRaw?.tabs?.payment_type_payer_product?.orders}
              otherScenarioHierarchyData={otherScenarioHierarchyData}
              appliedScenario={currentlyAppliedScenario}
              selectedCompareScenarios={selectedCompareScenarios}
              compareScenarioOptions={compareScenarioOptions}
              handleCompareScenarioChange={handleCompareScenarioChange}
              handleDownloadTable={handleDownloadTable}
              handleConfirmSave={handleConfirmSave}
              handleEnterTableEdit={handleEnterTableEdit}
              handleSaveTableChanges={handleSaveTableChanges}
              onSaveHierarchyChanges={handleSaveHierarchyTableChanges}
              handleCancelTableEdit={handleCancelTableEdit}
              tableEditing={tableEditing}
              isRefreshed={isRefreshed}
              savingTable={savingTable}
              isSavingEditChanges={isSavingEditChanges}
              editedHierarchies={editedHierarchies}
              appliedScenarioReady={!!currentlyAppliedScenario && sameScenario(currentlyAppliedScenario, tentativeRadioSelectedScenario)}
              setNewScenarioName={setNewScenarioName}
              setSaveScenarioDialogOpen={setSaveScenarioDialogOpen}
              expandedRows={threeLevelExpandedRows}
              setExpandedRows={setThreeLevelExpandedRows}
              hierarchyOrder={hierarchyOrder}
              setHierarchyOrder={setHierarchyOrder}
              tableScrollPosition={tableScrollPositionsRef.current[activeTab]}
              onTableScroll={handleTableScroll}
            />
          ) : (
            <>
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
                otherScenarioSeries={otherScenarioChartSeries}
              />
            </AccordionDetails>
          </Accordion>

          <ModelInputTable
            activeTab={activeTab}
            activeTabLabel={activeTabLabel}
            onActiveTabChange={setActiveTab}
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
            appliedScenarioReady={!!currentlyAppliedScenario && sameScenario(currentlyAppliedScenario, tentativeRadioSelectedScenario)}
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
            onDeleteScenario={handleDeleteScenario}
            onDeleteScenarioClick={handleDeleteScenarioClick}
            tableScrollPosition={tableScrollPositionsRef.current[activeTab]}
            onTableScroll={handleTableScroll}
          />
            </>
          )}
        </Box>
      </Paper>

      <Dialog
        open={deleteDialogOpen}
        onClose={() => {
          setDeleteDialogOpen(false);
          setScenarioToDelete("");
        }}
        maxWidth="xs"
        fullWidth
        PaperProps={{ sx: { borderRadius: "12px" } }}
      >
        <DialogTitle sx={{ fontWeight: 700, fontSize: "16px", color: "#0f172a", pb: 1 }}>
          Delete Scenario
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: "13px", color: "#64748b" }}>
            Are you sure you want to delete <b>{scenarioToDelete}</b>?
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
          <Button
            variant="outlined"
            onClick={() => {
              setDeleteDialogOpen(false);
              setScenarioToDelete("");
            }}
            sx={{ textTransform: "none", borderRadius: "8px", color: "#64748b", borderColor: "#e2e8f0" }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={() => handleDeleteScenario(scenarioToDelete)}
            sx={{ textTransform: "none", borderRadius: "8px", backgroundColor: "#dc2626" }}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

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