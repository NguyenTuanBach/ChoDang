import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";

// Inter có bộ ký tự tiếng Việt (Geist mặc định của shadcn thì không).
const sans = Inter({ subsets: ["latin", "latin-ext", "vietnamese"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "VIN-15",
  description: "Hệ thống hỗ trợ thực tập bằng AI",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi" suppressHydrationWarning className={cn("font-sans", sans.variable)}>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          {children}
          <Toaster position="top-right" richColors />
        </ThemeProvider>
      </body>
    </html>
  );
}
