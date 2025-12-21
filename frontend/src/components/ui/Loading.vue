<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  size?: 'sm' | 'md' | 'lg'
  text?: string
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
})

const sizeClasses = computed(() => {
  const sizes = {
    sm: 'h-8 w-8',
    md: 'h-16 w-16',
    lg: 'h-24 w-24',
  }
  return sizes[props.size]
})
</script>

<template>
  <div class="flex flex-col items-center justify-center">
    <div class="relative">
      <div :class="sizeClasses" class="animate-spin rounded-full border-t-2 border-b-2 border-purple-500"></div>
    </div>
    <p v-if="text" class="mt-4 text-gray-300">{{ text }}</p>
  </div>
</template>
