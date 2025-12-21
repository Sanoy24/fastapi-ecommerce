<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  variant?: 'success' | 'warning' | 'error' | 'info' | 'default'
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'md',
})

const badgeClasses = computed(() => {
  const base = 'inline-flex items-center font-semibold rounded-full'
  
  const variants = {
    success: 'bg-green-500/20 text-green-400 border border-green-500',
    warning: 'bg-amber-500/20 text-amber-400 border border-amber-500',
    error: 'bg-red-500/20 text-red-400 border border-red-500',
    info: 'bg-blue-500/20 text-blue-400 border border-blue-500',
    default: 'bg-purple-500/20 text-purple-400 border border-purple-500',
  }
  
  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base',
  }
  
  return `${base} ${variants[props.variant]} ${sizes[props.size]}`
})
</script>

<template>
  <span :class="badgeClasses">
    <slot />
  </span>
</template>
