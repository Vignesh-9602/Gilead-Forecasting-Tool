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

}) {

    const [editable, setEditable] = useState(false);

    const [editableRows, setEditableRows] = useState([]);

    const [originalRows, setOriginalRows] = useState([]);

    useEffect(() => {

        if (!tableData) return;

        const cloned = JSON.parse(
            JSON.stringify(tableData.rows)
        );

        setEditableRows(cloned);
        setOriginalRows(cloned);

    }, [tableData]);

    if (
        !tableData ||
        !editableRows?.length
    ) {
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

        setEditableRows(
            JSON.parse(
                JSON.stringify(originalRows)
            )
        );

        setEditable(false);

    };




    const handleCellChange = (
        rowIndex,
        valueIndex,
        value
    ) => {

        if (!/^\d*\.?\d*$/.test(value)) {
            return;
        }

        const updated = JSON.parse(
            JSON.stringify(editableRows)
        );

        updated[rowIndex].values[valueIndex] = value;

        setEditableRows(updated);

    };

    const renderEditableCell = (
        value,
        rowIndex,
        valueIndex
    ) => {

        if (!editable) {
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
                    handleCellChange(
                        rowIndex,
                        valueIndex,
                        e.target.value
                    )
                }

                style={{

                    width: "70px",

                    height: "28px",

                    padding: "2px 6px",

                    boxSizing: "border-box",

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
                            onChange={(e) =>
                                setSelectedMetric(
                                    e.target.value
                                )
                            }
                        >

                            {metricFilters.map((item) => (

                                <MenuItem
                                    key={item.value}
                                    value={item.value}
                                >
                                    {item.label}
                                </MenuItem>

                            ))}

                        </Select>

                    </FormControl>

                    <Button
                        variant="contained"
                        disabled={!editable}
                        onClick={() => {
                            console.log(editableRows);
                            setOriginalRows(
                                JSON.parse(
                                    JSON.stringify(
                                        editableRows
                                    )
                                )
                            );

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
                    >
                        {editable ? "Editing..." : "Edit Changes"}
                    </Button>

                    <Button
                        variant="outlined"
                        disabled={!editable}
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
                                Market
                            </TableCell>

                            {tableData.headers.map(
                                (header, index) => (

                                    <TableCell
                                        key={index}
                                        align="center"
                                        sx={{
                                            minWidth: 90,

                                            fontWeight: 700,

                                            color: "#334155",

                                            backgroundColor:
                                                index <
                                                    tableData.forecast_start_index
                                                    ? "#F8FAFC"
                                                    : "#ffffff",
                                        }}
                                    >
                                        {header}
                                    </TableCell>

                                )
                            )}

                        </TableRow>

                    </TableHead>

                    <TableBody>

                        {editableRows.map((row, rowIndex) => (

                            <TableRow
                                key={row.label}
                                hover
                            >
                                <TableCell
                                    sx={{
                                        position: "sticky",
                                        left: 0,

                                        zIndex: 2,

                                        backgroundColor: "#ffffff",

                                        fontWeight: 700,

                                        color: "#1E293B",

                                        minWidth: 170,
                                    }}
                                >
                                    {row.label}
                                </TableCell>

                                {row.values.map(
                                    (
                                        value,
                                        index
                                    ) => (

                                        <TableCell
                                            key={index}
                                            align="center"
                                            sx={{
                                                borderRight:
                                                    "1px solid #F1F5F9",

                                                background:
                                                    index <
                                                        tableData.forecast_start_index
                                                        ? "#F8FAFC"
                                                        : "#ffffff",
                                                py: 0.5,

                                                height: 40,

                                                verticalAlign: "middle",
                                            }}
                                        >
                                            {renderEditableCell(
                                                value,
                                                rowIndex,
                                                index
                                            )}
                                        </TableCell>

                                    )
                                )}

                            </TableRow>

                        ))}

                    </TableBody>

                </Table>

            </TableContainer>
        </Paper>

    );

}