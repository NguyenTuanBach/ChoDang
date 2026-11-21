import AuthGate from "@/components/auth/AuthGate";
import OutlinePage from "@/components/student/OutlinePage";

export default function Page() {
  return (
    <AuthGate roles={["student"]}>
      <OutlinePage />
    </AuthGate>
  );
}
