import React, { useState, useEffect } from "react";

import {
  Box,
  Paper,
  Typography,
  Button,
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

export default function HIVImpactCurveTable({
  tableData,
  metricFilters,
  selectedMetric,
  setSelectedMetric,
  selectedView,
  setSelectedView,
  activeTab,
}) {
  const [editable, setEditable] = useState(false);

  const [editableRows, setEditableRows] = useState([]);

  const [originalRows, setOriginalRows] = useState([]);

  const [expandedRows, setExpandedRows] = useState({});

  const [isRefreshed, setIsRefreshed] = useState(false);

  const [savingTable, setSavingTable] = useState(false);

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
    if (!tableData) return;

    const cloned = cloneRows(tableData.rows);

    setEditableRows(cloned);
    setOriginalRows(cloned);
    setIsRefreshed(false);

    const initialExpanded = {};
    cloned.forEach((row, index) => {
      if (Array.isArray(row.children) && row.children.length > 0) {
        initialExpanded[String(index)] = true;
      }
    });
    setExpandedRows(initialExpanded);
  }, [tableData]);

  const handleCancel = () => {
    setEditableRows(cloneRows(originalRows));

    setIsRefreshed(false);
    setEditable(false);
  };

  const handleCellChange = (rowIndex, valueIndex, value, childIndex = null) => {
    if (!/^\d*\.?\d*$/.test(value)) {
      return;
    }

    const updated = cloneRows(editableRows);

    if (childIndex !== null) {
      updated[rowIndex].children[childIndex].values[valueIndex] = value;
    } else {
      updated[rowIndex].values[valueIndex] = value;
    }

    setEditableRows(updated);
    setIsRefreshed(false);
  };

  const hasTableChanges =
    JSON.stringify(editableRows) !== JSON.stringify(originalRows);

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

  const handleRefreshTable = () => {
    try {
      setSavingTable(true);
      const refreshedRows = recalculateHierarchyParents(editableRows);
      setEditableRows(refreshedRows);
      setIsRefreshed(true);
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
        onClick={() => {
          if (hasChildren) {
            toggleRow(rowKey);
          }
        }}
        sx={{
          cursor: hasChildren ? "pointer" : "default",
          backgroundColor: isChildRow ? "#F8FAFC" : "#fff",
        }}
      >
        <TableCell
          sx={{
            position: "sticky",
            left: 0,
            zIndex: 2,
            backgroundColor: isChildRow ? "#F8FAFC" : "#fff",
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
              <Typography component="span" sx={{ fontSize: "10px", width: "12px" }}>
                {expandedRows[rowKey] ? "▼" : "▶"}
              </Typography>
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
                isChildRow
                  ? "#F8FAFC"
                  : index < forecastStartIndex
                    ? "#F8FAFC"
                    : "#fff",
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
        mt: 3,
        border: "1px solid #D8DEE8",
        borderRadius: "16px",
        boxShadow: "none",
        overflow: "hidden",
      }}
    >
      {/* Header */}

      <Box
        sx={{
          px: 2.5,
          py: 2,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 2,
          borderBottom: "1px solid #E5E7EB",
        }}
      >
        {/* Left */}

        <Typography
          sx={{
            fontSize: "16px",
            fontWeight: 700,
            color: "#0f172a",
          }}
        >
          Impact Curve Metrics Table
        </Typography>

        {/* Right */}

        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1.5,
            flexWrap: "wrap",
          }}
        >
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
                borderRadius: "8px",
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
              borderRadius: "8px",
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
              borderRadius: "8px",
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
                borderRadius: "8px",
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
              borderRadius: "8px",
              textTransform: "none",
            }}
          >
            Cancel
          </Button>
        </Box>
      </Box>

      {/* Table Placeholder */}
      <TableContainer
        sx={{
          overflowX: "auto",
          // borderTop: "1px solid #E2E8F0",
          // maxHeight: 420,

          // "&::-webkit-scrollbar": {
          //     height: 8,
          //     width: 8,
          // },

          // "&::-webkit-scrollbar-thumb": {
          //     background: "#CBD5E1",
          //     borderRadius: "8px",
          // },
        }}
      >
        <Table
          stickyHeader
          size="small"
          sx={{
            width: "100%",
            tableLayout: "auto",
            minWidth: "max-content",

            "& .MuiTableCell-root": {
              borderRight: "1px solid #D6DEE8",
              borderBottom: "1px solid #D6DEE8",
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

                    backgroundColor:
                      index < forecastStartIndex
                        ? "#F8FAFC"
                        : "#ffffff",
                  }}
                >
                  {header}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>

          <TableBody>
            {editableRows.length ? (
              editableRows.map((row, index) => renderRow(row, index))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={Math.max(headers.length + 1, 1)}
                  sx={{
                    py: 5,
                    textAlign: "center",
                    color: "#94a3b8",
                  }}
                >
                  No table data available.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
