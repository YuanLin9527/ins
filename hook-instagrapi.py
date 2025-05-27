from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# 收集instagrapi模块的所有子模块
hiddenimports = collect_submodules('instagrapi')

# 添加额外的重要子模块
additional_modules = [
    'instagrapi.mixins',
    'instagrapi.exceptions',
    'instagrapi.types',
    'instagrapi.utils',
    'instagrapi.extractors',
    'tzdata',
    'requests',
    'requests.sessions',
    'urllib3'
]

# 扩展hiddenimports列表
for module in additional_modules:
    try:
        hiddenimports.extend(collect_submodules(module))
    except Exception:
        hiddenimports.append(module)

# 收集instagrapi模块的所有数据文件
datas = collect_data_files('instagrapi') 