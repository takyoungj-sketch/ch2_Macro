export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white/90 dark:border-slate-700 dark:bg-slate-800/90">
        <div className="max-w-3xl mx-auto px-4 py-5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            <a href="/" className="hover:text-slate-800 dark:hover:text-slate-200">
              CH2 Macro
            </a>
            <span className="mx-1.5 text-slate-300">·</span>
            베타
          </p>
          <h1 className="text-xl font-bold mt-0.5">Macro Insight</h1>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-8" />
    </div>
  );
}
