<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useProductStore } from '@/stores/products'
import { useAuthStore } from '@/stores/auth'
import { SortByField, SortOrder } from '@/types/api.types'
import ProductCard from '../components/product/ProductCard.vue'
import Button from '../components/ui/Button.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import { SparklesIcon, TruckIcon, ShieldCheckIcon, StarIcon, ArrowRightIcon } from '@heroicons/vue/24/outline'

const productStore = useProductStore()
const authStore = useAuthStore()

const stats = [
  { label: 'Products', value: '1000+', icon: '📦' },
  { label: 'Happy Customers', value: '50K+', icon: '😊' },
  { label: 'Countries', value: '30+', icon: '🌍' },
  { label: 'Reviews', value: '4.9/5', icon: '⭐' },
]

const categories = [
  { name: 'Electronics', icon: '💻', color: 'from-blue-500 to-cyan-500', slug: 'electronics' },
  { name: 'Fashion', icon: '👕', color: 'from-pink-500 to-rose-500', slug: 'fashion' },
  { name: 'Home & Garden', icon: '🏡', color: 'from-green-500 to-emerald-500', slug: 'home-garden' },
  { name: 'Sports', icon: '⚽', color: 'from-orange-500 to-amber-500', slug: 'sports' },
]

const featuredProducts = computed(() => productStore.products.slice(0, 8))

onMounted(async () => {
  await productStore.fetchProducts({ per_page: 8, sort_by: SortByField.RATING, sort_order: SortOrder.DESC })
  await productStore.fetchCategories()
})
</script>

<template>
  <div class="min-h-screen">
    <!-- Hero Section -->
    <section class="relative overflow-hidden py-20 px-4 bg-gradient-to-br from-purple-900/30 via-pink-900/20 to-purple-900/30">
      <!-- Animated Background Pattern -->
      <div class="absolute inset-0 opacity-10">
        <div class="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjEpIiBzdHJva2Utd2lkdGg9IjEiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjZ3JpZCkiLz48L3N2Zz4=')]"></div>
      </div>

      <div class="relative max-w-7xl mx-auto">
        <div class="text-center mb-12">
          <!-- Main Heading -->
          <h1 class="text-5xl md:text-7xl font-bold mb-6 leading-tight">
            <span class="bg-gradient-to-r from-purple-400 via-pink-500 to-purple-400 bg-clip-text text-transparent animate-gradient bg-[length:200%_auto]">
              Discover Amazing
            </span>
            <br />
            <span class="text-white">Products Today</span>
          </h1>

          <p class="text-xl text-gray-300 mb-10 max-w-2xl mx-auto">
            Shop the latest trends with unbeatable prices. Fast shipping, secure payments, and exceptional quality.
          </p>

          <!-- CTA Buttons -->
          <div class="flex justify-center gap-4 flex-wrap mb-16">
            <router-link to="/products">
              <Button variant="primary" size="lg">
                <SparklesIcon class="h-5 w-5 mr-2" />
                Explore Products
              </Button>
            </router-link>
            <router-link v-if="!authStore.isAuthenticated" to="/register">
              <Button variant="secondary" size="lg">
                Join Now
              </Button>
            </router-link>
          </div>

          <!-- Stats -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-4xl mx-auto">
            <div v-for="stat in stats" :key="stat.label" 
                 class="bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-purple-500/20 hover:border-purple-500/40 transition-all transform hover:scale-105">
              <div class="text-3xl mb-2">{{ stat.icon }}</div>
              <div class="text-2xl font-bold text-white mb-1">{{ stat.value }}</div>
              <div class="text-sm text-gray-400">{{ stat.label }}</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Categories Section -->
    <section class="py-16 px-4">
      <div class="max-w-7xl mx-auto">
        <div class="flex justify-between items-center mb-8">
          <h2 class="text-3xl md:text-4xl font-bold text-white">
            Shop by Category
          </h2>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <router-link
            v-for="category in categories"
            :key="category.name"
            :to="`/products?category=${category.slug}`"
            class="group cursor-pointer"
          >
            <div class="relative overflow-hidden rounded-2xl p-8 h-40 flex flex-col items-center justify-center border border-purple-500/30 hover:border-purple-500/60 transition-all hover:scale-105">
              <div :class="`absolute inset-0 bg-gradient-to-br ${category.color} opacity-10 group-hover:opacity-20 transition-opacity`"></div>
              <div class="relative text-5xl mb-3 transform group-hover:scale-110 transition-transform">{{ category.icon }}</div>
              <div class="relative text-white font-semibold">{{ category.name }}</div>
            </div>
          </router-link>
        </div>
      </div>
    </section>

    <!-- Trending Products -->
    <section class="py-16 px-4 bg-black/20">
      <div class="max-w-7xl mx-auto">
        <div class="flex justify-between items-center mb-8">
          <div>
            <h2 class="text-3xl md:text-4xl font-bold text-white mb-2">
              Trending Products
            </h2>
            <p class="text-gray-400">Discover what's popular right now</p>
          </div>
          <router-link to="/products">
            <Button variant="ghost">
              View All
              <ArrowRightIcon class="h-5 w-5 ml-2" />
            </Button>
          </router-link>
        </div>

        <!-- Loading Skeletons -->
        <div v-if="productStore.loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div v-for="i in 8" :key="i" class="bg-white/5 rounded-xl p-4 border border-purple-500/20">
            <Skeleton variant="image" class="mb-4" />
            <Skeleton variant="text" height="1.5rem" class="mb-2" />
            <Skeleton variant="text" height="1rem" width="60%" />
          </div>
        </div>

        <!-- Products Grid -->
        <div v-else-if="featuredProducts.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <ProductCard v-for="product in featuredProducts" :key="product.id" :product="product" />
        </div>

        <!-- Empty State -->
        <div v-else class="text-center py-12">
          <p class="text-gray-400">No trending products available</p>
        </div>
      </div>
    </section>

    <!-- Features Section -->
    <section class="py-16 px-4">
      <div class="max-w-7xl mx-auto">
        <h2 class="text-3xl md:text-4xl font-bold text-white mb-12 text-center">
          Why Shop With Us?
        </h2>
        <div class="grid md:grid-cols-3 gap-8">
          <div class="bg-white/5 backdrop-blur-sm rounded-2xl p-8 border border-purple-500/20 hover:border-purple-500/40 transition-all group">
            <div class="w-14 h-14 bg-gradient-to-br from-purple-600 to-pink-600 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
              <TruckIcon class="h-7 w-7 text-white" />
            </div>
            <h3 class="text-xl font-semibold text-white mb-3">Fast & Free Shipping</h3>
            <p class="text-gray-400">Get your orders delivered quickly with our express shipping. Free on orders over $50.</p>
          </div>

          <div class="bg-white/5 backdrop-blur-sm rounded-2xl p-8 border border-purple-500/20 hover:border-purple-500/40 transition-all group">
            <div class="w-14 h-14 bg-gradient-to-br from-purple-600 to-pink-600 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
              <ShieldCheckIcon class="h-7 w-7 text-white" />
            </div>
            <h3 class="text-xl font-semibold text-white mb-3">Secure Payments</h3>
            <p class="text-gray-400">Shop with confidence using our encrypted payment system. Your data is always protected.</p>
          </div>

          <div class="bg-white/5 backdrop-blur-sm rounded-2xl p-8 border border-purple-500/20 hover:border-purple-500/40 transition-all group">
            <div class="w-14 h-14 bg-gradient-to-br from-purple-600 to-pink-600 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
              <StarIcon class="h-7 w-7 text-white" />
            </div>
            <h3 class="text-xl font-semibold text-white mb-3">Premium Quality</h3>
            <p class="text-gray-400">Every product is carefully selected and verified to meet our high quality standards.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA Section -->
    <section class="py-20 px-4">
      <div class="max-w-4xl mx-auto text-center">
        <div class="bg-gradient-to-r from-purple-600 to-pink-600 rounded-3xl p-12 shadow-2xl shadow-purple-500/30">
          <h2 class="text-3xl md:text-4xl font-bold text-white mb-4">
            Ready to Start Shopping?
          </h2>
          <p class="text-xl text-purple-100 mb-8">
            Join thousands of happy customers and discover amazing deals today!
          </p>
          <div class="flex justify-center gap-4 flex-wrap">
            <router-link to="/products">
              <Button variant="secondary" size="lg">
                Browse Products
              </Button>
            </router-link>
            <router-link v-if="!authStore.isAuthenticated" to="/register">
              <button class="px-8 py-4 bg-white text-purple-600 font-semibold rounded-lg hover:bg-gray-100 transition-all text-lg">
                Create Account
              </button>
            </router-link>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
@keyframes gradient {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

.animate-gradient {
  animation: gradient 3s ease infinite;
}
</style>
