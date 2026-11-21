import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VIN-15",
  description: "Hệ thống hỗ trợ thực tập bằng AI",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
