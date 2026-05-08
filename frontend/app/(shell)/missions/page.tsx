import { ExecutiveBriefPanel } from "@/components/shell/executive-brief-panel";
import { MissionSurface } from "@/components/shell/mission-surface";

export const metadata = {
  title: "Bifrost · Missions",
};

export default function MissionsPage() {
  return (
    <>
      <div className="px-6 pt-6">
        <ExecutiveBriefPanel />
      </div>
      <MissionSurface />
    </>
  );
}
