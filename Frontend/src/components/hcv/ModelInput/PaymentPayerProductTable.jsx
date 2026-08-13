import React, { useMemo, useState, useEffect, useLayoutEffect, useRef } from "react";
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

const DEFAULT_PAYERS = ["Commercial", "Medicare", "Medicaid", "Cash"];

const HIERARCHY_ORDERS = [
  { value: "pt-payer-product", label: "Payment type-Payer-Product", dims: ["pt", "payer", "product"] },
  { value: "pt-product-payer", label: "Payment type-Product-Payer", dims: ["pt", "product", "payer"] },
  { value: "product-pt-payer", label: "Product-Payment type-Payer", dims: ["product", "pt", "payer"] },
];

const ORDER_TO_BACKEND_KEY = {
  "pt-payer-product": "payment_type_payer_product",
  "pt-product-payer": "payment_type_product_payer",
  "product-pt-payer": "product_payment_type_payer",
};

const DIM_LABELS = { pt: "Payment Type", payer: "Payer", product: "Product" };

const DATE_INPUT_FORMATS = ["MMM-YY", "YYYY-MM", "YYYY-MM-DD", "YYYY-MM-DDTHH:mm:ssZ"];
const formatDateLabel = (s) => {
  const parsed = dayjs(s, DATE_INPUT_FORMATS, true);
  const p = parsed.isValid() ? parsed : dayjs(s);
  return p.isValid() ? p.format("MMM-YY") : s;
};

const seededRandom = (seedStr) => {
  let h = 0;
  for (let i = 0; i < seedStr.length; i++) h = (h * 31 + seedStr.charCodeAt(i)) | 0;
  const x = Math.sin(h) * 10000;
  return x - Math.floor(x);
};

const CHART_PALETTE = ["#4F46E5", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#06b6d4", "#3b82f6", "#ef4444"];

const getScenarioColor = (index) => `hsl(${(index * 137.508) % 360}, 70%, 50%)`;

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
  hierarchyData = {},
  otherScenarioHierarchyData = {},
  appliedScenario,
  selectedCompareScenarios = [],
  compareScenarioOptions = [],
  handleCompareScenarioChange,
  handleDownloadTable,
  handleConfirmSave,
  handleEnterTableEdit,
  handleSaveTableChanges,
  handleCancelTableEdit,
  onSaveHierarchyChanges,
  tableEditing,
  isRefreshed,
  savingTable,
  isSavingEditChanges,
  editedHierarchies = {},
  appliedScenarioReady,
  setNewScenarioName,
  setSaveScenarioDialogOpen,
  expandedRows = {},
  setExpandedRows,
  hierarchyOrder = HIERARCHY_ORDERS[0].value,
  setHierarchyOrder,
  tableScrollPosition,
  onTableScroll,
}) {
  const tableContainerRef = useRef(null);

  useLayoutEffect(() => {
    if (tableContainerRef.current && tableScrollPosition) {
      tableContainerRef.current.scrollTop = tableScrollPosition.scrollTop || 0;
      tableContainerRef.current.scrollLeft = tableScrollPosition.scrollLeft || 0;
    }
  }, [tableScrollPosition]);

  const handleContainerScroll = (e) => {
    if (onTableScroll) {
      onTableScroll({
        scrollTop: e.target.scrollTop,
        scrollLeft: e.target.scrollLeft,
      });
    }
  };

  const toggleRowExpand = (key) =>
    setExpandedRows((prev) => ({ ...prev, [key]: !prev[key] }));

  const [editedCells, setEditedCells] = useState({});
  const wasEditingRef = useRef(false);
  useEffect(() => {
    if (tableEditing !== wasEditingRef.current) {
      // Clear on both entering AND exiting edit mode. Entering: start fresh.
      // Exiting (after Refresh or Cancel): stale string values left in
      // editedCells would otherwise get rendered as shownVal in the now
      // read-only cells and crash formatValue, which expects a number.
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
    [monthsKey],
  );

  const paymentTypesKey = paymentTypes.join("|");
  const productsKey = products.join("|");

  const handleLocalDownloadTable = () => {
    try {
      const isYearly = totalMarketViewMode === "yearly";
      
      const formattedHeaders = columns.map((col) =>
        isYearly ? col.label : formatDateLabel(col.label)
      );
      const headerRow = ["Hierarchy Path", ...formattedHeaders];
      const csvRows = [headerRow];

      (rows || []).forEach((row) => {
        const labelPath = row.key ? row.key.replace(/__scenario__ > /g, "").replace(/::/g, " - ") : row.label;
        
        const rowValues = columns.map((col) => {
          const displayVal = useRealData
            ? Number(row.values?.[col.indices[0]] ?? 0)
            : (() => {
                const fixed = row.fixed || {};
                const ownVal = columnValue(fixed, col);
                const parentVal = row.level <= 1 ? columnValue({}, col) : parentColumnValue(row.parentFixed || {}, col);
                return isPercent ? (parentVal ? (ownVal / parentVal) * 100 : 0) : ownVal;
              })();

          return formatValue(displayVal);
        });

        csvRows.push([labelPath, ...rowValues]);
      });

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
    } catch (err) {
      console.error("Failed to download CSV from PaymentPayerProductTable:", err);
    }
  };

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
  }, [paymentTypesKey, productsKey]);

  const monthlyTotal = (monthIdx) => 8000 + monthIdx * 40 + seededRandom(`vol|${monthIdx}`) * 500;

  const leafVolume = (pt, payer, product, monthIdx) =>
    monthlyTotal(monthIdx) * ptWeights[pt] * payerWeights[payer] * (productShareMap[pt][payer][product] / 100);

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

  const yearOfLabel = (label) => "20" + String(label).split("-")[1];

  const isPercent = metric === "market_share";

  const backendOrderKey = ORDER_TO_BACKEND_KEY[hierarchyOrder];
  
  // SAFE NAVIGATION: Safeguard realOrder against undefined orders object
  const realOrder = hierarchyData && (hierarchyData[backendOrderKey] || hierarchyData[Object.keys(hierarchyData)[0]]);
  const realTableSrc = realOrder
    ? (totalMarketViewMode === "yearly" ? realOrder.yearlyTable : realOrder.table)
    : null;
  const useRealData = !!(realTableSrc && realTableSrc.rows && realTableSrc.rows.length);

  const columns = useMemo(() => {
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
  }, [monthLabels, totalMarketViewMode, realTableSrc]);

  const flattenRealRows = (rowsIn, level = 0, ancestorLabels = [], keyPrefix = "") => {
    const out = [];
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

  const columnValue = (fixed, col) => {
    const perMonth = col.indices.map((idx) => sumVolume(fixed, idx));
    if (!isPercent) return perMonth.reduce((a, b) => a + b, 0);
    return perMonth.reduce((a, b) => a + b, 0) / perMonth.length;
  };
  const parentColumnValue = (parentFixed, col) => {
    const perMonth = col.indices.map((idx) => sumVolume(parentFixed, idx));
    return perMonth.reduce((a, b) => a + b, 0) / (isPercent ? perMonth.length : 1);
  };

  const formatValue = (val) => {
    const n = Number(val);
    const safe = Number.isFinite(n) ? n : 0;
    return isPercent ? `${safe.toFixed(1)}%` : Math.round(safe).toLocaleString();
  };

  const activeOrder = HIERARCHY_ORDERS.find((o) => o.value === hierarchyOrder) || HIERARCHY_ORDERS[0];
  const [dim1, dim2, dim3] = activeOrder.dims;
  const dimValues = { pt: paymentTypes, payer: subPayers, product: products };

  const collectAllScenarioKeys = () => {
    if (!useRealData) return [];
    const keys = [];
    scenarioNamesToShow.forEach((name) => {
      const isApplied = name === appliedScenario;
      let scenarioTableForThis;
      if (isApplied) {
        scenarioTableForThis = realTableSrc;
      } else {
        const order = otherScenarioHierarchyData[name]?.[backendOrderKey] || otherScenarioHierarchyData[name]?.[Object.keys(otherScenarioHierarchyData[name] || {})[0]];
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
      parentKeys = ["__scenario__"];
      dimValues[dim1].forEach((v1) => {
        parentKeys.push(`__scenario__ > ${v1}`);
        dimValues[dim2].forEach((v2) => parentKeys.push(`__scenario__ > ${v1} > ${v2}`));
      });
    }
    setExpandedRows(Object.fromEntries(parentKeys.map((k) => [k, true])));
  };
  const handleCollapseAllRows = () => setExpandedRows({});

  useEffect(() => {
    if (!useRealData) return;
    if (Object.keys(expandedRows).length === 0) {
      setExpandedRows(Object.fromEntries(collectAllScenarioKeys().map((k) => [k, true])));
    }
  }, [backendOrderKey, totalMarketViewMode, useRealData, realTableSrc, selectedCompareScenarios, appliedScenario, otherScenarioHierarchyData]);

  const currentPayer = (appliedPayerFilter || "").toLowerCase();
  const currentBrand = (appliedProductFilter || "").toLowerCase();
  const currentSubPayer = (appliedSubPayerFilter || "").toLowerCase();
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

    if (currentPayer && reachedPt !== undefined && reachedPt !== currentPayer) return false;

    if (currentSubPayer) {
      if (reachedPayer !== undefined) {
        if (reachedPayer !== currentSubPayer) return false;
      } else if (reachedPt === "cash") {
        return false;
      }
    }

    if (currentBrand && reachedProduct !== undefined && reachedProduct !== currentBrand) return false;

    return true;
  };
  const dimMatchesPath = (path) => {
    if (!isFilterFocusMode) return false;
    return pathMatchesAppliedFilters(path);
  };

  const visibleChartDims = new Set([dim1, dim2]);
  const chartPathMatchesAppliedFilters = (path) => {
    const lower = path.map((p) => String(p || "").toLowerCase());
    const payerOk = !visibleChartDims.has("pt") || !currentPayer || lower.some((p) => p === currentPayer);
    const subPayerOk = !visibleChartDims.has("payer") || !currentSubPayer || lower.some((p) => p === currentSubPayer);
    const brandOk = !visibleChartDims.has("product") || !currentBrand || lower.some((p) => p === currentBrand);
    return payerOk && subPayerOk && brandOk;
  };

  const rowStyle = (level, highlighted, hasChildren, isCvsLevel) => {
    let fontWeight;
    if (level === 0) {
      fontWeight = 700;
    } else if (level === 1) {
      fontWeight = 700;
    } else if (tableEditing && isCvsLevel) {
      // In edit mode, make the CVS / Non CVS row stand out as bold,
      // regardless of which level of the tree it happens to sit at.
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

  const indentPx = (level) => {
    switch (level) {
      case 0:
        return "16px";
      case 1:
        return "48px";
      case 2:
        return "80px";
      case 3:
        return "112px";
      default:
        return `${16 + level * 32}px`;
    }
  };

  const scenarioNamesToShow = (
    selectedCompareScenarios?.length ? selectedCompareScenarios : appliedScenario ? [appliedScenario] : []
  ).filter(Boolean);

  const buildScenarioGroupRows = (scenarioName) => {
    const isApplied = scenarioName === appliedScenario;
    let scenarioTableForThis;
    if (isApplied) {
      scenarioTableForThis = realTableSrc;
    } else {
      const order = otherScenarioHierarchyData[scenarioName]?.[backendOrderKey] || otherScenarioHierarchyData[scenarioName]?.[Object.keys(otherScenarioHierarchyData[scenarioName] || {})[0]];
      scenarioTableForThis = totalMarketViewMode === "yearly" ? order?.yearlyTable : order?.table;
    }
    if (!scenarioTableForThis?.rows?.length) return [];

    const keyPrefix = isApplied ? "" : `${scenarioName}::`;
    const groupKey = `${keyPrefix}__scenario__`;
    const isGroupExpanded = !!expandedRows[groupKey];

    const flatContent = flattenRealRows(scenarioTableForThis.rows, 1, [], keyPrefix).map((r) => ({
      ...r,
      scenario: scenarioName,
    }));
    const topChildren = flatContent.filter((r) => r.level === 1);
    const valuesLength = topChildren.reduce((max, c) => Math.max(max, c.values.length), 0);
    const groupValues = Array.from({ length: valuesLength }, (_, i) =>
      isPercent
        ? 100
        : topChildren.reduce((sum, c) => sum + (Number(c.values?.[i]) || 0), 0),
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

  const activeChartForOrder = totalMarketViewMode === "yearly" ? realOrder?.yearlyChart : realOrder?.chart;
  const activeTableForChart = totalMarketViewMode === "yearly" ? realOrder?.yearlyTable : realOrder?.table;
  const chartMonths = activeChartForOrder?.months;
  const chartFsi = activeChartForOrder?.forecast_start_index ?? 0;
  
  const chartTraces = (() => {
    if (activeTableForChart?.rows?.length && chartMonths?.length) {
      const realLabels = totalMarketViewMode === "yearly" ? chartMonths : chartMonths.map(formatDateLabel);

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
        const scenarioOrder = scenarioOrders && (scenarioOrders[backendOrderKey] || scenarioOrders[Object.keys(scenarioOrders)[0]]);
        if (!scenarioOrder) return;
        const scenarioTable = totalMarketViewMode === "yearly" ? scenarioOrder.yearlyTable : scenarioOrder.table;
        buildLineDefsFromTable(scenarioTable).forEach((ld) => {
          otherScenarioLineDefs.push({ ...ld, scenario: name });
        });
      });
      const allLineDefs = [...lineDefs, ...otherScenarioLineDefs];

      const visibleLineDefs = isFilterFocusMode
        ? allLineDefs.filter(({ path }) => chartPathMatchesAppliedFilters(path))
        : allLineDefs;

      return visibleLineDefs.flatMap(({ label, path, values, scenario }, lineIndex) => {
        const highlighted = dimMatchesPath(path);
        
        const color = highlighted
          ? "#f59e0b"
          : scenario && scenarioColorMap[scenario]
            ? scenarioColorMap[scenario]
            : CHART_PALETTE[lineIndex % CHART_PALETTE.length];
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
            <FormControl size="small" sx={{ minWidth: 220 }}>
              <Select
                value={hierarchyOrder}
                onChange={(e) => {
                  // Editing is only allowed on the default "Payment type-Payer-Product"
                  // hierarchy, so exit edit mode when switching away from it.
                  if (tableEditing && e.target.value !== HIERARCHY_ORDERS[0].value) {
                    handleCancelTableEdit?.();
                  }
                  setHierarchyOrder(e.target.value);
                }}
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
                    {opt.label}
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
                <Button
                  key={mode}
                  onClick={() => {
                    if (mode === totalMarketViewMode) return;
                    setTotalMarketViewMode(mode);
                    if (mode === "yearly" && tableEditing) handleCancelTableEdit?.();
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

            {handleLocalDownloadTable && (
              <Tooltip title="Download table as CSV">
                <IconButton
                  size="small"
                  onClick={handleLocalDownloadTable}
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

            {handleEnterTableEdit && hierarchyOrder === HIERARCHY_ORDERS[0].value && (
              <Button
                variant="outlined"
                onClick={handleEnterTableEdit}
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

            {compareScenarioOptions.length > 1 && handleCompareScenarioChange && (
              <FormControl sx={{ ...tableInputStyle, width: 220, minWidth: 220, maxWidth: 220 }}>
                <Select
                  multiple
                  displayEmpty
                  value={selectedCompareScenarios}
                  onChange={handleCompareScenarioChange}
                  input={<OutlinedInput />}
                  sx={{
                    fontSize: "13px",
                    height: "34px",
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
          </Box>
        </Box>

        {/* ── TABLE ── */}
        <Box
          ref={tableContainerRef}
          onScroll={handleContainerScroll}
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
                const style = rowStyle(row.level, highlighted, row.siblingsHaveChildren ?? row.hasChildren, isPayerFilterValue(row.label));
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
                        {row.hasChildren ? (
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
                        ) : (
                          <Box sx={{ width: "14px", flexShrink: 0 }} />
                        )}
                        <Typography sx={{ fontSize: "14px", fontWeight: style.fontWeight, color: style.color }}>
                          {row.label}
                        </Typography>
                      </Box>
                    </Box>
                    {columns.map((col) => {
                      const displayVal = useRealData
                        ? Number(row.values?.[col.indices[0]] ?? 0)
                        : (() => {
                            const fixed = row.fixed || {};
                            const ownVal = columnValue(fixed, col);
                            const parentVal = row.level <= 1 ? columnValue({}, col) : parentColumnValue(row.parentFixed || {}, col);
                            return isPercent ? (parentVal ? (ownVal / parentVal) * 100 : 0) : ownVal;
                          })();

                      const isEditableCell =
                        tableEditing &&
                        totalMarketViewMode === "monthly" &&
                        useRealData &&
                        (!row.hasChildren || isPayerFilterValue(row.label)) &&
                        (!row.scenario || row.scenario === appliedScenario);
                      const cellKey = `${row.key}::${col.key}`;
                      const editedVal = editedCells[cellKey];
                      const shownVal = editedVal !== undefined ? editedVal : displayVal;

                      const isF = activeChartForOrder && chartFsi != null
                        ? col.indices.some((idx) => idx >= chartFsi)
                        : true;

                      const cellBg = isEditableCell
                        ? isF
                          ? "#eff6ff"
                          : "#f8fafc"
                        : highlighted && isF
                        ? "#fffbeb"
                        : isF
                        ? "#ffffff"
                        : "#F1F5F9";

                      const cellColor = !isEditableCell
                        ? isF && highlighted
                          ? "#f59e0b"
                          : row.level <= 1
                          ? "#1e293b"
                          : row.level === 2
                          ? "#334155"
                          : "#64748b"
                        : style.color;

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
                            color: cellColor,
                            backgroundColor: cellBg,
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