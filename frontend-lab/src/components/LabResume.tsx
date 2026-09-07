type LabResumeDoc = {
  next_id: string;
  title: string;
  say: string;
  do_not: string;
  how: string;
};

export default function LabResume({ resume }: { resume: LabResumeDoc }) {
  return (
    <section className="rounded border border-indigo-200 dark:border-indigo-800 bg-indigo-50/70 dark:bg-indigo-950/30 px-2.5 py-2 space-y-1">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-indigo-800 dark:text-indigo-200">
        다음 세션 · {resume.next_id}
      </p>
      <p className="font-semibold text-indigo-950 dark:text-indigo-50">{resume.title}</p>
      <p>{resume.say}</p>
      <p>
        <span className="font-medium">하지 않음.</span> {resume.do_not}
      </p>
      <p className="text-[11px] text-slate-600 dark:text-slate-300">{resume.how}</p>
    </section>
  );
}
