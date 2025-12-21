<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  variant?: 'text' | 'card' | 'circle' | 'image'
  width?: string
  height?: string
  count?: number
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'text',
  width: '100%',
  height: '1rem',
  count: 1,
})

const skeletonClasses = computed(() => {
  const base = 'animate-pulse bg-gradient-to-r from-gray-200 via-gray-300 to-gray-200 bg-[length:200%_100%]'
  
  const variants = {
    text: 'rounded',
    card: 'rounded-xl',
    circle: 'rounded-full',
    image: 'rounded-lg aspect-square',
  }
  
  return `${base} ${variants[props.variant]}`
})
</script>

<template>
  <div class="space-y-2">
    <div
      v-for="i in count"
      :key="i"
      :class="skeletonClasses"
      :style="{ width, height: variant === 'image' ? 'auto' : height }"
    ></div>
  </div>
</template>

<style scoped>
@keyframes shimmer {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}

.animate-pulse {
  animation: shimmer 2s infinite linear;
}
</style>
