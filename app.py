from flask import Flask, render_template, jsonify, request
import sys
import os

# 获取资源文件的绝对路径（支持PyInstaller/Nuitka打包）
def resource_path(relative_path):
    """
    获取资源文件的绝对路径，兼容打包后的环境
    
    Args:
        relative_path: 相对路径
    """

    base_path = sys.path[0]
    return os.path.join(base_path, relative_path)

# 设置Flask的template和static文件夹路径（从临时目录读取）
template_folder = resource_path('templates')
app = Flask(__name__, template_folder=template_folder)

# 全局变量存储景区数据
景区数据 = []

def 加载景区数据():
    """加载txt中的景区数据"""
    global 景区数据
    try:
        景区数据 = []
        # 数据文件从exe所在目录读取（不从临时目录）
        data_file = resource_path('景区数据.txt')
        print(f"正在从以下路径加载数据: {data_file}")
        with open(data_file, 'r', encoding='utf-8') as f:
            headers = f.readline().strip().split('\t')
            for line in f:
                fields = line.strip().split('\t')
                if len(fields) >= 5:
                    景区数据.append({
                        '景区名称': fields[0],
                        '地区': fields[1],
                        '景区等级': fields[2],
                        '经度': fields[3],
                        '纬度': fields[4]
                    })
        print(f"成功加载 {len(景区数据)} 个景区数据")
    except Exception as e:
        print(f"加载数据失败: {e}")
        景区数据 = []

@app.route('/')
def 主页():
    """主页面"""
    user_agent = request.headers.get('User-Agent', '').lower()
    is_mobile = any(keyword in user_agent for keyword in ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'windows phone'])
    return render_template('index.html', is_mobile=is_mobile)

def 标准化等级(level_value: str) -> str:
    """将各种可能的等级表示归一化为 A/2A/3A/4A/5A"""
    if not level_value or level_value.strip() == '':
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
    if not 景区数据:
        return jsonify({"error": "数据未加载"})
    
    # 获取查询参数
    地区 = request.args.get('地区', '')
    景区等级 = request.args.get('等级', '')
    限制数量 = request.args.get('limit', 13000, type=int)

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

    # 过滤数据
    数据 = 景区数据[:]
    
    if 地区:
        数据 = [item for item in 数据 if 地区 in item['地区']]

    # 等级归一化并筛选（及以上）
    if 景区等级:
        数据 = [item for item in 数据 if 等级满足及以上(item['景区等级'], 景区等级)]

    # 视口边界过滤
    if None not in (min_lng, max_lng, min_lat, max_lat):
        filtered = []
        for item in 数据:
            try:
                经度 = float(item['经度'])
                纬度 = float(item['纬度'])
                if (min_lng <= 经度 <= max_lng) and (min_lat <= 纬度 <= max_lat):
                    filtered.append(item)
            except (ValueError, TypeError):
                continue
        数据 = filtered
    
    # 限制返回数量（避免一次返回太多数据）
    数据 = 数据[:限制数量]
    
    # 转换为JSON格式
    结果 = []
    for item in 数据:
        try:
            经度 = float(item['经度'])
            纬度 = float(item['纬度'])
            
            # 检查经纬度范围是否合理
            if not (-180 <= 经度 <= 180) or not (-90 <= 纬度 <= 90):
                continue
                
            结果.append({
                'name': item['景区名称'],
                'region': item['地区'],
                'level': item['景区等级'],
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
    if not 景区数据:
        return jsonify({"error": "数据未加载"})
    
    # 统计地区
    地区统计 = {}
    for item in 景区数据:
        地区 = item['地区']
        地区统计[地区] = 地区统计.get(地区, 0) + 1
    
    # 统计等级
    等级统计 = {}
    for item in 景区数据:
        等级 = item['景区等级']
        等级统计[等级] = 等级统计.get(等级, 0) + 1
    
    统计 = {
        "总景区数": len(景区数据),
        "按地区统计": 地区统计,
        "按等级统计": 等级统计
    }
    
    return jsonify(统计)

if __name__ == '__main__':
    # 启动应用前加载数据
    加载景区数据()
    print("\n使用步骤:")
    print("1.请在edge中打开: http://127.0.0.1:5000")
    print("2.点击浏览器右上角三个点打开分屏")
    print("3.在右侧搜索栏搜索打开小红书并登录")
    print("4.在地址栏点击中间的按钮：打开右侧的左侧链接")
    print("5.点击你感兴趣的景点，其会自动在右侧小红书打开")
    from waitress import serve
    serve(app, host="0.0.0.0", port=5000)
    
