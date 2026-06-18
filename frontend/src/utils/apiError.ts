import axios from "axios";

export type ParsedApiError = {
  message: string;
  status?: number;
};

function parseDetailPayload(
  detail: unknown,
  status: number | undefined,
): ParsedApiError | null {
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

  return null;
}

/** FastAPI/Axios 오류 메시지를 사용자용 한 줄로 만든다. */
export function parseApiError(error: unknown): ParsedApiError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const data = error.response?.data as { detail?: unknown } | undefined;
    const parsed = parseDetailPayload(data?.detail, status);
    if (parsed) return parsed;

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

/** Blob 응답(예: CSV export 실패)의 JSON detail 파싱. */
export async function parseApiErrorAsync(error: unknown): Promise<ParsedApiError> {
  if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
    try {
      const text = await error.response.data.text();
      if (text.trim()) {
        const data = JSON.parse(text) as { detail?: unknown };
        const parsed = parseDetailPayload(data.detail, error.response.status);
        if (parsed) return parsed;
      }
    } catch {
      /* fall through */
    }
  }
  return parseApiError(error);
}
