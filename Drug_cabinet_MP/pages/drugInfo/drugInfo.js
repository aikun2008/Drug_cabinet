// drugInfo.js
Page({
  data: {
    drugs: [],
    searchKeyword: '',
    showDetailModal: false,
    selectedDrug: {},
    loading: false,
    page: 1,
    limit: 6,
    hasMore: true
  },

  // 药品名称到CDN图片的映射
  getDrugImage(name) {
    // 注意：请将域名替换为你的实际域名
    const imageMap = {
      'PBS缓冲液': 'https://your-domain.com/static/picture/PBS缓冲液.jpg',
      'Tris-HCl缓冲液': 'https://your-domain.com/static/picture/Tris-HCl缓冲液.jpg',
      '丙酮': 'https://your-domain.com/static/picture/丙酮.jpg',
      '乙酸乙酯': 'https://your-domain.com/static/picture/乙酸乙酯.jpg',
      '二氯甲烷': 'https://your-domain.com/static/picture/二氯甲烷.jpg',
      '异丙醇': 'https://your-domain.com/static/picture/异丙醇.jpg',
      '氢氧化钠': 'https://your-domain.com/static/picture/氢氧化钠.jpg',
      '氯化钠': 'https://your-domain.com/static/picture/氯化钠.jpg',
      '琼脂粉': 'https://your-domain.com/static/picture/琼脂粉.jpg',
      '甲基橙': 'https://your-domain.com/static/picture/甲基橙.jpg',
      '甲醇': 'https://your-domain.com/static/picture/甲醇.png',
      '甲醛溶液': 'https://your-domain.com/static/picture/甲醛溶液.jpg',
      '盐酸': 'https://your-domain.com/static/picture/盐酸.jpg',
      '硫酸': 'https://your-domain.com/static/picture/硫酸.jpg',
      '葡萄糖': 'https://your-domain.com/static/picture/葡萄糖.jpg',
      '蛋白胨': 'https://your-domain.com/static/picture/蛋白胨.jpg',
      '过氧化氢': 'https://your-domain.com/static/picture/过氧化氢.jpg',
      '酚酞指示剂': 'https://your-domain.com/static/picture/酚酞指示剂.jpg',
      '酵母提取物': 'https://your-domain.com/static/picture/酵母提取物.jpg',
      '三氯甲烷': 'https://your-domain.com/static/picture/三氯甲烷.jpg',
      '乙醚': 'https://your-domain.com/static/picture/乙醚.webp',
      '无水乙醇': 'https://your-domain.com/static/picture/无水乙醇.png'
    };
    return imageMap[name] || '';
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
    
    // 重置分页状态，确保每次进入页面都从第一页开始加载
    this.setData({
      page: 1,
      drugs: [],
      hasMore: true
    })
    
    // 每次进入页面都强制从服务器刷新数据，确保状态是最新的
    this.loadDrugs(false, true)
  },

  onSearchInput(e) {
    this.setData({
      searchKeyword: e.detail.value
    })
  },

  onSearch() {
    this.setData({
      page: 1,
      drugs: [],
      hasMore: true
    })
    this.loadDrugs(true)
  },

  loadDrugs(isSearch = false, isRefresh = false) {
    const app = getApp()
    const { searchKeyword, page, limit, drugs } = this.data
    
    // 如果是搜索，重置为第一页
    const currentPage = isSearch ? 1 : page
    
    this.setData({
      loading: true
    })
    
    wx.request({
      url: `${app.globalData.baseUrl}/mini/drugs`,
      method: 'GET',
      data: {
        keyword: searchKeyword,
        page: currentPage,
        limit: limit,
        refresh: isRefresh
      },
      header: {
        'Authorization': `Bearer ${wx.getStorageSync('token')}`
      },
      success: (res) => {
        console.log('API响应数据:', res.data);
        if (res.data.success) {
          let newDrugs = res.data.data
          console.log('药品数据:', newDrugs);
          
          // 为每个药品添加本地图片路径
          newDrugs = newDrugs.map(drug => ({
            ...drug,
            image_url: this.getDrugImage(drug.name)
          }))
          
          // 如果是搜索或第一页，直接使用新数据
          // 否则，在末尾追加数据
          const updatedDrugs = isSearch || currentPage === 1 ? newDrugs : [...drugs, ...newDrugs]
          
          this.setData({
            drugs: updatedDrugs,
            page: currentPage + 1,
            hasMore: res.data.has_more || false
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

  // 检查药品是否过期
  isDrugExpired(expiryDate) {
    if (!expiryDate) return true; // 没有有效期信息，视为过期
    
    try {
      // 解析日期字符串
      let dateObj;
      if (typeof expiryDate === 'string') {
        // 去除首尾空格
        let dateStr = expiryDate.trim();
        
        // 处理 HTTP 日期格式 (如: "Mon, 06 Apr 2026 00:00:00 GMT")
        // iOS 不支持这种格式，需要转换为标准格式
        if (dateStr.includes('GMT') || dateStr.includes('UTC')) {
          // 使用 Date 解析后转换为 YYYY-MM-DD 格式
          const tempDate = new Date(dateStr);
          if (!isNaN(tempDate.getTime())) {
            const year = tempDate.getFullYear();
            const month = String(tempDate.getMonth() + 1).padStart(2, '0');
            const day = String(tempDate.getDate()).padStart(2, '0');
            dateStr = `${year}-${month}-${day}`;
          }
        }
        
        // 尝试不同的日期格式
        if (dateStr.includes('/')) {
          // 将 yyyy/MM/dd 转换为 yyyy-MM-dd
          dateObj = new Date(dateStr.replace(/\//g, '-'));
        } else if (dateStr.includes('-')) {
          // 标准格式 yyyy-MM-dd
          dateObj = new Date(dateStr);
        } else if (dateStr.length === 8 && /^\d{8}$/.test(dateStr)) {
          // 处理 YYYYMMDD 格式
          const year = dateStr.substring(0, 4);
          const month = dateStr.substring(4, 6) - 1; // 月份从0开始
          const day = dateStr.substring(6, 8);
          dateObj = new Date(year, month, day);
        } else {
          // 其他格式，尝试直接解析
          dateObj = new Date(dateStr);
        }
      } else if (expiryDate instanceof Date) {
        dateObj = expiryDate;
      } else {
        dateObj = new Date(expiryDate);
      }
      
      // 检查日期是否有效
      if (isNaN(dateObj.getTime())) {
        console.warn('无效的日期:', expiryDate);
        return true; // 日期无效，视为过期
      }
      
      // 获取当前日期（不含时分秒）
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      
      // 获取有效期日期（不含时分秒）
      const expiry = new Date(dateObj);
      expiry.setHours(0, 0, 0, 0);
      
      // 比较日期
      return expiry < today;
    } catch (e) {
      console.error('日期解析错误:', e, '输入值:', expiryDate);
      return true; // 解析错误，视为过期
    }
  },

  showDrugDetail(e) {
    const drugId = e.currentTarget.dataset.drugId
    const drug = this.data.drugs.find(d => d.id === drugId)
    
    if (drug) {
      // 对药品详情按状态排序，在库中和已预定的在最上面显示
      const sortedItems = [...drug.items].sort((a, b) => {
        // 定义状态优先级
        const statusPriority = {
          'in_stock': 1,
          'reserved': 1, // 已预定与在库中优先级相同
          'lent_out': 2,
          'discarded': 3
        }
        
        const priorityA = statusPriority[a.status] || 999
        const priorityB = statusPriority[b.status] || 999
        
        return priorityA - priorityB
      })
      
      // 为每个药品项添加是否过期的标记
      const itemsWithExpiryStatus = sortedItems.map(item => ({
        ...item,
        isExpired: this.isDrugExpired(item.expiry_date)
      }));
      
      // 更新药品详情，添加排序后的items
      const updatedDrug = {
        ...drug,
        items: itemsWithExpiryStatus
      }
      
      this.setData({
        selectedDrug: updatedDrug,
        showDetailModal: true
      })
    }
  },

  closeModal() {
    this.setData({
      showDetailModal: false,
      selectedDrug: {}
    })
  },

  stopPropagation() {
    // 阻止事件冒泡，防止点击弹窗内容关闭弹窗
  },

  // 预定药品
  reserveDrug(e) {
    const drugId = e.currentTarget.dataset.drugId
    const app = getApp()
    const userId = app.globalData.userInfo.id
    const userRole = app.globalData.userInfo.role // 假设用户信息中包含角色信息

    wx.showModal({
      title: '确认预定',
      content: '确定要预定该药品吗？',
      success: (res) => {
        if (res.confirm) {
          // 根据用户角色选择不同的API端点
          const apiEndpoint = userRole === 1 ? 'teacher' : 'student'
          
          wx.request({
            url: `${app.globalData.baseUrl}/${apiEndpoint}/drugs/reserve`,
            method: 'POST',
            header: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${wx.getStorageSync('token')}`
            },
            data: { drug_id: drugId, user_id: userId },
            success: (res) => {
              if (res.data.success) {
                wx.showToast({ title: res.data.message || '预定成功', icon: 'success' })
                this.closeModal()
                // 清除本地缓存，确保下次加载时能获取最新数据
                this.clearCache()
                // 重新加载药品列表
                this.loadDrugs()
              } else {
                wx.showToast({ title: res.data.message || '预定失败', icon: 'none' })
              }
            },
            fail: (err) => {
              wx.showToast({ title: '网络错误，请稍后重试', icon: 'none' })
              console.error('预定药品失败:', err)
            }
          })
        }
      }
    })
  },

  onReachBottom() {
    console.log('触发onReachBottom'); // 打印调试信息
    const { loading, hasMore, page } = this.data
    
    console.log('当前状态:', { loading, hasMore, page }); // 打印当前状态
    
    // 如果正在加载或没有更多数据，则不加载
    if (loading || !hasMore) {
      console.log('不加载更多数据:', { loading, hasMore }); // 打印不加载的原因
      return
    }
    
    // 加载更多数据
    console.log('加载更多数据，当前页码:', page); // 打印加载更多的信息
    this.loadDrugs()
  },

  // 跳转到待借药品页面
  navigateToPendingDrugs() {
    wx.navigateTo({
      url: '/pages/pendingDrugs/pendingDrugs'
    })
  },

  // 下拉刷新
  onPullDownRefresh() {
    // 重置分页状态
    this.setData({
      page: 1,
      drugs: [],
      hasMore: true
    })
    
    // 重新加载药品列表，传递refresh参数绕过缓存
    this.loadDrugs(false, true)
    
    // 停止刷新动画
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