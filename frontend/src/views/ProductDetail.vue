<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProductStore } from '@/stores/products'
import { useCartStore } from '@/stores/cart'
import { useWishlistStore } from '@/stores/wishlist'
import { useAuthStore } from '@/stores/auth'
import Button from '../components/ui/Button.vue'
import Badge from '../components/ui/Badge.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import Breadcrumb from '../components/ui/Breadcrumb.vue'
import { 
  ShoppingCartIcon, 
  HeartIcon as HeartOutline, 
  StarIcon,
  TruckIcon,
  ShieldCheckIcon,
  ArrowPathIcon
} from '@heroicons/vue/24/outline'
import { HeartIcon as HeartSolid } from '@heroicons/vue/24/solid'
import { useToast } from 'vue-toastification'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const productStore = useProductStore()
const cartStore = useCartStore()
const wishlistStore = useWishlistStore()
const authStore = useAuthStore()

const quantity = ref(1)
const loading = ref(true)

// Get slug from route
const slug = computed(() => route.params.slug as string)

// Computed properties
const product = computed(() => productStore.currentProduct)
const inStock = computed(() => (product.value?.stock_quantity || 0) > 0)
const isInWishlist = computed(() => product.value ? wishlistStore.isInWishlist(product.value.id) : false)

// Breadcrumbs
const breadcrumbs = computed(() => {
  const items = [
    { text: 'Home', to: '/' },
    { text: 'Products', to: '/products' }
  ]
  
  if (product.value?.category) {
    items.push({ 
      text: product.value.category.name, 
      to: `/products?category=${product.value.category.slug}` 
    })
  }
  
  if (product.value) {
    items.push({ text: product.value.name, to: '' })
  }
  
  return items
})

// Actions
const loadProduct = async () => {
  loading.value = true
  try {
    const fetchedProduct = await productStore.fetchProductBySlug(slug.value)
    if (!fetchedProduct) {
      toast.error('Product not found')
      router.push('/products')
    }
  } finally {
    loading.value = false
  }
}

const updateQuantity = (newQty: number) => {
  if (newQty < 1) return
  if (product.value && newQty > product.value.stock_quantity) {
    toast.warning(`Only ${product.value.stock_quantity} items available`)
    return
  }
  quantity.value = newQty
}

const addToCart = async () => {
  if (!product.value) return
  
  const success = await cartStore.addItem(product.value.id, quantity.value)
  if (success) {
    // Optional: Reset quantity or show success feedback (already in store)
  }
}

const toggleWishlist = async () => {
  if (!authStore.isAuthenticated) {
    toast.info('Please log in to add items to wishlist')
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  
  if (product.value) {
    await wishlistStore.toggleWishlist(product.value.id)
  }
}

// Watch for route changes (e.g. clicking related product)
watch(() => route.params.slug, () => {
  if (route.params.slug) {
    loadProduct()
    quantity.value = 1
  }
})

// Initial load
onMounted(() => {
  loadProduct()
})
</script>

<template>
  <div class="min-h-screen pb-20">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Loading State -->
      <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 gap-12">
        <Skeleton variant="image" height="500px" class="rounded-2xl" />
        <div class="space-y-6">
          <Skeleton variant="text" height="40px" width="80%" />
          <Skeleton variant="text" height="24px" width="40%" />
          <Skeleton variant="text" height="32px" width="30%" />
          <Skeleton variant="text" height="100px" />
          <div class="flex gap-4">
            <Skeleton variant="text" height="50px" width="150px" />
            <Skeleton variant="text" height="50px" width="50px" />
          </div>
        </div>
      </div>

      <!-- Product Content -->
      <div v-else-if="product" class="animate-fade-in">
        <!-- Breadcrumbs -->
        <Breadcrumb :items="breadcrumbs" class="mb-8" />

        <div class="grid grid-cols-1 md:grid-cols-2 gap-12">
          <!-- Image Gallery (Left) -->
          <div class="space-y-4">
            <div class="aspect-square bg-gradient-to-br from-purple-900/40 to-pink-900/40 rounded-2xl border border-purple-500/20 flex items-center justify-center relative overflow-hidden group">
              <span class="text-9xl transform group-hover:scale-110 transition-transform duration-500">📦</span>
              
              <!-- Badges -->
              <div class="absolute top-4 left-4 flex flex-col gap-2">
                <Badge v-if="!inStock" variant="error">Out of Stock</Badge>
                <Badge v-else-if="product.stock_quantity < 5" variant="warning">Low Stock</Badge>
                <Badge v-else variant="success">In Stock</Badge>
              </div>
            </div>
          </div>

          <!-- Product Info (Right) -->
          <div class="space-y-8">
            <div>
              <h1 class="text-4xl font-bold text-white mb-2 leading-tight">{{ product.name }}</h1>
              
              <div class="flex items-center gap-4 text-sm">
                <!-- Rating -->
                <div class="flex items-center text-yellow-400 bg-yellow-400/10 px-3 py-1 rounded-full border border-yellow-400/20">
                  <StarIcon class="h-4 w-4 mr-1" />
                  <span class="font-bold mr-1">{{ product.average_rating?.toFixed(1) || '0.0' }}</span>
                  <span class="text-yellow-400/60">({{ product.review_count || 0 }} reviews)</span>
                </div>
                
                <!-- Category -->
                <router-link 
                  v-if="product.category"
                  :to="`/products?category=${product.category.slug}`"
                  class="text-purple-400 hover:text-purple-300 transition-colors bg-purple-500/10 px-3 py-1 rounded-full border border-purple-500/20"
                >
                  {{ product.category.name }}
                </router-link>
              </div>
            </div>

            <!-- Price -->
            <div class="flex items-baseline gap-2">
              <span class="text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500">
                ${{ product.price.toFixed(2) }}
              </span>
            </div>

            <!-- Description -->
            <p class="text-gray-300 text-lg leading-relaxed border-l-4 border-purple-500/30 pl-4 py-1">
              {{ product.description }}
            </p>

            <!-- Actions -->
            <div class="bg-white/5 backdrop-blur-sm rounded-2xl p-6 border border-purple-500/20 space-y-6">
              <!-- Quantity Selector -->
              <div class="flex items-center gap-4">
                <span class="text-gray-400 font-medium">Quantity:</span>
                <div class="flex items-center bg-black/20 rounded-lg border border-purple-500/30">
                  <button 
                    @click="updateQuantity(quantity - 1)" 
                    :disabled="quantity <= 1"
                    class="p-2 text-white hover:text-purple-400 disabled:opacity-30 transition-colors"
                  >
                    -
                  </button>
                  <span class="w-12 text-center text-white font-bold">{{ quantity }}</span>
                  <button 
                    @click="updateQuantity(quantity + 1)" 
                    :disabled="quantity >= product.stock_quantity"
                    class="p-2 text-white hover:text-purple-400 disabled:opacity-30 transition-colors"
                  >
                    +
                  </button>
                </div>
                <span class="text-sm text-gray-400 ml-auto">
                  {{ product.stock_quantity }} available
                </span>
              </div>

              <!-- Buttons -->
              <div class="flex gap-4">
                <Button 
                  @click="addToCart" 
                  :disabled="!inStock"
                  variant="primary" 
                  size="lg" 
                  full-width
                  class="text-lg"
                >
                  <ShoppingCartIcon class="h-6 w-6 mr-2" />
                  {{ inStock ? 'Add to Cart' : 'Out of Stock' }}
                </Button>
                
                <button 
                  @click="toggleWishlist"
                  class="p-4 rounded-xl border-2 transition-all duration-300 flex-shrink-0"
                  :class="isInWishlist 
                    ? 'border-pink-500 bg-pink-500/10 text-pink-500 hover:bg-pink-500/20' 
                    : 'border-purple-500/30 bg-white/5 text-gray-400 hover:border-purple-500 hover:text-white'"
                >
                  <HeartSolid v-if="isInWishlist" class="h-6 w-6" />
                  <HeartOutline v-else class="h-6 w-6" />
                </button>
              </div>
            </div>

            <!-- Benefits -->
            <div class="grid grid-cols-2 gap-4 pt-4">
              <div class="flex items-center gap-3 text-gray-300 hidden md:flex">
                <TruckIcon class="h-5 w-5 text-purple-400" />
                <span class="text-sm">Free shipping over $50</span>
              </div>
              <div class="flex items-center gap-3 text-gray-300 hidden md:flex">
                <ShieldCheckIcon class="h-5 w-5 text-purple-400" />
                <span class="text-sm">2 year extended warranty</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.5s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
