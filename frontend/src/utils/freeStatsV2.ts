import type { FreeStatsV2Response, PaidAnalysisRequest, YearlyTradeStat } from "../types";


/** 백엔드 `default_as_of_month_for_service` 와 동일: 해당 날짜가 속한 달의 직전 달 1일(UTC 일 단위). */
export function asOfMonthFromAssumedServiceToday(isoDate: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate.trim());
  if (!m) {
    throw new Error(`VITE_STATS_V2_ASSUMED_TODAY 형식 오류(YYYY-MM-DD): ${isoDate}`);
  }
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const firstUtc = Date.UTC(y, mo - 1, 1);
  const lastPrevUtc = firstUtc - 86400000;
  const d = new Date(lastPrevUtc);
  const yy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  return `${yy}-${mm}-01`;
}

/**
 * `VITE_STATS_V2_ASSUMED_TODAY` 가 있으면 API에 넣을 `as_of_month`(YYYY-MM-01).
 * 백엔드 `STATS_V2_ASSUMED_TODAY` 와 같은 값을 두면 무료 V2 기준월이 항상 일치합니다.
 */
export function viteOptionalV2AsOfMonth(): string | undefined {
  const raw = import.meta.env.VITE_STATS_V2_ASSUMED_TODAY as string | undefined;
  if (!raw || !String(raw).trim()) return undefined;
  try {
    return asOfMonthFromAssumedServiceToday(String(raw).trim());
  } catch {
    return undefined;
  }
}

/** V2 응답의 contract_date 구간(일 단위)이 걸치는 달력 연도 범위 → 필터 연동/매트릭스 연도 요청에 사용 */
export function v2PeriodToYearRange(
  data: Pick<FreeStatsV2Response, "period_start" | "period_end">
): { year_from: number; year_to: number } {
  const yf = Number(String(data.period_start).slice(0, 4));
  const yt = Number(String(data.period_end).slice(0, 4));
  if (!Number.isFinite(yf) || !Number.isFinite(yt)) return { year_from: 0, year_to: 0 };
  return { year_from: yf, year_to: yt };
}

/**
 * DECISIONS D-002 / D-006 — `as_of_month`(YYYY-MM-01 또는 stats_reference_date 호환) 를
 * 사용자 친화 라벨 「YYYY년 M월 말 기준」으로 변환.
 *
 * 입력 우선순위:
 *   - `as_of_month` (그 달 말일이 곧 라벨의 "M월 말") — 정석 표기
 *   - 없으면 `stats_reference_date` (= as_of_month 다음 달 1일)에서 한 달 빼서 동일 라벨
 *
 * 둘 다 없거나 형식이 잘못되면 `null`. (호출자는 본 문구를 숨기거나 "—" 등으로 폴백.)
 */
export function statsAsOfLabel(input: {
  as_of_month?: string | null;
  stats_reference_date?: string | null;
}): string | null {
  const trim = (v: string | null | undefined) => (v == null ? "" : String(v).trim());
  const a = trim(input.as_of_month);
  const r = trim(input.stats_reference_date);

  let y = NaN;
  let m = NaN;
  if (a) {
    const mm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(a);
    if (mm) {
      y = Number(mm[1]);
      m = Number(mm[2]);
    }
  } else if (r) {
    const mm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(r);
    if (mm) {
      // stats_reference_date = as_of_month 의 다음 달 1일 → 한 달 빼서 표기에 맞춘다.
      const yy = Number(mm[1]);
      const mo = Number(mm[2]);
      if (mo === 1) {
        y = yy - 1;
        m = 12;
      } else {
        y = yy;
        m = mo - 1;
      }
    }
  }
  if (!Number.isFinite(y) || !Number.isFinite(m) || m < 1 || m > 12) return null;
  return `${y}년 ${m}월 말 기준`;
}

/** 참고표: 순수 만년력 1·1~12·31 연도별. */
export function calendarYearReferenceRows(
  data: FreeStatsV2Response
): YearlyTradeStat[] | undefined {
  const r = data.by_year_calendar_reference;
  return r != null && r.length > 0 ? r : undefined;
}

/** 매트릭스 셀 모달(`/paid/matrix-yearly`) 롤링 트렌드 본문. */
export function rollingMatrixModalPayload(
  data: Pick<
    FreeStatsV2Response,
    "period_start" | "period_end" | "window_years" | "stats_reference_date"
  >
): Pick<
  PaidAnalysisRequest,
  | "rolling_matrix_period_start"
  | "rolling_matrix_period_end"
  | "rolling_bucket_count"
  | "rolling_stats_reference_date"
  | "year_from"
  | "year_to"
  | "years"
> {
  return {
    rolling_matrix_period_start: data.period_start ?? null,
    rolling_matrix_period_end: data.period_end ?? null,
    rolling_bucket_count: data.window_years,
    rolling_stats_reference_date: data.stats_reference_date ?? null,
    year_from: null,
    year_to: null,
    years: null,
  };
}
