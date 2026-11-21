import AuthGate from "@/components/auth/AuthGate";
import MilestonesPage from "@/components/student/MilestonesPage";

export default function Page() {
  return (
    <AuthGate roles={["student"]}>
      <MilestonesPage />
    </AuthGate>
  );
}
