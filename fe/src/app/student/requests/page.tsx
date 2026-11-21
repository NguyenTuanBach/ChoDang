import AuthGate from "@/components/auth/AuthGate";
import RequestsPage from "@/components/student/RequestsPage";

export default function Page() {
  return (
    <AuthGate roles={["student"]}>
      <RequestsPage />
    </AuthGate>
  );
}
