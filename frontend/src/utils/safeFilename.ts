export function safeFileStem(name: string, maxLen = 48): string {
  const t = name.trim().replace(/[<>:"/\\|?*\u0000-\u001f]+/g, "_").replace(/\s+/g, "_");
  if (t.length <= maxLen) return t || "export";
  return t.slice(0, maxLen) || "export";
}
