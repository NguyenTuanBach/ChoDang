import AuthGate from "@/components/auth/AuthGate";
import HomeRedirect from "@/components/shared/HomeRedirect";

export default function Home() {
  return (
    <AuthGate>
      <HomeRedirect />
    </AuthGate>
  );
}
