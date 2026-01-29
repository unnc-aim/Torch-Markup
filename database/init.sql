-- Torch-Markup 数据库初始化脚本
-- MySQL 8.0+

CREATE DATABASE IF NOT EXISTS torch_markup DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE torch_markup;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB;

-- 数据集表
CREATE TABLE IF NOT EXISTS datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    image_path VARCHAR(500) NOT NULL COMMENT '图片目录路径',
    label_path VARCHAR(500) COMMENT '标签目录路径',
    total_images INT DEFAULT 0,
    labeled_images INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name)
) ENGINE=InnoDB;

-- 类别表
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    shortcut_key VARCHAR(10) COMMENT '快捷键',
    color VARCHAR(20) DEFAULT '#FF0000',
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    INDEX idx_dataset (dataset_id),
    UNIQUE KEY uk_dataset_name (dataset_id, name)
) ENGINE=InnoDB;

-- 图片表
CREATE TABLE IF NOT EXISTS images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    width INT,
    height INT,
    status ENUM('pending', 'assigned', 'labeled', 'skipped') DEFAULT 'pending',
    assigned_to INT,
    assigned_at TIMESTAMP NULL,
    labeled_by INT,
    labeled_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (labeled_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_dataset (dataset_id),
    INDEX idx_status (status),
    INDEX idx_assigned (assigned_to),
    UNIQUE KEY uk_dataset_filename (dataset_id, filename)
) ENGINE=InnoDB;

-- 标注表
CREATE TABLE IF NOT EXISTS annotations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_id INT NOT NULL,
    category_id INT NOT NULL,
    x_center FLOAT NOT NULL COMMENT 'YOLO格式 x中心点 (0-1)',
    y_center FLOAT NOT NULL COMMENT 'YOLO格式 y中心点 (0-1)',
    width FLOAT NOT NULL COMMENT 'YOLO格式 宽度 (0-1)',
    height FLOAT NOT NULL COMMENT 'YOLO格式 高度 (0-1)',
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_image (image_id),
    INDEX idx_category (category_id)
) ENGINE=InnoDB;

-- 标注历史表 (用于撤销/重做)
CREATE TABLE IF NOT EXISTS annotation_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_id INT NOT NULL,
    user_id INT NOT NULL,
    action ENUM('create', 'update', 'delete') NOT NULL,
    annotation_data JSON NOT NULL COMMENT '标注数据快照',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_image_user (image_id, user_id)
) ENGINE=InnoDB;

-- 工作量统计表
CREATE TABLE IF NOT EXISTS work_statistics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    dataset_id INT NOT NULL,
    date DATE NOT NULL,
    images_labeled INT DEFAULT 0,
    annotations_created INT DEFAULT 0,
    time_spent INT DEFAULT 0 COMMENT '花费时间(秒)',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_dataset_date (user_id, dataset_id, date),
    INDEX idx_date (date)
) ENGINE=InnoDB;

-- 插入默认管理员账户
-- 密码: 123456 (bcrypt哈希)
INSERT INTO users (username, email, hashed_password, is_admin, is_active)
VALUES ('admin', 'admin@torch-markup.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.6HJgjCQnAENUHi', TRUE, TRUE)
ON DUPLICATE KEY UPDATE username = username;
