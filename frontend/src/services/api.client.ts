import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { API_CONFIG, STORAGE_KEYS } from '@/config/api'
import type { APIError } from '@/types/api.types'
import { useToast } from 'vue-toastification'

const toast = useToast()

class APIClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.BASE_URL,
      timeout: API_CONFIG.TIMEOUT,
      headers: API_CONFIG.HEADERS,
      withCredentials: true, // Important for session cookies
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    // Request interceptor - Add auth token
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN)
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // Response interceptor - Handle errors
    this.client.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error: AxiosError<APIError>) => {
        this.handleError(error)
        return Promise.reject(error)
      }
    )
  }

  private handleError(error: AxiosError<APIError>) {
    if (!error.response) {
      // Network error
      toast.error('Network error. Please check your connection.')
      return
    }

    const { status, data } = error.response

    switch (status) {
      case 400:
        toast.error(data?.detail || 'Bad request')
        break
      case 401:
        toast.error('Please log in to continue')
        // Clear auth data
        localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN)
        localStorage.removeItem(STORAGE_KEYS.USER)
        // Redirect to login if not already there
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        break
      case 403:
        toast.error('You do not have permission to perform this action')
        break
      case 404:
        toast.error(data?.detail || 'Resource not found')
        break
      case 422:
        // Validation error
        if (data?.fields) {
          Object.values(data.fields).forEach((message) => {
            toast.error(message)
          })
        } else {
          toast.error(data?.detail || 'Validation error')
        }
        break
      case 500:
        toast.error('Server error. Please try again later.')
        break
      default:
        toast.error(data?.detail || 'An error occurred')
    }
  }

  // HTTP Methods
  async get<T>(url: string, config = {}) {
    const response = await this.client.get<T>(url, config)
    return response.data
  }

  async post<T>(url: string, data?: any, config = {}) {
    const response = await this.client.post<T>(url, data, config)
    return response.data
  }

  async put<T>(url: string, data?: any, config = {}) {
    const response = await this.client.put<T>(url, data, config)
    return response.data
  }

  async patch<T>(url: string, data?: any, config = {}) {
    const response = await this.client.patch<T>(url, data, config)
    return response.data
  }

  async delete<T>(url: string, config = {}) {
    const response = await this.client.delete<T>(url, config)
    return response.data
  }

  // Get raw axios instance for special cases
  getClient() {
    return this.client
  }
}

export const apiClient = new APIClient()
export default apiClient
