import axios from "axios";
import { httpClient } from "./httpClient";

export const getTherapyAreaList = () => {
  return httpClient.get(`/api/ta/list`);
};

export const saveConfigurations = (payload) => {
  return httpClient.post(`/api/configurations`, payload);
};

export const getConfigurationByTherapyArea = (taName) => {
  return httpClient.get(`/api/configurations/${taName}`);
};


export const getAverageVials = (taName) => {
  return httpClient.get(`/api/configurations/${taName}/avg-vials`);
};

export const saveAverageVials = (payload) => {
  return httpClient.post(`/api/configurations/avg-vials`, payload);
};

export const getMetricFilters = (taName) => {
  return httpClient.get(`/api/metrics/filters/${taName}`);
};

export const applyMetricFilters = (payload) => {
  return httpClient.post(`/api/metrics/apply`, payload);
};


export const recalculateMetrics = (payload) => {
  return httpClient.post(`/api/metrics/recalculate`, payload);
};

export const normalizeMarketShare = async (payload) => {
  return httpClient.post(
    "/api/metrics/market-share/normalize",
    payload
  );
};

export const saveChanges = async (payload) => {
  return httpClient.post("/api/metrics/refresh", payload);
};


export const saveScenario = async (payload) => {
  return httpClient.post("/api/metrics/save", payload);
};

export const updateScenario = (payload) => {
  return httpClient.put("/api/update-scenario", payload);
};

export const getScenarioFilters = (taName) => {
  return httpClient.get(`/api/scenario/filters/${taName}`);
};

export const applyScenarioFilters = (payload) => {
  return httpClient.post(`/api/scenario/apply-filters`, payload);
};

export const saveScenarioSelection = (payload) => {
  return httpClient.post(`/api/scenario/save`, payload);
};

export const finalizeScenarios = (payload) => {
  return httpClient.post(`/api/scenario/finalize-scenarios`, payload);
};

export const getScenarioStatus = (payload) => {
  return httpClient.post(`/api/scenario/status`, payload);
};

export const clearStatus = (payload) => {
  return httpClient.post(`/api/scenario/clear`, payload);
};

export const getMarketEventFilters = (taName) => {
  return httpClient.get(`/api/market-events/filters/${taName}`);
};

export const getPersistencyFilters = (taName) => {
  return httpClient.get(`/api/persistency/filters/${taName}`);
};

export const applyMarketEventFilters = (payload) => {
  return httpClient.post(
    "/api/market-events/apply-filters",
    payload
  );
};

export const runMarketEventCalculation = (payload) => {
  return httpClient.post(
    "/api/market-events/run-calculation",
    payload
  );
};

export const saveMarketEventTable = (payload) => {
  return httpClient.post(
    "/api/market-events/market-events/save",
    payload
  );
};

export const applyPersistencyFilters = (payload) => {
  return httpClient.post(
    "/api/persistency/apply",
    payload
  );
};

export const calculateApplyPersistencyCurve = (payload) => {
  return httpClient.post(
    "/api/persistency/calculate-apply",
    payload
  );
};

export const getPersistencyCurves = (taName) => {
  return httpClient.get(`/api/persistency/curves/${taName}`);
};

export const getPersistencyCurveDetails = (curveName) => {
  return httpClient.get(`/api/persistency/curve-details/${curveName}`);
};

export const deletePersistencyCurve = (curveName) => {
  return httpClient.delete(`/api/persistency/delete-curve/${curveName}`);
};

export const applyPersistencyCurve = (
  payload
) => {
  return httpClient.post(
    "/api/persistency/apply-curve",
    payload
  );
};

export const saveAvgVials = (payload) => {
  return httpClient.post(
    "/api/persistency/avg-vials/save",
    payload
  );
};

export const saveDemandAdjustments = (payload) => {
  return httpClient.post(
    "/api/persistency/demand-adjustments/save",
    payload
  );
};

export const getComplianceConfiguration = (ta_name, indication, brand, lots) => {
  return httpClient.get("/api/persistency/compliance/configure",
    {
      params:
        { ta_name, indication, brand, lots },
    }
  );
};

export const applyComplianceConfiguration = (payload) => {
  return httpClient.post("/api/persistency/compliance/configure/apply", payload);
};

export const applyEditComplianceRowValues = (payload) => {
  return httpClient.post("/api/persistency/edit-complinace-row-values/apply", payload);
};

export const applyInventoryStockPercentage = (payload) => {
  return httpClient.post("/api/persistency/inventory/stock-percentage/apply", payload);
};

export const deleteMarketEvent = (payload) => {
  return httpClient.post(
    "/api/market-events/market-events/delete-event",
    payload
  );
};

export const getNetRevenueFilters = (taName) => {
  return httpClient.get(`/api/Net_Revenue/filters/${taName}`);
};

export const applyNetRevenueFilter = (payload) => {
  return httpClient.post(
    "/api/Net_Revenue/revenue/apply-filter",
    payload
  );
};

export const editNetRevenue = (payload) => {
  return httpClient.post(
    "/api/Net_Revenue/revenue/edit",
    payload
  );
};

export const getOutputFilters = (taName) => {
  return httpClient.get(
    `/api/Output_screen/new-screen/filters/${taName}`
  );
};

export const applyOutputFilters = (payload) => {
  return httpClient.post(
    "/api/Output_screen/demand-output/apply",
    payload
  );
};

export const getMonteCarloFilters = (taName) => {
  return httpClient.get(
    `/api/monte-carlo/filters/${taName}`
  );
};

export const runMonteCarloSimulation = (payload) => {
  return httpClient.post(
    "/api/monte-carlo/run",
    payload
  );
};

export const loginApi = (payload) =>
  httpClient.post("/api/login", payload);








// Liver APIs


// GET — loads existing config + available date options
export const getConfigurationByTherapyAreaHCV = (taName) => {
  return axios.get(`/api/liver/configurations/${taName}`);
};

// POST — saves / updates config
export const saveConfigurationsHCV = (payload) => {
  return axios.post(`/api/liver/configurations`, payload);
};

// Liver filters
export const getLiverFilters = (params = {}) => {
  return axios.get(`/api/liver/filters`, { params });
};

// POST — apply liver filters and return chart/table data
export const applyLiverFilters = (payload) => {
  return axios.post(`/api/liver/apply-filters`, payload);
};

// POST — recalculate liver with new ETS factors
export const recalculateLiver = (payload) => {
  return axios.post(`/api/liver/recalculate`, payload);
};

// POST — refresh liver table after manual edits
export const refreshLiverTable = (payload) => axios.post('/api/liver/refresh', payload);

// POST — create/update liver configurations with required envelope { config: { ... } }
export const postLiverConfigurations = (config) => {
  return axios.post(`/api/liver/configurations`, { config });
};

// POST — save a liver scenario
export const saveLiverScenario = (payload) => {
  return axios.post(`/api/liver/save-scenario`, payload);
};
// PUT — update an existing non-Base liver scenario
export const updateLiverScenario = (payload) => {
  return axios.put(`/api/liver/update-scenario`, payload);
};

// POST — activate a liver scenario
export const activateLiverScenario = (payload) => {
  return axios.post(`/api/liver/activate-scenario`, payload);
};

// DELETE — remove a saved liver scenario
export const deleteLiverScenario = (payload) => {
  return axios.delete(`/api/liver/delete-scenario`, { data: payload });
};

export const getLiverMarketEventsFilters = (ta = "HCV") => {
  return httpClient.get("/api/liver-market-events/filters", {
    params: { ta },
  });
};

// GET — loads every previously-saved Impact Curve Configuration row for the
// Events Management tab, grouped by event type (product_event / payer_event
// / payment_type_payer_product_event). This was previously imported and
// called from ModelInput.jsx but never actually defined here, so every call
// silently threw (caught by the surrounding try/catch) and the Events
// Management page never listed anything on open.
export const getLiverMarketEventsList = (taName = "HCV") => {
  return httpClient.get(`/api/liver-market-events/market-events/${encodeURIComponent(taName)}`);
};

// GET — list products (base + newly added) for the "Manage New Products"
// modal on the Impact Curve Configuration screen.
export const getLiverMarketEventsProducts = (params = {}) => {
  return httpClient.get("/api/liver-market-events/products", {
    params,
  });
};

// POST — add a new product from the "Manage New Products" modal.
// payload: { product_name: "string" }
export const addLiverMarketEventsProduct = (payload) => {
  return httpClient.post("/api/liver-market-events/products", payload);
};

// PUT — rename a product; payload: { new_product_name: "string" }
export const updateLiverMarketEventsProduct = (productName, payload) => {
  return httpClient.put(
    `/api/liver-market-events/products/${encodeURIComponent(productName)}`,
    payload,
  );
};

// DELETE — remove a product.
export const deleteLiverMarketEventsProduct = (productName) => {
  return httpClient.delete(
    `/api/liver-market-events/products/${encodeURIComponent(productName)}`,
  );
};

export const applyLiverMarketEventsFilters = (payload) => {
  return httpClient.post("/api/liver-market-events/apply-filters", payload);
};

export const refreshLiverMarketEventsTable = (payload) => {
  return httpClient.post("/api/liver-market-events/refresh", payload);
};

export const runLiverMarketEventsCalculation = (payload) => {
  return httpClient.post("/api/liver-market-events/run-calculation", payload);
};



export const saveLiverMarketEvents = (payload) => {
  return httpClient.post("/api/liver-market-events/save-scenario", payload);
};

// POST — save the Impact Curve Configuration (Events Management tab) rows
// for the currently applied filters.
export const saveLiverMarketEventsConfig = (payload) => {
  return httpClient.post("/api/liver-market-events/save", payload);
};

// DELETE — remove a single market event (Impact Curve Configuration row).
// event_id is a path param; ta_name/event_type are query params.
// event_type is one of: "product_event" | "payer_event" | "payment_type_payer_product_event".
export const deleteLiverMarketEvent = (eventId, { ta_name, event_type }) => {
  return httpClient.delete(`/api/liver-market-events/${eventId}`, {
    params: { ta_name, event_type },
  });
};

// GET — Output screen filters for a therapy area (e.g. ta=HCV)
export const getLiverOutputFilters = (ta) => {
  return httpClient.get(`/api/liver-output/filters`, {
    params: { ta },
  });
};

// POST — apply Output screen filters and get chart/table data back
export const applyLiverOutputFilters = (payload) => {
  return httpClient.post(`/api/liver-output/apply-filters`, payload);
};





//HIV API's
export const getHIVConfigurationByTherapyArea = (taName) => {
  return httpClient.get(`/api/hiv_treat/configurations/${taName}`);
};

export const saveHIVConfigurations = (payload) => {
  return httpClient.post(`/api/hiv_treat/save-configurations`, payload);
};


export const getHIVModelInputFilters = (taName) => {
  return httpClient.get("/api/hiv_treat/model-input-filters", {
    params: {
      ta_name: taName,
    },
  });
};

export const applyHIVScenario = (payload) => {
  return httpClient.post(
    "/api/hiv_treat/applyfilter",
    payload
  );
};

export const recalculateHIVScenario = (payload) =>
  httpClient.post(
    "/api/hiv_treat/recalculate",
    payload
  );

export const editHIVScenario = (payload) =>
  httpClient.post(
    "/api/hiv_treat/refresh-edits",
    payload
  );


export const saveHIVScenario = (payload) =>
  httpClient.post(
    "/api/hiv_treat/save-scenarios",
    payload
  );

export const applySelectedHIVScenario = (payload) =>
  httpClient.post(
    "/api/hiv_treat/apply_selected_scenario",
    payload
  );

export const updateHIVScenario = (scenarioName, payload) =>
  httpClient.put(
    `/api/hiv_treat/scenarios/${encodeURIComponent(scenarioName)}`,
    payload
  );

export const getHIVMarketEventFilters = (taName) =>
  httpClient.get("/api/hiv_treat/get_market_event_filters", {
    params: {
      ta_name: taName,
    },
  });

export const applyHIVMarketEventFilter = (payload) =>
  httpClient.post(
    "/api/hiv_treat/apply_market_event_filters",
    payload
  );

export const runHIVMarketEventCalculation = (payload) =>
  httpClient.post(
    "/api/hiv_treat/run-calculation",
    payload
  );

export const editHIVImpactCurveTable = (payload) =>
  httpClient.post(
    "/api/hiv_treat/edit_save",
    payload
  );

export const getHIVOutputFilters = (taName) =>
  httpClient.get("/api/hiv_treat/get_output_screen_filters", {
    params: {
      ta_name: taName,
    },
  });

export const applyHIVOutputFilters = (payload) =>
  httpClient.post(
    "/api/hiv_treat/output-screen/apply-filters",
    payload
  );

export const uploadPersistencyCurve = (formData) =>
  httpClient.post(
    "/api/persistency/upload-curve",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );

export const updatePersistencyCurve = (payload) =>
  httpClient.post(
    "/api/persistency/Edit-curve",
    payload
  );

// export const deleteHIVScenario = (payload) =>
//   httpClient.delete("/api/hiv_treat/scenarios/{scenario_name}", payload);

export const deleteHIVScenario = (payload) =>
  httpClient.delete(
    `/api/hiv_treat/scenarios/${payload.scenario_name}`,
    {
      data: payload,
    }
  );

export const addHIVProduct = (payload) =>
  httpClient.post(
    "/api/hiv_treat/products",
    payload
  );

export const getHIVProducts = () => {
  return httpClient.get("/api/hiv_treat/products");
};

export const updateHIVProduct = (payload) => {
  return httpClient.put("/api/hiv_treat/products", payload);
};

export const deleteHIVProduct = (payload) => {
  return httpClient.delete("/api/hiv_treat/products", {
    data: payload,
  });
};


// HIV Prep API's

export const getHIVPrepConfigurationByTherapyArea = (taName) => {
  return httpClient.get(`/api/hiv_prep/configurations/${taName}`);
};

export const saveHIVPrepConfigurations = (payload) => {
  return httpClient.post(`/api/hiv_prep/save-configurations`, payload);
};