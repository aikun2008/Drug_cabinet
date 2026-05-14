# Drug Cabinet 项目规则

## Git 工作流配置

### 分支策略
- **主分支**: `master` - 生产环境代码，只能由用户手动合并
- **开发分支**: `my-first-branch` - 所有新代码先推送到此分支
- **当前工作分支**: `my-first-branch`

### 推送规则
- 默认推送到当前分支: `git config push.default current`
- 所有代码变更先提交到 `my-first-branch`
- 禁止直接推送到 `master` 分支
- 由用户手动审查后合并到 `master`

### Git 用户信息
- 用户名: `aikun2008`
- 邮箱: `aikun2008@outlook.com`

### 提交规范
- 使用中文提交信息
- 格式: `<type>: <description>`
- 类型: `feat`, `fix`, `refactor`, `docs`, `security`, `test`

## 项目结构
- 后端: `Drug_cabinet_server/` (Flask + MySQL + Redis)
- 小程序: `Drug_cabinet_MP/` (WeChat Mini Program)
- 硬件: `ESP32WROOM/`, `drug/`

## 开发规范
- Python 代码使用卫语句优化嵌套 if
- 敏感配置使用环境变量（见 config.py）
- 使用清华镜像安装依赖: `-i https://pypi.tuna.tsinghua.edu.cn/simple`
