import AuthGate from "@/components/auth/AuthGate";
import AccountsPanel from "@/components/staff/AccountsPanel";

export default function Page() {
  return (
    <AuthGate roles={["admin"]}>
      <AccountsPanel viewer="admin" role="lecturer" title="Giảng viên" />
      <AccountsPanel viewer="admin" role="student" title="Sinh viên" />
    </AuthGate>
  );
}
