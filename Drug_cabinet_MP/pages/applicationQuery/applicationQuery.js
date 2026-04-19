// applicationQuery.js
Page({
  data: {
    applications: [],
    filteredApplications: [],
    activeTab: 'pending_approval', // 待审核
    loading: false
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
    
    // 加载申请记录
    this.loadApplications()
  },

  loadApplications() {
    const app = getApp()
    const userId = app.globalData.userInfo.id

    this.setData({ loading: true })

    wx.request({
      url: `${app.globalData.baseUrl}/student/drugs/applications`,
      method: 'GET',
      data: {
        user_id: userId
      },
      header: {
        'Authorization': `Bearer ${wx.getStorageSync('token')}`
      },
      success: (res) => {
        if (res.data.success) {
          this.setData({
            applications: res.data.data || []
          })
          // 初始筛选
          this.filterApplications(this.data.activeTab)
        } else {
          wx.showToast({
            title: '加载申请记录失败',
            icon: 'none'
          })
        }
      },
      fail: (err) => {
        wx.showToast({
          title: '网络错误，请稍后重试',
          icon: 'none'
        })
        console.error('加载申请记录失败:', err)
      },
      complete: () => {
        this.setData({ loading: false })
      }
    })
  },

  // 切换标签
  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ activeTab: tab })
    this.filterApplications(tab)
  },

  // 筛选申请记录
  filterApplications(tab) {
    const { applications } = this.data
    let filtered = []
    
    switch (tab) {
      case 'pending_approval':
        // 待审核包括pending_approval和approved状态
        filtered = applications.filter(app => app.status === 'pending_approval' || app.status === 'approved')
        break
      case 'completed':
        // 已完成包括completed状态
        filtered = applications.filter(app => app.status === 'completed')
        break
      case 'cancelled':
        // 已取消包括cancelled和rejected状态
        filtered = applications.filter(app => app.status === 'cancelled' || app.status === 'rejected')
        break
      default:
        filtered = applications
    }
    
    this.setData({ filteredApplications: filtered })
  },

  // 格式化状态显示
  formatStatus(status) {
    switch (status) {
      case 'pending_approval':
        return '审核中'
      case 'approved':
        return '已通过'
      case 'rejected':
        return '已驳回'
      case 'completed':
        return '已完成'
      case 'cancelled':
        return '已取消'
      case 'pending':
        return '待确认'
      default:
        return status
    }
  },

  // 格式化时间
  formatTime(time) {
    if (!time) return ''
    
    try {
      let dateStr = time
      
      // 处理 HTTP 日期格式 (如: "Mon, 06 Apr 2026 00:00:00 GMT")
      if (typeof time === 'string' && (time.includes('GMT') || time.includes('UTC'))) {
        const tempDate = new Date(time)
        if (!isNaN(tempDate.getTime())) {
          const year = tempDate.getFullYear()
          const month = String(tempDate.getMonth() + 1).padStart(2, '0')
          const day = String(tempDate.getDate()).padStart(2, '0')
          const hours = String(tempDate.getHours()).padStart(2, '0')
          const minutes = String(tempDate.getMinutes()).padStart(2, '0')
          const seconds = String(tempDate.getSeconds()).padStart(2, '0')
          dateStr = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
        }
      }
      
      const date = new Date(dateStr)
      if (isNaN(date.getTime())) {
        console.warn('无效的日期:', time)
        return time
      }
      
      return date.toLocaleString()
    } catch (e) {
      console.error('日期格式化错误:', e, '输入值:', time)
      return time
    }
  }
})
