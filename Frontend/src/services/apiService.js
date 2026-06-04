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

// export const mainConversation = () => {
//   return `api/conversations/messages`;
// };

// export const genieConversation = () => {
//   return `api/conversation/genie/genieResponse`;
// };

// export const mainConversationCharts = (message_id) => {
//   return `api/conversations/${message_id}/chart_image`;
// };

// export const getConversationId = (payload) => {
//   return httpClient.post(`/api/conversations`, payload);
// };

// export const getUserDetails = () => {
//   return httpClient2.get(`/api/users/user_details`);
// };

// export const updateChatTitles = (conv_id, title) => {
//   return `api/conversations/${conv_id}/title`;
// };
// export const bookmarkChatApi = (message_id) => {
//   return `api/conversations/message/${message_id}/bookmark`;
// };

// export const feedbackApi = (payload) => {
//   return httpClient.post(`/api/feedback/`, payload);
// };
// export const getLoginUrl = () => {
//   return httpClient.get('/users/login');
// };

// export const getAllChats = () => {
//   return httpClient.get(`/api/conversations/summary`);
// };

// export const deleteBookmark = (message_id, is_bookmarked) => {
//   return httpClient.put(`/api/conversations/messages/${message_id}/bookmark`, { is_bookmarked });
// };
// export const chatHistoryConversation = (conv_id) => {
//   return httpClient.get(`/api/conversations/${conv_id}/messages`);
// };

// export const bookmarkChatConversation = (message_id) => {
//   return httpClient.get(`/api/conversations/messages/${message_id}`);
// };

// export const getRecentQuestions = (limit = 4) => {
//   return httpClient.get(`/api/conversations/recent_questions?limit=${limit}`);
// };
