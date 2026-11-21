import AuthGate from "@/components/auth/AuthGate";
import QueuePanel from "@/components/staff/QueuePanel";

export default function Page() {
  return (
    <AuthGate roles={["lecturer"]}>
      <QueuePanel base="/lecturer" />
    </AuthGate>
  );
}
