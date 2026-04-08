// index.js
import { create } from 'zustand';
import { initialState } from './state';
import { showSnackbar, hideSnackbar } from './actions';

const useSnackbarStore = create((set) => ({
  ...initialState,
  showSnackbar: showSnackbar(set),
  hideSnackbar: hideSnackbar(set),
}));

export default useSnackbarStore;
