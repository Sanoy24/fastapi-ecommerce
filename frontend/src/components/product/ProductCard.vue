<script setup lang="ts">
import { computed } from 'vue'
import type { Product } from '@/types/api.types'
import { useCartStore } from '@/stores/cart'
import { useWishlistStore } from '@/stores/wishlist'
import { useAuthStore } from '@/stores/auth'
import { HeartIcon as HeartOutline, ShoppingCartIcon } from '@heroicons/vue/24/outline'
import { HeartIcon as HeartSolid } from '@heroicons/vue/24/solid'
import Badge from '../ui/Badge.vue'

interface Props {
  product: Product
}

const props = defineProps<Props>()

const cartStore = useCartStore()
const wishlistStore = useWishlistStore()
const authStore = useAuthStore()

const inStock = computed(() => props.product.stock_quantity > 0)
const isInWishlist = computed(() => wishlistStore.isInWishlist(props.product.id))

const addToCart = async () => {
  await cartStore.addItem(props.product.id, 1)
}

const toggleWishlist = async () => {
  if (!authStore.isAuthenticated) {
    // Redirect to login
    return
  }
  await wishlistStore.toggleWishlist(props.product.id)
}
</script>

<template>
  <div class="bg-white/10 backdrop-blur-lg rounded-xl overflow-hidden border border-purple-500/30 hover:border-purple-500/60 transition-all duration-300 hover:scale-105 hover:shadow-2xl hover:shadow-purple-500/30 group">
    <!-- Product Image Placeholder -->
    <div class="relative aspect-square bg-gradient-to-br from-purple-900/20 to-pink-900/20 flex items-center justify-center overflow-hidden">
      <span class="text-6xl">📦</span>
      
      <!-- Wishlist Button -->
      <button 
        v-if="authStore.isAuthenticated"
        @click.prevent="toggleWishlist"
        class="absolute top-2 right-2 p-2 bg-black/50 backdrop-blur-sm rounded-full hover:bg-black/70 transition-all"
      >
        <HeartSolid v-if="isInWishlist" class="h-5 w-5 text-pink-500" />
        <HeartOutline v-else class="h-5 w-5 text-white" />
      </button>

      <!-- Stock Badge -->
      <div class="absolute top-2 left-2">
        <Badge v-if="!inStock" variant="error" size="sm">
          Out of Stock
        </Badge>
      </div>
    </div>

    <!-- Product Info -->
    <div class="p-4">
      <router-link :to="`/products/${product.slug}`" class="block">
        <h3 class="text-lg font-semibold text-white mb-2 line-clamp-1 group-hover:text-purple-400 transition-colors">
          {{ product.name }}
        </h3>
      </router-link>
      
      <p class="text-gray-300 text-sm mb-3 line-clamp-2">
        {{ product.description }}
      </p>

      <!-- Rating -->
      <div v-if="product.average_rating" class="flex items-center mb-3">
        <span class="text-yellow-400 text-sm">★</span>
        <span class="text-white text-sm ml-1">{{ product.average_rating.toFixed(1) }}</span>
        <span class="text-gray-400 text-xs ml-1">({{ product.review_count || 0 }})</span>
      </div>

      <!-- Price and Actions -->
      <div class="flex items-center justify-between">
        <span class="text-2xl font-bold text-purple-400">
          ${{ product.price.toFixed(2) }}
        </span>
        
        <button 
          @click="addToCart"
          :disabled="!inStock"
          class="p-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg hover:shadow-lg hover:shadow-purple-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          :title="inStock ? 'Add to cart' : 'Out of stock'"
        >
          <ShoppingCartIcon class="h-5 w-5" />
        </button>
      </div>
    </div>
  </div>
</template>
