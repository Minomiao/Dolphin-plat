import zipfile
import os
from pathlib import Path

# 创建 plugins 目录
plugins_dir = Path('plugins')
plugins_dir.mkdir(exist_ok=True)

# 要打包的插件目录
plugin_package_dir = Path('plugins/user_input_plugin')

# 压缩包名称
zip_name = 'user_input_plugin.zip'
zip_path = plugins_dir / zip_name

# 创建压缩包
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    # 遍历插件目录中的所有文件
    for root, dirs, files in os.walk(plugin_package_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # 计算相对路径，确保压缩包中的目录结构正确
            # 移除 'plugins/user_input_plugin/' 前缀，直接从根目录开始
            arcname = os.path.relpath(file_path, plugin_package_dir)
            zipf.write(file_path, arcname)

print(f"插件压缩包已创建: {zip_path}")