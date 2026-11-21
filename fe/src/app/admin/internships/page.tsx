import AuthGate from "@/components/auth/AuthGate";
import InternshipList from "@/components/staff/InternshipList";

export default function Page() {
  return (
    <AuthGate roles={["admin"]}>
      <InternshipList base="/admin" />
    </AuthGate>
  );
}
