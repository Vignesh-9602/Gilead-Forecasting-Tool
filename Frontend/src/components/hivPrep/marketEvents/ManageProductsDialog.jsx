import React, { useEffect, useState } from "react";

import {
    Box,
    Paper,
    Typography,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Table,
    TableHead,
    TableBody,
    TableRow,
    TableCell,
    IconButton,
    Chip
} from "@mui/material";

import EditIcon from "@mui/icons-material/Edit";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";

import { useSnackbarStore } from "../../../stores";

export default function ManageProductsDialog({
    open,
    onClose,
    products,
    setProducts,
}) {

    const { showSnackbar } = useSnackbarStore();

    const [showAddRow, setShowAddRow] = useState(false);

    const [newProduct, setNewProduct] = useState("");

    const [editingId, setEditingId] = useState(null);

    const [editingValue, setEditingValue] = useState("");

    const [deleteProduct, setDeleteProduct] = useState(null);

    useEffect(() => {

        if (!open) {
            setShowAddRow(false);
            setNewProduct("");
            setEditingId(null);
            setEditingValue("");
            setDeleteProduct(null);
        }

    }, [open]);

    const handleAddProduct = () => {
        setShowAddRow(true);
        setNewProduct("");
    };

    const handleCancelAdd = () => {
        setShowAddRow(false);
        setNewProduct("");
    };

    const handleSaveProduct = () => {

        const name = newProduct.trim();

        if (!name) {
            showSnackbar("Product name is required", "warning");
            return;
        }

        const duplicate = products.some(
            item =>
                item.product_name.toLowerCase() ===
                name.toLowerCase()
        );

        if (duplicate) {
            showSnackbar("Product already exists", "warning");
            return;
        }

        const today = new Date().toISOString().split("T")[0];

        const newRow = {
            id: Date.now(),
            product_name: name,
            date_added: today,
            added_by: "Admin User",
            modified_by: "Admin User",
            is_new: true
        };

        setProducts(prev => [...prev, newRow]);

        setShowAddRow(false);

        setNewProduct("");

        showSnackbar(
            "Product added successfully",
            "success"
        );
    };

    const handleEdit = row => {

        setEditingId(row.id);

        setEditingValue(row.product_name);

    };

    const handleCancelEdit = () => {

        setEditingId(null);

        setEditingValue("");

    };

    const handleSaveEdit = () => {

        const value = editingValue.trim();

        if (!value) {

            showSnackbar(
                "Product name is required",
                "warning"
            );

            return;

        }

        const duplicate = products.some(
            item =>
                item.id !== editingId &&
                item.product_name.toLowerCase() ===
                value.toLowerCase()
        );

        if (duplicate) {

            showSnackbar(
                "Product already exists",
                "warning"
            );

            return;

        }

        setProducts(prev =>
            prev.map(item =>
                item.id === editingId
                    ? {
                        ...item,
                        product_name: value,
                        modified_by: "Admin User"
                    }
                    : item
            )
        );

        setEditingId(null);

        setEditingValue("");

        showSnackbar(
            "Product updated successfully",
            "success"
        );
    };

    const handleDelete = () => {

        setProducts(prev =>
            prev.filter(
                item => item.id !== deleteProduct.id
            )
        );

        setDeleteProduct(null);

        showSnackbar(
            "Product deleted successfully",
            "success"
        );
    };

    const headerStyle = {
        fontWeight: 700,
        color: "#64748b",
        fontSize: 13,
        background: "#F8FAFC"
    };

    const buttonStyle = {
        textTransform: "none",
        borderRadius: "8px",
        fontWeight: 600
    };

    return (

        <>
            <Dialog
                open={open}
                onClose={onClose}
                fullWidth
                maxWidth="md"
            >

                <DialogTitle
                    sx={{
                        fontWeight: 700,
                        fontSize: 28,
                        pt: 3,
                        px: 3
                    }}
                >
                    <Box
                        display="flex"
                        justifyContent="space-between"
                        alignItems="center"
                    >

                        <Typography
                            fontWeight={700}
                            fontSize={30}
                        >
                            Manage New Products
                        </Typography>

                        <Button
                            variant="contained"
                            onClick={handleAddProduct}
                            disabled={showAddRow}
                            sx={{
                                ...buttonStyle,
                                background: "#4F46E5"
                            }}
                        >
                            + Add Product
                        </Button>

                    </Box>

                </DialogTitle>

                <DialogContent sx={{ px: 3 }}>

                    {showAddRow && (

                        <Paper
                            sx={{
                                mt: 1,
                                mb: 3,
                                p: 2,
                                border: "1px solid #D8DEE8",
                                borderRadius: "10px",
                                boxShadow: "none"
                            }}
                        >

                            <Typography
                                sx={{
                                    mb: 1,
                                    fontWeight: 700,
                                    fontSize: 12,
                                    color: "#64748b"
                                }}
                            >
                                PRODUCT NAME
                            </Typography>

                            <Box
                                display="flex"
                                gap={1.5}
                                alignItems="center"
                            >

                                <TextField
                                    fullWidth
                                    size="small"
                                    value={newProduct}
                                    onChange={(e) =>
                                        setNewProduct(
                                            e.target.value
                                        )
                                    }
                                />

                                <Button
                                    variant="contained"
                                    onClick={handleSaveProduct}
                                    sx={{
                                        ...buttonStyle,
                                        background: "#4F46E5",
                                        minWidth: 70
                                    }}
                                >
                                    Save
                                </Button>

                                <Button
                                    variant="outlined"
                                    onClick={handleCancelAdd}
                                    sx={buttonStyle}
                                >
                                    Cancel
                                </Button>

                            </Box>

                        </Paper>

                    )}

                    <Table>

                        <TableHead>

                            <TableRow>

                                <TableCell sx={headerStyle}>
                                    Product Name
                                </TableCell>

                                <TableCell sx={headerStyle}>
                                    Date Added
                                </TableCell>

                                <TableCell sx={headerStyle}>
                                    Added By
                                </TableCell>

                                <TableCell sx={headerStyle}>
                                    Modified By
                                </TableCell>

                                <TableCell
                                    sx={headerStyle}
                                    align="center"
                                >
                                    Actions
                                </TableCell>

                            </TableRow>

                        </TableHead>

                        <TableBody>

                            {products.length === 0 ? (

                                <TableRow>

                                    <TableCell
                                        colSpan={5}
                                        align="center"
                                        sx={{
                                            py: 5,
                                            color: "#64748b"
                                        }}
                                    >
                                        No new products added yet.
                                    </TableCell>

                                </TableRow>

                            ) : (

                                products.map((row) => (

                                    <TableRow key={row.id}>

                                        <TableCell>

                                            {editingId === row.id ? (

                                                <TextField
                                                    fullWidth
                                                    size="small"
                                                    value={editingValue}
                                                    onChange={(e) =>
                                                        setEditingValue(
                                                            e.target.value
                                                        )
                                                    }
                                                />

                                            ) : (

                                                <Box
                                                    display="flex"
                                                    alignItems="center"
                                                    gap={1}
                                                >

                                                    <Typography
                                                        fontWeight={600}
                                                    >
                                                        {row.product_name}
                                                    </Typography>

                                                    {row.is_new && (

                                                        <Chip
                                                            label="NEW"
                                                            size="small"
                                                            sx={{
                                                                height: 20,
                                                                fontSize: 11,
                                                                bgcolor:
                                                                    "#FFF8E1",
                                                                color:
                                                                    "#F59E0B",
                                                                border:
                                                                    "1px solid #F59E0B"
                                                            }}
                                                        />

                                                    )}

                                                </Box>

                                            )}

                                        </TableCell>

                                        <TableCell>
                                            {row.date_added}
                                        </TableCell>

                                        <TableCell>
                                            {row.added_by}
                                        </TableCell>

                                        <TableCell>
                                            {row.modified_by}
                                        </TableCell>

                                        <TableCell align="center">

                                            {editingId === row.id ? (

                                                <Box
                                                    display="flex"
                                                    justifyContent="center"
                                                    gap={1}
                                                >

                                                    <Button
                                                        size="small"
                                                        variant="contained"
                                                        onClick={
                                                            handleSaveEdit
                                                        }
                                                        sx={{
                                                            ...buttonStyle,
                                                            background:
                                                                "#4F46E5"
                                                        }}
                                                    >
                                                        Update
                                                    </Button>

                                                    <Button
                                                        size="small"
                                                        variant="outlined"
                                                        onClick={
                                                            handleCancelEdit
                                                        }
                                                        sx={buttonStyle}
                                                    >
                                                        Cancel
                                                    </Button>

                                                </Box>

                                            ) : (

                                                <Box
                                                    display="flex"
                                                    justifyContent="center"
                                                    gap={1}
                                                >

                                                    <IconButton
                                                        onClick={() =>
                                                            handleEdit(
                                                                row
                                                            )
                                                        }
                                                    >
                                                        <EditIcon
                                                            fontSize="small"
                                                        // color="warning"
                                                        />
                                                    </IconButton>

                                                    <IconButton
                                                        onClick={() =>
                                                            setDeleteProduct(
                                                                row
                                                            )
                                                        }
                                                    >
                                                        <DeleteOutlineIcon
                                                            fontSize="small"
                                                            color="error"
                                                        />
                                                    </IconButton>

                                                </Box>

                                            )}

                                        </TableCell>

                                    </TableRow>

                                ))

                            )}

                        </TableBody>

                    </Table>

                </DialogContent>

                <DialogActions
                    sx={{
                        px: 3,
                        pb: 3
                    }}
                >
                    <Button
                        variant="contained"
                        onClick={onClose}
                        sx={{
                            ...buttonStyle,
                            background: "#4F46E5",
                            minWidth: 100
                        }}
                    >
                        Close
                    </Button>
                </DialogActions>

            </Dialog>

            {/* Delete Confirmation */}

            <Dialog
                open={Boolean(deleteProduct)}
                onClose={() => setDeleteProduct(null)}
                maxWidth="xs"
                fullWidth
            >

                <DialogTitle
                    sx={{
                        fontWeight: 700
                    }}
                >
                    Delete Product
                </DialogTitle>

                <DialogContent>

                    <Typography>

                        Are you sure you want to delete{" "}

                        <strong>
                            {deleteProduct?.product_name}
                        </strong>

                        ?

                    </Typography>

                </DialogContent>

                <DialogActions
                    sx={{
                        px: 3,
                        pb: 2
                    }}
                >

                    <Button
                        variant="outlined"
                        onClick={() =>
                            setDeleteProduct(null)
                        }
                        sx={buttonStyle}
                    >
                        Cancel
                    </Button>

                    <Button
                        variant="contained"
                        color="error"
                        onClick={handleDelete}
                        sx={buttonStyle}
                    >
                        Delete
                    </Button>

                </DialogActions>

            </Dialog>

        </>

    );

} 