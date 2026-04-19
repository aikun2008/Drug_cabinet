CREATE TABLE `batch_import_record` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `import_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '导入时间',
  `file_name` varchar(255) NOT NULL COMMENT '导入的文件名',
  `total_count` int NOT NULL COMMENT '总记录数',
  `success_count` int NOT NULL COMMENT '成功导入的记录数',
  `error_count` int NOT NULL COMMENT '失败的记录数',
  `error_details` text COMMENT '错误详情（JSON格式）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_import_time` (`import_time`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='批量药品入库记录表';