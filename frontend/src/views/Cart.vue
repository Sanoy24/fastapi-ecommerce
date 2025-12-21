<script setup lang="ts">
import { onMounted } from 'vue'
import { useCartStore } from '@/stores/cart'
import { storeToRefs } from 'pinia'

const cartStore = useCartStore()
const { items: cartItems, subtotal } = storeToRefs(cartStore)

onMounted(() => {
  cartStore.fetchCart()
})
</script>

<template>
  <div class="min-h-screen">
    <!-- Navigation -->


    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <h1 class="text-4xl font-bold mb-8 bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
        Shopping Cart
      </h1>

      <!-- Empty Cart -->
      <div v-if="cartItems.length === 0" class="text-center py-12">
        <div class="text-6xl mb-4">🛒</div>
        <p class="text-xl text-gray-400 mb-6">Your cart is empty</p>
        <router-link to="/products" 
                     class="inline-block px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-lg shadow-lg hover:shadow-purple-500/50 transform hover:scale-105 transition-all duration-200">
          Start Shopping
        </router-link>
      </div>

      <!-- Cart Items -->
      <div v-else class="grid lg:grid-cols-3 gap-8">
        <div class="lg:col-span-2 space-y-4">
          <div v-for="item in cartItems" :key="item.id" 
               class="bg-white/10 backdrop-blur-lg rounded-xl border border-purple-500/30 p-6 flex items-center justify-between">
            <div class="flex-1">
              <h3 class="text-xl font-semibold text-white mb-2">{{ item.product_name }}</h3>
              <p class="text-purple-400 font-bold">${{ item.unit_price.toFixed(2) }}</p>
            </div>
            
            <div class="flex items-center space-x-4">
              <div class="flex items-center space-x-2">
                <button @click="cartStore.updateItem(item.id, item.quantity - 1)" 
                        :disabled="cartStore.loading"
                        class="px-3 py-1 bg-white/10 border border-purple-500/50 rounded text-white hover:bg-white/20 transition-colors disabled:opacity-50">
                  -
                </button>
                <span class="text-white w-8 text-center">{{ item.quantity }}</span>
                <button @click="cartStore.updateItem(item.id, item.quantity + 1)" 
                         :disabled="cartStore.loading"
                        class="px-3 py-1 bg-white/10 border border-purple-500/50 rounded text-white hover:bg-white/20 transition-colors disabled:opacity-50">
                  +
                </button>
              </div>
              
              <button @click="cartStore.removeItem(item.id)" 
                      :disabled="cartStore.loading"
                      class="px-4 py-2 bg-red-500/20 border border-red-500 rounded text-red-400 hover:bg-red-500/30 transition-colors disabled:opacity-50">
                Remove
              </button>
            </div>
          </div>
        </div>

        <!-- Order Summary -->
        <div class="lg:col-span-1">
          <div class="bg-white/10 backdrop-blur-lg rounded-xl border border-purple-500/30 p-6 sticky top-4">
            <h2 class="text-2xl font-bold text-white mb-6">Order Summary</h2>
            
            <div class="space-y-3 mb-6">
              <div class="flex justify-between text-gray-300">
                <span>Subtotal</span>
                <span>${{ subtotal.toFixed(2) }}</span>
              </div>
              <div class="flex justify-between text-gray-300">
                <span>Shipping</span>
                <span>$0.00</span>
              </div>
              <div class="border-t border-purple-500/30 pt-3 flex justify-between text-white font-bold text-xl">
                <span>Total</span>
                <span>${{ subtotal.toFixed(2) }}</span>
              </div>
            </div>

            <button class="w-full px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-lg shadow-lg hover:shadow-purple-500/50 transform hover:scale-105 transition-all duration-200">
              Proceed to Checkout
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
