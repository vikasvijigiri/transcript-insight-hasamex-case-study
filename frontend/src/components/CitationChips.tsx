import { Citation } from "@/lib/api";

export default function CitationChips({ citations }: { citations: Citation[] }) {
  if (!citations || citations.length === 0) {
    return (
      <p className="mt-2 text-xs italic text-zinc-400">
        No direct quote found — treat with caution.
      </p>
    );
  }

  return (
    <div className="mt-2 flex flex-col gap-1.5">
      {citations.map((c, i) => (
        <div
          key={i}
          className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
        >
          <span className="mr-2 rounded bg-zinc-900 px-1.5 py-0.5 font-mono text-[11px] text-white dark:bg-zinc-100 dark:text-zinc-900">
            {c.timestamp}
          </span>
          <span className="font-semibold">{c.expert_name}:</span>{" "}
          <span className="italic">&ldquo;{c.quote}&rdquo;</span>
        </div>
      ))}
    </div>
  );
}
