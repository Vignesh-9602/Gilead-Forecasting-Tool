const favs = (state, action) => {
    switch (action.type) {
        case "USER_ID":
            return { ...state, userId: action.payload };
        case "LOGGED_IN_USER_ID":
            return { ...state, loggedInUserId: action.payload };
        case "CHAT_TITLES":
            return { ...state, chatTitles: action.payload };
        case "PINNED_CHAT_TITLES":
            return { ...state, pinnedChatTitles: action.payload };
        case "MESSAGE_DATA":
            return { ...state, messageData: action.payload };
        case "ACTIVE_CHAT":
            return { ...state, activeChat: action.payload };
        case "CHAT_ID":
            return { ...state, chatId: action.payload };
        case "MAX_WINDOW_ID":
            return { ...state, maxWindowId: action.payload };
        case "BOOKMARK_TITLE":
            return { ...state, bookmarksTitle: action.payload };
        case "FIRST_NAME":
            return { ...state, firstName: action.payload };
        case "LAST_NAME":
            return { ...state, lastName: action.payload };
        case "ACCESS_TOKEN":
            return { ...state, accessToken: action.payload };
        case "MESSAGE_ID":
            return { ...state, messageId: action.payload };
        case "EMAIL_ID":
            return { ...state, emailId: action.payload };
        case "USER_ROLE":
            return { ...state, userRole: action.payload };
        case "EDITED_CHAT_TITLE":
            return { ...state, editedChatTitle: action.payload };
        case "CHAT_TITLE":
            return { ...state, chatTitle: action.payload };
        case "REASONING_TAB":
            return { ...state, reasoningTab: action.payload };
        case "API_CHAT_TITLE":
            return { ...state, apiChatTitle: action.payload };
        case "LEFT_PANE_OPEN":
            return { ...state, leftPaneOpen: action.payload };
        case "BOOKMARKS_TAB":
            return { ...state, bookmarksTab: action.payload };
        case "PROFILE_IMAGE":
            return { ...state, profileImage: action.payload };
        case "SELECTED_REASONING_DATA":
            return { ...state, selectedReasoningData: action.payload };
        case "IS_LOADING":
            return { ...state, isLoading: action.payload };
        case "CHAT_TITLES_LOADING":
            return { ...state, chatTitlesLoading: action.payload };
        case "TYPING_LOADER":
            return { ...state, typingLoader: action.payload };
        case "HIGHLIGHT_CHAT":
            return { ...state, highlightChat: action.payload };
        case "ADD_CHAT_TITLE":
            return { ...state, chatTitles: [action.payload, ...state.chatTitles] };
        case "ADD_BOOKMARK_TITLE":
            return { ...state, bookmarksTitle: [action.payload, ...state.bookmarksTitle] };
        case "TOGGLE_GENIE_MODE":
            return {
                ...state,
                isGenieMode: action.payload
            };

        case "SET_GENIE_CHAT_ID":
            return {
                ...state,
                genieChatId: action.payload
            };

        case "SET_GENIE_API_CONVERSATION_ID":
            return {
                ...state,
                genieApiConversationId: action.payload
            };

        case "IS_EXISTING_CONVERSATION":
            return {
                ...state,
                isExistingConversation: action.payload
            };

        // case "ADD_CHAT_TITLE_PIN":
        //     return { ...state, chatTitles: [action.payload, ...state.chatTitles] };
        default:
            return state;
    }
};

export default favs;

