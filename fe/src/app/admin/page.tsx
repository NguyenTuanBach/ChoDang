import AuthGate from "@/components/auth/AuthGate";
import QueuePanel from "@/components/staff/QueuePanel";

export default function Page() {
  return (
    <AuthGate roles={["admin"]}>
      <QueuePanel base="/admin" />
    </AuthGate>
  );
}
