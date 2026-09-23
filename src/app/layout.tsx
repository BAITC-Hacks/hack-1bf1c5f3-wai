import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "HackAlem | Evidence Agent Starter",
  description: "Schema-agnostic analysis with a verifiable tool trace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
