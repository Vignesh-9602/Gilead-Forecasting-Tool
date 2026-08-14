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

import { useSnackbarStore, useLoadingStore } from "../../../stores";
import { addHIVPrepProduct, getHIVPrepProducts, updateHIVPrepProduct, deleteHIVPrepProduct } from "../../../services/apiService";


export default function ManageProductsDialog({
    open,
    onClose,
    products,
    setProducts,
    therapyArea,
    onProductSaved,
    scenarioName,
    onRefreshProducts
}) {

    const { showSnackbar } = useSnackbarStore();

    const [showAddRow, setShowAddRow] = useState(false);

    const [newProduct, setNewProduct] = useState("");

    const [savingProduct, setSavingProduct] = useState(false);

    const [editingId, setEditingId] = useState(null);

    const [editingValue, setEditingValue] = useState("");
    const [savingEdit, setSavingEdit] = useState(false);

    const [deleteProduct, setDeleteProduct] = useState(null);
    const [deletingProduct, setDeletingProduct] = useState(false);
    const [loadingProducts, setLoadingProducts] = useState(false);
    const { setLoading } = useLoadingStore();

    // useEffect(() => {

    //     if (!open) {
    //         setShowAddRow(false);
    //         setNewProduct("");
    //         setEditingId(null);
    //         setEditingValue("");
    //         setDeleteProduct(null);
    //     }

    // }, [open]);

    useEffect(() => {
        if (open) {
            fetchProducts();
        } else {
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

    const fetchProducts = async () => {
        try {
            setLoading(true);

            const { data: response } = await getHIVPrepProducts();

            const productList = Array.isArray(response?.products)
                ? response.products
                : [];

            const mappedProducts = productList.map((product) => ({
                id: product.product_id,
                product_id: product.product_id,
                product_name: product.product_name,
                date_added: product.date_added,
                added_by: product.added_by,
                modified_by: product.modified_by,
                is_new: false,
            }));

            setProducts(mappedProducts);
        } catch (error) {
            console.error("Failed to fetch products", error);

            const errorMessage =
                error?.response?.data?.message ||
                "Failed to fetch products";

            showSnackbar(errorMessage, "error");

            setProducts([]);
        } finally {
            setLoading(false);
        }
    };

    const handleSaveProduct = async () => {

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

        const payload = {
            ta_name: therapyArea,
            product_name: name,
        };

        try {

            setSavingProduct(true);

            const { data: response } = await addHIVPrepProduct(payload);

            const product = response?.product;

            if (!product) {
                throw new Error("Product details are missing from the API response");
            }

            const newRow = {
                id: product.product_id,
                product_id: product.product_id,
                product_name: product.product_name,
                product_code: product.product_code,
                active_flag: product.active_flag,
                company: product.company,
                date_added: product.date_added,
                added_by: product.added_by,
                modified_by: product.modified_by,
                is_new: true,
            };

            // setProducts(prev => [...prev, newRow]);

            setShowAddRow(false);
            setNewProduct("");

            await fetchProducts();

            // showSnackbar(
            //     "Product added successfully",
            //     "success"
            // );

            // Refresh the screen with the new product
            if (onProductSaved) {
                await onProductSaved();
            }

            showSnackbar(
                "Product added successfully",
                "success"
            );

        } catch (error) {

            console.error("Failed to add product", error);

            showSnackbar(
                "Failed to add product",
                "error"
            );

        } finally {

            setSavingProduct(false);

        }
    };

    const handleEdit = row => {

        setEditingId(row.id);

        setEditingValue(row.product_name);

    };

    const handleCancelEdit = () => {

        setEditingId(null);

        setEditingValue("");

    };

    const handleSaveEdit = async () => {
        const value = editingValue.trim();

        if (!value) {
            showSnackbar("Product name is required", "warning");
            return;
        }

        const currentProduct = products.find(
            (item) => item.id === editingId
        );

        if (!currentProduct) {
            showSnackbar("Unable to find the selected product", "error");
            return;
        }

        const originalProductName = currentProduct.product_name;

        if (
            originalProductName.toLowerCase() ===
            value.toLowerCase()
        ) {
            showSnackbar("No changes were made", "info");
            handleCancelEdit();
            return;
        }

        const duplicate = products.some(
            (item) =>
                item.id !== editingId &&
                item.product_name?.toLowerCase() ===
                value.toLowerCase()
        );

        if (duplicate) {
            showSnackbar("Product already exists", "warning");
            return;
        }

        const payload = {
            ta_name: therapyArea,
            product_name: originalProductName,
            new_product_name: value,
        };

        try {
            setSavingEdit(true);

            const { data: response } = await updateHIVPrepProduct(payload);

            if (!response?.product) {
                throw new Error(
                    "Updated product details are missing from the API response"
                );
            }

            setEditingId(null);
            setEditingValue("");

            await fetchProducts();

            // Refresh the screen with the new product
            if (onRefreshProducts) {
                await onRefreshProducts();
            }

            if (onProductSaved) {
                await onProductSaved();
            }

            showSnackbar(
                response?.message || "Product updated successfully",
                "success"
            );
        } catch (error) {
            console.error("Failed to update product", error);

            const errorMessage =
                error?.response?.data?.message ||
                error?.message ||
                "Failed to update product";

            showSnackbar(errorMessage, "error");
        } finally {
            setSavingEdit(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteProduct) {
            return;
        }

        if (!therapyArea) {
            showSnackbar("Therapy area is required", "warning");
            return;
        }

        if (!scenarioName) {
            showSnackbar("Scenario name is required", "warning");
            return;
        }

        const payload = {
            ta_name: therapyArea,
            product_name: deleteProduct.product_name,
            // scenario_name: scenarioName,
        };

        try {
            setLoading(true);

            const { data: response } = await deleteHIVPrepProduct(payload);

            setDeleteProduct(null);

            await fetchProducts();

            if (onRefreshProducts) {
                await onRefreshProducts();
            }

            if (onProductSaved) {
                await onProductSaved();
            }

            showSnackbar(
                response?.message || "Product deleted successfully",
                "success"
            );

        } catch (error) {
            console.error("Failed to delete product", error);

            const errorMessage =
                error?.response?.data?.message ||
                error?.message ||
                "Failed to delete product";

            showSnackbar(errorMessage, "error");
        } finally {
            setLoading(false);
        }
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
                                    disabled={savingProduct}
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
                                                    disabled={savingEdit}
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
                                            {row.added_by || "-"}
                                        </TableCell>

                                        <TableCell>
                                            {row.modified_by || "-"}
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
                                                        onClick={handleSaveEdit}
                                                        disabled={savingEdit}
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
                                                        onClick={handleCancelEdit}
                                                        disabled={savingEdit}
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
                                                            disabled={savingEdit}
                                                            fontSize="small"
                                                        // color="warning"
                                                        />
                                                    </IconButton>

                                                    <IconButton
                                                        disabled={savingEdit}
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

            </Dialog >

            {/* Delete Confirmation */}

            < Dialog
                open={Boolean(deleteProduct)}
                // onClose={() => setDeleteProduct(null)
                // }
                onClose={() => {

                    if (!deletingProduct) {

                        setDeleteProduct(null);

                    }

                }}
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

            </Dialog >

        </>

    );

} 