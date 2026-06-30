import React, { useState, useEffect, useContext, useMemo } from "react";
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
} from "@mui/material";
import Plot from "react-plotly.js";
const PlotComponent = Plot.default || Plot;
import { GlobalContext } from "../../../context/Provider";
import {
  getLiverFilters,
  applyLiverFilters,
  recalculateLiver,
  saveLiverScenario,
  getMetricFilters,
  applyMetricFilters,
  recalculateMetrics,
  saveScenario,
  updateScenario,
  getConfigurationByTherapyAreaHCV,
} from "../../../services/apiService";
import { useSnackbarStore, useLoadingStore } from "../../../stores";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
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
  payer_prod: "payer_wise_product",
  prod_payer: "product_wise_payer",
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
const ForecastChart = ({ chartData, productFilter, payerFilter, appliedBrand, activeTab }) => {
  if (!chartData?.months?.length || !chartData?.series?.length) {
    return (
      <Box sx={{ p: 4, textAlign: "center", color: "#94a3b8", fontSize: "14px" }}>
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

  const traces = series.flatMap((s, idx) => {
    const currentBrand = (productFilter || appliedBrand || "").toLowerCase();
    const currentPayer = (payerFilter || "").toLowerCase();
    const seriesLabel = (s.label || "").toLowerCase();

    let isSelectedTrace = false;
    if (activeTab === "prod_dist" && currentBrand) {
      isSelectedTrace = seriesLabel === currentBrand;
    } else if (activeTab === "payer_dist" && currentPayer) {
      isSelectedTrace = seriesLabel === currentPayer;
    } else if (activeTab === "payer_prod" && currentPayer && currentBrand) {
      isSelectedTrace = seriesLabel.includes(currentPayer) && seriesLabel.includes(currentBrand);
    } else if (activeTab === "prod_payer" && currentPayer && currentBrand) {
      isSelectedTrace = seriesLabel.includes(currentBrand) && seriesLabel.includes(currentPayer);
    } else if (activeTab === "total_market") {
      isSelectedTrace = true;
    } else {
      isSelectedTrace = (currentBrand && seriesLabel.includes(currentBrand)) || (currentPayer && seriesLabel.includes(currentPayer));
    }

    const color = isSelectedTrace ? CHART_COLORS[idx % CHART_COLORS.length] : "#e2e8f0";
    const width = isSelectedTrace ? 3.5 : 1.5;

    const trainX = allMonths.slice(0, fsi);
    const trainY = Array.isArray(s.train_values) ? s.train_values.slice(0, fsi) : [];
    const forecastX = fsi > 0 ? [allMonths[fsi - 1], ...allMonths.slice(fsi)] : allMonths.slice(fsi);
    const lastTrain = s.train_values?.length ? s.train_values[s.train_values.length - 1] : null;
    const forecastY = fsi > 0
        ? [lastTrain ?? null, ...(Array.isArray(s.forecast_values) ? s.forecast_values : [])]
        : Array.isArray(s.forecast_values) ? s.forecast_values : [];

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
  const [liverTabsRaw, setLiverTabsRaw] = useState(null);
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
  const [selectedCompareScenarios, setSelectedCompareScenarios] = useState(
    COMPARE_OPTIONS.slice(0, 2),
  );
  const [tentativeRadioSelectedScenario, setTentativeRadioSelectedScenario] =
    useState("");
  const [currentlyAppliedScenario, setCurrentlyAppliedScenario] = useState("");
  const [expandedBrands, setExpandedBrands] = useState({});

  // ── Derived ───────────────────────────────────────────────────────────────
  const metricUnit = useMemo(() => {
    if (activeTab === "total_market") return "";
    if (metric === "market_share") return "%";
    if (metric === "market_volume") return "";
    return allMetricsData?.[metric]?.unit || "";
  }, [metric, allMetricsData, activeTab]);

  const isPercentTab = activeTab !== "total_market";
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
        return !lbl.includes("total") && !lbl.includes("market volume") && !lbl.includes("market share");
      })
      .map((s) => ({
        label: s.label || "",
        lot: s.lot || s.label || "",
        train_values: Array.isArray(s.train_values) ? s.train_values : [],
        forecast_values: Array.isArray(s.forecast_values) ? s.forecast_values : [],
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
          return !lbl.includes("total") && !lbl.includes("market volume") && !lbl.includes("market share");
        });

        if (filteredCandidate.length) {
          const maxTL = Math.max(...filteredCandidate.map((s) => s.train_values?.length || 0), 0);
          const maxFL = Math.max(...filteredCandidate.map((s) => s.forecast_values?.length || 0), 0);
          const sumT = Array.from({ length: maxTL }, (_, i) =>
            filteredCandidate.reduce((a, s) => a + (Number((s.train_values || [])[i]) || 0), 0)
          );
          const sumF = Array.from({ length: maxFL }, (_, i) =>
            filteredCandidate.reduce((a, s) => a + (Number((s.forecast_values || [])[i]) || 0), 0)
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
    s_curve: {
      total_growth: totalGrowth,
      duration,
      trajectory_start: trajectoryStart,
      k_value: Number(kValue),
    },
    active_model: modelSelection,
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
    scenario: scenarioSelector || "Base",
  });

  // ── Effects ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (therapyArea) fetchMetricFilters();
  }, [therapyArea]);

  useEffect(() => {
    if (!filtersLoaded) return;
    
    let targetMetric = "market_volume";
    if (activeTab === "prod_dist" || activeTab === "payer_dist") {
      targetMetric = "market_share";
    } else if (activeTab === "payer_prod" || activeTab === "prod_payer" || activeTab === "total_market") {
      targetMetric = "market_volume";
    }

    if (metric !== targetMetric) {
      setMetric(targetMetric);
      if (targetMetric !== "market_share") setBrand("");
      handleApplyFilterWithMetric(targetMetric);
    }
  }, [activeTab, filtersLoaded]);

  useEffect(() => {
    if (!filtersLoaded || autoAppliedOnMount) return;
    (async () => {
      try {
        await handleApplyFilter();
        setAutoAppliedOnMount(true);
      } catch (e) {
        console.warn("Auto-apply failed", e);
      }
    })();
  }, [filtersLoaded, autoAppliedOnMount]);

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
      setSelectedCompareScenarios(
        names
          .filter((n) => n !== (currentlyAppliedScenario || names[0]))
          .slice(0, 2),
      );
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
        let cfg = null,
          savedFlag = null;
        try {
          savedFlag = localStorage.getItem("hcvConfigSaved");
        } catch (e) {
          savedFlag = null;
        }

        let localFrom = fromDate || "",
          localTo = toDate || "";
        let localPayer = payerFilter || "",
          localProduct = productFilter || "";
        let localToFromConfig = false;

        try {
          const cfgRes = await getConfigurationByTherapyAreaHCV(therapyArea);
          const cfgData = cfgRes?.data;
          if (cfgData?.exists && cfgData?.config) {
            cfg = cfgData.config;
            if (cfg.train_start_date) localFrom = cfg.train_start_date;
            if (cfg.forecast_periods) {
              localTo = cfg.forecast_periods;
              localToFromConfig = true;
            } else if (cfg.train_end_date) localTo = cfg.train_end_date;
          }
        } catch (err) {
          console.warn("Failed to load HCV config", err);
        }

        const response = await getLiverFilters();
        const resData = response?.data || {};
        setPayerOptions(resData?.payers || []);
        setProductOptions(resData?.products || []);
        const availDates = resData?.available_dates || [];
        setAvailableDates(availDates);

        if (!localPayer && resData?.payers?.length)
          localPayer = getFirstOption(resData.payers);
        if (!localProduct && resData?.products?.length)
          localProduct = getFirstOption(resData.products);
        if (
          !localFrom &&
          resData?.from_date &&
          availDates.includes(resData.from_date)
        )
          localFrom = resData.from_date;
        if (!localTo && resData?.to_date)
          localTo = availDates.includes(resData.to_date)
            ? resData.to_date
            : availDates[availDates.length - 1] || "";

        if (availDates.length) {
          if (localFrom && !availDates.includes(localFrom)) localFrom = "";
          if (localTo && !availDates.includes(localTo) && !localToFromConfig)
            localTo = availDates[availDates.length - 1];
        }

        setFromDate(localFrom);
        setToDate(localTo);
        setPayerFilter(localPayer);
        setProductFilter(localProduct);
        if (!metric && resData?.metric_options?.length)
          setMetric(resData.metric_options[0].value);

        setFilterOptions({
          indications: [],
          metric_filters: (resData?.metric_options || []).map((m) => ({
            label: m.label,
            value: m.value,
          })),
          scenario_names: resData?.scenarios || [],
        });
        if (resData?.scenarios?.length)
          setScenarioSelector(resData.scenarios[0]);

        if (cfg || savedFlag) {
          try {
            const autoPayload = {
              ta: therapyArea || "HCV",
              payer: localPayer
                ? [localPayer]
                : resData?.payers?.length
                  ? [getFirstOption(resData.payers)]
                  : [],
              brand: localProduct
                ? [localProduct]
                : resData?.products?.length
                  ? [getFirstOption(resData.products)]
                  : [],
              product: localProduct || getFirstOption(resData?.products || []),
              metric:
                metric ||
                resData?.metric_options?.[0]?.value ||
                "market_volume",
              from_date:
                cfg?.train_start_date ||
                localFrom ||
                resData.available_dates?.[0] ||
                "",
              scenario: resData?.scenarios?.[0] || "Base",
            };
            const applyResp = await applyLiverFilters(autoPayload);
            const data = applyResp?.data || {};
            const f = data?.factors || {};
            setAlpha(f?.level ?? 0);
            setBeta(f?.trend ?? 0);
            setGamma(f?.damping ?? 0);
            setMultiplier(f?.multiplier ?? 1);
            setLiverTabsRaw({
              months: data?.months || [],
              forecast_start_index: data?.forecast_start_index ?? 0,
              tabs: data?.tabs || {},
            });
            setEditable(false);
          } catch (err) {
            console.warn("Failed to auto-apply HCV config", err);
          }
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
          metric_filters: resData?.metric_filters || [],
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
        metric_filters: resData?.metric_filters || [],
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
      const factors = data?.factors || {};
      const am = factors?.active_model || "ets";
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

  const handleApplyFilterWithMetric = async (newMetric) => {
    try {
      setLoading(true);
      if (isHCV) {
        const response = await applyLiverFilters({
          ...buildLiverBasePayload(),
          metric: newMetric || "market_volume",
        });
        const data = response?.data || {};
        setAppliedLot(lot);
        setAppliedBrand(productFilter || brand);
        const f = data?.factors || {};
        setAlpha(f?.level ?? 0);
        setBeta(f?.trend ?? 0);
        setGamma(f?.damping ?? 0);
        setMultiplier(f?.multiplier ?? 1);
        setLiverTabsRaw({
          months: data?.months || [],
          forecast_start_index: data?.forecast_start_index ?? 0,
          tabs: data?.tabs || {},
        });
        setAllMetricsData({
          [newMetric]: { unit: newMetric === "market_share" ? "%" : "" },
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
      const am = factors?.active_model || "ets";
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
        const f = data?.factors || {};
        setAlpha(f?.level ?? 0);
        setBeta(f?.trend ?? 0);
        setGamma(f?.damping ?? 0);
        setMultiplier(f?.multiplier ?? 1);
        setLiverTabsRaw({
          months: data?.months || [],
          forecast_start_index: data?.forecast_start_index ?? 0,
          tabs: data?.tabs || {},
        });
        setEditable(false);
        showSnackbar("Filters applied successfully", "success");
        return;
      }
      const response = await applyMetricFilters(buildBasePayload());
      const data = response?.data;
      setAppliedLot(lot);
      setAppliedBrand(brand);
      const factors = data?.factors || {};
      const am = factors?.active_model || "ets";
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
        const response = await recalculateLiver({
          ...buildLiverBasePayload(),
          factors: {
            level: Number(alpha) || 0,
            trend: Number(beta) || 0,
            damping: Number(gamma) || 0,
            multiplier: Number(multiplier) || 1,
          },
        });
        const data = response?.data || {};
        const f = data?.factors || {};
        setAlpha(f?.level ?? 0);
        setBeta(f?.trend ?? 0);
        setGamma(f?.damping ?? 0);
        setMultiplier(f?.multiplier ?? 1);
        setLiverTabsRaw({
          months: data?.months || [],
          forecast_start_index: data?.forecast_start_index ?? 0,
          tabs: data?.tabs || {},
        });
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
      const am = factors?.active_model || "ets";
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
        await saveLiverScenario({
          scenario_name: scenarioNameFromDialog,
          ta: therapyArea || "HCV",
          payer: payerFilter ? [payerFilter] : ["All"],
          brand: productFilter ? [productFilter] : ["All"],
          product: productFilter || "All",
          metric: metric || "market_volume",
          from_date: resolveFromDate(),
          factors: {
            level: Number(alpha) || 0,
            trend: Number(beta) || 0,
            damping: Number(gamma) || 0,
            multiplier: Number(multiplier) || 1,
          },
          chart_data: { chart: chartData, table: tableData },
        });
        showSnackbar("Liver scenario saved successfully", "success");
        await fetchMetricFilters();
        setScenarioSelector(scenarioNameFromDialog);
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

  // ── UI handlers ───────────────────────────────────────────────────────────
  const toggleScenariosDropdown = (e) => {
    if (e?.stopPropagation) e.stopPropagation();
    setShowScenariosDropdown((s) => !s);
  };
  const handleScenarioSelectionChange = (s) => {
    setSelectedCompareScenarios((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s],
    );
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
                  onChange={(e) => setPayerFilter(e.target.value)}
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
                  onChange={(e) => setProductFilter(e.target.value)}
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
            onClick={() => handleSaveScenario(prompt("Enter scenario name:"))}
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
                    >
                      {trajectoryMonthOptions.map((m) => (
                        <MenuItem key={m} value={m}>
                          {new Date(m).toLocaleDateString("en-US", {
                            month: "short",
                            year: "2-digit",
                          })}
                        </MenuItem>
                      ))}
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
              productFilter={productFilter}
              payerFilter={payerFilter}
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
                        await handleApplyFilterWithMetric(nm);
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
                    if (val) setTotalMarketViewMode(val);
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

                {/* Edit Table */}
                <Button
                  size="small"
                  variant="outlined"
                  onClick={clickTableEdit}
                  sx={{
                    textTransform: "none",
                    fontSize: "12px",
                    fontWeight: 600,
                    borderRadius: "6px",
                    borderColor: "#e2e8f0",
                    color: "#3d89f3",
                    px: 1.5,
                    "&:hover": {
                      borderColor: "#cbd5e1",
                      backgroundColor: "#f8fafc",
                    },
                  }}
                >
                  Edit Table
                </Button>

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
                        {COMPARE_OPTIONS.map((s) => (
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
                  <Box component="tr">
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
                    {(chartData?.months || []).map((col) => (
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
                        {formatDateLabel(col)}
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
                        sx={{ "&:hover": { backgroundColor: "#f8fafc" } }}
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
                        {(chartData?.months || []).map((col, i) => {
                          const isF = isForecastMonth(col);
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
                                color: isF ? "#0ea5e9" : "#0f172a",
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
                            sx={{ "&:hover": { backgroundColor: "#f8fafc" } }}
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
                            {(chartData?.months || []).map((col, i) => {
                              const isF = isForecastMonth(col);
                              return (
                                <Box
                                  component="td"
                                  key={i}
                                  sx={{
                                    p: "10px 8px",
                                    textAlign: "center",
                                    fontSize: "13px",
                                    fontWeight: 400,
                                    backgroundColor: isF ? "#ffffff" : "#f8fafc",
                                    color: isF ? "#0ea5e9" : "#475569",
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
                    groupedTableHierarchy.map((group) => {
                      const isExpanded = !!expandedBrands[group.brandName];
                      const hasChildren = group.children.length > 0;
                      const mainRowApplied = group.mainRow?.is_applied;
                      const isSelected = tentativeRadioSelectedScenario === group.brandName;

                      const currentBrand = (productFilter || appliedBrand || "").toLowerCase();
                      const currentPayer = (payerFilter || "").toLowerCase();
                      const targetParentLabel = (group.brandName || "").toLowerCase();

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
                          {/* ── Parent row ── */}
                          <Box
                            component="tr"
                            onClick={() =>
                              hasChildren && toggleBrandExpand(group.brandName)
                            }
                            sx={{
                              cursor: hasChildren ? "pointer" : "default",
                              backgroundColor: hasChildren ? "#f8fafc" : "white",
                              "&:hover": {
                                backgroundColor: hasChildren ? "#f1f5f9" : "#f8fafc",
                              },
                            }}
                          >
                            {/* Sticky first column */}
                            <Box
                              component="td"
                              sx={{
                                position: "sticky",
                                left: 0,
                                zIndex: 1,
                                backgroundColor: hasChildren ? "#f8fafc" : "white",
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
                                    name="activeScenarioRadio"
                                    value={group.brandName}
                                    checked={isSelected}
                                    onChange={(e) => {
                                      e.stopPropagation();
                                      handleActiveScenarioRadioChange(
                                        group.brandName,
                                      );
                                    }}
                                    onClick={(e) => e.stopPropagation()}
                                    style={{
                                      accentColor: "#4F46E5",
                                      width: 14,
                                      height: 14,
                                      margin: 0,
                                      cursor: "pointer",
                                    }}
                                  />
                                )}

                                {hasChildren && (
                                  <Typography
                                    component="span"
                                    sx={{ fontSize: "10px", width: "12px" }}
                                  >
                                    {isExpanded ? "▼" : "▶"}
                                  </Typography>
                                )}

                                <Typography
                                  sx={{
                                    fontSize: "13px",
                                    fontWeight: 700,
                                    color: isAppliedParent ? "#f59e0b" : "#0f172a", 
                                  }}
                                >
                                  {group.brandName}
                                </Typography>

                                {(mainRowApplied ||
                                  currentlyAppliedScenario ===
                                    group.brandName) && (
                                  <Typography
                                    component="span"
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

                            {/* Parent data cells */}
                            {(chartData?.months || []).map((col) => {
                              const val = group.mainRow?.monthly_data?.[col];
                              const isF = isForecastMonth(col);
                              return (
                                <Box
                                  component="td"
                                  key={col}
                                  sx={{
                                    p: "10px 8px",
                                    textAlign: "center",
                                    fontSize: "13px",
                                    fontWeight: 700,
                                    backgroundColor: isF ? (isAppliedParent ? "#fffbeb" : "#ffffff") : "#f8fafc", 
                                    color: isF
                                      ? (isAppliedParent ? "#f59e0b" : "#0ea5e9") 
                                      : val != null
                                        ? "#0f172a"
                                        : "#cbd5e1",
                                    borderBottom: hasChildren
                                      ? "1px solid #cbd5e1"
                                      : "1px solid #f1f5f9",
                                  }}
                                >
                                  {formatCellValue(val)}
                                </Box>
                              );
                            })}
                          </Box>

                          {/* ── Child rows ── */}
                          {isExpanded &&
                            group.children.map((childRow, childIdx) => {
                              const isChildApplied = childRow.is_applied;
                              const cleanChildLabel = (childRow.cleanLabel || "").toLowerCase();
                              
                              let isAppliedChild = false;
                              if (activeTab === "payer_prod") {
                                isAppliedChild = (targetParentLabel === currentPayer) && (cleanChildLabel === currentBrand);
                              } else if (activeTab === "prod_payer") {
                                isAppliedChild = (targetParentLabel === currentBrand) && (cleanChildLabel === currentPayer);
                              }

                              return (
                                <Box
                                  component="tr"
                                  key={childIdx}
                                  sx={{
                                    backgroundColor: "white",
                                    "&:hover": {
                                      backgroundColor: "#f8fafc",
                                    },
                                  }}
                                >
                                  {/* Sticky first column */}
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
                                      pl: "40px",
                                    }}
                                  >
                                    <Box
                                      sx={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: 1.5,
                                      }}
                                    >
                                      <Typography
                                        sx={{
                                          fontSize: "13px",
                                          fontWeight: 500,
                                          color: isAppliedChild ? "#f59e0b" : "#334155", 
                                        }}
                                      >
                                        {childRow.cleanLabel}
                                      </Typography>
                                      {isChildApplied && (
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

                                  {/* Child data cells */}
                                  {(chartData?.months || []).map((col) => {
                                    const val = childRow.monthly_data?.[col];
                                    const isF = isForecastMonth(col);
                                    return (
                                      <Box
                                        component="td"
                                        key={col}
                                        sx={{
                                          p: "10px 8px",
                                          textAlign: "center",
                                          fontSize: "13px",
                                          fontWeight: 500,
                                          backgroundColor: isF ? (isAppliedChild ? "#fffbeb" : "#ffffff") : "#f8fafc",
                                          color: isF
                                            ? (isAppliedChild ? "#f59e0b" : "#0ea5e9") 
                                            : isChildApplied
                                              ? "#0f172a"
                                              : val != null
                                                ? "#475569"
                                                : "#cbd5e1",
                                          borderBottom: "1px solid #f1f5f9",
                                        }}
                                      >
                                        {formatCellValue(val)}
                                      </Box>
                                    );
                                  })}
                                </Box>
                              );
                            })}
                        </React.Fragment>
                      );
                    })
                  )}
                </Box>
              </Box>
            </Box>
          </Box>
        </Box>
      </Paper>
    </Box>
  );
}