import { insightLearnChapters, insightLearnUrl } from "./insightLearnLinks";

export default function InsightLearnFooter({ q }: { q: string | null }) {
  const chapters = insightLearnChapters(q);
  if (!chapters.length) return null;

  return (
    <footer className="max-w-3xl mx-auto px-4 pb-10 pt-2">
      <div className="rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-900/50 px-4 py-3">
        <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-2">
          통계학 &amp; 데이터 분석에서 더 보기
        </p>
        <ul className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
          {chapters.map((ch) => (
            <li key={ch.slug}>
              <a
                href={insightLearnUrl(ch)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-700 dark:text-indigo-300 font-medium hover:underline"
              >
                {ch.label} →
              </a>
            </li>
          ))}
          <li>
            <a
              href="https://ch2data.com/learn/stats/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-500 dark:text-slate-400 hover:underline"
            >
              전체 로드맵
            </a>
          </li>
        </ul>
      </div>
    </footer>
  );
}
