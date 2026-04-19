// drugRecords.js
Page({
  data: {
    records: [],
    filteredRecords: [],
    activeTab: 'reserved',
    loading: false,
    page: 1,
    hasMore: true
  },

  onLoad() {
    const app = getApp()
    
    // 检查登录状态
    if (!app.globalData.isLoggedIn) {
      // 未登录，跳转到登录页面
      wx.redirectTo({
        url: '/pages/login/login'
      })
      return
    }
    
    // 初始化数据
    this.setData({
      records: [],
      page: 1,
      hasMore: true
    })
    
    // 加载药品记录
    this.loadDrugRecords()
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
    
    // 初始化数据
    this.setData({
      records: [],
      page: 1,
      hasMore: true
    })
    
    // 加载药品记录
    this.loadDrugRecords()
  },
  
  // 导航到首页
  navigateToHome() {
    wx.switchTab({
      url: '/pages/index/index'
    })
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({
      activeTab: tab,
      records: [],
      page: 1,
      hasMore: true
    })
    
    // 加载药品记录
    this.loadDrugRecords()
  },

  loadDrugRecords() {
    const app = getApp()
    const userId = app.globalData.userInfo.id
    const userRole = app.globalData.userInfo.role
    const { activeTab, page } = this.data

    // 如果已经没有更多数据，不再加载
    if (!this.data.hasMore) return

    this.setData({
      loading: true
    })
    
    // 根据标签加载不同类型的记录
    if (activeTab === 'reserved' || activeTab === 'lent') {
      // 加载已预定或已借出记录
      this.loadStatusRecords(activeTab)
    } else if (activeTab === 'returned') {
      // 确定操作类型
      let operationType = 'return'
      
      // 根据用户角色选择API端点
      let apiUrl = ''
      if (userRole === 1) {
        // 教师
        apiUrl = `${app.globalData.baseUrl}/teacher/drugs/borrow-return-records`
      } else if (userRole === 2) {
        // 学生
        apiUrl = `${app.globalData.baseUrl}/student/drugs/borrow-return-records`
      }
      
      wx.request({
        url: apiUrl,
        method: 'GET',
        data: {
          user_id: userId,
          type: operationType,
          page: page,
          limit: 5
        },
        header: {
          'Authorization': `Bearer ${wx.getStorageSync('token')}`
        },
        success: (res) => {
          if (res.data.success) {
            const newRecords = res.data.data
            const updatedRecords = [...this.data.records, ...newRecords]
            
            this.setData({
              records: updatedRecords,
              hasMore: res.data.has_more,
              page: page + 1,
              filteredRecords: updatedRecords
            })
          }
        },
        fail: () => {
          wx.showToast({
            title: '加载失败',
            icon: 'error'
          })
        },
        complete: () => {
          this.setData({
            loading: false
          })
        }
      })
    }
  },

  // 加载状态记录（已预定或已借出）
  loadStatusRecords(tab) {
    const app = getApp()
    const userId = app.globalData.userInfo.id
    const userRole = app.globalData.userInfo.role

    // 根据用户角色选择API端点
    let apiUrl = ''
    if (userRole === 1) {
      // 教师
      apiUrl = `${app.globalData.baseUrl}/teacher/drugs/records`
    } else if (userRole === 2) {
      // 学生
      apiUrl = `${app.globalData.baseUrl}/student/drugs/records`
    }

    wx.request({
      url: apiUrl,
      method: 'GET',
      data: {
        user_id: userId
      },
      header: {
        'Authorization': `Bearer ${wx.getStorageSync('token')}`
      },
      success: (res) => {
        if (res.data.success) {
          let filteredRecords = []
          if (tab === 'reserved') {
            // 已预定记录
            filteredRecords = res.data.data.filter(record => record.status === 'reserved')
          } else if (tab === 'lent') {
            // 已借出记录
            filteredRecords = res.data.data.filter(record => record.status === 'lent_out')
          }
          
          this.setData({
            records: filteredRecords,
            filteredRecords: filteredRecords,
            hasMore: false
          })
        }
      },
      fail: () => {
        wx.showToast({
          title: '加载失败',
          icon: 'error'
        })
      },
      complete: () => {
        this.setData({
          loading: false
        })
      }
    })
  },

  // 加载已预定记录（保留旧函数以保持兼容性）
  loadReservedRecords() {
    this.loadStatusRecords('reserved')
  },

  // 下拉刷新
  onPullDownRefresh() {
    this.setData({
      records: [],
      page: 1,
      hasMore: true
    })
    this.loadDrugRecords()
    wx.stopPullDownRefresh()
  },

  // 上拉加载
  onReachBottom() {
    if (!this.data.loading && this.data.hasMore) {
      this.loadDrugRecords()
    }
  },

  // 跳转到待借药品页面
  navigateToPendingDrugs() {
    wx.navigateTo({
      url: '/pages/pendingDrugs/pendingDrugs'
    })
  },

  // 取消预定
  cancelReserve(e) {
    const drugId = e.currentTarget.dataset.drugId
    const app = getApp()
    const userId = app.globalData.userInfo.id
    const userRole = app.globalData.userInfo.role

    wx.showModal({
      title: '确认取消',
      content: '确定要取消预定该药品吗？',
      success: (res) => {
        if (res.confirm) {
          // 根据用户角色选择API端点
          let apiUrl = ''
          if (userRole === 1) {
            // 教师
            apiUrl = `${app.globalData.baseUrl}/teacher/drugs/cancel-reserve`
          } else if (userRole === 2) {
            // 学生
            apiUrl = `${app.globalData.baseUrl}/student/drugs/cancel-reserve`
          }
          
          wx.request({
            url: apiUrl,
            method: 'POST',
            header: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            data: { drug_id: drugId, user_id: userId },
            success: (res) => {
              if (res.data.success) {
                wx.showToast({ title: '取消预定成功', icon: 'success' })
                // 重新加载药品记录
                this.setData({
                  records: [],
                  page: 1,
                  hasMore: true
                })
                this.loadDrugRecords()
              } else {
                wx.showToast({ title: res.data.message || '取消预定失败', icon: 'none' })
              }
            },
            fail: (err) => {
              wx.showToast({ title: '网络错误，请稍后重试', icon: 'none' })
              console.error('取消预定药品失败:', err)
            }
          })
        }
      }
    })
  }
})