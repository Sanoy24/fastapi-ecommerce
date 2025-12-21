import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/services/api.client'
import { ROUTES } from '@/config/api'
import type { Cart, CartItem, CartItemCreate, CartItemUpdate } from '@/types/api.types'
import { useToast } from 'vue-toastification'
import { useAuthStore } from './auth'

const toast = useToast()

export const useCartStore = defineStore('cart', () => {
  // State
  const cart = ref<Cart | null>(null)
  const loading = ref(false)

  // Getters
  const itemCount = computed(() => cart.value?.total_items || 0)
  const subtotal = computed(() => cart.value?.subtotal || 0)
  const items = computed(() => cart.value?.items || [])

  // Actions
  async function fetchCart() {
    loading.value = true
    try {
      const data = await apiClient.get<Cart>(ROUTES.CART)
      cart.value = data
    } catch (error) {
      console.error('Fetch cart error:', error)
    } finally {
      loading.value = false
    }
  }

  async function addItem(productId: number, quantity: number = 1) {
    loading.value = true
    try {
      const data: CartItemCreate = { product_id: productId, quantity }
      await apiClient.post(ROUTES.CART_ITEMS, data)
      await fetchCart()
      toast.success('Item added to cart')
      return true
    } catch (error) {
      console.error('Add to cart error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function updateItem(itemId: number, quantity: number) {
    if (quantity < 1) {
      return removeItem(itemId)
    }

    loading.value = true
    try {
      const data: CartItemUpdate = { quantity }
      await apiClient.put(ROUTES.CART_ITEM(itemId), data)
      await fetchCart()
      toast.success('Cart updated')
      return true
    } catch (error) {
      console.error('Update cart error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function removeItem(itemId: number) {
    loading.value = true
    try {
      await apiClient.delete(ROUTES.CART_ITEM(itemId))
      await fetchCart()
      toast.success('Item removed from cart')
      return true
    } catch (error) {
      console.error('Remove from cart error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function clearCart() {
    // Clear all items one by one
    if (!cart.value?.items) return

    for (const item of cart.value.items) {
      await removeItem(item.id)
    }
  }

  function getItemQuantity(productId: number): number {
    const item = items.value.find((i) => i.product_id === productId)
    return item?.quantity || 0
  }

  function isInCart(productId: number): boolean {
    return items.value.some((i) => i.product_id === productId)
  }

  return {
    // State
    cart,
    loading,
    // Getters
    itemCount,
    subtotal,
    items,
    // Actions
    fetchCart,
    addItem,
    updateItem,
    removeItem,
    clearCart,
    getItemQuantity,
    isInCart,
  }
})
