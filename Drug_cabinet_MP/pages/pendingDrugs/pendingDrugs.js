// pendingDrugs.js
Page({
  data: {
    pendingDrugs: []
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
    
    // 加载待借药品列表
    this.loadPendingDrugs()
  },

  loadPendingDrugs() {
    const app = getApp()
    const userId = app.globalData.userInfo.id
    const userRole = app.globalData.userInfo.role
    const apiEndpoint = userRole === 1 ? 'teacher' : 'student'
    
    wx.request({
      url: `${app.globalData.baseUrl}/${apiEndpoint}/drugs/pending`,
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
            pendingDrugs: res.data.data || []
          })
        } else {
          wx.showToast({
            title: '加载待借药品失败',
            icon: 'none'
          })
        }
      },
      fail: (err) => {
        wx.showToast({
          title: '网络错误，请稍后重试',
          icon: 'none'
        })
        console.error('加载待借药品失败:', err)
      }
    })
  },

  removeDrug(e) {
    const drugId = e.currentTarget.dataset.drugId
    const app = getApp()
    const userId = app.globalData.userInfo.id

    wx.showModal({
      title: '确认移除',
      content: '确定要从待借列表中移除该药品吗？',
      success: (res) => {
        if (res.confirm) {
          const app = getApp()
          const userRole = app.globalData.userInfo.role
          const apiEndpoint = userRole === 1 ? 'teacher' : 'student'
          
          wx.request({
            url: `${app.globalData.baseUrl}/${apiEndpoint}/drugs/cancel-reserve`,
            method: 'POST',
            header: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            data: { drug_id: drugId, user_id: userId },
            success: (res) => {
              if (res.data.success) {
                wx.showToast({ title: '移除成功', icon: 'success' })
                this.loadPendingDrugs() // 重新加载待借药品列表
              } else {
                wx.showToast({ title: res.data.message || '移除失败', icon: 'none' })
              }
            },
            fail: (err) => {
              wx.showToast({ title: '网络错误，请稍后重试', icon: 'none' })
              console.error('移除待借药品失败:', err)
            }
          })
        }
      }
    })
  },

  // 跳转到待借药品页面
  navigateToPendingDrugs() {
    // 已经在待借药品页面，无需跳转
  },

  // 确定借阅按钮点击事件
  confirmBorrow() {
    const app = getApp()
    const userRole = app.globalData.userInfo.role
    const userId = app.globalData.userInfo.id
    const { pendingDrugs } = this.data

    if (pendingDrugs.length === 0) {
      wx.showToast({
        title: '待借列表为空',
        icon: 'none'
      })
      return
    }

    // 根据用户角色选择不同的API端点
    const apiEndpoint = userRole === 1 ? 'teacher' : 'student'
    const apiUrl = `${app.globalData.baseUrl}/${apiEndpoint}/drugs/confirm-reserve`

    wx.showModal({
      title: '确认借阅',
      content: `确定要借阅${pendingDrugs.length}个药品吗？`,
      success: (res) => {
        if (res.confirm) {
          // 逐个借阅药品
          let borrowedCount = 0
          let totalCount = pendingDrugs.length

          pendingDrugs.forEach((drug, index) => {
            wx.request({
              url: apiUrl,
              method: 'POST',
              header: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${wx.getStorageSync('token')}`
              },
              data: { drug_id: drug.id, user_id: userId },
              success: (res) => {
                if (res.data.success) {
                  borrowedCount++
                }
                
                // 所有药品处理完成
                if (index === totalCount - 1) {
                  if (borrowedCount === totalCount) {
                    wx.showToast({ title: '所有药品确认预定成功', icon: 'success' })
                    // 重新加载待借药品列表
                    this.loadPendingDrugs()
                  } else {
                    wx.showToast({ title: `成功确认预定${borrowedCount}个药品`, icon: 'none' })
                    // 重新加载待借药品列表
                    this.loadPendingDrugs()
                  }
                }
              },
              fail: (err) => {
                console.error('确认预定药品失败:', err)
                
                // 所有药品处理完成
                if (index === totalCount - 1) {
                  if (borrowedCount > 0) {
                    wx.showToast({ title: `成功确认预定${borrowedCount}个药品，部分失败`, icon: 'none' })
                  } else {
                    wx.showToast({ title: '确认预定失败', icon: 'none' })
                  }
                  // 重新加载待借药品列表
                  this.loadPendingDrugs()
                }
              }
            })
          })
        }
      }
    })
  }
})