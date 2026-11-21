import AuthGate from "@/components/auth/AuthGate";
import LmsAdminPanel from "@/components/admin/LmsAdminPanel";

export default function Page() {
  return (
    <AuthGate roles={["admin"]}>
      <LmsAdminPanel />
    </AuthGate>
  );
}
