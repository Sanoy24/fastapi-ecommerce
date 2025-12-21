<script setup lang="ts">
import { onMounted } from 'vue'
import { useProductStore } from '@/stores/products'
import ProductCard from '../components/product/ProductCard.vue'
import SearchBar from '../components/product/SearchBar.vue'
import Loading from '../components/ui/Loading.vue'

const productStore = useProductStore()

onMounted(() => {
  productStore.fetchProducts()
  productStore.fetchCategories()
})
</script>

<template>
  <div class="min-h-screen py-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <!-- Header with Search -->
      <div class="mb-8">
        <h1 class="text-4xl font-bold mb-6 bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
          Our Products
        </h1>
        <SearchBar />
      </div>

      <!-- Loading State -->
      <div v-if="productStore.loading" class="flex justify-center items-center h-64">
        <Loading size="lg" text="Loading products..." />
      </div>

      <!-- Products Grid -->
      <div v-else-if="productStore.hasProducts" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        <ProductCard 
          v-for="product in productStore.products" 
          :key="product.id" 
          :product="product"
        />
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-12">
        <div class="text-6xl mb-4">📦</div>
        <p class="text-xl text-gray-400 mb-6">No products found</p>
        <p class="text-gray-500">Try adjusting your search or filters</p>
      </div>

      <!-- Pagination -->
      <div v-if="productStore.totalPages > 1" class="mt-8 flex justify-center gap-2">
        <button
          v-for="page in productStore.totalPages"
          :key="page"
          @click="productStore.fetchProducts({ page })"
          :class="[
            'px-4 py-2 rounded-lg font-semibold transition-all',
            page === productStore.currentPage
              ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white'
              : 'bg-white/10 text-gray-300 hover:bg-white/20'
          ]"
        >
          {{ page }}
        </button>
      </div>
    </div>
  </div>
</template>
