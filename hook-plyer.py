from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# 收集plyer模块的所有子模块
hiddenimports = collect_submodules('plyer')

# 收集plyer模块的所有数据文件
datas = collect_data_files('plyer') 