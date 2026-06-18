import React, { useEffect, useState } from "react";
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Box,
    Typography,
    FormControl,
    Select,
    MenuItem,
    Checkbox,
    ListItemText,
} from "@mui/material";
import dayjs from "dayjs";
import CloseIcon from "@mui/icons-material/Close";
import IconButton from "@mui/material/IconButton";

export default function ConfigureCurveDialog({
    open,
    onClose,
    lot,
    curveOptions = [],
    months = [],
    selectedCurves,
    setSelectedCurves,
}) {
    const [selectedCurveNames, setSelectedCurveNames] = useState([]);
    const [curveConfigurations, setCurveConfigurations] = useState([]);

    useEffect(() => {
        if (!open || !lot) return;

        const existingConfig = selectedCurves?.[lot] || [];

        setCurveConfigurations(existingConfig);

        setSelectedCurveNames(
            existingConfig.map(
                (item) => item.curve_name
            )
        );
    }, [open, lot, selectedCurves]);

    const handleCurveSelection = (event) => {
        const value = event.target.value;

        let curveNames = [];

        if (value.includes("SELECT_ALL")) {
            if (
                selectedCurveNames.length ===
                curveOptions.length
            ) {
                curveNames = [];
            } else {
                curveNames = curveOptions.map(
                    (curve) => curve.curve_name
                );
            }
        } else {
            curveNames = value;
        }

        const updatedConfigurations =
            curveNames.map((curveName) => {
                const existing =
                    curveConfigurations.find(
                        (item) =>
                            item.curve_name ===
                            curveName
                    );

                return (
                    existing || {
                        curve_name: curveName,
                        start_date: "",
                        end_date: "",
                    }
                );
            });

        setSelectedCurveNames(curveNames);
        setCurveConfigurations(
            updatedConfigurations
        );
    };

    const handleDateChange = (
        curveName,
        field,
        value
    ) => {
        setCurveConfigurations((prev) =>
            prev.map((curve) =>
                curve.curve_name === curveName
                    ? {
                        ...curve,
                        [field]: value,
                    }
                    : curve
            )
        );
    };

    const handleConfigure = () => {
        setSelectedCurves((prev) => ({
            ...prev,
            [lot]: curveConfigurations,
        }));

        onClose();
    };

    const inputStyle = {
        "& .MuiOutlinedInput-root": {
            height: "35px",
            borderRadius: "8px",
            backgroundColor: "#fcfcfd",
        },
    };

    const getAvailableStartMonths = (
        currentIndex
    ) => {
        if (currentIndex === 0) {
            return months;
        }

        const previousCurve =
            curveConfigurations[
            currentIndex - 1
            ];

        if (!previousCurve?.end_date) {
            return months;
        }

        return months.filter(
            (month) =>
                dayjs(month).isAfter(
                    previousCurve.end_date
                )
        );
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="md"
            fullWidth
            PaperProps={{
                sx: {
                    width: "720px",
                    maxWidth: "720px",
                },
            }}
        >
            <DialogTitle
                sx={{
                    borderBottom: "1px solid #e2e8f0",
                    px: 3,
                    py: 2,
                }}
            >
                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                    }}
                >
                    <Typography
                        sx={{
                            fontWeight: 700,
                            fontSize: "18px",
                        }}
                    >
                        Configure Curves - {lot}
                    </Typography>

                    <IconButton
                        onClick={onClose}
                        size="small"
                        sx={{
                            color: "#64748b",
                        }}
                    >
                        <CloseIcon />
                    </IconButton>
                </Box>
            </DialogTitle>

            <DialogContent
                dividers
                sx={{
                    height: "400px",
                    overflowY: "auto",
                }}
            >
                <Box sx={{ mt: 1 }}>
                    <Typography
                        sx={{
                            mb: 1,
                            fontWeight: 600,
                            color: "#64748b",
                            fontSize: "14px",
                        }}
                    >
                        SELECT CURVES
                    </Typography>

                    <FormControl
                        sx={{
                            ...inputStyle,
                            width: "220px",
                            mb: 3,
                        }}
                    >
                        <Select
                            multiple
                            value={
                                selectedCurveNames
                            }
                            onChange={
                                handleCurveSelection
                            }
                            renderValue={(
                                selected
                            ) => {
                                if (
                                    selected.length ===
                                    0
                                ) {
                                    return "Select Curves";
                                }

                                if (
                                    selected.length <=
                                    6
                                ) {
                                    return selected.join(
                                        ", "
                                    );
                                }

                                return `${selected.length} Curves Selected`;
                            }}
                        >
                            <MenuItem value="SELECT_ALL">
                                <Checkbox
                                    checked={
                                        selectedCurveNames.length ===
                                        curveOptions.length &&
                                        curveOptions.length >
                                        0
                                    }
                                    indeterminate={
                                        selectedCurveNames.length >
                                        0 &&
                                        selectedCurveNames.length <
                                        curveOptions.length
                                    }
                                />

                                <ListItemText primary="Select All" />
                            </MenuItem>

                            {curveOptions.map(
                                (curve) => (
                                    <MenuItem
                                        key={
                                            curve.curve_name
                                        }
                                        value={
                                            curve.curve_name
                                        }
                                    >
                                        <Checkbox
                                            checked={selectedCurveNames.includes(
                                                curve.curve_name
                                            )}
                                        />

                                        <ListItemText
                                            primary={
                                                curve.curve_name
                                            }
                                        />
                                    </MenuItem>
                                )
                            )}
                        </Select>
                    </FormControl>
                </Box>

                {curveConfigurations.length === 0 ? (
                    <Box
                        sx={{
                            height: "220px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            border: "1px dashed #d1d5db",
                            borderRadius: "8px",
                            backgroundColor: "#fafafa",
                        }}
                    >
                        <Typography
                            sx={{
                                color: "#6b7280",
                                fontSize: "14px",
                            }}
                        >
                            Select curves from the dropdown above to configure start and end dates.
                        </Typography>
                    </Box>
                ) : (
                    <Box>
                        <Box
                            sx={{
                                display:
                                    "grid",
                                gridTemplateColumns:
                                    "220px 180px 180px",
                                gap: 2,
                                mb: 2,
                                pb: 1,
                                borderBottom:
                                    "1px solid #e2e8f0",
                                position:
                                    "sticky",
                                top: 0,
                                backgroundColor:
                                    "#fff",
                                zIndex: 1,
                            }}
                        >
                            <Typography
                                sx={{
                                    fontWeight: 700,
                                }}
                            >
                                Curve
                            </Typography>

                            <Typography
                                sx={{
                                    fontWeight: 700,
                                }}
                            >
                                Start Date
                            </Typography>

                            <Typography
                                sx={{
                                    fontWeight: 700,
                                }}
                            >
                                End Date
                            </Typography>
                        </Box>

                        {curveConfigurations.map(
                            (curve, index) => (
                                <Box
                                    key={
                                        curve.curve_name
                                    }
                                    sx={{
                                        display:
                                            "grid",
                                        gridTemplateColumns:
                                            "220px 180px 180px",
                                        gap: 2,
                                        alignItems:
                                            "center",
                                        mb: 2,
                                    }}
                                >
                                    <Typography
                                        sx={{
                                            fontSize:
                                                "14px",
                                        }}
                                    >
                                        {
                                            curve.curve_name
                                        }
                                    </Typography>

                                    {/* START DATE */}
                                    <FormControl
                                        sx={{
                                            width:
                                                "170px",
                                            ...inputStyle,
                                        }}
                                    >
                                        <Select
                                            value={
                                                curve.start_date ||
                                                ""
                                            }
                                            onChange={(
                                                e
                                            ) =>
                                                handleDateChange(
                                                    curve.curve_name,
                                                    "start_date",
                                                    e
                                                        .target
                                                        .value
                                                )
                                            }
                                            MenuProps={{
                                                PaperProps: {
                                                    sx: {
                                                        maxHeight: 220,
                                                        width: 130,
                                                    },
                                                },
                                            }}
                                            displayEmpty
                                        >
                                            <MenuItem
                                                value=""
                                                disabled
                                            >
                                                Select
                                                Start
                                                Date
                                            </MenuItem>

                                            {getAvailableStartMonths(index).map(
                                                (month) => (
                                                    <MenuItem
                                                        key={
                                                            month
                                                        }
                                                        value={
                                                            month
                                                        }
                                                    >
                                                        {dayjs(
                                                            month
                                                        ).format(
                                                            "MMM YY"
                                                        )}
                                                    </MenuItem>
                                                )
                                            )}
                                        </Select>
                                    </FormControl>

                                    {/* END DATE */}
                                    <FormControl
                                        sx={{
                                            width:
                                                "170px",
                                            ...inputStyle,
                                        }}
                                    >
                                        <Select
                                            value={
                                                curve.end_date ||
                                                ""
                                            }
                                            onChange={(
                                                e
                                            ) =>
                                                handleDateChange(
                                                    curve.curve_name,
                                                    "end_date",
                                                    e
                                                        .target
                                                        .value
                                                )
                                            }
                                            MenuProps={{
                                                PaperProps: {
                                                    sx: {
                                                        maxHeight: 220,
                                                        width: 130,
                                                    },
                                                },
                                            }}
                                            displayEmpty
                                        >
                                            <MenuItem
                                                value=""
                                                disabled
                                            >
                                                Select
                                                End
                                                Date
                                            </MenuItem>

                                            {months
                                                .filter(
                                                    (
                                                        month
                                                    ) =>
                                                        !curve.start_date ||
                                                        dayjs(
                                                            month
                                                        ).isAfter(
                                                            curve.start_date
                                                        )
                                                )
                                                .map(
                                                    (
                                                        month
                                                    ) => (
                                                        <MenuItem
                                                            key={
                                                                month
                                                            }
                                                            value={
                                                                month
                                                            }
                                                        >
                                                            {dayjs(
                                                                month
                                                            ).format(
                                                                "MMM YY"
                                                            )}
                                                        </MenuItem>
                                                    )
                                                )}
                                        </Select>
                                    </FormControl>
                                </Box>
                            )
                        )}
                    </Box>
                )}
            </DialogContent>

            <DialogActions
                sx={{
                    px: 3,
                    py: 2,
                    borderTop:
                        "1px solid #e2e8f0",
                }}
            >
                <Button
                    variant="outlined"
                    onClick={onClose}
                    sx={{
                        textTransform:
                            "none",
                    }}
                >
                    Cancel
                </Button>

                <Button
                    variant="contained"
                    onClick={
                        handleConfigure
                    }
                    sx={{
                        textTransform:
                            "none",
                        backgroundColor:
                            "#4F46E5",
                    }}
                >
                    Configure
                </Button>
            </DialogActions>
        </Dialog>
    );
}