import React, { useState, useEffect } from "react";

import {
    Box,
    Typography,
    Dialog,
    IconButton,
    Button,
    TextField,
    FormControl,
    Select,
    MenuItem,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
    Menu,
    MenuItem as DropdownMenuItem,
} from "@mui/material";
import MoreVertIcon from "@mui/icons-material/MoreVert";

import Plot from "react-plotly.js";

import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";

import { calculateApplyPersistencyCurve, getPersistencyCurves, getPersistencyCurveDetails, deletePersistencyCurve } from "../../../services/apiService";

const PlotComponent = Plot.default || Plot;

export default function PersistencyConfiguration({
    open,
    onClose,
    therapyArea,
    onCurveUpdated,
    showSnackbar
}) {
    const [curveRows, setCurveRows] = useState([]);

    const [selectedRowIndex, setSelectedRowIndex] =
        useState(null);

    const [openDeleteDialog, setOpenDeleteDialog] =
        useState(false);

    const [persistencyConfig, setPersistencyConfig] =
        useState({
            curve_name: "",
            start_month: "",
            end_month: "",
            start_value: "",
            end_value: "",
            method: "",
            k_value: "",
        });

    const [curvePreview, setCurvePreview] =
        useState({
            months: [],
            values: [],
        });

    const methodLabelMapping = {
        linear: "Linear",
        "s-curve": "S-Curve",
        exponential: "Exponential",
        logarithmic: "Logarithmic",
    };

    const [menuAnchorEl, setMenuAnchorEl] =
        useState(null);

    const resetPersistencyForm = () => {
        setPersistencyConfig({
            curve_name: "",
            start_month: "",
            end_month: "",
            start_value: "",
            end_value: "",
            method: "",
            k_value: "",
        });

        setCurvePreview({
            months: [],
            values: [],
        });
    };

    const handleDeleteCurve = async () => {
        try {
            const selectedCurve =
                curveRows[selectedRowIndex];

            if (!selectedCurve) return;

            const response =
                await deletePersistencyCurve(
                    selectedCurve.curve_name
                );

            setCurveRows(
                response?.data?.curve_list || []
            );

            onCurveUpdated?.();

            // if currently opened curve deleted
            if (
                persistencyConfig.curve_name ===
                selectedCurve.curve_name
            ) {
                resetPersistencyForm();
            }

            setOpenDeleteDialog(false);

            setSelectedRowIndex(null);

            showSnackbar("Curve was deleted successfully", "success");
        } catch (error) {
            console.error("Failed to delete curve", error);
            showSnackbar("Failed to delete the curve", "error");
        }
    };

    useEffect(() => {
        if (open && therapyArea) {
            fetchPersistencyCurves();
        }
    }, [open, therapyArea]);

    const fetchPersistencyCurves = async () => {
        try {
            const response = await getPersistencyCurves(therapyArea);
            setCurveRows(response?.data?.curve_list || []);
        } catch (error) {
            console.error("Failed to fetch persistency curves", error);
            showSnackbar("Failed to fetch the list of curves", "error");
        }
    };

    const handleConfigureCurve = async (curveName) => {
        try {
            const response = await getPersistencyCurveDetails(curveName);

            const curveDetails =
                response?.data?.curve_details;

            setPersistencyConfig({
                curve_name:
                    curveDetails?.curve_name || "",

                start_month:
                    curveDetails?.start_month || "",

                end_month:
                    curveDetails?.end_month || "",

                start_value:
                    curveDetails?.start_value || "",

                end_value:
                    curveDetails?.end_value || "",

                method:
                    methodLabelMapping[
                    curveDetails?.method
                    ] || "",

                k_value:
                    curveDetails?.k_factor ?? "",
            });

            setCurvePreview(
                response?.data?.curve_preview || {
                    months: [],
                    values: [],
                }
            );
        } catch (error) {
            console.error("Failed to fetch curve details", error);
            showSnackbar("Failed to fetch curve details", "error");
        }
    };

    const handleCalculateApply = async () => {
        try {
            const payload = {
                ta_name: therapyArea,

                curve_name:
                    persistencyConfig.curve_name,

                start_month: Number(
                    persistencyConfig.start_month
                ),

                end_month: Number(
                    persistencyConfig.end_month
                ),

                start_value: Number(
                    persistencyConfig.start_value
                ),

                end_value: Number(
                    persistencyConfig.end_value
                ),

                method:
                    persistencyConfig.method.toLowerCase(),

                k_factor:
                    persistencyConfig.method ===
                        "Linear"
                        ? 0
                        : Number(
                            persistencyConfig.k_value
                        ),
            };

            const response = await calculateApplyPersistencyCurve(payload);

            setCurvePreview(
                response.data.curve_preview
            );

            setCurveRows(
                response.data.curve_list
            );

            // fetch the updated curve list
            onCurveUpdated?.();
            showSnackbar("New curve added successfully", "success");
        } catch (error) {
            console.error("Failed to add new curve", error);
            showSnackbar("Failed to add new curve", "error");
        }
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

    const handleDuplicateCurve = async () => {
        try {
            const selectedCurve =
                curveRows[selectedRowIndex];

            if (!selectedCurve) return;

            const response =
                await getPersistencyCurveDetails(
                    selectedCurve.curve_name
                );

            const curveDetails =
                response?.data?.curve_details;

            setPersistencyConfig({
                curve_name: `${curveDetails?.curve_name}_duplicate`,

                start_month:
                    curveDetails?.start_month || "",

                end_month:
                    curveDetails?.end_month || "",

                start_value:
                    curveDetails?.start_value || "",

                end_value:
                    curveDetails?.end_value || "",

                method:
                    methodLabelMapping[
                    curveDetails?.method
                    ] || "",

                k_value:
                    curveDetails?.k_factor ?? "",
            });

            setCurvePreview(
                response?.data?.curve_preview || {
                    months: [],
                    values: [],
                }
            );

            handleCloseMenu();

        } catch (error) {
            console.error(
                "Failed to duplicate curve",
                error
            );
        }
    };

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
                <Typography sx={{ fontSize: "18px", fontWeight: 700, mb: 2 }}>
                    Create/Update Curve
                </Typography>
                <Box
                    sx={{
                        display: "grid",
                        gridTemplateColumns:
                            persistencyConfig.method &&
                                persistencyConfig.method !== "Linear"
                                ? "180px 120px 120px 140px 140px 160px 120px 180px"
                                : "180px 120px 120px 140px 140px 160px 180px",
                        gap: 1.5,
                        alignItems: "end",
                        mb: 4,
                    }}
                >
                    {/* Curve Name */}
                    <Box>
                        <Typography
                            sx={{ mb: 1, fontSize: "13px", fontWeight: 700, color: "#64748b", }}
                        >
                            CURVE NAME
                        </Typography>

                        <TextField
                            value={persistencyConfig.curve_name || ""}
                            onChange={(e) =>
                                setPersistencyConfig({
                                    ...persistencyConfig,
                                    curve_name: e.target.value,
                                })
                            }
                            // placeholder="Curve Name"
                            size="small"
                            sx={{
                                width: "180px",
                                "& .MuiOutlinedInput-root": {
                                    height: "35px",
                                    borderRadius: "10px",
                                    backgroundColor: "#fff",
                                    fontSize: "13px",
                                },
                            }}
                        />
                    </Box>

                    {/* Start Month */}
                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "13px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            START MONTH
                        </Typography>

                        <TextField
                            value={persistencyConfig.start_month}
                            onChange={(e) =>
                                setPersistencyConfig({
                                    ...persistencyConfig,
                                    start_month: e.target.value,
                                })
                            }
                            size="small"
                            sx={{
                                width: "120px",

                                "& .MuiOutlinedInput-root": {
                                    height: "35px",
                                    borderRadius: "10px",
                                    backgroundColor: "#fff",
                                    fontSize: "13px",
                                },
                            }}
                        />
                    </Box>

                    {/* End Month */}
                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "13px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            END MONTH
                        </Typography>

                        <TextField
                            value={persistencyConfig.end_month}
                            onChange={(e) =>
                                setPersistencyConfig({
                                    ...persistencyConfig,
                                    end_month: e.target.value,
                                })
                            }
                            size="small"
                            sx={{
                                width: "120px",

                                "& .MuiOutlinedInput-root": {
                                    height: "35px",
                                    borderRadius: "10px",
                                    backgroundColor: "#fff",
                                    fontSize: "13px",
                                },
                            }}
                        />
                    </Box>

                    {/* Start Value */}
                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "13px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            START VALUE (%)
                        </Typography>

                        <TextField
                            value={persistencyConfig.start_value}
                            onChange={(e) =>
                                setPersistencyConfig({
                                    ...persistencyConfig,
                                    start_value: e.target.value,
                                })
                            }
                            size="small"
                            sx={{
                                width: "120px",

                                "& .MuiOutlinedInput-root": {
                                    height: "35px",
                                    borderRadius: "10px",
                                    backgroundColor: "#fff",
                                    fontSize: "13px",
                                },
                            }}
                        />
                    </Box>

                    {/* End Value */}
                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "13px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            END VALUE (%)
                        </Typography>

                        <TextField
                            value={persistencyConfig.end_value}
                            onChange={(e) =>
                                setPersistencyConfig({
                                    ...persistencyConfig,
                                    end_value: e.target.value,
                                })
                            }
                            size="small"
                            sx={{
                                width: "120px",

                                "& .MuiOutlinedInput-root": {
                                    height: "35px",
                                    borderRadius: "10px",
                                    backgroundColor: "#fff",
                                    fontSize: "13px",
                                },
                            }}
                        />
                    </Box>

                    {/* Method */}
                    <Box>
                        <Typography
                            sx={{
                                mb: 1,
                                fontSize: "13px",
                                fontWeight: 700,
                                color: "#64748b",
                            }}
                        >
                            METHOD
                        </Typography>

                        <FormControl size="small">
                            <Select
                                value={persistencyConfig.method}
                                onChange={(e) =>
                                    setPersistencyConfig({
                                        ...persistencyConfig,
                                        method: e.target.value,
                                    })
                                }
                                sx={{
                                    width: "160px",
                                    height: "35px",
                                    borderRadius: "10px",
                                    backgroundColor: "#fff",
                                    fontSize: "13px",
                                }}
                            >
                                {[
                                    "Linear",
                                    "Exponential",
                                    "S-Curve",
                                    "Logarithmic",
                                ].map((item) => (
                                    <MenuItem key={item} value={item}>
                                        {item}
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>

                    {/* K Value */}
                    {persistencyConfig.method &&
                        persistencyConfig.method !== "Linear" && (
                            <Box>
                                <Typography
                                    sx={{
                                        mb: 1,
                                        fontSize: "13px",
                                        fontWeight: 700,
                                        color: "#64748b",
                                    }}
                                >
                                    K VALUE
                                </Typography>

                                <TextField
                                    value={persistencyConfig.k_value}
                                    onChange={(e) =>
                                        setPersistencyConfig({
                                            ...persistencyConfig,
                                            k_value: e.target.value,
                                        })
                                    }
                                    size="small"
                                    sx={{
                                        width: "120px",

                                        "& .MuiOutlinedInput-root": {
                                            height: "35px",
                                            borderRadius: "10px",
                                            backgroundColor: "#fff",
                                            fontSize: "13px",
                                        },
                                    }}
                                />
                            </Box>
                        )}

                    {/* Button */}
                    <Button
                        variant="contained"
                        onClick={handleCalculateApply}
                        sx={{
                            width: "180px",
                            height: "35px",
                            borderRadius: "10px",
                            textTransform: "none",
                            backgroundColor: "#4F46E5",
                            fontWeight: 700,
                            fontSize: "13px",
                            mt: "24px",
                        }}
                    >
                        Calculate & Apply
                    </Button>
                </Box>

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
                    <Box sx={{ width: "400px", flexShrink: 0 }}>
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

                            <Button
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
                            </Button>
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
                                                No curves available. Please create a new curve.
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
                                                            Configure
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
                                No chart data available. Please create a new curve.
                            </Typography>
                        ) : (
                            <PlotComponent
                                data={[
                                    {
                                        x: curvePreview.months,
                                        y: curvePreview.values,
                                        type: "scatter",
                                        mode: "lines",
                                        name: persistencyConfig.method || "Curve",
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
                                No table data available. Please create a new curve.
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
                                            key={curvePreview.months[index]}
                                            align="center"
                                            sx={{
                                                borderRight: "1px solid #D8DEE8",
                                                color: "#334155",
                                                fontWeight: 700,
                                            }}
                                        >
                                            {value}
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
                        onClick={handleDuplicateCurve}
                    >
                        Duplicate
                    </DropdownMenuItem>

                    <DropdownMenuItem
                        onClick={() => {
                            handleCloseMenu();
                            setOpenDeleteDialog(true);
                        }}
                        sx={{
                            color: "#ef4444",
                        }}
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
        </Dialog>
    );
}