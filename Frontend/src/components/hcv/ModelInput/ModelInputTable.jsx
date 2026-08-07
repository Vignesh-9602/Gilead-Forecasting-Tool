import React, { useMemo } from "react";
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
  Button,
  IconButton,
} from "@mui/material";
import Tooltip from "@mui/material/Tooltip";
import DownloadIcon from "@mui/icons-material/Download";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import dayjs from "dayjs";

// ─── Constants ────────────────────────────────────────────────────────────────
const TAB_KEY_MAP = {
  total_market: "total_market_volume",
  prod_dist: "product_distribution",
  // Backend key is "payment_type_distribution" — aliased both ways so
  // responses using either name still resolve (kept in sync with the same
  // map in ModelInput.jsx).
  payer_dist: "payment_type_distribution",
  payer_prod: "payer_product",
  prod_payer: "product_payer",
};

const DATE_INPUT_FORMATS = [
  "MMM-YY",
  "YYYY-MM",
  "YYYY-MM-DD",
  "YYYY-MM-DDTHH:mm:ssZ",
];

// ─── Pure helpers ─────────────────────────────────────────────────────────────
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

const toApiMetricKey = (m) => (m === "market_share" ? "payer_share" : "payer_volume");

const tagHierarchyWithScenario = (hierarchy, scenarioName) => {
  if (!hierarchy || hierarchy === scenarioName) return hierarchy;
  if (hierarchy.includes(" - ")) {
    const idx = hierarchy.indexOf(" - ");
    const parent = hierarchy.slice(0, idx);
    const child = hierarchy.slice(idx + 3);
    return `${parent} (${scenarioName}) - ${child} (${scenarioName})`;
  }
  return `${hierarchy} (${scenarioName})`;
};

// ─── MarketMetricsTable ───────────────────────────────────────────────────────
const ModelInputTable = React.memo(function ModelInputTable({
  // Data / derived inputs
  activeTab,
  activeTabLabel,
  onActiveTabChange,
  tableData,
  chartData,
  liverRawData,
  liverTabsRaw,
  metric,
  metricUnit,
  totalMarketViewMode,
  selectedCompareScenarios,
  compareScenarioOptions,
  currentlyAppliedScenario,
  tentativeRadioSelectedScenario,
  appliedScenarioReady,
  userHasCustomizedCompare,
  savedScenarioRows,
  appliedProductFilter,
  appliedPayerFilter,
  appliedBrand,
  appliedFromDate,
  appliedToDate,
  expandedBrands,
  filterOptions,
  // Edit / flags
  tableEditing,
  isRefreshed,
  savingTable,
  isSavingEditChanges,
  editedHierarchies,
  showMetricFilter,
  showScenarioControls,
  showCompareScenarios,
  // Setters / handlers
  setExpandedBrands,
  setNewScenarioName,
  setSaveScenarioDialogOpen,
  handleMetricChange,
  setTotalMarketViewMode,
  handleCancelTableEdit,
  handleDownloadTable,
  handleConfirmSave,
  handleEnterTableEdit,
  handleSaveTableChanges,
  applySelectedScenario,
  handleCompareScenarioChange,
  handleActiveScenarioRadioChange,
  handleCellChange,
  onDeleteScenario,
  onDeleteScenarioClick,
}) {
  const isPercentTab = metric === "market_share";
  const isScenarioParentTab = activeTab === "prod_dist" || activeTab === "payer_dist";
  // "payment_payer_prod" is rendered by PaymentPayerProductTable instead of
  // this component — isThreeLevelTab is always false here, but kept as a
  // guard in a few shared functions below for defensiveness.
  const isThreeLevelTab = activeTab === "payment_payer_prod";

  // ── Forecast helper ─────────────────────────────────────────────────────────
  const isForecastMonth = (col) => {
    if (!chartData?.months?.length || chartData?.forecast_start_index == null)
      return false;
    return chartData.months.slice(chartData.forecast_start_index).includes(col);
  };

  // ── Cell formatter ──────────────────────────────────────────────────────────
  const formatCellValue = (val) => {
    if (val == null) return "—";
    const num = Number(val);
    if (metricUnit === "%") {
      const formatted = Number.isInteger(num) ? num : parseFloat(num.toFixed(2));
      return `${formatted}%`;
    }
    return num.toLocaleString(undefined, { maximumFractionDigits: 0 });
  };

  const toggleBrandExpand = (name) => {
    setExpandedBrands((prev) => ({ ...prev, [name]: !prev[name] }));
  };

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

  // ─── Standard (non-3-level) tagged rows + hierarchy ────────────────────────
  const taggedTableRows = useMemo(() => {
    if (isThreeLevelTab) return []; // 3-level tab uses its own row generation

    if (activeTab === "total_market") {
      return tableData.map((row) => ({ ...row, scenario: row.hierarchy, cleanHierarchy: row.hierarchy }));
    }

    const scenarioNames = selectedCompareScenarios.length
      ? selectedCompareScenarios
      : (compareScenarioOptions.length
        ? compareScenarioOptions
        : (currentlyAppliedScenario ? [currentlyAppliedScenario] : []));

    const backendTabKey = TAB_KEY_MAP[activeTab] || activeTab;
    const activeMetricKey = toApiMetricKey(metric);
    const fallbackMonths = chartData?.months || [];

    const toDisplayData = (values, labelsForThisScenario) => {
      const obj = {};
      labelsForThisScenario.forEach((label, i) => {
        const v = values?.[i];
        obj[label] = v == null ? null : Number(v);
      });
      return obj;
    };

    const out = [];
    scenarioNames.forEach((scenarioName) => {
      if (scenarioName === currentlyAppliedScenario) {
        tableData.forEach((row) => {
          out.push({
            ...row,
            scenario: scenarioName,
            cleanHierarchy: row.hierarchy,
            hierarchy: tagHierarchyWithScenario(row.hierarchy, scenarioName),
          });
        });
        return;
      }

      const tabObj =
        liverRawData?.scenarios?.[scenarioName]?.market_analysis?.[backendTabKey];
      if (!tabObj) return;
      const metricObj =
        tabObj[activeMetricKey] ||
        tabObj.payer_volume ||
        tabObj.payer_share ||
        Object.values(tabObj)[0];
      const useYearlyData = totalMarketViewMode === "yearly";
      const labels = useYearlyData
        ? (metricObj?.yearly?.chart?.months || metricObj?.yearly?.table?.headers || metricObj?.monthly?.chart?.months || fallbackMonths)
        : (metricObj?.monthly?.chart?.months || metricObj?.chart?.months || fallbackMonths);
      const rows = useYearlyData
        ? (metricObj?.yearly?.table?.rows || metricObj?.monthly?.table?.rows || metricObj?.table?.rows || [])
        : (metricObj?.monthly?.table?.rows || metricObj?.table?.rows || []);

      rows.forEach((r) => {
        const parentLabel = r.label || r.hierarchy || "";
        if (!parentLabel) return;
        const values = Array.isArray(r.values) ? r.values : Array.isArray(r.total) ? r.total : [];
        out.push({
          hierarchy: tagHierarchyWithScenario(parentLabel, scenarioName),
          cleanHierarchy: parentLabel,
          monthly_data: toDisplayData(values, labels),
          is_applied: false,
          scenario: scenarioName,
        });
        (r.children || []).forEach((c) => {
          const cleanCombo = `${parentLabel} - ${c.label}`;
          const childValues = Array.isArray(c.values) ? c.values : [];
          out.push({
            hierarchy: tagHierarchyWithScenario(cleanCombo, scenarioName),
            cleanHierarchy: cleanCombo,
            monthly_data: toDisplayData(childValues, labels),
            is_applied: false,
            scenario: scenarioName,
          });
        });
      });
    });
    return out;
  }, [
    isThreeLevelTab,
    activeTab,
    tableData,
    liverRawData,
    metric,
    chartData,
    selectedCompareScenarios,
    currentlyAppliedScenario,
    totalMarketViewMode,
    compareScenarioOptions,
  ]);

  // ── Hierarchy grouping (standard 2-level tabs) ────────────────────────────
  const groupedTableHierarchy = useMemo(() => {
    if (isThreeLevelTab) return []; // guard kept for safety; always false here

    if (isScenarioParentTab) {
      const byScenario = {};
      taggedTableRows.forEach((row) => {
        const name = row.scenario || "Unknown Scenario";
        if (!byScenario[name]) byScenario[name] = { rows: [], scenario: name };
        byScenario[name].rows.push(row);
      });

      return Object.keys(byScenario).map((scenarioName) => {
        const entry = byScenario[scenarioName];
        const children = entry.rows
          .filter((row) => {
            const clean = (row.hierarchy || "").split(" (")[0].trim().toLowerCase();
            return !clean.startsWith("total") && !clean.startsWith("grand total");
          })
          .map((row) => ({
            ...row,
            cleanLabel: (row.hierarchy || "").split(" (")[0].trim(),
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
          monthly_data[m] = any ? sum : null;
        });
        return {
          brandName: scenarioName,
          mainRow: {
            hierarchy: scenarioName,
            monthly_data,
            is_applied: entry.rows.some((r) => r.is_applied),
          },
          children,
          isScenarioOverlay: scenarioName !== currentlyAppliedScenario,
          isScenarioGroup: true,
        };
      });
    }

    // total_market, Payer-Product, Product-Payer
    const map = {};
    taggedTableRows.forEach((row) => {
      const raw = row.hierarchy || "";
      if (raw.includes(" - ")) {
        const parts = raw.split(" - ");
        const brandKey = parts[0].trim();
        const payerKey = parts.slice(1).join(" - ").trim();
        if (!map[brandKey]) map[brandKey] = { mainRow: null, children: [], scenario: row.scenario };
        map[brandKey].children.push({ ...row, cleanLabel: payerKey });
      } else {
        const brandKey = raw.trim();
        if (!map[brandKey]) map[brandKey] = { mainRow: null, children: [], scenario: row.scenario };
        map[brandKey].mainRow = row;
      }
    });

    return Object.keys(map).map((brandKey) => {
      const entry = map[brandKey];
      let mainRow = entry.mainRow;
      if (!mainRow) {
        const children = (entry.children || []).filter((c) => {
          const clean = (c.cleanLabel || "").trim().toLowerCase();
          return !clean.startsWith("total") && !clean.startsWith("grand total");
        });
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
        isScenarioOverlay:
          activeTab === "total_market" ? false : entry.scenario !== currentlyAppliedScenario,
      };
    });
  }, [isThreeLevelTab, activeTab, isScenarioParentTab, taggedTableRows, chartData, currentlyAppliedScenario, isPercentTab]);

  // ── Monthly / Yearly toggle helpers ──────────────────────────────────────
  const displayColumns = useMemo(() => {
    // Guard kept for safety; always false here (payment_payer_prod is
    // rendered by PaymentPayerProductTable instead of this component).
    if (isThreeLevelTab) return [];

    const backendKey = TAB_KEY_MAP[activeTab] || activeTab;
    const tabsMap = liverTabsRaw?.tabs || {};
    const tab = tabsMap[backendKey] || tabsMap[Object.keys(tabsMap)[0]] || null;
    const globalMonths = liverTabsRaw?.months || [];

    const fromYM = appliedFromDate ? toYearMonth(appliedFromDate) : "";
    const toYM = appliedToDate ? toYearMonth(appliedToDate) : "";

    const finalize = (arr) => Array.from(new Set((arr || []).map((v) => String(v))));

    const clipMonthly = (arr) => {
      if (!fromYM && !toYM) return arr;
      return arr.filter((m) => {
        const ym = toYearMonth(m) || String(m);
        if (fromYM && ym < fromYM) return false;
        if (toYM && ym > toYM) return false;
        return true;
      });
    };

    if (totalMarketViewMode !== "yearly") return finalize(clipMonthly(globalMonths));

    const fromYear = fromYM ? fromYM.slice(0, 4) : "";
    const toYear = toYM ? toYM.slice(0, 4) : "";
    const clipYearly = (arr) => {
      if (!fromYear && !toYear) return arr;
      return arr.filter((y) => {
        const yr = String(y).slice(0, 4);
        if (fromYear && yr < fromYear) return false;
        if (toYear && yr > toYear) return false;
        return true;
      });
    };

    const yearlyMonths = tab?.yearlyChart?.months;
    if (yearlyMonths?.length) return finalize(clipYearly(yearlyMonths));
    const years = [];
    globalMonths.forEach((m) => {
      const y = String(m).slice(0, 4);
      if (y && !years.includes(y)) years.push(y);
    });
    return finalize(clipYearly(years));
  }, [isThreeLevelTab, liverTabsRaw, activeTab, totalMarketViewMode, appliedFromDate, appliedToDate]);

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

  const getColumnValue = (row, col) => {
    if (totalMarketViewMode !== "yearly") {
      return row?.monthly_data?.[col];
    }

    const direct = row?.monthly_data?.[col];
    if (direct != null) return direct;

    const values = Array.isArray(row?.values)
      ? row.values
      : Array.isArray(row?.total)
        ? row.total
        : [];
    if (values.length) {
      const idx = displayColumns.indexOf(col);
      if (idx >= 0 && values[idx] != null) {
        return Number(values[idx]);
      }
    }

    const monthsInYear = yearToMonthsMap[col] || [];
    let sum = 0, count = 0;
    monthsInYear.forEach((m) => {
      const v = row?.monthly_data?.[m];
      if (v != null && !Number.isNaN(Number(v))) { sum += Number(v); count += 1; }
    });
    if (count === 0) return null;
    return metricUnit === "%" ? sum / count : sum;
  };

  const isForecastColumn = (col) => {
    if (totalMarketViewMode !== "yearly") return isForecastMonth(col);
    const backendKey = TAB_KEY_MAP[activeTab] || activeTab;
    const yearlyChart = liverTabsRaw?.tabs?.[backendKey]?.yearlyChart;
    if (yearlyChart?.months?.length && yearlyChart?.forecast_start_index != null) {
      const fcastYears = yearlyChart.months.slice(yearlyChart.forecast_start_index);
      return fcastYears.includes(col);
    }
    const monthsInYear = yearToMonthsMap[col] || [];
    return monthsInYear.some((m) => isForecastMonth(m));
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
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

              {/* Expand/Collapse only for standard tabs with children */}
              {!isThreeLevelTab && groupedTableHierarchy.some((g) => g.children?.length > 0) && (
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
              {/* Hierarchy Order — 2-level tab (Payer/Product) */}
              {activeTab === "payer_prod" || activeTab === "prod_payer" ? (
                <FormControl size="small" sx={{ minWidth: 190 }}>
                  <Select
                    value={activeTab}
                    onChange={(e) => onActiveTabChange?.(e.target.value)}
                    sx={{
                      height: "34px",
                      fontSize: "12px",
                      fontWeight: 600,
                      borderRadius: "8px",
                      backgroundColor: "#fcfcfd",
                    }}
                  >
                    <MenuItem value="payer_prod" sx={{ fontSize: "12px" }}>
                     Payment Type-Product
                    </MenuItem>
                    <MenuItem value="prod_payer" sx={{ fontSize: "12px" }}>
                     Product-Payment Type
                    </MenuItem>
                  </Select>
                </FormControl>
              ) : null}

              {/* Metric filter */}
              {showMetricFilter && filterOptions?.metric_filters?.length > 0 && (
                <FormControl sx={{ ...tableInputStyle, minWidth: "160px" }}>
                  <Select
                    value={metric}
                    onChange={(e) => handleMetricChange(e.target.value)}
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

              {/* Download / Save / Edit / Refresh / Cancel — only for standard tabs */}
              {!isThreeLevelTab && (
                <>
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
                    Save
                  </Button>

                  <Button
                    variant="outlined"
                    onClick={handleEnterTableEdit}
                    disabled={
                      tableEditing ||
                      !appliedScenarioReady ||
                      (activeTab !== "total_market" && metric === "market_volume")
                    }
                    sx={secondaryButtonStyle}
                  >
                    Edit Changes
                  </Button>

                  {tableEditing && (
                    <Button
                      variant="contained"
                      disabled={savingTable || Object.keys(editedHierarchies).length === 0}
                      onClick={handleSaveTableChanges}
                      sx={primaryButtonStyle}
                    >
                     Refresh
                    </Button>
                  )}
                  {tableEditing && (
                  <Button
                    variant="outlined"
                    onClick={handleCancelTableEdit}
                    disabled={!tableEditing || totalMarketViewMode === "yearly"}
                    sx={secondaryButtonStyle}
                  >
                    Cancel
                  </Button>
                  )}

                  {showScenarioControls && (
                    <Button
                      variant="contained"
                      onClick={applySelectedScenario}
                      sx={primaryButtonStyle}
                    >
                      Apply Selected Scenario
                    </Button>
                  )}

                  {showCompareScenarios && (
                    <FormControl sx={{ ...tableInputStyle, width: 220, minWidth: 220, maxWidth: 220 }}>
                      <Select
                        multiple
                        displayEmpty
                        value={selectedCompareScenarios}
                        onChange={handleCompareScenarioChange}
                        input={<OutlinedInput />}
                        sx={{
                          fontSize: "13px",
                          "& .MuiSelect-select": {
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          },
                        }}
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
                </>
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
          {/* ═══════════════════════════════════════════════════════════════
              STANDARD TABS (total_market, prod_dist, payer_dist,
              payer_prod, prod_payer) — "payment_payer_prod" is rendered by
              PaymentPayerProductTable instead, so this component only ever
              needs the 2-level logic below.
              ═══════════════════════════════════════════════════════════════ */}
          <>
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
                        if (activeTab !== "total_market") return true;
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

                        const cleanBrandName =
                          group.mainRow?.cleanHierarchy || (group.brandName || "").split(" (")[0];

                        let isAppliedParent = false;

                        if (activeTab === "prod_dist" || activeTab === "payer_dist") {
                          isAppliedParent = !group.isScenarioOverlay;
                        } else if (activeTab === "payer_prod") {
                          isAppliedParent = targetParentLabel === currentPayer;
                        } else if (activeTab === "prod_payer") {
                          isAppliedParent = targetParentLabel === currentBrand;
                        }

                        const isTotalRow =
                          (group.brandName || "").trim().toLowerCase().startsWith("total");

                        const isAppliedScenarioGroup =
                          activeTab === "total_market"
                            ? (group.brandName || "") === (currentlyAppliedScenario || "")
                            : !group.isScenarioOverlay;
                        const isEditEligible = (() => {
                          if (!tableEditing) return false;
                          if (totalMarketViewMode !== "monthly") return false;
                          if (isTotalRow) return false;
                          if (!isAppliedScenarioGroup) return false;
                          if (activeTab === "total_market") {
                            return !hasChildren;
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
                                borderBottom: "1px solid #e2e8f0",
                                backgroundColor:
                                  (isAppliedScenarioGroup && activeTab === "total_market")
                                    ? "#fffbeb"
                                    : hasChildren
                                      ? "#f8fafc"
                                      : "white",
                                "&:hover": {
                                  backgroundColor:
                                    (isAppliedScenarioGroup && activeTab === "total_market")
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
                                    : (isAppliedScenarioGroup && activeTab === "total_market")
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
                                    justifyContent: "space-between",
                                    gap: 1,
                                    width: "100%",
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
                                        color: (isAppliedParent || (isAppliedScenarioGroup && activeTab === "total_market"))
                                          ? "#f59e0b"
                                          : "#64748b",
                                      }}
                                    >
                                      {isExpanded ? "▼" : "▶"}
                                    </Typography>
                                  )}

                                  <Box sx={{ display: "flex", alignItems: "center", flex: 1, minWidth: 0 }}>
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
                                          : (isAppliedScenarioGroup && activeTab === "total_market")
                                            ? "#f59e0b"
                                            : isTotalRow
                                              ? "#1e293b"
                                              : "#334155",
                                      }}
                                    >
                                      {group.brandName}
                                    </Typography>
                                  </Box>

                                  {activeTab === "total_market" && group.brandName !== "Base" && (
                                    <Tooltip title="Delete Scenario">
                                      <IconButton
                                        size="small"
                                        data-testid="delete-scenario-button"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          if (onDeleteScenarioClick) {
                                            onDeleteScenarioClick(group.brandName);
                                          } else if (onDeleteScenario) {
                                            onDeleteScenario(group.brandName);
                                          }
                                        }}
                                        sx={{ ml: "auto", mr: 0.25, color: "#dc2626" }}
                                      >
                                        <DeleteOutlineIcon fontSize="small" />
                                      </IconButton>
                                    </Tooltip>
                                  )}
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
                                      fontWeight: hasChildren ? 700 : isTotalRow ? 800 : 500,
                                      backgroundColor: isEditableCell
                                        ? isF ? '#eff6ff' : '#f8fafc'
                                        : isAppliedParent && isF ? '#fffbeb' : isF ? '#ffffff' : '#F1F5F9',
                                      color: !isEditableCell && isAppliedParent && isF ? '#f59e0b' : '#1e293b',
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
                                            handleCellChange(cleanBrandName, col, e.target.value);
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

                            {/* Children */}
                            {showChildren &&
                              group.children.map((childRow, ci) => {
                                const childLabel = childRow.cleanLabel || childRow.hierarchy || "";
                                const childClean = childLabel.split(" (")[0].trim().toLowerCase();

                                let isHighlightedChild = false;
                                if (activeTab === "prod_dist" && currentBrand) {
                                  isHighlightedChild = childClean === currentBrand;
                                } else if (activeTab === "payer_dist" && currentPayer) {
                                  isHighlightedChild = childClean === currentPayer;
                                } else if (activeTab === "payer_prod" || activeTab === "prod_payer") {
                                  isHighlightedChild =
                                    isAppliedParent &&
                                    ((activeTab === "payer_prod" && childClean === currentBrand) ||
                                     (activeTab === "prod_payer" && childClean === currentPayer));
                                }

                                const isEditableChild =
                                  tableEditing &&
                                  totalMarketViewMode === "monthly" &&
                                  activeTab !== "total_market" &&
                                  !isTotalRow &&
                                  isAppliedScenarioGroup;

                                return (
                                  <Box
                                    component="tr"
                                    key={ci}
                                    sx={{
                                      borderBottom: "1px solid #e2e8f0",
                                      backgroundColor: isHighlightedChild ? "#fffbeb" : "white",
                                      "&:hover": { backgroundColor: isHighlightedChild ? "#fff3c4" : "#f8fafc" },
                                    }}
                                  >
                                    <Box
                                      component="td"
                                      sx={{
                                        position: "sticky",
                                        left: 0,
                                        zIndex: 1,
                                        backgroundColor: isHighlightedChild ? "#fffbeb" : "white",
                                        borderRight: "2px solid #e2e8f0",
                                        p: "10px 16px",
                                        pl: "40px",
                                        minWidth: 220,
                                        maxWidth: 220,
                                      }}
                                    >
                                      <Typography
                                        sx={{
                                          fontSize: "14px",
                                          fontWeight: isHighlightedChild ? 700 : 500,
                                          color: isHighlightedChild ? "#f59e0b" : "#334155",
                                        }}
                                      >
                                        {childLabel}
                                      </Typography>
                                    </Box>

                                    {displayColumns.map((col) => {
                                      const isFChild = isForecastColumn(col);
                                      const childVal = childRow?.monthly_data?.[col];

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
                                                  handleCellChange(childRow.cleanHierarchy || childRow.hierarchy, col, e.target.value);
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

                    {/* Saved-scenario rows */}
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
                                  justifyContent: "space-between",
                                  gap: 1.5,
                                  width: "100%",
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
                                <Box sx={{ display: "flex", alignItems: "center", flex: 1, minWidth: 0 }}>
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
                                {name !== "Base" && (
                                  <Tooltip title="Delete Scenario">
                                    <IconButton
                                      size="small"
                                      data-testid="delete-scenario-button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        if (onDeleteScenarioClick) {
                                          onDeleteScenarioClick(name);
                                        } else if (onDeleteScenario) {
                                          onDeleteScenario(name);
                                        }
                                      }}
                                      sx={{ ml: "auto", mr: 0.25, color: "#dc2626" }}
                                    >
                                      <DeleteOutlineIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
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
            </>
        </Box>
      </Box>
    </Paper>
  );
});

export default ModelInputTable;