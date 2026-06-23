import React, { useState, useEffect, useContext, useMemo } from "react";
import {
    Box, Paper, Typography, FormControl, Select, MenuItem,
    TextField, Button, ToggleButton, ToggleButtonGroup,
} from "@mui/material";
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid,
    Tooltip as RechartsTooltip, Legend, ReferenceLine, ResponsiveContainer,
} from "recharts";
import { GlobalContext } from "../../../context/Provider";
import {
    getLiverFilters, applyLiverFilters, recalculateLiver, saveLiverScenario,
    getMetricFilters, applyMetricFilters, recalculateMetrics,
    saveScenario, updateScenario,
} from "../../../services/apiService";
import { useSnackbarStore, useLoadingStore } from "../../../stores";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import Tooltip from "@mui/material/Tooltip";
import dayjs from "dayjs";

// ─── Constants ───────────────────────────────────────────────────────────────
const TABS = [
    { label: "Total Market Volume",      value: "total_market" },
    { label: "Product Distribution (%)", value: "prod_dist" },
    { label: "Payer Distribution (%)",   value: "payer_dist" },
    { label: "Payer-wise Product",       value: "payer_prod" },
    { label: "Product-wise Payer",       value: "prod_payer" },
];

const TAB_KEY_MAP = {
    total_market: "total_market_volume",
    prod_dist:    "product_distribution",
    payer_dist:   "payer_distribution",
    payer_prod:   "payer_wise_product",
    prod_payer:   "product_wise_payer",
};

const COMPARE_OPTIONS = ["ETS 13M", "ETS 26M", "Exponential"];
const DATE_INPUT_FORMATS = ["MMM-YY", "YYYY-MM", "YYYY-MM-DD", "YYYY-MM-DDTHH:mm:ssZ"];
const CHART_COLORS = ["#4F46E5", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#0ea5e9", "#84cc16"];

// ─── Helper Functions ────────────────────────────────────────────────────────
const formatMonthLabel = (s) => {
    if (!s) return "";
    const parsed = dayjs(s, DATE_INPUT_FORMATS, true);
    return parsed.isValid() ? parsed.format("MMM-YY") : String(s);
};

const formatChartValue = (v, unit) => {
    if (v == null || isNaN(v)) return "—";
    const n = Number(v);
    if (unit === "%") return `${n.toFixed(1)}%`;
    if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return n.toFixed(1);
};

const ForecastChart = ({ chartData, metricUnit = "" }) => {
    const rows = useMemo(() => {
        if (!chartData?.months?.length || !chartData?.series?.length) return [];
        const { months, forecast_start_index: fsi = 0, series } = chartData;

        return months.map((month, i) => {
            const row = { month: formatMonthLabel(month) };
            series.forEach((s) => {
                const histKey = `${s.label}__h`;
                const fcstKey = `${s.label}__f`;
                const trainV = s.train_values?.[i];
                const forecastV = i >= fsi ? s.forecast_values?.[i - fsi] : null;

                row[histKey] = i < fsi ? (trainV ?? null) : null;
                row[fcstKey] = i >= fsi ? (forecastV ?? null) : null;
                if (i === fsi - 1 && trainV != null) row[fcstKey] = trainV;
            });
            return row;
        });
    }, [chartData]);

    if (!rows.length) {
        return (
            <Box sx={{ p: 4, textAlign: "center", color: "#94a3b8", fontSize: "14px" }}>
                No chart data available. Please select filters and apply.
            </Box>
        );
    }

    const { months, forecast_start_index: fsi = 0, series } = chartData;
    const cutoffLabel = fsi > 0 && fsi < months.length ? formatMonthLabel(months[fsi]) : null;

    return (
        <Box sx={{ width: "100%", height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 10, right: 24, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                        dataKey="month"
                        tick={{ fontSize: 10, fill: "#64748b" }}
                        interval="preserveStartEnd"
                        minTickGap={20}
                    />
                    <YAxis
                        tick={{ fontSize: 10, fill: "#64748b" }}
                        tickFormatter={(v) => formatChartValue(v, metricUnit)}
                        width={60}
                    />
                    <RechartsTooltip
                        formatter={(v, name) => [formatChartValue(v, metricUnit), name.replace(/__[hf]$/, "")]}
                        contentStyle={{ fontSize: 11, borderRadius: 6, border: "1px solid #e2e8f0" }}
                    />
                    <Legend
                        wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                        formatter={(value) => value.replace(/__h$/, " (History)").replace(/__f$/, " (Forecast)")}
                    />
                    {cutoffLabel && (
                        <ReferenceLine
                            x={cutoffLabel}
                            stroke="#94a3b8"
                            strokeDasharray="4 4"
                            label={{ value: "Forecast →", fontSize: 10, fill: "#64748b", position: "insideTopRight" }}
                        />
                    )}
                    {series.flatMap((s, idx) => {
                        const color = CHART_COLORS[idx % CHART_COLORS.length];
                        return [
                            <Line
                                key={`${s.label}-h`}
                                type="monotone"
                                dataKey={`${s.label}__h`}
                                stroke={color}
                                strokeWidth={2}
                                dot={false}
                                connectNulls
                                isAnimationActive={false}
                            />,
                            <Line
                                key={`${s.label}-f`}
                                type="monotone"
                                dataKey={`${s.label}__f`}
                                stroke={color}
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                                connectNulls
                                isAnimationActive={false}
                            />,
                        ];
                    })}
                </LineChart>
            </ResponsiveContainer>
        </Box>
    );
};

// ─── Component ───────────────────────────────────────────────────────────────
export default function PBCModelInput() {
    const { showSnackbar } = useSnackbarStore();
    const { setLoading } = useLoadingStore();
    const { favState } = useContext(GlobalContext);
    const therapyArea = favState?.selectedTherapyArea;
    const isHCV = therapyArea && therapyArea.toLowerCase() === "hcv";

    // ── Tab state ───────────────────────────────────────────────────────────
    const [activeTab, setActiveTab] = useState("total_market");

    // ── Filter states ───────────────────────────────────────────────────────
    const [scenarioSelector, setScenarioSelector] = useState("");
    const [fromDate, setFromDate]                 = useState("");
    const [toDate, setToDate]                     = useState("");
    const [payerFilter, setPayerFilter]           = useState("");
    const [productFilter, setProductFilter]       = useState("");
    const [metric, setMetric]                     = useState("");
    const [availableDates, setAvailableDates]     = useState([]);

    // ── Chart / table states ────────────────────────────────────────────────
    const [chartData, setChartData]               = useState(null);
    const [tableData, setTableData]               = useState([]);
    const [allMetricsData, setAllMetricsData]     = useState({});
    const [appliedLot, setAppliedLot]             = useState("");
    const [appliedBrand, setAppliedBrand]         = useState("");

    // Cached full HCV response so all 5 sub-tabs render without re-fetching
    const [liverTabsRaw, setLiverTabsRaw]         = useState(null);

    // ── Model states ────────────────────────────────────────────────────────
    const [editable, setEditable]                   = useState(false);
    const [modelSelection, setModelSelection]       = useState("ets");
    const [allFactors, setAllFactors]               = useState({});
    const [alpha, setAlpha]                         = useState(0);
    const [beta, setBeta]                           = useState(0);
    const [gamma, setGamma]                         = useState(0);
    const [totalGrowth, setTotalGrowth]             = useState(10);
    const [duration, setDuration]                   = useState(12);
    const [kValue, setKValue]                       = useState(1);
    const [multiplier, setMultiplier]               = useState(1.0);
    const [multiplierHorizon, setMultiplierHorizon] = useState("Forecast");
    const [trajectoryStart, setTrajectoryStart]     = useState("");

    // ── Filter option states ────────────────────────────────────────────────
    const [mappingData, setMappingData]   = useState({});
    const [filterOptions, setFilterOptions] = useState({
        indications: [],
        metric_filters: [],
        scenario_names: [],
    });
    const [payerOptions, setPayerOptions]     = useState([]);
    const [productOptions, setProductOptions] = useState([]);

    // ── Legacy filters (kept for API compatibility) ─────────────────────────
    const [indication, setIndication] = useState("");
    const [lot, setLot]               = useState("");
    const [brand, setBrand]           = useState("");

    // ── Market Metrics table UI state ───────────────────────────────────────
    const [totalMarketViewMode, setTotalMarketViewMode]                       = useState("monthly");
    const [showScenariosDropdown, setShowScenariosDropdown]                   = useState(false);
    const [selectedCompareScenarios, setSelectedCompareScenarios]             = useState(COMPARE_OPTIONS.slice(0, 2));
    const [tentativeRadioSelectedScenario, setTentativeRadioSelectedScenario] = useState("");
    const [currentlyAppliedScenario, setCurrentlyAppliedScenario]             = useState("");

    // Local UI state specifically to track which main brands are open/collapsed
    const [expandedBrands, setExpandedBrands] = useState({});

    const metricUnit   = allMetricsData?.[metric]?.unit || "";
    const isPercentTab = activeTab !== "total_market";

    // ─── Date helpers ───────────────────────────────────────────────────────
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
        return p.isValid() ? p.format("YYYY-MM") : (s || "");
    };
    const resolveFromDate = () => {
        if (fromDate) return toYearMonth(fromDate);
        if (availableDates?.length) return toYearMonth(availableDates[0]);
        return "";
    };

    // ─── Factor / metric sync helpers ───────────────────────────────────────
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

    // ─── HCV tab mapper ─────────────────────────────────────────────────────
    const mapLiverTabToView = (tabsPayload, uiTabKey) => {
        if (!tabsPayload) return { chart: null, table: [] };

        const { months = [], forecast_start_index: fsi = 0, tabs = {} } = tabsPayload;
        const backendKey = TAB_KEY_MAP[uiTabKey] || uiTabKey;
        const tab = tabs[backendKey] || tabs[Object.keys(tabs)[0]] || null;

        if (!tab) {
            return { chart: { months, forecast_start_index: fsi, series: [] }, table: [] };
        }

        const series = (tab.chart?.series || []).map((s) => ({
            label: s.label || "",
            lot: s.lot || s.label || "",
            train_values: Array.isArray(s.train_values) ? s.train_values : [],
            forecast_values: Array.isArray(s.forecast_values) ? s.forecast_values : [],
        }));

        const headers = tab.table?.headers || months;
        const table = (tab.table?.rows || []).map((r) => {
            const vals = r.values || [];
            const monthly_data = {};
            headers.forEach((m, i) => {
                const v = vals[i];
                monthly_data[m] = (v === null || v === undefined ? null : Number(v));
            });
            return { hierarchy: r.hierarchy, monthly_data, is_applied: !!r.is_applied };
        });

        return { chart: { months, forecast_start_index: fsi, series }, table };
    };

    // ─── Payload builders ───────────────────────────────────────────────────
    const buildBasePayload = () => ({
        ta_name: therapyArea,
        scenario_name: scenarioSelector,
        indications: indication ? [indication] : [],
        lots: lot ? [lot] : [],
        metric_filter: metric,
        product: metric === "market_share" ? brand : "",
        from_date: fromDate,
        to_date: toDate,
        payer: payerFilter,
        product_filter: productFilter,
    });

    const buildFullFactors = () => ({
        multiplier,
        multiplier_horizon: multiplierHorizon,
        ets: { alpha, beta, gamma },
        linear:      { total_growth: totalGrowth, duration, trajectory_start: trajectoryStart },
        exponential: { total_growth: totalGrowth, duration, trajectory_start: trajectoryStart, k_value: Number(kValue) },
        logarithmic: { total_growth: totalGrowth, duration, trajectory_start: trajectoryStart, k_value: Number(kValue) },
        s_curve:     { total_growth: totalGrowth, duration, trajectory_start: trajectoryStart, k_value: Number(kValue) },
        active_model: modelSelection,
    });

    const buildLiverBasePayload = () => ({
        ta: therapyArea || "HCV",
        payer: payerFilter ? [payerFilter] : ["All"],
        brand: productFilter ? [productFilter] : ["All"],
        product: productFilter || "All",
        metric: metric || "market_volume",
        from_date: resolveFromDate(),
        scenario: scenarioSelector || "Base",
    });

    // ─── Effects ────────────────────────────────────────────────────────────
    useEffect(() => {
        if (therapyArea) fetchMetricFilters();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [therapyArea]);

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
            if (!tentativeRadioSelectedScenario) setTentativeRadioSelectedScenario(names[0]);

            const candidates = names.filter((n) => n !== (currentlyAppliedScenario || names[0]));
            setSelectedCompareScenarios(candidates.slice(0, 2));
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filterOptions.scenario_names]);

    useEffect(() => {
        const onWindowClick = () => setShowScenariosDropdown(false);
        window.addEventListener("click", onWindowClick);
        return () => window.removeEventListener("click", onWindowClick);
    }, []);

    // ─── API: load filter options ───────────────────────────────────────────
    const fetchMetricFilters = async () => {
        try {
            setLoading(true);

            if (isHCV) {
                const response = await getLiverFilters();
                const resData = response?.data || {};

                setPayerOptions(resData?.payers || []);
                setProductOptions(resData?.products || []);
                setAvailableDates(resData?.available_dates || []);

                if (!payerFilter   && resData?.payers?.length)          setPayerFilter(resData.payers[0]);
                if (!productFilter && resData?.products?.length)        setProductFilter(resData.products[0]);
                if (!fromDate      && resData?.available_dates?.length) setFromDate(resData.available_dates[0]);
                if (!metric        && resData?.metric_options?.length)  setMetric(resData.metric_options[0].value);

                setFilterOptions({
                    indications: [],
                    metric_filters: (resData?.metric_options || []).map((m) => ({ label: m.label, value: m.value })),
                    scenario_names: resData?.scenarios || [],
                });

                if (resData?.scenarios?.length) setScenarioSelector(resData.scenarios[0]);
                return;
            }

            const response = await getMetricFilters(therapyArea);
            const resData = response?.data;

            setMappingData(resData?.data || {});
            setAvailableDates(resData?.available_dates || []);

            const defaultFilter = resData?.selected_filter;
            if (!defaultFilter) {
                setFilterOptions({
                    indications: [],
                    metric_filters: resData?.metric_filters || [],
                    scenario_names: resData?.scenario_names || [],
                });
                return;
            }

            setScenarioSelector(defaultFilter.scenario_name);
            setIndication(defaultFilter.indication);
            setLot(defaultFilter.lot);
            setMetric(defaultFilter.metric);
            setBrand(defaultFilter.product || "");
            setFromDate(defaultFilter.from_date || "");
            setToDate(defaultFilter.to_date || "");
            setPayerFilter(defaultFilter.payer || "");
            setProductFilter(defaultFilter.product_filter || "");

            setFilterOptions({
                indications: Object.keys(resData?.data?.[defaultFilter.scenario_name] || {}),
                metric_filters: resData?.metric_filters || [],
                scenario_names: resData?.scenario_names || [],
            });

            const payload = {
                ...buildBasePayload(),
                scenario_name: defaultFilter.scenario_name,
                indications: defaultFilter.indication ? [defaultFilter.indication] : [],
                lots: defaultFilter.lot ? [defaultFilter.lot] : [],
                metric_filter: defaultFilter.metric,
                product: defaultFilter.metric === "market_share" ? defaultFilter.product || "" : "",
                from_date: defaultFilter.from_date || "",
                to_date: defaultFilter.to_date || "",
                payer: defaultFilter.payer || "",
                product_filter: defaultFilter.product_filter || "",
            };

            const applyResponse = await applyMetricFilters(payload);
            const data = applyResponse?.data;
            setAppliedLot(defaultFilter.lot);
            setAppliedBrand(defaultFilter.product || "");

            const factors = data?.factors || {};
            const activeModel = factors?.active_model || "ets";
            setModelSelection(activeModel);
            syncFactors(factors, activeModel);
            syncMetrics(data?.metrics_data, defaultFilter.metric);
        } catch (error) {
            console.error("Failed to fetch metric filters", error);
            showSnackbar("Failed to fetch metric filters", "error");
        } finally {
            setLoading(false);
        }
    };

    // ─── API: apply filters ─────────────────────────────────────────────────
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
                showSnackbar("Liver filters applied successfully", "success");
                return;
            }

            const response = await applyMetricFilters(buildBasePayload());
            const data = response?.data;

            setAppliedLot(lot);
            setAppliedBrand(brand);

            const factors = data?.factors || {};
            const activeModel = factors?.active_model || "ets";
            setModelSelection(activeModel);
            syncFactors(factors, activeModel);
            syncMetrics(data?.metrics_data, metric);
            setEditable(false);
            showSnackbar("Filters applied successfully", "success");
        } catch (error) {
            const serverMessage = error?.response?.data || error?.message || "Unknown error";
            console.error("Failed to apply filters", serverMessage);
            showSnackbar(typeof serverMessage === "string" ? serverMessage : JSON.stringify(serverMessage), "error");
        } finally {
            setLoading(false);
        }
    };

    // ─── API: recalculate ───────────────────────────────────────────────────
    const handleRecalculate = async () => {
        try {
            setLoading(true);

            if (isHCV) {
                const payload = {
                    ...buildLiverBasePayload(),
                    factors: {
                        level: Number(alpha) || 0,
                        trend: Number(beta) || 0,
                        damping: Number(gamma) || 0,
                        multiplier: Number(multiplier) || 1,
                    },
                };

                const response = await recalculateLiver(payload);
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

                showSnackbar("Liver recalculated successfully", "success");
                return;
            }

            const modelFactors = modelSelection === "ets"
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
                factors: { multiplier, multiplier_horizon: multiplierHorizon, ...modelFactors },
            });
            const data = response?.data;
            const factors = data?.factors || {};
            syncFactors(factors, factors?.active_model);
            syncMetrics(data?.metrics_data, metric);
            showSnackbar("Metrics recalculated successfully", "success");
        } catch (error) {
            console.error("Failed to recalculate metrics/liver", error);
            showSnackbar("Failed to recalculate metrics", "error");
        } finally {
            setLoading(false);
        }
    };

    // ─── API: update scenario ───────────────────────────────────────────────
    const handleUpdateScenario = async () => {
        if (!scenarioSelector) { showSnackbar("Please select a scenario", "error"); return; }
        if (!chartData || !tableData.length) { showSnackbar("No data to update", "error"); return; }
        try {
            setLoading(true);
            const res = await updateScenario({
                ...buildBasePayload(),
                lot, indication, metric,
                product: brand || null,
                model_type: modelSelection,
                factors: buildFullFactors(),
                metrics_data: allMetricsData,
            });
            const data = res?.data;
            const factors = data?.factors || {};
            const activeModel = factors?.active_model || "ets";
            setModelSelection(activeModel);
            syncFactors(factors, activeModel);
            syncMetrics(data?.metrics_data, metric);
            setEditable(false);
            showSnackbar("Scenario updated successfully", "success");
        } catch (error) {
            showSnackbar("Failed to update scenario", "error");
        } finally {
            setLoading(false);
        }
    };

    // ─── API: save scenario ─────────────────────────────────────────────────
    const handleSaveScenario = async (scenarioNameFromDialog) => {
        if (!scenarioNameFromDialog) { showSnackbar("Please enter the scenario name", "error"); return; }
        if (!chartData || !tableData.length) { showSnackbar("No data to save", "error"); return; }
        try {
            setLoading(true);

            if (isHCV) {
                const payload = {
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
                };

                await saveLiverScenario(payload);
                showSnackbar("Liver scenario saved successfully", "success");
                await fetchMetricFilters();
                setScenarioSelector(scenarioNameFromDialog);
                return;
            }

            await saveScenario({
                ...buildBasePayload(),
                scenario_name: scenarioNameFromDialog,
                lot, indication, metric,
                product: brand || null,
                model_type: modelSelection,
                factors: buildFullFactors(),
                metrics_data: allMetricsData,
            });
            showSnackbar("Scenario created successfully", "success");

            const response = await getMetricFilters(therapyArea);
            const resData = response?.data;
            const newMappingData = resData?.data || {};
            setMappingData(newMappingData);
            setFilterOptions({
                indications: Object.keys(newMappingData?.[scenarioNameFromDialog] || {}),
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

    // ─── Market Metrics table UI handlers ───────────────────────────────────
    const toggleScenariosDropdown = (e) => {
        if (e && e.stopPropagation) e.stopPropagation();
        setShowScenariosDropdown((s) => !s);
    };
    const handleScenarioSelectionChange = (scenario) => {
        setSelectedCompareScenarios((prev) =>
            prev.includes(scenario) ? prev.filter((s) => s !== scenario) : [...prev, scenario]
        );
    };
    const handleActiveScenarioRadioChange = (scenarioName) => {
        setTentativeRadioSelectedScenario(scenarioName);
    };
    const clickTableEdit = () => setEditable(true);
    const applySelectedScenario = () => {
        setCurrentlyAppliedScenario(tentativeRadioSelectedScenario);
        showSnackbar(`Applied ${tentativeRadioSelectedScenario} successfully across all tabs!`, "success");
        setEditable(false);
    };

    // ─── Cell formatter ─────────────────────────────────────────────────────
    const formatCellValue = (val) => {
        if (val == null) return "—";
        const num = Number(val);
        if (isPercentTab) return `${num.toFixed(1)}%`;
        const fixed = num.toLocaleString(undefined, { maximumFractionDigits: 1 });
        return `${fixed}${metricUnit === "%" ? "%" : ""}`;
    };

    // ─── Toggle Brand Collapse Handler ──────────────────────────────────────
    const toggleBrandExpand = (brandName) => {
        setExpandedBrands(prev => ({
            ...prev,
            [brandName]: !prev[brandName]
        }));
    };

    // ─── Dynamic Hierarchy Grouping Logic ────────────────────────────────────
    const groupedTableHierarchy = useMemo(() => {
        const brandsMap = {};

        tableData.forEach((row) => {
            const rawLabel = row.hierarchy || "";
            
            if (rawLabel.includes(" - ")) {
                const parts = rawLabel.split(" - ");
                const brandKey = parts[0].trim();
                const payerKey = parts.slice(1).join(" - ").trim();

                if (!brandsMap[brandKey]) {
                    brandsMap[brandKey] = { mainRow: null, children: [] };
                }
                brandsMap[brandKey].children.push({ ...row, cleanLabel: payerKey });
            } else {
                const brandKey = rawLabel.trim();
                if (!brandsMap[brandKey]) {
                    brandsMap[brandKey] = { mainRow: null, children: [] };
                }
                brandsMap[brandKey].mainRow = row;
            }
        });

        return Object.keys(brandsMap).map((brandKey) => ({
            brandName: brandKey,
            mainRow: brandsMap[brandKey].mainRow || { hierarchy: brandKey, monthly_data: {}, is_applied: false },
            children: brandsMap[brandKey].children
        }));
    }, [tableData]);

    // ─── Derived ────────────────────────────────────────────────────────────
    const trajectoryMonthOptions = chartData?.months?.slice(chartData?.forecast_start_index) || [];

    // ─── Styles ─────────────────────────────────────────────────────────────
    const inputStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "160px",
        "& .MuiOutlinedInput-root": { borderRadius: "8px", height: "35px", backgroundColor: "#fcfcfd" },
    };
    const recalcStyle = {
        bgcolor: "#fcfcfd",
        borderRadius: "8px",
        minWidth: "100px",
        "& .MuiOutlinedInput-root": { borderRadius: "8px", height: "35px", backgroundColor: "#fcfcfd" },
    };
    const recalculateInputStyle = recalcStyle;

    // ─── Render ─────────────────────────────────────────────────────────────
    return (
        <Box sx={{ p: 3 }}>
            <Paper sx={{ p: 3, borderRadius: "16px", border: "1px solid #D8DEE8", boxShadow: "none", overflow: "hidden" }}>

                {/* ── TOP FILTER BAR ── */}
                <Box sx={{ p: 3, borderBottom: "1px solid #D8DEE8", display: "flex", alignItems: "end", gap: 3, flexWrap: "wrap", justifyContent: "space-between" }}>
                    <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", alignItems: "end" }}>

                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>THERAPEUTIC AREA</Typography>
                            <Box sx={{ height: 34, px: 2, display: "flex", alignItems: "center", gap: 1, borderRadius: "6px", backgroundColor: "#10b981", minWidth: "100px" }}>
                                <Typography sx={{ fontSize: "13px", fontWeight: 600, color: "white" }}>{therapyArea}</Typography>
                            </Box>
                        </Box>

                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>FROM DATE</Typography>
                            <FormControl sx={inputStyle}>
                                <Select value={fromDate} onChange={(e) => { setFromDate(e.target.value); setToDate(""); }} displayEmpty>
                                    <MenuItem value="" disabled>Select</MenuItem>
                                    {availableDates.map((d) => (
                                        <MenuItem key={d} value={d}>{formatDateLabel(d)}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Box>

                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>TO DATE</Typography>
                            <FormControl sx={inputStyle}>
                                <Select value={toDate} onChange={(e) => setToDate(e.target.value)} displayEmpty disabled={!fromDate}>
                                    <MenuItem value="" disabled>Select</MenuItem>
                                    {availableDates.filter((d) => {
                                        const pd = parseDateString(d);
                                        const fd = parseDateString(fromDate);
                                        if (!pd.isValid()) return false;
                                        if (!fd.isValid()) return true;
                                        return pd.isAfter(fd);
                                    }).map((d) => (
                                        <MenuItem key={d} value={d}>{formatDateLabel(d)}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Box>

                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>SCENARIO SELECTOR</Typography>
                            <FormControl sx={inputStyle}>
                                <Select value={scenarioSelector} onChange={(e) => {
                                    setScenarioSelector(e.target.value);
                                    setIndication(""); setLot(""); setBrand("");
                                    setFilterOptions((prev) => ({ ...prev, indications: Object.keys(mappingData?.[e.target.value] || {}) }));
                                    setChartData(null); setTableData([]);
                                }} displayEmpty>
                                    <MenuItem value="" disabled>Select Scenario</MenuItem>
                                    {filterOptions.scenario_names.map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
                                </Select>
                            </FormControl>
                        </Box>

                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>PAYER FILTER</Typography>
                            <FormControl sx={inputStyle}>
                                <Select value={payerFilter} onChange={(e) => setPayerFilter(e.target.value)} displayEmpty>
                                    <MenuItem value="" disabled>Select</MenuItem>
                                    {(payerOptions && payerOptions.length ? payerOptions : ["Commercial", "Medicare", "Medicaid"]).map((p) => {
                                        const val = typeof p === "string" ? p : (p.value || p.name || p.id || JSON.stringify(p));
                                        const label = typeof p === "string" ? p : (p.label || p.name || p.value || JSON.stringify(p));
                                        return <MenuItem key={val} value={val}>{label}</MenuItem>;
                                    })}
                                </Select>
                            </FormControl>
                        </Box>

                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>METRIC FILTER</Typography>
                            <FormControl sx={inputStyle}>
                                <Select value={metric} onChange={(e) => { setMetric(e.target.value); if (e.target.value !== "market_share") setBrand(""); }} displayEmpty>
                                    <MenuItem value="" disabled>Select Metric</MenuItem>
                                    {filterOptions.metric_filters.map((item) => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}
                                </Select>
                            </FormControl>
                        </Box>

                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}>PRODUCT FILTER</Typography>
                            <FormControl sx={inputStyle}>
                                <Select value={productFilter} onChange={(e) => setProductFilter(e.target.value)} displayEmpty>
                                    <MenuItem value="" disabled>Select</MenuItem>
                                    {(productOptions && productOptions.length ? productOptions : ["GILD", "ASGA", "others"]).map((p) => {
                                        const val = typeof p === "string" ? p : (p.value || p.name || p.id || JSON.stringify(p));
                                        const label = typeof p === "string" ? p : (p.label || p.name || p.value || JSON.stringify(p));
                                        return <MenuItem key={val} value={val}>{label}</MenuItem>;
                                    })}
                                </Select>
                            </FormControl>
                        </Box>

                        <Button variant="contained" onClick={handleApplyFilter}
                            sx={{ textTransform: "none", borderRadius: "6px", backgroundColor: "#4F46E5", height: "34px", fontSize: "13px" }}>
                            Apply Filter
                        </Button>
                    </Box>

                    <Button variant="contained" onClick={() => handleSaveScenario(prompt("Enter scenario name:"))}
                        sx={{ textTransform: "none", borderRadius: "6px", backgroundColor: "#10b981", height: "34px", fontSize: "12px", fontWeight: 700, flexShrink: 0 }}>
                        Save Scenario
                    </Button>
                </Box>

                {/* ── STATISTICAL PROJECTION ENGINE ── */}
                <Paper sx={{ mt: 3, p: 3, borderRadius: "16px", border: "1px solid #D8DEE8", boxShadow: "none", backgroundColor: editable ? "#fff" : "#eff6ff" }}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                        <Typography sx={{ fontSize: "14px", fontWeight: 700, color: "#1d4ed8", textTransform: "uppercase" }}>
                            STATISTICAL PROJECTION ENGINE
                        </Typography>
                        <Box display="flex" gap={2}>
                            <Button variant="outlined" size="small" onClick={() => setEditable(!editable)} sx={{ textTransform: "none", borderRadius: "8px" }}>
                                {editable ? "Lock Factors" : "Edit Factors"}
                            </Button>
                        </Box>
                    </Box>

                    <Box sx={{ display: "flex", gap: 3, flexWrap: "wrap", alignItems: "center" }}>
                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px", fontWeight: 700, color: "#64748b" }}> BASE MODEL </Typography>
                            <FormControl sx={inputStyle}>
                                <Select value={modelSelection} onChange={(e) => setModelSelection(e.target.value)} disabled={!editable}>
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
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>LEVEL (α)</Typography>
                                        <Tooltip title="Please enter value from 0 to 1" arrow placement="top">
                                            <InfoOutlinedIcon sx={{ fontSize: 16, color: "#64748b", cursor: "pointer" }} />
                                        </Tooltip>
                                    </Box>
                                    <TextField
                                        type="number" value={alpha} disabled={!editable}
                                        onChange={(e) => {
                                            const value = e.target.value;
                                            if (value === "" || (Number(value) >= 0 && Number(value) <= 1)) setAlpha(value);
                                        }}
                                        inputProps={{ min: 0, max: 1, step: 0.01 }} sx={recalculateInputStyle}
                                    />
                                </Box>

                                <Box>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>TREND (β)</Typography>
                                        <Tooltip title="Please enter value from 0 to 1" arrow placement="top">
                                            <InfoOutlinedIcon sx={{ fontSize: 16, color: "#64748b", cursor: "pointer" }} />
                                        </Tooltip>
                                    </Box>
                                    <TextField
                                        type="number" value={beta} disabled={!editable}
                                        onChange={(e) => {
                                            const value = e.target.value;
                                            if (value === "" || (Number(value) >= 0 && Number(value) <= 1)) setBeta(value);
                                        }}
                                        inputProps={{ min: 0, max: 1, step: 0.01 }} sx={recalculateInputStyle}
                                    />
                                </Box>

                                <Box>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>DAMPING (φ)</Typography>
                                        <Tooltip title="Please enter value from 0 to 1" arrow placement="top">
                                            <InfoOutlinedIcon sx={{ fontSize: 16, color: "#64748b", cursor: "pointer" }} />
                                        </Tooltip>
                                    </Box>
                                    <TextField
                                        type="number" value={gamma} disabled={!editable}
                                        onChange={(e) => {
                                            const value = e.target.value;
                                            if (value === "" || (Number(value) >= 0 && Number(value) <= 1)) setGamma(value);
                                        }}
                                        inputProps={{ min: 0, max: 1, step: 0.01 }} sx={recalculateInputStyle}
                                    />
                                </Box>
                            </>
                        )}

                        {["linear", "exponential", "logarithmic", "scurve"].includes(modelSelection) && (
                            <>
                                <Box>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>GROWTH %</Typography>
                                        <Tooltip title="Please enter the total growth%" arrow placement="top">
                                            <InfoOutlinedIcon sx={{ fontSize: 16, color: "#64748b", cursor: "pointer" }} />
                                        </Tooltip>
                                    </Box>
                                    <TextField
                                        type="number" value={totalGrowth} disabled={!editable}
                                        onChange={(e) => {
                                            const value = e.target.value;
                                            if (value === "" || (Number(value) >= -100 && Number(value) <= 100)) setTotalGrowth(value);
                                        }}
                                        inputProps={{ min: 0, max: 100, step: 0.1 }} sx={recalculateInputStyle}
                                    />
                                </Box>

                                <Box>
                                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                        <Typography sx={{ fontSize: "14px" }}>DURATION</Typography>
                                        <Tooltip title="Please enter the months" arrow placement="top">
                                            <InfoOutlinedIcon sx={{ fontSize: 16, color: "#64748b", cursor: "pointer" }} />
                                        </Tooltip>
                                    </Box>
                                    <TextField
                                        type="number" value={duration} disabled={!editable}
                                        onChange={(e) => setDuration(Number(e.target.value))}
                                        inputProps={{ min: 0, max: 100, step: 1 }} sx={recalculateInputStyle}
                                    />
                                </Box>

                                {modelSelection !== "linear" && (
                                    <Box>
                                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                            <Typography sx={{ fontSize: "14px" }}>K VALUE</Typography>
                                            <Tooltip title="Please enter value from 0 to 3" arrow placement="top">
                                                <InfoOutlinedIcon sx={{ fontSize: 16, color: "#64748b", cursor: "pointer" }} />
                                            </Tooltip>
                                        </Box>
                                        <TextField
                                            type="number" value={kValue} disabled={!editable}
                                            onChange={(e) => {
                                                const value = e.target.value;
                                                if (value === "" || (Number(value) >= 0 && Number(value) <= 3)) setKValue(value);
                                            }}
                                            inputProps={{ min: 0, max: 3, step: 0.01 }} sx={recalculateInputStyle}
                                        />
                                    </Box>
                                )}

                                <Box>
                                    <Typography sx={{ mb: 1, fontSize: "14px" }}>TRAJECTORY START</Typography>
                                    <FormControl sx={recalculateInputStyle}>
                                        <Select value={trajectoryStart} onChange={(e) => setTrajectoryStart(e.target.value)} disabled={!editable}>
                                            {trajectoryMonthOptions.map((month) => (
                                                <MenuItem key={month} value={month}>
                                                    {new Date(month).toLocaleDateString("en-US", { month: "short", year: "2-digit" })}
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>
                            </>
                        )}

                        <Box>
                            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
                                <Typography sx={{ fontSize: "14px" }}>MULTIPLIER</Typography>
                                <Tooltip title="Please enter value from 1 to 5" arrow placement="top">
                                    <InfoOutlinedIcon sx={{ fontSize: 16, color: "#64748b", cursor: "pointer" }} />
                                </Tooltip>
                            </Box>
                            <TextField
                                type="number" value={multiplier} disabled={!editable}
                                onChange={(e) => {
                                    const value = e.target.value;
                                    if (value === "" || (Number(value) >= 0 && Number(value) <= 2)) setMultiplier(value);
                                }}
                                inputProps={{ min: 0, max: 2, step: 0.01 }} sx={recalculateInputStyle}
                            />
                        </Box>

                        <Box>
                            <Typography sx={{ mb: 1, fontSize: "14px" }}>MULTIPLIER HORIZON</Typography>
                            <FormControl sx={inputStyle}>
                                <Select value={multiplierHorizon} onChange={(e) => setMultiplierHorizon(e.target.value)} disabled={!editable}>
                                    <MenuItem value="History">History</MenuItem>
                                    <MenuItem value="Forecast">Forecast</MenuItem>
                                    <MenuItem value="Both History & Forecast">Both History & Forecast </MenuItem>
                                </Select>
                            </FormControl>
                        </Box>

                        <Button variant="contained" disabled={!editable} onClick={handleRecalculate}
                            sx={{ height: "35px", mt: 3, textTransform: "none", backgroundColor: "#4F46E5", borderRadius: "8px" }}>
                            Recalculate
                        </Button>
                    </Box>
                </Paper>

                {/* ── SUB TABS ── */}
                <Box sx={{ mt: 2, backgroundColor: "#e2e8f0", borderBottom: "1px solid #D8DEE8", px: 0.5, pt: 0.5, display: "flex", gap: 0.5 }}>
                    {TABS.map((tab) => (
                        <Box
                            key={tab.value}
                            onClick={() => setActiveTab(tab.value)}
                            sx={{
                                px: 2, py: 1, cursor: "pointer", fontSize: "12px", fontWeight: 600,
                                borderRadius: "6px 6px 0 0",
                                color: activeTab === tab.value ? "#4F46E5" : "#64748b",
                                backgroundColor: activeTab === tab.value ? "white" : "transparent",
                                border: activeTab === tab.value ? "1px solid #D8DEE8" : "1px solid transparent",
                                borderBottom: activeTab === tab.value ? "1px solid white" : "1px solid transparent",
                                mb: activeTab === tab.value ? "-1px" : 0,
                                userSelect: "none",
                                "&:hover": { backgroundColor: activeTab === tab.value ? "white" : "#f1f5f9" },
                            }}
                        >
                            {tab.label}
                        </Box>
                    ))}
                </Box>

                {/* ── TAB CONTENT ── */}
                <Box sx={{ p: 3 }}>

                    {/* Chart Container */}
                    <Paper sx={{ p: 2, borderRadius: "12px", border: "1px solid #D8DEE8", boxShadow: "none", minHeight: "300px", mb: 3 }}>
                        <ForecastChart chartData={chartData} metricUnit={isPercentTab ? "%" : metricUnit} />
                    </Paper>

                    {/* ── MARKET METRICS TABLE ── */}
                    <Box id="volumeSection">

                        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.5, flexWrap: "wrap", gap: 1 }}>
                            <Typography sx={{ fontSize: "16px", fontWeight: 700, color: "#1e293b" }}>
                                Market Metrics Table
                            </Typography>

                            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, flexWrap: "wrap" }}>
                                <ToggleButtonGroup
                                    value={totalMarketViewMode}
                                    exclusive
                                    size="small"
                                    onChange={(e, val) => { if (val) setTotalMarketViewMode(val); }}
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

                                <Button
                                    size="small"
                                    variant="outlined"
                                    onClick={clickTableEdit}
                                    sx={{
                                        textTransform: "none", fontSize: "12px", fontWeight: 600,
                                        borderRadius: "6px", borderColor: "#e2e8f0", color: "#3d89f3", px: 1.5,
                                        "&:hover": { borderColor: "#cbd5e1", backgroundColor: "#f8fafc" },
                                    }}
                                >
                                    Edit Table
                                </Button>

                                <Button
                                    size="small"
                                    variant="contained"
                                    onClick={applySelectedScenario}
                                    sx={{
                                        textTransform: "none", fontSize: "12px", fontWeight: 600,
                                        borderRadius: "6px", backgroundColor: "#4F46E5", px: 1.5,
                                        "&:hover": { backgroundColor: "#4338ca" },
                                    }}
                                >
                                    Apply Selected Scenario
                                </Button>

                                <Box sx={{ position: "relative" }}>
                                    <Box
                                        onClick={(e) => { e.stopPropagation(); toggleScenariosDropdown(e); }}
                                        sx={{
                                            height: 32, px: 1.5, display: "flex", alignItems: "center",
                                            border: "1px solid #e2e8f0", borderRadius: "6px", cursor: "pointer",
                                            fontSize: "12px", fontWeight: 600, color: "#64748b", minWidth: 160, userSelect: "none",
                                            "&:hover": { backgroundColor: "#f8fafc" },
                                        }}
                                    >
                                        Compare Scenarios ▼
                                    </Box>
                                    {showScenariosDropdown && (
                                        <Box
                                            onClick={(e) => e.stopPropagation()}
                                            sx={{
                                                position: "absolute", top: 36, right: 0, backgroundColor: "white",
                                                border: "1px solid #e2e8f0", borderRadius: "8px",
                                                boxShadow: "0 4px 16px rgba(0,0,0,0.12)", zIndex: 200, p: 1, minWidth: 200,
                                            }}
                                        >
                                            {COMPARE_OPTIONS.map((s) => (
                                                <Box
                                                    key={s}
                                                    component="label"
                                                    sx={{
                                                        display: "flex", alignItems: "center", gap: 1,
                                                        px: 1, py: 0.75, cursor: "pointer", borderRadius: "4px",
                                                        "&:hover": { backgroundColor: "#f8fafc" },
                                                    }}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        value={s}
                                                        checked={selectedCompareScenarios.includes(s)}
                                                        onChange={() => handleScenarioSelectionChange(s)}
                                                    />
                                                    <Typography sx={{ fontSize: "13px", fontWeight: 500, color: "#1e293b" }}>
                                                        {s}
                                                    </Typography>
                                                </Box>
                                            ))}
                                        </Box>
                                    )}
                                </Box>
                            </Box>
                        </Box>

                        {/* Table Layout Wrapper */}
                        <Box sx={{ backgroundColor: "white", borderRadius: "8px", border: "1px solid #e2e8f0", overflowX: "auto" }}>
                            <Box component="table" sx={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                                <Box component="thead">
                                    <Box component="tr">
                                        <Box component="th" sx={{
                                            position: "sticky", left: 0, zIndex: 2,
                                            backgroundColor: "#f8fafc", color: "#0f172a",
                                            fontWeight: 700, fontSize: "13px", textAlign: "left",
                                            p: "12px 16px", minWidth: 220,
                                            borderRight: "1px solid #e2e8f0", borderBottom: "1px solid #e2e8f0",
                                        }}>
                                            Hierarchy
                                        </Box>
                                        {(chartData?.months || []).map((col) => (
                                            <Box component="th" key={col} sx={{
                                                backgroundColor: "#f8fafc", color: "#475569",
                                                fontWeight: 700, fontSize: "12px", textAlign: "center",
                                                p: "12px 8px", minWidth: 85, whiteSpace: "nowrap",
                                                borderBottom: "1px solid #e2e8f0",
                                            }}>
                                                {formatDateLabel(col)}
                                            </Box>
                                        ))}
                                    </Box>
                                </Box>

                                <Box component="tbody">
                                    {tableData.length === 0 ? (
                                        <>
                                            <Box component="tr" sx={{ "&:hover": { backgroundColor: "#f8fafc" } }}>
                                                <Box component="td" sx={{
                                                    position: "sticky", left: 0, zIndex: 1,
                                                    backgroundColor: "white",
                                                    borderRight: "1px solid #e2e8f0",
                                                    borderBottom: "1px solid #f1f5f9",
                                                    p: "10px 16px",
                                                }}>
                                                    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                                                        <input
                                                            type="radio"
                                                            name="activeScenarioRadio"
                                                            value={currentlyAppliedScenario || "Engine Forecast"}
                                                            checked={tentativeRadioSelectedScenario === (currentlyAppliedScenario || "Engine Forecast")}
                                                            onChange={() => handleActiveScenarioRadioChange(currentlyAppliedScenario || "Engine Forecast")}
                                                            style={{ accentColor: "#4F46E5", width: 14, height: 14, margin: 0 }}
                                                        />
                                                        <Typography sx={{ fontSize: "13px", fontWeight: 700, color: "#0f172a" }}>
                                                            {currentlyAppliedScenario || "Engine Forecast"}
                                                        </Typography>
                                                    </Box>
                                                </Box>
                                                {(chartData?.months || []).map((_, i) => (
                                                    <Box component="td" key={i} sx={{
                                                        p: "10px 8px", textAlign: "center", fontSize: "13px",
                                                        fontWeight: 700, color: "#0f172a",
                                                        borderBottom: "1px solid #f1f5f9",
                                                    }}>
                                                        —
                                                    </Box>
                                                ))}
                                            </Box>

                                            {selectedCompareScenarios.map((scen) => {
                                                const isApplied = currentlyAppliedScenario === scen;
                                                return (
                                                    <Box component="tr" key={scen} sx={{ "&:hover": { backgroundColor: "#f8fafc" } }}>
                                                        <Box component="td" sx={{
                                                            position: "sticky", left: 0, zIndex: 1,
                                                            backgroundColor: "white",
                                                            borderRight: "1px solid #e2e8f0",
                                                            borderBottom: "1px solid #f1f5f9",
                                                            p: "10px 16px",
                                                        }}>
                                                            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                                                                <input
                                                                    type="radio"
                                                                    name="activeScenarioRadio"
                                                                    value={scen}
                                                                    checked={tentativeRadioSelectedScenario === scen}
                                                                    onChange={() => handleActiveScenarioRadioChange(scen)}
                                                                    style={{ accentColor: "#4F46E5", width: 14, height: 14, margin: 0 }}
                                                                />
                                                                <Typography sx={{ fontSize: "13px", fontWeight: 600, color: "#0f172a" }}>
                                                                    {scen}
                                                                </Typography>
                                                                {isApplied && (
                                                                    <Typography component="span" sx={{ fontSize: "12px", fontWeight: 600, color: "#10b981" }}>
                                                                        (Applied)
                                                                    </Typography>
                                                                )}
                                                            </Box>
                                                        </Box>
                                                        {(chartData?.months || []).map((_, i) => (
                                                            <Box component="td" key={i} sx={{
                                                                p: "10px 8px", textAlign: "center", fontSize: "13px",
                                                                fontWeight: 400, color: "#475569",
                                                                borderBottom: "1px solid #f1f5f9",
                                                            }}>
                                                                —
                                                            </Box>
                                                        ))}
                                                    </Box>
                                                );
                                            })}
                                        </>
                                    ) : (
                                        groupedTableHierarchy.map((group) => {
                                            const isExpanded = !!expandedBrands[group.brandName];
                                            const hasChildren = group.children.length > 0;
                                            const mainRowApplied = group.mainRow?.is_applied;

                                            return (
                                                <React.Fragment key={group.brandName}>
                                                    {/* Parent Product Row Header Element */}
                                                    <Box 
                                                        component="tr" 
                                                        onClick={() => hasChildren && toggleBrandExpand(group.brandName)}
                                                        sx={{ 
                                                            cursor: hasChildren ? "pointer" : "default", 
                                                            backgroundColor: "#f8fafc",
                                                            fontWeight: "bold",
                                                            "&:hover": { backgroundColor: "#f1f5f9" } 
                                                        }}
                                                    >
                                                        <Box component="td" sx={{
                                                            position: "sticky", left: 0, zIndex: 1,
                                                            backgroundColor: "#f8fafc",
                                                            borderRight: "1px solid #e2e8f0",
                                                            borderBottom: "1px solid #cbd5e1",
                                                            p: "12px 16px",
                                                        }}>
                                                            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                                                                {hasChildren && (
                                                                    <Typography component="span" sx={{ fontSize: "10px", width: "12px" }}>
                                                                        {isExpanded ? "▼" : "▶"}
                                                                    </Typography>
                                                                )}
                                                                <Typography sx={{ fontSize: "13px", fontWeight: 700, color: "#0f172a" }}>
                                                                    {group.brandName}
                                                                </Typography>
                                                                {mainRowApplied && (
                                                                    <Typography component="span" sx={{ fontSize: "11px", fontWeight: 600, color: "#10b981" }}>
                                                                        (Applied)
                                                                    </Typography>
                                                                )}
                                                            </Box>
                                                        </Box>
                                                        {(chartData?.months || []).map((col) => {
                                                            const val = group.mainRow?.monthly_data?.[col];
                                                            return (
                                                                <Box component="td" key={col} sx={{
                                                                    p: "10px 8px", textAlign: "center", fontSize: "13px",
                                                                    fontWeight: 700, color: "#0f172a",
                                                                    borderBottom: "1px solid #cbd5e1",
                                                                }}>
                                                                    {formatCellValue(val)}
                                                                </Box>
                                                            );
                                                        })}
                                                    </Box>

                                                    {/* Nested Payers Subsplit Rows */}
                                                    {isExpanded && group.children.map((childRow, childIdx) => {
                                                        const isChildApplied = childRow.is_applied;
                                                        return (
                                                            <Box component="tr" key={childIdx} sx={{ "&:hover": { backgroundColor: "#f8fafc" } }}>
                                                                <Box component="td" sx={{
                                                                    position: "sticky", left: 0, zIndex: 1,
                                                                    backgroundColor: "white",
                                                                    borderRight: "1px solid #e2e8f0",
                                                                    borderBottom: "1px solid #f1f5f9",
                                                                    p: "10px 16px", pl: 4
                                                                }}>
                                                                    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                                                                        <input
                                                                            type="radio"
                                                                            name="activeScenarioRadio"
                                                                            value={childRow.hierarchy}
                                                                            checked={tentativeRadioSelectedScenario === childRow.hierarchy}
                                                                            onChange={() => handleActiveScenarioRadioChange(childRow.hierarchy)}
                                                                            style={{ accentColor: "#4F46E5", width: 14, height: 14, margin: 0 }}
                                                                        />
                                                                        <Typography sx={{
                                                                            fontSize: "13px",
                                                                            fontWeight: isChildApplied ? 700 : 400,
                                                                            color: "#334155"
                                                                        }}>
                                                                            {childRow.cleanLabel}
                                                                        </Typography>
                                                                        {isChildApplied && (
                                                                            <Typography component="span" sx={{ fontSize: "12px", fontWeight: 600, color: "#10b981" }}>
                                                                                (Applied)
                                                                            </Typography>
                                                                        )}
                                                                    </Box>
                                                                </Box>
                                                                {(chartData?.months || []).map((col) => {
                                                                    const val = childRow.monthly_data?.[col];
                                                                    return (
                                                                        <Box component="td" key={col} sx={{
                                                                            p: "10px 8px", textAlign: "center", fontSize: "13px",
                                                                            fontWeight: isChildApplied ? 700 : 400,
                                                                            color: isChildApplied ? "#0f172a" : (val != null ? "#475569" : "#cbd5e1"),
                                                                            borderBottom: "1px solid #f1f5f9",
                                                                        }}>
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