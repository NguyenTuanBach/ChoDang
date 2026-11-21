import type { Metadata } from "next";
import AssistantChat from "@/components/assistant/AssistantChat";

export const metadata: Metadata = {
  title: "Trợ lý chính sách | VIN-15",
};

export default function AssistantPage() {
  return <AssistantChat />;
}
