import AuthGate from "@/components/auth/AuthGate";
import InternshipList from "@/components/staff/InternshipList";

export default function Page() {
  return (
    <AuthGate roles={["lecturer"]}>
      <InternshipList base="/lecturer" />
    </AuthGate>
  );
}
