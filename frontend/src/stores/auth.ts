import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@/services/api.client'
import { ROUTES, STORAGE_KEYS } from '@/config/api'
import type { User, LoginRequest, RegisterRequest, TokenResponse } from '@/types/api.types'
import { useToast } from 'vue-toastification'

const toast = useToast()

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const loading = ref(false)

  // Getters
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.is_admin || false)

  // Actions
  async function login(credentials: LoginRequest) {
    loading.value = true
    try {
      // Backend expects JSON with email and password, not FormData
      const response = await apiClient.post<TokenResponse>(
        ROUTES.LOGIN,
        {
          email: credentials.email,
          password: credentials.password,
        }
      )

      token.value = response.token
      localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, response.token)

      // Fetch user data
      await fetchUser()

      toast.success('Welcome back!')
      return true
    } catch (error) {
      console.error('Login error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function register(data: RegisterRequest) {
    loading.value = true
    try {
      await apiClient.post<User>(ROUTES.REGISTER, data)
      toast.success('Registration successful! Please log in.')
      return true
    } catch (error) {
      console.error('Registration error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchUser() {
    try {
      const userData = await apiClient.get<User>(ROUTES.ME)
      user.value = userData
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(userData))
    } catch (error) {
      console.error('Fetch user error:', error)
      logout()
    }
  }

  async function updateProfile(data: Partial<User>) {
    loading.value = true
    try {
      const updatedUser = await apiClient.put<User>(ROUTES.ME, data)
      user.value = updatedUser
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(updatedUser))
      toast.success('Profile updated successfully')
      return true
    } catch (error) {
      console.error('Update profile error:', error)
      return false
    } finally {
      loading.value = false
    }
  }

  function logout() {
    user.value = null
    token.value = null
    localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN)
    localStorage.removeItem(STORAGE_KEYS.USER)
    toast.info('Logged out successfully')
  }

  function initializeAuth() {
    const storedToken = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN)
    const storedUser = localStorage.getItem(STORAGE_KEYS.USER)

    if (storedToken && storedUser) {
      token.value = storedToken
      user.value = JSON.parse(storedUser)
      // Optionally refresh user data
      fetchUser()
    }
  }

  return {
    // State
    user,
    token,
    loading,
    // Getters
    isAuthenticated,
    isAdmin,
    // Actions
    login,
    register,
    fetchUser,
    updateProfile,
    logout,
    initializeAuth,
  }
})
