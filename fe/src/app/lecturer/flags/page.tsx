import AuthGate from "@/components/auth/AuthGate";
import FlagsPanel from "@/components/staff/FlagsPanel";

export default function Page() {
  return (
    <AuthGate roles={["lecturer"]}>
      <FlagsPanel base="/lecturer" />
    </AuthGate>
  );
}
