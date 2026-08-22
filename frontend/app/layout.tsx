import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { NavBar } from "@/components/NavBar";

export const metadata: Metadata = {
  title: "영종 AI",
  description: "사장님에게는 AI 직원을, 방문객에게는 AI 여행 안내원을.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>
          <NavBar />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
