import React, { useState, useEffect, useRef } from "react";
import { Box, Typography, Dialog, IconButton, Button, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, DialogTitle, DialogContent, DialogContentText, DialogActions, Menu, MenuItem as DropdownMenuItem, TextField } from "@mui/material";
import MoreVertIcon from "@mui/icons-material/MoreVert";
// import Tooltip from "@mui/material/Tooltip";
// import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import Plot from "react-plotly.js";
import CloseIcon from "@mui/icons-material/Close";
// import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { useLoadingStore } from "../../../stores";
import ExcelJS from "exceljs";
import { saveAs } from "file-saver";

import { getPersistencyCurves, getPersistencyCurveDetails, deletePersistencyCurve, uploadPersistencyCurve, updatePersistencyCurve } from "../../../services/apiService";

const PlotComponent = Plot.default || Plot;

export default function PersistencyConfiguration({
    open,
    onClose,
    therapyArea,
    onCurveUpdated,
    showSnackbar
}) {
    const [curveRows, setCurveRows] = useState([]);

    const [selectedFile, setSelectedFile] = useState(null);

    const [uploadLoading, setUploadLoading] =
        useState(false);

    const [selectedRowIndex, setSelectedRowIndex] =
        useState(null);

    const [openDeleteDialog, setOpenDeleteDialog] =
        useState(false);

    const fileInputRef = useRef(null);

    const [isEditMode, setIsEditMode] = useState(false);

    const [editableValues, setEditableValues] = useState([]);

    const [isCurveLoaded, setIsCurveLoaded] = useState(false);

    // const [persistencyConfig, setPersistencyConfig] =
    //     useState({
    //         curve_name: "",
    //         start_month: "",
    //         end_month: "",
    //         start_value: "",
    //         end_value: "",
    //         method: "",
    //         k_value: "",
    //     });

    const [curvePreview, setCurvePreview] =
        useState({
            curve_name: "",
            months: [],
            values: [],
        });

    // const methodLabelMapping = {
    //     linear: "Linear",
    //     "s-curve": "S-Curve",
    //     exponential: "Exponential",
    //     logarithmic: "Logarithmic",
    // };

    const [menuAnchorEl, setMenuAnchorEl] =
        useState(null);

    const resetPersistencyForm = () => {

        setSelectedFile(null);

        setCurvePreview({
            curve_name: "",
            months: [],
            values: [],
        });

        setEditableValues([]);
        setIsEditMode(false);
        setIsCurveLoaded(false);

    };

    const { setLoading, isLoading } = useLoadingStore();

    const handleDeleteCurve = async () => {
        try {
            setLoading(true);
            const selectedCurve = curveRows[selectedRowIndex];
            if (!selectedCurve) return;

            const response = await deletePersistencyCurve(selectedCurve.curve_name);
            setCurveRows(response?.data?.curve_list || []);
            onCurveUpdated?.();

            // if currently opened curve deleted
            resetPersistencyForm();
            setOpenDeleteDialog(false);
            setSelectedRowIndex(null);
            showSnackbar("Curve was deleted successfully", "success");
        } catch (error) {
            console.error("Failed to delete curve", error);
            showSnackbar("Failed to delete the curve", "error");
        }
        finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (open && therapyArea) {
            fetchPersistencyCurves();
        }
    }, [open, therapyArea]);

    const fetchPersistencyCurves = async () => {
        try {
            // setLoading(true);
            const response = await getPersistencyCurves(therapyArea);
            setCurveRows(response?.data?.curve_list || []);
        } catch (error) {
            console.error("Failed to fetch persistency curves", error);
            showSnackbar("Failed to fetch the list of curves", "error");
        }
        // finally {
        //     setLoading(false);
        // }
    };

    const handleFileChange = (
        event
    ) => {

        const file =
            event.target.files[0];

        if (!file) return;

        if (
            !file.name
                .toLowerCase()
                .endsWith(".xlsx")
        ) {

            showSnackbar(
                "Only .xlsx files are allowed.",
                "error"
            );

            return;

        }

        if (
            file.size >
            5 * 1024 * 1024
        ) {

            showSnackbar(
                "Maximum file size is 5 MB.",
                "error"
            );

            return;

        }

        setSelectedFile(file);

    };

    const handleUploadPersistency = async () => {

        if (!selectedFile) {
            showSnackbar(
                "Please choose a file.",
                "warning"
            );
            return;
        }

        try {

            setLoading(true);
            setUploadLoading(true);

            const formData = new FormData();

            formData.append(
                "file",
                selectedFile
            );

            formData.append(
                "ta_name",
                therapyArea
            );

            const response =
                await uploadPersistencyCurve(
                    formData
                );

            const responseData =
                response.data;

            // Refresh Curve List
            setCurveRows(
                responseData.curve_list || []
            );

            // Show uploaded curve preview
            setCurvePreview({
                curve_name:
                    responseData.curve_preview
                        ?.curve_name || "",

                months:
                    responseData.curve_preview
                        ?.months || [],

                values:
                    responseData.curve_preview
                        ?.values || [],
            });

            setEditableValues(
                responseData.curve_preview?.values || []
            );

            setIsCurveLoaded(true);

            // Clear selected file
            setSelectedFile(null);

            // Clear file input so same file can be uploaded again
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }

            onCurveUpdated?.();

            showSnackbar(
                "Persistency curve uploaded successfully.",
                "success"
            );

        } catch (error) {

            console.error(error);

            showSnackbar(
                error?.response?.data?.detail ||
                "Failed to upload persistency.",
                "error"
            );

        } finally {
            setUploadLoading(false);
            setLoading(false);
        }

    };

    const handleDownloadTemplate = async () => {

        const workbook = new ExcelJS.Workbook();

        const worksheet = workbook.addWorksheet("Persistency Template");

        // -------------------------------------------------
        // Instructions
        // -------------------------------------------------

        worksheet.mergeCells("A1:K1");

        const titleCell = worksheet.getCell("A1");

        titleCell.value = "Instruction:";

        titleCell.font = {
            bold: true,
            size: 14,
        };

        worksheet.mergeCells("A2:K2");

        worksheet.getCell("A2").value =
            "1. Update the curve names and their persistency values in the Excel. The template supports updating multiple curves simultaneously.";

        worksheet.getCell("A2").font = {
            size: 12,
        };

        worksheet.mergeCells("A3:K3");

        worksheet.getCell("A3").value =
            "2. If more months are needed, add Mn and enter the values.";

        worksheet.getCell("A3").font = {
            size: 12,
        };

        worksheet.addRow([]);

        // -------------------------------------------------
        // Header Row
        // -------------------------------------------------

        const header = ["Curve name"];

        for (let i = 1; i <= 14; i++) {
            header.push(`M${i}`);
        }

        const headerRow = worksheet.addRow(header);

        headerRow.eachCell((cell) => {

            cell.font = {
                bold: true,
            };

            cell.alignment = {
                horizontal: "center",
                vertical: "middle",
            };

            cell.border = {
                top: { style: "thin" },
                left: { style: "thin" },
                bottom: { style: "thin" },
                right: { style: "thin" },
            };

        });

        // -------------------------------------------------
        // Empty Editable Rows
        // -------------------------------------------------

        const numberOfRows = 5;

        for (let i = 0; i < numberOfRows; i++) {

            const row = worksheet.addRow(
                new Array(15).fill("")
            );

            row.height = 22;

            row.eachCell((cell) => {

                // cell.fill = {
                //     type: "pattern",
                //     pattern: "solid",
                //     // fgColor: {
                //     //     argb: "FFFFFF00",
                //     // },
                // };

                cell.border = {
                    top: { style: "thin" },
                    left: { style: "thin" },
                    bottom: { style: "thin" },
                    right: { style: "thin" },
                };

                cell.alignment = {
                    horizontal: "center",
                    vertical: "middle",
                };

            });

        }

        // -------------------------------------------------
        // Column Width
        // -------------------------------------------------

        worksheet.getColumn(1).width = 22;

        for (let i = 2; i <= 15; i++) {
            worksheet.getColumn(i).width = 12;
        }

        const buffer = await workbook.xlsx.writeBuffer();

        saveAs(
            new Blob([buffer]),
            "Persistency_Template.xlsx"
        );

    };

    const handleConfigureCurve = async (
        curveName
    ) => {

        try {
            setLoading(true);

            const response =
                await getPersistencyCurveDetails(
                    curveName
                );

            setCurvePreview({
                curve_name:
                    response.data.curve_preview
                        ?.curve_name,

                months:
                    response.data.curve_preview
                        ?.months || [],

                values:
                    response.data.curve_preview
                        ?.values || [],
            });

            setEditableValues(
                response.data.curve_preview.values
            );

            setIsEditMode(false);

            setIsCurveLoaded(true);

        } catch (error) {

            console.error(error);

            showSnackbar(
                "Failed to load curve.",
                "error"
            );

        } finally {
            setLoading(false);
        }

    };

    // const handleCalculateApply = async () => {
    //     try {
    //         // setLoading(true);
    //         const payload = {
    //             ta_name: therapyArea,
    //             curve_name: persistencyConfig.curve_name,
    //             start_month: Number(persistencyConfig.start_month),
    //             end_month: Number(persistencyConfig.end_month),
    //             start_value: Number(persistencyConfig.start_value),
    //             end_value: Number(persistencyConfig.end_value),
    //             method: persistencyConfig.method.toLowerCase(),
    //             k_factor:
    //                 persistencyConfig.method ===
    //                     "Linear"
    //                     ? 0
    //                     : Number(
    //                         persistencyConfig.k_value
    //                     ),
    //         };
    //         const response = await calculateApplyPersistencyCurve(payload);
    //         setCurvePreview(response.data.curve_preview);
    //         setCurveRows(response.data.curve_list);

    //         // fetch the updated curve list
    //         onCurveUpdated?.();
    //         showSnackbar("New curve added successfully", "success");
    //     } catch (error) {
    //         console.error("Failed to add new curve", error);
    //         showSnackbar("Failed to add new curve", "error");
    //     }
    //     // finally {
    //     //     setLoading(false);
    //     // }
    // };

    const handleEdit = () => {

        setEditableValues([
            ...curvePreview.values
        ]);

        setIsEditMode(true);

    };

    const handleCancel = () => {

        setEditableValues([
            ...curvePreview.values
        ]);

        setIsEditMode(false);

    };

    const handleOpenMenu = (
        event,
        rowIndex
    ) => {
        setMenuAnchorEl(event.currentTarget);
        setSelectedRowIndex(rowIndex);
    };

    const handleCloseMenu = () => {
        setMenuAnchorEl(null);
    };

    const handleApplyEdit = async () => {

        try {
            setLoading(true);

            // ----------------------------
            // Validation
            // ----------------------------

            const hasInvalidValue =
                editableValues.some(
                    (value) =>
                        value === "" ||
                        value === null ||
                        value === undefined ||
                        Number.isNaN(Number(value))
                );

            if (hasInvalidValue) {

                showSnackbar(
                    "Please enter valid values for all months.",
                    "warning"
                );

                return;

            }

            // ----------------------------
            // Payload
            // ----------------------------

            const payload = {

                ta_name: therapyArea,

                curve_name:
                    curvePreview.curve_name,

                months:
                    curvePreview.months,

                values:
                    editableValues.map(Number),

            };

            // ----------------------------
            // API
            // ----------------------------

            const response =
                await updatePersistencyCurve(
                    payload
                );

            const responseData =
                response.data;

            // ----------------------------
            // Update Preview
            // ----------------------------

            setCurvePreview({
                curve_name:
                    responseData.curve_preview
                        ?.curve_name,

                months:
                    responseData.curve_preview
                        ?.months || [],

                values:
                    responseData.curve_preview
                        ?.values || [],
            });

            setEditableValues(
                responseData.curve_preview
                    ?.values || []
            );

            setIsEditMode(false);

            showSnackbar(
                responseData.message ||
                "Curve updated successfully.",
                "success"
            );

        } catch (error) {

            console.error(error);

            showSnackbar(
                error?.response?.data?.detail ||
                "Failed to update curve.",
                "error"
            );

        } finally {
            setLoading(false);
        }

    };

    // const handleDuplicateCurve = async () => {
    //     try {
    //         const selectedCurve = curveRows[selectedRowIndex];
    //         if (!selectedCurve) return;
    //         const response = await getPersistencyCurveDetails(selectedCurve.curve_name);
    //         const curveDetails = response?.data?.curve_details;

    //         setPersistencyConfig({
    //             curve_name: `${curveDetails?.curve_name}_duplicate`,
    //             start_month: curveDetails?.start_month || "",
    //             end_month: curveDetails?.end_month || "",
    //             start_value: curveDetails?.start_value || "",
    //             end_value: curveDetails?.end_value || "",
    //             method:
    //                 methodLabelMapping[
    //                 curveDetails?.method
    //                 ] || "",
    //             k_value: curveDetails?.k_factor ?? "",
    //         });

    //         setCurvePreview(
    //             response?.data?.curve_preview || {
    //                 months: [],
    //                 values: [],
    //             }
    //         );
    //         handleCloseMenu();
    //     } catch (error) {
    //         console.error("Failed to duplicate curve", error);
    //     }
    // };

    return (
        <Dialog
            open={open}
            onClose={() => {
                resetPersistencyForm();
                onClose();
            }}
            maxWidth={false}
            PaperProps={{
                sx: {
                    width: "1350px",
                    height: "700px",
                    maxWidth: "95vw",
                    maxHeight: "90vh",
                    borderRadius: "16px",
                    overflow: "hidden",
                },
            }}
        >
            <Box
                sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", px: 3, py: 2, borderBottom: "1px solid #E2E8F0", }}
            >
                <Typography sx={{ fontSize: "20px", fontWeight: 700 }}>
                    Persistency Management
                </Typography>

                <IconButton
                    onClick={() => {
                        resetPersistencyForm();
                        onClose();
                    }}
                >
                    <CloseIcon />
                </IconButton>
            </Box>

            <Box sx={{ p: 3, flex: 1, overflowY: "auto" }}>
                <Typography
                    sx={{
                        fontSize: "18px",
                        fontWeight: 700,
                        mb: 2
                    }}
                >
                    Persistency Template
                </Typography>

                <Typography
                    sx={{
                        color: "#64748B",
                        fontSize: "15px",
                        mb: 2
                    }}
                >
                    Download the template, enter the curve name and monthly persistency values, then upload the completed Excel file.
                </Typography>

                <Box
                    sx={{
                        display: "flex",
                        gap: 2,
                        alignItems: "center",
                        mb: 4
                    }}
                >
                    <Button
                        variant="outlined"
                        onClick={handleDownloadTemplate}
                        sx={{
                            borderRadius: "10px",
                            textTransform: "none",
                            height: 42,
                            px: 3
                        }}
                    >
                        Download Format (.xlsx)
                    </Button>
                </Box>

                <Box
                    sx={{
                        borderTop: "1px solid #E2E8F0",
                        pt: 4,
                        mb: 4
                    }}
                >
                    <Typography
                        sx={{
                            fontWeight: 700,
                            color: "#64748B",
                            mb: 2
                        }}
                    >
                        UPLOAD PERSISTENCY FILE
                    </Typography>

                    <Box
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 2
                        }}
                    >
                        <Button
                            component="label"
                            variant="outlined"
                            sx={{
                                textTransform: "none",
                                borderRadius: "8px"
                            }}
                        >
                            Choose File

                            <input
                                ref={fileInputRef}
                                hidden
                                type="file"
                                accept=".xlsx"
                                onChange={handleFileChange}
                            />
                        </Button>

                        <Typography
                            sx={{
                                color: "#64748B"
                            }}
                        >
                            {selectedFile
                                ? selectedFile.name
                                : "No file chosen"}
                        </Typography>

                        <Button
                            variant="contained"
                            disabled={
                                !selectedFile ||
                                uploadLoading
                            }
                            onClick={
                                handleUploadPersistency
                            }
                            sx={{
                                textTransform: "none",
                                borderRadius: "10px",
                                minWidth: 170
                            }}
                        >
                            {
                                uploadLoading
                                    ? "Uploading..."
                                    : "Upload"
                            }
                        </Button>
                    </Box>
                </Box>

                {/* </Box> */}

                {/* table+chart */}
                <Box
                    sx={{
                        display: "flex",
                        gap: 3,
                        alignItems: "flex-start",
                        mt: 2,
                    }}
                >
                    {/* LEFT SIDE */}
                    <Box sx={{ width: "450px", flexShrink: 0 }}>
                        {/* Header */}
                        <Box
                            sx={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                mb: 2,
                            }}
                        >
                            <Typography sx={{ fontSize: "18px", fontWeight: 700 }}>
                                Persistency Curves
                            </Typography>

                            {/* <Button
                                variant="contained"
                                onClick={resetPersistencyForm}
                                sx={{
                                    textTransform: "none",
                                    borderRadius: "10px",
                                    px: 2,
                                    height: "35px",
                                    backgroundColor: "#4F46E5",
                                    fontWeight: 700,
                                }}
                            >
                                + Add New
                            </Button> */}
                        </Box>

                        {/* Table */}
                        <TableContainer
                            sx={{
                                border: "1px solid #D8DEE8",
                                borderRadius: "12px",
                                maxHeight: "300px",
                                overflowY: "auto",
                                overflowX: "hidden",
                            }}
                        >
                            <Table stickyHeader>
                                <TableHead>
                                    <TableRow sx={{ backgroundColor: "#f8fafc" }}>
                                        <TableCell
                                            sx={{
                                                fontWeight: 700,
                                                color: "#64748b",
                                                fontSize: "16px",
                                            }}
                                        >
                                            Curve Name
                                        </TableCell>

                                        <TableCell
                                            align="right"
                                            sx={{
                                                fontWeight: 700,
                                                color: "#64748b",
                                                fontSize: "16px",
                                                width: 180,
                                            }}
                                        >
                                            Actions
                                        </TableCell>
                                    </TableRow>
                                </TableHead>

                                <TableBody>
                                    {!curveRows.length ? (
                                        <TableRow>
                                            <TableCell
                                                colSpan={2}
                                                align="center"
                                                sx={{
                                                    py: 5,
                                                    color: "#94a3b8",
                                                    fontWeight: 600,
                                                    fontSize: "15px",
                                                }}
                                            >
                                                No curves available. Please upload a persistency curve.
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        curveRows.map((row, rowIndex) => (
                                            <TableRow key={`${row.curve_name}-${rowIndex}`}>
                                                <TableCell
                                                    sx={{
                                                        fontSize: "15px",
                                                        fontWeight: 600,
                                                        py: 2,
                                                    }}
                                                >
                                                    {row.curve_name}
                                                </TableCell>

                                                <TableCell align="right">
                                                    <Box
                                                        sx={{
                                                            display: "flex",
                                                            justifyContent: "flex-end",
                                                            gap: 1,
                                                        }}
                                                    >
                                                        <Button
                                                            disabled={isEditMode}
                                                            variant="outlined"
                                                            onClick={() =>
                                                                handleConfigureCurve(
                                                                    row.curve_name
                                                                )
                                                            }
                                                            sx={{
                                                                textTransform: "none",
                                                                borderRadius: "10px",
                                                                height: "34px",
                                                                fontWeight: 700,
                                                            }}
                                                        >
                                                            View
                                                        </Button>

                                                        <IconButton
                                                            onClick={(event) =>
                                                                handleOpenMenu(
                                                                    event,
                                                                    rowIndex
                                                                )
                                                            }
                                                        >
                                                            <MoreVertIcon />
                                                        </IconButton>
                                                    </Box>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Box>

                    {/* RIGHT SIDE CHART */}
                    <Box
                        sx={{
                            flex: 1,
                            border: "1px solid #D8DEE8",
                            borderRadius: "12px",
                            p: 2,
                            backgroundColor: "#fff",
                            height: "350px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                        }}
                    >
                        {!curvePreview?.months?.length ? (
                            <Typography
                                sx={{
                                    color: "#94a3b8",
                                    fontWeight: 600,
                                    fontSize: "15px",
                                }}
                            >
                                No chart data available. Please upload or view a curve.
                            </Typography>
                        ) : (
                            <PlotComponent
                                data={[
                                    {
                                        x: curvePreview.months,
                                        y: curvePreview.values,
                                        type: "scatter",
                                        mode: "lines",
                                        name: curvePreview.curve_name || "Curve",
                                        line: {
                                            color: "#4F46E5",
                                            width: 3,
                                        },
                                    },
                                ]}
                                layout={{
                                    autosize: true,
                                    height: 320,

                                    margin: {
                                        l: 30,
                                        r: 10,
                                        t: 10,
                                        b: 30,
                                    },

                                    legend: {
                                        orientation: "h",
                                        x: 0.5,
                                        xanchor: "center",
                                        y: -0.2,
                                    },

                                    showlegend: true,

                                    paper_bgcolor: "#fff",
                                    plot_bgcolor: "#fff",

                                    xaxis: {
                                        tickangle: -45,
                                        showgrid: true,
                                    },

                                    yaxis: {
                                        range: [0, 110],
                                        showgrid: true,
                                        gridcolor: "#E2E8F0",
                                    },
                                }}
                                style={{
                                    width: "100%",
                                    height: "100%",
                                }}
                                config={{
                                    responsive: true,
                                    displayModeBar: false,
                                }}
                            />
                        )}
                    </Box>
                </Box>

                <Box
                    sx={{
                        mt: 2,
                        mb: 2,
                        display: "flex",
                        justifyContent: "flex-end",
                        gap: 2
                    }}
                >

                    {/* {!isEditMode ? ( */}

                    <Button
                        variant="outlined"
                        onClick={handleEdit}
                        disabled={!isCurveLoaded || isEditMode}
                        sx={{
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none"
                        }}
                    >
                        Edit
                    </Button>

                    {/* ) : ( */}

                    {/* <> */}

                    <Button
                        variant="contained"
                        onClick={handleApplyEdit}
                        disabled={!isCurveLoaded || !isEditMode}
                        sx={{
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none"
                        }}
                    >
                        Save
                    </Button>

                    <Button
                        variant="outlined"
                        onClick={handleCancel}
                        disabled={!isCurveLoaded || !isEditMode}
                        sx={{
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none"
                        }}
                    >
                        Cancel
                    </Button>

                    {/* </> */}

                    {/* )} */}

                </Box>

                {/* Persistency values table */}
                <TableContainer
                    sx={{
                        border: "1px solid #D8DEE8",
                        borderRadius: "8px",
                        overflowX: "auto",
                        mt: 3,
                    }}
                >
                    {!curvePreview?.months?.length ? (
                        <Box
                            sx={{
                                height: "120px",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                            }}
                        >
                            <Typography
                                sx={{
                                    color: "#94a3b8",
                                    fontWeight: 600,
                                    fontSize: "15px",
                                }}
                            >
                                No table data available. Please upload or view a curve.
                            </Typography>
                        </Box>
                    ) : (
                        <Table size="small" sx={{ minWidth: "max-content" }}>
                            <TableHead>
                                <TableRow>
                                    {curvePreview.months.map((month) => (
                                        <TableCell
                                            key={month}
                                            align="center"
                                            sx={{
                                                minWidth: 72,
                                                backgroundColor: "#f8fafc",
                                                borderRight: "1px solid #D8DEE8",
                                                color: "#000",
                                                fontWeight: 700,
                                            }}
                                        >
                                            {month}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            </TableHead>

                            <TableBody>
                                <TableRow>
                                    {curvePreview.values.map((value, index) => (
                                        <TableCell
                                            align="center"
                                            sx={{
                                                backgroundColor: isEditMode
                                                    ? "#f8fbff"
                                                    : "#fff",
                                                borderRight: "1px solid #E2E8F0"
                                            }}
                                            key={curvePreview.months[index]}
                                            align="center"
                                        >
                                            {isEditMode ? (

                                                <input
                                                    value={editableValues[index]}
                                                    onChange={(e) => {
                                                        const input = e.target.value;

                                                        if (/^\d*\.?\d*$/.test(input)) {
                                                            const updated = [...editableValues];
                                                            updated[index] = input;
                                                            setEditableValues(updated);
                                                        }
                                                    }}
                                                    style={{
                                                        width: "48px",
                                                        height: "22px",
                                                        boxSizing: "border-box",
                                                        border: "1px solid #93c5fd",
                                                        borderRadius: "4px",
                                                        outline: "none",
                                                        background: "#eff6ff",
                                                        color: "#1e293b",
                                                        textAlign: "center",
                                                        fontSize: "13px",
                                                        padding: "1px 4px",
                                                    }}
                                                />

                                            ) : (

                                                value

                                            )}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            </TableBody>
                        </Table>
                    )}
                </TableContainer>

                <Menu
                    anchorEl={menuAnchorEl}
                    open={Boolean(menuAnchorEl)}
                    onClose={handleCloseMenu}
                >
                    <DropdownMenuItem
                        onClick={() => {
                            handleCloseMenu();
                            setOpenDeleteDialog(true);
                        }}
                        sx={{
                            color: "#ef4444",
                        }}
                        disabled={isEditMode}
                    >
                        Delete
                    </DropdownMenuItem>
                </Menu>

                {/* Delete Dialog */}
                <Dialog
                    open={openDeleteDialog}
                    onClose={() => setOpenDeleteDialog(false)}
                >
                    <DialogTitle
                        sx={{
                            color: "#ef4444",
                            fontWeight: 700,
                        }}
                    >
                        Delete Curve?
                    </DialogTitle>

                    <DialogContent>
                        <DialogContentText>
                            Are you sure you want to delete this curve?
                        </DialogContentText>
                    </DialogContent>

                    <DialogActions sx={{ pb: 2, pr: 3 }}>
                        <Button
                            onClick={() => setOpenDeleteDialog(false)}
                            variant="outlined"
                            sx={{ textTransform: "none" }}
                        >
                            Cancel
                        </Button>

                        <Button
                            onClick={handleDeleteCurve}
                            variant="contained"
                            color="error"
                            sx={{ textTransform: "none" }}
                        >
                            Delete
                        </Button>
                    </DialogActions>
                </Dialog>
            </Box>
        </Dialog >
    );
}