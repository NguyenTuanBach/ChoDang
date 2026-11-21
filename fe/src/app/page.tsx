import AuthProvider from "@/components/auth/AuthProvider";
import HomeRedirect from "@/components/shared/HomeRedirect";

export default function Home() {
  return (
    <AuthProvider>
      <HomeRedirect />
    </AuthProvider>
  );
}
