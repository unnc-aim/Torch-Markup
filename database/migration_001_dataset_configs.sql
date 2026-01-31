-- Migration 001: 创建数据集配置表
-- 用于支持不同格式的数据集（YOLO、DJI ROCO 等）
USE torch_markup
CREATE TABLE IF NOT EXISTS dataset_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL UNIQUE,
    format_type ENUM('yolo', 'dji_roco') DEFAULT 'yolo' COMMENT '数据集格式类型',
    annotation_path VARCHAR(500) COMMENT '标注文件目录路径',
    source_width INT DEFAULT 1920 COMMENT '原始图片宽度',
    source_height INT DEFAULT 1080 COMMENT '原始图片高度',
    auto_import_annotations BOOLEAN DEFAULT TRUE COMMENT '是否自动导入标注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 添加索引
CREATE INDEX idx_dataset_configs_dataset_id ON dataset_configs(dataset_id);
