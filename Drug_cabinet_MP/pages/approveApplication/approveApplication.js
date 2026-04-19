// approveApplication.js
Page({
  data: {
    applications: [],
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
    
    // 加载待审核的申请记录
    this.loadApplications()
  },

  loadApplications() {
    const app = getApp()
    const userId = app.globalData.userInfo.id

    this.setData({ loading: true })

    wx.request({
      url: `${app.globalData.baseUrl}/teacher/drugs/pending-approval`,
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

  // 审核通过
  approveApplication(e) {
    const app = getApp()
    const drugId = e.currentTarget.dataset.drugId
    const userId = app.globalData.userInfo.id

    wx.showModal({
      title: '审核通过',
      content: '确定要通过该申请吗？',
      success: (res) => {
        if (res.confirm) {
          this.submitApproval(drugId, userId, true, '')
        }
      }
    })
  },

  // 审核拒绝
  rejectApplication(e) {
    const app = getApp()
    const drugId = e.currentTarget.dataset.drugId
    const userId = app.globalData.userInfo.id

    wx.showModal({
      title: '审核拒绝',
      content: '确定要拒绝该申请吗？',
      success: (res) => {
        if (res.confirm) {
          this.submitApproval(drugId, userId, false, '申请被拒绝')
        }
      }
    })
  },

  // 提交审核结果
  submitApproval(drugId, userId, approve, remark) {
    const app = getApp()

    wx.request({
      url: `${app.globalData.baseUrl}/teacher/drugs/approve-reserve`,
      method: 'POST',
      data: {
        drug_id: drugId,
        user_id: userId,
        approve: approve,
        remark: remark
      },
      header: {
        'Authorization': `Bearer ${wx.getStorageSync('token')}`,
        'Content-Type': 'application/json'
      },
      success: (res) => {
        if (res.data.success) {
          wx.showToast({
            title: '审核成功',
            icon: 'success'
          })
          // 重新加载申请记录
          this.loadApplications()
        } else {
          wx.showToast({
            title: '审核失败: ' + res.data.message,
            icon: 'none'
          })
        }
      },
      fail: (err) => {
        wx.showToast({
          title: '网络错误，请稍后重试',
          icon: 'none'
        })
        console.error('提交审核失败:', err)
      }
    })
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
