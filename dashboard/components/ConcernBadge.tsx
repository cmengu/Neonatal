import { ConcernLevel, CONCERN_TO_LABEL } from "@/lib/types";

const BADGE_CLASSES: Record<ConcernLevel, string> = {
  RED: "bg-red-700 text-red-100 font-semibold tracking-wide",
  YELLOW: "bg-amber-600 text-amber-50 font-medium",
  GREEN: "bg-slate-600 text-slate-300 font-normal",
};

export function ConcernBadge({ level }: { level: ConcernLevel }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs uppercase ${BADGE_CLASSES[level]}`}
    >
      {CONCERN_TO_LABEL[level]}
    </span>
  );
}
