// record.js
Page({
  data: {
    records: [],
    filteredRecords: [],
    activeTab: 'all',
    loading: false
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
    
    // 跳转到药品记录界面
    wx.navigateTo({
      url: '/pages/drugRecords/drugRecords'
    })
  },
  
  onShow() {
    // 页面显示时不执行任何操作，因为已经在 onLoad 中跳转到药品记录页面
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({
      activeTab: tab
    })
    
    // 筛选记录
    this.filterRecords()
  },

  loadRecords() {
    const app = getApp()
    
    this.setData({
      loading: true
    })
    
    wx.request({
      url: `${app.globalData.baseUrl}/user_records`,
      method: 'GET',
      header: {
        'Authorization': `Bearer ${wx.getStorageSync('token')}`
      },
      success: (res) => {
        if (res.data.success) {
          this.setData({
            records: res.data.data
          })
          // 筛选记录
          this.filterRecords()
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

  filterRecords() {
    const { records, activeTab } = this.data
    let filteredRecords = [...records]
    
    // 根据标签筛选
    if (activeTab !== 'all') {
      filteredRecords = records.filter(record => record.type === activeTab)
    }
    
    this.setData({
      filteredRecords
    })
  },

  // 跳转到待借药品页面
  navigateToPendingDrugs() {
    wx.navigateTo({
      url: '/pages/pendingDrugs/pendingDrugs'
    })
  }
})