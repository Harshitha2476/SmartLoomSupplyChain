-- Smart Loom — Tier 1 & Tier 2 database upgrade
-- Run in MySQL:  USE smartloom;  then source this file or paste in Workbench

USE smartloom;

-- ---------------------------------------------------------------------------
-- Tier 1: products — link weaver to users table (keep weaver_name for display)
-- ---------------------------------------------------------------------------
-- Run once. Skip if column already exists.
ALTER TABLE products
  ADD COLUMN weaver_id INT NULL AFTER weaver_name;

-- Skip if constraint fk_products_weaver already exists:
ALTER TABLE products
  ADD CONSTRAINT fk_products_weaver
  FOREIGN KEY (weaver_id) REFERENCES users(user_id)
  ON DELETE SET NULL;

-- ---------------------------------------------------------------------------
-- Tier 2: notifications (low-stock alerts, system messages)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
  notification_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  message VARCHAR(500) NOT NULL,
  is_read TINYINT(1) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_notifications_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Tier 2: activity / audit log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_log (
  log_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL,
  action VARCHAR(100) NOT NULL,
  table_name VARCHAR(50) NULL,
  record_id INT NULL,
  details VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_activity_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- ---------------------------------------------------------------------------
-- Tier 2: supplier ratings (after material delivery)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS supplier_ratings (
  rating_id INT AUTO_INCREMENT PRIMARY KEY,
  supplier_id INT NOT NULL,
  rated_by INT NOT NULL,
  material_request_id INT NULL,
  rating TINYINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment VARCHAR(300) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_rating_supplier
    FOREIGN KEY (supplier_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_rating_user
    FOREIGN KEY (rated_by) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_rating_request
    FOREIGN KEY (material_request_id) REFERENCES material_requests(request_id) ON DELETE SET NULL
);

-- Optional: strengthen existing FKs (skip if already defined or errors on duplicate)
-- ALTER TABLE orders ADD CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(user_id);
-- ALTER TABLE orders ADD CONSTRAINT fk_orders_product FOREIGN KEY (product_id) REFERENCES products(product_id);
-- ALTER TABLE materials ADD CONSTRAINT fk_materials_supplier FOREIGN KEY (supplier_id) REFERENCES users(user_id);

-- Backfill weaver_id for weavers who match weaver_name (run after data exists)
UPDATE products p
JOIN users u ON u.full_name = p.weaver_name AND u.role = 'Weaver'
SET p.weaver_id = u.user_id
WHERE p.weaver_id IS NULL;
