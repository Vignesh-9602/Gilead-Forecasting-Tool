import React, { useState } from "react";

import {
    Box,
    Button,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    FormControl,
    Select,
    MenuItem,
} from "@mui/material";

import UnfoldMoreIcon from "@mui/icons-material/UnfoldMore";
import UnfoldLessIcon from "@mui/icons-material/UnfoldLess";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";

export default function MarketEventTable() {

    const months = [
        "Apr-24",
        "May-24",
        "Jun-24",
        "Jul-24",
        "Aug-24",
        "Sep-24",
        "Oct-24",
        "Nov-24",
        "Dec-24",
        "Jan-25",
        "Feb-25",
        "Mar-25",
    ];

    const initialData = [
        {
            lot: "1L",

            total: [
                100, 100, 100, 100, 100, 100,
                100, 100, 100, 100, 100, 100,
            ],

            children: [
                {
                    label: "Taxanes",

                    values: [
                        13.25, 13, 12.75, 12.5,
                        12.25, 12, 11.75, 11.5,
                        11.25, 11, 10.75, 10.5,
                    ],
                },

                {
                    label: "TPC",

                    values: [
                        14.25, 14, 13.75, 13.5,
                        13.25, 13, 12.75, 12.5,
                        12.25, 12, 11.75, 11.5,
                    ],
                },

                {
                    label: "Trodelvy",

                    values: [
                        26, 26.5, 27, 27.5,
                        28, 28.5, 29, 29.5,
                        30, 30.5, 31, 31.5,
                    ],
                },
            ],
        },

        {
            lot: "2L",

            total: [
                100, 100, 100, 100, 100, 100,
                100, 100, 100, 100, 100, 100,
            ],

            children: [
                {
                    label: "Taxanes",

                    values: [
                        12.25, 12, 11.75, 11.5,
                        11.25, 11, 10.75, 10.5,
                        10.25, 10, 9.75, 9.5,
                    ],
                },

                {
                    label: "Trodelvy",

                    values: [
                        25.7, 26.2, 26.7, 27.2,
                        27.7, 28.2, 28.7, 29.2,
                        29.7, 30.2, 30.7, 31.2,
                    ],
                },
            ],
        },
    ];

    const [editable, setEditable] = useState(false);

    const [selectedMetricView, setSelectedMetricView] =
        useState("overall_market_volume");

    const [tableRows, setTableRows] = useState(
        JSON.parse(JSON.stringify(initialData))
    );

    const [originalRows, setOriginalRows] = useState(
        JSON.parse(JSON.stringify(initialData))
    );

    const [expandedLots, setExpandedLots] = useState({
        "1L": true,
        "2L": true,
    });

    const handleCellChange = (
        lotIndex,
        childIndex,
        valueIndex,
        value
    ) => {

        const updatedRows =
            JSON.parse(JSON.stringify(tableRows));

        updatedRows[lotIndex]
            .children[childIndex]
            .values[valueIndex] = value;

        setTableRows(updatedRows);
    };

    const handleCancel = () => {

        setTableRows(
            JSON.parse(JSON.stringify(originalRows))
        );

        setEditable(false);
    };

    const handleExpandAll = () => {

        const expanded = {};

        tableRows.forEach((row) => {
            expanded[row.lot] = true;
        });

        setExpandedLots(expanded);
    };

    const handleCollapseAll = () => {

        const collapsed = {};

        tableRows.forEach((row) => {
            collapsed[row.lot] = false;
        });

        setExpandedLots(collapsed);
    };

    const toggleLot = (lot) => {

        setExpandedLots((prev) => ({
            ...prev,
            [lot]: !prev[lot],
        }));
    };

    const renderEditableCell = (
        value,
        lotIndex,
        childIndex,
        valueIndex
    ) => {

        return editable ? (
            <input
                value={value}
                onChange={(e) => {

                    const input = e.target.value;

                    if (/^\d*\.?\d*$/.test(input)) {

                        handleCellChange(
                            lotIndex,
                            childIndex,
                            valueIndex,
                            input
                        );
                    }
                }}
                style={{
                    width: "100%",
                    maxWidth: "42px",
                    border: "none",
                    outline: "none",
                    background: "transparent",
                    textAlign: "center",
                    fontSize: "13px",
                    padding: 0,
                    color: "#334155",
                }}
            />
        ) : (
            <Box
                sx={{
                    color: "#334155",
                    fontSize: "13px",
                }}
            >
                {value}
            </Box>
        );
    };

    return (
        <Paper
            sx={{
                mt: 3,
                p: 2,
                borderRadius: "16px",
                border: "1px solid #D8DEE8",
                boxShadow: "none",
            }}
        >

            {/* TOP ACTIONS */}
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

                {/* LEFT SIDE */}
                <Box
                    sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                    }}
                >
                    <Tooltip title="Expand All">
                        <IconButton onClick={handleExpandAll}>
                            <UnfoldMoreIcon />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title="Collapse All">
                        <IconButton onClick={handleCollapseAll}>
                            <UnfoldLessIcon />
                        </IconButton>
                    </Tooltip>
                </Box>

                {/* RIGHT SIDE */}
                <Box
                    sx={{
                        display: "flex",
                        gap: 1.5,
                        alignItems: "center",
                        flexWrap: "wrap",
                    }}
                >

                    {/* DROPDOWN */}
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
                            value={selectedMetricView}
                            onChange={(e) =>
                                setSelectedMetricView(
                                    e.target.value
                                )
                            }
                        >
                            <MenuItem value="overall_market_volume">
                                Overall Market Volume
                            </MenuItem>

                            <MenuItem value="market_share">
                                Market Share
                            </MenuItem>
                        </Select>
                    </FormControl>

                    {/* SAVE */}
                    <Button
                        variant="contained"
                        sx={{
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none",
                        }}
                    >
                        Save
                    </Button>

                    {/* EDIT */}
                    <Button
                        variant="outlined"
                        onClick={() => setEditable(true)}
                        sx={{
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none",
                        }}
                    >
                        Edit Changes
                    </Button>

                    {/* NORMALIZE */}
                    <Button
                        variant="outlined"
                        sx={{
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none",
                        }}
                    >
                        Normalize
                    </Button>

                    {/* CANCEL */}
                    <Button
                        variant="outlined"
                        color="error"
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

            {/* TABLE */}
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
                        minWidth: "max-content",
                    }}
                >

                    {/* HEADER */}
                    <TableHead>
                        <TableRow>

                            <TableCell
                                sx={{
                                    fontWeight: 700,
                                    minWidth: 180,
                                    position: "sticky",
                                    left: 0,
                                    zIndex: 3,
                                    backgroundColor: "#fff",
                                    borderRight: "1px solid #E2E8F0",
                                }}
                            >
                                Product / LOT
                            </TableCell>

                            {months.map((month, index) => (

                                <TableCell
                                    key={index}
                                    align="center"
                                    sx={{
                                        fontWeight: 700,
                                        minWidth: 90,
                                        borderRight: "1px solid #E2E8F0",
                                    }}
                                >
                                    {month}
                                </TableCell>
                            ))}
                        </TableRow>
                    </TableHead>

                    {/* BODY */}
                    <TableBody>

                        {tableRows.map((lotGroup, lotIndex) => (

                            <React.Fragment key={lotGroup.lot}>

                                {/* LOT ROW */}
                                <TableRow
                                    onClick={() =>
                                        toggleLot(lotGroup.lot)
                                    }
                                    sx={{
                                        cursor: "pointer",
                                        backgroundColor: "#f8fafc",
                                    }}
                                >
                                    <TableCell
                                        sx={{
                                            fontWeight: 700,
                                            position: "sticky",
                                            left: 0,
                                            zIndex: 2,
                                            backgroundColor: "#f8fafc",
                                            borderRight:
                                                "1px solid #E2E8F0",
                                        }}
                                    >
                                        {expandedLots[lotGroup.lot]
                                            ? "▼"
                                            : "▶"}{" "}
                                        {lotGroup.lot}
                                    </TableCell>

                                    {lotGroup.total.map(
                                        (value, index) => (

                                            <TableCell
                                                key={index}
                                                align="center"
                                                sx={{
                                                    fontWeight: 700,
                                                    borderRight:
                                                        "1px solid #E2E8F0",
                                                    backgroundColor:
                                                        "#f8fafc",
                                                }}
                                            >
                                                {value}
                                            </TableCell>
                                        )
                                    )}
                                </TableRow>

                                {/* CHILD ROWS */}
                                {expandedLots[lotGroup.lot] &&
                                    lotGroup.children.map(
                                        (row, childIndex) => (

                                            <TableRow key={childIndex}>

                                                <TableCell
                                                    sx={{
                                                        pl: 4,
                                                        position: "sticky",
                                                        left: 0,
                                                        zIndex: 1,
                                                        backgroundColor: "#fff",
                                                        borderRight:
                                                            "1px solid #E2E8F0",
                                                    }}
                                                >
                                                    {row.label}
                                                </TableCell>

                                                {row.values.map(
                                                    (
                                                        value,
                                                        valueIndex
                                                    ) => (

                                                        <TableCell
                                                            key={valueIndex}
                                                            align="center"
                                                            sx={{
                                                                borderRight:
                                                                    "1px solid #E2E8F0",
                                                            }}
                                                        >
                                                            {renderEditableCell(
                                                                value,
                                                                lotIndex,
                                                                childIndex,
                                                                valueIndex
                                                            )}
                                                        </TableCell>
                                                    )
                                                )}
                                            </TableRow>
                                        )
                                    )}
                            </React.Fragment>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Paper>
    );
}