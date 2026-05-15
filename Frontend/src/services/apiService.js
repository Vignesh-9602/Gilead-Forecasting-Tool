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