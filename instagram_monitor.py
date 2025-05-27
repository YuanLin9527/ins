import time
import json
import logging
import os
import random
import re
import sys
from datetime import datetime, timedelta
import requests
from plyer import notification
import threading
import configparser
from base64 import b64encode

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('instagram_monitor.log')
    ]
)

# 导入instagrapi
try:
    from instagrapi import Client
    logging.info("成功导入instagrapi库")
except ImportError:
    logging.error("错误: 无法导入instagrapi模块，程序无法正常运行")
    logging.error("请确保已安装instagrapi: pip install instagrapi")
    sys.exit(1)

# 函数：获取资源路径 (适配PyInstaller)
def get_resource_path(relative_path):
    """ 获取资源的绝对路径，适配开发环境和PyInstaller打包环境 """
    try:
        # PyInstaller 创建临时文件夹并将路径存储在 _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 获取配置文件和日志文件的路径
CONFIG_FILE_PATH = get_resource_path("config.json")
LOG_FILE_PATH = get_resource_path("instagram_monitor.log")

class InstagramMonitor:
    def __init__(self):
        self.client = Client()
        self.config = self.load_config()
        self.logged_in = False
        self.last_posts = {}  # 存储每个博主的最新帖子ID
        self.comment_templates = self.config.get('templates', [])
        
    def load_config(self):
        """加载配置文件"""
        default_config = {
            'username': '',
            'password': '',
            'bloggers': [],
            'templates': [
                "太棒了，非常喜欢!",
                "这个内容真不错，感谢分享!",
                "喜欢这个风格，继续加油!",
                "很有创意，支持一下!",
                "这个太赞了，谢谢分享！❤️",
                "真漂亮，喜欢这种风格!",
                "这个{content}真的很吸引人!"
            ],
            'auto_comment': False,
            'auto_comment_delay': [2, 5],
            'comment_variation': True,
            'check_interval': 60, # 秒
            'active_hours': {
                'enabled': False,
                'start': 9,  # 上午9点
                'end': 23    # 晚上11点
            },
            'cookie_file': '',
            'last_posts': {}  # 新增：记录每个博主的最新帖子ID
        }
        
        try:
            if os.path.exists(CONFIG_FILE_PATH):
                with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    
                    # 合并配置，确保所有默认项都存在
                    for key, value in default_config.items():
                        if key not in loaded_config:
                            loaded_config[key] = value
                            
                    self.config = loaded_config
                    
                    # 加载保存的last_posts信息
                    if 'last_posts' in loaded_config:
                        self.last_posts = loaded_config['last_posts']
                        logging.info(f"已加载 {len(self.last_posts)} 个博主的最新帖子ID")
                    
                    # 加载评论模板
                    self.comment_templates = self.config.get('templates', default_config['templates'])
                    
                    logging.info("配置文件加载成功")
            else:
                # 尝试保存一次默认配置
                self.config = default_config
                self.comment_templates = default_config['templates']
                self.save_config()
                logging.info("使用默认配置")
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}，使用默认配置")
            self.config = default_config
            self.comment_templates = default_config['templates']
        
        return self.config
    
    def save_config(self):
        """保存配置文件"""
        try:
            # 创建一个副本，以防止修改原始配置
            config_to_save = self.config.copy()
            
            # 保存last_posts信息到配置中
            config_to_save['last_posts'] = self.last_posts
            
            # 保存配置
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=4)
            
            logging.debug(f"配置文件已保存到: {CONFIG_FILE_PATH}")
        except Exception as e:
            logging.error(f"保存配置文件 {CONFIG_FILE_PATH} 失败: {e}")
            
    def login(self, username=None, password=None):
        """登录Instagram"""
        if username:
            self.config['username'] = username
        if password:
            self.config['password'] = password
            
        if not self.config['username'] or not self.config['password']:
            logging.error("请先设置Instagram账号密码")
            return False
            
        try:
            logging.info(f"尝试登录Instagram账号: {self.config['username']}")
            
            # 配置客户端
            self.client = Client()
            self.client.delay_range = [1, 3]  # 设置请求延迟，防止被封
            
            # 尝试登录
            login_result = self.client.login(self.config['username'], self.config['password'])
            logging.info(f"登录结果: {login_result}")
            
            # 检查登录状态 - 新版API可能使用不同方式判断登录状态
            if hasattr(self.client, 'user_id') and self.client.user_id:
                self.logged_in = True
                self.save_config()
                logging.info(f"成功登录Instagram账号: {self.config['username']}")
                return True
            elif hasattr(self.client, 'user_info') and self.client.user_info:
                self.logged_in = True
                self.save_config()
                logging.info(f"成功登录Instagram账号: {self.config['username']}")
                return True
            elif hasattr(self.client, 'username') and self.client.username:
                self.logged_in = True
                self.save_config()
                logging.info(f"成功登录Instagram账号: {self.client.username}")
                return True
            elif login_result == True:
                # 如果login方法返回True但没有其他标识，仍视为登录成功
                self.logged_in = True
                self.save_config()
                logging.info(f"成功登录Instagram账号(通过返回值确认): {self.config['username']}")
                return True
            else:
                logging.error("登录失败: 无法确认登录状态")
                return False
        except Exception as e:
            logging.error(f"登录失败: {str(e)}")
            logging.info("提示: 如果频繁登录失败，可能是因为IP被临时限制或账号需要验证")
            return False
    
    def add_blogger(self, username):
        """添加要监控的博主"""
        if username not in self.config['bloggers']:
            try:
                # 获取用户信息以验证用户名是否存在
                user_id = self.client.user_id_from_username(username)
                self.config['bloggers'].append(username)
                self.save_config()
                logging.info(f"添加博主成功: {username}")
                # 获取最新帖子ID用于后续比较
                self.update_last_post(username)
                return True
            except Exception as e:
                logging.error(f"添加博主失败: {str(e)}")
                return False
        else:
            logging.info(f"博主已在监控列表中: {username}")
            return True
    
    def remove_blogger(self, username):
        """移除监控的博主"""
        if username in self.config['bloggers']:
            self.config['bloggers'].remove(username)
            if username in self.last_posts:
                del self.last_posts[username]
            self.save_config()
            logging.info(f"移除博主成功: {username}")
            return True
        return False
    
    def update_last_post(self, username):
        """更新博主最新帖子ID"""
        try:
            user_id = self.client.user_id_from_username(username)
            
            # 使用与check_new_posts相同的逻辑获取帖子
            medias = None
            try:
                # 首先尝试使用user_medias_v1方法(私有API)
                if hasattr(self.client, 'user_medias_v1'):
                    medias = self.client.user_medias_v1(user_id, 1)
                else:
                    # 然后尝试标准方法
                    medias = self.client.user_medias(user_id, 1)
            except Exception as api_error:
                logging.warning(f"更新帖子ID: 使用标准方法获取帖子失败: {str(api_error)}，尝试备用方法")
                # 最后尝试feed方法
                if hasattr(self.client, 'user_feed'):
                    medias = self.client.user_feed(user_id, 1)
            
            if medias and len(medias) > 0:
                self.last_posts[username] = medias[0].id
                logging.info(f"更新博主 {username} 最新帖子ID: {medias[0].id}")
                
                # 如果可以，也记录帖子链接用于验证
                try:
                    # 尝试获取帖子链接
                    if hasattr(medias[0], 'code') and medias[0].code:
                        post_url = f"https://www.instagram.com/p/{medias[0].code}/"
                        logging.info(f"博主 {username} 最新帖子链接: {post_url}")
                except:
                    pass
                
                # 保存配置
                self.save_config()
                return True
            else:
                logging.warning(f"未找到博主 {username} 的帖子")
                return False
        except Exception as e:
            logging.error(f"更新博主 {username} 最新帖子失败: {str(e)}")
            return False
    
    def parse_timestamp(self, timestamp_value):
        """解析各种格式的时间戳，返回Unix时间戳（整数）"""
        try:
            # 情况1: 已经是整数或浮点数时间戳
            if isinstance(timestamp_value, (int, float)):
                return int(timestamp_value)
            
            # 情况2: 是datetime对象
            if isinstance(timestamp_value, datetime):
                return int(timestamp_value.timestamp())
            
            # 情况3: 是字符串时间戳
            if isinstance(timestamp_value, str):
                # 尝试直接转换为数字
                if timestamp_value.isdigit():
                    return int(timestamp_value)
                
                # 尝试作为ISO格式解析
                try:
                    dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                    return int(dt.timestamp())
                except ValueError:
                    pass
                
                # 尝试常见的日期格式
                formats = [
                    '%Y-%m-%dT%H:%M:%S',  # ISO
                    '%Y-%m-%dT%H:%M:%S.%f',  # ISO with microseconds
                    '%Y-%m-%d %H:%M:%S',  # Standard
                    '%a %b %d %H:%M:%S %Y',  # Weekday Month Day Time Year
                    '%d/%m/%Y %H:%M:%S'  # Day/Month/Year
                ]
                
                for fmt in formats:
                    try:
                        dt = datetime.strptime(timestamp_value, fmt)
                        return int(dt.timestamp())
                    except ValueError:
                        continue
                    
            # 情况4: 可能是一个对象，尝试获取其timestamp属性
            if hasattr(timestamp_value, 'timestamp') and callable(timestamp_value.timestamp):
                return int(timestamp_value.timestamp())
            
            logging.warning(f"无法解析时间戳类型: {type(timestamp_value)}")
            return None
        
        except Exception as e:
            logging.error(f"解析时间戳失败: {str(e)} - 值: {timestamp_value}")
            return None

    def is_valid_post(self, media):
        """验证帖子是否为有效的真实帖子"""
        try:
            # 1. 检查基本属性
            if not media or not hasattr(media, 'id'):
                logging.warning("帖子对象缺少基本属性")
                return False
            
            logging.info(f"开始验证帖子ID: {media.id}")
            
            # 2. 验证帖子代码
            has_valid_code = False
            if hasattr(media, 'code') and media.code:
                has_valid_code = True
                post_url = f"https://www.instagram.com/p/{media.code}/"
                logging.info(f"帖子链接: {post_url}")
            elif hasattr(media, 'shortcode') and media.shortcode:
                has_valid_code = True
                post_url = f"https://www.instagram.com/p/{media.shortcode}/"
                logging.info(f"帖子链接(shortcode): {post_url}")
            
            # 记录可用属性，帮助调试
            media_attrs = [attr for attr in dir(media) if not attr.startswith('_') and not callable(getattr(media, attr))]
            logging.debug(f"帖子属性: {', '.join(media_attrs)}")
            
            # 3. 尝试验证帖子内容
            try:
                # 获取帖子详情
                logging.info(f"尝试获取帖子详情: {media.id}")
                media_detail = self.client.media_info(media.id)
                
                # 记录详情属性，帮助调试
                detail_attrs = [attr for attr in dir(media_detail) if not attr.startswith('_') and not callable(getattr(media_detail, attr))]
                logging.debug(f"帖子详情属性: {', '.join(detail_attrs)}")
                
                # 检查发布时间
                if hasattr(media_detail, 'taken_at'):
                    # 处理taken_at可能是不同类型的情况
                    post_timestamp = media_detail.taken_at
                    logging.info(f"帖子时间戳原始值: {post_timestamp} (类型: {type(post_timestamp)})")
                    
                    # 使用通用解析方法处理时间戳
                    parsed_timestamp = self.parse_timestamp(post_timestamp)
                    if parsed_timestamp:
                        current_time = int(time.time())
                        logging.info(f"当前时间戳: {current_time}, 帖子解析后时间戳: {parsed_timestamp}")
                        
                        # 计算时间差
                        time_diff = current_time - parsed_timestamp
                        logging.info(f"帖子时间差: {time_diff} 秒 ({time_diff/3600:.1f} 小时)")
                        
                        # 检查时间合理性(30天内)
                        if time_diff < 30 * 24 * 3600:
                            logging.info(f"帖子发布于 {time_diff//3600} 小时前，时间验证通过")
                            return True
                        else:
                            logging.warning(f"帖子发布时间过久({time_diff//86400}天前)，可能不是新帖子")
                            # 如果时间太久，但有有效代码，仍视为有效但较老的帖子
                            if has_valid_code:
                                logging.info("虽然帖子较旧，但通过代码验证通过")
                                return True
                            return False
                    else:
                        logging.warning("无法解析帖子时间戳")
                        if has_valid_code:
                            logging.info("但通过帖子代码验证通过")
                            return True
                else:
                    logging.info("帖子详情中没有taken_at属性")
                
                # 检查其他内容属性作为备选验证方法
                if hasattr(media_detail, 'caption_text') and media_detail.caption_text:
                    logging.info(f"帖子包含内容描述: {media_detail.caption_text[:50]}...")
                    return True
                elif hasattr(media_detail, 'like_count'):
                    logging.info(f"帖子包含点赞数据: {media_detail.like_count}")
                    return True
                
                logging.info("帖子详情未包含明确的内容或互动数据")
                
            except Exception as e:
                logging.warning(f"获取帖子详情失败: {str(e)}")
                
                # 4. 备用验证：通过帖子基本属性验证
                if has_valid_code:
                    logging.info("无法获取详情，但通过帖子代码验证通过")
                    return True
                
                # 检查常见属性
                valid_attributes = []
                if hasattr(media, 'caption') and media.caption:
                    valid_attributes.append('caption')
                if hasattr(media, 'like_count'):
                    valid_attributes.append('like_count')
                if hasattr(media, 'comment_count') and media.comment_count:
                    valid_attributes.append('comment_count')
                
                if valid_attributes:
                    logging.info(f"通过帖子基本属性验证通过: {', '.join(valid_attributes)}")
                    return True
                
                if hasattr(media, 'user') and media.user:
                    user_info = getattr(media.user, 'username', 'unknown')
                    logging.info(f"帖子包含用户信息: {user_info}")
                    return True
                
                # 5. 最后的备用检查
                keys = [attr for attr in dir(media) if not attr.startswith('_') and hasattr(media, attr)]
                content_keys = ['image_versions2', 'carousel_media', 'video_versions']
                matching_keys = [key for key in content_keys if key in keys]
                
                if matching_keys:
                    logging.info(f"帖子包含媒体内容: {', '.join(matching_keys)}")
                    return True
                
                logging.warning(f"所有验证方法都失败，无法确认帖子 {media.id} 的有效性")
                return False
            
        except Exception as e:
            logging.error(f"验证帖子时发生错误: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    
    def check_new_posts(self):
        """检查博主是否有新帖子"""
        if not self.logged_in:
            logging.error("未登录Instagram，无法检查新帖子")
            return
            
        if not self.config['bloggers']:
            logging.info("没有要监控的博主")
            return
            
        for blogger in self.config['bloggers']:
            try:
                # 获取用户ID
                user_id = self.client.user_id_from_username(blogger)
                logging.info(f"检查博主 {blogger} (ID: {user_id}) 的新帖子")
                
                # 定义获取帖子的方法，便于重试
                def attempt_get_medias():
                    # 尝试获取帖子 - 使用try/except捕获可能的错误
                    try:
                        # 首先尝试使用user_medias_v1方法(私有API)
                        if hasattr(self.client, 'user_medias_v1'):
                            medias = self.client.user_medias_v1(user_id, 1)
                            logging.info(f"通过v1 API获取到 {len(medias) if medias else 0} 个帖子")
                            return medias
                    except Exception as api_error:
                        logging.warning(f"使用v1方法获取帖子失败: {str(api_error)}")
                    
                    try:
                        # 然后尝试标准方法
                        medias = self.client.user_medias(user_id, 1)
                        logging.info(f"通过标准API获取到 {len(medias) if medias else 0} 个帖子")
                        return medias
                    except Exception as api_error:
                        logging.warning(f"使用标准方法获取帖子失败: {str(api_error)}")
                    
                    try:
                        # 最后尝试feed方法
                        if hasattr(self.client, 'user_feed'):
                            medias = self.client.user_feed(user_id, 1)
                            logging.info(f"通过feed API获取到 {len(medias) if medias else 0} 个帖子")
                            return medias
                    except Exception as api_error:
                        logging.warning(f"使用feed方法获取帖子失败: {str(api_error)}")
                    
                    return None
                
                # 设置最大重试次数
                max_attempts = 3
                for attempt in range(max_attempts):
                    medias = attempt_get_medias()
                    if medias:
                        break
                    elif attempt < max_attempts - 1:
                        logging.info(f"尝试获取帖子失败，等待后重试 ({attempt+1}/{max_attempts})")
                        time.sleep(2)  # 短暂延迟后重试
                
                # 检查是否获取到帖子
                if not medias or len(medias) == 0:
                    logging.info(f"博主 {blogger} 没有帖子或无法获取")
                    continue
                    
                # 获取最新帖子ID
                latest_post_id = medias[0].id
                logging.info(f"博主 {blogger} 最新帖子ID: {latest_post_id}")
                
                # 验证帖子是否真实存在
                if not self.is_valid_post(medias[0]):
                    logging.warning(f"博主 {blogger} 的帖子ID {latest_post_id} 验证失败，可能是假帖子ID")
                    continue
                
                # 如果是首次检查，只记录最新帖子ID
                if blogger not in self.last_posts:
                    self.last_posts[blogger] = latest_post_id
                    self.save_config()  # 保存最新的帖子ID
                    continue
                
                # 检查是否有新帖子
                if latest_post_id != self.last_posts[blogger]:
                    # 发现新帖子
                    logging.info(f"发现博主 {blogger} 的新帖子!")
                    self.notify_new_post(blogger, medias[0])
                    self.last_posts[blogger] = latest_post_id
                    self.save_config()  # 更新帖子ID
                
            except Exception as e:
                logging.error(f"检查博主 {blogger} 新帖子失败: {str(e)}")
                continue  # 继续检查下一个博主
    
    def notify_new_post(self, blogger, media):
        """通知新帖子"""
        try:
            # 确保桌面通知不会阻塞
            def show_notification():
                try:
                    notification.notify(
                        title=f"{blogger} 发布了新帖子!",
                        message=f"{'正在自动评论...' if self.config.get('auto_comment') else '点击查看并快速评论'}",
                        timeout=10
                    )
                except Exception as e:
                    logging.error(f"发送桌面通知失败: {str(e)}")
            
            # 在单独线程中发送通知，防止阻塞
            threading.Thread(target=show_notification, daemon=True).start()
            
            # 获取有效的Instagram帖子链接
            post_url = None
            media_id = None
            
            # 1. 首先尝试使用code/shortcode (最可靠)
            if hasattr(media, 'code') and media.code:
                post_url = f"https://www.instagram.com/p/{media.code}/"
                media_id = media.id
                logging.info(f"使用media.code生成链接: {post_url}")
                
            # 2. 尝试使用shortcode属性
            elif hasattr(media, 'shortcode') and media.shortcode:
                post_url = f"https://www.instagram.com/p/{media.shortcode}/"
                media_id = media.id
                logging.info(f"使用media.shortcode生成链接: {post_url}")
                
            # 3. 如果有pk属性，尝试使用pk
            elif hasattr(media, 'pk') and media.pk:
                # 如果pk是字符串且不是纯数字，可能是shortcode
                if isinstance(media.pk, str) and not media.pk.isdigit():
                    post_url = f"https://www.instagram.com/p/{media.pk}/"
                    media_id = media.id if hasattr(media, 'id') else media.pk
                    logging.info(f"使用media.pk生成链接: {post_url}")
                else:
                    # 如果pk是纯数字，可能是媒体ID
                    media_id = media.pk
                    # 尝试通过API获取shortcode
                    try:
                        if hasattr(self.client, 'media_id_to_code'):
                            shortcode = self.client.media_id_to_code(media_id)
                            post_url = f"https://www.instagram.com/p/{shortcode}/"
                            logging.info(f"从media_id转换为shortcode: {post_url}")
                    except Exception as e:
                        logging.warning(f"媒体ID转换失败: {str(e)}")
                    
            # 如果上述方法都失败，使用通用链接
            if not post_url and media_id:
                post_url = f"https://www.instagram.com/media/view/?id={media_id}"
                logging.warning(f"使用备选链接格式: {post_url}")
            
            logging.info(f"博主 {blogger} 发布了新帖子: {post_url}")
            
            # 打印到控制台，便于用户快速查看
            print(f"\n====================")
            print(f"博主 {blogger} 发布了新帖子!")
            print(f"链接: {post_url}")
            print(f"====================")
            
            # 如果启用了自动评论，启动独立线程处理
            if self.config.get('auto_comment') and self.comment_templates and media_id:
                threading.Thread(
                    target=self.auto_comment_post,
                    args=(blogger, media),
                    daemon=True
                ).start()
                logging.info(f"已启动自动评论线程")
            elif not self.config.get('auto_comment') and media_id:
                # 半自动模式：显示评论模板
                self.show_comment_templates(media_id)
            
        except Exception as e:
            logging.error(f"通知新帖子失败: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
    
    def auto_comment_post(self, blogger, media):
        """自动评论发帖"""
        try:
            # 随机选择评论延迟时间
            min_delay, max_delay = self.config.get('auto_comment_delay', [2, 5])
            delay = random.uniform(min_delay, max_delay)
            
            logging.info(f"将在 {delay:.1f} 秒后对 {blogger} 的帖子发表评论")
            time.sleep(delay)
            
            # 随机选择评论模板
            comment_template = random.choice(self.comment_templates)
            
            # 如果启用了评论变异，对评论进行小修改以降低被识别风险
            if self.config.get('comment_variation', True):
                comment = self.vary_comment(comment_template)
            else:
                comment = comment_template
                
            # 尝试提取帖子内容，以便生成更相关的评论
            try:
                media_detail = self.client.media_info(media.id)
                post_text = media_detail.caption_text if media_detail.caption_text else ""
                
                # 只有当评论中有特定占位符时才替换
                if "{content}" in comment:
                    if post_text:
                        # 提取帖子中的前5个词
                        words = post_text.split()[:5]
                        topic = " ".join(words)
                        comment = comment.replace("{content}", topic)
                    else:
                        # 如果没有帖文内容，就替换为通用短语
                        comment = comment.replace("{content}", "这个内容")
            except:
                # 如果提取失败，确保没有占位符
                comment = comment.replace("{content}", "这个内容")
            
            # 发表评论
            self.post_comment(media.id, comment)
            
        except Exception as e:
            logging.error(f"自动评论失败: {str(e)}")
    
    def vary_comment(self, comment):
        """对评论进行微小变化，降低自动化特征"""
        # 1. 随机添加或删除标点
        punctuations = ["！", "～", "，", "。", "~", "…"]
        if comment[-1] in punctuations and random.random() < 0.3:
            # 30%概率删除末尾标点
            comment = comment[:-1]
        elif comment[-1] not in punctuations and random.random() < 0.3:
            # 30%概率添加末尾标点
            comment += random.choice(punctuations)
            
        # 2. 随机替换表情符号
        happy_emojis = ["😊", "😁", "😄", "😃", "😀", "😍", "🥰", "💖", "👍", "❤️", "✨", "🙌", "🤗"]
        
        # 50%的概率添加随机表情
        if random.random() < 0.5:
            if random.random() < 0.5:  # 放在末尾
                comment += random.choice(happy_emojis)
            else:  # 放在开头
                comment = random.choice(happy_emojis) + comment
                
        # 3. 随机调整空格(如果有)
        if " " in comment:
            if random.random() < 0.3:
                # 30%概率删除一个空格
                comment = comment.replace(" ", "", 1)
            elif random.random() < 0.3:
                # 30%概率添加一个空格
                pos = random.randint(0, len(comment)-1)
                comment = comment[:pos] + " " + comment[pos:]
                
        # 4. 随机大小写调整(针对英文评论)
        if re.search(r'[a-zA-Z]', comment):
            words = comment.split()
            for i, word in enumerate(words):
                if re.match(r'^[a-zA-Z]+$', word) and random.random() < 0.2:
                    # 20%概率调整单词大小写
                    if word.islower():
                        words[i] = word.capitalize()
                    else:
                        words[i] = word.lower()
            comment = " ".join(words)
            
        return comment
    
    def show_comment_templates(self, media_id):
        """显示评论模板"""
        print("\n== 快速评论模板 ==")
        for i, template in enumerate(self.comment_templates, 1):
            print(f"{i}. {template}")
        
        try:
            choice = int(input("\n选择评论模板(输入序号)或输入0自定义评论: "))
            if 1 <= choice <= len(self.comment_templates):
                comment = self.comment_templates[choice-1]
                self.post_comment(media_id, comment)
            elif choice == 0:
                comment = input("请输入自定义评论: ")
                self.post_comment(media_id, comment)
        except ValueError:
            logging.error("无效输入")
    
    def post_comment(self, media_id, comment_text):
        """发布评论"""
        try:
            logging.info(f"尝试对帖子 {media_id} 发表评论: {comment_text}")
            
            # 检查评论长度
            if len(comment_text.strip()) == 0:
                logging.error("评论内容为空")
                return False
                
            # 尝试发送评论，使用指数退避策略
            max_retries = 2  # 最多重试2次
            retry_delay = 5  # 初始延迟5秒
            
            for retry in range(max_retries + 1):
                try:
                    if retry > 0:
                        logging.info(f"第{retry}次重试发表评论，等待{retry_delay}秒...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数增长的延迟

                    result = self.client.media_comment(media_id, comment_text)
                    logging.info(f"API返回结果: {result}")
                    
                    if result:
                        logging.info(f"评论发布成功: {comment_text}")
                        return True
                    else:
                        logging.error("评论API返回空结果")
                        # 第一次失败就跳到下一次重试
                        continue
                        
                except Exception as api_error:
                    error_msg = str(api_error)
                    
                    # 检查是否是500错误
                    if "500" in error_msg and "response" in error_msg.lower():
                        logging.error(f"Instagram服务器返回500错误: {error_msg}")
                        if retry < max_retries:
                            continue  # 尝试重试
                        else:
                            logging.error("多次尝试后仍返回500错误，Instagram服务器可能暂时不可用")
                            return False
                    
                    # 处理其他常见错误
                    logging.error(f"Instagram API评论调用失败: {error_msg}")
                    
                    # 记录特定类型的错误
                    if "login_required" in error_msg.lower():
                        logging.error("错误原因: 需要重新登录")
                        return False
                    elif "feedback_required" in error_msg.lower():
                        logging.error("错误原因: 可能被检测为垃圾评论或评论频率过高")
                        return False
                    elif "media_comment_disabled" in error_msg.lower():
                        logging.error("错误原因: 该帖子已禁用评论功能")
                        return False
                    elif "spam" in error_msg.lower():
                        logging.error("错误原因: 评论被判定为垃圾信息")
                        return False
                    elif "media not found" in error_msg.lower():
                        logging.error("错误原因: 帖子不存在或已被删除")
                        return False
                    elif "max retries exceeded" in error_msg.lower():
                        if "500" in error_msg:
                            logging.error("Instagram服务器内部错误(500)，服务器可能过载或API已变更")
                        else:
                            logging.error("网络请求失败，请检查网络连接")
                        # 对于超过重试次数的错误，我们也尝试再重试一次
                        if retry < max_retries:
                            continue
                        return False
                    
                    # 其他错误，如果还有重试机会，继续尝试
                    if retry < max_retries:
                        continue
                    return False
            
            logging.error("所有重试均失败，无法发表评论")
            return False
                
        except Exception as e:
            logging.error(f"评论发布过程中出现错误: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    
    def add_comment_template(self, template):
        """添加评论模板"""
        if template not in self.comment_templates:
            self.comment_templates.append(template)
            self.config['templates'] = self.comment_templates
            self.save_config()
            logging.info(f"添加评论模板成功: {template}")
            return True
        return False
    
    def remove_comment_template(self, index):
        """移除评论模板"""
        if 0 <= index < len(self.comment_templates):
            template = self.comment_templates.pop(index)
            self.config['templates'] = self.comment_templates
            self.save_config()
            logging.info(f"移除评论模板成功: {template}")
            return True
        return False
    
    def toggle_auto_comment(self):
        """切换自动评论开关"""
        self.config['auto_comment'] = not self.config.get('auto_comment', False)
        self.save_config()
        status = "开启" if self.config['auto_comment'] else "关闭"
        logging.info(f"自动评论功能已{status}")
        return self.config['auto_comment']
    
    def set_comment_delay(self, min_delay, max_delay):
        """设置评论延迟范围"""
        if min_delay > 0 and max_delay >= min_delay:
            self.config['auto_comment_delay'] = [min_delay, max_delay]
            self.save_config()
            logging.info(f"评论延迟已设置为 {min_delay}-{max_delay} 秒")
            return True
        return False
    
    def toggle_comment_variation(self):
        """切换评论变异开关"""
        self.config['comment_variation'] = not self.config.get('comment_variation', True)
        self.save_config()
        status = "开启" if self.config['comment_variation'] else "关闭"
        logging.info(f"评论变异功能已{status}")
        return self.config['comment_variation']
    
    def start_monitoring(self):
        """开始监控"""
        if not self.logged_in:
            if not self.login():
                return False
        
        logging.info("开始监控博主动态...")
        if self.config.get('auto_comment'):
            logging.info("⚠️ 全自动评论模式已开启，系统将自动为新帖子发表评论")
        
        try:
            while True:
                self.check_new_posts()
                time.sleep(self.config['check_interval'])
        except KeyboardInterrupt:
            logging.info("监控已停止")
        
        return True

    def generate_ai_comment(self, post_content):
        """基于帖子内容使用AI生成相关评论"""
        try:
            # 提取帖子关键词
            keywords = self.extract_keywords(post_content)
            # 根据关键词生成相关评论
            comment = self.ai_comment_generator.generate(keywords)
            return comment
        except Exception as e:
            logging.error(f"AI评论生成失败: {str(e)}")
            return random.choice(self.comment_templates)

    def is_active_time(self):
        """判断当前是否为设定的活跃时间"""
        now = datetime.now()
        weekday = now.weekday()
        hour = now.hour
        
        # 根据用户设置的活跃时间进行判断
        active_times = self.config.get('active_times', {})
        if str(weekday) in active_times:
            active_hours = active_times[str(weekday)]
            return hour in active_hours
        
        # 默认工作时间活跃
        return 8 <= hour <= 22

    def learn_behavior_pattern(self, action_type, success):
        """学习行为模式，根据操作成功率调整策略"""
        if action_type not in self.behavior_stats:
            self.behavior_stats[action_type] = {"total": 0, "success": 0}
            
        self.behavior_stats[action_type]["total"] += 1
        if success:
            self.behavior_stats[action_type]["success"] += 1
            
        # 计算成功率
        success_rate = self.behavior_stats[action_type]["success"] / self.behavior_stats[action_type]["total"]
        
        # 如果成功率低于阈值，自动调整策略
        if success_rate < 0.7:  # 70%阈值
            self.adjust_strategy(action_type)

    def cross_platform_posting(self, comment, platforms):
        """跨平台发布评论，增加自然度"""
        results = {}
        for platform in platforms:
            if platform == "instagram":
                results[platform] = self.post_comment(self.media_id, comment)
            elif platform == "twitter":
                results[platform] = self.twitter_client.post_comment(comment)
            # 其他平台...
        
        return results

    def analyze_safety_risks(self):
        """分析当前操作的安全风险"""
        risk_factors = {
            "comment_frequency": 0,
            "content_repetition": 0,
            "account_age": 0,
            "total_risk": 0
        }
        
        # 检查评论频率
        comments_last_hour = self.get_comments_count_last_hour()
        if comments_last_hour > 10:
            risk_factors["comment_frequency"] = min(comments_last_hour / 5, 10)
            
        # 检查内容重复度
        repetition_score = self.analyze_content_repetition()
        risk_factors["content_repetition"] = repetition_score
        
        # 计算总风险
        risk_factors["total_risk"] = sum([v for k, v in risk_factors.items() if k != "total_risk"])
        
        return risk_factors

def main():
    monitor = InstagramMonitor()
    
    while True:
        print("\n=== Instagram博主监控工具 ===")
        print("1. 登录Instagram账号")
        print("2. 添加监控博主")
        print("3. 移除监控博主")
        print("4. 查看监控博主列表")
        print("5. 添加评论模板")
        print("6. 查看/删除评论模板")
        print("7. 设置检查间隔(秒)")
        print(f"8. {'关闭' if monitor.config.get('auto_comment') else '开启'}自动评论")
        print("9. 自动评论高级设置")
        print("10. 开始监控")
        print("0. 退出")
        
        choice = input("\n请选择: ")
        
        if choice == '1':
            username = input("Instagram用户名: ")
            password = input("Instagram密码: ")
            monitor.login(username, password)
        
        elif choice == '2':
            if not monitor.logged_in:
                print("请先登录Instagram账号")
                continue
            username = input("请输入博主用户名: ")
            monitor.add_blogger(username)
        
        elif choice == '3':
            if not monitor.config['bloggers']:
                print("监控列表为空")
                continue
            print("当前监控博主:")
            for i, blogger in enumerate(monitor.config['bloggers'], 1):
                print(f"{i}. {blogger}")
            try:
                index = int(input("请输入要移除的博主序号: ")) - 1
                if 0 <= index < len(monitor.config['bloggers']):
                    monitor.remove_blogger(monitor.config['bloggers'][index])
                else:
                    print("无效序号")
            except ValueError:
                print("请输入有效数字")
        
        elif choice == '4':
            if not monitor.config['bloggers']:
                print("监控列表为空")
            else:
                print("当前监控博主:")
                for i, blogger in enumerate(monitor.config['bloggers'], 1):
                    print(f"{i}. {blogger}")
        
        elif choice == '5':
            print("添加评论模板 (提示: 可以使用 {content} 作为占位符代表帖子内容)")
            template = input("请输入新的评论模板: ")
            monitor.add_comment_template(template)
            print("添加成功")
        
        elif choice == '6':
            if not monitor.comment_templates:
                print("评论模板为空")
                continue
            print("当前评论模板:")
            for i, template in enumerate(monitor.comment_templates, 1):
                print(f"{i}. {template}")
            try:
                action = input("输入序号删除模板，或按Enter返回: ")
                if action.strip():
                    index = int(action) - 1
                    if monitor.remove_comment_template(index):
                        print("删除成功")
                    else:
                        print("无效序号")
            except ValueError:
                print("请输入有效数字")
        
        elif choice == '7':
            try:
                interval = int(input("请输入检查间隔(秒): "))
                if interval < 10:
                    print("间隔不能小于10秒")
                else:
                    monitor.config['check_interval'] = interval
                    monitor.save_config()
                    print(f"检查间隔已设置为 {interval} 秒")
            except ValueError:
                print("请输入有效数字")
                
        elif choice == '8':
            auto_comment = monitor.toggle_auto_comment()
            status = "开启" if auto_comment else "关闭"
            print(f"自动评论功能已{status}")
            if auto_comment:
                print("⚠️ 警告：自动评论可能违反Instagram政策，可能导致账号被限制或封禁")
                
        elif choice == '9':
            print("\n=== 自动评论高级设置 ===")
            print("1. 设置评论延迟")
            print(f"2. {'关闭' if monitor.config.get('comment_variation', True) else '开启'}评论变异功能")
            print("3. 返回主菜单")
            
            subchoice = input("\n请选择: ")
            
            if subchoice == '1':
                try:
                    min_delay = float(input("请输入最小延迟秒数: "))
                    max_delay = float(input("请输入最大延迟秒数: "))
                    if monitor.set_comment_delay(min_delay, max_delay):
                        print(f"评论延迟已设置为 {min_delay}-{max_delay} 秒")
                    else:
                        print("设置失败，请确保最小延迟大于0且不大于最大延迟")
                except ValueError:
                    print("请输入有效数字")
            
            elif subchoice == '2':
                variation = monitor.toggle_comment_variation()
                status = "开启" if variation else "关闭"
                print(f"评论变异功能已{status}")
                if variation:
                    print("评论变异将对评论内容进行细微调整，以降低自动化特征")
        
        elif choice == '10':
            if not monitor.logged_in:
                print("请先登录Instagram账号")
                continue
            if not monitor.config['bloggers']:
                print("请先添加监控博主")
                continue
            if monitor.config.get('auto_comment') and not monitor.comment_templates:
                print("自动评论模式需要至少一个评论模板")
                continue
            monitor.start_monitoring()
        
        elif choice == '0':
            print("已退出程序")
            break
        
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    main() 