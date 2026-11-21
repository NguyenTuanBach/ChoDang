import type { Metadata } from "next";
import AssistantChat from "@/components/assistant/AssistantChat";
import AuthGate from "@/components/auth/AuthGate";

export const metadata: Metadata = {
  title: "Trợ lý chính sách | VIN-15",
};

export default function AssistantPage() {
  return (
    <AuthGate>
      <AssistantChat />
    </AuthGate>
  );
}
