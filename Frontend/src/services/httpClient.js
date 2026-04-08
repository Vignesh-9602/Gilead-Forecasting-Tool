import axios from "axios";
import { useSnackbarStore } from "../stores";

const baseURL = process.env.REACT_APP_BASE_URL

// Flag to prevent duplicate snackbar + redirect
let isSessionExpired = false;

const handleTokenExpiry = () => {
    const { showSnackbar } = useSnackbarStore.getState();
    if (isSessionExpired) return; // prevent multiple calls

    isSessionExpired = true;
    showSnackbar("You're session has expired. Reloading the application", "error");

    setTimeout(() => {
        clearWholeStorage();
        window.location.href = "/";
    }, 2000);
};

// Default HTTP client for general APIs (uses access_token)
const httpClient = axios.create({
    baseURL: baseURL,
    withCredentials: false,
    headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` }
});

// Inject access_token before every request for httpClient
httpClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        } else {
            delete config.headers.Authorization;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Handle expired/invalid token globally for httpClient
httpClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response) {
            const status = error.response.status;
            if ([401, 403, 302].includes(status)) {
                console.warn("Token expired or unauthorized, clearing storage...");
                handleTokenExpiry();
                return Promise.reject({ ...error, handledGlobally: true });
            }
        }
        return Promise.reject(error);
    }
);

// Second HTTP client to manage APIs requiring id_token
const httpClient2 = axios.create({
    baseURL: baseURL,
    withCredentials: true, // Try with credentials
    headers: {
        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        "Id-Token": `${localStorage.getItem('id_token')}`
    },
});

// Inject id_token before every request for httpClient2
httpClient2.interceptors.request.use(
    (config) => {
        const accessToken = localStorage.getItem('access_token');
        const idToken = localStorage.getItem('id_token');

        if (accessToken) {
            config.headers.Authorization = `Bearer ${accessToken}`;
        } else {
            delete config.headers.Authorization; // prevent Bearer null
        }

        if (idToken) {
            // Backend expects exactly "Id-Token" header
            config.headers['Id-Token'] = `${idToken}`;
        } else {
            delete config.headers['Id-Token'];
        }

        return config;
    },
    (error) => Promise.reject(error)
);

// Handle expired/invalid token globally for httpClient2
httpClient2.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response) {
            const status = error.response.status;
            if ([401, 403, 302].includes(status)) {
                console.warn("Token expired or unauthorized, clearing storage...");
                handleTokenExpiry();
                return Promise.reject({ ...error, handledGlobally: true });
            }
        }
        return Promise.reject(error);
    }
);

const clearCookies = () => {
    document.cookie.split(";").forEach(cookie => {
        const eqPos = cookie.indexOf("=");
        const name = eqPos > -1 ? cookie.slice(0, eqPos) : cookie;
        document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
    });
};

const clearWholeStorage = () => {
    localStorage.clear();
    sessionStorage.clear();
    clearCookies();
};

export { httpClient, httpClient2 };


// import axios from 'axios';
// import { create } from 'zustand';

// const baseURL = import.meta.env.REACT_APP_BASE_URL;
// const env = import.meta.env.REACT_APP_ENV;
// const httpClient = axios.create({
//     baseURL: baseURL
// });

// // Tracking user activity and handle 401 errors as specified, we need to:
// //--------------------------------------------------------------------------------------------
// // Implement user activity tracking.
// // Modify the 401 error handling logic to distinguish between active and inactive users.
// // Refresh the tokens if the user is active, and retry the failed request with the new tokens.
// //---------------------------------------------------------------------------------------------

// // Token Handling:

// // Modified useTokenStore to store both the access token and the refresh token.
// // The refreshAuthToken function handles refreshing the tokens using the refresh token.
// const useTokenStore = create((set) => ({
//   token: localStorage.getItem('token') || null,
//   refreshToken: localStorage.getItem('refreshToken') || null,
//   setToken: (newToken, newRefreshToken) => {
//     set({
//       token: newToken,
//       refreshToken: newRefreshToken,
//     });
//     localStorage.setItem('token', newToken);
//     localStorage.setItem('refreshToken', newRefreshToken);
//   },
// }));

// // Activity Tracking:

// // Added a useActivityStore store to manage user activity state.
// // The updateLastActivity method updates the timestamp of the last activity.
// // The isUserActive method checks if the user has been active within the last 5 minutes.
// const useActivityStore = create((set) => ({
//   lastActivity: Date.now(),
//   updateLastActivity: () => set({ lastActivity: Date.now() }),
//   isUserActive: () =>
//     Date.now() - useActivityStore.getState().lastActivity < 5 * 60 * 1000, // 5 minutes of inactivity
// }));

// document.addEventListener(
//   'mousemove',
//   useActivityStore.getState().updateLastActivity()
// );
// document.addEventListener(
//   'keydown',
//   useActivityStore.getState().updateLastActivity()
// );
// document.addEventListener(
//   'click',
//   useActivityStore.getState().updateLastActivity()
// );

// console.log('User is active:', useActivityStore.getState().isUserActive());

// const refreshAuthToken = async () => {
//   const { refreshToken } = useTokenStore.getState();
//   // console.log("refreshToken", refreshToken)
//   try {
//     const response = await axios.get(`${baseURL}refresh_token`, {
//       params: { refresh_token: refreshToken },
//     });
//     // console.log(" refresh token REsponse", response.data)
//     const { access_token, refresh_token: newRefreshToken } = response.data;

//     useTokenStore.setState({
//       token: access_token,
//       refreshToken: newRefreshToken,
//     });
//     // console.log("Refresh otken in use token  store", useTokenStore.getState().refreshToken)
//     return access_token;
//   } catch (error) {
//     console.error('Failed to refresh token', error);
//     return null;
//   }
// };

// httpClient.interceptors.request.use(
//   (config) => {
//     const token = useTokenStore.getState().token;
//     // const env = process.env.NODE_ENV;

//     if (token) {
//       if (env === 'local') {
//         console.log('ENV IS LOCAL:', env);
//         config.headers['x-user-orche-token'] = `Bearer ${token}`;
//       } else {
//         console.log('ENV IS Non local:', env);

//         config.headers['x-user-token'] = `Bearer ${token}`;
//       }
//     }

//     return config;
//   },
//   (error) => Promise.reject(error)
// );


// // Add a response interceptor
// httpClient.interceptors.response.use(
//   (response) => response,
//   async (error) => {
//     if (error.response && error.response.status === 401) {
//       const isActive = useActivityStore.getState().isUserActive();

//       if (isActive) {
//         const newToken = await refreshAuthToken();
//         if (newToken) {
//           error.config.headers.Authorization = `Bearer ${newToken}`;
//           return httpClient.request(error.config); // Retry the request with the new token
//         }
//       }
//       localStorage.removeItem('token');
//       localStorage.removeItem('refreshToken');
//       // window.location.href = '/login';
//       localStorage.setItem('token', null);
//     }
//     return Promise.reject(error);
//   }
// );

// export default httpClient;
// export { useTokenStore, useActivityStore };
