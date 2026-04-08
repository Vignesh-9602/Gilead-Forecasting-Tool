import React from 'react';
import { Snackbar, Alert } from '@mui/material';
import { useSnackbarStore } from '../../stores';

function SnackbarNotification() {
    const { snackbar, hideSnackbar } = useSnackbarStore();

    const handleClose = (_, reason) => {
        if (reason === 'clickaway') return;
        hideSnackbar();
    };

    return (
        <Snackbar
            open={snackbar.open}
            onClose={handleClose}
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            autoHideDuration={3000}
        >
            <Alert
                onClose={handleClose}
                severity={snackbar.severity}
                sx={{ width: '100%' }}
            >
                {snackbar.message}
            </Alert>
        </Snackbar>
    );
};

export default SnackbarNotification;
