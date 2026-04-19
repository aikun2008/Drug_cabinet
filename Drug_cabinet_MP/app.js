// app.js
App({
  onLaunch() {
    // 检查是否有登录凭证
    const token = wx.getStorageSync('token')
    if (token) {
      // 有token，验证有效性
      this.checkTokenValidity(token)
    }
  },

  checkTokenValidity(token) {
    // 调用后端API验证token
    wx.request({
      url: `${this.globalData.baseUrl}/check_token`,
      method: 'GET',
      header: {
        'Authorization': `Bearer ${token}`
      },
      success: (res) => {
        if (res.data.success) {
          // token有效，更新用户信息
          this.globalData.userInfo = res.data.user_info
          this.globalData.isLoggedIn = true
        } else {
          // token无效，清除本地存储
          wx.removeStorageSync('token')
          this.globalData.isLoggedIn = false
          this.globalData.userInfo = null
        }
      },
      fail: () => {
        // 网络错误，默认未登录
        this.globalData.isLoggedIn = false
        this.globalData.userInfo = null
      }
    })
  },

  globalData: {
    isLoggedIn: false,
    userInfo: null,
    // 域名配置
    domainName: 'your-domain.com',
    // baseUrl 配置
    // 注意：微信小程序需要使用 HTTPS 域名并且已完成 ICP 备案
    // 本地开发时使用 IP，正式环境使用域名
    // baseUrl: 'http://localhost:5000/api',  // 本地开发
    // baseUrl: 'http://your-server-ip:5000/api',    // IP访问
    baseUrl: 'https://your-domain.com/api',           // 域名访问（启用HTTPS）
    // 角色配置
    roleConfig: {
      0: {
        name: '管理员',
        color: '#FF9800',
        icon: '👑'
      },
      1: {
        name: '教师',
        color: '#4CAF50',
        icon: '👨‍🏫'
      },
      2: {
        name: '学生',
        color: '#2196F3',
        icon: '👨‍🎓'
      }
    }
  }
})