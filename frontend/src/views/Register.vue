<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Input from '../components/ui/Input.vue'
import Button from '../components/ui/Button.vue'
import { EyeIcon, EyeSlashIcon } from '@heroicons/vue/24/outline'

const router = useRouter()
const authStore = useAuthStore()

const firstName = ref('')
const lastName = ref('')
const phone = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const error = ref('')
const loading = ref(false)

const handleRegister = async () => {
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }

  loading.value = true
  error.value = ''
  
  try {
    const success = await authStore.register({
      email: email.value,
      password: password.value,
      first_name: firstName.value,
      last_name: lastName.value,
      phone: phone.value
    })

    if (success) {
      router.push('/login')
    } else {
      error.value = 'Registration failed. Please try again.'
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail || 'Registration failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-12">
    <div class="max-w-md w-full">
      <!-- Header -->
      <div class="text-center mb-8">
        <router-link to="/" class="inline-block">
          <h1 class="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent">
            FastAPI E-Commerce
          </h1>
        </router-link>
        <h2 class="mt-6 text-3xl font-bold text-white">Create your account</h2>
        <p class="mt-2 text-gray-400">Join us to start shopping today</p>
      </div>

      <!-- Register Form -->
      <div class="bg-white/10 backdrop-blur-lg rounded-2xl border border-purple-500/30 p-8 shadow-2xl">
        <form @submit.prevent="handleRegister" class="space-y-6">
          <!-- Error Message -->
          <div v-if="error" class="bg-red-500/20 border border-red-500 rounded-lg p-4 flex items-start space-x-3">
            <svg class="h-5 w-5 text-red-400 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-red-200 text-sm">{{ error }}</p>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <!-- First Name -->
            <Input
              v-model="firstName"
              label="First Name"
              placeholder="John"
              required
            />
            <!-- Last Name -->
            <Input
              v-model="lastName"
              label="Last Name"
              placeholder="Doe"
              required
            />
          </div>

          <!-- Phone -->
          <Input
            v-model="phone"
            type="tel"
            label="Phone Number"
            placeholder="+1 234 567 8900"
            required
          />

          <!-- Email -->
          <Input
            v-model="email"
            type="email"
            label="Email address"
            placeholder="you@example.com"
            required
          />

          <!-- Password -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">
              Password
            </label>
            <div class="relative">
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                required
                class="w-full px-4 py-3 pr-12 bg-white/5 border border-purple-500/30 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                placeholder="••••••••"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
              >
                <EyeIcon v-if="!showPassword" class="h-5 w-5" />
                <EyeSlashIcon v-else class="h-5 w-5" />
              </button>
            </div>
            <p class="mt-1 text-xs text-gray-500">Must be at least 8 characters</p>
          </div>

          <!-- Confirm Password -->
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">
              Confirm Password
            </label>
            <div class="relative">
              <input
                v-model="confirmPassword"
                :type="showConfirmPassword ? 'text' : 'password'"
                required
                class="w-full px-4 py-3 pr-12 bg-white/5 border border-purple-500/30 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                placeholder="••••••••"
              />
              <button
                type="button"
                @click="showConfirmPassword = !showConfirmPassword"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
              >
                <EyeIcon v-if="!showConfirmPassword" class="h-5 w-5" />
                <EyeSlashIcon v-else class="h-5 w-5" />
              </button>
            </div>
          </div>

          <!-- Terms -->
          <div class="flex items-start">
            <div class="flex items-center h-5">
              <input
                id="terms"
                type="checkbox"
                required
                class="w-4 h-4 bg-white/5 border-purple-500/30 rounded text-purple-600 focus:ring-purple-500 focus:ring-offset-0"
              />
            </div>
            <div class="ml-3 text-sm">
              <label for="terms" class="text-gray-300">
                I agree to the <a href="#" class="text-purple-400 hover:text-purple-300">Terms of Service</a> and <a href="#" class="text-purple-400 hover:text-purple-300">Privacy Policy</a>
              </label>
            </div>
          </div>

          <!-- Submit Button -->
          <Button
            type="submit"
            variant="primary"
            size="lg"
            :loading="loading"
            full-width
          >
            {{ loading ? 'Creating account...' : 'Create Account' }}
          </Button>
        </form>

        <!-- Login Link -->
        <div class="mt-6 text-center">
          <p class="text-gray-400">
            Already have an account?
            <router-link to="/login" class="text-purple-400 hover:text-purple-300 font-semibold transition-colors">
              Sign in
            </router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
