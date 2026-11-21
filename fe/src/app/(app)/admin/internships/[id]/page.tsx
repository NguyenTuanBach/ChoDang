import { Suspense } from "react";
import InternshipDetailView from "@/components/staff/InternshipDetailView";

type Params = Promise<{ id: string }>;

async function Detail({ params }: { params: Params }) {
  const { id } = await params;
  return <InternshipDetailView id={Number(id)} role="admin" />;
}

export default function Page({ params }: { params: Params }) {
  return (
    <Suspense fallback={null}>
        <Detail params={params} />
      </Suspense>
  );
}
