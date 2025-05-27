"""
Mock instagrapi模块，用于打包测试
"""

class Client:
    """模拟的Instagram客户端"""
    
    def __init__(self):
        self.logged_in = False
        print("已初始化Mock Instagram客户端")
    
    def login(self, username, password):
        """模拟登录功能"""
        self.logged_in = True
        print(f"已模拟登录Instagram账号: {username}")
        return True
    
    def user_id_from_username(self, username):
        """模拟获取用户ID"""
        return f"mock_user_id_{username}"
    
    def user_medias(self, user_id, amount=1):
        """模拟获取用户媒体列表"""
        return [Media(id=f"mock_media_{i}", user_id=user_id, code=f"ABC{i}") for i in range(amount)]
    
    def media_info(self, media_id):
        """模拟获取媒体详情"""
        media = Media(id=media_id, user_id="mock_user", code="ABCDEF")
        media.caption_text = "这是一个模拟的Instagram帖子内容"
        return media
    
    def media_comment(self, media_id, text):
        """模拟发表评论"""
        print(f"已模拟在{media_id}上发表评论: {text}")
        return True

class Media:
    """模拟的媒体对象"""
    
    def __init__(self, id, user_id, code):
        self.id = id
        self.user_id = user_id
        self.code = code
        self.caption_text = "" 