import AuthGate from "@/components/auth/AuthGate";
import ConfigPanel from "@/components/admin/ConfigPanel";

export default function Page() {
  return (
    <AuthGate roles={["admin"]}>
      <ConfigPanel />
    </AuthGate>
  );
}
