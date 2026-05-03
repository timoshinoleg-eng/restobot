export interface MenuCategory {
  id: number;
  name: string;
  emoji?: string;
  sort_order: number;
}

export interface MenuItem {
  id: number;
  category_id: number | null;
  name: string;
  description: string | null;
  price: number;
  image_url: string | null;
  is_available: boolean;
}

export interface CartItem {
  item: MenuItem;
  quantity: number;
}

export interface WidgetSession {
  tenant_id: string;
  user_id: number;
  loyalty_points: number;
  access_token: string;
}

export interface OrderItemPayload {
  menu_item_id: number;
  quantity: number;
  price: number;
  modifiers: null;
}

export interface OrderCreatePayload {
  user_id: number;
  type: 'delivery' | 'pickup' | 'dine_in' | 'pre_order';
  items: OrderItemPayload[];
  address: string | null;
  phone: string | null;
  comment: string | null;
  payment_method: 'cash' | 'card' | 'online';
  loyalty_points_to_use: number;
}

export interface OrderResponse {
  id: number;
  order_number: string;
  status: string;
  payment_status: string;
  amount: number;
  items: OrderItemPayload[];
  created_at: string;
}

export interface PaymentSession {
  payment_id: string;
  confirmation_url: string;
  status: string;
}

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
}

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: TelegramUser;
    query_id?: string;
  };
  ready: () => void;
  expand: () => void;
  close: () => void;
  openLink?: (url: string) => void;
  MainButton: {
    text: string;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
    setText: (text: string) => void;
  };
  themeParams: Record<string, string>;
  colorScheme: 'light' | 'dark';
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}
