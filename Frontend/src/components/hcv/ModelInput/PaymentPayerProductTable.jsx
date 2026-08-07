import React, { useMemo, useState } from "react";
import {
  Box,
  Paper,
  Typography,
  FormControl,
  Select,
  MenuItem,
  Button,
  IconButton,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DownloadIcon from "@mui/icons-material/Download";
import Tooltip from "@mui/material/Tooltip";
import Plot from "react-plotly.js";
import dayjs from "dayjs";

const PlotComponent = Plot.default || Plot;

// 3-level hierarchy tab (Payment Type -> Payer -> Product). The backend now
// returns real data for this tab under market_analysis.payment_type_payer_product
// (three pre-computed orderings — see ORDER_TO_BACKEND_KEY / hierarchyData
// prop). DEFAULT_PAYERS + the seeded generator below are kept only as a
// fallback for responses/scenarios that don't include this tab yet, so the
// table structure never goes fully blank.
const DEFAULT_PAYERS = ["Commercial", "Medicare", "Medicaid", "Cash"];

const HIERARCHY_ORDERS = [
  { value: "pt-payer-product", label: "Payment type-Payer-Product", dims: ["pt", "payer", "product"] },
  { value: "pt-product-payer", label: "Payment type-Product-Payer", dims: ["pt", "product", "payer"] },
  { value: "product-pt-payer", label: "Product-Payment type-Payer", dims: ["product", "pt", "payer"] },
];

// Maps each Hierarchy Order dropdown option onto the matching backend
// ordering key inside market_analysis.payment_type_payer_product (see
// ModelInput's normalizeLiverResponse -> buildHierarchyOrderTab). When the
// response includes real data for an ordering, it's used instead of the
// seeded mock below.
const ORDER_TO_BACKEND_KEY = {
  "pt-payer-product": "payment_type_payer_product",
  "pt-product-payer": "payment_type_product_payer",
  "product-pt-payer": "product_payment_type_payer",
};

const DIM_LABELS = { pt: "Payment Type", payer: "Payer", product: "Product" };

const DATE_INPUT_FORMATS = ["MMM-YY", "YYYY-MM", "YYYY-MM-DD", "YYYY-MM-DDTHH:mm:ssZ"];
// Same convention as ModelInputTable/ModelInputChart: always display as "Jun-20".
const formatDateLabel = (s) => {
  const parsed = dayjs(s, DATE_INPUT_FORMATS, true);
  const p = parsed.isValid() ? parsed : dayjs(s);
  return p.isValid() ? p.format("MMM-YY") : s;
};

// Simple deterministic hash -> [0, 1) so re-renders don't reshuffle mock values.
const seededRandom = (seedStr) => {
  let h = 0;
  for (let i = 0; i < seedStr.length; i++) h = (h * 31 + seedStr.charCodeAt(i)) | 0;
  const x = Math.sin(h) * 10000;
  return x - Math.floor(x);
};

const CHART_PALETTE = ["#4F46E5", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4"];

export default function PaymentPayerProductTable({
  activeTabLabel,
  payerOptions = [],
  productOptions = [],
  months = [],
  metric,
  filterOptions,
  handleMetricChange,
  totalMarketViewMode,
  setTotalMarketViewMode,
  appliedPayerFilter,
  appliedProductFilter,
  // Real backend data keyed by ordering (see ORDER_TO_BACKEND_KEY). Each
  // entry is { chart, table, yearlyChart, yearlyTable } — same shape every
  // other tab in this app uses. Falls back to the seeded mock below when a
  // given ordering has no real data.
  hierarchyData = {},
  // Toolbar action handlers (passed from ModelInput)
  handleDownloadTable,
  handleConfirmSave,
  handleEnterTableEdit,
  handleSaveTableChanges,
  handleCancelTableEdit,
  tableEditing,
  isRefreshed,
  savingTable,
  isSavingEditChanges,
  editedHierarchies = {},
  appliedScenarioReady,
}) {
  const [hierarchyOrder, setHierarchyOrder] = useState(HIERARCHY_ORDERS[0].value);

  const paymentTypes = payerOptions.length ? payerOptions : DEFAULT_PAYERS;
  const subPayers = paymentTypes;
  const products = productOptions.length ? productOptions : ["GILD", "ASGA", "Other"];
  const monthsKey = months.join("|");
  const monthLabels = useMemo(
    () => (months.length ? months : ["Jan-25", "Feb-25", "Mar-25", "Apr-25", "May-25", "Jun-25"]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [monthsKey],
  );

  const paymentTypesKey = paymentTypes.join("|");
  const productsKey = products.join("|");

  // Weights + product mix are generated once per dimension set (stable across
  // re-renders) so parent subtotals always equal the sum of their children.
  const { ptWeights, payerWeights, productShareMap } = useMemo(() => {
    const rawPt = Object.fromEntries(paymentTypes.map((pt) => [pt, 1 + seededRandom(`pt|${pt}`) * 3]));
    const ptSum = Object.values(rawPt).reduce((a, b) => a + b, 0);
    const ptW = Object.fromEntries(paymentTypes.map((pt) => [pt, rawPt[pt] / ptSum]));

    const rawPayer = Object.fromEntries(subPayers.map((p) => [p, 1 + seededRandom(`payer|${p}`) * 3]));
    const payerSum = Object.values(rawPayer).reduce((a, b) => a + b, 0);
    const payerW = Object.fromEntries(subPayers.map((p) => [p, rawPayer[p] / payerSum]));

    const shareMap = {};
    paymentTypes.forEach((pt) => {
      shareMap[pt] = {};
      subPayers.forEach((payer) => {
        const raw = products.map((prod) => 1 + seededRandom(`share|${pt}|${payer}|${prod}`) * 3);
        const sum = raw.reduce((a, b) => a + b, 0);
        shareMap[pt][payer] = Object.fromEntries(products.map((prod, i) => [prod, (raw[i] / sum) * 100]));
      });
    });

    return { ptWeights: ptW, payerWeights: payerW, productShareMap: shareMap };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paymentTypesKey, productsKey]);

  const monthlyTotal = (monthIdx) => 8000 + monthIdx * 40 + seededRandom(`vol|${monthIdx}`) * 500;

  const leafVolume = (pt, payer, product, monthIdx) =>
    monthlyTotal(monthIdx) * ptWeights[pt] * payerWeights[payer] * (productShareMap[pt][payer][product] / 100);

  // Sums leafVolume over every dimension not present in `fixed`.
  const sumVolume = (fixed, monthIdx) => {
    const pts = fixed.pt ? [fixed.pt] : paymentTypes;
    const payers = fixed.payer ? [fixed.payer] : subPayers;
    const prods = fixed.product ? [fixed.product] : products;
    let total = 0;
    pts.forEach((pt) => payers.forEach((payer) => prods.forEach((product) => {
      total += leafVolume(pt, payer, product, monthIdx);
    })));
    return total;
  };

  // ── Monthly / Yearly columns ──────────────────────────────────────────────
  const yearOfLabel = (label) => "20" + String(label).split("-")[1];

  const isPercent = metric === "market_share";

  // ── Real backend data for the currently selected ordering ────────────────
  // When present, this replaces the seeded mock below with actual
  // payer_volume/payer_share numbers from the apply-filters response.
  // (Declared before `columns` below, which reads realTableSrc.)
  const backendOrderKey = ORDER_TO_BACKEND_KEY[hierarchyOrder];
  const realOrder = hierarchyData && hierarchyData[backendOrderKey];
  const realTableSrc = realOrder
    ? (totalMarketViewMode === "yearly" ? realOrder.yearlyTable : realOrder.table)
    : null;
  const useRealData = !!(realTableSrc && realTableSrc.rows && realTableSrc.rows.length);

  const columns = useMemo(() => {
    // Real data: columns come straight from the backend table's own headers
    // (monthly dates or yearly labels) — one value per column already.
    if (realTableSrc?.headers?.length) {
      return realTableSrc.headers.map((label, idx) => ({ label, indices: [idx] }));
    }
    if (totalMarketViewMode !== "yearly") return monthLabels.map((label, idx) => ({ label, indices: [idx] }));
    const byYear = {};
    monthLabels.forEach((label, idx) => {
      const yr = yearOfLabel(label);
      if (!byYear[yr]) byYear[yr] = [];
      byYear[yr].push(idx);
    });
    return Object.entries(byYear).map(([yr, indices]) => ({ label: yr, indices }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monthLabels, totalMarketViewMode, realTableSrc]);

  // Flattens the backend's nested table.rows (arbitrary depth, via
  // `children`) into the same flat row list this component renders,
  // carrying each row's own values array (already the correctly-scaled
  // volume/share numbers computed by the backend for that hierarchy level).
  const flattenRealRows = (rowsIn, level = 0, ancestorLabels = []) => {
    const out = [];
    (rowsIn || []).forEach((r) => {
      const label = r.label || r.hierarchy || "";
      const path = [...ancestorLabels, label];
      out.push({
        level,
        label,
        values: Array.isArray(r.total) ? r.total : r.values || [],
        highlighted: dimMatchesPath(path),
      });
      if (r.children?.length) {
        out.push(...flattenRealRows(r.children, level + 1, path));
      }
    });
    return out;
  };

  // volumeFn(fixed) -> aggregated value across a column's month indices,
  // summed for volume, averaged for share.
  const columnValue = (fixed, col) => {
    const perMonth = col.indices.map((idx) => sumVolume(fixed, idx));
    if (!isPercent) return perMonth.reduce((a, b) => a + b, 0);
    return perMonth.reduce((a, b) => a + b, 0) / perMonth.length;
  };
  const parentColumnValue = (parentFixed, col) => {
    const perMonth = col.indices.map((idx) => sumVolume(parentFixed, idx));
    return perMonth.reduce((a, b) => a + b, 0) / (isPercent ? perMonth.length : 1);
  };

  const formatValue = (val) => (isPercent ? `${val.toFixed(1)}%` : Math.round(val).toLocaleString());

  const activeOrder = HIERARCHY_ORDERS.find((o) => o.value === hierarchyOrder) || HIERARCHY_ORDERS[0];
  const [dim1, dim2, dim3] = activeOrder.dims;
  const dimValues = { pt: paymentTypes, payer: subPayers, product: products };

  // Same highlighting convention as ModelInputTable's Payer/Product tab:
  // a row is highlighted only if every dimension already fixed on it (pt /
  // product — the mock Payer dimension isn't filterable) matches the
  // page's applied Payment Type / Product filter, cascading down so a leaf
  // only lights up once every ancestor level also matched.
  const currentPayer = (appliedPayerFilter || "").toLowerCase();
  const currentBrand = (appliedProductFilter || "").toLowerCase();
  const dimMatches = (dimKey, val) => {
    if (val === undefined) return true;
    if (dimKey === "pt") return !!currentPayer && val.toLowerCase() === currentPayer;
    if (dimKey === "product") return !!currentBrand && val.toLowerCase() === currentBrand;
    return true;
  };
  const isRowHighlighted = (row) => {
    if (!currentPayer && !currentBrand) return false;
    return (
      dimMatches(dim1, row.fixed[dim1]) &&
      dimMatches(dim2, row.fixed[dim2]) &&
      dimMatches(dim3, row.fixed[dim3])
    );
  };

  // Same highlight rule as isRowHighlighted, but for real backend rows where
  // we only have a label path (e.g. ["Commercial", "CVS", "ASGA"]) rather
  // than a { pt, payer, product } fixed map — matches if the applied payer
  // filter and/or applied product filter both appear somewhere on the path.
  const dimMatchesPath = (path) => {
    if (!currentPayer && !currentBrand) return false;
    const lower = path.map((p) => String(p || "").toLowerCase());
    const payerOk = !currentPayer || lower.some((p) => p === currentPayer || p.includes(currentPayer));
    const brandOk = !currentBrand || lower.some((p) => p === currentBrand || p.includes(currentBrand));
    return payerOk && brandOk;
  };

  // Row styling matches ModelInputTable's existing hasChildren/leaf convention
  // (background #f8fafc + #1e293b bold for parent rows, white + #334155 for
  // leaves) — only the left padding increases per hierarchy level. A matched
  // row switches to the app's shared "applied" amber highlight.
  const rowStyle = (level, highlighted) => ({
    backgroundColor: highlighted ? "#fffbeb" : level < 2 ? "#f8fafc" : "white",
    fontWeight: level === 0 ? 700 : level === 1 ? 600 : 500,
    color: highlighted ? "#f59e0b" : level < 2 ? "#1e293b" : "#334155",
  });
  const indentPx = (level) => (level === 0 ? "16px" : level === 1 ? "32px" : "56px");

  const rows = useRealData ? flattenRealRows(realTableSrc.rows) : [];
  if (!useRealData) {
    dimValues[dim1].forEach((v1) => {
      rows.push({ level: 0, label: v1, fixed: { [dim1]: v1 }, parentFixed: {} });
      dimValues[dim2].forEach((v2) => {
        rows.push({ level: 1, label: v2, fixed: { [dim1]: v1, [dim2]: v2 }, parentFixed: { [dim1]: v1 } });
        dimValues[dim3].forEach((v3) => {
          rows.push({
            level: 2,
            label: v3,
            fixed: { [dim1]: v1, [dim2]: v2, [dim3]: v3 },
            parentFixed: { [dim1]: v1, [dim2]: v2 },
          });
        });
      });
    });
  }

  // ── Chart: one line per top-level dimension value, full monthly resolution ──
  // Real data: the backend's chart.series only contains fully-flattened leaf
  // combinations (e.g. "Cash - ASGA", "Commercial - CVS - ASGA") — there's no
  // separate top-level-only series to filter for. Use the top-level (level 0)
  // rows of the MONTHLY table instead: each already carries the correctly
  // pre-aggregated total for that dim1 value across every month, independent
  // of the Monthly/Yearly toggle (chart always shows monthly resolution).
  const realMonthlyTable = realOrder?.table;
  const realChartMonths = realOrder?.chart?.months;
  const chartTraces = (() => {
    if (realMonthlyTable?.rows?.length && realChartMonths?.length) {
      const realLabels = realChartMonths.map(formatDateLabel);
      return realMonthlyTable.rows.map((r, idx) => {
        const label = r.label || r.hierarchy || "";
        const highlighted = dimMatchesPath([label]);
        const values = Array.isArray(r.total) ? r.total : r.values || [];
        return {
          x: realLabels,
          y: values,
          type: "scatter",
          mode: "lines",
          name: label,
          line: {
            color: highlighted ? "#f59e0b" : CHART_PALETTE[idx % CHART_PALETTE.length],
            width: highlighted ? 3.5 : 1.5,
          },
        };
      });
    }
    const chartLabels = monthLabels.map(formatDateLabel);
    return dimValues[dim1].map((v1, idx) => {
      const isHighlighted = isRowHighlighted({ fixed: { [dim1]: v1 } });
      const values = monthLabels.map((_, monthIdx) => {
        const val = sumVolume({ [dim1]: v1 }, monthIdx);
        if (!isPercent) return val;
        const total = sumVolume({}, monthIdx);
        return total ? (val / total) * 100 : 0;
      });
      return {
        x: chartLabels,
        y: values,
        type: "scatter",
        mode: "lines",
        name: v1,
        line: {
          color: isHighlighted ? "#f59e0b" : CHART_PALETTE[idx % CHART_PALETTE.length],
          width: isHighlighted ? 3.5 : 1.5,
        },
      };
    });
  })();

  // ── Toolbar button styles (matches ModelInputTable) ──────────────────
  const primaryBtnSx = {
    height: "35px",
    borderRadius: "8px",
    textTransform: "none",
    fontSize: "13px",
    fontWeight: 600,
    backgroundColor: "#4F46E5",
    "&:hover": { backgroundColor: "#4338ca" },
  };
  const secondaryBtnSx = {
    height: "35px",
    borderRadius: "8px",
    textTransform: "none",
    fontSize: "13px",
    fontWeight: 600,
    borderColor: "#e2e8f0",
    color: "#64748b",
    "&:hover": { borderColor: "#cbd5e1", backgroundColor: "#f8fafc" },
  };

  return (
    <Box>
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
          <Typography sx={{ fontWeight: 700, fontSize: "16px" }}>Market Analysis Chart</Typography>
        </AccordionSummary>
        <AccordionDetails sx={{ pt: 0, pb: 1, px: 1 }}>
          <Box sx={{ width: "100%", height: 380 }}>
            <PlotComponent
              data={chartTraces}
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
        </AccordionDetails>
      </Accordion>

      {/* Table section — Paper + toolbar convention matches ModelInputTable's
          standard tabs (border-radius 12px, toolbar border-bottom instead of
          a separate margin) so this tab looks consistent with the rest. */}
      <Paper sx={{ borderRadius: "12px", border: "1px solid #D8DEE8", boxShadow: "none", overflow: "hidden" }}>
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
          <Typography sx={{ fontSize: "16px", fontWeight: 700, color: "#1e293b" }}>{activeTabLabel}</Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, flexWrap: "wrap" }}>
            {/* Hierarchy Order dropdown — was previously missing from this
                tab; styling matches the 3-level dropdown used elsewhere. */}
            <FormControl size="small" sx={{ minWidth: 220 }}>
              <Select
                value={hierarchyOrder}
                onChange={(e) => setHierarchyOrder(e.target.value)}
                sx={{
                  height: "34px",
                  fontSize: "12px",
                  fontWeight: 600,
                  borderRadius: "8px",
                  backgroundColor: "#fcfcfd",
                }}
              >
                {HIERARCHY_ORDERS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value} sx={{ fontSize: "12px" }}>
                    Hierarchy: {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {filterOptions?.metric_filters?.length > 0 && (
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <Select
                value={metric}
                onChange={(e) => handleMetricChange(e.target.value)}
                sx={{ height: "34px", fontSize: "13px", fontWeight: 600, borderRadius: "8px", backgroundColor: "#fcfcfd" }}
              >
                {filterOptions.metric_filters.map((item) => (
                  <MenuItem key={item.value} value={item.value} sx={{ fontSize: "13px" }}>
                    {item.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          <Box sx={{ display: "flex", bgcolor: "#E2E8F0", borderRadius: "10px", p: "2px" }}>
            {["monthly", "yearly"].map((mode) => (
              <Box
                key={mode}
                onClick={() => {
                  if (mode === totalMarketViewMode) return;
                  setTotalMarketViewMode(mode);
                  if (mode === "yearly" && tableEditing) handleCancelTableEdit?.();
                }}
                sx={{
                  minWidth: 70,
                  textAlign: "center",
                  cursor: "pointer",
                  py: 0.5,
                  px: 1.5,
                  borderRadius: "8px",
                  fontSize: "12px",
                  fontWeight: 600,
                  bgcolor: totalMarketViewMode === mode ? "#fff" : "transparent",
                  color: totalMarketViewMode === mode ? "#4F46E5" : "#64748B",
                }}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </Box>
            ))}
          </Box>

          {/* Download / Save / Edit / Refresh / Cancel */}
          {handleDownloadTable && (
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
          )}

          {handleConfirmSave && (
            <Button
              variant="contained"
              disabled={(tableEditing && !isRefreshed) || isSavingEditChanges}
              onClick={handleConfirmSave}
              sx={primaryBtnSx}
            >
              Save
            </Button>
          )}

          {handleEnterTableEdit && (
            <Button
              variant="outlined"
              onClick={handleEnterTableEdit}
              disabled={tableEditing || !appliedScenarioReady}
              sx={secondaryBtnSx}
            >
              Edit Changes
            </Button>
          )}

          {tableEditing && handleSaveTableChanges && (
            <Button
              variant="contained"
              disabled={savingTable || Object.keys(editedHierarchies).length === 0}
              onClick={handleSaveTableChanges}
              sx={primaryBtnSx}
            >
              Refresh
            </Button>
          )}

          {tableEditing && handleCancelTableEdit && (
            <Button
              variant="outlined"
              onClick={handleCancelTableEdit}
              disabled={!tableEditing || totalMarketViewMode === "yearly"}
              sx={secondaryBtnSx}
            >
              Cancel
            </Button>
          )}
        </Box>
      </Box>

      {/* ── TABLE ── */}
      <Box
        sx={{
          backgroundColor: "white",
          maxHeight: 500,
          overflow: "auto",
        }}
      >
        <Box component="table" sx={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
          <Box component="thead">
            <Box component="tr">
              <Box
                component="th"
                sx={{
                  position: "sticky", left: 0, top: 0, zIndex: 3, backgroundColor: "#f8fafc", color: "#64748b",
                  fontWeight: 700, fontSize: "14px", textAlign: "left", p: "12px 16px", minWidth: 220, borderRight: "2px solid #e2e8f0", borderBottom: "2px solid #e2e8f0",
                }}
              >
                {DIM_LABELS[dim1]} / {DIM_LABELS[dim2]} / {DIM_LABELS[dim3]}
              </Box>
              {columns.map((col) => (
                <Box
                  key={col.label}
                  component="th"
                  sx={{
                    position: "sticky", top: 0, zIndex: 2, backgroundColor: "#f8fafc", color: "#64748b",
                    fontWeight: 700, fontSize: "14px", textAlign: "center", p: "12px 8px", minWidth: 90, borderRight: "1px solid #e2e8f0", borderBottom: "2px solid #e2e8f0",
                  }}
                >
                  {totalMarketViewMode === "yearly" ? col.label : formatDateLabel(col.label)}
                </Box>
              ))}
            </Box>
          </Box>
          <Box component="tbody">
            {rows.map((row, i) => {
              const highlighted = useRealData ? !!row.highlighted : isRowHighlighted(row);
              const style = rowStyle(row.level, highlighted);
              return (
                <Box component="tr" key={i} sx={{ borderBottom: "1px solid #e2e8f0" }}>
                  <Box
                    component="td"
                    sx={{
                      position: "sticky", left: 0, zIndex: 1, backgroundColor: style.backgroundColor,
                      fontWeight: style.fontWeight, fontSize: "14px", color: style.color, textAlign: "left",
                      p: "10px 16px", pl: indentPx(row.level), minWidth: 220, borderRight: "2px solid #e2e8f0",
                    }}
                  >
                    {row.label}
                  </Box>
                  {columns.map((col) => {
                    // Real data: the backend already computed the correctly
                    // scaled volume sum / share % for this row+column — use
                    // it directly instead of re-deriving from mock weights.
                    const displayVal = useRealData
                      ? Number(row.values?.[col.indices[0]] ?? 0)
                      : (() => {
                          const ownVal = columnValue(row.fixed, col);
                          const parentVal = row.level === 0 ? columnValue({}, col) : parentColumnValue(row.parentFixed, col);
                          return isPercent ? (parentVal ? (ownVal / parentVal) * 100 : 0) : ownVal;
                        })();
                    return (
                      <Box
                        key={col.label}
                        component="td"
                        sx={{
                          textAlign: "center", p: "10px 8px", fontSize: "14px", fontWeight: style.fontWeight,
                          color: style.color, backgroundColor: style.backgroundColor, borderRight: "1px solid #e2e8f0",
                        }}
                      >
                        {formatValue(displayVal)}
                      </Box>
                    );
                  })}
                </Box>
              );
            })}
          </Box>
        </Box>
      </Box>
      </Paper>
    </Box>
  );
}