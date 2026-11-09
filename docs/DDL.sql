-- ==========================
-- table user --
-- ==========================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    role VARCHAR(20) DEFAULT 'customer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- ========================
-- table addresses --
-- ========================
CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL,
    street TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    is_default BOOLEAN DEFAULT FALSE
);
-- =======================
-- table categories --
-- =======================
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(20) UNIQUE,
    slug VARCHAR(20) UNIQUE,
    parent_id INTEGER REFERENCES categories(id),
    description TEXT,
    image_url VARCHAR(30)
)
-- =========================
-- table products
-- =========================
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INTEGER DEFAULT 0,
    sku VARCHAR(100) UNIQUE,
    image_url VARCHAR(500),
    category_id INTEGER REFERENCES categories(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ========================================
--  CARTS
-- ========================================
CREATE TABLE Carts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NULL,
    session_id VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_carts_user FOREIGN KEY (user_id) REFERENCES Users(id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- ========================================
--  CART ITEMS
-- ========================================
CREATE TABLE CartItems (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    cart_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INT DEFAULT 1,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_cartitems_cart FOREIGN KEY (cart_id) REFERENCES Carts(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_cartitems_product FOREIGN KEY (product_id) REFERENCES Products(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ========================================
--  ORDERS
-- ========================================
CREATE TABLE Orders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    shipping_address_id BIGINT NOT NULL,
    billing_address_id BIGINT NOT NULL,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    status ENUM('pending', 'paid', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shipped_at TIMESTAMP NULL,
    tx_ref VARCHAR(255) UNIQUE,
    payment_status ENUM('pending', 'success', 'failed') DEFAULT 'pending'
    
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES Users(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_orders_shipping FOREIGN KEY (shipping_address_id) REFERENCES Addresses(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_orders_billing FOREIGN KEY (billing_address_id) REFERENCES Addresses(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);

-- ========================================
--  ORDER ITEMS
-- ========================================
CREATE TABLE OrderItems (
    id SERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    
    CONSTRAINT fk_orderitems_order FOREIGN KEY (order_id) REFERENCES Orders(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_orderitems_product FOREIGN KEY (product_id) REFERENCES Products(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ========================================
--  PAYMENTS
-- ========================================
CREATE TABLE Payments (
    id SERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL,
    payment_method ENUM('credit_card', 'paypal', 'bank_transfer') NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status ENUM('pending', 'completed', 'failed') DEFAULT 'pending',
    transaction_id VARCHAR(100),
    paid_at TIMESTAMP NULL,
    
    CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES Orders(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- ========================================
--  REVIEWS
-- ========================================
CREATE TABLE Reviews (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_approved BOOLEAN DEFAULT FALSE,
    
    CONSTRAINT fk_reviews_user FOREIGN KEY (user_id) REFERENCES Users(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_reviews_product FOREIGN KEY (product_id) REFERENCES Products(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);