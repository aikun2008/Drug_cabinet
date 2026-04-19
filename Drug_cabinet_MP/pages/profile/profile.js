// profile.js
Page({
  data: {
    userInfo: {},
    roleText: '',
    roleIcon: '',
    roleColor: '',
    showLogoutModal: false,
    showStudentsModal: false,
    showStudentSelectModal: false,
    students: [],
    availableStudents: [],
    selectedStudentId: null,
    loading: false,
    error: ''
  },

  onShow() {
    const app = getApp()
    
    // 检查登录状态
    if (!app.globalData.isLoggedIn) {
      // 未登录，跳转到登录页面
      wx.redirectTo({
        url: '/pages/login/login'
      })
      return
    }
    
    this.setData({
      userInfo: app.globalData.userInfo
    })
    
    // 设置角色信息
    this.setRoleInfo()
  },

  setRoleInfo() {
    const app = getApp()
    const role = this.data.userInfo.role
    const roleConfig = app.globalData.roleConfig[role] || {
      name: '未知角色',
      color: '#999',
      icon: '❓'
    }
    
    this.setData({
      roleText: roleConfig.name,
      roleIcon: roleConfig.icon,
      roleColor: roleConfig.color
    })
  },

  navigateToChangePassword() {
    wx.showToast({
      title: '功能开发中',
      icon: 'none'
    })
  },

  showAbout() {
    wx.showModal({
      title: '关于系统',
      content: '药品柜管理系统 v1.0.0\n\n该系统用于管理药品柜的使用，包括药品信息管理、环境监测、使用记录查询等功能。',
      showCancel: false
    })
  },

  onLogout() {
    this.setData({
      showLogoutModal: true
    })
  },

  closeLogoutModal() {
    this.setData({
      showLogoutModal: false
    })
  },

  confirmLogout() {
    // 清除本地存储的token
    wx.removeStorageSync('token')
    
    // 更新全局登录状态
    const app = getApp()
    app.globalData.isLoggedIn = false
    app.globalData.userInfo = null
    
    // 跳转到登录页面
    wx.redirectTo({
      url: '/pages/login/login'
    })
  },

  stopPropagation() {
    // 阻止事件冒泡，防止点击弹窗内容关闭弹窗
  },

  // 显示学生管理模态框
  showStudentsModal() {
    this.setData({ showStudentsModal: true })
    this.loadStudents()
  },

  // 关闭学生管理模态框
  closeStudentsModal() {
    this.setData({ showStudentsModal: false })
  },

  // 加载学生列表
  loadStudents() {
    const app = getApp()
    const userId = this.data.userInfo.id

    this.setData({ loading: true, error: '' })

    wx.request({
      url: `${app.globalData.baseUrl}/teacher-student/students/${userId}`,
      method: 'GET',
      header: {
        'Authorization': `Bearer ${wx.getStorageSync('token')}`
      },
      success: (res) => {
        if (res.data.success) {
          this.setData({ students: res.data.data || [] })
        } else {
          this.setData({ error: res.data.message || '加载学生列表失败' })
        }
      },
      fail: (err) => {
        this.setData({ error: '网络错误，请稍后重试' })
        console.error('加载学生列表失败:', err)
      },
      complete: () => {
        this.setData({ loading: false })
      }
    })
  },

  // 绑定新学生
  bindStudent() {
    this.setData({ showStudentSelectModal: true })
    this.loadAvailableStudents()
  },

  // 关闭学生选择模态框
  closeStudentSelectModal() {
    this.setData({ 
      showStudentSelectModal: false,
      selectedStudentId: null 
    })
  },

  // 加载可绑定的学生列表
  loadAvailableStudents() {
    const app = getApp()
    const userId = this.data.userInfo.id

    this.setData({ loading: true, error: '' })

    wx.request({
      url: `${app.globalData.baseUrl}/teacher-student/available-students/${userId}`,
      method: 'GET',
      header: {
        'Authorization': `Bearer ${wx.getStorageSync('token')}`
      },
      success: (res) => {
        if (res.data.success) {
          this.setData({ availableStudents: res.data.data || [] })
        } else {
          this.setData({ error: res.data.message || '加载可绑定学生失败' })
        }
      },
      fail: (err) => {
        this.setData({ error: '网络错误，请稍后重试' })
        console.error('加载可绑定学生失败:', err)
      },
      complete: () => {
        this.setData({ loading: false })
      }
    })
  },

  // 选择学生
  selectStudent(e) {
    const studentId = e.currentTarget.dataset.id
    this.setData({ selectedStudentId: studentId })
  },

  // 确认绑定学生
  confirmBindStudent() {
    const selectedStudentId = this.data.selectedStudentId
    if (!selectedStudentId) {
      wx.showToast({
        title: '请选择一个学生',
        icon: 'none'
      })
      return
    }

    const app = getApp()

    wx.showModal({
      title: '确认绑定',
      content: '确定要绑定该学生吗？',
      success: (res) => {
        if (res.confirm) {
          wx.request({
            url: `${app.globalData.baseUrl}/teacher-student/bind`,
            method: 'POST',
            header: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            data: { teacher_id: this.data.userInfo.id, student_id: selectedStudentId },
            success: (res) => {
              if (res.data.success) {
                wx.showToast({ title: '绑定成功', icon: 'success' })
                this.closeStudentSelectModal()
                this.loadStudents() // 重新加载学生列表
              } else {
                wx.showToast({ title: res.data.message || '绑定失败', icon: 'none' })
              }
            },
            fail: (err) => {
              wx.showToast({ title: '网络错误，请稍后重试', icon: 'none' })
              console.error('绑定学生失败:', err)
            }
          })
        }
      }
    })
  },

  // 解绑学生
  unbindStudent(e) {
    const studentId = e.currentTarget.dataset.id
    const app = getApp()

    wx.showModal({
      title: '确认解绑',
      content: '确定要解绑该学生吗？',
      success: (res) => {
        if (res.confirm) {
          wx.request({
            url: `${app.globalData.baseUrl}/teacher-student/unbind`,
            method: 'POST',
            header: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            data: { student_id: studentId },
            success: (res) => {
              if (res.data.success) {
                wx.showToast({ title: '解绑成功', icon: 'success' })
                this.loadStudents() // 重新加载学生列表
              } else {
                wx.showToast({ title: res.data.message || '解绑失败', icon: 'none' })
              }
            },
            fail: (err) => {
              wx.showToast({ title: '网络错误，请稍后重试', icon: 'none' })
              console.error('解绑学生失败:', err)
            }
          })
        }
      }
    })
  },

  // 跳转到待借药品页面
  navigateToPendingDrugs() {
    wx.navigateTo({
      url: '/pages/pendingDrugs/pendingDrugs'
    })
  }
})