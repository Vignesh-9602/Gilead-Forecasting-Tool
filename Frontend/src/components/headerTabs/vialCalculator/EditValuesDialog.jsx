import React, { useState, useEffect } from "react";
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Box,
    Typography,
    Button,
    TextField,
    Select,
    MenuItem,
    IconButton,
} from "@mui/material";

import CloseIcon from "@mui/icons-material/Close";

export default function EditValuesDialog({
    open,
    onClose,
    months = [],
    onApply,
}) {

    const [formData, setFormData] =
        useState({

            startMonth: "",

            percentageChange: "",

            numberOfMonths: ""

        });

    useEffect(() => {
        if (open) {
            setFormData({
                startMonth: months?.[0] || "",
                percentageChange: "",
                numberOfMonths: ""
            });
        }
    }, [open, months
    ]);

    const handleChange = (
        field,
        value
    ) => {

        setFormData((prev) => ({
            ...prev,
            [field]: value,
        }));
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="sm"
            fullWidth
            PaperProps={{
                sx: {
                    borderRadius: "16px"
                }
            }}
        >

            <DialogTitle
                sx={{
                    borderBottom:
                        "1px solid #E2E8F0",
                    fontWeight: 700,
                    fontSize: "20px",
                    p: 2,
                }}
            >
                Edit Row Values

                <IconButton
                    onClick={onClose}
                    sx={{
                        position: "absolute",
                        top: 14,
                        right: 14,
                    }}
                >
                    <CloseIcon />
                </IconButton>

            </DialogTitle>

            <DialogContent
                sx={{
                    py: 2,
                    mt: 2,
                }}
            >

                {/* Start Month */}

                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        mb: 2.5,
                    }}
                >

                    <Typography
                        sx={{
                            fontSize: "16px",
                        }}
                    >
                        Start Month
                    </Typography>

                    <Select
                        value={
                            formData.startMonth
                        }
                        onChange={(e) =>
                            handleChange(
                                "startMonth",
                                e.target.value
                            )
                        }
                        size="small"
                        sx={{
                            width: "100px",
                        }}
                    >
                        {
                            months.map(
                                (month) => (
                                    <MenuItem
                                        key={month}
                                        value={month}
                                    >
                                        {
                                            new Date(
                                                month
                                            ).toLocaleDateString(
                                                "en-US",
                                                {
                                                    month: "short",
                                                    year: "2-digit",
                                                }
                                            )
                                        }
                                    </MenuItem>
                                )
                            )
                        }
                    </Select>

                </Box>

                {/* Percentage Change */}

                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        mb: 2.5,
                    }}
                >
                    <Typography>
                        % Change (per month)
                    </Typography>

                    <TextField
                        size="small"
                        value={
                            formData.percentageChange
                        }
                        onChange={(e) =>
                            handleChange(
                                "percentageChange",
                                e.target.value
                            )
                        }
                        sx={{
                            width: "100px"
                        }}
                    />
                </Box>


                {/* Number of Months */}

                <Box
                    sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                    }}
                >
                    <Typography>
                        Number of Months
                    </Typography>

                    <TextField
                        size="small"
                        value={
                            formData.numberOfMonths
                        }
                        onChange={(e) =>
                            handleChange(
                                "numberOfMonths",
                                e.target.value
                            )
                        }
                        sx={{
                            width: "100px"
                        }}
                    />
                </Box>

            </DialogContent>

            <DialogActions
                sx={{
                    borderTop:
                        "1px solid #E2E8F0",
                    p: 2,
                }}
            >
                <Button
                    variant="outlined"
                    onClick={onClose}
                    sx={{
                        textTransform: "none"
                    }}
                >
                    Cancel
                </Button>

                <Button
                    variant="contained"
                    onClick={() => {
                        onApply(formData);
                        onClose();
                    }}
                    sx={{
                        textTransform: "none",
                        backgroundColor:
                            "#4F46E5",
                    }}
                >
                    Apply
                </Button>

            </DialogActions>

        </Dialog>
    );
}