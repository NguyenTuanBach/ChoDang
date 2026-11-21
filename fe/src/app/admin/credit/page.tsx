import AuthGate from "@/components/auth/AuthGate";
import InternshipList from "@/components/staff/InternshipList";

export default function Page() {
  return (
    <AuthGate roles={["admin"]}>
      <InternshipList base="/admin" fixedStatus="credit_review" title="Hồ sơ chờ phê duyệt công nhận tín chỉ" />
    </AuthGate>
  );
}
