import type { Metadata, Viewport } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'WayToGo 旅伴手札',
  description: '和旅伴一起整理景點、協調投票，安排每一天的旅程。',
  manifest: '/manifest.webmanifest',
  icons: { icon: '/compass.svg', apple: '/icon-192.png' },
};
export const viewport: Viewport = { themeColor: '#f8f8f4', width: 'device-width', initialScale: 1 };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
