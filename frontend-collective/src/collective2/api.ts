import axios from "axios";

const token = (import.meta.env.VITE_API_TOKEN ?? "").trim();

const api = axios.create({
  baseURL: "/api/collective2",
  headers: token ? { "X-Api-Token": token } : undefined,
});

export async function fetchCollective2Access(): Promise<{ ok: boolean }> {
  const { data } = await api.get<{ ok: boolean }>("/access");
  return data;
}
