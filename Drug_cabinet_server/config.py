# config.py
# 域名配置
DOMAIN_NAME = "your-domain.com"

# MQTT (EMQX) 配置
#EMQX_BROKER_IP = "your-mqtt-server-ip"
EMQX_BROKER_IP = "8.134.109.28"  # 云服务器
#EMQX_BROKER_IP = DOMAIN_NAME  # 使用域名访问（ICP备案完成后启用）

EMQX_BROKER_PORT = 1883
EMQX_USERNAME = "your-mqtt-username"
EMQX_PASSWORD = "your-mqtt-password"
EMQX_CLIENT_ID = "server_windows"  # 不要相同，否则会报错

# Redis配置
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = None
REDIS_DB = 0
REDIS_DEFAULT_TTL = 3600  # 默认缓存过期时间（秒）

# 数据库配置
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "your-database-password"
MYSQL_DATABASE_1 = "web"
MYSQL_DATABASE_2 = "history"
MYSQL_TABLE_USER_1 = "web_user"


# 登录配置
MAX_LOGIN_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 30

# JWT配置
JWT_SECRET_KEY = 'your-jwt-secret-key-change-in-production'
JWT_EXPIRATION_HOURS = 24  # Token有效期（小时）

# EMQX 控制台配置
EMQX_DASHBOARD_USERNAME = "admin"
EMQX_DASHBOARD_PASSWORD = "your-emqx-dashboard-password"

# EMQX 5.x API配置
EMQX_API_KEY = "your-emqx-api-key"
EMQX_API_SECRET = "your-emqx-api-secret"
EMQX_API_BASE_URL = f"http://{EMQX_BROKER_IP}:18083/api/v5"

'''
CREATE TABLE `web_equipment` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `equipment_name` varchar(100) NOT NULL COMMENT '设备名称（中文显示用）',
  `equipment_id` varchar(100) NOT NULL COMMENT '设备ID（对应EMQX客户端ID）',
  `equipment_address` varchar(200) NOT NULL COMMENT '设备详细地址',
  `connection_status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '连接状态：0-在线，1-离线',
  `health_status` tinyint(1) NOT NULL DEFAULT '0' COMMENT '健康状态：0-正常，1-异常，2-报警',
  `door_status` tinyint(1) NOT NULL DEFAULT '0' COMMENT '门状态：0-关闭，1-开启',
  `lock_status` tinyint(1) NOT NULL DEFAULT '0' COMMENT '锁状态：0-锁定，1-解锁',
  `timeout` int unsigned NOT NULL DEFAULT '300' COMMENT '超时时间（秒）',
  `last_online` datetime DEFAULT NULL COMMENT '最后在线时间',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_equipment_id` (`equipment_id`),
  KEY `idx_last_online` (`last_online`),
  KEY `idx_door_lock` (`door_status`,`lock_status`),
  KEY `idx_health_status` (`health_status`),
  KEY `idx_connection_health` (`connection_status`,`health_status`),
  KEY `idx_status_query` (`connection_status`,`health_status`,`last_online`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Web端设备表';
'''


'''
CREATE TABLE `web_equipment_config` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `equipment_id` varchar(100) NOT NULL COMMENT '设备ID',
  `temp_NOR_min` decimal(5,2) NOT NULL DEFAULT '15.00' COMMENT '温度正常范围下限',
  `temp_NOR_max` decimal(5,2) NOT NULL DEFAULT '25.00' COMMENT '温度正常范围上限',
  `temp_ABN_min` decimal(5,2) NOT NULL DEFAULT '10.00' COMMENT '温度异常范围下限',
  `temp_ABN_max` decimal(5,2) NOT NULL DEFAULT '30.00' COMMENT '温度异常范围上限',
  `humi_NOR_min` decimal(5,2) NOT NULL DEFAULT '30.00' COMMENT '湿度正常范围下限',
  `humi_NOR_max` decimal(5,2) NOT NULL DEFAULT '60.00' COMMENT '湿度正常范围上限',
  `humi_ABN_min` decimal(5,2) NOT NULL DEFAULT '20.00' COMMENT '湿度异常范围下限',
  `humi_ABN_max` decimal(5,2) NOT NULL DEFAULT '70.00' COMMENT '湿度异常范围上限',
  `aqi_NOR_max` decimal(6,2) NOT NULL DEFAULT '100.00' COMMENT 'AQI正常范围上限',
  `aqi_ABN_max` decimal(6,2) NOT NULL DEFAULT '200.00' COMMENT 'AQI异常范围上限',
  `timeout_NOR` int NOT NULL DEFAULT '300' COMMENT '门开正常时间上限(秒)',
  `timeout_ABN` int NOT NULL DEFAULT '600' COMMENT '门开异常时间上限(秒)',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_equipment_id` (`equipment_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='设备配置表';
'''



'''
CREATE TABLE `web_user` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(100) NOT NULL COMMENT '登录用户名',
  `password` varchar(255) NOT NULL COMMENT '加密后的密码',
  `real_name` varchar(100) DEFAULT NULL COMMENT '真实姓名',
  `email` varchar(100) DEFAULT NULL,
  `role` tinyint(1) NOT NULL DEFAULT '2' COMMENT '角色：0-管理员，1-教师，2-学生',
  `status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '状态：0-禁用，1-启用',
  `rfid_card_id` varchar(100) DEFAULT NULL COMMENT '绑定的RFID卡号',
  `department` varchar(100) DEFAULT NULL COMMENT '所属部门',
  `phone` varchar(20) DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `login_attempts` tinyint(1) DEFAULT '0',
  `locked_until` datetime DEFAULT NULL,
  `created_by` int unsigned DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `rfid_card_id` (`rfid_card_id`)
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Web系统用户表';
'''


'''
CREATE TABLE `history_environment_data_cabinet_003` (
  `id` int NOT NULL AUTO_INCREMENT,
  `temperature` float NOT NULL COMMENT '温度',
  `humidity` float NOT NULL COMMENT '湿度',
  `aqi` int NOT NULL COMMENT '空气质量指数',
  `save_time` datetime NOT NULL COMMENT '保存时间',
  PRIMARY KEY (`id`),
  KEY `idx_save_time` (`save_time`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
'''

'''
CREATE TABLE `web_medicine_list` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `medicine_code` varchar(64) NOT NULL COMMENT '药品编码(RFID)',
  `name` varchar(100) NOT NULL COMMENT '药品名称',
  `type` enum('0','1','2') DEFAULT '0' COMMENT '药品类型: 0-普通药品, 1-危化品, 2-管制药品',
  `specification` varchar(100) DEFAULT NULL COMMENT '规格',
  `manufacturer` varchar(100) DEFAULT NULL COMMENT '生产厂商',
  `batch_number` varchar(50) DEFAULT NULL COMMENT '批号',
  `production_date` date DEFAULT NULL COMMENT '生产日期',
  `expiry_date` date DEFAULT NULL COMMENT '有效期',
  `storage_condition` varchar(100) DEFAULT NULL COMMENT '存储条件',
  `status` enum('in_stock','lent_out','discarded','reserved') DEFAULT 'in_stock' COMMENT '状态：in_stock-在库，lent_out-已借出，discarded-已废弃，reserved-已预定',
  `current_holder_id` varchar(50) DEFAULT NULL COMMENT '当前持有人ID',
  `location` varchar(50) DEFAULT NULL COMMENT '所在柜子',
  `unit` varchar(20) DEFAULT NULL COMMENT '单位',
  `last_operation_time` datetime DEFAULT NULL COMMENT '最后操作时间',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `medicine_code` (`medicine_code`),
  KEY `idx_status` (`status`),
  KEY `idx_location` (`location`),
  KEY `idx_expiry` (`expiry_date`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
'''



'''
CREATE TABLE `user_operations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `operation_time` datetime NOT NULL COMMENT '操作时间',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `operation_type` enum('access_granted','access_denied','remote_unlock','remote_lock','add_user','delete_user','update_user','add_medicine','update_medicine','delete_medicine','system_config') NOT NULL COMMENT '操作类型',
  `equipment_id` varchar(50) DEFAULT NULL COMMENT '相关设备ID',
  `target_id` varchar(100) DEFAULT NULL COMMENT '操作目标ID（用户ID/药品ID等）',
  `description` varchar(500) NOT NULL COMMENT '操作描述',
  `ip_address` varchar(45) DEFAULT NULL COMMENT '操作IP',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_operation_time` (`operation_time`),
  KEY `idx_user` (`user_id`),
  KEY `idx_operation_type` (`operation_type`),
  KEY `idx_equipment` (`equipment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户操作表';


CREATE TABLE `medicine_trace` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `operation_time` datetime NOT NULL COMMENT '操作时间',
  `equipment_id` varchar(50) NOT NULL COMMENT '设备ID',
  `rfid_card_id` varchar(64) NOT NULL COMMENT '用户卡号',
  `medicine_code` varchar(64) NOT NULL COMMENT '药品RFID',
  `operation_type` enum('borrow','return') NOT NULL COMMENT '操作类型',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_operation_time` (`operation_time`),
  KEY `idx_equipment` (`equipment_id`),
  KEY `idx_user` (`rfid_card_id`),
  KEY `idx_medicine` (`medicine_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='药品追溯表';
'''


'''
CREATE TABLE `web_medicine_reservation` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `drug_id` bigint NOT NULL COMMENT '药品ID',
  `rfid_card_id` varchar(100) NOT NULL COMMENT 'RFID卡号',
  `reservation_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '预定时间',
  `status` enum('pending','pending_approval','completed','cancelled') NOT NULL DEFAULT 'pending' COMMENT '预定状态：pending-待处理，pending_approval-待审核，completed-已完成，cancelled-已取消',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_drug_id` (`drug_id`),
  KEY `idx_rfid_card_id` (`rfid_card_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_reservation_drug` FOREIGN KEY (`drug_id`) REFERENCES `web_medicine_list` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_reservation_rfid` FOREIGN KEY (`rfid_card_id`) REFERENCES `web_user` (`rfid_card_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='药品预定表';
'''


'''
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
'''


'''
CREATE TABLE `web_alarm_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `equipment_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '设备ID',
  `alarm_category` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '报警分类(环境异常/环境报警/门锁异常/门锁报警)',
  `alarm_content` text COLLATE utf8mb4_unicode_ci COMMENT '报警内容',
  `temp` float DEFAULT NULL COMMENT '温度',
  `humi` float DEFAULT NULL COMMENT '湿度',
  `aqi` int DEFAULT NULL COMMENT '空气质量指数',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT '未处理' COMMENT '处理状态(未处理/已处理)',
  `handled_by` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '处理人RFID',
  `handle_result` text COLLATE utf8mb4_unicode_ci COMMENT '处理结果',
  `save_time` datetime NOT NULL COMMENT '报警时间',
  `handled_time` datetime DEFAULT NULL COMMENT '处理时间',
  PRIMARY KEY (`id`),
  KEY `idx_equipment_id` (`equipment_id`),
  KEY `idx_status` (`status`),
  KEY `idx_save_time` (`save_time`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
'''