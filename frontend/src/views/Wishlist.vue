<script setup lang="ts">
import { onMounted } from 'vue'
import { useWishlistStore } from '@/stores/wishlist'

const wishlistStore = useWishlistStore()

onMounted(() => {
  wishlistStore.fetchWishlist()
})

const moveToCart = async (productId: number) => {
  await wishlistStore.moveToCart(productId)
}

const removeItem = async (productId: number) => {
  await wishlistStore.removeFromWishlist(productId)
}
</script>

<template>
  <div class="min-h-screen">
    <!-- Navigation -->
    <nav class="bg-black/30 backdrop-blur-md border-b border-purple-500/20">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center h-16">
          <router-link to="/" class="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
            FastAPI E-Commerce
          </router-link>
          <div class="flex space-x-4">
            <router-link to="/" class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors">
              Home
            </router-link>
            <router-link to="/products" class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors">
              Products
            </router-link>
            <router-link to="/cart" class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors">
              Cart
            </router-link>
            <router-link to="/wishlist" class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors">
              Wishlist
            </router-link>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 class="text-4xl font-bold mb-8 bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
        My Wishlist
      </h1>

      <!-- Loading State -->
      <div v-if="wishlistStore.loading" class="flex justify-center items-center h-64">
        <div class="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-purple-500"></div>
      </div>

      <!-- Empty Wishlist -->
      <div v-else-if="wishlistStore.items.length === 0" class="text-center py-12">
        <div class="text-6xl mb-4">💝</div>
        <p class="text-xl text-gray-400 mb-6">Your wishlist is empty</p>
        <router-link to="/products" 
                     class="inline-block px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-lg shadow-lg hover:shadow-purple-500/50 transform hover:scale-105 transition-all duration-200">
          Browse Products
        </router-link>
      </div>

      <!-- Wishlist Items -->
      <div v-else class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div v-for="item in wishlistStore.items" :key="item.product_id" 
             class="bg-white/10 backdrop-blur-lg rounded-xl border border-purple-500/30 overflow-hidden hover:border-purple-500/60 transition-all">
          <div class="p-6">
            <h3 class="text-xl font-semibold text-white mb-2">{{ item.product.name }}</h3>
            <p class="text-gray-300 mb-4 line-clamp-2">{{ item.product.description }}</p>
            
            <div class="mb-4">
              <span class="text-2xl font-bold text-purple-400">${{ item.product.price.toFixed(2) }}</span>
            </div>

            <div class="flex gap-2">
              <button @click="moveToCart(item.product_id)"
                      class="flex-1 px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-lg hover:shadow-lg hover:shadow-purple-500/50 transition-all duration-200">
                Move to Cart
              </button>
              <button @click="removeItem(item.product_id)"
                      class="px-4 py-2 bg-red-500/20 border border-red-500 rounded-lg text-red-400 hover:bg-red-500/30 transition-colors">
                Remove
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
