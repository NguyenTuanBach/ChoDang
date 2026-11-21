import AuthGate from "@/components/auth/AuthGate";
import NotificationsPage from "@/components/shared/NotificationsPage";

export default function Page() {
  return (
    <AuthGate>
      <NotificationsPage />
    </AuthGate>
  );
}
