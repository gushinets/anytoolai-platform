import "@anytoolai/shared-ui/src/tokens.css";
import { DM_Mono, DM_Sans } from "next/font/google";

const dmSans = DM_Sans({ subsets: ["latin"], variable: "--font-body" });
const dmMono = DM_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });

// Cabinet Grotesk (headline) isn't a Google Font, and its ITF Free Font License permits
// self-hosting on our own infrastructure but separately prohibits distributing the Font Software
// through a repository or publicly-accessible server -- this repo is public, so a self-hosted
// next/font/local binary doesn't fit here (see the exec-plan's design-decisions log). The same
// license explicitly sanctions the Fontshare API as an alternative delivery method: "the Font
// Software is delivered directly from servers used by Indian Type Foundry to the Licensee's
// website, without the Licensee having to download or host the Font Software." Weight 900
// ("Black", SKILL.md's own "Display" role weight) is used because Fontshare's CSS API
// intermittently bundles unrelated extra @font-face declarations for some other weights of this
// specific font (700/800) -- verified 900 returns only Cabinet Grotesk across repeated requests.
const CABINET_GROTESK_CSS_URL = "https://api.fontshare.com/v2/css?f[]=cabinet-grotesk@900&display=swap";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${dmSans.variable} ${dmMono.variable}`}>
      <head>
        <link rel="preconnect" href="https://api.fontshare.com" />
        <link rel="preconnect" href="https://cdn.fontshare.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href={CABINET_GROTESK_CSS_URL} />
      </head>
      <body className="page-background">{children}</body>
    </html>
  );
}
