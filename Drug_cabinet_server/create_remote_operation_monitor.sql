-- 创建远程操作监控表
-- 用于记录远程开锁操作并监控超时

CREATE TABLE IF NOT EXISTS remote_operation_monitor (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    equipment_id VARCHAR(50) NOT NULL COMMENT '设备ID',
    operation_time DATETIME NOT NULL COMMENT '操作时间',
    operator_id INT NOT NULL COMMENT '操作员ID',
    status VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '状态：active-进行中, completed-已完成, timeout-已超时',
    timeout_seconds INT NOT NULL DEFAULT 60 COMMENT '超时时间（秒）',
    alarm_generated BOOLEAN DEFAULT FALSE COMMENT '是否已生成报警',
    completed_time DATETIME NULL COMMENT '完成时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_equipment_id (equipment_id),
    INDEX idx_status (status),
    INDEX idx_operation_time (operation_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='远程操作监控表';
