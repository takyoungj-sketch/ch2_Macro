import axios from "axios";
import { attachApiScreenHeader } from "@ch2/macro-shell/apiScreen";

export const apiClient = axios.create({
  baseURL: "/api",
});
attachApiScreenHeader(apiClient, "profile", "main");

const apiToken = import.meta.env.VITE_API_TOKEN as string | undefined;
if (apiToken) {
  apiClient.defaults.headers.common["X-Api-Token"] = apiToken;
}
