# RestoBot WebApp

Tenant-aware ordering frontend for Telegram WebApp and browser.

## Stack

- React 18 + TypeScript
- Vite (build + dev server)
- No CSS framework — custom mobile-first CSS

## Routes

- `/:tenant/menu` — browse menu, add items to cart
- `/:tenant/order` — checkout, create widget session, place order
- `/:tenant/*` — redirects to `/:tenant/menu`

## Backend contracts used

- `POST /widget/{tenant}/session` → `{user_id, access_token}`
- `GET /widget/{tenant}/menu` → menu items (with `category_id`)
- `GET /widget/{tenant}/menu/categories` → categories
- `POST /widget/{tenant}/orders` → create order (`menu_item_id`, `quantity`, `price`)
- `GET /widget/{tenant}/orders/{order_id}` → order status
- `POST /api/v1/{tenant}/orders/{order_id}/payment` → create YooKassa redirect payment for online checkout

Auth: Bearer token stored in `localStorage` after widget session creation.

## Local development

```bash
npm install
npm run dev
```

Open: `http://localhost:5173/demo/menu`

Vite proxy forwards `/widget` and `/admin` to local backends (`localhost:8001/8000`).

## Production build

```bash
npm ci
npm run build
```

Static files are written to `dist/` and served by Caddy under `app.chatbot24.su`.

## Environment

Copy `.env.example` to `.env` if you need to override `VITE_API_BASE_URL`.
By default the app uses same-origin requests (works when API and frontend share a domain).

## Telegram WebApp

If opened inside Telegram, the app calls `Telegram.WebApp.ready()` and `expand()`
and pre-fills the user name from `initDataUnsafe.user`.
