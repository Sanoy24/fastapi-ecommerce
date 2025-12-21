import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/services/api.client'
import { ROUTES } from '@/config/api'
import type { WishlistResponse, WishlistItem } from '@/types/api.types'
import { useToast } from 'vue-toastification'
import { useCartStore } from './cart'

const toast = useToast()

export const useWishlistStore = defineStore('wishlist', () => {
  // State
  const items = ref<WishlistItem[]>([])
  const loading = ref(false)

  // Getters
  const itemCount = computed(() => items.value.length)
  const productIds = computed(() => items.value.map((item) => item.product_id))

  // Actions
  async function fetchWishlist() {
    loading.value = true
    try {
      const response = await apiClient.get<WishlistResponse>(ROUTES.WISHLIST)
      items.value = response.items
    } catch (error) {
      console.error('Fetch wishlist error:', error)
    } finally {
      loading.value = false
    }
  }

  async function addToWishlist(productId: number) {
    loading.value = true
    try {
      await apiClient.post(ROUTES.WISHLIST, { product_id: productId })
      await fetchWishlist()
      toast.success('Added to wishlist')
      return true
    } catch (error) {
      console.error('Add to wishlist error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function removeFromWishlist(productId: number) {
    loading.value = true
    try {
      await apiClient.delete(ROUTES.WISHLIST_ITEM(productId))
      await fetchWishlist()
      toast.success('Removed from wishlist')
      return true
    } catch (error) {
      console.error('Remove from wishlist error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function clearWishlist() {
    loading.value = true
    try {
      await apiClient.delete(ROUTES.WISHLIST)
      items.value = []
      toast.success('Wishlist cleared')
      return true
    } catch (error) {
      console.error('Clear wishlist error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function moveToCart(productId: number) {
    const cartStore = useCartStore()
    loading.value = true
    try {
      await apiClient.post(ROUTES.WISHLIST_MOVE_TO_CART(productId))
      await fetchWishlist()
      await cartStore.fetchCart()
      toast.success('Moved to cart')
      return true
    } catch (error) {
      console.error('Move to cart error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  function isInWishlist(productId: number): boolean {
    return productIds.value.includes(productId)
  }

  function toggleWishlist(productId: number) {
    if (isInWishlist(productId)) {
      return removeFromWishlist(productId)
    } else {
      return addToWishlist(productId)
    }
  }

  return {
    // State
    items,
    loading,
    // Getters
    itemCount,
    productIds,
    // Actions
    fetchWishlist,
    addToWishlist,
    removeFromWishlist,
    clearWishlist,
    moveToCart,
    isInWishlist,
    toggleWishlist,
  }
})
