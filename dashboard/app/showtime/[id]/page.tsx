import { getTrace } from "@/lib/trace-client";
import { ShowtimeShell } from "@/components/showtime/ShowtimeShell";

/**
 * The immersive "showtime" experience (ticket #61) — a full-page, clinical-noir
 * stage where the whole cascade plays across one shared clock. The 3-D world-model
 * embedding (#62) mounts in the hero; the tier rails (#63) and agent theater (#64)
 * elevate in their own tickets. This route provides the shell + the shared scrubber.
 */
export default async function ShowtimePage({
  params,
}: {
  params: { id: string };
}) {
  const trace = await getTrace(params.id);
  return <ShowtimeShell trace={trace} />;
}
