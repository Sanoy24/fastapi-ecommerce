<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import { useWishlistStore } from '@/stores/wishlist'
import { ShoppingCartIcon, HeartIcon, UserIcon, Bars3Icon, XMarkIcon } from '@heroicons/vue/24/outline'

const authStore = useAuthStore()
const cartStore = useCartStore()
const wishlistStore = useWishlistStore()
const router = useRouter()

const mobileMenuOpen = ref(false)

const cartCount = computed(() => cartStore.itemCount)
const wishlistCount = computed(() => wishlistStore.itemCount)

const handleLogout = () => {
  authStore.logout()
  router.push('/')
}
</script>

<template>
  <nav class="bg-black/30 backdrop-blur-md border-b border-purple-500/20 sticky top-0 z-40">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-16">
        <!-- Logo -->
        <router-link to="/" class="flex items-center space-x-2">
          <span class="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
            FastAPI E-Commerce
          </span>
        </router-link>

        <!-- Desktop Navigation -->
        <div class="hidden md:flex items-center space-x-6">
          <router-link 
            to="/" 
            exact
            class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors"
            active-class="text-white bg-white/10"
          >
            Home
          </router-link>
          <router-link 
            to="/products" 
            class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors"
            active-class="text-white bg-white/10"
          >
            Products
          </router-link>
        </div>

        <!-- Right Side Icons -->
        <div class="hidden md:flex items-center space-x-4">
          <!-- Wishlist -->
          <router-link 
            v-if="authStore.isAuthenticated"
            to="/wishlist" 
            class="relative text-gray-300 hover:text-white p-2 rounded-md transition-colors"
          >
            <HeartIcon class="h-6 w-6" />
            <span 
              v-if="wishlistCount > 0" 
              class="absolute -top-1 -right-1 bg-pink-600 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center"
            >
              {{ wishlistCount }}
            </span>
          </router-link>

          <!-- Cart -->
          <router-link 
            to="/cart" 
            class="relative text-gray-300 hover:text-white p-2 rounded-md transition-colors"
          >
            <ShoppingCartIcon class="h-6 w-6" />
            <span 
              v-if="cartCount > 0" 
              class="absolute -top-1 -right-1 bg-purple-600 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center"
            >
              {{ cartCount }}
            </span>
          </router-link>

          <!-- User Menu -->
          <div v-if="authStore.isAuthenticated" class="relative group">
            <button class="flex items-center space-x-2 text-gray-300 hover:text-white p-2 rounded-md transition-colors">
              <UserIcon class="h-6 w-6" />
              <span class="text-sm">{{ authStore.user?.full_name }}</span>
            </button>
            
            <!-- Dropdown -->
            <div class="absolute right-0 mt-2 w-48 bg-slate-900 border border-purple-500/30 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">
              <router-link 
                to="/profile" 
                class="block px-4 py-2 text-sm text-gray-300 hover:bg-white/10 hover:text-white transition-colors"
              >
                Profile
              </router-link>
              <router-link 
                to="/orders" 
                class="block px-4 py-2 text-sm text-gray-300 hover:bg-white/10 hover:text-white transition-colors"
              >
                Orders
              </router-link>
              <button 
                @click="handleLogout"
                class="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-white/10 transition-colors"
              >
                Logout
              </button>
            </div>
          </div>

          <!-- Login/Register -->
          <div v-else class="flex items-center space-x-2">
            <router-link 
              to="/login" 
              class="text-gray-300 hover:text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
            >
              Login
            </router-link>
            <router-link 
              to="/register" 
              class="px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white text-sm font-semibold rounded-lg hover:shadow-lg hover:shadow-purple-500/50 transition-all"
            >
              Sign Up
            </router-link>
          </div>
        </div>

        <!-- Mobile Menu Button -->
        <button 
          @click="mobileMenuOpen = !mobileMenuOpen"
          class="md:hidden text-gray-300 hover:text-white p-2"
        >
          <Bars3Icon v-if="!mobileMenuOpen" class="h-6 w-6" />
          <XMarkIcon v-else class="h-6 w-6" />
        </button>
      </div>

      <!-- Mobile Menu -->
      <div v-if="mobileMenuOpen" class="md:hidden py-4 border-t border-purple-500/20">
        <div class="flex flex-col space-y-2">
          <router-link 
            to="/" 
            class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors"
            @click="mobileMenuOpen = false"
          >
            Home
          </router-link>
          <router-link 
            to="/products" 
            class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors"
            @click="mobileMenuOpen = false"
          >
            Products
          </router-link>
          <router-link 
            to="/cart" 
            class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center justify-between"
            @click="mobileMenuOpen = false"
          >
            <span>Cart</span>
            <span v-if="cartCount > 0" class="bg-purple-600 text-white text-xs font-bold rounded-full px-2 py-1">
              {{ cartCount }}
            </span>
          </router-link>
          
          <template v-if="authStore.isAuthenticated">
            <router-link 
              to="/wishlist" 
              class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center justify-between"
              @click="mobileMenuOpen = false"
            >
              <span>Wishlist</span>
              <span v-if="wishlistCount > 0" class="bg-pink-600 text-white text-xs font-bold rounded-full px-2 py-1">
                {{ wishlistCount }}
              </span>
            </router-link>
            <router-link 
              to="/profile" 
              class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors"
              @click="mobileMenuOpen = false"
            >
              Profile
            </router-link>
            <router-link 
              to="/orders" 
              class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors"
              @click="mobileMenuOpen = false"
            >
              Orders
            </router-link>
            <button 
              @click="handleLogout(); mobileMenuOpen = false"
              class="text-left text-red-400 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            >
              Logout
            </button>
          </template>
          
          <template v-else>
            <router-link 
              to="/login" 
              class="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors"
              @click="mobileMenuOpen = false"
            >
              Login
            </router-link>
            <router-link 
              to="/register" 
              class="text-center px-3 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white text-sm font-semibold rounded-lg"
              @click="mobileMenuOpen = false"
            >
              Sign Up
            </router-link>
          </template>
        </div>
      </div>
    </div>
  </nav>
</template>
