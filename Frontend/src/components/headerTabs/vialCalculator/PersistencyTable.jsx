import React, { useState, useEffect } from "react";
import { Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography, Select, MenuItem, FormControl, Button, Checkbox } from "@mui/material";
import PersistencyConfiguration from "./PersistencyConfiguration";
import { getPersistencyCurves, applyPersistencyCurve } from "../../../services/apiService";

export default function PersistencyTable({
    persistencyData,
    setPersistencyData,
    loading,
    therapyArea,
    indication,
    brand,
    startDate,
    endDate,
}) {
    const formattedMonths =
        persistencyData?.months?.map(
            (month) =>
                new Date(month).toLocaleDateString(
                    "en-US",
                    {
                        month: "short",
                        year: "2-digit",
                    }
                )
        ) || [];

    const [curveOptions, setCurveOptions] =
        useState([]);

    const [selectedCurves, setSelectedCurves] =
        useState({});

    const [selectedLots, setSelectedLots] =
        useState([]);

    const [avgVialsEditable, setAvgVialsEditable] =
        useState(false);

    const [demandVialsEditable, setDemandVialsEditable] =
        useState(false);

    const handleAvgVialsCellChange = (
        lotIndex,
        childIndex,
        valueIndex,
        value
    ) => {

        const updatedRows =
            JSON.parse(
                JSON.stringify(avgVialsRows)
            );

        updatedRows[lotIndex]
            .children[childIndex]
            .values[valueIndex] = value;

        setAvgVialsRows(updatedRows);
    };

    const handleCancelAvgVials = () => {

        setAvgVialsRows(
            JSON.parse(
                JSON.stringify(
                    originalAvgVialsRows
                )
            )
        );

        setAvgVialsEditable(false);
    };

    const persistencyRows =
        persistencyData?.persistency_table || [];

    const avgVialsRowsTable =
        persistencyData?.avg_vials_per_dose_table || [];

    const demandVialsRowsTable =
        persistencyData?.demand_vials_table || [];

    const handleDemandVialsCellChange = (
        rowIndex,
        childIndex,
        valueIndex,
        value
    ) => {

        const updatedRows =
            JSON.parse(
                JSON.stringify(
                    demandVialsRows
                )
            );

        updatedRows[rowIndex]
            .children[childIndex]
            .values[valueIndex] = value;

        setDemandVialsRows(updatedRows);
    };

    const handleCancelDemandVials = () => {

        setDemandVialsRows(
            JSON.parse(
                JSON.stringify(
                    originalDemandVialsRows
                )
            )
        );

        setDemandVialsEditable(false);
    };

    useEffect(() => {
        if (therapyArea) {
            fetchCurveOptions();
        }
    }, [therapyArea]);

    useEffect(() => {

        if (
            avgVialsRowsTable?.length
        ) {

            const clonedData =
                JSON.parse(
                    JSON.stringify(
                        avgVialsRowsTable
                    )
                );

            setAvgVialsRows(clonedData);

            setOriginalAvgVialsRows(
                clonedData
            );
        }

    }, [avgVialsRowsTable]);

    useEffect(() => {

        if (
            demandVialsRowsTable?.length
        ) {

            const clonedData =
                JSON.parse(
                    JSON.stringify(
                        demandVialsRowsTable
                    )
                );

            setDemandVialsRows(
                clonedData
            );

            setOriginalDemandVialsRows(
                clonedData
            );
        }

    }, [demandVialsRowsTable]);

    const [avgVialsRows, setAvgVialsRows] =
        useState([]);

    const [originalAvgVialsRows, setOriginalAvgVialsRows] =
        useState([]);

    const [demandVialsRows, setDemandVialsRows] =
        useState([]);

    const [
        originalDemandVialsRows,
        setOriginalDemandVialsRows,
    ] = useState([]);

    const [openPersistencyDialog, setOpenPersistencyDialog] = useState(false);

    const tableInputStyle = {
        borderRadius: "8px",
        "& .MuiOutlinedInput-root": {
            height: "42px",
            borderRadius: "10px",
            backgroundColor: "#fff",
            fontSize: "14px",
        },
    };

    const fetchCurveOptions = async () => {
        try {
            const response =
                await getPersistencyCurves(
                    therapyArea
                );

            setCurveOptions(
                response?.data?.curve_list || []
            );
        } catch (error) {
            console.error(
                "Failed to fetch curve options",
                error
            );
        }
    };

    const handleApplyCurve = async () => {
        try {
            const lotCurveMapping =
                selectedLots
                    .filter(
                        (lot) =>
                            selectedCurves[lot]
                    )
                    .map((lot) => ({
                        lot,
                        curve_name:
                            selectedCurves[lot],
                    }));

            if (!lotCurveMapping.length) {
                return;
            }

            const payload = {
                ta_name: therapyArea,

                indication,
                brand,
                start_date: startDate,
                end_date: endDate,

                lot_curve_mapping:
                    lotCurveMapping,
            };

            console.log(
                "APPLY CURVE PAYLOAD",
                payload
            );

            const response =
                await applyPersistencyCurve(
                    payload
                );

            console.log(
                "APPLY CURVE RESPONSE",
                response?.data
            );

            setPersistencyData(response?.data || null);

        } catch (error) {
            console.error(
                "Failed to apply persistency curve",
                error
            );
        }
    };

    return (
        <Box sx={{ mt: 3 }}>
            {/* Header */}
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
                <Typography sx={{ fontSize: "18px", fontWeight: 700 }}>
                    Persistency
                </Typography>

                <Box sx={{ display: "flex", gap: 2 }}>
                    <Button
                        variant="outlined"
                        onClick={() => setOpenPersistencyDialog(true)}
                        sx={{ textTransform: "none", borderRadius: "8px", height: "38px" }}
                    >
                        Configure Persistency
                    </Button>

                    <Button
                        variant="contained"
                        onClick={handleApplyCurve}
                        sx={{ textTransform: "none", borderRadius: "8px", height: "38px", backgroundColor: "#4F46E5" }}
                    >
                        Apply Curve
                    </Button>
                </Box>
            </Box>

            {/* Persistency Table */}
            <TableContainer
                sx={{
                    border: "1px solid #D8DEE8",
                    borderRadius: "12px",
                    overflowX: "auto",
                }}
            >
                <Table size="small" sx={{ minWidth: "max-content" }}>
                    {persistencyRows.length > 0 && (
                        <TableHead>
                            <TableRow>
                                <TableCell
                                    sx={{ fontWeight: 700, minWidth: 320, position: "sticky", left: 0, backgroundColor: "#fff", zIndex: 5, borderRight: "1px solid #CBD5E1", }}
                                >
                                    Metric
                                </TableCell>

                                {formattedMonths.map((month) => (
                                    <TableCell
                                        key={month}
                                        align="center"
                                        sx={{ fontWeight: 700, minWidth: 72, fontSize: "13px", py: 1.2, backgroundColor: "#f8fafc", borderRight: "1px solid #CBD5E1" }}
                                    >
                                        {month}
                                    </TableCell>
                                ))}
                            </TableRow>
                        </TableHead>
                    )}

                    <TableBody>
                        {!persistencyRows.length ? (
                            <TableRow>
                                <TableCell
                                    colSpan={formattedMonths.length + 1}
                                    align="center"
                                    sx={{ py: 5, color: "#94a3b8", fontWeight: 600 }}
                                >
                                    No persistency data available. Please apply filters.
                                </TableCell>
                            </TableRow>
                        ) : (
                            persistencyRows.map((row) => (
                                <React.Fragment key={row.lot}>
                                    <TableRow
                                        sx={{ backgroundColor: "#f8fafc", }}
                                    >

                                        <TableCell
                                            sx={{ position: "sticky", left: 0, backgroundColor: "#f8fafc", zIndex: 4, borderRight: "1px solid #CBD5E1", }}
                                        >
                                            <Box
                                                sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
                                            >
                                                <Checkbox
                                                    checked={selectedLots.includes(
                                                        row.lot
                                                    )}
                                                    onChange={(e) => {
                                                        if (e.target.checked) {
                                                            setSelectedLots((prev) => [
                                                                ...prev,
                                                                row.lot,
                                                            ]);
                                                        } else {
                                                            setSelectedLots((prev) =>
                                                                prev.filter(
                                                                    (item) =>
                                                                        item !== row.lot
                                                                )
                                                            );
                                                        }
                                                    }}
                                                />
                                                <Typography
                                                    sx={{ fontWeight: 700, }} >
                                                    {persistencyData?.brand}{" "} - {row.lot}
                                                </Typography>

                                                <FormControl size="small">
                                                    <Select
                                                        value={
                                                            selectedCurves[row.lot] ||
                                                            row.curve_name ||
                                                            ""
                                                        }
                                                        displayEmpty
                                                        onChange={(e) => {
                                                            setSelectedCurves((prev) => ({
                                                                ...prev,
                                                                [row.lot]: e.target.value,
                                                            }));
                                                        }}
                                                        renderValue={(selected) => {
                                                            if (!selected) {
                                                                return "Curves";
                                                            }

                                                            return selected;
                                                        }}
                                                        sx={{
                                                            height: 32,
                                                            minWidth: 140,
                                                            borderRadius: "10px",
                                                            backgroundColor: "#fff",
                                                        }}
                                                    >
                                                        <MenuItem value="" disabled>
                                                            Curves
                                                        </MenuItem>

                                                        {curveOptions.map((option) => (
                                                            <MenuItem
                                                                key={option.curve_name}
                                                                value={option.curve_name}
                                                            >
                                                                {option.curve_name}
                                                            </MenuItem>
                                                        ))}
                                                    </Select>
                                                </FormControl>
                                            </Box>
                                        </TableCell>

                                        {formattedMonths.map((month, idx) => (
                                            <TableCell
                                                key={idx}
                                                sx={{
                                                    backgroundColor: "#f1f5f9",
                                                    borderRight: "1px solid #CBD5E1",
                                                }}
                                            />
                                        ))}
                                    </TableRow>

                                    {row.children.map(
                                        (child) => (
                                            <TableRow key={child.label}>
                                                <TableCell
                                                    sx={{ pl: 3, position: "sticky", left: 0, backgroundColor: "#fff", zIndex: 3, borderRight: "1px solid #CBD5E1" }}
                                                >

                                                    <Typography sx={{ color: "#506784", fontWeight: 500, }} >
                                                        {child.label}
                                                    </Typography>
                                                </TableCell>

                                                {child.values.map((value, idx) => (
                                                    <TableCell
                                                        key={idx}
                                                        align="center"
                                                        sx={{ borderRight: "1px solid #CBD5E1", color: "#506784", fontWeight: 500, fontSize: "13px", py: 1.2, }}
                                                    >
                                                        {value}
                                                    </TableCell>
                                                ))}
                                            </TableRow>
                                        )
                                    )}
                                </React.Fragment>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* =========================================
                AVG VIALS PER DOSE TABLE
                ========================================= */}

            <Box sx={{ mt: 5 }}>
                {/* HEADER */}
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1.5, }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, }} >
                        {/* <Box sx={{ px: 1.5, py: 0.5, borderRadius: "8px",border: "1px solid #CBD5E1", backgroundColor: "#F8FAFC",fontSize: "13px", fontWeight: 700,color: "#64748B", }} >
                            TABLE 2
                        </Box> */}

                        <Typography sx={{ fontSize: "18px", fontWeight: 700, }}>
                            Avg Vials Per Dose
                        </Typography>
                    </Box>

                    <Box sx={{ display: "flex", gap: 1.5 }}>
                        <Button
                            variant="outlined"
                            onClick={() =>
                                setAvgVialsEditable(true)
                            }
                            // disabled={avgVialsEditable}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Edit
                        </Button>

                        <Button
                            variant="contained"
                            onClick={() => {
                                setOriginalAvgVialsRows(
                                    JSON.parse(
                                        JSON.stringify(
                                            avgVialsRows
                                        )
                                    )
                                );

                                setPersistencyData((prev) => ({
                                    ...prev,
                                    avg_vials_per_dose_table:
                                        avgVialsRows,
                                }));

                                setAvgVialsEditable(false);
                            }}
                            // disabled={!avgVialsEditable}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", backgroundColor: "#4F46E5", fontWeight: 700, }}
                        >
                            Apply
                        </Button>
                        {/* {avgVialsEditable && ( */}
                        <Button
                            variant="outlined"
                            onClick={handleCancelAvgVials}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Cancel
                        </Button>
                        {/* )} */}
                    </Box>
                </Box>

                {/* AVG VIALS TABLE */}
                <TableContainer
                    sx={{ border: "1px solid #D8DEE8", borderRadius: "12px", overflowX: "auto", }}
                >
                    <Table
                        size="small"
                        sx={{ minWidth: "max-content", }}
                    >
                        <TableHead>
                            <TableRow>
                                <TableCell
                                    sx={{ fontWeight: 700, minWidth: 320, position: "sticky", left: 0, backgroundColor: "#fff", zIndex: 5, borderRight: "1px solid #CBD5E1", }}
                                >
                                    Metric
                                </TableCell>
                                {formattedMonths.map((month) => (
                                    <TableCell
                                        key={month}
                                        align="center"
                                        sx={{
                                            fontWeight: 700,
                                            minWidth: 72,
                                            fontSize: "13px",
                                            height: "36px",
                                            py: 0,
                                            backgroundColor: "#f8fafc",
                                            borderRight: "1px solid #CBD5E1",
                                        }}
                                    >
                                        {month}
                                    </TableCell>
                                ))}
                            </TableRow>
                        </TableHead>

                        <TableBody>
                            {avgVialsRows.map(
                                (row, rowIndex) => (
                                    <React.Fragment key={row.lot}>
                                        {row.children.map((child, childIndex) => (
                                            <TableRow key={child.label}>
                                                <TableCell
                                                    sx={{ pl: 2, position: "sticky", left: 0, backgroundColor: "#fff", zIndex: 3, borderRight: "1px solid #CBD5E1", fontWeight: 700, }}
                                                >
                                                    {child.label}
                                                </TableCell>

                                                {child.values.map((value, idx) => (

                                                    <TableCell
                                                        key={idx}
                                                        align="center"
                                                        sx={{ borderRight: "1px solid #CBD5E1", color: "#334155", fontSize: "13px", height: "36px", py: 0, }}
                                                    >
                                                        <Box
                                                            sx={{ width: "40px", height: "20px", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto", fontSize: "13px", color: "#334155", lineHeight: 1, }}
                                                        >
                                                            {avgVialsEditable ? (
                                                                <input
                                                                    value={value}
                                                                    onChange={(e) => {
                                                                        const input = e.target.value;
                                                                        if (/^\d*\.?\d*$/.test(input)) {
                                                                            handleAvgVialsCellChange(
                                                                                rowIndex,
                                                                                childIndex,
                                                                                idx,
                                                                                input
                                                                            );
                                                                        }
                                                                    }}
                                                                    style={{ width: "100%", height: "100%", border: "none", outline: "none", background: "transparent", textAlign: "center", fontSize: "13px", fontFamily: "inherit", color: "#334155", padding: 0, margin: 0, lineHeight: 1, }}
                                                                />
                                                            ) : (
                                                                value
                                                            )}
                                                        </Box>
                                                    </TableCell>
                                                )
                                                )}
                                            </TableRow>
                                        )
                                        )}
                                    </React.Fragment>
                                )
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>

            {/*demand vials*/}
            <Box sx={{ mt: 5 }}>
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1.5, }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, }} >
                        {/* <Box sx={{ px: 1.5, py: 0.5, borderRadius: "8px",border: "1px solid #CBD5E1", backgroundColor: "#F8FAFC",fontSize: "13px", fontWeight: 700,color: "#64748B", }} >
                            TABLE 2
                        </Box> */}

                        <Typography sx={{ fontSize: "18px", fontWeight: 700, }}>
                            Demand (Vials)
                        </Typography>
                    </Box>

                    <Box sx={{ display: "flex", gap: 1.5 }}>
                        <Button
                            variant="outlined"
                            // onClick={() =>
                            //     setAvgVialsEditable(true)
                            // }
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Edit Values
                        </Button>
                        <Button
                            variant="outlined"
                            // onClick={() =>
                            //     setAvgVialsEditable(true)
                            // }
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Configure Compliance
                        </Button>
                        <Button
                            variant="outlined"
                            onClick={() =>
                                setDemandVialsEditable(true)
                            }
                            // disabled={demandVialsEditable}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Edit
                        </Button>

                        <Button
                            variant="contained"
                            onClick={() => {

                                setOriginalDemandVialsRows(
                                    JSON.parse(
                                        JSON.stringify(
                                            demandVialsRows
                                        )
                                    )
                                );

                                setPersistencyData((prev) => ({
                                    ...prev,
                                    demand_vials_table:
                                        demandVialsRows,
                                }));

                                setDemandVialsEditable(false);
                            }}
                            // disabled={!demandVialsEditable}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", backgroundColor: "#4F46E5", fontWeight: 700, }}
                        >
                            Apply
                        </Button>
                        {/* {avgVialsEditable && ( */}
                        <Button
                            variant="outlined"
                            onClick={
                                handleCancelDemandVials
                            }
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Cancel
                        </Button>
                        {/* )} */}
                    </Box>
                </Box>

            </Box>

            {/* Persistency Dialog */}
            <PersistencyConfiguration
                open={openPersistencyDialog}
                onClose={() =>
                    setOpenPersistencyDialog(false)
                }
                therapyArea={therapyArea}
            />
        </Box >
    );
}
