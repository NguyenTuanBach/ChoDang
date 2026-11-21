import AuthGate from "@/components/auth/AuthGate";
import JournalPage from "@/components/student/JournalPage";

export default function Page() {
  return (
    <AuthGate roles={["student"]}>
      <JournalPage />
    </AuthGate>
  );
}
