/** 페이지·모달 분석 설명 (토지·복합·집합 공통). */

export type AnalysisExplainPreset = {
  id: string;
  question: string;
  answer: string;
};

export type AnalysisExplain = {
  spec_id: string;
  spec_version: string;
  title: string;
  summary: string;
  formula?: string | null;
  index_rule?: string | null;
  reference?: string | null;
  floor_groups?: string[];
  controls?: string[];
  interpretation: string[];
  limitations: string[];
  interpretation_hints?: string[];
  presets?: AnalysisExplainPreset[];
};
