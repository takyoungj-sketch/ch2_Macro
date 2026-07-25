import axios from "axios";

export const apiClient = axios.create({
  baseURL: "/api",
});

const apiToken = import.meta.env.VITE_API_TOKEN as string | undefined;
if (apiToken) {
  apiClient.defaults.headers.common["X-Api-Token"] = apiToken;
}
