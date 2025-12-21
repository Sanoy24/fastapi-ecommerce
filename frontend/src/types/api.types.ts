// Product Types
export interface Product {
  id: number
  name: string
  slug: string
  description: string
  price: number
  stock_quantity: number
  category_id: number
  category?: Category
  average_rating?: number
  review_count?: number
  created_at?: string
  updated_at?: string
}

export interface Category {
  id: number
  name: string
  slug: string
  description?: string
  parent_id?: number
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

// User Types
export interface User {
  id: number
  email: string
  full_name: string
  is_active: boolean
  is_admin: boolean
  created_at: string
  addresses?: Address[]
}

export interface Address {
  id: number
  user_id: number
  street: string
  city: string
  state: string
  postal_code: string
  country: string
  is_primary: boolean
}

// Auth Types
export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  first_name: string
  last_name: string
  phone: string
}

export interface TokenResponse {
  token: string
  token_type: string
}

// Cart Types
export interface CartItem {
  id: number
  product_id: number
  quantity: number
  product_name: string
  unit_price: number
  subtotal: number
}

export interface Cart {
  id: number
  items: CartItem[]
  total_items: number
  subtotal: number
}

export interface CartItemCreate {
  product_id: number
  quantity: number
}

export interface CartItemUpdate {
  quantity: number
}

// Order Types
export interface Order {
  id: number
  user_id: number
  status: OrderStatus
  total_amount: number
  shipping_address_id: number
  billing_address_id: number
  items: OrderItem[]
  created_at: string
  updated_at: string
}

export interface OrderItem {
  id: number
  order_id: number
  product_id: number
  quantity: number
  price: number
  product: Product
}

export enum OrderStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  SHIPPED = 'shipped',
  DELIVERED = 'delivered',
  CANCELLED = 'cancelled',
}

export interface OrderCreateRequest {
  shipping_address_id: number
  billing_address_id: number
}

// Review Types
export interface Review {
  id: number
  product_id: number
  user_id: number
  rating: number
  comment: string
  created_at: string
  updated_at: string
  user?: User
}

export interface ReviewCreate {
  product_id: number
  rating: number
  comment: string
}

export interface ReviewUpdate {
  rating?: number
  comment?: string
}

// Wishlist Types
export interface WishlistItem {
  product_id: number
  product: Product
  added_at: string
}

export interface Wishlist {
  items: WishlistItem[]
  total_items: number
}

export interface WishlistResponse {
  items: WishlistItem[]
  total_items: number
}

// Search & Filter Types
export enum AvailabilityFilter {
  ALL = 'all',
  IN_STOCK = 'in_stock',
  OUT_OF_STOCK = 'out_of_stock',
}

export enum SortByField {
  ID = 'id',
  NAME = 'name',
  PRICE = 'price',
  RATING = 'rating',
  POPULARITY = 'popularity',
  CREATED_AT = 'created_at',
}

export enum SortOrder {
  ASC = 'asc',
  DESC = 'desc',
}

export interface ProductFilters {
  search?: string
  category_id?: number
  min_price?: number
  max_price?: number
  min_rating?: number
  availability?: AvailabilityFilter
  sort_by?: SortByField
  sort_order?: SortOrder
  page?: number
  per_page?: number
}

export interface AutocompleteResponse {
  suggestions: string[]
}

// API Error Types
export interface APIError {
  detail: string
  fields?: Record<string, string>
}
