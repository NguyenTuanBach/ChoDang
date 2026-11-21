import Link from "next/link";
import { Suspense } from "react";
import AuthGate from "@/components/auth/AuthGate";
import ClientPing from "@/components/ClientPing";
import ServerStatus from "@/components/ServerStatus";

export default function Home() {
  return (
    <AuthGate>
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "2rem 1rem" }}>
        <h1>VIN-15 — Hệ thống hỗ trợ thực tập bằng AI</h1>
        <Suspense fallback={<p>Đang kiểm tra trạng thái...</p>}>
          <ServerStatus />
        </Suspense>
        <p>
          <Link href="/assistant">Mở trợ lý chính sách thực tập</Link>
        </p>
        <ClientPing />
      </main>
    </AuthGate>
  );
}
