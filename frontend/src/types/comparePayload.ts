import type { MatrixCell, StatsResult } from "../types";

/** 비교 전용 탭에 넘기는 최소 스냅샷 (추가 API 없음) */
export interface ComparePayloadV1 {
  v: 1;
  savedAt: number;
  /** 창 제목·표지용 */
  title: string;
  matrix: MatrixCell[];
  by_zone: Record<string, StatsResult>;
  by_land_category: Record<string, StatsResult>;
  by_region: Record<string, StatsResult>;
  /** 표시 순서 */
  regionOrder: string[];
  regionLabels: Record<string, string>;
}
