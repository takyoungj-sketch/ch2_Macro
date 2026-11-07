import type { AiContextPayload } from "./aiClient";

/** Request-time copy of the rendered public report, never the chat or raw API rows. */
export function withVisibleInsightReport(context: AiContextPayload): AiContextPayload {
  if (context.app !== "insight" || typeof document === "undefined") return context;
  const article = document.querySelector("article");
  if (!article) return context;
  const sections: Array<{ heading: string; text: string }> = [];
  let heading = article.querySelector("h2")?.textContent?.trim() || "Macro Insight";
  let length = 0;
  let truncated = false;
  for (const node of article.querySelectorAll<HTMLElement>("h3,h4,p,li,tr,figcaption")) {
    if (!node.getClientRects().length || node.closest("[hidden],[aria-hidden='true']")) continue;
    if (/^H[34]$/.test(node.tagName)) { heading = node.innerText.trim(); continue; }
    if (node.tagName === "P" && node.closest("li")) continue;
    const text = node.innerText.trim();
    if (!text) continue;
    if (length + text.length > 30000 || sections.length >= 120) { truncated = true; break; }
    sections.push({ heading, text });
    length += text.length;
  }
  return { ...context, facts: { ...context.facts, report: {
    title: article.querySelector("h2")?.textContent?.trim() || context.panel,
    sections, truncated, public_number: new URLSearchParams(window.location.search).get("q"),
    source: "visible_insight_report",
  } } };
}
