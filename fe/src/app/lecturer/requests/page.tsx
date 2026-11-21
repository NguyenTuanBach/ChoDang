import AuthGate from "@/components/auth/AuthGate";
import RequestsReview from "@/components/staff/RequestsReview";

export default function Page() {
  return (
    <AuthGate roles={["lecturer"]}>
      <RequestsReview base="/lecturer" />
    </AuthGate>
  );
}
