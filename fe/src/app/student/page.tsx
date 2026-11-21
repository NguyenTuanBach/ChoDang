import AuthGate from "@/components/auth/AuthGate";
import StudentHome from "@/components/student/StudentHome";

export default function Page() {
  return (
    <AuthGate roles={["student"]}>
      <StudentHome />
    </AuthGate>
  );
}
