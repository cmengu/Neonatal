import { ShowtimeWard } from "@/components/showtime/ShowtimeWard";

/**
 * Home = the showtime ward (#65): the demo's opening "scale → drill-in" beat. Ten calm
 * beds and one destabilising infant (infant7); clicking it drills into the immersive
 * cascade at /showtime/[id] (#61). The legacy live-refresh ward dashboard (WardGrid /
 * PatientDrawer / useWardData) stays in the tree but is no longer the entry point.
 */
export default function Home() {
  return <ShowtimeWard />;
}
