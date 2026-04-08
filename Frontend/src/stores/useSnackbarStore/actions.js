// actions.js
export const showSnackbar =
  (set) =>
  (message, severity = 'success') =>
    set({
      snackbar: { open: true, message, severity },
    });

export const hideSnackbar = (set) => () =>
  set({
    snackbar: { open: false, message: '', severity: 'success' },
  });
