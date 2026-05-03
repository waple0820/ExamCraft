import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";

import { I18nProvider } from "@/components/I18nProvider";
import { messagesByLocale } from "@/lib/i18n";
import { getLocale } from "@/lib/i18n/server";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
  axes: ["opsz", "SOFT"],
});

export const metadata: Metadata = {
  title: "ExamCraft",
  description: "Personal AI-generated exams in your teacher's style.",
};

// The root layout reads the examcraft_locale cookie via getLocale() so it
// can hand the client-side <I18nProvider> the right dictionary. Without
// force-dynamic Next 15 was prerendering /login with the default locale
// and the toggle had no effect on a refresh.
export const dynamic = "force-dynamic";

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  const messages = messagesByLocale[locale];
  const htmlLang = locale === "zh" ? "zh-CN" : "en";

  return (
    <html lang={htmlLang} className={`${inter.variable} ${fraunces.variable}`}>
      <body className="font-sans">
        <I18nProvider locale={locale} messages={messages}>
          <main className="min-h-screen">{children}</main>
        </I18nProvider>
      </body>
    </html>
  );
}
