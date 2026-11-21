import AuthGate from "@/components/auth/AuthGate";
import FinalPage from "@/components/student/FinalPage";

export default function Page() {
  return (
    <AuthGate roles={["student"]}>
      <FinalPage />
    </AuthGate>
  );
}
