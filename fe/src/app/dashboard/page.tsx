import AuthGate from "@/components/auth/AuthGate";
import DashboardView from "@/components/staff/DashboardView";

export default function Page() {
  return (
    <AuthGate roles={["lecturer", "admin"]}>
      <DashboardView />
    </AuthGate>
  );
}
