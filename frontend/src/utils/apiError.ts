import axios from "axios";

export type ParsedApiError = {
  message: string;
  status?: number;
};

/** FastAPI/Axios 오류 메시지를 사용자용 한 줄로 만든다. */
export function parseApiError(error: unknown): ParsedApiError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const data = error.response?.data as { detail?: unknown } | undefined;
    const detail = data?.detail;

    if (typeof detail === "string" && detail.trim()) {
      return { message: detail.trim(), status };
    }

    if (Array.isArray(detail)) {
      const parts = detail.map((item) => {
        if (
          typeof item === "object" &&
          item !== null &&
          "msg" in item &&
          typeof (item as { msg: unknown }).msg === "string"
        ) {
          const loc = (item as { loc?: unknown }).loc;
          const locStr =
            Array.isArray(loc) && loc.length ? `${loc.slice(1).join(".")}: ` : "";
          return `${locStr}${(item as { msg: string }).msg}`;
        }
        return JSON.stringify(item);
      });
      return { message: parts.join(" · "), status };
    }

    if (detail != null && typeof detail !== "object") {
      return { message: String(detail), status };
    }

    if (!error.response) {
      return {
        message:
          "서버에 연결할 수 없습니다. 백엔드(예: http://localhost:8000)가 실행 중인지 확인해 주세요.",
      };
    }

    const fallback =
      typeof error.response.statusText === "string" &&
      error.response.statusText.trim()
        ? `${error.response.status} ${error.response.statusText}`
        : `요청 실패 (${status ?? "?"})`;
    return { message: fallback, status };
  }

  if (error instanceof Error) return { message: error.message };
  return { message: "알 수 없는 오류가 발생했습니다." };
}
