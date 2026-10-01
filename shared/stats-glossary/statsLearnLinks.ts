/** CH2 DATA Learn — Macro ? 팝업에서 외부 SSOT로 연결 */
const LEARN_BASE = "https://ch2data.com";

export const STATS_LEARN_URLS: Record<string, string> = {
  r_squared: `${LEARN_BASE}/learn/stats/model-fit/#r-squared`,
  adj_r_squared: `${LEARN_BASE}/learn/stats/model-fit/#adj-r-squared`,
  mape: `${LEARN_BASE}/learn/stats/model-fit/#mape`,
  cv_mape: `${LEARN_BASE}/learn/stats/cross-validation/#cv-mape`,
  pearson_r: `${LEARN_BASE}/learn/stats/correlation/`,
  ols: `${LEARN_BASE}/learn/stats/regression/`,
  log_model: `${LEARN_BASE}/learn/stats/log-regression/`,
  fit_n: `${LEARN_BASE}/learn/stats/sample-size/`,
  iqr_outliers: `${LEARN_BASE}/learn/stats/iqr-outliers/#iqr-multiplier`,
  unit_price_mean: `${LEARN_BASE}/learn/stats/mean-and-median/`,
  unit_price_median: `${LEARN_BASE}/learn/stats/mean-and-median/`,
  quantile: `${LEARN_BASE}/learn/stats/quantiles/`,
  insight_p50: `${LEARN_BASE}/learn/stats/quantiles/`,
};

export function getStatsLearnUrl(termId: string): string | undefined {
  return STATS_LEARN_URLS[termId];
}
