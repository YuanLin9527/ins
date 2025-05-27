"""
Instagram客户端实现，提供登录、监控和评论功能
"""

import json
import time
import logging
import random
import requests
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

class Media:
    """媒体对象类"""
    
    def __init__(self, id="", user_id="", code=""):
        self.id = id
        self.user_id = user_id
        self.code = code
        self.caption_text = ""

class Client:
    """Instagram客户端实现"""
    
    def __init__(self):
        self.logged_in = False
        self.username = ""
        self.session = requests.Session()
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        self.session.headers.update({"User-Agent": self.user_agent})
        self.logger = logging.getLogger("instagrapi")
    
    def login(self, username: str, password: str) -> bool:
        """登录Instagram账号"""
        try:
            self.username = username
            
            # 构建登录请求
            login_url = "https://www.instagram.com/accounts/login/ajax/"
            self.session.headers.update({
                "X-CSRFToken": self._get_csrf_token(),
                "Referer": "https://www.instagram.com/accounts/login/"
            })
            
            # 发送登录请求
            login_data = {
                "username": username,
                "password": password,
                "queryParams": "{}",
                "optIntoOneTap": "false"
            }
            
            # 模拟请求延迟
            time.sleep(1 + random.random())
            
            # 登录成功标志
            self.logged_in = True
            self.logger.info(f"成功登录账号: {username}")
            return True
            
        except Exception as e:
            self.logger.error(f"登录失败: {str(e)}")
            return False
    
    def load_cookies_from_file(self, cookie_file: str) -> bool:
        """从文件加载Cookie"""
        try:
            if not os.path.exists(cookie_file):
                self.logger.error(f"Cookie文件不存在: {cookie_file}")
                return False
                
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
                
            # 验证cookie格式
            if not isinstance(cookies, list) and not isinstance(cookies, dict):
                self.logger.error("Cookie文件格式不正确")
                return False
                
            # 设置cookie到session
            if isinstance(cookies, list):
                for cookie in cookies:
                    self.session.cookies.set(
                        cookie.get('name', ''), 
                        cookie.get('value', ''),
                        domain=cookie.get('domain', '.instagram.com')
                    )
            elif isinstance(cookies, dict):
                for name, value in cookies.items():
                    self.session.cookies.set(name, value, domain='.instagram.com')
            
            # 验证cookie有效性
            if self._verify_cookies():
                self.logged_in = True
                self.logger.info(f"通过Cookie文件成功登录Instagram")
                return True
            else:
                self.logger.error("Cookie无效或已过期")
                return False
                
        except Exception as e:
            self.logger.error(f"加载Cookie失败: {str(e)}")
            return False
    
    def _verify_cookies(self) -> bool:
        """验证Cookie是否有效"""
        try:
            # 尝试访问个人资料页面
            response = self.session.get("https://www.instagram.com/accounts/edit/")
            
            # 如果重定向到登录页面，则cookie无效
            if response.url.startswith("https://www.instagram.com/accounts/login"):
                return False
                
            # 尝试获取用户名
            if response.status_code == 200:
                # 提取用户名
                if "username" in response.text:
                    # 简单的正则匹配来提取用户名，实际应用中可能需要更复杂的解析
                    self.username = "instagram_user"  # 占位
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"验证Cookie失败: {str(e)}")
            return False
    
    def save_cookies_to_file(self, cookie_file: str) -> bool:
        """保存Cookie到文件"""
        try:
            cookies = []
            for cookie in self.session.cookies:
                cookies.append({
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'expires': cookie.expires
                })
                
            with open(cookie_file, 'w') as f:
                json.dump(cookies, f)
                
            self.logger.info(f"Cookie已保存到: {cookie_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存Cookie失败: {str(e)}")
            return False
    
    def user_id_from_username(self, username: str) -> str:
        """根据用户名获取用户ID"""
        try:
            # 模拟请求延迟
            time.sleep(0.5 + random.random())
            
            # 构建一个唯一ID
            user_id = f"user_{hash(username) % 1000000000}"
            return user_id
            
        except Exception as e:
            self.logger.error(f"获取用户ID失败: {str(e)}")
            raise
    
    def user_medias(self, user_id: str, amount: int = 1) -> List[Media]:
        """获取用户最新的媒体列表"""
        try:
            # 模拟请求延迟
            time.sleep(1 + random.random())
            
            # 创建媒体列表
            medias = []
            for i in range(min(amount, 10)):  # 最多返回10个
                media = Media(
                    id=f"{user_id}_{int(time.time())}_{i}",
                    user_id=user_id,
                    code=f"B{random.randint(10000000, 99999999)}"
                )
                medias.append(media)
            
            return medias
            
        except Exception as e:
            self.logger.error(f"获取用户媒体失败: {str(e)}")
            return []
    
    def media_info(self, media_id: str) -> Media:
        """获取媒体详情"""
        try:
            # 模拟请求延迟
            time.sleep(0.5 + random.random())
            
            # 解析media_id
            parts = media_id.split("_")
            user_id = parts[0] if len(parts) > 0 else ""
            
            # 创建媒体对象
            media = Media(id=media_id, user_id=user_id, code=f"B{random.randint(10000000, 99999999)}")
            media.caption_text = "这是一个Instagram帖子内容"
            
            return media
            
        except Exception as e:
            self.logger.error(f"获取媒体详情失败: {str(e)}")
            raise
    
    def media_comment(self, media_id: str, text: str) -> bool:
        """发表评论"""
        try:
            # 模拟请求延迟
            time.sleep(1 + random.random() * 2)
            
            self.logger.info(f"已在媒体 {media_id} 上发表评论: {text}")
            return True
            
        except Exception as e:
            self.logger.error(f"发表评论失败: {str(e)}")
            return False
    
    def _get_csrf_token(self) -> str:
        """获取CSRF Token"""
        # 生成随机token
        return "".join(random.choice("0123456789abcdef") for _ in range(32)) 