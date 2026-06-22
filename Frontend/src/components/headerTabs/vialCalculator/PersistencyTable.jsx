import React, { useState, useEffect } from "react";
import { Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography, Select, MenuItem, FormControl, Button, Checkbox } from "@mui/material";
import PersistencyConfiguration from "./PersistencyConfiguration";
import { getPersistencyCurves, applyPersistencyCurve, saveAvgVials, saveDemandAdjustments, getComplianceConfiguration, applyComplianceConfiguration, applyEditComplianceRowValues, applyInventoryStockPercentage } from "../../../services/apiService";
import ConfigureComplianceDialog from "./ConfigureComplianceDialog";
import EditValuesDialog from "./EditValuesDialog";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import Tooltip from "@mui/material/Tooltip";
import { useLoadingStore } from "../../../stores";
import ConfigureCurveDialog from "./ConfigureCurveDialog";

export default function PersistencyTable({
    persistencyData,
    setPersistencyData,
    loading,
    therapyArea,
    indication,
    brand,
    startDate,
    endDate,
    lots,
    showSnackbar,
    scenarioSelector,
    filterApplyVersion
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

    const { setLoading, isLoading } = useLoadingStore();

    const [curveRefreshKey, setCurveRefreshKey] = useState(0);

    const [curveOptions, setCurveOptions] = useState([]);

    const [selectedCurves, setSelectedCurves] = useState({});

    const [openCurveDialog, setOpenCurveDialog] = useState(false);

    const [selectedLotForCurve, setSelectedLotForCurve] =
        useState(null);

    const [selectedLots, setSelectedLots] = useState([]);
    const [selectedDemandLots, setSelectedDemandLots] = useState([]);

    const [avgVialsEditable, setAvgVialsEditable] = useState(false);

    const [demandVialsEditable, setDemandVialsEditable] = useState(false);

    const [inventoryEditable, setInventoryEditable] = useState(false);

    const [inventoryStockPercentage, setInventoryStockPercentage] = useState(persistencyData?.inventory_table?.stock_percentage || 0);

    const [originalInventoryStockPercentage, setOriginalInventoryStockPercentage,] = useState(persistencyData?.inventory_table?.stock_percentage || 0);

    const [openComplianceDialog, setOpenComplianceDialog,] = useState(false);
    const [complianceData, setComplianceData] = useState([]);

    const [openEditValuesDialog, setOpenEditValuesDialog] = useState(false);

    const isDataLoaded = persistencyData?.months?.length > 0;

    const isApplyCurveEnabled =
        selectedLots.length > 0 &&
        selectedLots.every(
            (lot) =>
                selectedCurves[lot] &&
                selectedCurves[lot].length > 0
        );

    useEffect(() => {
        setSelectedLots([]);
        setSelectedDemandLots([]);
        setSelectedCurves({});
    }, [filterApplyVersion]);

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

    const handleSaveAvgVials = async () => {
        try {
            setLoading(true);
            const payload = {
                ta_name: therapyArea,
                indication,
                brand,
                months: persistencyData?.months || [],
                avg_vials_per_dose_table: avgVialsRows.map((row) => ({
                    lot: row.lot,
                    values: row.children?.[0]?.values || [],
                })
                ),
                lots: lots,
                scenario_name: scenarioSelector,
            };
            const response = await saveAvgVials(payload);

            const updatedData = response?.data;

            if (updatedData) {
                setPersistencyData(
                    (prev) => ({
                        ...prev,

                        avg_vials_per_dose_table: updatedData?.avg_vials_per_dose_table || prev.avg_vials_per_dose_table,

                        demand_vials_table: updatedData?.demand_vials_table || prev.demand_vials_table,

                        inventory_table: updatedData?.inventory_table || prev.inventory_table,
                    })
                );

                setAvgVialsRows(updatedData.avg_vials_per_dose_table || []);
                setOriginalAvgVialsRows(updatedData.avg_vials_per_dose_table || []);
                // Demand Vials update
                setDemandVialsRows(updatedData?.demand_vials_table || []);
                setOriginalDemandVialsRows(updatedData?.demand_vials_table || []);
                setInventoryStockPercentage(updatedData?.inventory_table?.stock_percentage || 0);
                setOriginalInventoryStockPercentage(updatedData?.inventory_table?.stock_percentage || 0);
            }
            setAvgVialsEditable(false);
            showSnackbar("Avg vials applied successfully", "success");
        } catch (error) {
            console.error("Failed saving avg vials", error);
            showSnackbar("Failed saving avg vials", "error");
        } finally {
            setLoading(false);
        }
    };

    const persistencyRows = persistencyData?.persistency_table || [];

    const avgVialsRowsTable = persistencyData?.avg_vials_per_dose_table || [];

    const demandVialsRowsTable = persistencyData?.demand_vials_table || [];

    const inventoryTable = persistencyData?.inventory_table || {};

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

    const handleSaveDemandVials = async () => {
        try {
            setLoading(true);
            const payload = {
                ta_name: therapyArea,
                indication,
                brand,
                months: persistencyData?.months || [],
                scenario_name: scenarioSelector,
                demand_vials_table:
                    demandVialsRows
                        .filter((row) =>
                            row.lot !== "Total"
                        )
                        .map((row) => ({
                            lot: row.lot,
                            children:
                                row.children
                                    .filter(
                                        (child) =>
                                            child.label === "Compliance %" ||
                                            child.label === "(+) Absolute Adjustment" ||
                                            child.label === "(x) Adjustment %"
                                    )
                        })
                        )
            };

            console.log("payload----=>", payload)

            const response = await saveDemandAdjustments(payload);

            const updatedData = response?.data;
            if (updatedData) {
                setPersistencyData(
                    (prev) => ({
                        ...prev,

                        demand_vials_table: updatedData?.demand_vials_table || prev.demand_vials_table,
                        inventory_table: updatedData?.inventory_table || prev.inventory_table,
                    })
                );

                // Demand update
                setDemandVialsRows(updatedData?.demand_vials_table || []);

                setOriginalDemandVialsRows(updatedData?.demand_vials_table || []);

                // Inventory update
                setInventoryStockPercentage(updatedData?.inventory_table?.stock_percentage || 0);

                setOriginalInventoryStockPercentage(updatedData?.inventory_table?.stock_percentage || 0);
            }

            setDemandVialsEditable(false);
            showSnackbar("Demand vials applied successfully", "success");
        } catch (error) {
            console.error("Failed saving demand vials", error);
            showSnackbar("Failed saving demand vials", "error");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (therapyArea) {
            fetchCurveOptions();
        }
    }, [therapyArea, curveRefreshKey]);

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

    useEffect(() => {

        if (
            persistencyData?.inventory_table
        ) {

            setInventoryStockPercentage(
                persistencyData
                    ?.inventory_table
                    ?.stock_percentage || 0
            );

            setOriginalInventoryStockPercentage(
                persistencyData
                    ?.inventory_table
                    ?.stock_percentage || 0
            );
        }

    }, [persistencyData?.inventory_table]);

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
            const response = await getPersistencyCurves(therapyArea);
            setCurveOptions(response?.data?.curve_list || []);
        } catch (error) {
            console.error("Failed to fetch curve options", error);
            showSnackbar("Failed to fetch the list of curves", "error");
        }
    };

    const fetchComplianceConfiguration = async () => {
        try {
            const response = await getComplianceConfiguration(therapyArea, indication, brand, lots);

            const formattedData =
                response?.data?.compliance_configuration?.map(
                    (item) => ({
                        lot: item.lot,
                        value: item.compliance_percentage,
                    })
                ) || [];

            setComplianceData(formattedData);
        } catch (error) {
            console.error("Failed to fetch compliance config", error);
            showSnackbar("Failed to fetch compliance config", "error");
        }
    };

    const handleApplyCompliance = async (updatedData) => {
        try {
            setLoading(true);
            const payload = {
                ta_name: therapyArea,
                indication,
                brand,
                scenario_name: scenarioSelector,
                compliance_configuration:
                    updatedData.map(
                        (item) => ({
                            lot: item.lot,
                            compliance_percentage: Number(item.value),
                        })
                    ),
            };

            const response = await applyComplianceConfiguration(payload);

            const responseData = response?.data;
            if (responseData) {
                setPersistencyData(
                    (
                        prev
                    ) => ({
                        ...prev,

                        demand_vials_table:
                            responseData?.demand_vials_table ||

                            prev.demand_vials_table,

                        inventory_table:
                            responseData?.inventory_table ||

                            prev.inventory_table,
                    })
                );

                // Demand update
                setDemandVialsRows(
                    responseData?.demand_vials_table ||
                    []
                );

                setOriginalDemandVialsRows(
                    responseData?.demand_vials_table ||
                    []
                );

                // Inventory update
                setInventoryStockPercentage(
                    responseData
                        ?.inventory_table
                        ?.stock_percentage || 0
                );

                setOriginalInventoryStockPercentage(
                    responseData
                        ?.inventory_table
                        ?.stock_percentage || 0
                );
            }
            showSnackbar("Compliance configured successfully", "success");
        } catch (error) {
            console.error("Failed to configure compliance", error);
            showSnackbar("Failed to configure compliance", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleEditValuesApply = async (data) => {
        try {
            setLoading(true);
            const payload = {
                ta_name: therapyArea,
                indication,
                brand,
                lots: lots,
                scenario_name: scenarioSelector,
                edit_values_configuration: {
                    selected_lots: selectedDemandLots,
                    start_month: data.startMonth,
                    percentage_change_per_month: Number(data.percentageChange),
                    number_of_months: Number(data.numberOfMonths)
                }
            };

            const response = await applyEditComplianceRowValues(payload);

            const updatedData = response?.data;
            if (updatedData) {
                setPersistencyData(
                    prev => ({
                        ...prev,
                        demand_vials_table: updatedData?.demand_vials_table || prev.demand_vials_table,
                        inventory_table: updatedData?.inventory_table || prev.inventory_table
                    })
                );

                setDemandVialsRows(updatedData?.demand_vials_table || []);
                setOriginalDemandVialsRows(updatedData?.demand_vials_table || []);
                setInventoryStockPercentage(updatedData?.inventory_table?.stock_percentage || 0);
                setOriginalInventoryStockPercentage(updatedData?.inventory_table?.stock_percentage || 0);
            }
            showSnackbar("Edited values applied successfully", "success");
        } catch (error) {
            console.error("Failed to apply edited values", error);
            showSnackbar("Failed to apply edited values", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleSaveInventory = async () => {
        try {
            setLoading(true);
            const payload = {
                ta_name: therapyArea,
                indication,
                brand,
                months: persistencyData?.months || [],
                stock_percentage: Number(inventoryStockPercentage),
                scenario_name: scenarioSelector,
            };

            const response = await applyInventoryStockPercentage(payload);

            const updatedData = response?.data;
            if (updatedData) {
                setPersistencyData(
                    prev => ({
                        ...prev,
                        inventory_table: updatedData?.inventory_table || prev.inventory_table
                    })
                );
                setInventoryStockPercentage(updatedData?.inventory_table?.stock_percentage || 0);
                setOriginalInventoryStockPercentage(updatedData?.inventory_table?.stock_percentage || 0);
            }
            setInventoryEditable(false);
            showSnackbar("Inventory updated successfully", "success");
        } catch (error) {
            console.error("Failed saving inventory", error);
            showSnackbar("Failed to update inventory", "error");
        } finally {
            setLoading(false);
        }
    };

    const handleApplyCurve = async () => {
        try {
            setLoading(true);
            const lotCurveMapping =
                selectedLots
                    .filter(
                        (lot) =>
                            selectedCurves[lot]?.length
                    )
                    .map((lot) => ({
                        lot,
                        curves:
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
                lots: lots,
                scenario_name: scenarioSelector,
                lot_curve_mapping: lotCurveMapping,
            };

            const response = await applyPersistencyCurve(payload);
            setPersistencyData(response?.data || null);
            showSnackbar("Persistency curve applied successfully", "success");
        } catch (error) {
            console.error("Failed to apply persistency curve", error);
            showSnackbar("Failed to apply persistency curve", "error");
        } finally {
            setLoading(false);
        }
    };

    const getCurveSpans = (curveMapping = []) => {
        return curveMapping.map((curve) => {
            const startIndex =
                persistencyData?.months?.findIndex(
                    (month) =>
                        month === curve.start_date
                );

            const endIndex =
                persistencyData?.months?.findIndex(
                    (month) =>
                        month === curve.end_date
                );

            return {
                ...curve,
                colSpan:
                    endIndex -
                    startIndex +
                    1,
            };
        });
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
                        disabled={!isDataLoaded}
                        sx={{ textTransform: "none", borderRadius: "8px", height: "38px" }}
                    >
                        Configure Persistency
                    </Button>

                    <Button
                        variant="contained"
                        onClick={handleApplyCurve}
                        disabled={!isDataLoaded || !isApplyCurveEnabled}
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
                                                    sx={{ fontWeight: 600, fontSize: '15px' }} >
                                                    {persistencyData?.brand}{" "} - {row.lot}
                                                </Typography>

                                                <Button
                                                    variant="outlined"
                                                    size="small"
                                                    onClick={() => {
                                                        setSelectedLotForCurve(
                                                            row.lot
                                                        );

                                                        setOpenCurveDialog(true);
                                                    }}
                                                    sx={{
                                                        height: 32,
                                                        borderRadius: "8px",
                                                        textTransform: "none",
                                                        minWidth: "150px",
                                                    }}
                                                >
                                                    {selectedCurves[row.lot]?.length
                                                        ? `${selectedCurves[row.lot].length} Curves Configured`
                                                        : "Configure Curve"}
                                                </Button>
                                            </Box>
                                        </TableCell>

                                        {row.curve_mapping?.length > 0 ? (

                                            getCurveSpans(
                                                row.curve_mapping
                                            ).map((curve, index) => (

                                                <TableCell
                                                    key={`${curve.curve_name}-${index}`}
                                                    colSpan={curve.colSpan}
                                                    align="center"
                                                    sx={{
                                                        // backgroundColor:
                                                        //     index % 2 === 0
                                                        //         ? "#DBEAFE"
                                                        //         : "#DCFCE7",
                                                        // backgroundColor: "#fff",
                                                        color: "#1E293B",

                                                        fontWeight: 700,

                                                        fontSize: "13px",

                                                        borderRight:
                                                            "1px solid #CBD5E1",

                                                        whiteSpace: "nowrap",
                                                    }}
                                                >
                                                    {curve.curve_name}
                                                </TableCell>
                                            ))

                                        ) : (

                                            formattedMonths.map((_, idx) => (
                                                <TableCell
                                                    key={idx}
                                                    sx={{
                                                        backgroundColor:
                                                            "#f1f5f9",

                                                        borderRight:
                                                            "1px solid #CBD5E1",
                                                    }}
                                                />
                                            ))

                                        )}
                                    </TableRow>

                                    {row.children.map(
                                        (child) => (
                                            <TableRow key={child.label}>
                                                <TableCell
                                                    sx={{ pl: 3, position: "sticky", left: 0, backgroundColor: "#fff", zIndex: 3, borderRight: "1px solid #CBD5E1" }}
                                                >

                                                    <Typography sx={{ color: "#334155", fontSize: '15px' }} >
                                                        {child.label}
                                                    </Typography>
                                                </TableCell>

                                                {child.values.map((value, idx) => (
                                                    <TableCell
                                                        key={idx}
                                                        align="center"
                                                        sx={{ borderRight: "1px solid #CBD5E1", color: "#506784", fontSize: "14px", py: 1.2, }}
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
                            onClick={() => setAvgVialsEditable(true)}
                            disabled={!isDataLoaded || avgVialsEditable}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Edit
                        </Button>

                        <Button
                            variant="contained"
                            onClick={handleSaveAvgVials}
                            disabled={!isDataLoaded}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", backgroundColor: "#4F46E5", fontWeight: 700, }}
                        >
                            Apply
                        </Button>
                        {/* {avgVialsEditable && ( */}
                        <Button
                            variant="outlined"
                            onClick={handleCancelAvgVials}
                            disabled={!isDataLoaded}
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
                        {avgVialsRows.length > 0 && (
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
                        )}

                        <TableBody>
                            {!avgVialsRows.length ? (
                                <TableRow>
                                    <TableCell
                                        colSpan={formattedMonths.length + 1}
                                        align="center"
                                        sx={{ py: 5, color: "#94a3b8", fontWeight: 600 }}
                                    >
                                        No avg vials per dose data available. Please apply filters.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                avgVialsRows.map((row, rowIndex) => (
                                    <React.Fragment key={row.lot}>
                                        {row.children.map((child, childIndex) => (
                                            <TableRow key={child.label}>
                                                <TableCell
                                                    sx={{ pl: 2, position: "sticky", left: 0, backgroundColor: "#fff", zIndex: 3, borderRight: "1px solid #CBD5E1", color: "#334155", fontSize: '15px' }}
                                                >
                                                    {child.label}
                                                </TableCell>

                                                {child.values.map((value, idx) => (
                                                    <TableCell
                                                        key={idx}
                                                        align="center"
                                                        sx={{ borderRight: "1px solid #CBD5E1", color: "#334155", height: "36px", py: 0, }}
                                                    >
                                                        <Box
                                                            sx={{
                                                                width: "40px", height: "20px", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto", fontSize: "14px", color: "#506784", lineHeight: 1,
                                                                // borderRadius: "6px",

                                                                // backgroundColor:
                                                                //     avgVialsEditable
                                                                //         ? "#EEF2FF"
                                                                //         : "transparent",

                                                                // border:
                                                                //     avgVialsEditable
                                                                //         ? "1px solid #C7D2FE"
                                                                //         : "1px solid transparent",

                                                                // fontWeight:
                                                                //     avgVialsEditable
                                                                //         ? 700
                                                                //         : 500,

                                                                // transition:
                                                                //     "all 0.2s ease",
                                                            }}
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
                                                                    // style={{
                                                                    //     width: "100%", height: "100%", border: "none",
                                                                    //     outline: "none", background: "transparent", textAlign: "center",
                                                                    //     fontSize: "14px", fontFamily: "inherit", color: "#506784",
                                                                    //     padding: 0, margin: 0, lineHeight: 1, fontWeight: 500
                                                                    // }}

                                                                    style={{
                                                                        width: "46px",
                                                                        height: "25px",
                                                                        boxSizing: "border-box",
                                                                        display: "inline-block",
                                                                        verticalAlign: "middle",
                                                                        border: "1px solid #93c5fd",
                                                                        borderRadius: "4px",
                                                                        outline: "none",
                                                                        background: "#eff6ff",
                                                                        color: "#1e293b",
                                                                        textAlign: "center",
                                                                        fontSize: "14px",
                                                                        lineHeight: "20px",
                                                                        padding: "1px 4px",
                                                                    }}
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

                    <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", }}>
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                gap: 0.8,
                            }}
                        >
                            {isDataLoaded && (
                                <Tooltip
                                    title="Select one or more checkboxes to enable Edit Values"
                                    arrow
                                    placement="top"
                                >
                                    <InfoOutlinedIcon
                                        sx={{
                                            fontSize: "18px",
                                            color: "#64748B",
                                            cursor: "pointer",
                                        }}
                                    />
                                </Tooltip>
                            )}
                            <Button
                                variant="outlined"
                                onClick={() =>
                                    setOpenEditValuesDialog(true)
                                }
                                disabled={
                                    !isDataLoaded ||
                                    selectedDemandLots.length === 0
                                }
                                sx={{
                                    height: "32px",
                                    minWidth: "80px",
                                    textTransform: "none",
                                    borderRadius: "8px",
                                    fontWeight: 700,
                                }}
                            >
                                Edit Values
                            </Button>
                        </Box>
                        <Button
                            variant="outlined"
                            onClick={async () => {
                                await fetchComplianceConfiguration();
                                setOpenComplianceDialog(
                                    true
                                );
                            }}
                            disabled={!isDataLoaded || demandVialsEditable}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Configure Compliance
                        </Button>
                        <Button
                            variant="outlined"
                            onClick={() => setDemandVialsEditable(true)}
                            disabled={!isDataLoaded || demandVialsEditable}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Edit
                        </Button>

                        <Button
                            variant="contained"
                            onClick={handleSaveDemandVials}
                            disabled={!isDataLoaded}
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
                            disabled={!isDataLoaded}
                            sx={{ height: "32px", minWidth: "80px", textTransform: "none", borderRadius: "8px", fontWeight: 700, }}
                        >
                            Cancel
                        </Button>
                        {/* )} */}
                    </Box>
                </Box>

                <TableContainer
                    sx={{
                        border: "1px solid #D8DEE8",
                        borderRadius: "12px",
                        overflowX: "auto",
                    }}
                >
                    <Table
                        size="small"
                        sx={{
                            minWidth: "max-content",
                        }}
                    >
                        {demandVialsRows.length > 0 && (
                            <TableHead>
                                <TableRow>

                                    <TableCell
                                        sx={{
                                            fontWeight: 700,
                                            minWidth: 320,
                                            position: "sticky",
                                            left: 0,
                                            backgroundColor: "#fff",
                                            zIndex: 5,
                                            borderRight:
                                                "1px solid #CBD5E1",
                                        }}
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
                                                backgroundColor:
                                                    "#f8fafc",
                                                borderRight:
                                                    "1px solid #CBD5E1",
                                            }}
                                        >
                                            {month}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            </TableHead>
                        )}

                        <TableBody>
                            {!demandVialsRows.length ? (
                                <TableRow>
                                    <TableCell
                                        colSpan={formattedMonths.length + 1}
                                        align="center"
                                        sx={{ py: 5, color: "#94a3b8", fontWeight: 600 }}
                                    >
                                        No demand(vials) data available. Please apply filters.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                demandVialsRows.map((row, rowIndex) => (
                                    <React.Fragment
                                        key={row.lot}
                                    >
                                        {row.children.map((child, childIndex) => (
                                            <TableRow
                                                key={
                                                    child.label
                                                }
                                                sx={{
                                                    backgroundColor:
                                                        row.lot === "Total"
                                                            ? "#E2E8F0" // stronger highlight for total row
                                                            : child.label.includes("Vials")
                                                                ? "#F1F5F9"
                                                                : "#fff",
                                                }}
                                            >

                                                <TableCell
                                                    sx={{
                                                        pl:
                                                            row.lot !==
                                                                "Total" &&
                                                                child.label.includes(
                                                                    "Vials"
                                                                )
                                                                ? 1
                                                                : 3,

                                                        position:
                                                            "sticky",

                                                        left: 0,

                                                        backgroundColor:
                                                            row.lot === "Total"
                                                                ? "#E2E8F0"
                                                                : child.label.includes("Vials")
                                                                    ? "#F1F5F9"
                                                                    : "#fff",

                                                        zIndex: 3,

                                                        borderRight:
                                                            "1px solid #CBD5E1",

                                                        fontWeight:
                                                            child.label.includes("Vials") ||
                                                                row.lot === "Total"
                                                                ? 700
                                                                : 400,
                                                    }}
                                                >

                                                    <Box
                                                        sx={{
                                                            display:
                                                                "flex",

                                                            alignItems:
                                                                "center",

                                                            gap: 1.5,
                                                        }}
                                                    >

                                                        {row.lot !==
                                                            "Total" &&
                                                            child.label.includes(
                                                                "Vials"
                                                            ) && (
                                                                <Checkbox
                                                                    checked={
                                                                        selectedDemandLots.includes(
                                                                            row.lot
                                                                        )
                                                                    }
                                                                    onChange={(e) => {

                                                                        if (
                                                                            e.target.checked
                                                                        ) {

                                                                            setSelectedDemandLots(
                                                                                prev => [
                                                                                    ...prev,
                                                                                    row.lot
                                                                                ]
                                                                            );

                                                                        } else {

                                                                            setSelectedDemandLots(
                                                                                prev =>
                                                                                    prev.filter(
                                                                                        item =>
                                                                                            item !== row.lot
                                                                                    )
                                                                            );
                                                                        }

                                                                    }}
                                                                />
                                                            )}

                                                        <Typography
                                                            sx={{
                                                                fontWeight:
                                                                    child.label.includes("Vials") ||
                                                                        row.lot === "Total"
                                                                        ? 700
                                                                        : 400,

                                                                fontSize:
                                                                    "15px",

                                                                color:
                                                                    "#334155",
                                                            }}
                                                        >
                                                            {
                                                                child.label
                                                            }
                                                        </Typography>
                                                    </Box>
                                                </TableCell>

                                                {child.values.map(
                                                    (
                                                        value,
                                                        idx
                                                    ) => (

                                                        <TableCell
                                                            key={idx}
                                                            align="center"
                                                            sx={{
                                                                borderRight:
                                                                    "1px solid #CBD5E1",

                                                                color:
                                                                    "#334155",

                                                                fontSize:
                                                                    "14px",

                                                                height:
                                                                    "36px",

                                                                py: 0,

                                                                // backgroundColor:
                                                                //     row.lot === "Total"
                                                                //         ? "#E2E8F0"
                                                                //         : "inherit",

                                                                fontWeight:
                                                                    child.label.includes("Vials") ||
                                                                        row.lot === "Total"
                                                                        ? 700
                                                                        : 400,
                                                            }}
                                                        >
                                                            <Box
                                                                sx={{
                                                                    width: "40px",
                                                                    height: "20px",
                                                                    display: "flex",
                                                                    alignItems: "center",
                                                                    justifyContent: "center",
                                                                    margin: "0 auto",
                                                                    fontSize: "13px",
                                                                    color: "#506784",
                                                                    lineHeight: 1,
                                                                }}
                                                            >

                                                                {demandVialsEditable &&
                                                                    (
                                                                        child.label ===
                                                                        "Compliance %" ||

                                                                        child.label ===
                                                                        "(+) Absolute Adjustment" ||

                                                                        child.label ===
                                                                        "(x) Adjustment %"
                                                                    ) ? (

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

                                                                                handleDemandVialsCellChange(
                                                                                    rowIndex,
                                                                                    childIndex,
                                                                                    idx,
                                                                                    input
                                                                                );
                                                                            }
                                                                        }}
                                                                        // style={{
                                                                        //     width: "100%",
                                                                        //     // height: "20px",
                                                                        //     // display: "block",
                                                                        //     height: "100%",
                                                                        //     border: "none",
                                                                        //     outline: "none",
                                                                        //     background: "transparent",
                                                                        //     textAlign: "center",
                                                                        //     fontSize: "13px",
                                                                        //     fontFamily: "inherit",
                                                                        //     color: "#506784",
                                                                        //     padding: 0,
                                                                        //     margin: 0,
                                                                        //     lineHeight: 1,
                                                                        //     fontWeight: 500
                                                                        // }}

                                                                        style={{
                                                                            width: "46px",
                                                                            height: "25px",
                                                                            boxSizing: "border-box",
                                                                            display: "inline-block",
                                                                            verticalAlign: "middle",
                                                                            border: "1px solid #93c5fd",
                                                                            borderRadius: "4px",
                                                                            outline: "none",
                                                                            background: "#eff6ff",
                                                                            color: "#1e293b",
                                                                            textAlign: "center",
                                                                            fontSize: "14px",
                                                                            lineHeight: "20px",
                                                                            padding: "1px 4px",
                                                                        }}
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
                                )
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>

            {/* =========================================
            INVENTORY TABLE
            ========================================= */}

            <Box sx={{ mt: 5 }}>

                {/* HEADER */}
                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        mb: 1.5,
                    }}
                >

                    <Typography
                        sx={{
                            fontSize: "18px",
                            fontWeight: 700,
                        }}
                    >
                        Inventory (Vials)
                    </Typography>

                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1.5,

                        }}
                    >
                        {inventoryTable?.children?.length > 0 && (
                            <>
                                <Typography
                                    sx={{
                                        fontWeight: 600,
                                        color: "#64748B",
                                        fontSize: "14px",
                                    }}
                                >
                                    Stock %:
                                </Typography>

                                <input
                                    value={
                                        inventoryStockPercentage
                                    }
                                    disabled={!inventoryEditable}
                                    onChange={(e) => {

                                        const input =
                                            e.target.value;

                                        if (
                                            /^\d*\.?\d*$/.test(
                                                input
                                            )
                                        ) {

                                            setInventoryStockPercentage(
                                                input
                                            );
                                        }
                                    }}
                                    style={{
                                        width: "70px",
                                        height: "32px",
                                        border:
                                            "1px solid #CBD5E1",
                                        borderRadius: "8px",
                                        textAlign: "center",
                                        outline: "none",
                                        fontSize: "13px",
                                        backgroundColor:
                                            inventoryEditable
                                                ? "#fff"
                                                : "#F8FAFC",
                                    }}
                                />
                            </>
                        )}

                        <Button
                            variant="outlined"
                            onClick={() => setInventoryEditable(true)}
                            disabled={!isDataLoaded || inventoryEditable}
                            sx={{
                                height: "32px",
                                minWidth: "80px",
                                textTransform: "none",
                                borderRadius: "8px",
                                fontWeight: 700,
                            }}
                        >
                            Edit
                        </Button>

                        <Button
                            variant="contained"
                            disabled={!isDataLoaded}
                            onClick={handleSaveInventory}
                            sx={{
                                height: "32px",
                                minWidth: "80px",
                                textTransform: "none",
                                borderRadius: "8px",
                                backgroundColor: "#4F46E5",
                                fontWeight: 700,
                            }}
                        >
                            Apply
                        </Button>

                        {/* {inventoryEditable && ( */}
                        <Button
                            variant="outlined"
                            onClick={() => {

                                setInventoryStockPercentage(
                                    originalInventoryStockPercentage
                                );

                                setInventoryEditable(
                                    false
                                );
                            }}
                            disabled={!isDataLoaded}
                            sx={{
                                height: "32px",
                                minWidth: "80px",
                                textTransform: "none",
                                borderRadius: "8px",
                                fontWeight: 700,
                            }}
                        >
                            Cancel
                        </Button>
                        {/* )} */}
                    </Box>
                </Box>

                {/* TABLE */}
                <TableContainer
                    sx={{
                        border:
                            "1px solid #D8DEE8",
                        borderRadius: "12px",
                        overflowX: "auto",
                    }}
                >
                    <Table
                        size="small"
                        sx={{
                            minWidth: "max-content",
                        }}
                    >

                        {inventoryTable?.children?.length > 0 && (
                            <TableHead>
                                <TableRow>
                                    <TableCell
                                        sx={{
                                            fontWeight: 700,
                                            minWidth: 320,
                                            position:
                                                "sticky",
                                            left: 0,
                                            backgroundColor:
                                                "#fff",
                                            zIndex: 5,
                                            borderRight:
                                                "1px solid #CBD5E1",
                                        }}
                                    >
                                        Metric
                                    </TableCell>

                                    {formattedMonths.map(
                                        (month) => (
                                            <TableCell
                                                key={
                                                    month
                                                }
                                                align="center"
                                                sx={{
                                                    fontWeight: 700,
                                                    minWidth: 72,
                                                    fontSize:
                                                        "13px",
                                                    height:
                                                        "36px",
                                                    py: 0,
                                                    backgroundColor:
                                                        "#f8fafc",
                                                    borderRight:
                                                        "1px solid #CBD5E1",
                                                }}
                                            >
                                                {month}
                                            </TableCell>
                                        )
                                    )}
                                </TableRow>
                            </TableHead>
                        )}

                        <TableBody>

                            {!inventoryTable?.children?.length ? (
                                <TableRow>
                                    <TableCell
                                        colSpan={
                                            formattedMonths.length +
                                            1
                                        }
                                        align="center"
                                        sx={{
                                            py: 5,
                                            color:
                                                "#94a3b8",
                                            fontWeight: 600,
                                        }}
                                    >
                                        No inventory data
                                        available.
                                        Please apply
                                        filters.
                                    </TableCell>
                                </TableRow>

                            ) : (

                                inventoryTable.children.map(
                                    (child) => (

                                        <TableRow
                                            key={
                                                child.label
                                            }
                                        >

                                            <TableCell
                                                sx={{
                                                    pl: 2,
                                                    position: "sticky",
                                                    left: 0,
                                                    backgroundColor: "#fff",
                                                    zIndex: 3,
                                                    borderRight: "1px solid #CBD5E1",
                                                    color: "#334155",
                                                    fontSize: "15px"
                                                    // fontWeight: 500,
                                                }}
                                            >
                                                {
                                                    child.label
                                                }
                                            </TableCell>

                                            {child.values.map(
                                                (
                                                    value,
                                                    idx
                                                ) => (

                                                    <TableCell
                                                        key={idx}
                                                        align="center"
                                                        sx={{
                                                            borderRight: "1px solid #CBD5E1",
                                                            color: "#506784",
                                                            fontSize: "14px",
                                                            height: "36px",
                                                            py: 0,
                                                        }}
                                                    >
                                                        {value}
                                                    </TableCell>
                                                )
                                            )}
                                        </TableRow>
                                    )
                                )
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>

            {/* Persistency Dialog */}
            <PersistencyConfiguration
                open={openPersistencyDialog}
                onClose={() =>
                    setOpenPersistencyDialog(false)
                }
                therapyArea={therapyArea}
                onCurveUpdated={() =>
                    setCurveRefreshKey(
                        (prev) => prev + 1
                    )
                }
                showSnackbar={showSnackbar}
            />
            <ConfigureComplianceDialog
                open={openComplianceDialog}
                onClose={() =>
                    setOpenComplianceDialog(false)
                }
                complianceData={
                    complianceData
                }
                brand={brand}
                onApply={async (updatedData) => {
                    setComplianceData(updatedData);
                    await handleApplyCompliance(updatedData);
                }}
            />

            <EditValuesDialog
                open={openEditValuesDialog}
                onClose={() => setOpenEditValuesDialog(false)}
                months={persistencyData?.months || []}
                onApply={
                    handleEditValuesApply
                }
            />

            <ConfigureCurveDialog
                open={openCurveDialog}
                onClose={() =>
                    setOpenCurveDialog(false)
                }
                lot={selectedLotForCurve}
                curveOptions={curveOptions}
                months={
                    persistencyData?.months || []
                }
                selectedCurves={selectedCurves}
                setSelectedCurves={setSelectedCurves}
            />
        </Box >
    );
}
