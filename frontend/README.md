# SVR Operator Console (Frontend)

Bilingual (`EN` / `AR` RTL) telecom customer-care web console for Smart Voicemail Router, built with **Vite**, **React 19**, **TypeScript**, **Tailwind CSS v4**, **shadcn/ui**, **TanStack Router**, and **Recharts**.

## Development

```bash
npm ci
npm run dev
```

The dev server starts on `http://localhost:3000` and proxies `/api` and `/ws` to `http://127.0.0.1:8000` (configurable via `SVR_API_UPSTREAM`).

## Production Build

```bash
npx tsc --noEmit
npm run build
npm run preview
```
