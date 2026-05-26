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
    IconButton,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

export default function ConfigureComplianceDialog({
    open,
    onClose,
    complianceData = [],
    onApply,
    brand,
}) {
    const [rows, setRows] =
        useState([]);

    useEffect(() => {
        setRows(complianceData);
    }, [complianceData]);

    const handleChange = (
        index,
        value
    ) => {

        if (
            !/^\d*\.?\d*$/.test(
                value
            )
        )
            return;

        const updated = [
            ...rows,
        ];

        updated[index].value =
            value;

        setRows(updated);
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="sm"
            fullWidth
            PaperProps={{
                sx: {
                    borderRadius:
                        "16px",
                },
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
                Configure Compliance %

                <IconButton
                    onClick={
                        onClose
                    }
                    sx={{
                        position:
                            "absolute",
                        right: 15,
                        top: 15,
                    }}
                >
                    <CloseIcon />
                </IconButton>
            </DialogTitle>

            <DialogContent
                sx={{
                    py: 2,
                    mt: 4,
                }}
            >
                {rows.map(
                    (
                        item,
                        index
                    ) => (
                        <Box
                            key={
                                item.lot
                            }
                            sx={{
                                display:
                                    "flex",
                                justifyContent:
                                    "space-between",
                                alignItems:
                                    "center",
                                mb: 2,
                            }}
                        >
                            <Typography
                                sx={{
                                    fontSize:
                                        "16px",
                                    // fontWeight: 600,
                                }}
                            >
                                {brand} - {item.lot}
                            </Typography>

                            <TextField
                                value={
                                    item.value
                                }
                                onChange={(
                                    e
                                ) =>
                                    handleChange(
                                        index,
                                        e
                                            .target
                                            .value
                                    )
                                }
                                size="small"
                                sx={{ width: "100px" }}
                            />
                        </Box>
                    )
                )}
            </DialogContent>

            <DialogActions
                sx={{
                    borderTop:
                        "1px solid #E2E8F0",
                    px: 3,
                    py: 2,
                }}
            >
                <Button
                    variant="outlined"
                    onClick={
                        onClose
                    }
                >
                    Cancel
                </Button>

                <Button
                    variant="contained"
                    onClick={() => {
                        onApply(
                            rows
                        );
                        onClose();
                    }}
                    sx={{
                        backgroundColor:
                            "#4F46E5",
                    }}
                >
                    Apply to All Months
                </Button>
            </DialogActions>
        </Dialog>
    );
}