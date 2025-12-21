// App constants
export const APP_NAME = 'FastAPI E-Commerce'
export const APP_DESCRIPTION = 'Modern e-commerce platform built with Vue 3 and FastAPI'

// Pagination
export const DEFAULT_PAGE_SIZE = 12
export const PAGE_SIZE_OPTIONS = [12, 24, 48, 96]

// Error messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Network error. Please check your connection.',
  SERVER_ERROR: 'Server error. Please try again later.',
  NOT_FOUND: 'Resource not found.',
  UNAUTHORIZED: 'Please login to continue.',
  VALIDATION_ERROR: 'Please check your input and try again.',
  GENERIC_ERROR: 'Something went wrong. Please try again.',
}

// Success messages
export const SUCCESS_MESSAGES = {
  LOGIN: 'Welcome back!',
  REGISTER: 'Account created successfully!',
  LOGOUT: 'Logged out successfully.',
  ADD_TO_CART: 'Added to cart!',
  REMOVE_FROM_CART: 'Removed from cart.',
  ADD_TO_WISHLIST: 'Added to wishlist!',
  REMOVE_FROM_WISHLIST: 'Removed from wishlist.',
  UPDATE_PROFILE: 'Profile updated successfully!',
  ORDER_PLACED: 'Order placed successfully!',
}

// Validation rules
export const VALIDATION_RULES = {
  EMAIL_MAX_LENGTH: 255,
  PASSWORD_MIN_LENGTH: 8,
  PASSWORD_MAX_LENGTH: 128,
  NAME_MIN_LENGTH: 2,
  NAME_MAX_LENGTH: 100,
  PHONE_MIN_LENGTH: 10,
  PHONE_MAX_LENGTH: 15,
}

// Product constants
export const PRODUCT_SORT_OPTIONS = [
  { value: 'created_at', label: 'Newest', order: 'desc' },
  { value: 'price', label: 'Price: Low to High', order: 'asc' },
  { value: 'price', label: 'Price: High to Low', order: 'desc' },
  { value: 'rating', label: 'Highest Rated', order: 'desc' },
  { value: 'popularity', label: 'Most Popular', order: 'desc' },
  { value: 'name', label: 'Name: A to Z', order: 'asc' },
]

export const AVAILABILITY_OPTIONS = [
  { value: 'all', label: 'All Products' },
  { value: 'in_stock', label: 'In Stock' },
  { value: 'out_of_stock', label: 'Out of Stock' },
]

// Rating stars
export const RATING_OPTIONS = [
  { value: 5, label: '5 Stars' },
  { value: 4, label: '4 Stars & Up' },
  { value: 3, label: '3 Stars & Up' },
  { value: 2, label: '2 Stars & Up' },
  { value: 1, label: '1 Star & Up' },
]

// Image placeholders
export const PLACEHOLDER_IMAGE = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="400"%3E%3Crect width="400" height="400" fill="%23f3f4f6"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="24" fill="%239ca3af"%3ENo Image%3C/text%3E%3C/svg%3E'
