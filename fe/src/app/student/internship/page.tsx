import AuthGate from "@/components/auth/AuthGate";
import InternshipForm from "@/components/student/InternshipForm";

export default function Page() {
  return (
    <AuthGate roles={["student"]}>
      <InternshipForm />
    </AuthGate>
  );
}
