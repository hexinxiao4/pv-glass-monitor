# 光伏玻璃价格自动监控

自动从上海有色网(SMM)获取每日光伏玻璃现货报价，生成趋势图表并部署为静态网页。

## 访问地址

部署成功后，网页可通过以下地址访问：

```
https://<你的用户名>.github.io/pv-glass-monitor/
```

## 功能特性

- ✅ 每日自动抓取 SMM 光伏玻璃报价（3.2mm/2.0mm单层镀膜）
- ✅ 自动生成价格趋势折线图（莫兰迪配色）
- ✅ 计算每日涨跌幅度
- ✅ 保存历史数据到 SQLite 数据库
- ✅ 响应式网页设计，支持手机/电脑访问
- ✅ GitHub Actions 全自动部署，零维护

## 数据来源

- **上海有色网(SMM)**: https://hq.smm.cn/photovoltaic
- 更新频率: 工作日每日更新
- 数据品种: 3.2mm单层镀膜、2.0mm单层镀膜（元/平方米）

## 技术栈

- Python 3.11 + Selenium (数据抓取)
- BeautifulSoup (HTML解析)
- Matplotlib (图表生成)
- SQLite (数据存储)
- GitHub Actions (定时任务 + 自动部署)
- GitHub Pages (静态网站托管)

## 本地运行

```bash
# 安装依赖
pip install selenium beautifulsoup4 matplotlib requests lxml

# 确保已安装 Chrome 和 ChromeDriver
# macOS: brew install chromedriver
# Ubuntu: sudo apt install chromium-chromedriver

# 运行爬虫
python crawler.py

# 查看生成的网页
open site/index.html
```

## 部署步骤

1. **Fork 本仓库** 到你的 GitHub 账号
2. **启用 GitHub Pages**:
   - 进入仓库 Settings → Pages
   - Source 选择 "GitHub Actions"
3. **配置定时任务**:
   - GitHub Actions 已配置每天 15:30 (北京时间) 自动运行
   - 也可在 Actions 页面手动触发 "Daily PV Glass Price Update"
4. **等待首次构建完成**（约2-3分钟）
5. **访问你的专属链接**

## 目录结构

```
.
├── .github/workflows/
│   └── deploy.yml          # GitHub Actions 工作流
├── data/
│   └── pv_glass.db         # SQLite 数据库 (自动创建)
├── site/
│   ├── index.html          # 生成的网页
│   └── chart.png           # 生成的趋势图
├── crawler.py              # 主爬虫脚本
└── README.md
```

## 注意事项

- SMM 网站在节假日可能不更新数据，脚本会自动使用最近可用数据
- 若 SMM 网站结构变更，可能需要更新爬虫选择器
- GitHub Actions 每月有 2000 分钟免费额度，本任务每次约 3 分钟，足够使用

## License

MIT
