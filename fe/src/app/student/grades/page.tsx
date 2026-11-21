import AuthGate from "@/components/auth/AuthGate";
import GradesPage from "@/components/student/GradesPage";

export default function Page() {
  return (
    <AuthGate roles={["student"]}>
      <GradesPage />
    </AuthGate>
  );
}
