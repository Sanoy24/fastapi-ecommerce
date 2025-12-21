<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4">
    <div class="max-w-2xl w-full">
      <div class="text-center mb-8">
        <h1 class="text-4xl font-bold mb-4 bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
          My Profile
        </h1>
      </div>

      <div class="bg-white/10 backdrop-blur-lg rounded-2xl border border-purple-500/30 p-8 shadow-2xl">
        <div v-if="authStore.user" class="space-y-6">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">Full Name</label>
            <div class="px-4 py-3 bg-white/5 border border-purple-500/30 rounded-lg text-white">
              {{ authStore.user.full_name }}
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">Email</label>
            <div class="px-4 py-3 bg-white/5 border border-purple-500/30 rounded-lg text-white">
              {{ authStore.user.email }}
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">Account Status</label>
            <div class="px-4 py-3 bg-white/5 border border-purple-500/30 rounded-lg">
              <span :class="authStore.user.is_active ? 'text-green-400' : 'text-red-400'">
                {{ authStore.user.is_active ? 'Active' : 'Inactive' }}
              </span>
            </div>
          </div>

          <div class="pt-4">
            <button @click="authStore.logout" 
                    class="w-full px-6 py-3 bg-red-500/20 border border-red-500 text-red-400 font-semibold rounded-lg hover:bg-red-500/30 transition-colors">
              Logout
            </button>
          </div>
        </div>

        <div v-else class="text-center text-gray-400">
          <p>Loading profile...</p>
        </div>
      </div>

      <div class="mt-6 text-center">
        <router-link to="/" class="text-purple-400 hover:text-purple-300 transition-colors">
          ← Back to Home
        </router-link>
      </div>
    </div>
  </div>
</template>
