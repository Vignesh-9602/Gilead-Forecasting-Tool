import axios from "axios";

const baseURL = import.meta.env.VITE_BASE_URL;

// Create axios instance
const httpClient = axios.create({
  baseURL: baseURL,
  withCredentials: false,
});

// Request interceptor (attach token if exists)
httpClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// httpClient.interceptors.request.use(
//   (config) => {
//     const user = JSON.parse(
//       localStorage.getItem("user")
//     );

//     if (user?.email) {
//       config.headers["X-User-Email"] =
//         user.email;
//     }

//     return config;
//   },
//   (error) => Promise.reject(error)
// );

// Response interceptor (handle errors globally)
httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;

      if (status === 401 || status === 403) {
        console.warn("Unauthorized - clearing session");

        localStorage.clear();
        window.location.href = "/";
      }
    }

    return Promise.reject(error);
  }
);

export { httpClient };