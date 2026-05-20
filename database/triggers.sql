-- =============================================================================
-- Smart Loom — MySQL Triggers
-- Run after tables exist:  USE smartloom;  then source this file
-- =============================================================================

USE smartloom;

DROP TRIGGER IF EXISTS trg_products_after_insert;
DROP TRIGGER IF EXISTS trg_products_before_insert;
DROP TRIGGER IF EXISTS trg_products_before_update;
DROP TRIGGER IF EXISTS trg_materials_before_update;
DROP TRIGGER IF EXISTS trg_orders_before_insert;
DROP TRIGGER IF EXISTS trg_orders_after_insert;
DROP TRIGGER IF EXISTS trg_orders_after_update;
DROP TRIGGER IF EXISTS trg_material_requests_before_update;
DROP TRIGGER IF EXISTS trg_material_requests_after_update;

DELIMITER $$

-- 1. Auto-generate product code BEFORE insert (cannot UPDATE same table in AFTER INSERT)
CREATE TRIGGER trg_products_before_insert
BEFORE INSERT ON products
FOR EACH ROW
BEGIN
    DECLARE next_id INT;
    IF NEW.product_code IS NULL OR NEW.product_code = '' THEN
        SELECT IFNULL(MAX(product_id), 0) + 1 INTO next_id FROM products;
        SET NEW.product_code = CONCAT('P-', 1000 + next_id);
    END IF;
END$$

-- 2. Prevent negative product stock on manual edits
CREATE TRIGGER trg_products_before_update
BEFORE UPDATE ON products
FOR EACH ROW
BEGIN
    IF NEW.stock < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Product stock cannot be negative';
    END IF;
END$$

-- 3. Prevent negative material stock on manual edits
CREATE TRIGGER trg_materials_before_update
BEFORE UPDATE ON materials
FOR EACH ROW
BEGIN
    IF NEW.stock < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Material stock cannot be negative';
    END IF;
END$$

-- 4. Before order: validate stock and calculate total price
CREATE TRIGGER trg_orders_before_insert
BEFORE INSERT ON orders
FOR EACH ROW
BEGIN
    DECLARE v_stock INT;
    DECLARE v_price DECIMAL(10,2);

    SELECT stock, price INTO v_stock, v_price
    FROM products
    WHERE product_id = NEW.product_id;

    IF v_stock IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Product not found';
    END IF;

    IF v_stock < NEW.quantity THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Not enough stock available';
    END IF;

    SET NEW.total_price = v_price * NEW.quantity;

    IF NEW.order_status IS NULL OR NEW.order_status = '' THEN
        SET NEW.order_status = 'Pending';
    END IF;
END$$

-- 5. After order: reduce product stock automatically
CREATE TRIGGER trg_orders_after_insert
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    UPDATE products
    SET stock = stock - NEW.quantity
    WHERE product_id = NEW.product_id;
END$$

-- 6. After order status change: restore stock when cancelled
CREATE TRIGGER trg_orders_after_update
AFTER UPDATE ON orders
FOR EACH ROW
BEGIN
    IF NEW.order_status = 'Cancelled'
       AND (OLD.order_status IS NULL OR OLD.order_status <> 'Cancelled') THEN
        UPDATE products
        SET stock = stock + OLD.quantity
        WHERE product_id = OLD.product_id;
    END IF;
END$$

-- 7. Before material delivery: validate supplier material stock
CREATE TRIGGER trg_material_requests_before_update
BEFORE UPDATE ON material_requests
FOR EACH ROW
BEGIN
    DECLARE v_stock INT;

    IF NEW.request_status = 'Delivered'
       AND (OLD.request_status IS NULL OR OLD.request_status <> 'Delivered') THEN
        SELECT stock INTO v_stock
        FROM materials
        WHERE material_id = NEW.material_id;

        IF v_stock IS NULL THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Material not found';
        END IF;

        IF v_stock < NEW.quantity THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Not enough stock available';
        END IF;
    END IF;
END$$

-- 8. After material delivery: reduce material stock automatically
CREATE TRIGGER trg_material_requests_after_update
AFTER UPDATE ON material_requests
FOR EACH ROW
BEGIN
    IF NEW.request_status = 'Delivered'
       AND (OLD.request_status IS NULL OR OLD.request_status <> 'Delivered') THEN
        UPDATE materials
        SET stock = stock - NEW.quantity
        WHERE material_id = NEW.material_id;
    END IF;
END$$

DELIMITER ;
