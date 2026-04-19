// index.js
Page({
  data: {
    userInfo: {},
    roleText: '',
    roleIcon: '',
    roleColor: '',
    records: [],
    lastUpdateTime: null,
    // 弹窗状态
    showApplyModal: false,
    showBorrowModal: false,
    showReturnModal: false
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
    
    // 加载数据
    this.loadRecentRecords()
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

  loadRecentRecords() {
    const app = getApp()
    
    const requestData = {
      limit: 5
    }
    
    if (this.data.lastUpdateTime) {
      requestData.last_update = this.data.lastUpdateTime
    }
    
    wx.request({
      url: `${app.globalData.baseUrl}/recent_records`,
      method: 'GET',
      data: requestData,
      header: {
        'Authorization': `Bearer ${wx.getStorageSync('token')}`
      },
      success: (res) => {
        if (res.data.success) {
          if (res.data.data && res.data.data.updated) {
            // 增量更新
            this.setData({
              records: res.data.data.records,
              lastUpdateTime: res.data.data.timestamp
            })
          } else {
            // 全量更新
            this.setData({
              records: res.data.data,
              lastUpdateTime: new Date().toISOString()
            })
          }
        }
      },
      fail: () => {
        wx.showToast({
          title: '加载失败',
          icon: 'error'
        })
      }
    })
  },

  // 学生功能弹窗
  showApplyModal() {
    this.setData({
      showApplyModal: true
    })
  },

  closeApplyModal() {
    this.setData({
      showApplyModal: false
    })
  },

  showBorrowModal() {
    this.setData({
      showBorrowModal: true
    })
  },

  closeBorrowModal() {
    this.setData({
      showBorrowModal: false
    })
  },

  showReturnModal() {
    this.setData({
      showReturnModal: true
    })
  },

  closeReturnModal() {
    this.setData({
      showReturnModal: false
    })
  },

  // 教师功能弹窗
  showApproveModal() {
    wx.navigateTo({
      url: '/pages/approveApplication/approveApplication'
    })
  },

  showStudentRecordsModal() {
    wx.showToast({
      title: '学生记录功能开发中',
      icon: 'none'
    })
  },

  showDrugManageModal() {
    wx.switchTab({
      url: '/pages/drugRecords/drugRecords'
    })
  },

  // 管理员功能弹窗
  showUserManageModal() {
    wx.showToast({
      title: '用户管理功能开发中',
      icon: 'none'
    })
  },

  showEquipManageModal() {
    wx.showToast({
      title: '设备管理功能开发中',
      icon: 'none'
    })
  },

  showSystemManageModal() {
    wx.showToast({
      title: '系统管理功能开发中',
      icon: 'none'
    })
  },

  // 阻止事件冒泡
  stopPropagation() {
    // 阻止事件冒泡，防止点击弹窗内容关闭弹窗
  },

  // 页面跳转
  navigateToDrugInfo() {
    wx.switchTab({
      url: '/pages/drugInfo/drugInfo'
    })
  },

  // 跳转到待借药品页面
  navigateToPendingDrugs() {
    wx.navigateTo({
      url: '/pages/pendingDrugs/pendingDrugs'
    })
  },

  // 跳转到申请查询页面
  navigateToApplicationQuery() {
    wx.navigateTo({
      url: '/pages/applicationQuery/applicationQuery'
    })
  },

  // 下拉刷新
  onPullDownRefresh() {
    // 重新加载最近操作记录
    this.loadRecentRecords()
    
    // 模拟网络请求延迟，然后停止刷新
    setTimeout(() => {
      wx.stopPullDownRefresh()
      wx.showToast({
        title: '刷新成功',
        icon: 'success',
        duration: 1000
      })
    }, 1000)
  }

})