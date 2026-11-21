import { Suspense } from "react";
import AuthGate from "@/components/auth/AuthGate";
import InternshipDetailView from "@/components/staff/InternshipDetailView";

type Params = Promise<{ id: string }>;

async function Detail({ params }: { params: Params }) {
  const { id } = await params;
  return <InternshipDetailView id={Number(id)} role="lecturer" />;
}

export default function Page({ params }: { params: Params }) {
  return (
    <AuthGate roles={["lecturer"]}>
      <Suspense fallback={null}>
        <Detail params={params} />
      </Suspense>
    </AuthGate>
  );
}
