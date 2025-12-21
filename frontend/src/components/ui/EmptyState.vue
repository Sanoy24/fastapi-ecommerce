<script setup lang="ts">
interface Props {
  icon?: string
  title: string
  description?: string
  actionText?: string
  actionTo?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
    <div class="text-6xl mb-4">{{ icon || '📦' }}</div>
    <h3 class="text-2xl font-bold text-white mb-2">{{ title }}</h3>
    <p v-if="description" class="text-gray-400 mb-6 max-w-md">{{ description }}</p>
    
    <router-link v-if="actionTo" :to="actionTo">
      <button class="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-lg hover:shadow-lg hover:shadow-purple-500/50 transition-all">
        {{ actionText || 'Take Action' }}
      </button>
    </router-link>
    
    <button
      v-else-if="actionText"
      @click="emit('action')"
      class="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-semibold rounded-lg hover:shadow-lg hover:shadow-purple-500/50 transition-all"
    >
      {{ actionText }}
    </button>
  </div>
</template>
