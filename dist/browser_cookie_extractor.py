"""
用于从浏览器中提取Instagram的Cookie
"""

import os
import json
import logging
import sqlite3
from datetime import datetime
import base64
import tempfile
import shutil
from pathlib import Path

try:
    import win32crypt
    from Crypto.Cipher import AES
    EXTRACTOR_AVAILABLE = True
except ImportError:
    EXTRACTOR_AVAILABLE = False

class BrowserCookieExtractor:
    """从浏览器提取Cookie的工具类"""
    
    def __init__(self):
        self.available = EXTRACTOR_AVAILABLE
    
    def extract_from_chrome(self):
        """从Chrome浏览器提取Instagram的Cookie"""
        if not self.available:
            return None
            
        try:
            # 获取用户数据路径
            user_data_path = os.path.join(os.environ["USERPROFILE"], 
                                          "AppData", "Local", 
                                          "Google", "Chrome", 
                                          "User Data", "Default")
            
            # 创建临时文件来存储Cookie数据库的副本
            cookie_file = os.path.join(user_data_path, "Network", "Cookies")
            
            if not os.path.exists(cookie_file):
                cookie_file = os.path.join(user_data_path, "Cookies")
            
            if not os.path.exists(cookie_file):
                logging.error("找不到Chrome Cookie文件")
                return None
                
            # 创建临时文件以复制Cookie数据库
            temp_cookie_file = tempfile.NamedTemporaryFile(delete=False).name
            shutil.copy2(cookie_file, temp_cookie_file)
            
            # 连接到Cookie数据库
            conn = sqlite3.connect(temp_cookie_file)
            cursor = conn.cursor()
            
            # 查询Instagram相关的Cookie
            cursor.execute("""
                SELECT name, value, encrypted_value, host_key, path, expires_utc
                FROM cookies
                WHERE host_key LIKE '%instagram.com%'
            """)
            
            cookies = []
            
            # 获取加密密钥
            state_file = os.path.join(user_data_path, "Local State")
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.loads(f.read())
            
            key = base64.b64decode(state_data["os_crypt"]["encrypted_key"])[5:]
            key = win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
            
            # 处理获取的Cookie
            for row in cursor.fetchall():
                name, value, encrypted_value, host_key, path, expires_utc = row
                
                # 如果是加密的值，解密它
                if value == "" and encrypted_value:
                    try:
                        # 解密
                        iv = encrypted_value[3:15]
                        encrypted_value = encrypted_value[15:]
                        cipher = AES.new(key, AES.MODE_GCM, iv)
                        decrypted_value = cipher.decrypt(encrypted_value)
                        decrypted_value = decrypted_value[:-16].decode()  # 去除尾部的验证值
                        value = decrypted_value
                    except Exception as e:
                        logging.error(f"解密Cookie值失败: {str(e)}")
                        continue
                
                # 构建Cookie对象
                cookie = {
                    "name": name,
                    "value": value,
                    "domain": host_key,
                    "path": path,
                    "expires": None if expires_utc == 0 else expires_utc
                }
                
                cookies.append(cookie)
            
            # 关闭数据库连接
            cursor.close()
            conn.close()
            
            # 删除临时文件
            try:
                os.unlink(temp_cookie_file)
            except:
                pass
                
            if not cookies:
                logging.error("未找到Instagram相关的Cookie")
                return None
                
            # 保存Cookie到文件
            temp_json = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            temp_json.close()
            
            with open(temp_json.name, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
                
            logging.info(f"已从Chrome提取到{len(cookies)}个Cookie")
            return temp_json.name
            
        except Exception as e:
            logging.error(f"从Chrome提取Cookie时发生错误: {str(e)}")
            return None
            
    def extract(self):
        """尝试从各种浏览器提取Cookie"""
        if not self.available:
            logging.error("Cookie提取器不可用，缺少必要依赖")
            return None
            
        # 先尝试Chrome
        chrome_cookies = self.extract_from_chrome()
        if chrome_cookies:
            return chrome_cookies
            
        # 如果需要，这里可以添加其他浏览器的支持
        
        logging.error("从所有支持的浏览器中均未提取到Cookie")
        return None




