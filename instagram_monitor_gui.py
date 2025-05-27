import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys
import os
import random
import json
from datetime import datetime
import io
import requests
from PIL import Image, ImageTk, ImageDraw

# 添加manual_deps到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
manual_deps_path = os.path.join(current_dir, 'manual_deps')
if os.path.exists(manual_deps_path):
    sys.path.insert(0, manual_deps_path)

# 导入原始的InstagramMonitor类
from instagram_monitor import InstagramMonitor, logging

# 添加直接导入真实的instagrapi
try:
    from instagrapi import Client
except ImportError:
    print("错误: 无法导入instagrapi模块，程序可能无法正常运行")
    print("请确保已安装instagrapi: pip install instagrapi")

# 尝试导入Cookie提取器
try:
    from browser_cookie_extractor import BrowserCookieExtractor
    COOKIE_EXTRACTOR_AVAILABLE = True
except ImportError:
    COOKIE_EXTRACTOR_AVAILABLE = False

class RedirectText:
    """重定向文本输出到Tkinter文本控件"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""

    def write(self, string):
        self.buffer += string
        self.text_widget.configure(state=tk.NORMAL)
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state=tk.DISABLED)
    
    def flush(self):
        pass

class InstagramMonitorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram博主监控工具")
        self.root.geometry("900x650")  # 增加高度以适应头像
        self.root.resizable(True, True)
        
        # 设置图标
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # 创建InstagramMonitor实例
        self.monitor = InstagramMonitor()
        
        # 初始化图像相关变量
        self.user_avatar = None
        self.blogger_avatars = {}
        self.default_avatar = self.create_default_avatar()
        
        # 初始化UI变量，防止被调用前未定义
        self.selected_blogger_var = tk.StringVar()
        self.blogger_combobox = None
        self.template_combobox = None
        
        # 尝试自动加载Cookie
        self.try_load_saved_cookie()
        
        # 创建监控线程
        self.monitoring_thread = None
        self.is_monitoring = False
        
        # 创建选项卡控件
        self.tab_control = ttk.Notebook(root)
        
        # 创建各个选项卡
        self.tab_main = ttk.Frame(self.tab_control)
        self.tab_bloggers = ttk.Frame(self.tab_control)
        self.tab_templates = ttk.Frame(self.tab_control)
        self.tab_settings = ttk.Frame(self.tab_control)
        self.tab_stats = ttk.Frame(self.tab_control)
        self.tab_posts = ttk.Frame(self.tab_control)  # 新增帖子浏览选项卡
        
        # 添加选项卡
        self.tab_control.add(self.tab_main, text="主页")
        self.tab_control.add(self.tab_bloggers, text="监控博主")
        self.tab_control.add(self.tab_posts, text="帖子浏览")  # 新增选项卡
        self.tab_control.add(self.tab_templates, text="评论模板")
        self.tab_control.add(self.tab_settings, text="设置")
        self.tab_control.add(self.tab_stats, text="数据统计")
        
        self.tab_control.pack(expand=1, fill="both")
        
        # 初始化各选项卡的内容 - 调整初始化顺序，确保posts_tab先初始化
        self.init_main_tab()
        self.init_posts_tab()  # 先初始化posts_tab，创建blogger_combobox
        self.init_bloggers_tab()  # 再初始化bloggers_tab，使用blogger_combobox
        self.init_templates_tab()
        self.init_settings_tab()
        self.init_stats_tab()
        
        # 设置关闭窗口的处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def create_default_avatar(self, size=64):
        """创建默认头像"""
        img = Image.new('RGB', (size, size), color='lightgray')
        draw = ImageDraw.Draw(img)  # 正确使用ImageDraw.Draw
        # 画一个简单的用户图标
        draw.ellipse([size//4, size//4, size*3//4, size*3//4], fill='white')
        draw.ellipse([size*3//8, size*3//8, size*5//8, size*5//8], fill='lightgray')
        return ImageTk.PhotoImage(img)
    
    def get_avatar_image(self, url, size=64):
        """从URL获取头像图片"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content))
                img = img.resize((size, size), Image.LANCZOS)
                # 裁剪为圆形
                mask = Image.new('L', (size, size), 0)
                draw = ImageDraw.Draw(mask)  # 正确使用ImageDraw.Draw
                draw.ellipse([0, 0, size, size], fill=255)
                img.putalpha(mask)
                return ImageTk.PhotoImage(img)
        except Exception as e:
            logging.error(f"获取头像出错: {str(e)}")
        return self.default_avatar
    
    def try_load_saved_cookie(self):
        """尝试加载保存的Cookie文件"""
        cookie_file = self.monitor.config.get('cookie_file')
        
        if cookie_file and os.path.exists(cookie_file):
            try:
                if self.monitor.client.load_cookies_from_file(cookie_file):
                    self.monitor.logged_in = True
                    logging.info(f"已自动加载Cookie并登录Instagram")
                    
                    # 更新登录状态显示
                    self.login_status_var.set("已登录")
                    self.login_method_var.set("Cookie")
                    
                    # 获取用户信息和头像
                    self.root.after(500, self.fetch_user_info)  # 延迟半秒获取用户信息，确保登录已完成
                    
                    return True
            except Exception as e:
                logging.error(f"自动加载Cookie失败: {str(e)}")
        
        return False
        
    def init_main_tab(self):
        """初始化主页选项卡"""
        # 添加用户头像区域
        user_frame = ttk.Frame(self.tab_main)
        user_frame.pack(fill="x", padx=10, pady=5)
        
        # 用户头像标签
        self.user_avatar_label = ttk.Label(user_frame)
        self.user_avatar_label.config(image=self.default_avatar)
        self.user_avatar_label.image = self.default_avatar
        self.user_avatar_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # 用户信息
        self.user_info_var = tk.StringVar(value="未登录")
        self.user_info_label = ttk.Label(user_frame, textvariable=self.user_info_var, font=("", 12, "bold"))
        self.user_info_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # 创建登录框架
        login_frame = ttk.LabelFrame(self.tab_main, text="账号登录")
        login_frame.pack(fill="x", padx=10, pady=5)
        
        # 用户名
        ttk.Label(login_frame, text="用户名:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.username_var = tk.StringVar(value=self.monitor.config.get('username', ''))
        ttk.Entry(login_frame, textvariable=self.username_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        # 密码
        ttk.Label(login_frame, text="密码:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.password_var = tk.StringVar(value=self.monitor.config.get('password', ''))
        password_entry = ttk.Entry(login_frame, textvariable=self.password_var, width=30, show="*")
        password_entry.grid(row=1, column=1, padx=5, pady=5)
        
        # 登录按钮
        ttk.Button(login_frame, text="登录", command=self.login).grid(row=1, column=2, padx=5, pady=5)
        
        # Cookie导入框架
        cookie_frame = ttk.LabelFrame(self.tab_main, text="Cookie导入(推荐)")
        cookie_frame.pack(fill="x", padx=10, pady=5)
        
        # Cookie文件说明
        cookie_info = "从浏览器导入Instagram的Cookie，可绕过密码验证"
        ttk.Label(cookie_frame, text=cookie_info, wraplength=500).grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        
        # 自动提取Cookie按钮
        if COOKIE_EXTRACTOR_AVAILABLE:
            ttk.Button(cookie_frame, text="自动从浏览器提取Cookie", command=self.auto_extract_cookies).grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        
        # 手动导入Cookie
        ttk.Label(cookie_frame, text="或手动导入Cookie文件:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.cookie_path_var = tk.StringVar()
        ttk.Entry(cookie_frame, textvariable=self.cookie_path_var, width=40).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        # 浏览按钮
        ttk.Button(cookie_frame, text="浏览", command=self.browse_cookie_file).grid(row=2, column=2, padx=5, pady=5)
        
        # 导入按钮
        ttk.Button(cookie_frame, text="导入Cookie文件", command=self.import_cookie).grid(row=3, column=1, padx=5, pady=5)
        
        # 状态框架
        status_frame = ttk.LabelFrame(self.tab_main, text="状态")
        status_frame.pack(fill="x", padx=10, pady=5)
        
        # 登录状态
        ttk.Label(status_frame, text="登录状态:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.login_status_var = tk.StringVar(value="未登录")
        ttk.Label(status_frame, textvariable=self.login_status_var).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # 登录方式
        ttk.Label(status_frame, text="登录方式:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.login_method_var = tk.StringVar(value="无")
        ttk.Label(status_frame, textvariable=self.login_method_var).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # 监控状态
        ttk.Label(status_frame, text="监控状态:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.monitor_status_var = tk.StringVar(value="未启动")
        ttk.Label(status_frame, textvariable=self.monitor_status_var).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        # 监控博主数量
        ttk.Label(status_frame, text="监控博主:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.blogger_count_var = tk.StringVar(value=f"{len(self.monitor.config.get('bloggers', []))}个")
        ttk.Label(status_frame, textvariable=self.blogger_count_var).grid(row=3, column=1, padx=5, pady=5, sticky="w")
        
        # 评论模式
        ttk.Label(status_frame, text="评论模式:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.comment_mode_var = tk.StringVar(value="半自动" if not self.monitor.config.get('auto_comment') else "全自动")
        ttk.Label(status_frame, textvariable=self.comment_mode_var).grid(row=4, column=1, padx=5, pady=5, sticky="w")
        
        # 控制框架
        control_frame = ttk.LabelFrame(self.tab_main, text="控制")
        control_frame.pack(fill="x", padx=10, pady=5)
        
        # 开始/停止监控按钮
        self.monitor_button = ttk.Button(control_frame, text="开始监控", command=self.toggle_monitoring)
        self.monitor_button.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 切换评论模式按钮
        self.toggle_mode_button = ttk.Button(control_frame, text="切换评论模式", command=self.toggle_comment_mode)
        self.toggle_mode_button.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 导出Cookie按钮
        self.export_cookie_button = ttk.Button(control_frame, text="导出Cookie", command=self.export_cookie)
        self.export_cookie_button.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 日志框架
        log_frame = ttk.LabelFrame(self.tab_main, text="日志")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 重定向日志输出到GUI
        self.redirect = RedirectText(self.log_text)
        sys.stdout = self.redirect
        
        # 设置日志处理器
        handler = logging.StreamHandler(self.redirect)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(handler)
        
    def init_bloggers_tab(self):
        """初始化博主管理选项卡"""
        # 博主列表框架
        bloggers_frame = ttk.LabelFrame(self.tab_bloggers, text="已添加的博主")
        bloggers_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 使用Canvas和Frame创建可滚动的博主列表
        canvas = tk.Canvas(bloggers_frame)
        scrollbar = ttk.Scrollbar(bloggers_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        # 配置滚动区域
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 保存引用，以便后续更新
        self.bloggers_frame = scrollable_frame
        
        # 添加与移除博主的框架
        add_remove_frame = ttk.Frame(self.tab_bloggers)
        add_remove_frame.pack(fill="x", padx=10, pady=5)
        
        # 添加博主输入框
        ttk.Label(add_remove_frame, text="博主用户名:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.blogger_var = tk.StringVar()
        ttk.Entry(add_remove_frame, textvariable=self.blogger_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        # 添加/删除按钮
        ttk.Button(add_remove_frame, text="添加博主", command=self.add_blogger).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(add_remove_frame, text="移除选中的博主", command=self.remove_blogger).grid(row=0, column=3, padx=5, pady=5)
        
        # 加载博主列表
        self.load_bloggers()
    
    def init_posts_tab(self):
        """初始化帖子浏览选项卡"""
        # 博主选择框架
        blogger_select_frame = ttk.Frame(self.tab_posts)
        blogger_select_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(blogger_select_frame, text="选择博主:").pack(side=tk.LEFT, padx=5, pady=5)
        self.selected_blogger_var = tk.StringVar()
        self.blogger_combobox = ttk.Combobox(blogger_select_frame, textvariable=self.selected_blogger_var, width=30)
        self.blogger_combobox.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(blogger_select_frame, text="获取帖子", command=self.fetch_blogger_posts).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 帖子列表框架
        posts_frame = ttk.LabelFrame(self.tab_posts, text="博主帖子列表")
        posts_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 创建可滚动的帖子列表
        canvas = tk.Canvas(posts_frame)
        scrollbar = ttk.Scrollbar(posts_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.posts_scrollable_frame = ttk.Frame(canvas)
        
        # 配置滚动区域
        self.posts_scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.posts_scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 评论框架
        comment_frame = ttk.LabelFrame(self.tab_posts, text="发表评论")
        comment_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(comment_frame, text="评论内容:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.comment_var = tk.StringVar()
        ttk.Entry(comment_frame, textvariable=self.comment_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(comment_frame, text="发送评论", command=self.post_comment_to_selected).grid(row=0, column=2, padx=5, pady=5)
        
        # 模板选择
        ttk.Label(comment_frame, text="或选择模板:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.template_combobox = ttk.Combobox(comment_frame, width=50)
        self.template_combobox.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(comment_frame, text="使用模板", command=self.use_template).grid(row=1, column=2, padx=5, pady=5)
        
        # 更新博主列表和模板列表
        self.update_blogger_combobox()
        self.update_template_combobox()
    
    def init_templates_tab(self):
        """初始化评论模板选项卡"""
        # 模板列表框架
        templates_frame = ttk.LabelFrame(self.tab_templates, text="评论模板")
        templates_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 创建一个scrollbar
        scrollbar = ttk.Scrollbar(templates_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 模板列表
        self.templates_listbox = tk.Listbox(templates_frame, yscrollcommand=scrollbar.set, height=15, width=80)
        self.templates_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        scrollbar.config(command=self.templates_listbox.yview)
        
        # 加载模板列表
        self.load_templates()
        
        # 添加与移除模板的框架
        add_remove_frame = ttk.Frame(self.tab_templates)
        add_remove_frame.pack(fill="x", padx=10, pady=5)
        
        # 模板文本框
        ttk.Label(add_remove_frame, text="评论模板内容:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.template_var = tk.StringVar()
        ttk.Entry(add_remove_frame, textvariable=self.template_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        
        # 模板提示
        ttk.Label(add_remove_frame, text="提示: 使用{name}表示博主名字，{emoji}表示随机表情").grid(row=1, column=0, columnspan=3, padx=5, pady=0, sticky="w")
        
        # 添加/删除按钮
        ttk.Button(add_remove_frame, text="添加模板", command=self.add_template).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(add_remove_frame, text="移除选中的模板", command=self.remove_template).grid(row=0, column=3, padx=5, pady=5)
    
    def init_settings_tab(self):
        """初始化设置选项卡"""
        # 设置框架
        settings_frame = ttk.LabelFrame(self.tab_settings, text="监控设置")
        settings_frame.pack(fill="x", padx=10, pady=5)
        
        # 自动评论设置
        auto_comment_var = tk.BooleanVar(value=self.monitor.config.get('auto_comment', False))
        ttk.Checkbutton(settings_frame, text="自动发送评论（启用后将自动发送评论，不再询问）", 
                       variable=auto_comment_var, command=self.toggle_auto_comment).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        # 变化评论设置
        vary_comment_var = tk.BooleanVar(value=self.monitor.config.get('vary_comments', True))
        ttk.Checkbutton(settings_frame, text="随机变化评论内容（启用后将在模板中使用随机表情）", 
                       variable=vary_comment_var, command=self.toggle_comment_variation).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        
        # 监控时间设置框架
        monitor_time_frame = ttk.LabelFrame(self.tab_settings, text="监控时间设置")
        monitor_time_frame.pack(fill="x", padx=10, pady=5)
        
        # 监控间隔
        ttk.Label(monitor_time_frame, text="博主检查间隔(秒):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.check_interval_var = tk.StringVar(value=str(self.monitor.config.get('check_interval', 300)))
        ttk.Entry(monitor_time_frame, textvariable=self.check_interval_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        # 发帖检测时间窗口
        ttk.Label(monitor_time_frame, text="发帖时间窗口(分钟):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.post_window_var = tk.StringVar(value=str(self.monitor.config.get('post_time_window', 10)))
        ttk.Entry(monitor_time_frame, textvariable=self.post_window_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        # 通知设置框架
        notification_frame = ttk.LabelFrame(self.tab_settings, text="通知设置")
        notification_frame.pack(fill="x", padx=10, pady=5)
        
        # 桌面通知
        desktop_notify_var = tk.BooleanVar(value=self.monitor.config.get('desktop_notifications', True))
        ttk.Checkbutton(notification_frame, text="启用桌面通知", 
                       variable=desktop_notify_var).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        # 声音通知
        sound_notify_var = tk.BooleanVar(value=self.monitor.config.get('sound_notifications', True))
        ttk.Checkbutton(notification_frame, text="启用声音通知", 
                       variable=sound_notify_var).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        
        # 保存按钮
        ttk.Button(self.tab_settings, text="保存设置", command=self.save_settings).pack(padx=10, pady=10)
        
        # 保存变量，以便后续使用
        self.settings_vars = {
            'auto_comment': auto_comment_var,
            'vary_comments': vary_comment_var,
            'check_interval': self.check_interval_var,
            'post_window': self.post_window_var,
            'desktop_notifications': desktop_notify_var,
            'sound_notifications': sound_notify_var
        }
    
    def init_stats_tab(self):
        """初始化数据统计选项卡"""
        # 统计框架
        stats_frame = ttk.LabelFrame(self.tab_stats, text="监控数据统计")
        stats_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 基础数据
        basic_stats_frame = ttk.Frame(stats_frame)
        basic_stats_frame.pack(fill="x", padx=5, pady=5)
        
        # 博主数量
        ttk.Label(basic_stats_frame, text="监控的博主数:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.stats_blogger_count = tk.StringVar(value="0")
        ttk.Label(basic_stats_frame, textvariable=self.stats_blogger_count).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # 已发现帖子
        ttk.Label(basic_stats_frame, text="发现的新帖子数:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.stats_post_count = tk.StringVar(value="0")
        ttk.Label(basic_stats_frame, textvariable=self.stats_post_count).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # 已发送评论
        ttk.Label(basic_stats_frame, text="已发送的评论数:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.stats_comment_count = tk.StringVar(value="0")
        ttk.Label(basic_stats_frame, textvariable=self.stats_comment_count).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        # 运行时间
        ttk.Label(basic_stats_frame, text="总运行时间:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.stats_runtime = tk.StringVar(value="0分钟")
        ttk.Label(basic_stats_frame, textvariable=self.stats_runtime).grid(row=3, column=1, padx=5, pady=5, sticky="w")
        
        # 图表框架
        chart_frame = ttk.Frame(stats_frame)
        chart_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 创建图表
        self.figure = plt.Figure(figsize=(5, 4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.chart_canvas = FigureCanvasTkAgg(self.figure, chart_frame)
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # 刷新按钮
        ttk.Button(self.tab_stats, text="刷新统计数据", command=self.refresh_stats).pack(padx=10, pady=10)
        
        # 初始化统计数据
        self.refresh_stats()
        
    def browse_cookie_file(self):
        """浏览选择Cookie文件"""
        file_path = filedialog.askopenfilename(
            title="选择Cookie文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            self.cookie_path_var.set(file_path)
            
    def auto_extract_cookies(self):
        """自动从浏览器提取Cookie"""
        if not COOKIE_EXTRACTOR_AVAILABLE:
            messagebox.showerror("错误", "Cookie提取器不可用，缺少必要依赖")
            return
        
        # 创建进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("正在提取Cookie")
        progress_window.geometry("300x100")
        progress_window.resizable(False, False)
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # 进度标签
        ttk.Label(progress_window, text="正在从浏览器提取Instagram Cookie...").pack(padx=20, pady=10)
        
        # 进度条
        progress = ttk.Progressbar(progress_window, mode="indeterminate")
        progress.pack(fill="x", padx=20, pady=10)
        progress.start()
        
        # 在单独的线程中执行提取，避免阻塞UI
        def extract_thread():
            try:
                extractor = BrowserCookieExtractor()
                cookie_file = extractor.extract()
                
                # 在主线程中更新UI
                self.root.after(0, lambda: self._finish_cookie_extraction(cookie_file, progress_window))
                
            except Exception as e:
                # 在主线程中显示错误
                self.root.after(0, lambda: self._show_extraction_error(str(e), progress_window))
        
        threading.Thread(target=extract_thread, daemon=True).start()

    def _finish_cookie_extraction(self, cookie_file, progress_window):
        """完成Cookie提取后的处理"""
        progress_window.destroy()
        
        if cookie_file:
            self.cookie_path_var.set(cookie_file)
            messagebox.showinfo("成功", "已成功从浏览器提取Instagram Cookie")
            # 自动导入提取的Cookie
            self._import_cookie_file(cookie_file)
        else:
            messagebox.showerror("错误", "未能从浏览器提取到Instagram Cookie")
    
    def _show_extraction_error(self, error_msg, progress_window):
        """显示提取Cookie时的错误"""
        progress_window.destroy()
        messagebox.showerror("提取Cookie出错", f"提取Cookie时发生错误: {error_msg}")
            
    def _import_cookie_file(self, cookie_file):
        """导入Cookie文件"""
        try:
            # 创建新的Client实例（确保使用真实的instagrapi）
            self.monitor.client = Client()
            
            # 读取Cookie文件并查找sessionid
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    cookies_data = json.load(f)
                    
                # 提取sessionid
                sessionid = None
                for cookie in cookies_data:
                    if cookie.get('name') == 'sessionid':
                        sessionid = cookie.get('value')
                        break
                        
                if sessionid:
                    logging.info(f"从Cookie文件中提取到sessionid: {sessionid[:10]}...")
                    
                    # 尝试使用sessionid登录
                    login_success = self.monitor.client.login_by_sessionid(sessionid)
                    logging.info(f"使用sessionid登录结果: {login_success}")
                    
                    if login_success:
                        self.monitor.logged_in = True
                        self.monitor.config['cookie_file'] = cookie_file
                        self.monitor.save_config()
                        
                        # 更新UI
                        self.login_status_var.set("已登录")
                        self.login_method_var.set("Cookie")
                        
                        # 获取用户信息和头像
                        self.fetch_user_info()
                        
                        messagebox.showinfo("成功", "已成功通过Cookie导入登录Instagram")
                        return True
                    else:
                        # 如果sessionid直接登录失败，尝试其他方法
                        logging.warning("使用sessionid直接登录失败，尝试加载完整Cookie文件")
                
                # 如果没有sessionid或sessionid登录失败，尝试完整加载Cookie
                if hasattr(self.monitor.client, 'load_settings'):
                    settings = {
                        "cookies": {cookie['name']: cookie['value'] for cookie in cookies_data if 'name' in cookie and 'value' in cookie}
                    }
                    self.monitor.client.load_settings(settings)
                    
                    # 尝试验证cookie是否有效
                    try:
                        # 尝试一个简单的API调用来验证cookie
                        self.monitor.client.get_timeline_feed()
                        self.monitor.logged_in = True
                        self.monitor.config['cookie_file'] = cookie_file
                        self.monitor.save_config()
                        
                        # 更新UI
                        self.login_status_var.set("已登录")
                        self.login_method_var.set("Cookie")
                        
                        # 获取用户信息和头像
                        self.fetch_user_info()
                        
                        messagebox.showinfo("成功", "已成功通过Cookie导入登录Instagram")
                        return True
                    except Exception as e:
                        logging.error(f"验证Cookie失败: {str(e)}")
                        messagebox.showerror("错误", f"验证Cookie失败: {str(e)}")
                        return False
                
                messagebox.showerror("错误", "当前instagrapi版本不支持通过Cookie文件登录")
                return False
                
            except json.JSONDecodeError:
                messagebox.showerror("错误", "Cookie文件格式错误，不是有效的JSON格式")
                return False
            except Exception as e:
                messagebox.showerror("错误", f"读取Cookie文件失败: {str(e)}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"导入Cookie出错: {str(e)}")
            messagebox.showerror("错误", f"导入Cookie失败: {str(e)}")
            return False
            
    def import_cookie(self):
        """导入Cookie文件"""
        cookie_file = self.cookie_path_var.get()
        if not cookie_file:
            messagebox.showwarning("警告", "请先选择Cookie文件")
            return
            
        if not os.path.exists(cookie_file):
            messagebox.showerror("错误", f"文件不存在: {cookie_file}")
            return
            
        self._import_cookie_file(cookie_file)
    
    def login(self):
        """登录Instagram账号"""
        username = self.username_var.get()
        password = self.password_var.get()
        
        if not username or not password:
            messagebox.showwarning("警告", "请输入用户名和密码")
            return
            
        if self.monitor.login(username, password):
            self.login_status_var.set("已登录")
            self.login_method_var.set("账号密码")
            
            # 获取用户信息和头像
            self.fetch_user_info()
            
            messagebox.showinfo("成功", "已成功登录Instagram")
        else:
            messagebox.showerror("登录失败", "无法使用用户名和密码登录Instagram")
    
    def fetch_user_info(self):
        """获取用户信息和头像"""
        try:
            logging.info("正在获取用户信息和头像...")
            # 获取用户信息
            if hasattr(self.monitor.client, 'user_info'):
                # 获取自己的ID
                user_id = None
                if hasattr(self.monitor.client, 'user_id'):
                    user_id = self.monitor.client.user_id
                    logging.info(f"获取到user_id: {user_id}")
                elif hasattr(self.monitor.client, 'user_info_by_username'):
                    # 尝试通过username获取用户信息
                    if hasattr(self.monitor.client, 'username'):
                        username = self.monitor.client.username
                        logging.info(f"使用username获取用户信息: {username}")
                        user_info = self.monitor.client.user_info_by_username(username)
                        user_id = user_info.pk if hasattr(user_info, 'pk') else None
                
                if not user_id:
                    logging.warning("未能获取用户ID，尝试其他方法获取用户信息")
                    # 回退方案：设置基本用户名信息
                    username = self.monitor.client.username if hasattr(self.monitor.client, 'username') else self.monitor.config.get('username', 'unknown')
                    self.user_info_var.set(f"已登录: {username}")
                    # 尝试通过简单的API调用来更新UI显示
                    self.root.after(0, self.update_user_display, username)
                    return
                
                # 获取用户详细信息
                user_info = self.monitor.client.user_info(user_id)
                
                # 设置用户信息文本
                username = user_info.username if hasattr(user_info, 'username') else 'unknown'
                self.user_info_var.set(f"已登录: {username}")
                
                # 获取用户头像
                if hasattr(user_info, 'profile_pic_url') and user_info.profile_pic_url:
                    self.user_avatar = self.get_avatar_image(user_info.profile_pic_url)
                    # 确保在主线程中更新UI
                    self.root.after(0, self.update_user_display, username)
            else:
                # 回退方案：设置基本用户名信息
                username = self.monitor.client.username if hasattr(self.monitor.client, 'username') else self.monitor.config.get('username', 'unknown')
                self.user_info_var.set(f"已登录: {username}")
                # 更新UI显示
                self.root.after(0, self.update_user_display, username)
        except Exception as e:
            logging.error(f"获取用户信息出错: {str(e)}")
            # 仍然尝试更新显示
            username = self.monitor.client.username if hasattr(self.monitor.client, 'username') else 'unknown'
            self.root.after(0, self.update_user_display, username)
    
    def update_user_display(self, username):
        """更新用户显示信息和头像"""
        # 更新用户信息文本
        self.user_info_var.set(f"已登录: {username}")
        
        # 更新头像
        if hasattr(self, 'user_avatar') and self.user_avatar:
            self.user_avatar_label.config(image=self.user_avatar)
            self.user_avatar_label.image = self.user_avatar
    
    def load_bloggers(self):
        """加载博主列表到界面"""
        # 清空现有的博主标签
        for widget in self.bloggers_frame.winfo_children():
            widget.destroy()
        
        # 加载每个博主
        for index, blogger in enumerate(self.monitor.config.get('bloggers', [])):
            self.add_blogger_to_ui(blogger, index)
            
        # 更新博主下拉列表
        self.update_blogger_combobox()
    
    def add_blogger_to_ui(self, blogger, index):
        """将博主添加到UI，包括头像"""
        # 创建博主条目框架
        blogger_frame = ttk.Frame(self.bloggers_frame)
        blogger_frame.pack(fill="x", padx=5, pady=5)
        
        # 添加头像标签
        avatar_label = ttk.Label(blogger_frame)
        
        # 使用默认头像
        avatar_label.config(image=self.default_avatar)
        avatar_label.image = self.default_avatar
        avatar_label.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 添加博主名称标签
        blogger_label = ttk.Label(blogger_frame, text=blogger, width=20)
        blogger_label.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 添加删除按钮
        delete_button = ttk.Button(blogger_frame, text="删除", 
                                   command=lambda b=blogger: self.remove_specific_blogger(b))
        delete_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 添加浏览帖子按钮
        browse_button = ttk.Button(blogger_frame, text="浏览帖子", 
                                  command=lambda b=blogger: self.browse_blogger_posts(b))
        browse_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 尝试获取博主头像
        self.fetch_blogger_avatar(blogger, avatar_label)
    
    def fetch_blogger_avatar(self, blogger, avatar_label):
        """获取博主头像"""
        def get_avatar_thread():
            try:
                # 获取博主信息
                user_id = self.monitor.client.user_id_from_username(blogger)
                user_info = self.monitor.client.user_info(user_id)
                
                # 获取并设置头像
                if hasattr(user_info, 'profile_pic_url') and user_info.profile_pic_url:
                    avatar = self.get_avatar_image(user_info.profile_pic_url)
                    self.blogger_avatars[blogger] = avatar
                    
                    # 在主线程中更新UI
                    self.root.after(0, lambda: self.update_avatar_label(avatar_label, avatar))
            except Exception as e:
                logging.error(f"获取博主 {blogger} 头像出错: {str(e)}")
        
        # 在后台线程中获取头像，避免阻塞UI
        threading.Thread(target=get_avatar_thread, daemon=True).start()
    
    def update_avatar_label(self, label, image):
        """更新头像标签"""
        label.config(image=image)
        label.image = image  # 保持引用，防止被垃圾回收
    
    def remove_specific_blogger(self, blogger):
        """移除特定博主"""
        if messagebox.askyesno("确认", f"确定要移除博主 {blogger} 吗?"):
            if self.monitor.remove_blogger(blogger):
                self.load_bloggers()
                self.blogger_count_var.set(f"{len(self.monitor.config.get('bloggers', []))}个")
            else:
                messagebox.showerror("错误", f"无法移除博主: {blogger}")
    
    def browse_blogger_posts(self, blogger):
        """浏览博主帖子"""
        # 切换到帖子选项卡并选择对应博主
        self.tab_control.select(self.tab_posts)
        self.selected_blogger_var.set(blogger)
        # 获取帖子
        self.fetch_blogger_posts()
    
    def update_blogger_combobox(self):
        """更新博主下拉列表"""
        # 添加防御性检查，确保combobox已经创建
        if not hasattr(self, 'blogger_combobox') or self.blogger_combobox is None:
            return
        
        bloggers = self.monitor.config.get('bloggers', [])
        self.blogger_combobox['values'] = bloggers
        if bloggers:
            self.blogger_combobox.current(0)
    
    def update_template_combobox(self):
        """更新评论模板下拉列表"""
        # 添加防御性检查
        if not hasattr(self, 'template_combobox') or self.template_combobox is None:
            return
        
        templates = self.monitor.comment_templates
        self.template_combobox['values'] = templates
        if templates:
            self.template_combobox.current(0)
    
    def fetch_blogger_posts(self):
        """获取选定博主的帖子"""
        blogger = self.selected_blogger_var.get()
        if not blogger:
            messagebox.showwarning("警告", "请先选择一个博主")
            return
            
        if not self.monitor.logged_in:
            messagebox.showwarning("警告", "请先登录Instagram")
            return
            
        # 清空帖子列表
        for widget in self.posts_scrollable_frame.winfo_children():
            widget.destroy()
            
        # 创建加载中提示
        loading_label = ttk.Label(self.posts_scrollable_frame, text="正在加载帖子...")
        loading_label.pack(padx=10, pady=10)
        self.root.update()
            
        def fetch_posts_thread():
            try:
                # 获取博主ID
                user_id = self.monitor.client.user_id_from_username(blogger)
                
                # 获取帖子（最多20条）
                medias = []
                try:
                    if hasattr(self.monitor.client, 'user_medias_v1'):
                        medias = self.monitor.client.user_medias_v1(user_id, 20)
                    else:
                        medias = self.monitor.client.user_medias(user_id, 20)
                except Exception as e:
                    logging.error(f"获取帖子失败: {str(e)}")
                    medias = []
                
                # 在主线程中显示帖子
                self.root.after(0, lambda: self.display_posts(blogger, medias, loading_label))
            except Exception as e:
                error_msg = f"获取博主 {blogger} 的帖子失败: {str(e)}"
                logging.error(error_msg)
                self.root.after(0, lambda: self.show_posts_error(error_msg, loading_label))
        
        # 在后台线程中获取帖子
        threading.Thread(target=fetch_posts_thread, daemon=True).start()
    
    def display_posts(self, blogger, medias, loading_label=None):
        """显示博主的帖子列表"""
        # 移除加载提示
        if loading_label:
            loading_label.destroy()
            
        if not medias:
            ttk.Label(self.posts_scrollable_frame, text=f"没有找到 {blogger} 的帖子").pack(padx=10, pady=10)
            return
            
        # 显示每条帖子
        ttk.Label(self.posts_scrollable_frame, text=f"{blogger} 的帖子列表 ({len(medias)}条)", 
                 font=("", 12, "bold")).pack(padx=10, pady=10)
                 
        for media in medias:
            self.add_post_to_ui(blogger, media)
    
    def show_posts_error(self, error_msg, loading_label=None):
        """显示帖子获取错误"""
        # 移除加载提示
        if loading_label:
            loading_label.destroy()
            
        ttk.Label(self.posts_scrollable_frame, text=error_msg, foreground="red").pack(padx=10, pady=10)
    
    def add_post_to_ui(self, blogger, media):
        """将帖子添加到UI"""
        # 创建帖子框架
        post_frame = ttk.Frame(self.posts_scrollable_frame)
        post_frame.pack(fill="x", padx=10, pady=5)
        
        # 帖子ID和时间（如果有）
        post_id = media.id if hasattr(media, 'id') else 'unknown'
        post_time = ''
        if hasattr(media, 'taken_at'):
            if isinstance(media.taken_at, datetime):
                post_time = media.taken_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                try:
                    post_time = datetime.fromtimestamp(media.taken_at).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    post_time = str(media.taken_at)
        
        # 帖子类型和链接
        post_type = '帖子'
        if hasattr(media, 'media_type'):
            post_type = {1: '图片', 2: '视频', 8: '相册'}.get(media.media_type, '帖子')
        
        post_url = '#'
        if hasattr(media, 'code') and media.code:
            post_url = f"https://www.instagram.com/p/{media.code}/"
        
        # 帖子描述（如果有）
        caption = ''
        if hasattr(media, 'caption_text') and media.caption_text:
            caption = media.caption_text[:100] + ('...' if len(media.caption_text) > 100 else '')
        
        # 显示帖子信息
        info_text = f"ID: {post_id}\n"
        info_text += f"时间: {post_time}\n" if post_time else ""
        info_text += f"类型: {post_type}\n"
        info_text += f"描述: {caption}\n" if caption else ""
        
        ttk.Label(post_frame, text=info_text, wraplength=400, justify=tk.LEFT).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 评论按钮
        ttk.Button(post_frame, text="评论", 
                  command=lambda m=media, b=blogger: self.comment_on_post(m, b)).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 打开链接按钮
        if post_url != '#':
            ttk.Button(post_frame, text="查看帖子", 
                      command=lambda url=post_url: self.open_url(url)).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 添加分隔线
        ttk.Separator(self.posts_scrollable_frame, orient=tk.HORIZONTAL).pack(fill="x", padx=10, pady=5)
    
    def open_url(self, url):
        """打开帖子链接"""
        import webbrowser
        webbrowser.open(url)
    
    def comment_on_post(self, media, blogger):
        """在指定帖子上发表评论"""
        # 打开评论对话框
        comment_dialog = tk.Toplevel(self.root)
        comment_dialog.title(f"评论 {blogger} 的帖子")
        comment_dialog.geometry("600x350")  # 增加高度以容纳新的控件
        comment_dialog.resizable(True, True)
        comment_dialog.transient(self.root)
        comment_dialog.grab_set()
        
        # 帖子信息
        post_frame = ttk.Frame(comment_dialog)
        post_frame.pack(fill="x", padx=10, pady=5)
        
        # 帖子ID和时间
        post_id = media.id if hasattr(media, 'id') else 'unknown'
        
        # 获取帖子链接
        post_url = '#'
        if hasattr(media, 'code') and media.code:
            post_url = f"https://www.instagram.com/p/{media.code}/"
        
        # 显示帖子信息
        ttk.Label(post_frame, text=f"博主: {blogger}\n帖子ID: {post_id}\n链接: {post_url}", 
                 justify=tk.LEFT).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 评论内容
        comment_frame = ttk.Frame(comment_dialog)
        comment_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        ttk.Label(comment_frame, text="评论内容:").pack(anchor=tk.W, padx=5, pady=5)
        comment_text = tk.Text(comment_frame, height=5, width=50)
        comment_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 添加状态文本
        status_var = tk.StringVar(value="准备发送评论")
        status_label = ttk.Label(comment_frame, textvariable=status_var, foreground="blue")
        status_label.pack(fill="x", padx=5, pady=2)
        
        # 高级选项框架
        advanced_frame = ttk.LabelFrame(comment_dialog, text="高级选项")
        advanced_frame.pack(fill="x", padx=10, pady=5)
        
        # 添加延迟设置
        delay_frame = ttk.Frame(advanced_frame)
        delay_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(delay_frame, text="发送前延迟(秒):").pack(side=tk.LEFT, padx=5, pady=2)
        delay_var = tk.StringVar(value="1")
        delay_entry = ttk.Spinbox(delay_frame, from_=0, to=30, textvariable=delay_var, width=5)
        delay_entry.pack(side=tk.LEFT, padx=5, pady=2)
        
        ttk.Label(delay_frame, text="提示: 使用较长延迟可以减少被Instagram限制的可能").pack(side=tk.LEFT, padx=5, pady=2)
        
        # 模板选择
        templates_frame = ttk.Frame(comment_dialog)
        templates_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(templates_frame, text="使用模板:").pack(side=tk.LEFT, padx=5, pady=5)
        template_var = tk.StringVar()
        template_combo = ttk.Combobox(templates_frame, textvariable=template_var, width=40)
        template_combo['values'] = self.monitor.comment_templates
        if self.monitor.comment_templates:
            template_combo.current(0)
        template_combo.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 按钮框架
        button_frame = ttk.Frame(comment_dialog)
        button_frame.pack(fill="x", padx=10, pady=5)
        
        # 应用模板按钮
        ttk.Button(button_frame, text="应用模板", 
                  command=lambda: comment_text.insert(tk.END, template_var.get())).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 发表评论按钮
        def post_and_close():
            comment = comment_text.get("1.0", tk.END).strip()
            if not comment:
                messagebox.showwarning("警告", "请输入评论内容", parent=comment_dialog)
                return
            
            # 禁用发送按钮，防止重复点击
            send_button.config(state=tk.DISABLED)
            
            try:
                # 获取延迟值
                delay = float(delay_var.get())
                if delay > 0:
                    # 更新状态标签
                    status_var.set(f"正在等待 {delay} 秒后发送...")
                    comment_dialog.update()
                    time.sleep(delay)
                
                # 更新状态
                status_var.set("正在发送评论...")
                comment_dialog.update()
                
                # 发表评论
                result = self.monitor.post_comment(media.id, comment)
                
                if result:
                    messagebox.showinfo("成功", "评论发布成功", parent=comment_dialog)
                    comment_dialog.destroy()
                else:
                    # 获取最近的错误日志
                    recent_logs = self.get_recent_error_logs()
                    
                    if "500" in recent_logs and "response" in recent_logs:
                        status_var.set("失败: Instagram服务器错误(500)，服务器可能暂时不可用")
                        messagebox.showerror("服务器错误", 
                                          "Instagram服务器返回500错误，这是服务器内部问题:\n"
                                          "1. 请稍后再试\n"
                                          "2. Instagram可能暂时限制了评论功能\n"
                                          "3. 该帖子可能被设为限制评论", parent=comment_dialog)
                    elif "需要重新登录" in recent_logs:
                        status_var.set("失败: 需要重新登录")
                        messagebox.showerror("登录失效", "您的登录状态已失效，请重新登录Instagram账号", parent=comment_dialog)
                    elif "垃圾评论" in recent_logs or "频率过高" in recent_logs:
                        status_var.set("失败: 评论受限")
                        messagebox.showerror("评论受限", 
                                          "评论失败：您的评论频率过高或内容被视为垃圾评论\n"
                                          "建议等待一段时间后再尝试，或修改评论内容", parent=comment_dialog)
                    elif "禁用评论" in recent_logs:
                        status_var.set("失败: 该帖子已禁用评论")
                        messagebox.showerror("评论已禁用", "该帖子已禁用评论功能", parent=comment_dialog)
                    elif "不存在" in recent_logs or "已被删除" in recent_logs:
                        status_var.set("失败: 帖子不存在或已被删除")
                        messagebox.showerror("帖子不可用", "该帖子不存在或已被删除", parent=comment_dialog)
                    else:
                        status_var.set("发送失败，请查看详细错误")
                        messagebox.showerror("评论失败", 
                                           "发表评论失败，可能是由于以下原因：\n"
                                           "1. Instagram服务器暂时性错误\n"
                                           "2. 您的账号被限制发表评论\n"
                                           "3. 网络连接问题", parent=comment_dialog)
                    
                    # 重新启用发送按钮
                    send_button.config(state=tk.NORMAL)
            except Exception as e:
                error_msg = str(e)
                logging.error(f"发布评论时出错: {error_msg}")
                
                if "login" in error_msg.lower() or "auth" in error_msg.lower():
                    messagebox.showerror("登录问题", "评论失败：登录状态异常，请重新登录Instagram账号", parent=comment_dialog)
                elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                    messagebox.showerror("速率限制", "评论失败：您被Instagram临时限制了评论频率\n建议等待30分钟后再尝试", parent=comment_dialog)
                else:
                    messagebox.showerror("错误", f"发送评论过程中出错: {str(e)}", parent=comment_dialog)
                
                send_button.config(state=tk.NORMAL)
                
        send_button = ttk.Button(button_frame, text="发表评论", command=post_and_close)
        send_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 取消按钮
        ttk.Button(button_frame, text="取消", command=comment_dialog.destroy).pack(side=tk.RIGHT, padx=5, pady=5)
    
    def post_comment_to_selected(self):
        """在所选帖子上发表评论"""
        messagebox.showwarning("提示", "请先在帖子列表中选择要评论的帖子")
    
    def use_template(self):
        """使用所选模板作为评论内容"""
        template = self.template_combobox.get()
        if template:
            self.comment_var.set(template)
    
    def toggle_monitoring(self):
        """开始或停止监控"""
        if not self.monitor.logged_in:
            messagebox.showwarning("警告", "请先登录Instagram")
            return
            
        if self.is_monitoring:
            # 停止监控
            self.is_monitoring = False
            self.monitor_status_var.set("未启动")
            self.monitor_button.config(text="开始监控")
            logging.info("已停止监控博主")
        else:
            # 开始监控前检查是否有博主
            if not self.monitor.config.get('bloggers', []):
                messagebox.showwarning("警告", "请先添加至少一个要监控的博主")
                return
                
            # 更新界面状态
            self.is_monitoring = True
            self.monitor_status_var.set("监控中")
            self.monitor_button.config(text="停止监控")
            
            # 启动监控线程
            if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
                self.monitoring_thread = threading.Thread(target=self.monitoring_task, daemon=True)
                self.monitoring_thread.start()
                logging.info("已开始监控博主")
                
                # 在主线程中短暂更新UI，防止界面卡死
                self.root.after(100, self.update_monitoring_status)
    
    def update_monitoring_status(self):
        """更新监控状态，保持UI响应"""
        if self.is_monitoring:
            # 定期检查监控状态
            self.monitor_status_var.set("监控中")
            # 每秒更新一次UI
            self.root.after(1000, self.update_monitoring_status)
    
    def monitoring_task(self):
        """监控任务的线程函数"""
        while self.is_monitoring:
            try:
                # 更新UI状态
                self.root.after_idle(lambda: self.monitor_status_var.set("检查中..."))
                
                # 检查新帖子
                self.monitor.check_new_posts()
                
                # 更新统计数据
                self.root.after_idle(self.refresh_stats)
                
                # 更新状态为空闲
                self.root.after_idle(lambda: self.monitor_status_var.set("监控中"))
                
                # 检查间隔
                check_interval = int(self.monitor.config.get('check_interval', 60))
                # 分段睡眠，以便更快响应停止命令
                for _ in range(check_interval):
                    if not self.is_monitoring:
                        break
                    time.sleep(1)
            except Exception as e:
                logging.error(f"监控过程中发生错误: {str(e)}")
                # 在UI上显示错误
                self.root.after_idle(lambda e=e: self.monitor_status_var.set(f"错误: {str(e)[:30]}..."))
                # 短暂等待后继续
                time.sleep(10)  # 出错后等待一段时间再继续
    
    def load_templates(self):
        """加载评论模板到界面"""
        self.templates_listbox.delete(0, tk.END)
        for template in self.monitor.comment_templates:
            self.templates_listbox.insert(tk.END, template)
    
    def add_template(self):
        """添加评论模板"""
        template = self.template_var.get()
        if not template:
            messagebox.showwarning("警告", "请输入评论模板内容")
            return
            
        if self.monitor.add_comment_template(template):
            self.load_templates()
            self.template_var.set("")  # 清空输入框
    
    def remove_template(self):
        """移除评论模板"""
        selection = self.templates_listbox.curselection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要移除的模板")
            return
            
        index = selection[0]
        if self.monitor.remove_comment_template(index):
            self.load_templates()
    
    def toggle_comment_mode(self):
        """切换评论模式"""
        if self.monitor.toggle_auto_comment():
            self.comment_mode_var.set("全自动" if self.monitor.config.get('auto_comment') else "半自动")
    
    def toggle_auto_comment(self):
        """切换自动评论设置"""
        self.monitor.config['auto_comment'] = self.settings_vars['auto_comment'].get()
        self.monitor.save_config()
        self.comment_mode_var.set("全自动" if self.monitor.config.get('auto_comment') else "半自动")
    
    def toggle_comment_variation(self):
        """切换评论变化设置"""
        self.monitor.config['comment_variation'] = self.settings_vars['vary_comments'].get()
        self.monitor.save_config()
    
    def save_settings(self):
        """保存设置"""
        try:
            # 更新配置
            self.monitor.config['check_interval'] = int(self.check_interval_var.get())
            self.monitor.config['post_time_window'] = int(self.post_window_var.get())
            self.monitor.config['desktop_notifications'] = self.settings_vars['desktop_notifications'].get()
            self.monitor.config['sound_notifications'] = self.settings_vars['sound_notifications'].get()
            
            # 保存配置
            self.monitor.save_config()
            messagebox.showinfo("成功", "设置已保存")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
    
    def refresh_stats(self):
        """刷新统计数据"""
        # 更新基础数据
        blogger_count = len(self.monitor.config.get('bloggers', []))
        self.stats_blogger_count.set(str(blogger_count))
        
        # 这里应该添加实际的统计数据，可以从monitor对象中获取
        # 暂时使用示例数据
        self.stats_post_count.set("0")
        self.stats_comment_count.set("0")
        self.stats_runtime.set("0分钟")
        
        # 更新图表 (简单示例)
        self.ax.clear()
        self.ax.bar(['博主数', '新帖子数', '评论数'], [blogger_count, 0, 0])
        self.ax.set_title('监控统计')
        self.chart_canvas.draw()
    
    def export_cookie(self):
        """导出当前Cookie到文件"""
        if not self.monitor.logged_in:
            messagebox.showwarning("警告", "请先登录Instagram")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="保存Cookie文件",
            filetypes=[("JSON文件", "*.json")],
            defaultextension=".json"
        )
        
        if file_path:
            try:
                # 获取当前客户端的会话cookie
                cookie_data = []
                
                # 检查是否有可用的session对象
                if hasattr(self.monitor.client, 'session') and self.monitor.client.session:
                    # 从session中提取cookie
                    for cookie in self.monitor.client.session.cookies:
                        cookie_data.append({
                            'name': cookie.name,
                            'value': cookie.value,
                            'domain': cookie.domain,
                            'path': cookie.path,
                            'expires': cookie.expires if hasattr(cookie, 'expires') else None
                        })
                        
                    # 如果没有从session获取到cookie，尝试从其他属性获取
                    if not cookie_data and hasattr(self.monitor.client, 'cookies'):
                        cookies_dict = self.monitor.client.cookies
                        for name, value in cookies_dict.items():
                            cookie_data.append({
                                'name': name,
                                'value': value,
                                'domain': '.instagram.com',
                                'path': '/'
                            })
                
                # 如果cookie_data为空，尝试使用API特定的导出方法
                if not cookie_data:
                    # 尝试从客户端获取sessionid
                    if hasattr(self.monitor.client, 'sessionid') and self.monitor.client.sessionid:
                        cookie_data.append({
                            'name': 'sessionid',
                            'value': self.monitor.client.sessionid,
                            'domain': '.instagram.com',
                            'path': '/'
                        })
                        
                    # 如果有user_id或username，也一并保存
                    if hasattr(self.monitor.client, 'user_id') and self.monitor.client.user_id:
                        cookie_data.append({
                            'name': 'user_id',
                            'value': self.monitor.client.user_id,
                            'domain': '.instagram.com',
                            'path': '/'
                        })
                        
                    if hasattr(self.monitor.client, 'username') and self.monitor.client.username:
                        cookie_data.append({
                            'name': 'username',
                            'value': self.monitor.client.username,
                            'domain': '.instagram.com',
                            'path': '/'
                        })
                
                # 如果还是没有cookie，尝试从设置中获取
                if not cookie_data and hasattr(self.monitor.client, 'get_settings'):
                    settings = self.monitor.client.get_settings()
                    if settings and isinstance(settings, dict) and 'cookies' in settings:
                        cookies_dict = settings['cookies']
                        for name, value in cookies_dict.items():
                            cookie_data.append({
                                'name': name,
                                'value': value,
                                'domain': '.instagram.com',
                                'path': '/'
                            })
                
                # 如果cookie_data还是空的，则抛出错误
                if not cookie_data:
                    raise Exception("无法获取有效的Cookie信息，请重新登录后再尝试导出")
                
                # 保存到文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(cookie_data, f, ensure_ascii=False, indent=4)
                    
                messagebox.showinfo("成功", f"Cookie已保存到 {file_path}")
                logging.info(f"Cookie已保存到: {file_path}")
                
            except Exception as e:
                error_msg = f"保存Cookie失败: {str(e)}"
                messagebox.showerror("错误", error_msg)
                logging.error(error_msg)
    
    def on_closing(self):
        """关闭窗口时的处理"""
        if self.is_monitoring:
            if messagebox.askyesno("确认", "监控正在进行中，确定要退出吗？"):
                self.is_monitoring = False
                self.root.destroy()
        else:
            self.root.destroy()

    def add_blogger(self):
        """添加博主到监控列表"""
        blogger = self.blogger_var.get()
        if not blogger:
            messagebox.showwarning("警告", "请输入博主用户名")
            return
        
        if not self.monitor.logged_in:
            messagebox.showwarning("警告", "请先登录Instagram")
            return
        
        # 显示加载中对话框
        progress = ttk.Progressbar(self.tab_bloggers, mode="indeterminate")
        progress.pack(fill="x", padx=10, pady=5)
        progress.start()
        self.root.update()
        
        def add_blogger_thread():
            success = False
            error_msg = ""
            try:
                success = self.monitor.add_blogger(blogger)
                if not success:
                    error_msg = "无法添加博主，可能用户不存在或网络问题"
            except Exception as e:
                error_msg = str(e)
            
            # 在主线程中更新UI
            self.root.after(0, lambda: self.finish_add_blogger(blogger, success, error_msg, progress))
        
        # 在后台线程中添加博主
        threading.Thread(target=add_blogger_thread, daemon=True).start()

    def finish_add_blogger(self, blogger, success, error_msg, progress):
        """完成添加博主操作"""
        # 移除进度条
        progress.destroy()
        
        if success:
            self.load_bloggers()
            self.blogger_count_var.set(f"{len(self.monitor.config.get('bloggers', []))}个")
            self.blogger_var.set("")  # 清空输入框
            self.update_blogger_combobox()  # 更新下拉列表
        else:
            messagebox.showerror("错误", f"无法添加博主 {blogger}: {error_msg}")

    def remove_blogger(self):
        """从监控列表中移除博主"""
        # 由于已经使用了remove_specific_blogger方法，
        # 这个方法现在只是一个提示用户使用UI中的删除按钮
        messagebox.showinfo("提示", "请在博主列表中点击对应博主行的'删除'按钮来移除博主")

    def post_comment_to_media(self, media_id, comment):
        """在指定帖子上发表评论"""
        try:
            result = self.monitor.post_comment(media_id, comment)
            if result:
                messagebox.showinfo("成功", "评论发布成功")
            else:
                # 获取最近的错误日志，提供更详细的错误信息
                recent_logs = self.get_recent_error_logs()
                if "需要重新登录" in recent_logs:
                    messagebox.showerror("登录失效", "您的登录状态已失效，请重新登录Instagram账号")
                elif "垃圾评论" in recent_logs or "频率过高" in recent_logs:
                    messagebox.showerror("评论受限", "评论失败：您的评论频率过高或内容被视为垃圾评论\n建议等待一段时间后再尝试，或修改评论内容")
                elif "禁用评论" in recent_logs:
                    messagebox.showerror("评论已禁用", "该帖子已禁用评论功能")
                elif "不存在" in recent_logs or "已被删除" in recent_logs:
                    messagebox.showerror("帖子不可用", "该帖子不存在或已被删除")
                elif "500" in recent_logs and "response" in recent_logs:
                    messagebox.showerror("服务器错误", 
                                      "Instagram服务器返回500错误，这是服务器内部问题:\n"
                                      "1. 请稍后再试\n"
                                      "2. Instagram可能暂时限制了评论功能")
                else:
                    messagebox.showerror("评论失败", "发表评论失败，可能是由于以下原因：\n1. 网络连接问题\n2. Instagram临时限制了评论功能\n3. 您的账号被限制发表评论")
        except Exception as e:
            error_msg = str(e)
            logging.error(f"发布评论时出错: {error_msg}")
            
            if "login" in error_msg.lower() or "auth" in error_msg.lower():
                messagebox.showerror("登录问题", "评论失败：登录状态异常，请重新登录Instagram账号")
            elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                messagebox.showerror("速率限制", "评论失败：您被Instagram临时限制了评论频率\n建议等待30分钟后再尝试")
            else:
                messagebox.showerror("错误", f"发布评论时出错: {error_msg}")
    
    def get_recent_error_logs(self):
        """获取最近的错误日志"""
        try:
            with open('instagram_monitor.log', 'r', encoding='utf-8') as f:
                # 读取最后20行
                lines = f.readlines()[-20:]
                # 只保留ERROR行
                error_lines = [line for line in lines if 'ERROR' in line]
                return '\n'.join(error_lines)
        except Exception:
            return ""

# 主函数入口
if __name__ == "__main__":
    root = tk.Tk()
    app = InstagramMonitorGUI(root)
    root.mainloop() 