// stores/useLoadingStore/index.js
import { create } from 'zustand';
import { initialState } from './state';
import { actions } from './actions';

const useLoadingStore = create((set) => ({
  ...initialState,
  ...actions(set),
}));

export default useLoadingStore;
