<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronRightIcon, HomeIcon } from '@heroicons/vue/24/outline'

interface BreadcrumbItem {
  label: string
  to?: string
}

interface Props {
  items?: BreadcrumbItem[]
}

const props = defineProps<Props>()
const route = useRoute()

const breadcrumbs = computed(() => {
  if (props.items) return props.items

  // Auto-generate from route
  const paths = route.path.split('/').filter(Boolean)
  const items: BreadcrumbItem[] = [{ label: 'Home', to: '/' }]

  paths.forEach((path, index) => {
    const to = '/' + paths.slice(0, index + 1).join('/')
    const label = path.charAt(0).toUpperCase() + path.slice(1).replace(/-/g, ' ')
    items.push({ label, to: index === paths.length - 1 ? undefined : to })
  })

  return items
})
</script>

<template>
  <nav class="flex items-center space-x-2 text-sm text-gray-400 mb-6">
    <router-link
      v-for="(item, index) in breadcrumbs"
      :key="index"
      :to="item.to || '#'"
      :class="[
        'flex items-center space-x-2 hover:text-white transition-colors',
        !item.to && 'text-white cursor-default pointer-events-none'
      ]"
    >
      <HomeIcon v-if="index === 0" class="h-4 w-4" />
      <span v-else>{{ item.label }}</span>
      <ChevronRightIcon v-if="index < breadcrumbs.length - 1" class="h-4 w-4" />
    </router-link>
  </nav>
</template>
