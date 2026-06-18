import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediBot — MediAssist Internal Assistant",
  description: "Role-based AI knowledge assistant for MediAssist Health Network staff",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full">
      <body
        className="h-full antialiased"
        style={{
          background: "linear-gradient(135deg, #f0f4ff 0%, #faf5ff 50%, #f0fdf4 100%)",
          minHeight: "100vh",
        }}
      >
        {children}
      </body>
    </html>
  );
}
