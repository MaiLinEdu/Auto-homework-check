import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "@/styles/globals.css";
import { I18nProvider } from "@/i18n/provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "GradeAI",
  description: "AI-Powered International Curriculum Grading System",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}
