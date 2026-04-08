export const getErrorMessage = (error) => {
  if (error?.response?.status) {
    switch (error.response.status) {
      case 400:
        return "Oops! I couldn’t understand that request. Please check your input and try again.";
      case 401:
        return "You don’t have the access. Please contact your admin to Login.";
      case 403:
        return "This data is restricted. Please reach out for permissions.";
      case 404:
        return "Looks like the field you’re asking for isn’t available.";
      case 409:
        return "Conflict. The request could not be completed due to a conflict.";
      case 422:
        return "Unprocessable entity. Please check the data you submitted.";
      case 429:
        return "I’m receiving too many requests right now. Please try again in a moment.";
      case 500:
        return "Something went wrong on my side. Please try again later.";
      case 502:
        return "The query engine isn’t responding right now. Please try again.";
      case 503:
        return "The system is under maintenance. Please check back later.";
      case 504:
        return "This request is taking longer than expected. Please try again.";
      default:
        return "An unexpected error occurred. Please try again.";
    }
  }
  return "Something went wrong. Please try again later.";
};
