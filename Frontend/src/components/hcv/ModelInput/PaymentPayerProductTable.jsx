import React, { useMemo, useState, useEffect, useRef } from "react";
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
  Checkbox,
  ListItemText,
  OutlinedInput,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DownloadIcon from "@mui/icons-material/Download";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
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

// Same scenario-color convention ModelInputChart uses for Compare
// Scenarios on the other tabs, so a scenario reads as the same color
// everywhere in the app.
const getScenarioColor = (index) => `hsl(${(index * 137.508) % 360}, 70%, 50%)`;

// Collects every row key that has children (used both to auto-expand the
// table on first load / whenever the Hierarchy Order or Monthly-Yearly
// toggle changes the underlying data, and by the "Expand All" toolbar
// button). Pure — depends only on its argument — so it lives outside the
// component and never needs to be in a useEffect/useMemo dependency array.
const collectParentKeys = (rowsIn, ancestorLabels = []) => {
  const keys = [];
  (rowsIn || []).forEach((r) => {
    const label = r.label || r.hierarchy || "";
    const path = [...ancestorLabels, label];
    if (r.children?.length) {
      keys.push(path.join(" > "));
      keys.push(...collectParentKeys(r.children, path));
    }
  });
  return keys;
};

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
  appliedSubPayerFilter,
  // Real backend data keyed by ordering (see ORDER_TO_BACKEND_KEY). Each
  // entry is { chart, table, yearlyChart, yearlyTable } — same shape every
  // other tab in this app uses. Falls back to the seeded mock below when a
  // given ordering has no real data.
  hierarchyData = {},
  // Compare Scenarios support for the chart: other selected scenarios'
  // full orders maps (see ModelInput's otherScenarioHierarchyData),
  // keyed by scenario name — { [scenarioName]: { [backendOrderKey]: {...} } }.
  otherScenarioHierarchyData = {},
  appliedScenario,
  selectedCompareScenarios = [],
  // Compare Scenarios dropdown — same control ModelInputTable renders in
  // its own toolbar, wired to the same shared handler/state in ModelInput
  // (selectedCompareScenarios is app-wide, not per-tab, so picking
  // scenarios here or on another tab affects both).
  compareScenarioOptions = [],
  handleCompareScenarioChange,
  // Toolbar action handlers (passed from ModelInput)
  handleDownloadTable,
  handleConfirmSave,
  handleEnterTableEdit,
  handleSaveTableChanges,
  handleCancelTableEdit,
  // Saves this tab's own edited cells (3-level hierarchy — doesn't fit the
  // shared tableData/editedHierarchies flow the standard tabs use). Falls
  // back to handleSaveTableChanges if not provided.
  onSaveHierarchyChanges,
  tableEditing,
  isRefreshed,
  savingTable,
  isSavingEditChanges,
  editedHierarchies = {},
  appliedScenarioReady,
  // Save Scenario — same dialog every other tab uses (state/dialog itself
  // lives in ModelInput.jsx and renders regardless of active tab).
  setNewScenarioName,
  setSaveScenarioDialogOpen,
}) {
  const [hierarchyOrder, setHierarchyOrder] = useState(HIERARCHY_ORDERS[0].value);
  // Collapsible rows — same convention as ModelInputTable's expandedBrands:
  // keyed map of { [rowKey]: true } for expanded rows. Starts expanded (see
  // the auto-expand effect below), not collapsed — the user can collapse
  // individual rows or hit "Collapse All" if they want a tighter view.
  const [expandedRows, setExpandedRows] = useState({});
  const toggleRowExpand = (key) =>
    setExpandedRows((prev) => ({ ...prev, [key]: !prev[key] }));

  // Local edit tracking — this tab's row/column shape (a real nested
  // hierarchy keyed by label path, not the flat "hierarchy" strings
  // ModelInputTable's tableData/editedHierarchies use) doesn't fit the
  // standard tabs' shared edit state, so edits are tracked here instead:
  // { [rowKey::colKey]: newNumericValue }. Cleared whenever edit mode is
  // (re-)entered.
  const [editedCells, setEditedCells] = useState({});
  const wasEditingRef = useRef(false);
  useEffect(() => {
    if (tableEditing && !wasEditingRef.current) {
      setEditedCells({});
    }
    wasEditingRef.current = tableEditing;
  }, [tableEditing]);

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
    const f = fixed || {};
    const pts = f.pt ? [f.pt] : paymentTypes;
    const payers = f.payer ? [f.payer] : subPayers;
    const prods = f.product ? [f.product] : products;
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
    // NOTE: backend yearly headers can legitimately repeat a year label
    // (e.g. "2023" appearing twice — once for the historical portion up to
    // forecast_start_index, once for the forecast portion of that same
    // year, with genuinely different values in each). `key` here is a
    // unique per-column identifier (index-based) separate from the display
    // `label`, so React never sees two columns with the same key — reusing
    // the duplicate label as the key was causing React's reconciliation to
    // misbehave across repeated Monthly/Yearly toggles (a stale extra
    // column would stick around instead of being replaced cleanly).
    if (realTableSrc?.headers?.length) {
      return realTableSrc.headers.map((label, idx) => ({ label, indices: [idx], key: `h-${idx}` }));
    }
    if (totalMarketViewMode !== "yearly") return monthLabels.map((label, idx) => ({ label, indices: [idx], key: `m-${idx}` }));
    const byYear = {};
    monthLabels.forEach((label, idx) => {
      const yr = yearOfLabel(label);
      if (!byYear[yr]) byYear[yr] = [];
      byYear[yr].push(idx);
    });
    return Object.entries(byYear).map(([yr, indices], idx) => ({ label: yr, indices, key: `y-${idx}` }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monthLabels, totalMarketViewMode, realTableSrc]);

  // Flattens the backend's nested table.rows (arbitrary depth, via
  // `children`) into the same flat row list this component renders,
  // carrying each row's own values array (already the correctly-scaled
  // volume/share numbers computed by the backend for that hierarchy level).
  // Collapsible: a row's children are only included in the output when the
  // row itself is expanded (same behavior as ModelInputTable's
  // expandedBrands), so collapsing a parent hides its whole subtree.
  // keyPrefix namespaces the expand/collapse keys — used when flattening
  // an OTHER (Compare Scenarios) scenario's rows, so collapsing/expanding
  // those doesn't collide with the applied scenario's own row keys.
  const flattenRealRows = (rowsIn, level = 0, ancestorLabels = [], keyPrefix = "") => {
    const out = [];
    // Some hierarchy orderings have a sibling that skips a level entirely
    // (e.g. "Cash" has no Payer breakdown, so under a given Product it sits
    // alongside "Commercial"/"Medicaid"/"Medicare" with zero children while
    // they each have CVS/Non CVS children). Basing bold weight purely on
    // that row's OWN hasChildren made Cash render as a plain leaf (400)
    // while its true siblings at the same level got the bolder "has more
    // depth below" weight (600) — visually inconsistent even though they're
    // meant to read as the same level. siblingsHaveChildren looks at
    // whether ANY row in this same sibling group has children, so the
    // whole group gets the same weight regardless of which individual
    // sibling happens to be a leaf.
    const siblingsHaveChildren = (rowsIn || []).some((r) => r.children && r.children.length);
    (rowsIn || []).forEach((r) => {
      const label = r.label || r.hierarchy || "";
      const path = [...ancestorLabels, label];
      const key = keyPrefix + path.join(" > ");
      const hasChildren = !!(r.children && r.children.length);
      const isExpanded = !!expandedRows[key];
      out.push({
        level,
        label,
        key,
        hasChildren,
        siblingsHaveChildren,
        isExpanded,
        values: Array.isArray(r.total) ? r.total : r.values || [],
        highlighted: dimMatchesPath(path),
      });
      if (hasChildren && isExpanded) {
        out.push(...flattenRealRows(r.children, level + 1, path, keyPrefix));
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

  // Expand All / Collapse All — same toolbar affordance ModelInputTable uses
  // for its own expandable tabs. Shared helper collects every expandable
  // key across all scenario groups currently being shown (the scenario
  // group key itself, plus every parent key within that scenario's tree,
  // namespaced the same way buildScenarioGroupRows/flattenRealRows are).
  const collectAllScenarioKeys = () => {
    if (!useRealData) return [];
    const keys = [];
    scenarioNamesToShow.forEach((name) => {
      const isApplied = name === appliedScenario;
      let scenarioTableForThis;
      if (isApplied) {
        scenarioTableForThis = realTableSrc;
      } else {
        const order = otherScenarioHierarchyData[name]?.[backendOrderKey];
        scenarioTableForThis = totalMarketViewMode === "yearly" ? order?.yearlyTable : order?.table;
      }
      if (!scenarioTableForThis?.rows?.length) return;
      const keyPrefix = isApplied ? "" : `${name}::`;
      keys.push(`${keyPrefix}__scenario__`);
      collectParentKeys(scenarioTableForThis.rows).forEach((k) => keys.push(keyPrefix + k));
    });
    return keys;
  };

  const handleExpandAllRows = () => {
    let parentKeys;
    if (useRealData) {
      parentKeys = collectAllScenarioKeys();
    } else {
      // Mock data: every level-0 and level-1 combination has children,
      // nested under the synthetic scenario group header.
      parentKeys = ["__scenario__"];
      dimValues[dim1].forEach((v1) => {
        parentKeys.push(`__scenario__ > ${v1}`);
        dimValues[dim2].forEach((v2) => parentKeys.push(`__scenario__ > ${v1} > ${v2}`));
      });
    }
    setExpandedRows(Object.fromEntries(parentKeys.map((k) => [k, true])));
  };
  const handleCollapseAllRows = () => setExpandedRows({});

  // Starts fully expanded on first load, and again whenever the Hierarchy
  // Order dropdown, Monthly/Yearly toggle, or Compare Scenarios selection
  // changes the underlying data — matching ModelInputTable's Payer/Product
  // tabs, which also default to expanded rather than collapsed. The user
  // can still collapse individual rows/scenario groups, or hit "Collapse
  // All", afterward; this only sets the starting point each time the data
  // changes.
  useEffect(() => {
    if (!useRealData) return;
    setExpandedRows(Object.fromEntries(collectAllScenarioKeys().map((k) => [k, true])));
  }, [backendOrderKey, totalMarketViewMode, useRealData, realTableSrc, selectedCompareScenarios, appliedScenario, otherScenarioHierarchyData]);

  // Same highlighting convention as ModelInputTable's Payer/Product tab:
  // a row is highlighted only if every dimension already fixed on it (pt /
  // payer / product) matches the page's applied Payment Type / Payer /
  // Product filter, cascading down so a leaf only lights up once every
  // ancestor level also matched.
  const currentPayer = (appliedPayerFilter || "").toLowerCase();
  const currentBrand = (appliedProductFilter || "").toLowerCase();
  const currentSubPayer = (appliedSubPayerFilter || "").toLowerCase();
  // True whenever ANY of the three filters is applied — same
  // isFilterFocusMode convention ModelInputChart uses on the other tabs to
  // decide whether to narrow the chart down to just the matching line(s)
  // instead of showing everything.
  const isFilterFocusMode = !!currentPayer || !!currentSubPayer || !!currentBrand;
  const dimMatches = (dimKey, val) => {
    if (val === undefined) return true;
    if (dimKey === "pt") return !!currentPayer && val.toLowerCase() === currentPayer;
    if (dimKey === "payer") return !!currentSubPayer && val.toLowerCase() === currentSubPayer;
    if (dimKey === "product") return !!currentBrand && val.toLowerCase() === currentBrand;
    return true;
  };
  const isRowHighlighted = (row) => {
    if (!isFilterFocusMode) return false;
    const fixed = row.fixed || {};
    return (
      dimMatches(dim1, fixed[dim1]) &&
      dimMatches(dim2, fixed[dim2]) &&
      dimMatches(dim3, fixed[dim3])
    );
  };

  // Same highlight rule as isRowHighlighted, but for real backend rows where
  // we only have a label path (e.g. ["Commercial", "CVS", "ASGA"]) rather
  // than a { pt, payer, product } fixed map.
  //
  // Matches ModelInputTable's actual convention (not just "same colors"):
  // a row highlights only once every dimension it has ALREADY REACHED
  // matches that dimension's applied filter, cascading down — a filter for
  // a dimension this row hasn't reached yet (e.g. a Product filter checked
  // against a Payment-Type-only parent row) doesn't block it, exactly like
  // ModelInputTable's parent row only checking its own single dimension
  // and leaving the child to check the next one once isAppliedParent is
  // true.
  //
  // Classifies each label in the path by VALUE (is it a known Payment
  // Type / CVS-Non CVS / Product name?) rather than by its POSITION in the
  // path. Position alone isn't reliable here: "Cash" has no Payer
  // breakdown, so in the Payment type-Payer-Product ordering, "Cash"'s
  // children are Products sitting at the path position that would
  // normally hold a Payer value for every other Payment Type. Classifying
  // by value naturally handles that regardless of which Hierarchy Order is
  // selected or which branch collapsed a level.
  const isPtValue = (v) =>
    paymentTypes.some((p) => String(p).toLowerCase() === String(v || "").toLowerCase());
  const isPayerFilterValue = (v) => {
    const s = String(v || "").toLowerCase();
    return s === "cvs" || s === "non cvs";
  };
  const isProductValue = (v) =>
    products.some((p) => String(p).toLowerCase() === String(v || "").toLowerCase());

  const pathMatchesAppliedFilters = (path) => {
    const lower = path.map((p) => String(p || "").toLowerCase());
    const reachedPt = lower.find(isPtValue);
    const reachedPayer = lower.find(isPayerFilterValue);
    const reachedProduct = lower.find(isProductValue);

    // Payment Type: only checked once this row's own pt value is known —
    // for every ordering, the very first label in any path is always a
    // Payment Type value, so this is effectively always "reached".
    if (currentPayer && reachedPt !== undefined && reachedPt !== currentPayer) return false;

    // Payer (CVS / Non CVS): checked once reached. "Cash" skips the Payer
    // level entirely, so a branch whose Payment Type is Cash can never
    // satisfy an applied Payer filter — that branch should NOT highlight,
    // not be treated as "not yet reached, so pass".
    if (currentSubPayer) {
      if (reachedPayer !== undefined) {
        if (reachedPayer !== currentSubPayer) return false;
      } else if (reachedPt === "cash") {
        return false;
      }
    }

    // Product: checked once reached; a row that hasn't drilled down to a
    // specific product yet (e.g. a Payment Type or Payer-level row) isn't
    // penalized for a Product filter it hasn't gotten to yet.
    if (currentBrand && reachedProduct !== undefined && reachedProduct !== currentBrand) return false;

    return true;
  };
  const dimMatchesPath = (path) => {
    if (!isFilterFocusMode) return false;
    return pathMatchesAppliedFilters(path);
  };

  // Chart-only variant of the filter check above. The chart only ever
  // plots the current Hierarchy Order's top TWO levels (dim1/dim2) — e.g.
  // "Payment type-Payer-Product" only shows Payment Type + Payer, never
  // Product. If a Product filter were checked against those 2-level paths
  // anyway, it would never find a match and the chart would go completely
  // blank even though the filtered data genuinely exists one level deeper
  // (visible in the table, just not chartable at this order — confirmed
  // e.g. filtering Payment Type=Commercial + Product=ASGA on that order:
  // "Commercial > CVS > ASGA" is real data, but neither "Commercial" nor
  // "CVS" contains "asga"). Filters on a dimension the chart can't
  // represent at the current order are ignored here instead of hiding
  // every line.
  const visibleChartDims = new Set([dim1, dim2]);
  const chartPathMatchesAppliedFilters = (path) => {
    const lower = path.map((p) => String(p || "").toLowerCase());
    const payerOk = !visibleChartDims.has("pt") || !currentPayer || lower.some((p) => p === currentPayer);
    const subPayerOk = !visibleChartDims.has("payer") || !currentSubPayer || lower.some((p) => p === currentSubPayer);
    const brandOk = !visibleChartDims.has("product") || !currentBrand || lower.some((p) => p === currentBrand);
    return payerOk && subPayerOk && brandOk;
  };

  // Row styling matches ModelInputTable's existing hasChildren/leaf convention
  // (background #f8fafc + #1e293b bold for parent rows, white + #334155 for
  // leaf children). The top level (level 0) is always bold (700).
  // Below level 0, two SEPARATE rules apply depending on how many siblings
  // a row has under its own parent (not on depth):
  //   - Single-child case: that one child is always plain/light (400) —
  //     never bold, since there's no sibling to visually rank it against.
  //   - Multi-child case (2+): only the FIRST child is bold, one step
  //     lighter than its parent (600); every other sibling stays light
  //     (400) — matching "first child bold-but-subordinate, rest plain".
  // Color still steps down per level too so the hierarchy stays readable.
  // Left padding increases by a full 48px per level — set via explicit pl
  // (not the "p" shorthand) so there's no ambiguity about which wins —
  // much larger than a single level's step in ModelInputTable, since this
  // tab goes one level deeper. A matched row switches to the app's shared
  // "applied" amber highlight regardless of level.
  const rowStyle = (level, highlighted, hasChildren) => {
    // Data under this tab isn't a uniform depth — some branches are only
    // 2 levels deep (e.g. "Cash" -> "ASGA"/"GILD"/"Other", straight to
    // leaves), others are 3 levels deep (e.g. "Commercial" -> "CVS"/"Non
    // CVS" -> "ASGA"/"GILD"/"Other"). The two cases get a different bold
    // falloff instead of one fixed rule per depth number:
    //   - 2-level branch: top (700) -> leaf (400). Two steps.
    //   - 3-level branch: top (700) -> intermediate parent (600, since
    //     "CVS"/"Non CVS" are themselves parents of something) -> leaf
    //     (400). Three steps.
    // `hasChildren` here is really "siblingsHaveChildren" (passed in by the
    // caller) rather than this exact row's own hasChildren — some rows
    // (e.g. "Cash" under a Product, in the Product-Payment type-Payer
    // ordering) have zero children of their own while their siblings under
    // the SAME parent (Commercial/Medicaid/Medicare) do have children.
    // Weighting purely on the individual row's own hasChildren made that
    // one sibling render as a plain leaf (400) while its peers at the same
    // visual level got 600 — inconsistent bolding across what should read
    // as one uniform row of siblings. Using "does ANY sibling in this group
    // have children" keeps the whole sibling group at the same weight.
    let fontWeight;
    if (level === 0) {
      // Scenario group header (e.g. "Base", "test2") — the outermost
      // wrapper, matching ModelInputTable's Product/Payment Type
      // Distribution convention of putting the scenario name itself at
      // the top, with the tab's own hierarchy nested underneath.
      fontWeight = 700;
    } else if (level === 1) {
      // Top of this tab's own hierarchy (e.g. "Cash"/"Commercial") — same
      // prominence it always had, just one level deeper now that the
      // scenario wrapper sits above it.
      fontWeight = 700;
    } else if (hasChildren) {
      fontWeight = 600;
    } else {
      fontWeight = 400;
    }
    return {
      backgroundColor: highlighted ? "#fffbeb" : level <= 1 ? "#f8fafc" : "white",
      fontWeight,
      color: highlighted ? "#f59e0b" : level <= 1 ? "#1e293b" : level === 2 ? "#334155" : "#64748b",
    };
  };
  const indentPx = (level) =>
    level === 0 ? "16px" : level === 1 ? "48px" : level === 2 ? "96px" : "144px";

  // Scenario group rows: matches ModelInputTable's Product/Payment Type
  // Distribution tables, where the SCENARIO itself (e.g. "Base", "test2")
  // is the top-level parent and the tab's own hierarchy is nested under
  // it — not a flat "(scenario)"-suffixed sibling row, which is what this
  // used to do. One group per scenario currently being shown (the applied
  // scenario plus any Compare Scenarios selections); each group's own row
  // is the sum of its top-level children, same aggregate convention
  // ModelInputTable uses for its scenario-group header row.
  const scenarioNamesToShow = (
    selectedCompareScenarios?.length ? selectedCompareScenarios : appliedScenario ? [appliedScenario] : []
  ).filter(Boolean);

  const buildScenarioGroupRows = (scenarioName) => {
    const isApplied = scenarioName === appliedScenario;
    let scenarioTableForThis;
    if (isApplied) {
      scenarioTableForThis = realTableSrc;
    } else {
      const order = otherScenarioHierarchyData[scenarioName]?.[backendOrderKey];
      scenarioTableForThis = totalMarketViewMode === "yearly" ? order?.yearlyTable : order?.table;
    }
    if (!scenarioTableForThis?.rows?.length) return [];

    const keyPrefix = isApplied ? "" : `${scenarioName}::`;
    const groupKey = `${keyPrefix}__scenario__`;
    const isGroupExpanded = !!expandedRows[groupKey];

    // Always compute the flattened content (needed for the group's own
    // aggregate row), but only include it in the rendered list when the
    // scenario group itself is expanded. Every row gets tagged with its
    // scenario (flattenRealRows itself doesn't know about scenarios) so
    // downstream logic — e.g. restricting cell editing to the applied
    // scenario's own rows — can tell them apart.
    const flatContent = flattenRealRows(scenarioTableForThis.rows, 1, [], keyPrefix).map((r) => ({
      ...r,
      scenario: scenarioName,
    }));
    const topChildren = flatContent.filter((r) => r.level === 1);
    const valuesLength = topChildren.reduce((max, c) => Math.max(max, c.values.length), 0);
    const groupValues = Array.from({ length: valuesLength }, (_, i) =>
      topChildren.reduce((sum, c) => sum + (Number(c.values?.[i]) || 0), 0),
    );

    const groupRow = {
      level: 0,
      label: scenarioName,
      key: groupKey,
      hasChildren: true,
      isExpanded: isGroupExpanded,
      values: groupValues,
      highlighted: false,
      scenario: scenarioName,
      isScenarioGroup: true,
    };

    return [groupRow, ...(isGroupExpanded ? flatContent : [])];
  };

  let rows = [];
  if (useRealData) {
    rows = scenarioNamesToShow.flatMap(buildScenarioGroupRows);
  } else {
    // Mock fallback: wrap the existing synthetic 3-level tree under a
    // single scenario header too, so the visual convention still matches
    // even without real backend data.
    const scenarioLabel = appliedScenario || "Base";
    const groupKey = "__scenario__";
    const isGroupExpanded = !!expandedRows[groupKey];
    rows.push({
      level: 0,
      label: scenarioLabel,
      key: groupKey,
      hasChildren: true,
      isExpanded: isGroupExpanded,
      scenario: scenarioLabel,
      isScenarioGroup: true,
    });
    if (isGroupExpanded) {
      dimValues[dim1].forEach((v1) => {
        const key1 = `${groupKey} > ${v1}`;
        const expanded1 = !!expandedRows[key1];
        rows.push({ level: 1, label: v1, key: key1, hasChildren: true, isExpanded: expanded1, fixed: { [dim1]: v1 }, parentFixed: {} });
        if (!expanded1) return;
        dimValues[dim2].forEach((v2) => {
          const key2 = `${key1} > ${v2}`;
          const expanded2 = !!expandedRows[key2];
          rows.push({ level: 2, label: v2, key: key2, hasChildren: true, isExpanded: expanded2, fixed: { [dim1]: v1, [dim2]: v2 }, parentFixed: { [dim1]: v1 } });
          if (!expanded2) return;
          dimValues[dim3].forEach((v3) => {
            rows.push({
              level: 3,
              label: v3,
              key: `${key2} > ${v3}`,
              hasChildren: false,
              fixed: { [dim1]: v1, [dim2]: v2, [dim3]: v3 },
              parentFixed: { [dim1]: v1, [dim2]: v2 },
            });
          });
        });
      });
    }
  }


  // ── Chart: one line per direct-child combination ────────────────────────
  // Real data: the backend's chart.series only contains fully-flattened leaf
  // combinations (e.g. "Cash - ASGA", "Commercial - CVS - ASGA") — there's no
  // separate top-level-only series to filter for. Use the table instead:
  // each row already carries the correctly pre-aggregated total for that
  // path across every column. Plots the "Parent - Child" combination line
  // for each of level 0's direct children (e.g. "Cash - ASGA", "Commercial -
  // CVS") — never the bare parent-only line, since that's just the sum of
  // those children and would duplicate the same shape as an extra,
  // unlabeled line. A row with no children at all is plotted on its own,
  // using just its own label. Level 2+ stays table-only to avoid
  // overcrowding the chart with too many lines.
  // Switches between monthly/yearly chart+table together with the
  // Monthly/Yearly toggle (realTableSrc above already does this for the
  // table; the chart previously stayed hardcoded to monthly regardless of
  // the toggle — this mirrors ModelInputChart/ModelInputTable, which both
  // switch chart data on totalMarketViewMode too).
  const activeChartForOrder = totalMarketViewMode === "yearly" ? realOrder?.yearlyChart : realOrder?.chart;
  const activeTableForChart = totalMarketViewMode === "yearly" ? realOrder?.yearlyTable : realOrder?.table;
  const chartMonths = activeChartForOrder?.months;
  const chartFsi = activeChartForOrder?.forecast_start_index ?? 0;
  const chartTraces = (() => {
    if (activeTableForChart?.rows?.length && chartMonths?.length) {
      // Yearly months are already plain year strings ("2023") — formatting
      // them through formatDateLabel (which assumes a real date and always
      // outputs "MMM-YY") turned "2023" into "Jan-23". Only monthly labels
      // need that MMM-YY formatting; yearly labels are used as-is, matching
      // the table header's same totalMarketViewMode check just below.
      const realLabels = totalMarketViewMode === "yearly" ? chartMonths : chartMonths.map(formatDateLabel);

      // One line per (parent's) direct child ("Parent - Child" combination),
      // never the bare parent-only line by itself. A parent row with
      // children (e.g. "Cash" -> "ASGA"/"GILD"/"Other") is really just the
      // sum of those children — plotting it as its own separate line
      // duplicated that same shape/trend as an extra, label-less "Cash"
      // line sitting alongside "Cash - ASGA" etc., which read as if there
      // were two unrelated "Cash" values. Only rows with NO children at all
      // (true leaves at this table's top level) get plotted on their own,
      // using their own label with no " - " suffix.
      const buildLineDefsFromTable = (tableObj) => {
        const out = [];
        (tableObj?.rows || []).forEach((r) => {
          const parentLabel = r.label || r.hierarchy || "";
          const children = r.children || [];
          if (!children.length) {
            out.push({
              label: parentLabel,
              path: [parentLabel],
              values: Array.isArray(r.total) ? r.total : r.values || [],
            });
            return;
          }
          children.forEach((c) => {
            const childLabel = c.label || c.hierarchy || "";
            out.push({
              label: `${parentLabel} - ${childLabel}`,
              path: [parentLabel, childLabel],
              values: Array.isArray(c.total) ? c.total : c.values || [],
            });
          });
        });
        return out;
      };
      const lineDefs = buildLineDefsFromTable(activeTableForChart);

      // Compare Scenarios: this tab previously had no scenario-comparison
      // support at all in its chart (unlike every other tab), so switching
      // on another scenario never showed anything for it here. Add each
      // OTHER selected scenario's equivalent lines for the SAME hierarchy
      // ordering currently selected, tagged with the scenario name so they
      // get their own color (matching ModelInputChart's convention) and
      // label suffix instead of being mistaken for the applied scenario's
      // own lines.
      const otherScenarioNames = (selectedCompareScenarios || []).filter(
        (name) => name && name !== appliedScenario,
      );
      const scenarioColorMap = {};
      otherScenarioNames.forEach((name, idx) => {
        scenarioColorMap[name] = getScenarioColor(idx);
      });
      const otherScenarioLineDefs = [];
      otherScenarioNames.forEach((name) => {
        const scenarioOrders = otherScenarioHierarchyData[name];
        const scenarioOrder = scenarioOrders && scenarioOrders[backendOrderKey];
        if (!scenarioOrder) return;
        const scenarioTable = totalMarketViewMode === "yearly" ? scenarioOrder.yearlyTable : scenarioOrder.table;
        buildLineDefsFromTable(scenarioTable).forEach((ld) => {
          otherScenarioLineDefs.push({ ...ld, scenario: name });
        });
      });
      const allLineDefs = [...lineDefs, ...otherScenarioLineDefs];

      // Once a Payment Type / Payer / Product filter is applied, narrow the
      // chart down to only the line(s) that actually match it — same
      // "isFilterFocusMode" behavior ModelInputChart applies on the other
      // tabs (a filtered view showing every line was confusing: the filter
      // looked like it only did highlighting instead of actually
      // narrowing what's plotted).
      const visibleLineDefs = isFilterFocusMode
        ? allLineDefs.filter(({ path }) => chartPathMatchesAppliedFilters(path))
        : allLineDefs;

      // Split each row's combined values into a solid "train" segment and a
      // dotted "forecast" segment (forecast segment starts one point early,
      // at the last train point, so the two lines connect visually) — same
      // convention ModelInputChart uses for every other tab's forecast line.
      return visibleLineDefs.flatMap(({ label, path, values, scenario }, idx) => {
        const highlighted = dimMatchesPath(path);
        // Other-scenario lines get their scenario's color (and a "(Scenario)"
        // suffix on the name) instead of the default palette, matching
        // ModelInputChart's convention — a highlighted match still wins
        // (amber) regardless of which scenario it came from.
        const color = highlighted
          ? "#f59e0b"
          : scenario && scenarioColorMap[scenario]
            ? scenarioColorMap[scenario]
            : CHART_PALETTE[idx % CHART_PALETTE.length];
        const width = highlighted ? 3.5 : 1.5;
        const traceName = scenario ? `${label} (${scenario})` : label;

        const trainX = realLabels.slice(0, chartFsi);
        const trainY = values.slice(0, chartFsi);
        const forecastX = chartFsi > 0 ? [realLabels[chartFsi - 1], ...realLabels.slice(chartFsi)] : realLabels.slice(chartFsi);
        const lastTrain = trainY.length ? trainY[trainY.length - 1] : null;
        const forecastY = chartFsi > 0 ? [lastTrain ?? null, ...values.slice(chartFsi)] : values.slice(chartFsi);

        return [
          {
            x: trainX,
            y: trainY,
            type: "scatter",
            mode: "lines",
            name: traceName,
            legendgroup: traceName,
            line: { color, width },
          },
          {
            x: forecastX,
            y: forecastY,
            type: "scatter",
            mode: "lines",
            name: traceName,
            legendgroup: traceName,
            showlegend: false,
            line: { color, width, dash: "dot" },
          },
        ];
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

  // See the `revision` prop on PlotComponent below — forces react-plotly.js
  // to fully re-diff against the latest chartTraces whenever something that
  // can change which lines exist or what they contain actually changes
  // (Hierarchy Order, Monthly/Yearly, which scenarios are being compared,
  // the applied scenario, the metric, or any of the three filters).
  // Deliberately NOT bumped on every render — react-plotly already handles
  // most `data` prop changes on its own, and constantly forcing a redraw
  // (once per render) risks the opposite problem: Plotly re-processing a
  // trace list mid-transition, right as a new scenario's traces are being
  // added, and settling on an incomplete one — which looks exactly like
  // "only one scenario shows at a time" right after toggling Compare
  // Scenarios. Keying revision off the actual inputs avoids that.
  const chartRevision = useMemo(
    () =>
      JSON.stringify({
        order: hierarchyOrder,
        mode: totalMarketViewMode,
        scenarios: (selectedCompareScenarios || []).slice().sort(),
        applied: appliedScenario,
        metric,
        payer: appliedPayerFilter,
        product: appliedProductFilter,
        subPayer: appliedSubPayerFilter,
      }),
    [
      hierarchyOrder,
      totalMarketViewMode,
      selectedCompareScenarios,
      appliedScenario,
      metric,
      appliedPayerFilter,
      appliedProductFilter,
      appliedSubPayerFilter,
    ],
  );

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
              // react-plotly.js can keep a stale internal trace list across
              // renders when the trace COUNT/shape changes (e.g. going from
              // no data / mock fallback to real backend traces, or the
              // number of Compare Scenarios lines changing) — it doesn't
              // always fully repaint every line's geometry even though the
              // `data` prop did change, which showed up as a legend entry
              // appearing with no visible line underneath it. `revision`
              // (react-plotly's documented escape hatch for this) forces a
              // full redraw whenever anything that can change which lines
              // exist or what they contain changes.
              revision={chartRevision}
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
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Typography sx={{ fontSize: "16px", fontWeight: 700, color: "#1e293b" }}>{activeTabLabel}</Typography>

            {setSaveScenarioDialogOpen && (
              <Button
                variant="contained"
                onClick={() => {
                  setNewScenarioName?.("");
                  setSaveScenarioDialogOpen(true);
                }}
                sx={primaryBtnSx}
              >
                Save Scenario
              </Button>
            )}

            {/* Expand All / Collapse All — same affordance ModelInputTable
                uses for its own expandable tabs. */}
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
          </Box>
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

            {/* Compare Scenarios — identical control to ModelInputTable's
                own toolbar (same options list, same handler, same shared
                selectedCompareScenarios state), so picking scenarios here
                behaves exactly the way it does on every other tab. */}
            {compareScenarioOptions.length > 1 && handleCompareScenarioChange && (
              <FormControl sx={{ minWidth: 220, maxWidth: 220 }}>
                <Select
                  multiple
                  displayEmpty
                  value={selectedCompareScenarios}
                  onChange={handleCompareScenarioChange}
                  input={<OutlinedInput />}
                  sx={{
                    height: "34px",
                    fontSize: "13px",
                    borderRadius: "8px",
                    backgroundColor: "#fcfcfd",
                    "& .MuiSelect-select": {
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    },
                  }}
                  MenuProps={{ PaperProps: { sx: { maxHeight: 260 } } }}
                  renderValue={(selected) => {
                    if (!selected.length) return "Compare Scenarios";
                    if (selected.length === compareScenarioOptions.length) return "All Scenarios";
                    return selected.join(", ");
                  }}
                >
                  {compareScenarioOptions.map((option) => {
                    const isActive = option === appliedScenario;
                    return (
                      <MenuItem key={option} value={option} disabled={isActive}>
                        <Checkbox size="small" checked={selectedCompareScenarios.includes(option)} disabled={isActive} />
                        <ListItemText primary={isActive ? `${option} (Active)` : option} />
                      </MenuItem>
                    );
                  })}
                </Select>
              </FormControl>
            )}

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
              // Editing is only meaningful in Market Share view — disabled
              // in Market Volume so users can't edit raw volume cells here.
              disabled={tableEditing || !appliedScenarioReady || metric === "market_volume"}
              sx={secondaryBtnSx}
            >
              Edit Changes
            </Button>
          )}

          {tableEditing && (onSaveHierarchyChanges || handleSaveTableChanges) && (
            <Button
              variant="contained"
              disabled={savingTable || Object.keys(editedCells).length === 0}
              onClick={() => {
                if (onSaveHierarchyChanges) {
                  onSaveHierarchyChanges({
                    editedCells,
                    backendOrderKey,
                    columns,
                    rows,
                  });
                } else {
                  handleSaveTableChanges();
                }
              }}
              sx={primaryBtnSx}
            >
              Refresh
            </Button>
          )}

          {tableEditing && handleCancelTableEdit && (
            <Button
              variant="outlined"
              onClick={() => {
                setEditedCells({});
                handleCancelTableEdit();
              }}
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
                Scenario / {DIM_LABELS[dim1]} / {DIM_LABELS[dim2]} / {DIM_LABELS[dim3]}
              </Box>
              {columns.map((col) => (
                <Box
                  key={col.key}
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
              const style = rowStyle(row.level, highlighted, row.siblingsHaveChildren ?? row.hasChildren);
              return (
                <Box
                  component="tr"
                  key={row.key ?? i}
                  onClick={() => {
                    if (row.hasChildren) toggleRowExpand(row.key);
                  }}
                  sx={{
                    borderBottom: "1px solid #e2e8f0",
                    cursor: row.hasChildren ? "pointer" : "default",
                    "&:hover": row.hasChildren ? { backgroundColor: highlighted ? "#fff3c4" : "#f1f5f9" } : undefined,
                  }}
                >
                  <Box
                    component="td"
                    sx={{
                      position: "sticky", left: 0, zIndex: 1, backgroundColor: style.backgroundColor,
                      fontWeight: style.fontWeight, fontSize: "14px", color: style.color, textAlign: "left",
                      pt: "10px", pb: "10px", pr: "16px", pl: indentPx(row.level), minWidth: 220, borderRight: "2px solid #e2e8f0",
                    }}
                  >
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      {row.hasChildren && (
                        <Typography
                          component="span"
                          sx={{
                            fontSize: "9px",
                            fontWeight: 700,
                            width: "14px",
                            flexShrink: 0,
                            color: highlighted ? "#f59e0b" : "#64748b",
                          }}
                        >
                          {row.isExpanded ? "▼" : "▶"}
                        </Typography>
                      )}
                      <Typography sx={{ fontSize: "14px", fontWeight: style.fontWeight, color: style.color }}>
                        {row.label}
                      </Typography>
                    </Box>
                  </Box>
                  {columns.map((col) => {
                    // Real data: the backend already computed the correctly
                    // scaled volume sum / share % for this row+column — use
                    // it directly instead of re-deriving from mock weights.
                    const displayVal = useRealData
                      ? Number(row.values?.[col.indices[0]] ?? 0)
                      : (() => {
                          // The scenario-group header row (level 0) has no
                          // .fixed at all — it's a pure grouping label, not
                          // a real dimension combination — so both it and
                          // level 1 (the actual top of this tab's own
                          // hierarchy) fall back to the grand total ({})
                          // for their own value/parent reference, same as
                          // this always worked before the scenario wrapper
                          // was added (just shifted from level 0 to <= 1).
                          const fixed = row.fixed || {};
                          const ownVal = columnValue(fixed, col);
                          const parentVal = row.level <= 1 ? columnValue({}, col) : parentColumnValue(row.parentFixed || {}, col);
                          return isPercent ? (parentVal ? (ownVal / parentVal) * 100 : 0) : ownVal;
                        })();

                    // Same eligibility rule ModelInputTable uses (isEditEligible):
                    // edit mode on, monthly view only, leaf rows only. Real
                    // data only — the mock fallback has no backend row to
                    // patch values into on save. Also restricted to the
                    // applied scenario's own rows — handleSaveHierarchyTableChanges
                    // only ever patches the applied scenario's raw data, so
                    // editing a comparison scenario's cells would silently
                    // go nowhere.
                    const isEditableCell =
                      tableEditing &&
                      totalMarketViewMode === "monthly" &&
                      useRealData &&
                      !row.hasChildren &&
                      (!row.scenario || row.scenario === appliedScenario);
                    const cellKey = `${row.key}::${col.key}`;
                    const editedVal = editedCells[cellKey];
                    const shownVal = editedVal !== undefined ? editedVal : displayVal;

                    return (
                      <Box
                        key={col.key}
                        component="td"
                        onClick={(e) => isEditableCell && e.stopPropagation()}
                        sx={{
                          textAlign: "center",
                          p: isEditableCell ? "4px 3px" : "10px 8px",
                          fontSize: "14px",
                          fontWeight: style.fontWeight,
                          color: style.color,
                          backgroundColor: isEditableCell ? "#eff6ff" : style.backgroundColor,
                          borderRight: "1px solid #e2e8f0",
                        }}
                      >
                        {isEditableCell ? (
                          <input
                            value={editedVal !== undefined ? editedVal : String(Math.round(Number(shownVal)))}
                            onChange={(e) => {
                              if (!/^-?\d*\.?\d*$/.test(e.target.value)) return;
                              setEditedCells((prev) => ({ ...prev, [cellKey]: e.target.value }));
                            }}
                            style={{
                              width: "72px",
                              height: "22px",
                              boxSizing: "border-box",
                              border: "1px solid #93c5fd",
                              borderRadius: "4px",
                              outline: "none",
                              background: "#eff6ff",
                              color: "#1e293b",
                              textAlign: "center",
                              fontSize: "12px",
                              padding: "1px 4px",
                            }}
                          />
                        ) : (
                          formatValue(shownVal)
                        )}
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