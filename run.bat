@echo off
echo 启动中国A级景区地图系统...
echo.
echo 正在安装Python依赖...
pip install Flask pandas openpyxl
echo.
echo 启动Flask应用...
python app.py
echo.
pause




