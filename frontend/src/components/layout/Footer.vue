<script setup lang="ts">
const currentYear = new Date().getFullYear()
</script>

<template>
  <footer class="bg-black/30 backdrop-blur-md border-t border-purple-500/20 mt-auto">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div class="grid md:grid-cols-4 gap-8">
        <!-- Brand -->
        <div class="col-span-1">
          <h3 class="text-xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent mb-4">
            FastAPI E-Commerce
          </h3>
          <p class="text-gray-400 text-sm">
            Your one-stop shop for amazing products. Built with Vue 3 and FastAPI.
          </p>
        </div>

        <!-- Quick Links -->
        <div>
          <h4 class="text-white font-semibold mb-4">Quick Links</h4>
          <ul class="space-y-2">
            <li>
              <router-link to="/" class="text-gray-400 hover:text-white text-sm transition-colors">
                Home
              </router-link>
            </li>
            <li>
              <router-link to="/products" class="text-gray-400 hover:text-white text-sm transition-colors">
                Products
              </router-link>
            </li>
            <li>
              <router-link to="/cart" class="text-gray-400 hover:text-white text-sm transition-colors">
                Shopping Cart
              </router-link>
            </li>
          </ul>
        </div>

        <!-- Customer Service -->
        <div>
          <h4 class="text-white font-semibold mb-4">Customer Service</h4>
          <ul class="space-y-2">
            <li>
              <a href="#" class="text-gray-400 hover:text-white text-sm transition-colors">
                Contact Us
              </a>
            </li>
            <li>
              <a href="#" class="text-gray-400 hover:text-white text-sm transition-colors">
                Shipping Info
              </a>
            </li>
            <li>
              <a href="#" class="text-gray-400 hover:text-white text-sm transition-colors">
                Returns
              </a>
            </li>
            <li>
              <a href="#" class="text-gray-400 hover:text-white text-sm transition-colors">
                FAQ
              </a>
            </li>
          </ul>
        </div>

        <!-- Legal -->
        <div>
          <h4 class="text-white font-semibold mb-4">Legal</h4>
          <ul class="space-y-2">
            <li>
              <a href="#" class="text-gray-400 hover:text-white text-sm transition-colors">
                Privacy Policy
              </a>
            </li>
            <li>
              <a href="#" class="text-gray-400 hover:text-white text-sm transition-colors">
                Terms of Service
              </a>
            </li>
            <li>
              <a href="#" class="text-gray-400 hover:text-white text-sm transition-colors">
                Cookie Policy
              </a>
            </li>
          </ul>
        </div>
      </div>

      <!-- Bottom Bar -->
      <div class="mt-8 pt-8 border-t border-purple-500/20 text-center">
        <p class="text-gray-400 text-sm">
          &copy; {{ currentYear }} FastAPI E-Commerce. Built with Vue 3 + FastAPI. All rights reserved.
        </p>
      </div>
    </div>
  </footer>
</template>
