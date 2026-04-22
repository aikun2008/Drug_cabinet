---
name: "drug-cabinet-project-docs"
description: "Provides comprehensive documentation for the drug cabinet management system project. Invoke when users need project architecture, implementation details, troubleshooting guides, or development history."
---

# 药品柜管理系统项目文档

## 项目概述

这是一个完整的药品柜管理系统，包含以下组件：
- **Web 管理端**：Flask 后端 + HTML/CSS/JavaScript 前端
- **设备端**：ESP32 + STM32 双控制器
- **MQTT 中间件**：EMQX 5.x
- **数据库**：MySQL + Redis 缓存
- **小程序端**：微信小程序

## 已实现功能清单

### 1. 用户认证系统
- ✅ 登录/退出功能
- ✅ 密码加密存储（bcrypt）
- ✅ 权限管理装饰器（permission_required）
- ✅ 支持 Web 端 session 和小程序端 Bearer token 双认证

### 2. 管理员功能
#### 用户管理
- ✅ 用户档案管理（admin_user_profile.py）
- ✅ 用户配置管理（admin_user_config.py）
- ✅ 用户操作日志（admin_user_log.py）
- ✅ 用户组配置
- ✅ 学生 - 导师绑定关系

#### 设备管理
- ✅ 设备监控界面（admin_equip_montior.py）
- ✅ 设备配置管理（admin_equip_config.py）
- ✅ 设备 OTA 升级（admin_equip_ota.py）
- ✅ 设备在线状态实时更新（EMQX Webhook）
- ✅ 设备远程控制（开锁/上锁）
- ✅ 设备实时数据查询（温湿度、门锁状态）

#### 药品管理
- ✅ 药品目录管理（admin_drug_catalogue.py）
- ✅ 药品入库/出库（admin_drug_input_output.py）
- ✅ 药品操作日志（admin_drug_log.py）
- ✅ 药品追溯功能
- ✅ 药品审批流程

#### 环境监控
- ✅ 环境数据日志（admin_env_log.py）
- ✅ 温湿度趋势图（Chart.js 三轴显示）
- ✅ 智能数据采样算法
- ✅ 动态时间格式化

#### 报警管理
- ✅ 报警日志管理（admin_alarm_log.py）
- ✅ 远程操作超时报警
- ✅ 设备异常报警
- ✅ LED 状态指示（黄灯异常、红灯报警）

#### 仪表盘
- ✅ 综合数据展示（admin_dashboard.py）
- ✅ 在线设备统计
- ✅ 药品统计
- ✅ 报警统计
- ✅ 用户统计
- ✅ 最新消息通知

### 3. 教师端功能（teacher_drug_*.py）
- ✅ 药品查询
- ✅ 药品预定/取消预定
- ✅ 学生绑定/解绑
- ✅ 带教学生管理
- ✅ 药品使用审批

### 4. 学生端功能（student_drug_*.py）
- ✅ 个人信息管理
- ✅ 药品查询和浏览
- ✅ 药品预定申请
- ✅ 预定状态查询
- ✅ 药品使用记录查看

### 5. 小程序端功能
- ✅ API 端点支持 Bearer token 认证
- ✅ 药品浏览
- ✅ 预定功能
- ✅ 个人中心

## 技术架构

### 后端技术栈
```
Flask 3.1.2
MySQL (数据库)
Redis (缓存)
EMQX 5.x (MQTT Broker)
bcrypt (密码加密)
pandas (数据处理)
paho-mqtt (MQTT 客户端)
```

### 前端技术栈
```
HTML/CSS/JavaScript
Chart.js (数据可视化)
Bootstrap (UI 框架)
```

### 设备端技术
```
ESP32 (WiFi + MQTT)
STM32 (控制 LED、蜂鸣器)
FreeRTOS (实时操作系统)
```

## 核心模块说明

### 1. EMQX 管理器（emqx_manager.py）
**功能**：
- MQTT 连接管理
- 设备状态实时更新（Webhook）
- 消息发布/订阅
- 主题管理

**关键主题**：
```python
/server/command/esp32          # 服务器→设备命令
/esp32/environment_data/server # 环境数据
/esp32/heartbeat/server        # 心跳数据
/esp32/alarm_data/server       # 报警数据
```

### 2. Redis 缓存管理器（redis_manager.py）
**功能**：
- 数据库查询结果缓存
- 设备实时数据缓存
- 自定义 JSON 编码器（处理 datetime 序列化）
- 缓存同步机制

**缓存策略**：
- 减少重复数据库查询
- 提高 Web 响应效率
- 支持缓存失效自动刷新

### 3. 权限管理器（permission_manager.py）
**功能**：
- 用户权限验证
- 支持多种认证方式：
  - Web 端：session 认证
  - 小程序端：Bearer token 认证
  - 备用方案：请求参数认证

**使用示例**：
```python
@app.route('/api/endpoint')
@login_required
@permission_required('admin')
def endpoint():
    pass
```

### 4. 数据库缓存同步（db_cache_sync.py）
**功能**：
- 数据库操作与 Redis 缓存同步
- 缓存失效管理
- 事务处理

### 5. 报警处理器（alarm_handler.py）
**功能**：
- 自动检测异常情况
- 生成报警记录
- 推送报警通知到设备
- 远程操作超时监控

## 设备通信协议

### 心跳机制
- **方向**：设备 → 服务器
- **间隔**：20 秒（HEARTBEAT_INTERVAL_SECONDS）
- **格式**：
```json
{
  "equipment_id": "cabinet_002",
  "timestamp": 1234567890
}
```

### 健康状态指令
- **方向**：ESP32 → STM32（串口通信）
- **指令**：
  - 'N' - 正常（关闭所有 LED）
  - 'Y' - 异常（黄灯闪烁）
  - 'R' - 报警（红灯闪烁 + 蜂鸣器）

### 网络状态指令
- **方向**：ESP32 → STM32
- **指令**：
  - 'C' - MQTT 已连接（蓝灯常亮）
  - 'D' - 有网络但 MQTT 未连接（蓝灯慢闪）
  - 'O' - 无网络（蓝灯熄灭）

## 常见问题与解决方案

### 1. 数据格式不一致问题
**问题**：前端期望字段名与实际后端字段名不一致

**解决方案**：
```python
# 在 admin_equip_montior.py 中添加字段映射
frontend_data = {
    'temp': backend_data.get('temperature', '').replace('°C', ''),
    'humi': backend_data.get('humidity', '').replace('%', ''),
    'door': 1 if backend_data.get('door_status') == '开启' else 0,
}
```

### 2. EMQX Webhook 格式问题
**问题**：EMQX 发送的 event 使用点号（client.connected），代码期望下划线

**解决方案**：
```python
# 格式转换
event = event.replace('.', '_')
```

### 3. Redis 序列化问题
**问题**：datetime 对象无法 JSON 序列化

**解决方案**：
```python
# 在 redis_manager.py 中添加自定义编码器
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)
```

### 4. OTA 升级问题
**常见问题**：
1. 固件 URL 格式错误（包含引号）
2. 分区表缺少 otadata 分区
3. 重复写入导致分区空间不足
4. MIME 类型不正确

**解决方案**：
- 添加 URL 清理逻辑
- 配置正确的分区表
- 禁用 HTTP 事件处理避免重复写入
- 设置正确的 MIME 类型：`application/octet-stream`

### 5. MySQL 服务未启动
**解决方案**：
```python
# 实现自动检查和启动
import subprocess
try:
    subprocess.run(['net', 'start', 'MySQL'], check=True)
except subprocess.CalledProcessError:
    print("MySQL 服务启动失败")
```

### 6. 小程序认证问题
**问题**：permission_required 装饰器不支持小程序 token

**解决方案**：
```python
# 修改装饰器支持多种认证来源
def get_user_id():
    # 1. 从 session 获取（Web 端）
    if 'user_id' in session:
        return session['user_id']
    # 2. 从 Authorization 头获取（小程序端）
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]
        return verify_token(token)
    # 3. 从请求参数获取（备用）
    return request.args.get('user_id')
```

## 部署配置

### 服务器端口
- **5000**: Flask Web 服务
- **1883**: MQTT 连接
- **18083**: EMQX 管理控制台
- **3306**: MySQL 数据库

### 云服务器配置
- 开放必要端口（安全组）
- 配置 HTTPS 证书（正式环境）
- 配置 Redis 缓存
- 配置域名（需 ICP 备案）

### 虚拟环境管理
**Windows**:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**Ubuntu**:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 开发最佳实践

### 1. 代码规范
- 使用 bcrypt 加密密码
- 实现错误处理和边界情况处理
- 添加详细的调试日志
- 移除不必要的调试信息

### 2. 性能优化
- 使用 Redis 缓存减少数据库查询
- 实现智能数据采样算法
- 优化前端数据加载
- 添加加载状态管理

### 3. 用户体验
- 添加旋转动画和加载提示
- 响应式设计适配不同屏幕
- 平滑过渡避免界面闪烁
- 自动查询减少用户操作

### 4. 系统稳定性
- 实现 MQTT 重连机制
- 添加心跳检测
- 实现超时监控
- 记录详细操作日志

## 编码准则（Karpathy Guidelines）

### 1. 编码前思考（Think Before Coding）
- **不要假设**：明确陈述你的假设，如有不确定，询问确认
- **不隐藏困惑**：如果存在多种解释，应呈现出来，不要默默选择
- **权衡取舍**：如果存在更简单的方法，应指出并在必要时提出反对
- **及时暂停**：如果有不清楚的地方，停止并说明困惑之处

### 2. 简单优先（Simplicity First）
- **最小化代码**：只编写解决问题所需的最少代码，不添加推测性内容
- **避免过度抽象**：单一使用的代码不需要抽象层
- **拒绝不必要的灵活性**：不添加未请求的"灵活性"或"可配置性"
- **合理的错误处理**：不为不可能的场景添加错误处理
- **代码审查**：如果写了200行代码但本可以用50行完成，应重写

### 3. 精确修改（Surgical Changes）
- **最小改动**：只修改必须修改的部分，不"改进"相邻代码
- **不重构正常代码**：不重构未损坏的代码
- **风格一致**：匹配现有代码风格，即使你有不同偏好
- **谨慎删除**：注意到不相关的死代码时，只提及不删除
- **清理自己的代码**：移除因你的更改而变得未使用的导入/变量/函数
- **验证标准**：每一行修改都应直接追溯到用户的需求

### 4. 目标驱动执行（Goal-Driven Execution）
- **定义可验证的成功标准**：
  - "添加验证" → "为无效输入编写测试，然后使其通过"
  - "修复bug" → "编写重现bug的测试，然后使其通过"
  - "重构X" → "确保重构前后测试都通过"

- **多步骤任务规划**：
```
1. [步骤] → 验证: [检查点]
2. [步骤] → 验证: [检查点]
3. [步骤] → 验证: [检查点]
```

**权衡说明**：这些准则偏向谨慎而非速度。对于简单任务，使用判断力决定是否严格遵循。

## 改进点（待实现）

- [ ] HTTPS 配置
- [ ] 用户表细分（学生、教师、管理员）
- [ ] 学生新增带教老师功能
- [ ] 药品柜新增回收柜类型
- [ ] 库存预警功能
- [ ] 更多数据可视化图表

## 项目文件结构

```
Drug_cabinet_server/
├── main.py                      # 主程序入口
├── config.py                    # 配置文件
├── emqx_manager.py              # EMQX 管理器
├── redis_manager.py             # Redis 管理器
├── permission_manager.py        # 权限管理器
├── db_cache_sync.py             # 数据库缓存同步
├── alarm_handler.py             # 报警处理器
├── login.py                     # 登录认证
├── admin_*.py                   # 管理员功能模块
├── teacher_*.py                 # 教师端功能模块
├── student_*.py                 # 学生端功能模块
├── templates/                   # HTML 模板
├── static/                      # 静态资源
└── requirements.txt             # 依赖包列表
```

## 使用指南

### 启动服务器
```bash
# 激活虚拟环境
venv\Scripts\activate

# 启动主程序
python main.py
```

### 查看设备状态
访问：`http://localhost:5000/admin/device-monitoring`

### 配置 EMQX Webhook
1. 登录 EMQX 管理控制台（http://服务器 IP:18083）
2. 进入"集成" → "Webhook"
3. 创建新 Webhook，URL 指向：`http://服务器 IP:5000/api/emqx/webhook`
4. 选择事件：client.connected, client.disconnected

### OTA 升级流程
1. 在设备管理界面选择设备
2. 上传新固件文件
3. 系统自动生成固件 URL
4. 设备收到升级命令后下载固件
5. 设备自动重启并切换到新固件

## 故障排查

### 设备离线
1. 检查 MQTT 连接状态
2. 检查设备网络连接
3. 查看 EMQX 日志
4. 检查设备心跳是否正常

### 数据不更新
1. 检查 Redis 缓存是否失效
2. 检查前端字段映射是否正确
3. 查看浏览器控制台错误
4. 检查后端 API 响应格式

### OTA 失败
1. 检查固件 URL 是否可访问
2. 检查分区表配置
3. 查看 ESP32 串口日志
4. 检查固件大小是否超过分区限制

## 参考资料

- [Flask 官方文档](https://flask.palletsprojects.com/)
- [EMQX 文档](https://docs.emqx.com/zh/emqx/v5.4/)
- [ESP32 OTA 指南](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/ota.html)
- [Chart.js 文档](https://www.chartjs.org/docs/latest/)
