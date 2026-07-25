import type { Metadata } from 'next'
import '../styles/globals.css'

export const metadata: Metadata = {
  title: 'FraudShield — Real-Time Fraud Detection API',
  description: 'Protect your business with ML-powered fraud detection. Detect fraud in <10ms with our production-grade API.',
  keywords: ['fraud detection', 'API', 'machine learning', 'fintech', 'security'],
  authors: [{ name: 'FraudShield' }],
  openGraph: {
    title: 'FraudShield — Real-Time Fraud Detection',
    description: 'ML-powered fraud detection API. <10ms latency. Free tier available.',
    type: 'website',
    url: 'https://fraudshield-platform.vercel.app',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  )
}
