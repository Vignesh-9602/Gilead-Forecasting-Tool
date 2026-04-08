import { httpClient, httpClient2 } from "../utility/httpClient";

export const mainConversation = () => {
  return `api/conversations/messages`;
};

export const genieConversation = () => {
  return `api/conversation/genie/genieResponse`;
};

export const mainConversationCharts = (message_id) => {
  return `api/conversations/${message_id}/chart_image`;
};

export const getConversationId = (payload) => {
  return httpClient.post(`/api/conversations`, payload);
};

export const getUserDetails = () => {
  return httpClient2.get(`/api/users/user_details`);
};

export const updateChatTitles = (conv_id, title) => {
  return `api/conversations/${conv_id}/title`;
};
export const bookmarkChatApi = (message_id) => {
  return `api/conversations/message/${message_id}/bookmark`;
};

export const feedbackApi = (payload) => {
  return httpClient.post(`/api/feedback/`, payload);
};
export const getLoginUrl = () => {
  return httpClient.get('/users/login');
};

export const getAllChats = () => {
  return httpClient.get(`/api/conversations/summary`);
};

export const updatePin = (conv_id, is_pinned) => {
  return httpClient.put(`/api/conversations/${conv_id}/pin`, {
    is_pinned
  });
};

export const deleteChats = (conv_id) => {
  return httpClient.delete(`/api/conversations/${conv_id}`);
};

export const getAllBookmarkedChats = () => {
  return httpClient.get(`/api/conversations/messages/bookmark_list`);
};

export const updateBookmarkTitle = (message_id, new_bookmark_title) => {
  return httpClient.put(`/api/conversations/messages/${message_id}/title`, {
    new_bookmark_title
  });
};

export const deleteBookmark = (message_id, is_bookmarked) => {
  return httpClient.put(`/api/conversations/messages/${message_id}/bookmark`, { is_bookmarked });
};
export const chatHistoryConversation = (conv_id) => {
  return httpClient.get(`/api/conversations/${conv_id}/messages`);
};

export const bookmarkChatConversation = (message_id) => {
  return httpClient.get(`/api/conversations/messages/${message_id}`);
};

export const getRecentQuestions = (limit = 4) => {
  return httpClient.get(`/api/conversations/recent_questions?limit=${limit}`);
};