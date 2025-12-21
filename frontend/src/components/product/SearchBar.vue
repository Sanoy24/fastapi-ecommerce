<script setup lang="ts">
import { ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { useProductStore } from '@/stores/products'
import { MagnifyingGlassIcon } from '@heroicons/vue/24/outline'

const productStore = useProductStore()

const searchQuery = ref('')
const suggestions = ref<string[]>([])
const showSuggestions = ref(false)
const loading = ref(false)

const fetchSuggestions = useDebounceFn(async (query: string) => {
  if (query.length < 2) {
    suggestions.value = []
    return
  }
  
  loading.value = true
  suggestions.value = await productStore.getAutocomplete(query)
  loading.value = false
  showSuggestions.value = true
}, 300)

watch(searchQuery, (newValue) => {
  if (newValue.length >= 2) {
    fetchSuggestions(newValue)
  } else {
    suggestions.value = []
    showSuggestions.value = false
  }
})

const handleSearch = () => {
  if (searchQuery.value.trim()) {
    productStore.searchProducts(searchQuery.value)
    showSuggestions.value = false
  }
}

const selectSuggestion = (suggestion: string) => {
  searchQuery.value = suggestion
  showSuggestions.value = false
  handleSearch()
}

const handleBlur = () => {
  // Delay to allow click on suggestion
  setTimeout(() => {
    showSuggestions.value = false
  }, 200)
}
</script>

<template>
  <div class="relative w-full max-w-2xl">
    <div class="relative">
      <input
        v-model="searchQuery"
        type="search"
        placeholder="Search products..."
        class="w-full px-4 py-3 pl-12 bg-white/10 backdrop-blur-md border border-purple-500/30 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
        @keyup.enter="handleSearch"
        @focus="showSuggestions = suggestions.length > 0"
        @blur="handleBlur"
      />
      
      <MagnifyingGlassIcon class="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
      
      <button
        v-if="searchQuery"
        @click="handleSearch"
        class="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-1.5 bg-gradient-to-r from-purple-600 to-pink-600 text-white text-sm font-semibold rounded-md hover:shadow-lg hover:shadow-purple-500/50 transition-all"
      >
        Search
      </button>
    </div>

    <!-- Autocomplete Suggestions -->
    <div
      v-if="showSuggestions && suggestions.length > 0"
      class="absolute z-50 w-full mt-2 bg-slate-900 border border-purple-500/30 rounded-lg shadow-xl max-h-60 overflow-y-auto"
    >
      <button
        v-for="(suggestion, index) in suggestions"
        :key="index"
        @click="selectSuggestion(suggestion)"
        class="w-full text-left px-4 py-3 text-white hover:bg-white/10 transition-colors border-b border-purple-500/10 last:border-b-0"
      >
        <MagnifyingGlassIcon class="inline h-4 w-4 mr-2 text-gray-400" />
        {{ suggestion }}
      </button>
    </div>

    <!-- Loading Indicator -->
    <div
      v-if="loading"
      class="absolute right-14 top-1/2 -translate-y-1/2"
    >
      <div class="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-purple-500"></div>
    </div>
  </div>
</template>
