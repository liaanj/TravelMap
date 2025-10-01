from flask import Flask, render_template, jsonify, request
import pandas as pd

app = Flask(__name__)

# 全局变量存储景区数据
景区数据 = None

def 加载景区数据():
    """加载Excel中的景区数据"""
    global 景区数据
    try:
        景区数据 = pd.read_excel('A级景区（按省份）.xlsx')
        print(f"成功加载 {len(景区数据)} 个景区数据")
    except Exception as e:
        print(f"加载数据失败: {e}")
        景区数据 = pd.DataFrame()

@app.route('/')
def 主页():
    """主页面"""
    return render_template('index.html')

def 标准化等级(level_value: str) -> str:
    """将各种可能的等级表示归一化为 A/2A/3A/4A/5A"""
    if pd.isna(level_value):
        return ''
    text = str(level_value).strip().upper().replace('级', '').replace('Ａ', 'A').replace(' ', '')
    # 常见写法兜底
    if text in {'A', '2A', '3A', '4A', '5A'}:
        return text
    # 处理如 "AAAA" → 4A
    if set(text) == {'A'} and 1 <= len(text) <= 5:
        return f"{len(text)}A" if len(text) > 1 else 'A'
    # 处理如 "4A级"、"四A"（简单兜底，不做中文数字复杂映射）
    for n in ['5A', '4A', '3A', '2A', 'A']:
        if n in text:
            return n
    return text


def 等级满足及以上(level_value: str, min_level: str) -> bool:
    等级优先级 = {'A': 1, '2A': 2, '3A': 3, '4A': 4, '5A': 5}
    lv = 等级优先级.get(标准化等级(level_value), 0)
    need = 等级优先级.get(标准化等级(min_level), 0)
    return lv >= need if need > 0 else True


@app.route('/api/景区数据')
def 获取景区数据():
    """获取所有景区数据的API接口"""
    if 景区数据 is None or 景区数据.empty:
        return jsonify({"error": "数据未加载"})
    
    # 获取查询参数
    地区 = request.args.get('地区', '')
    景区等级 = request.args.get('等级', '')
    限制数量 = request.args.get('limit', '13000', type=int)

    # 视口边界过滤参数（经纬度边界）
    def _get_float(name):
        v = request.args.get(name)
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    min_lng = _get_float('minLng')
    max_lng = _get_float('maxLng')
    min_lat = _get_float('minLat')
    max_lat = _get_float('maxLat')

    # 不再使用网格抽稀，保证完整结果
    
    # 过滤数据
    数据 = 景区数据.copy()
    
    if 地区:
        数据 = 数据[数据['地区'].astype(str).str.contains(地区, na=False)]

    # 等级归一化并筛选（及以上）
    if 景区等级:
        数据 = 数据[数据['景区等级'].map(lambda v: 等级满足及以上(v, 景区等级))]

    # 视口边界过滤
    if None not in (min_lng, max_lng, min_lat, max_lat):
        数据 = 数据[
            (数据['经度'] >= min_lng) & (数据['经度'] <= max_lng) &
            (数据['纬度'] >= min_lat) & (数据['纬度'] <= max_lat)
        ]

        # 不抽稀，原样返回视口范围内的所有点（受limit限制）
    
    # 限制返回数量（避免一次返回太多数据）
    数据 = 数据.head(限制数量)
    
    # 转换为JSON格式
    结果 = []
    for index, row in 数据.iterrows():
        try:
            经度 = row['经度']
            纬度 = row['纬度']
            
            # 检查是否为NaN或无效值
            if pd.isna(经度) or pd.isna(纬度):
                continue
                
            经度 = float(经度)
            纬度 = float(纬度)
            
            # 检查经纬度范围是否合理
            if not (-180 <= 经度 <= 180) or not (-90 <= 纬度 <= 90):
                continue
                
            结果.append({
                'name': str(row['景区名称']),
                'region': str(row['地区']),
                'level': str(row['景区等级']),
                'lng': 经度,
                'lat': 纬度
            })
        except (ValueError, TypeError, OverflowError):
            continue  # 跳过无效的经纬度数据
    
    return jsonify({
        "total": len(结果),
        "data": 结果
    })

@app.route('/api/统计信息')
def 获取统计信息():
    """获取数据统计信息"""
    if 景区数据 is None or 景区数据.empty:
        return jsonify({"error": "数据未加载"})
    
    统计 = {
        "总景区数": len(景区数据),
        "按地区统计": 景区数据['地区'].value_counts().to_dict(),
        "按等级统计": 景区数据['景区等级'].value_counts().to_dict()
    }
    
    return jsonify(统计)

if __name__ == '__main__':
    # 启动应用前加载数据
    加载景区数据()
    from waitress import serve
    serve(app, host="0.0.0.0", port=5000)
    # app.run(host='0.0.0.0', port=5000)
