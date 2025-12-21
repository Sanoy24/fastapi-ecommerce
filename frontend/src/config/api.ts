export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  TIMEOUT: 30000,
  HEADERS: {
    'Content-Type': 'application/json',
  },
}

export const STORAGE_KEYS = {
  AUTH_TOKEN: 'auth_token',
  USER: 'user',
  CART_SESSION: 'cart_session_id',
}

export const ROUTES = {
  // Auth
  LOGIN: '/users/login',
  REGISTER: '/users/register',
  ME: '/users/me',
  
  // Products
  PRODUCTS: '/product',
  PRODUCT_AUTOCOMPLETE: '/product/autocomplete',
  PRODUCT_BY_SLUG: (slug: string) => `/product/${slug}`,
  PRODUCTS_BY_CATEGORY: (slug: string) => `/product/category/${slug}`,
  
  // Cart
  CART: '/cart',
  CART_ITEMS: '/cart/items',
  CART_ITEM: (id: number) => `/cart/items/${id}`,
  
  // Orders
  ORDERS: '/order',
  ORDER: (id: number) => `/order/${id}`,
  
  // Wishlist
  WISHLIST: '/wishlist',
  WISHLIST_ITEM: (productId: number) => `/wishlist/${productId}`,
  WISHLIST_COUNT: '/wishlist/count',
  WISHLIST_MOVE_TO_CART: (productId: number) => `/wishlist/${productId}/move-to-cart`,
  
  // Reviews
  REVIEWS: '/reviews',
  PRODUCT_REVIEWS: (productId: number) => `/reviews/product/${productId}`,
  REVIEW: (id: number) => `/reviews/${id}`,
  
  // Categories
  CATEGORIES: '/category',
  CATEGORY: (id: number) => `/category/${id}`,
  
  // Address
  ADDRESSES: '/users/me/address',
  ADDRESS: (id: number) => `/users/me/address/${id}`,
}
