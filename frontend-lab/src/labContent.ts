import roadmapJson from "../../docs/lab/roadmap.json";
import planJson from "../../docs/lab/plan.json";

export type PlanDomainId = "land" | "built" | "collective" | "rent" | "profile" | "admin";

export type PlanCellStatus = "done" | "stopped" | "planned";
export type PlanCommit = "committed" | "needed" | "none";

export type PlanCell = {
  text: string;
  status: PlanCellStatus;
  commit?: PlanCommit;
  decision?: string;
};

export type PlanGrid = {
  updated: string;
  domains: { id: PlanDomainId; label: string }[];
  past: { date: string; cells: Partial<Record<PlanDomainId, PlanCell>> }[];
  today: { date: string; cells: Partial<Record<PlanDomainId, PlanCell>> };
  next: { cells: Partial<Record<PlanDomainId, PlanCell>> };
  common: { text: string; decision?: string };
};

export const plan = planJson as PlanGrid;

export type DecisionStatus = "confirmed" | "experimental" | "deferred";

export type DecisionCard = {
  id: string;
  topic: string;
  date: string;
  status: DecisionStatus;
  background: string;
  decision: string;
  rationale: string;
  revisit: string;
  related?: string[];
};

export type RoadmapSlot = {
  title: string;
  note: string;
  journal: string | null;
  decisions: string[];
};

export type Roadmap = {
  updated: string;
  now: RoadmapSlot;
  next: RoadmapSlot;
  then: RoadmapSlot;
  later: RoadmapSlot;
};

export type JournalTag = { kind: string; text: string };

export type JournalEntry = {
  date: string;
  work: string[];
  decisions: string[];
  verify: string[];
  next: string[];
  commit: string[];
  tags: JournalTag[];
};

const journalRaw = import.meta.glob("../../docs/lab/journal/*.md", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

const decisionRaw = import.meta.glob("../../docs/lab/decisions/*.json", {
  eager: true,
  import: "default",
}) as Record<string, DecisionCard>;

export const roadmap = roadmapJson as Roadmap;

export function loadDecisions(): DecisionCard[] {
  return Object.values(decisionRaw).sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : a.id.localeCompare(b.id)));
}

export function getDecision(id: string): DecisionCard | undefined {
  return loadDecisions().find((d) => d.id === id);
}

export function loadJournals(): JournalEntry[] {
  return Object.entries(journalRaw)
    .map(([path, md]) => {
      const file = path.split("/").pop() || "";
      const date = file.replace(/\.md$/, "");
      return parseJournal(md, date);
    })
    .sort((a, b) => (a.date < b.date ? 1 : -1));
}

export function parseJournal(md: string, date: string): JournalEntry {
  const sections: Record<string, string[]> = {
    작업: [],
    결정: [],
    검증: [],
    다음: [],
    커밋: [],
    태그: [],
  };
  let current = "";
  for (const line of md.split(/\r?\n/)) {
    const h = line.match(/^##\s+(.+)\s*$/);
    if (h) {
      current = h[1].trim();
      continue;
    }
    const item = line.match(/^-\s+(.+)$/);
    if (item && current && sections[current]) {
      sections[current].push(item[1].trim());
    }
  }
  const tags: JournalTag[] = sections["태그"].map((t) => {
    const m = t.match(/^\[([^\]]+)\]\s*(.*)$/);
    if (!m) return { kind: "기타", text: t };
    const raw = m[1];
    const kind = raw === "GPT" ? "제안" : raw === "Cursor" ? "구현" : raw;
    return { kind, text: m[2] };
  });
  return {
    date,
    work: sections["작업"],
    decisions: sections["결정"],
    verify: sections["검증"],
    next: sections["다음"],
    commit: sections["커밋"],
    tags,
  };
}

export const COMMIT_LABEL: Record<PlanCommit, string> = {
  committed: "커밋됨",
  needed: "커밋 필요",
  none: "",
};

export const STATUS_LABEL: Record<DecisionStatus, string> = {
  confirmed: "확정",
  experimental: "실험적 — 최적값으로 검증된 설정이 아님",
  deferred: "보류",
};

export const TOOL_WHY: Record<string, string[]> = {
  plan: [],
  qa: ["D-042"],
  twin: ["D-041", "D-044", "D-029-weights"],
  rent: ["D-040"],
};
