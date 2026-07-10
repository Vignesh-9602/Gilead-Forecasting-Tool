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

  const isHierarchy = tableData?.type === "hierarchy";

  const labelText =
    activeTab === "product_event"
      ? "Product"
      : activeTab === "overall_event"
        ? "Event"
        : "Payer";

  useEffect(() => {
    if (!tableData) return;

    const cloned = JSON.parse(JSON.stringify(tableData.rows));

    setEditableRows(cloned);
    setOriginalRows(cloned);
  }, [tableData]);

  if (!tableData || !editableRows?.length) {
    return (
      <Paper
        sx={{
          mt: 3,
          p: 4,
          borderRadius: "16px",
          border: "1px solid #D8DEE8",
          textAlign: "center",
        }}
      >
        No table data available.
      </Paper>
    );
  }

  const handleCancel = () => {
    setEditableRows(JSON.parse(JSON.stringify(originalRows)));

    setEditable(false);
  };

  const handleCellChange = (rowIndex, valueIndex, value, childIndex = null) => {
    if (!/^\d*\.?\d*$/.test(value)) {
      return;
    }

    const updated = JSON.parse(JSON.stringify(editableRows));

    if (childIndex !== null) {
      updated[rowIndex].children[childIndex].values[valueIndex] = value;
    } else {
      updated[rowIndex].values[valueIndex] = value;
    }

    setEditableRows(updated);
  };

  const renderEditableCell = (value, rowIndex, valueIndex, childIndex = null) => {
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
          fontFamily: "inherit",
          lineHeight: "20px",
          outline: "none",
        }}
      />
    );
  };

  const renderRow = (row, rowIndex, level = 0, childIndex = null) => (
    <React.Fragment key={`${rowIndex}-${childIndex}-${row.label}`}>
      <TableRow>
        <TableCell
          sx={{
            position: "sticky",
            left: 0,
            zIndex: 2,
            backgroundColor: "#fff",
            minWidth: 170,
            fontWeight: level === 0 ? 700 : 500,
          }}
        >
          <Box sx={{ pl: level * 3 }}>{row.label}</Box>
        </TableCell>

        {row.values.map((value, index) => (
          <TableCell
            key={index}
            align="center"
            sx={{
              background:
                index < tableData.forecast_start_index ? "#F8FAFC" : "#fff",
            }}
          >
            {renderEditableCell(value, rowIndex, index, childIndex)}
          </TableCell>
        ))}
      </TableRow>

      {isHierarchy &&
        row.children?.map((child, idx) =>
          renderRow(child, rowIndex, level + 1, idx),
        )}
    </React.Fragment>
  );

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
            disabled={!editable || selectedMetric === "market_volume"}
            onClick={() => {
              console.log(editableRows);
              setOriginalRows(JSON.parse(JSON.stringify(editableRows)));

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
            onClick={() => setEditable(true)}
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
            tableLayout: "fixed",
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

                  minWidth: 170,

                  color: "#334155",
                }}
              >
                {labelText}
              </TableCell>

              {tableData.headers.map((header, index) => (
                <TableCell
                  key={index}
                  align="center"
                  sx={{
                    minWidth: 90,

                    fontWeight: 700,

                    color: "#334155",

                    backgroundColor:
                      index < tableData.forecast_start_index
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
            {editableRows.map((row, index) => renderRow(row, index))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
