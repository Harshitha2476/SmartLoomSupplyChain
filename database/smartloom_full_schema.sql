-- =============================================================================
-- Smart Loom — Complete MySQL Database Script
-- Supply Chain Management System for Textile Industry
-- =============================================================================
-- How to run (MySQL Workbench or command line):
--   mysql -u root -p < database/smartloom_full_schema.sql
-- Or open this file in Workbench and execute all.
--
-- Default DB name: smartloom (matches app.py)
-- App connection: host=localhost, user=root, password=password
-- =============================================================================

SET FOREIGN_KEY_CHECKS = 0;

DROP DATABASE IF EXISTS smartloom;
CREATE DATABASE smartloom CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smartloom;

-- =============================================================================
-- 1. USERS (Buyer, Weaver, Supplier, Admin)
-- =============================================================================
CREATE TABLE users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(120) NOT NULL,
    phone         VARCHAR(20)  NULL,
    password      VARCHAR(255) NOT NULL,
    role          ENUM('Buyer', 'Weaver', 'Supplier', 'Admin') NOT NULL,
    location      VARCHAR(100) NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_email_role (email, role)
) ENGINE=InnoDB;

-- =============================================================================
-- 2. PRODUCTS (woven goods listed by weavers)
-- =============================================================================
CREATE TABLE products (
    product_id    INT AUTO_INCREMENT PRIMARY KEY,
    product_code  VARCHAR(20)  NULL,
    product_name  VARCHAR(150) NOT NULL,
    category      VARCHAR(50)  NOT NULL,
    weaver_name   VARCHAR(100) NULL,
    weaver_id     INT          NULL,
    price         DECIMAL(10,2) NOT NULL DEFAULT 0,
    stock         INT NOT NULL DEFAULT 0,
    description   TEXT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_products_weaver
        FOREIGN KEY (weaver_id) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- =============================================================================
-- 3. MATERIALS (raw materials owned by suppliers)
-- =============================================================================
CREATE TABLE materials (
    material_id   INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id   INT NOT NULL,
    material_name VARCHAR(150) NOT NULL,
    material_type VARCHAR(50)  NOT NULL,
    stock         INT NOT NULL DEFAULT 0,
    price         DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_materials_supplier
        FOREIGN KEY (supplier_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- 4. ORDERS (buyers purchase products)
-- =============================================================================
CREATE TABLE orders (
    order_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    product_id    INT NOT NULL,
    quantity      INT NOT NULL DEFAULT 1,
    total_price   DECIMAL(10,2) NOT NULL,
    order_status  VARCHAR(30) NOT NULL DEFAULT 'Pending',
    order_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_orders_product
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- 5. MATERIAL REQUESTS (weavers request materials from suppliers)
-- =============================================================================
CREATE TABLE material_requests (
    request_id      INT AUTO_INCREMENT PRIMARY KEY,
    weaver_id       INT NOT NULL,
    supplier_id     INT NOT NULL,
    material_id     INT NOT NULL,
    quantity        INT NOT NULL,
    request_status  VARCHAR(30) NOT NULL DEFAULT 'Pending',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mr_weaver
        FOREIGN KEY (weaver_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_mr_supplier
        FOREIGN KEY (supplier_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_mr_material
        FOREIGN KEY (material_id) REFERENCES materials(material_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- 6. NOTIFICATIONS (low-stock alerts, system messages)
-- =============================================================================
CREATE TABLE notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    message         VARCHAR(500) NOT NULL,
    is_read         TINYINT(1) NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =============================================================================
-- 7. ACTIVITY LOG (audit trail)
-- =============================================================================
CREATE TABLE activity_log (
    log_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NULL,
    action      VARCHAR(100) NOT NULL,
    table_name  VARCHAR(50)  NULL,
    record_id   INT NULL,
    details     VARCHAR(255) NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_activity_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- =============================================================================
-- 8. SUPPLIER RATINGS (weavers rate after delivery)
-- =============================================================================
CREATE TABLE supplier_ratings (
    rating_id             INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id           INT NOT NULL,
    rated_by              INT NOT NULL,
    material_request_id   INT NULL,
    rating                TINYINT NOT NULL,
    comment               VARCHAR(300) NULL,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rating_supplier
        FOREIGN KEY (supplier_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_rating_user
        FOREIGN KEY (rated_by) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_rating_request
        FOREIGN KEY (material_request_id) REFERENCES material_requests(request_id) ON DELETE SET NULL,
    CONSTRAINT chk_rating_range CHECK (rating BETWEEN 1 AND 5),
    UNIQUE KEY uq_rating_per_user_request (rated_by, material_request_id)
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- TRIGGERS (automated business rules — same logic as Flask app)
-- =============================================================================
DROP TRIGGER IF EXISTS trg_products_after_insert;
DROP TRIGGER IF EXISTS trg_products_before_update;
DROP TRIGGER IF EXISTS trg_materials_before_update;
DROP TRIGGER IF EXISTS trg_orders_before_insert;
DROP TRIGGER IF EXISTS trg_orders_after_insert;
DROP TRIGGER IF EXISTS trg_orders_after_update;
DROP TRIGGER IF EXISTS trg_material_requests_before_update;
DROP TRIGGER IF EXISTS trg_material_requests_after_update;

DELIMITER $$

CREATE TRIGGER trg_products_after_insert
AFTER INSERT ON products
FOR EACH ROW
BEGIN
    UPDATE products
    SET product_code = CONCAT('P-', 1000 + product_id)
    WHERE product_id = NEW.product_id;
END$$

CREATE TRIGGER trg_products_before_update
BEFORE UPDATE ON products
FOR EACH ROW
BEGIN
    IF NEW.stock < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Product stock cannot be negative';
    END IF;
END$$

CREATE TRIGGER trg_materials_before_update
BEFORE UPDATE ON materials
FOR EACH ROW
BEGIN
    IF NEW.stock < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Material stock cannot be negative';
    END IF;
END$$

CREATE TRIGGER trg_orders_before_insert
BEFORE INSERT ON orders
FOR EACH ROW
BEGIN
    DECLARE v_stock INT;
    DECLARE v_price DECIMAL(10,2);
    SELECT stock, price INTO v_stock, v_price
    FROM products WHERE product_id = NEW.product_id;
    IF v_stock IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Product not found';
    END IF;
    IF v_stock < NEW.quantity THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Not enough stock available';
    END IF;
    SET NEW.total_price = v_price * NEW.quantity;
    IF NEW.order_status IS NULL OR NEW.order_status = '' THEN
        SET NEW.order_status = 'Pending';
    END IF;
END$$

CREATE TRIGGER trg_orders_after_insert
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    UPDATE products SET stock = stock - NEW.quantity WHERE product_id = NEW.product_id;
END$$

CREATE TRIGGER trg_orders_after_update
AFTER UPDATE ON orders
FOR EACH ROW
BEGIN
    IF NEW.order_status = 'Cancelled'
       AND (OLD.order_status IS NULL OR OLD.order_status <> 'Cancelled') THEN
        UPDATE products SET stock = stock + OLD.quantity WHERE product_id = OLD.product_id;
    END IF;
END$$

CREATE TRIGGER trg_material_requests_before_update
BEFORE UPDATE ON material_requests
FOR EACH ROW
BEGIN
    DECLARE v_stock INT;
    IF NEW.request_status = 'Delivered'
       AND (OLD.request_status IS NULL OR OLD.request_status <> 'Delivered') THEN
        SELECT stock INTO v_stock FROM materials WHERE material_id = NEW.material_id;
        IF v_stock IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Material not found';
        END IF;
        IF v_stock < NEW.quantity THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Not enough stock available';
        END IF;
    END IF;
END$$

CREATE TRIGGER trg_material_requests_after_update
AFTER UPDATE ON material_requests
FOR EACH ROW
BEGIN
    IF NEW.request_status = 'Delivered'
       AND (OLD.request_status IS NULL OR OLD.request_status <> 'Delivered') THEN
        UPDATE materials SET stock = stock - NEW.quantity WHERE material_id = NEW.material_id;
    END IF;
END$$

DELIMITER ;

-- =============================================================================
-- INDEXES (performance for common app queries)
-- =============================================================================
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_stock ON products(stock);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(order_status);
CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_materials_supplier ON materials(supplier_id);
CREATE INDEX idx_mr_weaver ON material_requests(weaver_id);
CREATE INDEX idx_mr_supplier ON material_requests(supplier_id);
CREATE INDEX idx_mr_status ON material_requests(request_status);

-- =============================================================================
-- VIEWS (useful for reports / DBMS project)
-- =============================================================================
CREATE OR REPLACE VIEW v_order_summary AS
SELECT
    o.order_id,
    o.order_date,
    o.order_status,
    o.quantity,
    o.total_price,
    u.full_name AS buyer_name,
    p.product_name,
    p.product_code,
    p.category
FROM orders o
JOIN users u ON o.user_id = u.user_id
JOIN products p ON o.product_id = p.product_id;

CREATE OR REPLACE VIEW v_material_request_summary AS
SELECT
    mr.request_id,
    mr.request_status,
    mr.quantity,
    mr.created_at,
    w.full_name AS weaver_name,
    s.full_name AS supplier_name,
    m.material_name,
    m.material_type
FROM material_requests mr
JOIN users w ON mr.weaver_id = w.user_id
JOIN users s ON mr.supplier_id = s.user_id
JOIN materials m ON mr.material_id = m.material_id;

CREATE OR REPLACE VIEW v_low_stock_products AS
SELECT product_id, product_code, product_name, category, stock, weaver_name
FROM products
WHERE stock < 10;

-- =============================================================================
-- SAMPLE DATA (demo users — password: demo123 for all)
-- Register via app to use hashed passwords; these are for quick testing only.
-- =============================================================================
INSERT INTO users (full_name, email, phone, password, role, location) VALUES
('Admin User',    'admin@smartloom.in',    '9000000001', 'demo123', 'Admin',    'Mumbai'),
('Riya Mehta',    'buyer@smartloom.in',    '9000000002', 'demo123', 'Buyer',    'Delhi'),
('Anika Verma',   'weaver@smartloom.in',   '9000000003', 'demo123', 'Weaver',   'Varanasi'),
('Kabir Sethi',   'supplier@smartloom.in', '9000000004', 'demo123', 'Supplier', 'Surat');

INSERT INTO products (product_name, category, weaver_name, weaver_id, price, stock, description, product_code) VALUES
('Banarasi Silk Saree',  'Saree',   'Anika Verma', 3, 14500.00, 8,  'Handwoven Banarasi silk saree', 'P-1001'),
('Chanderi Dupatta',     'Dupatta', 'Anika Verma', 3,  3200.00, 15, 'Lightweight Chanderi dupatta',  'P-1002'),
('Khadi Cotton Yardage', 'Yardage', 'Anika Verma', 3,  1800.00, 25, 'Organic khadi yardage',         'P-1003'),
('Pashmina Shawl',       'Shawl',   'Anika Verma', 3, 22000.00, 5,  'Premium pashmina shawl',        'P-1004');

INSERT INTO materials (supplier_id, material_name, material_type, stock, price) VALUES
(4, 'Mulberry Silk Yarn', 'Yarn',   500, 850.00),
(4, 'Cotton Warp Roll',   'Cotton', 200, 420.00),
(4, 'Natural Dye Kit',    'Dye',    80,  650.00);

INSERT INTO orders (user_id, product_id, quantity, total_price, order_status) VALUES
(2, 1, 1, 14500.00, 'Pending'),
(2, 2, 2,  6400.00, 'Delivered');

INSERT INTO material_requests (weaver_id, supplier_id, material_id, quantity, request_status) VALUES
(3, 4, 1, 10, 'Pending'),
(3, 4, 2,  5, 'Approved');

-- =============================================================================
-- COMMON QUERIES USED IN THE FLASK APP (reference for DBMS report)
-- =============================================================================

-- Login
-- SELECT * FROM users WHERE email = ? AND role = ?;

-- Register (check duplicate email)
-- SELECT * FROM users WHERE email = ?;

-- Dashboard: counts and revenue
-- SELECT COUNT(*) AS total_products FROM products;
-- SELECT COUNT(*) AS total_orders FROM orders;
-- SELECT COUNT(*) AS total_users FROM users;
-- SELECT SUM(total_price) AS revenue FROM orders;

-- Low stock alert
-- SELECT * FROM products WHERE stock < 10;

-- Recent orders with product name (JOIN)
-- SELECT orders.order_id, products.product_name, orders.total_price, orders.order_status
-- FROM orders JOIN products ON orders.product_id = products.product_id
-- ORDER BY orders.order_date DESC LIMIT 5;

-- Buyer orders
-- SELECT orders.*, products.product_name FROM orders
-- JOIN products ON orders.product_id = products.product_id
-- WHERE orders.user_id = ? ORDER BY orders.order_date DESC;

-- Place order (triggers handle price, stock check, stock reduction):
-- INSERT INTO orders (user_id, product_id, quantity, total_price) VALUES (?,?,?,0);
--   -> trg_orders_before_insert sets total_price, validates stock
--   -> trg_orders_after_insert reduces product stock

-- Cancel order (trigger restores stock):
-- UPDATE orders SET order_status = 'Cancelled' WHERE order_id = ?;
--   -> trg_orders_after_update restores product stock

-- Supplier material requests
-- SELECT material_requests.*, materials.material_name
-- FROM material_requests JOIN materials ON material_requests.material_id = materials.material_id
-- WHERE material_requests.supplier_id = ?;

-- Deliver material (triggers handle stock):
-- UPDATE material_requests SET request_status = 'Delivered' WHERE request_id = ?;
--   -> trg_material_requests_before_update validates stock
--   -> trg_material_requests_after_update reduces material stock

-- Add product (trigger sets product code):
-- INSERT INTO products (...) VALUES (...);
--   -> trg_products_after_insert sets product_code = P-{id}

-- Monthly revenue report (GROUP BY)
-- SELECT DATE_FORMAT(order_date, '%Y-%m') AS month,
--        SUM(total_price) AS revenue, COUNT(*) AS order_count
-- FROM orders GROUP BY DATE_FORMAT(order_date, '%Y-%m');

-- Top selling products
-- SELECT p.product_name, SUM(o.quantity) AS units_sold, SUM(o.total_price) AS revenue
-- FROM orders o JOIN products p ON o.product_id = p.product_id
-- WHERE o.order_status != 'Cancelled' GROUP BY p.product_id ORDER BY revenue DESC;

-- Supplier average rating
-- SELECT supplier_id, AVG(rating) AS avg_rating, COUNT(*) AS rating_count
-- FROM supplier_ratings GROUP BY supplier_id;

-- =============================================================================
-- END OF SCRIPT
-- =============================================================================
