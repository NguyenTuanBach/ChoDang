import AuthGate from "@/components/auth/AuthGate";
import AccountsPanel from "@/components/staff/AccountsPanel";

export default function Page() {
  return (
    <AuthGate roles={["lecturer"]}>
      <AccountsPanel viewer="lecturer" role="student" title="Sinh viên tôi phụ trách" />
    </AuthGate>
  );
}
