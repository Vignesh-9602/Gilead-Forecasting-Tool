import React, {
    useState,
    useEffect,
} from "react";

import {
    Typography,
    Paper,
    Box,
    Button,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
} from "@mui/material";

import dayjs from "dayjs";
import { useLoadingStore, useSnackbarStore } from "../../../stores";
import { editNetRevenue } from "../../../services/apiService";

export default function RevenueTable({
    tableData,
    forecastStartIndex,
    ta_name,
    scenario_name,
    product,
    onRevenueUpdated
}) {

    const months =
        tableData?.months?.map((month) =>
            dayjs(month).format("MMM YY")
        ) || [];

    const [editable, setEditable] = useState(false);

    const [editableRows, setEditableRows] = useState([]);

    const [originalRows, setOriginalRows] = useState([]);

    const { showSnackbar } = useSnackbarStore();

    const { setLoading } = useLoadingStore();

    const EDITABLE_METRICS = [
        // "Derived Factor",
        "Final Factor",
        "WAC Price ($)",
        "Price Increase (%)",
        "GTN (%)",
    ];

    useEffect(() => {

        if (tableData?.rows) {

            const clonedRows =
                JSON.parse(
                    JSON.stringify(
                        tableData.rows
                    )
                );

            setEditableRows(
                clonedRows
            );

            setOriginalRows(
                JSON.parse(
                    JSON.stringify(
                        clonedRows
                    )
                )
            );
        }

    }, [tableData]);

    const formatDisplayValue = (
        metric,
        value
    ) => {

        if (
            value === null ||
            value === undefined ||
            value === ""
        ) {
            return "";
        }

        const currencyMetrics = [
            "WAC Price ($)",
            "Net Price",
            "Net Demand Revenue",
            "Net Revenue",
        ];

        const percentageMetrics = [
            "Price Increase (%)",
            "GTN (%)",
        ];

        if (
            currencyMetrics.includes(
                metric
            )
        ) {
            return `$${Number(
                value
            ).toLocaleString()}`;
        }

        if (
            percentageMetrics.includes(
                metric
            )
        ) {
            return `${value}%`;
        }

        return value;
    };

    const isEditableMetric = (
        metric
    ) =>
        EDITABLE_METRICS.includes(
            metric
        );

    const handleCellChange = (
        rowIndex,
        colIndex,
        value
    ) => {

        const updatedRows =
            JSON.parse(
                JSON.stringify(
                    editableRows
                )
            );

        updatedRows[rowIndex].values[
            colIndex
        ] =
            value === ""
                ? ""
                : Number(value);

        setEditableRows(
            updatedRows
        );
    };

    const handleCancel = () => {

        setEditableRows(
            JSON.parse(
                JSON.stringify(
                    originalRows
                )
            )
        );

        setEditable(false);
    };

    const handleSave = async () => {
        try {
            setLoading(true);

            const payload = {
                ta_name,
                scenario_name,
                product,

                months: tableData.months,

                rows: editableRows.filter(
                    (row) =>
                        EDITABLE_METRICS.includes(
                            row.metric
                        )
                ),
            };

            console.log(
                "EDIT PAYLOAD",
                payload
            );

            const { data } =
                await editNetRevenue(
                    payload
                );

            if (
                onRevenueUpdated &&
                data
            ) {
                onRevenueUpdated(data);
            }

            setEditable(false);

            showSnackbar(
                "Revenue updated successfully",
                "success"
            );
        } catch (error) {
            console.error(
                "Error updating revenue",
                error
            );

            showSnackbar(
                "Failed to update revenue",
                "error"
            );
        } finally {
            setLoading(false);
        }
    };

    const renderCell = (
        row,
        rowIndex,
        value,
        colIndex
    ) => {

        const canEdit =
            editable &&
            isEditableMetric(
                row.metric
            );

        if (!canEdit) {
            return formatDisplayValue(
                row.metric,
                value
            );
        }

        return (
            <input
                value={value}
                onChange={(e) => {

                    const input =
                        e.target.value;

                    if (
                        /^\d*\.?\d*$/.test(
                            input
                        )
                    ) {
                        handleCellChange(
                            rowIndex,
                            colIndex,
                            input
                        );
                    }
                }}
                style={{
                    width: "50px",
                    height: "22px",

                    padding: "2px 4px",
                    boxSizing:
                        "border-box",
                    border:
                        "1px solid #93c5fd",
                    borderRadius:
                        "4px",
                    outline: "none",
                    background:
                        "#eff6ff",
                    color:
                        "#1e293b",
                    textAlign:
                        "center",
                    fontSize:
                        "13px",
                }}
            />
        );
    };

    return (
        <Paper
            sx={{
                mt: 3,
                p: 2,
                borderRadius:
                    "12px",
                border:
                    "1px solid #D8DEE8",
                boxShadow:
                    "none",
            }}
        >
            <Box
                sx={{
                    mb: 2,
                    display:
                        "flex",
                    justifyContent:
                        "space-between",
                    alignItems:
                        "center",
                }}
            >
                <Typography
                    sx={{
                        fontWeight:
                            700,
                        fontSize:
                            "16px",
                    }}
                >
                    Net Revenue Details
                </Typography>

                <Box
                    sx={{
                        display:
                            "flex",
                        gap: 2,
                    }}
                >
                    <Button
                        variant="contained"
                        disabled={
                            !editable
                        }
                        onClick={
                            handleSave
                        }
                        sx={{
                            textTransform:
                                "none",
                            borderRadius:
                                "8px",
                        }}
                    >
                        Save
                    </Button>

                    <Button
                        variant="outlined"
                        // disabled={
                        //     editable
                        // }
                        onClick={() =>
                            setEditable(
                                true
                            )
                        }
                        sx={{
                            textTransform:
                                "none",
                            borderRadius:
                                "8px",
                        }}
                    >
                        {editable
                            ? "Editing..."
                            : "Edit Changes"}
                    </Button>

                    <Button
                        variant="outlined"
                        onClick={
                            handleCancel
                        }
                        sx={{
                            textTransform:
                                "none",
                            borderRadius:
                                "8px",
                        }}
                    >
                        Cancel
                    </Button>
                </Box>
            </Box>

            {!editableRows.length ? (
                <Paper
                    sx={{
                        p: 4,
                        textAlign:
                            "center",
                    }}
                >
                    No table data
                    available
                </Paper>
            ) : (
                <TableContainer
                    sx={{
                        border:
                            "1px solid #D8DEE8",
                        borderRadius:
                            "12px",
                        overflowX:
                            "auto",
                    }}
                >
                    <Table
                        size="small"
                        sx={{
                            minWidth:
                                "max-content",
                        }}
                    >
                        <TableHead>
                            <TableRow>
                                <TableCell
                                    sx={{
                                        fontWeight:
                                            700,
                                        minWidth:
                                            220,
                                        position:
                                            "sticky",
                                        left: 0,
                                        zIndex: 2,
                                        backgroundColor:
                                            "#fff",
                                        borderRight:
                                            "1px solid #E2E8F0",
                                        py: "2px",
                                        height: "28px",
                                    }}
                                >
                                    Metric
                                </TableCell>

                                {months.map(
                                    (
                                        month,
                                        index
                                    ) => (
                                        <TableCell
                                            key={
                                                month
                                            }
                                            align="center"
                                            sx={{
                                                fontWeight:
                                                    700,
                                                minWidth:
                                                    110,
                                                borderRight:
                                                    "1px solid #E2E8F0",

                                                backgroundColor:
                                                    index <
                                                        forecastStartIndex
                                                        ? "#f1f5f9"
                                                        : "#ffffff",
                                            }}
                                        >
                                            {
                                                month
                                            }
                                        </TableCell>
                                    )
                                )}
                            </TableRow>
                        </TableHead>

                        <TableBody>
                            {editableRows.map(
                                (
                                    row,
                                    rowIndex
                                ) => (
                                    <TableRow
                                        key={
                                            row.metric
                                        }
                                    >
                                        <TableCell
                                            sx={{
                                                fontWeight:
                                                    row.metric === "Net Revenue"
                                                        ? 700
                                                        : 600,
                                                position:
                                                    "sticky",
                                                left: 0,
                                                zIndex: 1,
                                                backgroundColor:
                                                    "#fff",
                                                borderRight:
                                                    "1px solid #E2E8F0",
                                            }}
                                        >
                                            {
                                                row.metric
                                            }
                                        </TableCell>

                                        {row.values.map(
                                            (
                                                value,
                                                idx
                                            ) => (
                                                <TableCell
                                                    key={
                                                        idx
                                                    }
                                                    align="center"
                                                    sx={{
                                                        borderRight:
                                                            "1px solid #E2E8F0",

                                                        backgroundColor:
                                                            idx <
                                                                forecastStartIndex
                                                                ? "#f1f5f9"
                                                                : "#ffffff",
                                                        py: "2px",
                                                        px: 1,
                                                        height: "28px",
                                                        lineHeight: "20px",
                                                        fontWeight:
                                                            row.metric === "Net Revenue"
                                                                ? 700
                                                                : 400,
                                                    }}
                                                >
                                                    {renderCell(
                                                        row,
                                                        rowIndex,
                                                        value,
                                                        idx
                                                    )}
                                                </TableCell>
                                            )
                                        )}
                                    </TableRow>
                                )
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}
        </Paper>
    );
}