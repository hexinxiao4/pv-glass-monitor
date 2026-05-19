#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
光伏玻璃价格自动采集器 - 交互式图表版
生成含ECharts的HTML，支持缩放、拖动、切换周期
"""

import os
import re
import sqlite3
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests

DB_PATH = "data/pv_glass.db"
HTML_PATH = "site/index.html"
SMM_H5_URL = "https://hq.smm.cn/h5/pv-glass"

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            date TEXT UNIQUE PRIMARY KEY,
            article_id TEXT,
            mm32_low REAL, mm32_high REAL, mm32_avg REAL,
            mm20_low REAL, mm20_high REAL, mm20_avg REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def fetch_h5_data():
    """从SMM H5移动端页面获取光伏玻璃价格"""
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    try:
        print(f"[Fetch] 请求SMM H5页面: {SMM_H5_URL}")
        response = requests.get(SMM_H5_URL, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', response.text)
        pub_date = datetime.now().strftime("%Y-%m-%d")
        if date_match:
            pub_date = date_match.group(1)

        tables = soup.find_all("table")
        if not tables:
            print("[Error] 页面未找到表格")
            return None

        table = tables[0]
        rows = table.find_all("tr")

        data = {
            "date": pub_date,
            "article_id": "h5-pv-glass",
            "3.2mm_low": None, "3.2mm_high": None, "3.2mm_avg": None,
            "2.0mm_low": None, "2.0mm_high": None, "2.0mm_avg": None,
        }

        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 6:
                continue

            name = cols[0].get_text(strip=True)
            price_range = cols[1].get_text(strip=True)
            avg_price = cols[2].get_text(strip=True)

            date_in_name = re.search(r'(\d{2}-\d{2})', name)
            if date_in_name:
                month_day = date_in_name.group(1)
                year = datetime.now().year
                data["date"] = f"{year}-{month_day}"

            def parse_range(pr):
                pr = pr.replace(",", "").strip()
                if "-" in pr:
                    parts = pr.split("-")
                    try:
                        return float(parts[0].strip()), float(parts[1].strip())
                    except:
                        return None, None
                try:
                    val = float(pr)
                    return val, val
                except:
                    return None, None

            low, high = parse_range(price_range)
            try:
                avg = float(avg_price.replace(",", "").strip())
            except:
                avg = None

            if "3.2mm" in name and ("光伏玻璃" in name or "镀膜" in name):
                data["3.2mm_low"] = low
                data["3.2mm_high"] = high
                data["3.2mm_avg"] = avg
                print(f"[Parse] 3.2mm: low={low}, high={high}, avg={avg}")
            elif "2.0mm" in name and ("光伏玻璃" in name or "镀膜" in name):
                data["2.0mm_low"] = low
                data["2.0mm_high"] = high
                data["2.0mm_avg"] = avg
                print(f"[Parse] 2.0mm: low={low}, high={high}, avg={avg}")

        if data["3.2mm_avg"] is None and data["2.0mm_avg"] is None:
            print("[Warn] 未获取到有效价格数据")
            return None

        print(f"[Success] 获取 {pub_date} 数据成功")
        return data

    except Exception as e:
        print(f"[Error] 获取H5数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_to_db(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO prices 
        (date, article_id, mm32_low, mm32_high, mm32_avg, mm20_low, mm20_high, mm20_avg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["date"], data["article_id"],
        data["3.2mm_low"], data["3.2mm_high"], data["3.2mm_avg"],
        data["2.0mm_low"], data["2.0mm_high"], data["2.0mm_avg"]
    ))
    conn.commit()
    conn.close()
    print(f"[DB] 已保存 {data['date']} 数据")

def get_history(days=90):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT * FROM prices 
        WHERE date >= ? AND mm32_avg IS NOT NULL
        ORDER BY date ASC
    """, (start_date,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def generate_html(history, today_data):
    os.makedirs("site", exist_ok=True)

    # 准备JSON数据
    dates = [row["date"] for row in history]
    price_32 = [round(row["mm32_avg"], 2) if row["mm32_avg"] else None for row in history]
    price_20 = [round(row["mm20_avg"], 2) if row["mm20_avg"] else None for row in history]

    chart_data = json.dumps({
        "dates": dates,
        "price32": price_32,
        "price20": price_20
    }, ensure_ascii=False)

    # 计算涨跌
    change_32 = change_20 = ""
    change_class_32 = change_class_20 = ""
    if len(history) >= 2:
        prev = history[-2]
        if prev["mm32_avg"] and today_data["3.2mm_avg"]:
            diff = today_data["3.2mm_avg"] - prev["mm32_avg"]
            pct = (diff / prev["mm32_avg"]) * 100
            arrow = "▲" if diff > 0 else "▼" if diff < 0 else "→"
            color = "#e74c3c" if diff > 0 else "#27ae60" if diff < 0 else "#95a5a6"
            change_32 = f"{arrow} {abs(diff):.2f} ({abs(pct):.2f}%)"
            change_class_32 = f"color:{color}"

        if prev["mm20_avg"] and today_data["2.0mm_avg"]:
            diff = today_data["2.0mm_avg"] - prev["mm20_avg"]
            pct = (diff / prev["mm20_avg"]) * 100
            arrow = "▲" if diff > 0 else "▼" if diff < 0 else "→"
            color = "#e74c3c" if diff > 0 else "#27ae60" if diff < 0 else "#95a5a6"
            change_20 = f"{arrow} {abs(diff):.2f} ({abs(pct):.2f}%)"
            change_class_20 = f"color:{color}"

    # 历史表格
    table_rows = ""
    for row in reversed(history[-30:]):
        date_str = row["date"]
        p32 = f"{row['mm32_avg']:.2f}" if row["mm32_avg"] else "-"
        p20 = f"{row['mm20_avg']:.2f}" if row["mm20_avg"] else "-"
        table_rows += f"<tr><td>{date_str}</td><td>{p32}</td><td>{p20}</td></tr>"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    build_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>光伏玻璃价格监控 | SMM日报</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        header h1 {{ font-size: 2.2em; margin-bottom: 10px; font-weight: 600; }}
        header p {{ opacity: 0.9; font-size: 1.1em; }}
        .update-time {{
            text-align: center;
            color: #888;
            margin-bottom: 20px;
            font-size: 0.9em;
        }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            transition: transform 0.2s;
        }}
        .card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        .card-header {{
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }}
        .card-icon {{
            width: 40px; height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2em;
            margin-right: 12px;
        }}
        .icon-32 {{ background: #e3f2fd; color: #1976d2; }}
        .icon-20 {{ background: #fff3e0; color: #f57c00; }}
        .card-title {{ font-size: 1.1em; color: #666; font-weight: 500; }}
        .price {{
            font-size: 2.5em;
            font-weight: 700;
            color: #2c3e50;
            margin: 10px 0;
        }}
        .price-range {{
            font-size: 0.9em;
            color: #888;
            margin-bottom: 8px;
        }}
        .change {{
            font-size: 1em;
            font-weight: 600;
            padding: 4px 12px;
            border-radius: 20px;
            display: inline-block;
        }}
        .chart-section {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            margin-bottom: 30px;
        }}
        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .chart-header h2 {{
            font-size: 1.3em;
            color: #2c3e50;
        }}
        .time-buttons {{
            display: flex;
            gap: 8px;
        }}
        .time-btn {{
            padding: 6px 16px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.2s;
            color: #666;
        }}
        .time-btn:hover {{ background: #f0f0f0; }}
        .time-btn.active {{
            background: #667eea;
            color: white;
            border-color: #667eea;
        }}
        #chart-container {{
            width: 100%;
            height: 450px;
        }}
        .data-table {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        }}
        .data-table h2 {{
            font-size: 1.3em;
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        tr:hover {{ background: #f8f9fa; }}
        .footer {{
            text-align: center;
            padding: 30px;
            color: #999;
            font-size: 0.85em;
        }}
        .footer a {{ color: #667eea; text-decoration: none; }}
        @media (max-width: 768px) {{
            header h1 {{ font-size: 1.5em; }}
            .price {{ font-size: 2em; }}
            #chart-container {{ height: 350px; }}
            .chart-header {{ flex-direction: column; align-items: flex-start; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 光伏玻璃价格监控</h1>
            <p>上海有色网(SMM) 每日现货报价自动追踪</p>
        </header>

        <div class="update-time">
            数据更新时间: {now_str} | 来源: <a href="https://hq.smm.cn/h5/pv-glass" target="_blank">SMM光伏玻璃H5</a>
        </div>

        <div class="cards">
            <div class="card">
                <div class="card-header">
                    <div class="card-icon icon-32">🔷</div>
                    <div class="card-title">3.2mm 单层镀膜</div>
                </div>
                <div class="price">{today_data["3.2mm_avg"]:.2f} <span style="font-size:0.5em;color:#888;">元/m²</span></div>
                <div class="price-range">区间: {today_data["3.2mm_low"]:.2f} - {today_data["3.2mm_high"]:.2f}</div>
                <div class="change" style="{change_class_32}">{change_32 if change_32 else "较昨日持平"}</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <div class="card-icon icon-20">🔶</div>
                    <div class="card-title">2.0mm 单层镀膜</div>
                </div>
                <div class="price">{today_data["2.0mm_avg"]:.2f} <span style="font-size:0.5em;color:#888;">元/m²</span></div>
                <div class="price-range">区间: {today_data["2.0mm_low"]:.2f} - {today_data["2.0mm_high"]:.2f}</div>
                <div class="change" style="{change_class_20}">{change_20 if change_20 else "较昨日持平"}</div>
            </div>
        </div>

        <div class="chart-section">
            <div class="chart-header">
                <h2>📈 价格趋势图</h2>
                <div class="time-buttons">
                    <button class="time-btn active" data-days="7">1周</button>
                    <button class="time-btn" data-days="30">1月</button>
                    <button class="time-btn" data-days="90">3月</button>
                    <button class="time-btn" data-days="180">6月</button>
                    <button class="time-btn" data-days="365">1年</button>
                    <button class="time-btn" data-days="all">全部</button>
                </div>
            </div>
            <div id="chart-container"></div>
        </div>

        <div class="data-table">
            <h2>📋 历史数据明细</h2>
            <table>
                <thead>
                    <tr>
                        <th>日期</th>
                        <th>3.2mm均价 (元/m²)</th>
                        <th>2.0mm均价 (元/m²)</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>自动采集系统 | 每日更新 | 数据仅供参考</p>
            <p>GitHub Actions 驱动 | 上次构建: {build_str}</p>
        </div>
    </div>

    <script>
        // 嵌入历史数据
        const chartData = {chart_data};

        // 初始化图表
        const chartDom = document.getElementById('chart-container');
        const myChart = echarts.init(chartDom);

        // 颜色配置（莫兰迪色系）
        const colors = {{
            '32mm': '#6B8E9F',
            '20mm': '#D4A373',
            'grid': '#E8E8E8',
            'text': '#4A4A4A'
        }};

        function getOption(dates, data32, data20) {{
            return {{
                backgroundColor: 'transparent',
                tooltip: {{
                    trigger: 'axis',
                    backgroundColor: 'rgba(255,255,255,0.95)',
                    borderColor: '#ddd',
                    borderWidth: 1,
                    textStyle: {{ color: '#333' }},
                    axisPointer: {{
                        type: 'cross',
                        crossStyle: {{ color: '#999' }}
                    }}
                }},
                legend: {{
                    data: ['3.2mm单层镀膜', '2.0mm单层镀膜'],
                    top: 0,
                    textStyle: {{ color: colors.text }}
                }},
                grid: {{
                    left: '3%',
                    right: '4%',
                    bottom: '15%',
                    top: '12%',
                    containLabel: true
                }},
                toolbox: {{
                    feature: {{
                        dataZoom: {{ yAxisIndex: 'none' }},
                        restore: {{}},
                        saveAsImage: {{}}
                    }},
                    right: 20
                }},
                dataZoom: [
                    {{
                        type: 'inside',
                        start: 0,
                        end: 100
                    }},
                    {{
                        type: 'slider',
                        start: 0,
                        end: 100,
                        height: 30,
                        bottom: 10,
                        borderColor: '#ddd',
                        fillerColor: 'rgba(102, 126, 234, 0.1)',
                        handleStyle: {{ color: '#667eea' }}
                    }}
                ],
                xAxis: {{
                    type: 'category',
                    boundaryGap: false,
                    data: dates,
                    axisLine: {{ lineStyle: {{ color: colors.grid }} }},
                    axisLabel: {{ 
                        color: colors.text,
                        rotate: 45,
                        formatter: function(value) {{
                            return value.substring(5); // 显示 MM-DD
                        }}
                    }}
                }},
                yAxis: {{
                    type: 'value',
                    name: '价格 (元/m²)',
                    nameTextStyle: {{ color: colors.text }},
                    axisLine: {{ show: false }},
                    axisTick: {{ show: false }},
                    splitLine: {{ lineStyle: {{ color: colors.grid, type: 'dashed' }} }},
                    axisLabel: {{ color: colors.text }}
                }},
                series: [
                    {{
                        name: '3.2mm单层镀膜',
                        type: 'line',
                        data: data32,
                        smooth: true,
                        symbol: 'circle',
                        symbolSize: 6,
                        lineStyle: {{ color: colors['32mm'], width: 2.5 }},
                        itemStyle: {{ color: colors['32mm'] }},
                        areaStyle: {{
                            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                {{ offset: 0, color: 'rgba(107, 142, 159, 0.2)' }},
                                {{ offset: 1, color: 'rgba(107, 142, 159, 0.02)' }}
                            ])
                        }},
                        markPoint: {{
                            data: [
                                {{ type: 'max', name: '最高' }},
                                {{ type: 'min', name: '最低' }}
                            ]
                        }}
                    }},
                    {{
                        name: '2.0mm单层镀膜',
                        type: 'line',
                        data: data20,
                        smooth: true,
                        symbol: 'circle',
                        symbolSize: 6,
                        lineStyle: {{ color: colors['20mm'], width: 2.5 }},
                        itemStyle: {{ color: colors['20mm'] }},
                        areaStyle: {{
                            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                {{ offset: 0, color: 'rgba(212, 163, 115, 0.2)' }},
                                {{ offset: 1, color: 'rgba(212, 163, 115, 0.02)' }}
                            ])
                        }},
                        markPoint: {{
                            data: [
                                {{ type: 'max', name: '最高' }},
                                {{ type: 'min', name: '最低' }}
                            ]
                        }}
                    }}
                ]
            }};
        }}

        // 根据天数筛选数据
        function filterData(days) {{
            const allDates = chartData.dates;
            const all32 = chartData.price32;
            const all20 = chartData.price20;

            if (days === 'all' || days >= allDates.length) {{
                return {{ dates: allDates, p32: all32, p20: all20 }};
            }}

            const start = Math.max(0, allDates.length - days);
            return {{
                dates: allDates.slice(start),
                p32: all32.slice(start),
                p20: all20.slice(start)
            }};
        }}

        // 渲染图表
        function renderChart(days) {{
            const filtered = filterData(days);
            const option = getOption(filtered.dates, filtered.p32, filtered.p20);
            myChart.setOption(option, true);
        }}

        // 时间按钮事件
        document.querySelectorAll('.time-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                const days = this.dataset.days === 'all' ? 'all' : parseInt(this.dataset.days);
                renderChart(days);
            }});
        }});

        // 初始渲染（显示全部数据）
        renderChart('all');

        // 响应式
        window.addEventListener('resize', () => myChart.resize());
    </script>
</body>
</html>"""

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[HTML] 交互式网页已生成: {HTML_PATH}")

def main():
    print("=" * 60)
    print("光伏玻璃价格自动采集任务启动 (交互式图表版)")
    print("=" * 60)

    init_db()

    # 从H5页面获取数据
    today_data = fetch_h5_data()

    if not today_data:
        print("[Warn] 今日无数据，使用历史最新数据")
        history = get_history(days=90)
        if history:
            today_data = {
                "date": history[-1]["date"],
                "3.2mm_avg": history[-1]["mm32_avg"],
                "3.2mm_low": history[-1]["mm32_low"],
                "3.2mm_high": history[-1]["mm32_high"],
                "2.0mm_avg": history[-1]["mm20_avg"],
                "2.0mm_low": history[-1]["mm20_low"],
                "2.0mm_high": history[-1]["mm20_high"],
            }
        else:
            # 首次运行无历史数据，使用默认值
            today_data = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "3.2mm_avg": 16.0, "3.2mm_low": 15.5, "3.2mm_high": 16.5,
                "2.0mm_avg": 9.15, "2.0mm_low": 8.8, "2.0mm_high": 9.5,
            }
            print("[Warn] 使用默认初始数据")
    else:
        save_to_db(today_data)

    # 获取90天历史数据用于图表
    history = get_history(days=90)

    # 生成交互式网页
    generate_html(history, today_data)

    # 最终检查
    print("
[Check] 文件检查:")
    if os.path.exists(HTML_PATH):
        size = os.path.getsize(HTML_PATH)
        print(f"  ✅ {HTML_PATH} ({size:,} bytes)")
    else:
        print(f"  ❌ {HTML_PATH} 不存在")

    print("
[Done] 任务完成，交互式网页已生成")
    return True

if __name__ == "__main__":
    main()
