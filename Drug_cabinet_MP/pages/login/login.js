// login.js
Page({
  data: {
    username: '',
    password: '',
    error: '',
    loading: false
  },

  onUsernameInput(e) {
    this.setData({
      username: e.detail.value
    })
  },

  onPasswordInput(e) {
    this.setData({
      password: e.detail.value
    })
  },

  onLogin() {
    const { username, password } = this.data
    
    // 表单验证
    if (!username || !password) {
      this.setData({
        error: '用户名和密码不能为空'
      })
      return
    }
    
    this.setData({
      loading: true,
      error: ''
    })
    
    const app = getApp()
    
    // 调用登录API
    wx.request({
      url: `${app.globalData.baseUrl}/login`,
      method: 'POST',
      data: {
        username,
        password
      },
      success: (res) => {
        if (res.data.success) {
          // 登录成功，保存token和用户信息
          wx.setStorageSync('token', res.data.token)
          app.globalData.isLoggedIn = true
          app.globalData.userInfo = res.data.data
          
          // 跳转到首页
          wx.switchTab({
            url: '/pages/index/index'
          })
        } else {
          // 登录失败，显示错误信息
          this.setData({
            error: res.data.message || '登录失败，请检查用户名和密码'
          })
        }
      },
      fail: () => {
        // 网络错误
        this.setData({
          error: '网络错误，请稍后重试'
        })
      },
      complete: () => {
        this.setData({
          loading: false
        })
      }
    })
  }
})