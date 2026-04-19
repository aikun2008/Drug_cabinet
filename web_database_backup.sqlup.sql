-- MySQL dump 10.13  Distrib 8.0.34, for Win64 (x86_64)
--
-- Host: localhost    Database: web
-- ------------------------------------------------------
-- Server version	8.0.34

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `batch_import_record`
--

DROP TABLE IF EXISTS `batch_import_record`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='批量药品入库记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `batch_import_record`
--

LOCK TABLES `batch_import_record` WRITE;
/*!40000 ALTER TABLE `batch_import_record` DISABLE KEYS */;
INSERT INTO `batch_import_record` VALUES (1,'2026-02-27 04:44:35','药品导入示例2_new.xlsx',5,5,0,NULL,'2026-02-26 20:44:35');
/*!40000 ALTER TABLE `batch_import_record` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `medicine_trace`
--

DROP TABLE IF EXISTS `medicine_trace`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `medicine_trace`
--

LOCK TABLES `medicine_trace` WRITE;
/*!40000 ALTER TABLE `medicine_trace` DISABLE KEYS */;
/*!40000 ALTER TABLE `medicine_trace` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `permission_groups`
--

DROP TABLE IF EXISTS `permission_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `permission_groups` (
  `id` int NOT NULL COMMENT '权限组ID',
  `name` varchar(50) NOT NULL COMMENT '权限组名称',
  `description` varchar(200) DEFAULT NULL COMMENT '权限组描述',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='权限组表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `permission_groups`
--

LOCK TABLES `permission_groups` WRITE;
/*!40000 ALTER TABLE `permission_groups` DISABLE KEYS */;
INSERT INTO `permission_groups` VALUES (0,'管理员','系统管理员，拥有所有权限','2026-03-14 04:38:59','2026-03-14 04:38:59'),(1,'教师','教师用户，拥有教学相关权限','2026-03-14 04:38:59','2026-03-14 04:38:59'),(2,'学生','学生用户，拥有学习相关权限','2026-03-14 04:38:59','2026-03-14 04:38:59');
/*!40000 ALTER TABLE `permission_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `permission_settings`
--

DROP TABLE IF EXISTS `permission_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `permission_settings` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `group_id` int NOT NULL COMMENT '权限组ID',
  `can_login` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否允许登录',
  `login_time_range` varchar(20) NOT NULL DEFAULT '00:00-23:59' COMMENT '登录时间范围',
  `can_query_drugs` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否允许查询药品',
  `can_book_drugs` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否允许预定药品',
  `can_borrow_return_drugs` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否允许借还药品',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_group_id` (`group_id`),
  CONSTRAINT `fk_permission_group` FOREIGN KEY (`group_id`) REFERENCES `permission_groups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='权限设置表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `permission_settings`
--

LOCK TABLES `permission_settings` WRITE;
/*!40000 ALTER TABLE `permission_settings` DISABLE KEYS */;
INSERT INTO `permission_settings` VALUES (1,0,1,'00:00-23:59',1,1,1,'2026-03-14 04:39:07','2026-03-14 04:39:07'),(2,1,0,'00:00-23:59',1,1,1,'2026-03-14 04:39:07','2026-03-14 04:46:29'),(3,2,1,'00:00-23:59',1,1,1,'2026-03-14 04:39:07','2026-03-14 04:39:07');
/*!40000 ALTER TABLE `permission_settings` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `remote_operation_monitor`
--

DROP TABLE IF EXISTS `remote_operation_monitor`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `remote_operation_monitor` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `equipment_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '设备ID',
  `operation_time` datetime NOT NULL COMMENT '操作时间',
  `operator_id` int NOT NULL COMMENT '操作员ID',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT '状态：active-进行中, completed-已完成, timeout-已超时',
  `timeout_seconds` int NOT NULL DEFAULT '60' COMMENT '超时时间（秒）',
  `alarm_generated` tinyint(1) DEFAULT '0' COMMENT '是否已生成报警',
  `completed_time` datetime DEFAULT NULL COMMENT '完成时间',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_equipment_id` (`equipment_id`),
  KEY `idx_status` (`status`),
  KEY `idx_operation_time` (`operation_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='远程操作监控表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `remote_operation_monitor`
--

LOCK TABLES `remote_operation_monitor` WRITE;
/*!40000 ALTER TABLE `remote_operation_monitor` DISABLE KEYS */;
/*!40000 ALTER TABLE `remote_operation_monitor` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `teacher_student_relationship`
--

DROP TABLE IF EXISTS `teacher_student_relationship`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `teacher_student_relationship` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `teacher_id` int unsigned NOT NULL COMMENT '教师ID',
  `student_id` int unsigned NOT NULL COMMENT '学生ID',
  `status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '状态: 0-解除, 1-正常',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_by` int unsigned DEFAULT NULL COMMENT '创建人',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_student` (`student_id`),
  KEY `idx_teacher` (`teacher_id`),
  KEY `idx_student` (`student_id`),
  CONSTRAINT `fk_relationship_student` FOREIGN KEY (`student_id`) REFERENCES `web_user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_relationship_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `web_user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='师生关系表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `teacher_student_relationship`
--

LOCK TABLES `teacher_student_relationship` WRITE;
/*!40000 ALTER TABLE `teacher_student_relationship` DISABLE KEYS */;
INSERT INTO `teacher_student_relationship` VALUES (1,7,8,1,'2026-03-14 04:29:16','2026-03-14 04:29:16',NULL),(2,7,9,1,'2026-03-14 04:29:16','2026-03-14 04:29:16',NULL);
/*!40000 ALTER TABLE `teacher_student_relationship` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_operations`
--

DROP TABLE IF EXISTS `user_operations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_operations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `operation_time` datetime NOT NULL COMMENT '操作时间',
  `rfid_card_id` varchar(64) NOT NULL COMMENT '用户RFID卡号',
  `operation_type` enum('access_granted','access_denied','remote_unlock','remote_lock','add_user','delete_user','update_user','add_medicine','update_medicine','delete_medicine','system_config') NOT NULL COMMENT '操作类型',
  `equipment_id` varchar(50) DEFAULT NULL COMMENT '相关设备ID',
  `target_id` varchar(100) DEFAULT NULL COMMENT '操作目标ID',
  `description` varchar(500) NOT NULL COMMENT '操作描述',
  `ip_address` varchar(45) DEFAULT NULL COMMENT '操作IP',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_operation_time` (`operation_time`),
  KEY `idx_rfid_card` (`rfid_card_id`),
  KEY `idx_operation_type` (`operation_type`),
  KEY `idx_equipment` (`equipment_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户操作表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_operations`
--

LOCK TABLES `user_operations` WRITE;
/*!40000 ALTER TABLE `user_operations` DISABLE KEYS */;
INSERT INTO `user_operations` VALUES (1,'2026-03-14 04:25:04','7CBE2006','access_granted','cabinet_003',NULL,'用户 admin 通过RFID卡访问设备 cabinet_003',NULL,'2026-03-13 20:25:04'),(2,'2026-03-14 04:25:14','7CBE2006','access_granted','cabinet_003',NULL,'用户 admin 结束了对设备 cabinet_003 的访问',NULL,'2026-03-13 20:25:14'),(3,'2026-03-14 04:25:17','71BEE15D','access_granted','cabinet_003',NULL,'用户 Einstein 通过RFID卡访问设备 cabinet_003',NULL,'2026-03-13 20:25:17');
/*!40000 ALTER TABLE `user_operations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `web_alarm_log`
--

DROP TABLE IF EXISTS `web_alarm_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `web_alarm_log`
--

LOCK TABLES `web_alarm_log` WRITE;
/*!40000 ALTER TABLE `web_alarm_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `web_alarm_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `web_equipment`
--

DROP TABLE IF EXISTS `web_equipment`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
  `firmware_version` varchar(20) DEFAULT NULL COMMENT '固件版本号',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_equipment_id` (`equipment_id`),
  KEY `idx_last_online` (`last_online`),
  KEY `idx_door_lock` (`door_status`,`lock_status`),
  KEY `idx_health_status` (`health_status`),
  KEY `idx_connection_health` (`connection_status`,`health_status`),
  KEY `idx_status_query` (`connection_status`,`health_status`,`last_online`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Web端设备表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `web_equipment`
--

LOCK TABLES `web_equipment` WRITE;
/*!40000 ALTER TABLE `web_equipment` DISABLE KEYS */;
INSERT INTO `web_equipment` VALUES (1,'危化品柜01','cabinet_001','化学实验楼A座3层301实验室',1,0,0,1,0,'2026-03-13 14:32:46','2025-11-11 04:06:24','2026-03-13 14:54:24','1.0.0'),(2,'普通药品柜02','cabinet_002','化学实验楼A座3层302实验室',1,0,0,0,0,'2026-03-13 22:39:29','2025-11-11 04:06:24','2026-03-13 23:10:09','1.1.1'),(3,'低温药品柜03','cabinet_003','生物实验楼B座2层208实验室',0,2,0,0,0,'2026-03-14 06:02:29','2025-11-11 04:06:24','2026-03-14 06:02:29','2.1.3'),(4,'仪器柜04','cabinet_004','物理实验楼C座1层105实验室',1,0,0,0,300,'2025-11-12 11:16:45','2025-11-11 04:06:24','2025-11-13 18:48:21',NULL),(5,'麻醉药品柜05','cabinet_005','医学实验楼D座4层415实验室',1,0,0,1,300,'2025-11-12 11:16:42','2025-11-11 04:06:24','2025-11-13 18:48:23',NULL),(6,'易燃品柜06','cabinet_006','化学实验楼A座1层109实验室',1,0,1,1,300,'2025-11-12 11:16:39','2025-11-11 04:06:24','2025-11-13 18:48:25',NULL),(7,'生物样本柜07','cabinet_007','生物实验楼B座2层210实验室',1,0,0,1,300,'2025-11-12 11:16:54','2025-11-11 04:06:24','2025-11-13 18:48:28',NULL),(8,'光学仪器柜08','cabinet_008','物理实验楼C座2层206实验室',1,0,1,0,300,'2025-11-12 11:16:24','2025-11-11 04:06:24','2025-11-13 18:48:32',NULL),(9,'急救药品柜09','cabinet_009','医学实验楼D座1层118实验室',1,0,1,0,2546,'2025-11-13 19:03:37','2025-11-11 04:06:24','2025-11-15 04:32:38',NULL),(10,'废弃回收柜10','cabinet_010','生物实验楼B座1层101回收站',1,0,1,1,60,'2025-11-16 19:49:01','2025-11-13 19:06:11','2025-11-16 20:06:38',NULL);
/*!40000 ALTER TABLE `web_equipment` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `web_equipment_config`
--

DROP TABLE IF EXISTS `web_equipment_config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='设备配置表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `web_equipment_config`
--

LOCK TABLES `web_equipment_config` WRITE;
/*!40000 ALTER TABLE `web_equipment_config` DISABLE KEYS */;
INSERT INTO `web_equipment_config` VALUES (1,'cabinet_001',20.00,25.00,15.00,27.00,30.00,60.00,20.00,70.00,998.00,999.00,999,1000,'2025-11-11 09:20:26','2026-03-14 04:20:49'),(2,'cabinet_003',2.00,900.00,33.00,0.00,2.00,900.00,1.00,991.00,800.00,900.00,900,901,'2025-11-11 09:20:26','2026-02-28 03:49:32'),(5,'cabinet_002',20.00,25.00,15.00,27.00,30.00,60.00,20.00,70.00,998.00,999.00,999,1000,'2025-11-11 15:06:12','2026-03-07 03:02:44'),(6,'cabinet_009',20.00,50.00,10.00,60.00,40.00,60.00,20.00,65.00,20.00,30.00,300,500,'2025-11-13 18:45:20','2025-11-13 18:45:51');
/*!40000 ALTER TABLE `web_equipment_config` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `web_medicine_list`
--

DROP TABLE IF EXISTS `web_medicine_list`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=45 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `web_medicine_list`
--

LOCK TABLES `web_medicine_list` WRITE;
/*!40000 ALTER TABLE `web_medicine_list` DISABLE KEYS */;
INSERT INTO `web_medicine_list` VALUES (1,'0ABABC02','无水乙醇','0','500ml/瓶','国药集团化学试剂有限公司','20240801','2024-08-01','2026-07-31','阴凉干燥，远离火源','in_stock',NULL,'cabinet_002','瓶','2026-03-13 03:15:22','2026-03-05 06:33:40'),(2,'RFID2409005','氯化钠','0','500g/瓶','Sigma-Aldrich','20240805','2024-08-05','2026-08-04','室温保存','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:42:55','2026-03-05 06:33:40'),(3,'0446F605','葡萄糖','0','250g/瓶','Sigma-Aldrich','20240901','2024-09-01','2026-08-31','室温干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-11 11:17:58','2026-03-05 06:33:40'),(4,'RFID2410002','琼脂粉','0','250g/瓶','OXOID','20240822','2024-08-22','2026-08-21','阴凉干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:42:48','2026-03-05 06:33:40'),(5,'RFID2410003','蛋白胨','0','250g/瓶','OXOID','20240815','2024-08-15','2026-08-14','阴凉干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:42:45','2026-03-05 06:33:40'),(6,'RFID2410004','酵母提取物','0','250g/瓶','OXOID','20240828','2024-08-28','2026-08-27','阴凉干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:42:41','2026-03-05 06:33:40'),(7,'RFID2411002','Tris-HCl缓冲液','0','500ml/瓶','北京索莱宝科技有限公司','20240912','2024-09-12','2026-12-17','室温保存','in_stock',NULL,'cabinet_002','瓶','2026-03-13 14:10:51','2026-03-05 06:33:40'),(8,'RFID2411003','酚酞指示剂','0','100ml/瓶','上海阿拉丁生化科技股份有限公司','20240925','2024-09-25','2026-08-12','阴凉干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:43:16','2026-03-05 06:33:40'),(9,'RFID2409002','丙酮','1','500ml/瓶','西陇科学股份有限公司','20240715','2024-07-15','2027-05-13','剧毒，阴凉通风，双人双锁','in_stock',NULL,'cabinet_006','瓶','2026-03-05 14:47:40','2026-03-05 06:33:40'),(10,'RFID2409003','盐酸','1','500ml/瓶','国药集团化学试剂有限公司','20240820','2024-08-20','2026-09-23','强腐蚀性，阴凉干燥，腐蚀品柜','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:43:30','2026-03-05 06:33:40'),(11,'RFID2409004','氢氧化钠','1','500g/瓶','上海阿拉丁生化科技股份有限公司','20240710','2024-07-10','2026-07-09','强腐蚀性，干燥密封','in_stock',NULL,'cabinet_001','瓶','2026-03-13 03:15:23','2026-03-05 06:33:40'),(12,'RFID2409006','硫酸','1','500ml/瓶','国药集团化学试剂有限公司','20240720','2024-07-20','2026-04-14','强腐蚀性，阴凉通风，腐蚀品柜','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:43:36','2026-03-05 06:33:40'),(13,'RFID2409007','甲醇','1','500ml/瓶','西陇科学股份有限公司','20240812','2024-08-12','2026-05-19','剧毒，阴凉通风，易燃品柜','in_stock',NULL,'cabinet_006','瓶','2026-03-05 14:48:06','2026-03-05 06:33:40'),(14,'RFID2409008','异丙醇','1','500ml/瓶','国药集团化学试剂有限公司','20240818','2024-08-18','2026-08-17','有毒，阴凉干燥','in_stock',NULL,'cabinet_006','瓶','2026-03-13 03:15:24','2026-03-05 06:33:40'),(15,'RFID2409009','乙酸乙酯','1','500ml/瓶','上海阿拉丁生化科技股份有限公司','20240725','2024-07-25','2026-06-24','有毒，阴凉通风，易燃品柜','in_stock',NULL,'cabinet_006','瓶','2026-03-05 14:48:16','2026-03-05 06:33:40'),(16,'RFID2409010','二氯甲烷','1','500ml/瓶','Sigma-Aldrich','20240815','2024-08-15','2026-07-21','剧毒，阴凉通风，有害品柜','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:44:00','2026-03-05 06:33:40'),(17,'RFID2411001','PBS缓冲液','1','500ml/瓶','HyClone','20240905','2024-09-05','2026-12-29','含叠氮钠，有毒，2-8℃冷藏','in_stock','','cabinet_003','瓶','2026-03-13 14:11:54','2026-03-05 06:33:40'),(18,'RFID2411004','甲基橙','1','25g/瓶','国药集团化学试剂有限公司','20240930','2024-09-30','2026-09-29','有毒，阴凉干燥','in_stock','','cabinet_001','瓶','2026-03-05 14:44:36','2026-03-05 06:33:40'),(19,'RFID2412001','过氧化氢','1','500ml/瓶','国药集团化学试剂有限公司','20241005','2024-10-05','2026-10-04','氧化剂，腐蚀性，阴凉避光','in_stock',NULL,'cabinet_001','瓶','2026-03-13 03:35:58','2026-03-05 06:33:40'),(20,'RFID2412002','甲醛溶液','1','500ml/瓶','西陇科学股份有限公司','20241010','2024-10-10','2028-10-09','剧毒，致癌物，阴凉通风，有毒品柜','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:44:47','2026-03-05 06:33:40'),(21,'RFID2422001','三氯甲烷','2','500ml/瓶','国药集团化学试剂有限公司','20241101','2024-11-01','2026-10-31','易制毒，剧毒，双人双锁，监控保存','in_stock','','cabinet_005','瓶','2026-03-13 14:11:48','2026-03-05 06:33:40'),(22,'RFID2422002','乙醚','2','500ml/瓶','西陇科学股份有限公司','20241105','2024-11-05','2026-11-04','易制毒，极易燃，双人双锁，防爆柜','in_stock',NULL,'cabinet_005','瓶','2026-03-13 02:59:39','2026-03-05 06:33:40'),(23,'RFID2509001','无水乙醇','0','500ml/瓶','国药集团化学试剂有限公司','20240801','2024-08-01','2026-07-31','阴凉干燥，远离火源','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:56:01','2026-03-05 06:54:30'),(24,'RFID2609005','氯化钠','0','500g/瓶','Sigma-Aldrich','20240805','2024-08-05','2026-08-04','室温保存','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:56:05','2026-03-05 06:54:30'),(25,'RFID2610001','葡萄糖','0','250g/瓶','Sigma-Aldrich','20240901','2024-09-01','2026-08-31','室温干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:56:08','2026-03-05 06:54:30'),(26,'RFID2610002','琼脂粉','0','250g/瓶','OXOID','20240822','2024-08-22','2026-08-21','阴凉干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:56:13','2026-03-05 06:54:30'),(27,'RFID2610003','蛋白胨','0','250g/瓶','OXOID','20240815','2024-08-15','2026-08-14','阴凉干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:56:16','2026-03-05 06:54:30'),(28,'RFID2610004','酵母提取物','0','250g/瓶','OXOID','20240828','2024-08-28','2026-08-27','阴凉干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:56:22','2026-03-05 06:54:30'),(29,'RFID2611002','Tris-HCl缓冲液','0','500ml/瓶','北京索莱宝科技有限公司','20240912','2024-09-12','2028-09-11','室温保存','in_stock',NULL,'cabinet_002','瓶','2026-03-13 14:10:47','2026-03-05 06:54:30'),(30,'RFID2611003','酚酞指示剂','0','100ml/瓶','上海阿拉丁生化科技股份有限公司','20240925','2024-09-25','2029-09-24','阴凉干燥','in_stock',NULL,'cabinet_002','瓶','2026-03-05 14:57:47','2026-03-05 06:54:30'),(31,'RFID2609002','丙酮','1','500ml/瓶','西陇科学股份有限公司','20240715','2024-07-15','2029-07-14','剧毒，易燃，阴凉通风，双人双锁','in_stock',NULL,'cabinet_006','瓶','2026-03-05 14:57:53','2026-03-05 06:54:30'),(32,'RFID2609003','盐酸','1','500ml/瓶','国药集团化学试剂有限公司','20240820','2024-08-20','2028-08-19','强腐蚀性，阴凉干燥，腐蚀品柜','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:58:02','2026-03-05 06:54:30'),(33,'RFID2609004','氢氧化钠','1','500g/瓶','上海阿拉丁生化科技股份有限公司','20240710','2024-07-10','2026-07-09','强腐蚀性，干燥密封','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:56:49','2026-03-05 06:54:30'),(34,'RFID2609006','硫酸','1','500ml/瓶','国药集团化学试剂有限公司','20240720','2024-07-20','2026-03-13','强腐蚀性，阴凉通风，腐蚀品柜','in_stock',NULL,'cabinet_001','瓶','2026-03-13 11:36:12','2026-03-05 06:54:30'),(35,'RFID2609007','甲醇','1','500ml/瓶','西陇科学股份有限公司','20240812','2024-08-12','2026-03-13','剧毒，易燃，阴凉通风','in_stock',NULL,'cabinet_006','瓶','2026-03-13 11:36:08','2026-03-05 06:54:30'),(36,'RFID2609008','异丙醇','1','500ml/瓶','国药集团化学试剂有限公司','20240818','2024-08-18','2026-08-17','有毒，易燃','in_stock',NULL,'cabinet_006','瓶','2026-03-05 14:57:25','2026-03-05 06:54:30'),(37,'RFID2609009','乙酸乙酯','1','500ml/瓶','上海阿拉丁生化科技股份有限公司','20240725','2024-07-25','2026-06-17','有毒，易燃','in_stock',NULL,'cabinet_006','瓶','2026-03-13 12:03:16','2026-03-05 06:54:30'),(38,'RFID2609010','二氯甲烷','1','500ml/瓶','Sigma-Aldrich','20240815','2024-08-15','2026-05-21','剧毒，阴凉通风','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:59:28','2026-03-05 06:54:30'),(39,'RFID2611001','PBS缓冲液','1','500ml/瓶','HyClone','20240905','2024-09-05','2026-04-06','含叠氮钠，有毒，2-8℃冷藏','in_stock',NULL,'cabinet_003','瓶','2026-03-13 14:09:22','2026-03-05 06:54:30'),(40,'RFID2611004','甲基橙','1','25g/瓶','国药集团化学试剂有限公司','20240930','2024-09-30','2026-04-16','有毒，阴凉干燥','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:59:05','2026-03-05 06:54:30'),(41,'RFID2612001','过氧化氢','1','500ml/瓶','国药集团化学试剂有限公司','20241005','2024-10-05','2026-03-31','氧化剂，腐蚀性，阴凉避光','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:58:52','2026-03-05 06:54:30'),(42,'RFID2612002','甲醛溶液','1','500ml/瓶','西陇科学股份有限公司','20241010','2024-10-10','2026-05-22','剧毒，致癌物，阴凉通风','in_stock',NULL,'cabinet_001','瓶','2026-03-05 14:58:44','2026-03-05 06:54:30'),(43,'RFID2622001','三氯甲烷','2','500ml/瓶','国药集团化学试剂有限公司','20241101','2024-11-01','2026-07-30','易制毒，剧毒，双人双锁，监控保存','in_stock','','cabinet_005','瓶','2026-03-13 14:13:52','2026-03-05 06:54:30'),(44,'RFID2622002','乙醚','2','500ml/瓶','西陇科学股份有限公司','20241105','2024-11-05','2026-06-11','易制毒，极易燃，双人双锁，防爆','in_stock',NULL,'cabinet_005','瓶','2026-03-13 11:36:35','2026-03-05 06:54:30');
/*!40000 ALTER TABLE `web_medicine_list` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `web_medicine_reservation`
--

DROP TABLE IF EXISTS `web_medicine_reservation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='药品预定表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `web_medicine_reservation`
--

LOCK TABLES `web_medicine_reservation` WRITE;
/*!40000 ALTER TABLE `web_medicine_reservation` DISABLE KEYS */;
/*!40000 ALTER TABLE `web_medicine_reservation` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `web_user`
--

DROP TABLE IF EXISTS `web_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `web_user`
--

LOCK TABLES `web_user` WRITE;
/*!40000 ALTER TABLE `web_user` DISABLE KEYS */;
INSERT INTO `web_user` VALUES (1,'admin','admin','超级管理员',NULL,0,1,'7CBE2006','系统管理部',NULL,'2026-03-14 04:46:24',0,NULL,NULL,'2025-11-08 03:28:06','2026-03-14 04:46:24'),(7,'teacher','00000','小明',NULL,1,1,'31FA8105','行政部',NULL,'2026-03-14 04:30:19',0,NULL,NULL,'2025-11-08 07:55:38','2026-03-14 04:30:18'),(8,'student','00000','小红',NULL,2,1,'71BEE15D','化学系',NULL,'2026-03-13 14:14:05',0,NULL,NULL,'2025-11-08 07:55:48','2026-03-14 04:28:13'),(9,'0000002','00000','小王',NULL,2,1,'6RDV2352','中药系',NULL,'2026-03-13 14:10:32',0,NULL,NULL,'2025-11-08 07:55:58','2026-03-14 04:28:24'),(10,'0000003','00000','示例用户0000003',NULL,2,1,'YEBE8306',NULL,NULL,NULL,0,NULL,NULL,'2025-11-08 07:56:26','2026-02-25 02:35:49'),(11,'0000004','00000','示例用户0000004',NULL,2,1,NULL,NULL,NULL,NULL,0,NULL,NULL,'2025-11-08 07:56:34','2026-02-25 02:35:54'),(12,'0000005','00000','示例用户0000005',NULL,2,0,NULL,NULL,NULL,NULL,0,NULL,NULL,'2025-11-08 07:56:44','2025-11-09 12:11:13'),(19,'0000006','00000','示例用户0000006',NULL,2,1,'71BEE152','行政部',NULL,'2026-03-13 03:01:09',0,NULL,NULL,'2025-11-09 03:30:40','2026-03-14 04:29:04');
/*!40000 ALTER TABLE `web_user` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-03-14  6:20:46
