

import React, { useState, useEffect, useMemo, useRef } from "react";

import {
  Box,
  Paper,
  Typography,
  Button,
  IconButton,
  Tooltip,
  FormControl,
  Select,
  MenuItem,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
} from "@mui/material";
import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";

export default function HIVImpactCurveTable({
  tableData,
  metricFilters,
  selectedMetric,
  setSelectedMetric,
  selectedView,
  setSelectedView,
  activeTab,
  hierarchyView: hierarchyViewProp,
  onHierarchyViewChange,
  subViewOptions,
  onRefreshTable,
}) {
  const [editable, setEditable] = useState(false);

  const [editableRows, setEditableRows] = useState([]);

  const [originalRows, setOriginalRows] = useState([]);

  const [expandedRows, setExpandedRows] = useState({});

  const [isRefreshed, setIsRefreshed] = useState(false);

  const [savingTable, setSavingTable] = useState(false);

  const [lastEditedLabel, setLastEditedLabel] = useState("");

  // The parent refreshes the whole app state (like an apply-filters call) in
  // response to the Refresh button, which flows back down as a new
  // `tableData` prop. This ref lets the sync effect below tell "tableData
  // changed because of a refresh I triggered" apart from "tableData changed
  // for some other reason (filters/tab/metric/etc.)" — only the former
  // should leave the Save button enabled.
  const refreshInFlightRef = useRef(false);

  // Falls back to local state only if the parent doesn't control this
  // (keeps the component usable standalone / in older call sites).
  const [localHierarchyView, setLocalHierarchyView] = useState("");

  const isControlled = typeof onHierarchyViewChange === "function";

  const hierarchyView = isControlled ? hierarchyViewProp || "" : localHierarchyView;

  const setHierarchyView = isControlled ? onHierarchyViewChange : setLocalHierarchyView;

  const isHierarchy = tableData?.type === "hierarchy";

  const cloneRows = (rows = []) =>
    JSON.parse(JSON.stringify(Array.isArray(rows) ? rows : []));

  const headers = Array.isArray(tableData?.headers)
    ? tableData.headers
    : [];

  const forecastStartIndex =
    tableData?.forecast_start_index || 0;

  const labelText =
    activeTab === "product_event"
      ? "Product"
      : activeTab === "overall_event"
        ? "Event"
        : "Payer";

  useEffect(() => {
    if (isControlled) return;

    if (activeTab === "product_event") {
      setLocalHierarchyView("product_level");
      return;
    }

    if (activeTab === "payer_event") {
      setLocalHierarchyView("payer_level");
      return;
    }

    setLocalHierarchyView("");
  }, [activeTab, isControlled]);

  // The backend's own `view_options.label` text has been observed swapped
  // between the Payer Event and Product Event tabs across responses, so we
  // don't trust it for display. We still use the API's `value` (needed to
  // correctly look up the matching sub-view data), just not its label.
  const HIERARCHY_VIEW_LABELS = {
    payer_event:   ["Payer Level", "Product-Payer Level"],
    product_event: ["Product Level", "Payer-Product Level"],
  };

  const rawHierarchyOptions =
    Array.isArray(subViewOptions) && subViewOptions.length > 0
      ? subViewOptions
      : activeTab === "product_event"
        ? [
          { value: "product_level",       label: "Product Level" },
          { value: "payer_product_level",  label: "Payer-Product Level" },
        ]
        : activeTab === "payer_event"
          ? [
            { value: "payer_level",         label: "Payer Level" },
            { value: "product_payer_level",  label: "Product-Payer Level" },
          ]
          : [];

  const hierarchyOptions = rawHierarchyOptions.map((option, index) => ({
    ...option,
    label: HIERARCHY_VIEW_LABELS[activeTab]?.[index] || option.label,
  }));

  // The parent already resolves `tableData` to the API's pre-built payload
  // for the currently selected sub-view (e.g. product_level vs
  // product_payer_level), so it can be rendered as-is — no client-side
  // aggregation/transposition needed here.
  const displayTableData = useMemo(() => tableData || {}, [tableData]);

  useEffect(() => {
    if (!displayTableData) return;

    const cloned = cloneRows(displayTableData.rows);

    setEditableRows(cloned);
    setOriginalRows(cloned);
    setLastEditedLabel("");

    if (refreshInFlightRef.current) {
      refreshInFlightRef.current = false;
      setIsRefreshed(true);
    } else {
      setIsRefreshed(false);
    }

    setExpandedRows((prev) => {
      const nextExpanded = {};
      cloned.forEach((row, index) => {
        if (Array.isArray(row.children) && row.children.length > 0) {
          const rowKey = String(index);
          nextExpanded[rowKey] = prev[rowKey] ?? true;
        }
      });
      return nextExpanded;
    });
  }, [displayTableData]);

  const handleCancel = () => {
    refreshInFlightRef.current = false;
    setEditableRows(cloneRows(originalRows));

    setIsRefreshed(false);
    setLastEditedLabel("");
    setEditable(false);
  };

  const handleCellChange = (rowIndex, valueIndex, value, childIndex = null) => {
    if (!/^\d*\.?\d*$/.test(value)) {
      return;
    }

    const updated = cloneRows(editableRows);

    const editedLabel =
      childIndex !== null
        ? `${updated[rowIndex]?.label || ""} - ${updated[rowIndex]?.children?.[childIndex]?.label || ""}`
        : updated[rowIndex]?.label || "";

    if (childIndex !== null) {
      updated[rowIndex].children[childIndex].values[valueIndex] = value;
    } else {
      updated[rowIndex].values[valueIndex] = value;
    }

    setEditableRows(updated);
    setIsRefreshed(false);
    setLastEditedLabel(editedLabel);
  };

  const hasTableChanges =
    JSON.stringify(editableRows) !== JSON.stringify(originalRows);

  const hasTableData = editableRows.length > 0;

  const hasHierarchyRows = editableRows.some(
    (row) => Array.isArray(row?.children) && row.children.length > 0,
  );

  const recalculateHierarchyParents = (rows) =>
    rows.map((row) => {
      if (!Array.isArray(row.children) || !row.children.length) {
        return row;
      }

      const childCount = row.children.length;
      const valueLen = row.children[0]?.values?.length || row.values?.length || 0;

      const recalculatedValues = Array.from({ length: valueLen }, (_, colIndex) => {
        const sum = row.children.reduce((acc, child) => {
          const numeric = Number(child?.values?.[colIndex] ?? 0);
          return acc + (Number.isNaN(numeric) ? 0 : numeric);
        }, 0);

        if (selectedMetric === "market_share") {
          return Number(sum.toFixed(2));
        }

        return Math.round(sum);
      });

      return {
        ...row,
        values: recalculatedValues,
      };
    });

  // The inputs store edited values as strings (to allow partial typing like
  // "12." while validating), so convert them to real numbers before sending
  // to the API.
  const toNumericRow = (row) => ({
    ...row,
    values: Array.isArray(row?.values)
      ? row.values.map((value) => {
        const numeric = Number(value === "" || value === null || value === undefined ? 0 : value);
        return Number.isNaN(numeric) ? 0 : numeric;
      })
      : row?.values,
    children: Array.isArray(row?.children) ? row.children.map(toNumericRow) : row?.children,
  });

  const toNumericRows = (rows = []) => rows.map(toNumericRow);

  const handleRefreshTable = async () => {
    setSavingTable(true);

    try {
      if (typeof onRefreshTable === "function") {
        refreshInFlightRef.current = true;

        await onRefreshTable(toNumericRows(editableRows), lastEditedLabel);

        // The awaited call updates the parent's state, which re-renders this
        // component with a new `tableData` prop; the sync effect above picks
        // that up and sets isRefreshed(true) via refreshInFlightRef. Nothing
        // further to do here on the happy path.
      } else {
        setEditableRows(recalculateHierarchyParents(editableRows));
        setIsRefreshed(true);
      }
    } catch (error) {
      refreshInFlightRef.current = false;
      console.error("Failed to refresh liver market event table", error);
    } finally {
      setSavingTable(false);
    }
  };

  const toggleRow = (rowKey) => {
    setExpandedRows((prev) => ({
      ...prev,
      [rowKey]: !prev[rowKey],
    }));
  };

  const handleExpandAll = () => {
    const expanded = {};
    editableRows.forEach((row, index) => {
      if (Array.isArray(row?.children) && row.children.length > 0) {
        expanded[String(index)] = true;
      }
    });
    setExpandedRows(expanded);
  };

  const handleCollapseAll = () => {
    const collapsed = {};
    editableRows.forEach((row, index) => {
      if (Array.isArray(row?.children) && row.children.length > 0) {
        collapsed[String(index)] = false;
      }
    });
    setExpandedRows(collapsed);
  };

  const renderEditableCell = (
    value,
    rowIndex,
    valueIndex,
    childIndex = null,
    isParentRow = false,
  ) => {
    const isMarketShare = selectedMetric === "market_share";

    const isOverallEvent = activeTab === "overall_event";

    const canEdit =
      editable &&
      isMarketShare &&
      !isOverallEvent &&
      (!isHierarchy || childIndex !== null);

    if (!canEdit) {
      return (
        <Typography
          sx={{
            fontSize: "13px",
            fontWeight: isParentRow ? 700 : 500,
            color: "#334155",
            lineHeight: "28px",
          }}
        >
          {value}
        </Typography>
      );
    }

    return (
      <input
        value={value}
        onChange={(e) =>
          handleCellChange(rowIndex, valueIndex, e.target.value, childIndex)
        }
        style={{
          width: "100%",
          maxWidth: "72px",
          minWidth: "56px",
          height: "28px",
          padding: "2px 6px",
          boxSizing: "border-box",
          display: "block",
          margin: "0 auto",
          border: "1px solid #93C5FD",
          borderRadius: "4px",
          background: "#EFF6FF",
          textAlign: "center",
          fontSize: "13px",
          fontWeight: isParentRow ? 700 : 500,
          fontFamily: "inherit",
          lineHeight: "20px",
          outline: "none",
        }}
      />
    );
  };

  const renderRow = (
    row,
    rowIndex,
    level = 0,
    childIndex = null,
    rowKey = String(rowIndex),
  ) => {
    const hasChildren = Array.isArray(row.children) && row.children.length > 0;
    const isChildRow = level > 0;

    return (
    <React.Fragment key={`${rowKey}-${row.label}`}>
      <TableRow
        sx={{
          cursor: "default",
          backgroundColor: hasChildren ? "#F8FAFC" : "#fff",
        }}
      >
        <TableCell
          sx={{
            position: "sticky",
            left: 0,
            zIndex: 2,
            backgroundColor: hasChildren ? "#F8FAFC" : "#fff",
            minWidth: 360,
            width: 360,
            maxWidth: 360,
            fontWeight: hasChildren ? 700 : 500,
            overflow: "hidden",
          }}
        >
          <Box
            sx={{
              pl: level * 2,
              display: "flex",
              alignItems: "center",
              gap: 1,
              width: "100%",
              minWidth: 0,
              overflow: "hidden",
            }}
          >
            {hasChildren && (
              <Box
                component="button"
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  toggleRow(rowKey);
                }}
                sx={{
                  border: "none",
                  background: "transparent",
                  color: "#475569",
                  fontSize: "10px",
                  width: "16px",
                  minWidth: "16px",
                  p: 0,
                  lineHeight: 1,
                  cursor: "pointer",
                }}
              >
                {expandedRows[rowKey] ? "▼" : "▶"}
              </Box>
            )}
            <Typography
              sx={{
                fontSize: "13px",
                fontWeight: hasChildren ? 700 : 500,
                color: isChildRow ? "#475569" : "#334155",
                whiteSpace: "nowrap",
                minWidth: 0,
              }}
            >
              {row.label}
            </Typography>
          </Box>
        </TableCell>

        {(Array.isArray(row.values) ? row.values : []).map((value, index) => (
          <TableCell
            key={index}
            align="center"
            sx={{
              background:
                hasChildren
                  ? "#F8FAFC"
                  : index < forecastStartIndex
                    ? "#F8FAFC"
                    : "#fff",
              py: isChildRow ? "4px" : undefined,
              px: isChildRow ? 1 : undefined,
            }}
          >
            {renderEditableCell(value, rowIndex, index, childIndex, hasChildren)}
          </TableCell>
        ))}
      </TableRow>

      {isHierarchy &&
        (expandedRows[rowKey] ?? true) &&
        row.children?.map((child, idx) =>
          renderRow(child, rowIndex, level + 1, idx, `${rowKey}-${idx}`),
        )}
    </React.Fragment>
    );
  };

  return (
    <Paper
      sx={{
        mt: 0,
        p: 2,
        border: "1px solid #D8DEE8",
        borderRadius: "16px",
        boxShadow: "none",
      }}
    >
      {/* Header */}

      <Box
        sx={{
          mb: 2,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 2,
        }}
      >
        {/* Left */}

        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
          }}
        >
          <Tooltip title="Expand All">
            <span>
              <IconButton
                size="small"
                onClick={handleExpandAll}
                disabled={!hasTableData || !hasHierarchyRows}
              >
                <UnfoldMoreIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>

          <Tooltip title="Collapse All">
            <span>
              <IconButton
                size="small"
                onClick={handleCollapseAll}
                disabled={!hasTableData || !hasHierarchyRows}
              >
                <UnfoldLessIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Box>

        {/* Right */}

        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1.5,
            flexWrap: "wrap",
          }}
        >
          {hierarchyOptions.length > 0 && (
            <FormControl
              size="small"
              sx={{
                minWidth: 210,
                "& .MuiOutlinedInput-root": {
                  height: "35px",
                  borderRadius: "10px",
                  backgroundColor: "#fff",
                },
              }}
            >
              <Select
                value={hierarchyView}
                onChange={(e) => setHierarchyView(e.target.value)}
              >
                {hierarchyOptions.map((item) => (
                  <MenuItem key={item.value} value={item.value}>
                    {item.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              backgroundColor: "#f1f5f9",
              borderRadius: "6px",
              p: "3px",
              gap: 1,
            }}
          >
            {["monthly", "yearly"].map((mode) => (
              <Box
                key={mode}
                onClick={() => {
                  if (mode === selectedView) return;
                  setSelectedView(mode);
                }}
                sx={{
                  px: 1.5,
                  py: 0.4,
                  borderRadius: "4px",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                  userSelect: "none",
                  transition: "all 0.2s",
                  backgroundColor:
                    selectedView === mode ? "white" : "transparent",
                  color: selectedView === mode ? "#4F46E5" : "#94a3b8",
                  boxShadow:
                    selectedView === mode
                      ? "0 1px 4px rgba(0,0,0,0.12)"
                      : "none",
                }}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </Box>
            ))}
          </Box>

          <FormControl
            size="small"
            sx={{
              minWidth: 220,

              "& .MuiOutlinedInput-root": {
                height: "35px",
                borderRadius: "10px",
                backgroundColor: "#fff",
              },
            }}
          >
            <Select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value)}
            >
              {metricFilters.map((item) => (
                <MenuItem key={item.value} value={item.value}>
                  {item.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Button
            variant="contained"
            disabled={
              !editable ||
              selectedMetric === "market_volume" ||
              !isRefreshed
            }
            onClick={() => {
              console.log(editableRows);
              setOriginalRows(cloneRows(editableRows));

              setIsRefreshed(false);
              setEditable(false);
            }}
            sx={{
              height: "35px",
              borderRadius: "10px",
              textTransform: "none",
            }}
          >
            Save
          </Button>

          <Button
            variant="outlined"
            onClick={() => {
              setEditable(true);
              setIsRefreshed(false);
            }}
            sx={{
              height: "35px",
              borderRadius: "10px",
              textTransform: "none",
            }}
            disabled={
              editable ||
              selectedMetric === "market_volume" ||
              activeTab === "overall_event"
            }
          >
            {editable ? "Editing..." : "Edit Changes"}
          </Button>

          {editable && (
            <Button
              variant="contained"
              disabled={savingTable || !hasTableChanges}
              onClick={handleRefreshTable}
              sx={{
                height: "35px",
                borderRadius: "10px",
                textTransform: "none",
                backgroundColor: "#4F46E5",
              }}
            >
              {savingTable ? "Refreshing..." : "Refresh"}
            </Button>
          )}

          <Button
            variant="outlined"
            disabled={!editable || selectedMetric === "market_volume"}
            onClick={handleCancel}
            sx={{
              height: "35px",
              borderRadius: "10px",
              textTransform: "none",
            }}
          >
            Cancel
          </Button>
        </Box>
      </Box>

      {editableRows.length === 0 ? (
        <Box
          sx={{
            height: 120,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#94a3b8",
            fontSize: "14px",
            border: "1px solid #D8DEE8",
            borderRadius: "12px",
          }}
        >
          No table data available. Please apply filters.
        </Box>
      ) : (
        <TableContainer
          sx={{
            overflowX: "auto",
            border: "1px solid #D8DEE8",
            borderRadius: "12px",
          }}
        >
          <Table
            size="small"
            sx={{
              width: "100%",
              tableLayout: "auto",
              minWidth: "max-content",

              "& .MuiTableCell-root": {
                borderRight: "1px solid #E2E8F0",
                borderBottom: "1px solid #E2E8F0",
              },
            }}
          >
          <TableHead>
            <TableRow>
              <TableCell
                sx={{
                  position: "sticky",
                  left: 0,
                  zIndex: 5,

                  backgroundColor: "#ffffff",

                  fontWeight: 700,

                  minWidth: 360,

                  color: "#334155",
                  borderRight: "1px solid #E2E8F0",
                }}
              >
                {labelText}
              </TableCell>

              {headers.map((header, index) => (
                <TableCell
                  key={index}
                  align="center"
                  sx={{
                    minWidth: 90,

                    fontWeight: 700,

                    color: "#334155",
                    borderRight: "1px solid #E2E8F0",
                    backgroundColor: "#ffffff",
                  }}
                >
                  {header}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>

          <TableBody>
            {editableRows.map((row, index) => renderRow(row, index))}
          </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>
  );
}