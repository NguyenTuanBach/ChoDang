import AuthGate from "@/components/auth/AuthGate";
import PoliciesPanel from "@/components/admin/PoliciesPanel";

export default function Page() {
  return (
    <AuthGate roles={["admin"]}>
      <PoliciesPanel />
    </AuthGate>
  );
}
