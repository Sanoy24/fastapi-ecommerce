import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/services/api.client'
import { ROUTES } from '@/config/api'
import type {
  Product,
  PaginatedResponse,
  ProductFilters,
  Category,
  AutocompleteResponse,
} from '@/types/api.types'

export const useProductStore = defineStore('products', () => {
  // State
  const products = ref<Product[]>([])
  const currentProduct = ref<Product | null>(null)
  const categories = ref<Category[]>([])
  const totalProducts = ref(0)
  const currentPage = ref(1)
  const totalPages = ref(1)
  const loading = ref(false)
  const filters = ref<ProductFilters>({
    page: 1,
    per_page: 12,
  })

  // Getters
  const hasProducts = computed(() => products.value.length > 0)
  const hasMore = computed(() => currentPage.value < totalPages.value)

  // Actions
  async function fetchProducts(newFilters?: Partial<ProductFilters>) {
    loading.value = true
    try {
      // Merge filters
      if (newFilters) {
        filters.value = { ...filters.value, ...newFilters }
      }

      // Build query params
      const params = new URLSearchParams()
      Object.entries(filters.value).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          params.append(key, value.toString())
        }
      })

      const response = await apiClient.get<any>(
        `${ROUTES.PRODUCTS}?${params.toString()}`
      )

      // Backend returns { data: [...], meta: {...}, links: {...} }
      // Parse the actual backend response format
      if (response.data && Array.isArray(response.data)) {
        products.value = response.data
        totalProducts.value = response.meta?.total_items || response.data.length
        currentPage.value = response.meta?.current_page || 1
        totalPages.value = response.meta?.total_pages || 1
      } else {
        // Fallback for empty or unexpected response
        products.value = []
        totalProducts.value = 0
        currentPage.value = 1
        totalPages.value = 1
      }
    } catch (error) {
      console.error('Fetch products error:', error)
      // Set empty state on error to prevent crashes
      products.value = []
      totalProducts.value = 0
      currentPage.value = 1
      totalPages.value = 1
    } finally {
      loading.value = false
    }
  }

  async function fetchProductBySlug(slug: string) {
    loading.value = true
    try {
      const product = await apiClient.get<Product>(ROUTES.PRODUCT_BY_SLUG(slug))
      currentProduct.value = product
      return product
    } catch (error) {
      console.error('Fetch product error:', error)
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchProductsByCategory(slug: string) {
    loading.value = true
    try {
      const productList = await apiClient.get<Product[]>(
        ROUTES.PRODUCTS_BY_CATEGORY(slug)
      )
      products.value = productList
      return productList
    } catch (error) {
      console.error('Fetch products by category error:', error)
      return []
    } finally {
      loading.value = false
    }
  }

  async function searchProducts(query: string) {
    return fetchProducts({ search: query, page: 1 })
  }

  async function getAutocomplete(query: string): Promise<string[]> {
    try {
      const response = await apiClient.get<AutocompleteResponse>(
        `${ROUTES.PRODUCT_AUTOCOMPLETE}?q=${encodeURIComponent(query)}`
      )
      return response.suggestions
    } catch (error) {
      console.error('Autocomplete error:', error)
      return []
    }
  }

  async function fetchCategories() {
    try {
      const categoryList = await apiClient.get<Category[]>(ROUTES.CATEGORIES)
      categories.value = categoryList
    } catch (error) {
      console.error('Fetch categories error:', error)
    }
  }

  function resetFilters() {
    filters.value = {
      page: 1,
      per_page: 12,
    }
    fetchProducts()
  }

  function setFilter(key: keyof ProductFilters, value: any) {
    filters.value = {
      ...filters.value,
      [key]: value,
      page: 1, // Reset to first page when filter changes
    }
    fetchProducts()
  }

  return {
    // State
    products,
    currentProduct,
    categories,
    totalProducts,
    currentPage,
    totalPages,
    loading,
    filters,
    // Getters
    hasProducts,
    hasMore,
    // Actions
    fetchProducts,
    fetchProductBySlug,
    fetchProductsByCategory,
    searchProducts,
    getAutocomplete,
    fetchCategories,
    resetFilters,
    setFilter,
  }
})
