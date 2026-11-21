import AuthGate from "@/components/auth/AuthGate";
import AuditPanel from "@/components/admin/AuditPanel";

export default function Page() {
  return (
    <AuthGate roles={["admin"]}>
      <AuditPanel />
    </AuthGate>
  );
}
