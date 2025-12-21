# FastAPI E-Commerce Frontend

A modern, responsive e-commerce frontend built with **Vue 3**, **TypeScript**, **Vite**, and **Tailwind CSS**.

## Features

*   🛍️ **Product Browsing**: Advanced filtering, search, and sorting.
*   📦 **Product Details**: Image galleries, related products, and reviews.
*   🛒 **Shopping Cart**: Real-time updates, quantity management.
*   🔐 **Authentication**: Secure Login and Registration flows.
*   ✨ **Modern UI**: Polished interface with animations and responsive design.

## Prerequisites

*   Node.js 18+
*   npm 9+

## Local Development

1.  **Install dependencies**:
    ```bash
    npm install
    ```

2.  **Start development server**:
    ```bash
    npm run dev
    ```
    Access the app at `http://localhost:5173`.

## Docker Deployment

To run the frontend using Docker (Production Build with Nginx):

### Method 1: Docker Compose (Recommended)

The frontend is integrated into the main project `docker-compose.yml`.
Simply run from the root directory:

```bash
docker-compose up -d --build
```
Access the app at `http://localhost:3000`.

### Method 2: Standalone Container

1.  **Build the image**:
    ```bash
    docker build -t ecom-frontend .
    ```

2.  **Run the container**:
    ```bash
    docker run -p 3000:80 ecom-frontend
    ```
    Access at `http://localhost:3000`.

## Project Structure

*   `src/views`: Page components (Home, Products, Login, etc.)
*   `src/components`: Reusable UI components
*   `src/stores`: Pinia state management (Cart, Auth, etc.)
*   `src/services`: API client configuration
