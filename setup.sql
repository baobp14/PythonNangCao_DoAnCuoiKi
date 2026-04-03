/* SCRIPT TẠO CƠ SỞ DỮ LIỆU ĐẦY ĐỦ CHO ĐỒ ÁN
    Database: banhang_db
*/

-- 1. Tạo Database (Nếu chưa có)
CREATE DATABASE IF NOT EXISTS banhang_db 
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE banhang_db;

/* Tắt kiểm tra khóa ngoại để tạo bảng thuận lợi */
SET FOREIGN_KEY_CHECKS = 0;

-- 2. Bảng `user` (Lưu người dùng, admin)
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `phone_number` varchar(20) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `full_name` varchar(100) DEFAULT NULL,
  `user_role` varchar(20) DEFAULT 'user',
  PRIMARY KEY (`id`),
  UNIQUE KEY `phone_number` (`phone_number`)
) ENGINE=InnoDB;

-- 3. Bảng `product` (Lưu sản phẩm)
DROP TABLE IF EXISTS `product`;
CREATE TABLE `product` (
  `id` int NOT NULL AUTO_INCREMENT,
  `base_name` varchar(255) NOT NULL,
  `color` varchar(50) DEFAULT NULL,
  `storage` varchar(50) DEFAULT NULL,
  `price` decimal(12,0) NOT NULL,
  `stock_quantity` int NOT NULL DEFAULT '0',
  `description` text,
  `main_image_url` varchar(512) DEFAULT NULL,
  `category_name` varchar(100) DEFAULT NULL,
  `brand_name` varchar(100) DEFAULT NULL,
  `specs` json DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;

-- 4. Bảng `cart` (Lưu giỏ hàng của user)
DROP TABLE IF EXISTS `cart`;
CREATE TABLE `cart` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `cart_content` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `cart_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. Bảng `orders` (Lưu đơn hàng đã thanh toán/COD)
DROP TABLE IF EXISTS `orders`;
CREATE TABLE `orders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `amount` decimal(12,0) NOT NULL,
  `status` varchar(50) NOT NULL DEFAULT 'pending',          -- Trạng thái thanh toán (pending, success, cod)
  `fulfillment_status` varchar(50) NOT NULL DEFAULT 'preparing',  -- Trạng thái giao hàng (preparing, delivering, delivered)
  `shipping_address` text,
  `order_content` json DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,                      -- Email khách nhập lúc thanh toán
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB;

-- 6. Bảng `product_reviews` (Lưu đánh giá sản phẩm)
DROP TABLE IF EXISTS `product_reviews`;
CREATE TABLE `product_reviews` (
  `id` int NOT NULL AUTO_INCREMENT,
  `product_id` int NOT NULL,
  `user_id` int NOT NULL,
  `rating` int NOT NULL,
  `comment` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `product_id` (`product_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `product_reviews_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `product` (`id`),
  CONSTRAINT `product_reviews_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB;

/* Bật lại kiểm tra khóa ngoại */
SET FOREIGN_KEY_CHECKS = 1;