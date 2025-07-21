import requests
from typing import Dict, List, Optional, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.models.adguard_config import AdGuardConfig

class AdGuardService:
    """AdGuardHome API服务类
    
    用于处理所有与AdGuardHome的API交互，包括客户端管理、过滤规则配置等。
    所有方法都会自动从数据库获取API配置信息。
    """
    
    def __init__(self, config: Optional[AdGuardConfig] = None):
        """
        初始化AdGuardHome服务实例
        
        Args:
            config: AdGuardHome配置对象，如果不提供则从数据库获取
            
        Raises:
            Exception: 当配置验证失败时抛出异常
        """
        self.config = config or AdGuardConfig.get_config()
        
        # 验证配置
        is_valid, error_msg = self.config.validate()
        if not is_valid:
            raise Exception(f'AdGuardHome配置无效：{error_msg}')
            
        # 设置API基础URL，不自动添加/control前缀
        self.base_url = self.config.api_base_url.rstrip('/')
        
        # 设置Basic认证头部
        import base64
        # 临时使用硬编码的认证信息
        auth_str = "yuanhu:yuanhu66"
        auth_bytes = auth_str.encode('utf-8')
        auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
        self.headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json'
        }
        
        # 初始化会话
        self.session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=3,  # 最多重试3次
            backoff_factor=0.5,  # 重试间隔时间
            status_forcelist=[500, 502, 503, 504]  # 这些状态码会触发重试
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        json: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """发送HTTP请求到AdGuardHome API
        
        Args:
            method: HTTP方法（GET、POST、PUT、DELETE）
            endpoint: API端点路径（不包含基础URL）
            json: 请求体数据（可选）
            params: URL查询参数（可选）
            
        Returns:
            API响应的JSON数据
            
        Raises:
            Exception: 当API请求失败时，包含详细的错误信息
        """
        # 确保endpoint以/开头
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
            
        # 对于所有API，添加/control前缀（除非已经有了）
        if not endpoint.startswith('/control/'):
            endpoint = '/control' + endpoint
            
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json,
                params=params,
                timeout=10  # 设置超时时间
            )
            
            # 处理常见的HTTP错误
            if response.status_code == 401:
                raise Exception("认证失败：请检查用户名和密码是否正确")
            elif response.status_code == 403:
                raise Exception("权限不足：当前用户没有执行此操作的权限")
            elif response.status_code == 404:
                raise Exception(f"API端点不存在：{endpoint}")
            elif response.status_code >= 500:
                raise Exception(f"AdGuardHome服务器错误（状态码：{response.status_code}）")
                
            # 尝试解析响应数据
            try:
                if response.content:
                    data = response.json()
                    if isinstance(data, dict) and 'error' in data:
                        raise Exception(f"API错误：{data['error']}")
                    return data
                return {}
            except ValueError:
                if 200 <= response.status_code < 300:
                    return {}
                raise Exception("无法解析服务器响应：响应不是有效的JSON格式")
            
        except requests.exceptions.ConnectionError as e:
            raise Exception(f"无法连接到AdGuardHome服务器（{self.base_url}）：{str(e)}")
        except requests.exceptions.Timeout as e:
            raise Exception(f"连接AdGuardHome服务器超时（{self.base_url}）：{str(e)}")
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                error_msg = f"状态码：{e.response.status_code}"
                try:
                    error_data = e.response.json()
                    if isinstance(error_data, dict) and 'error' in error_data:
                        error_msg += f"，错误信息：{error_data['error']}"
                except:
                    pass
                raise Exception(f"请求AdGuardHome API失败：{error_msg}")
            raise Exception(f"请求AdGuardHome API失败：{str(e)}")
    
    def create_client(
        self,
        name: str,
        ids: Optional[List[str]] = None,
        use_global_settings: bool = True,
        filtering_enabled: bool = True,
        safebrowsing_enabled: bool = False,
        parental_enabled: bool = False,
        safe_search: Optional[Dict] = None,
        use_global_blocked_services: bool = True,
        blocked_services: Optional[List[str]] = None,
        upstreams: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        ignore_querylog: bool = False,
        ignore_statistics: bool = False
    ) -> Dict:
        """创建新的AdGuardHome客户端
        
        Args:
            name: 客户端名称
            ids: 客户端标识列表（可以是IP、CIDR、MAC或客户端ID）
            use_global_settings: 是否使用全局设置
            filtering_enabled: 是否启用过滤
            safebrowsing_enabled: 是否启用安全浏览
            parental_enabled: 是否启用家长控制
            safe_search: 安全搜索配置，包含各搜索引擎的启用状态
            use_global_blocked_services: 是否使用全局服务屏蔽设置
            blocked_services: 要屏蔽的服务列表
            upstreams: 上游DNS服务器列表
            tags: 客户端标签列表
            ignore_querylog: 是否忽略查询日志
            ignore_statistics: 是否忽略统计信息
            
        Returns:
            创建成功的客户端信息
        """
        # 如果没有提供ids，使用默认的IP地址
        if ids is None:
            ids = ['192.168.31.1']
            
        data = {
            "name": name,
            "ids": ids,
            "use_global_settings": use_global_settings,
            "filtering_enabled": filtering_enabled,
            "safebrowsing_enabled": safebrowsing_enabled,
            "parental_enabled": parental_enabled,
            "use_global_blocked_services": use_global_blocked_services,
            "ignore_querylog": ignore_querylog,
            "ignore_statistics": ignore_statistics
        }
        
        if safe_search is not None:
            data["safe_search"] = safe_search
        if blocked_services is not None:
            data["blocked_services"] = blocked_services
        if upstreams is not None:
            data["upstreams"] = upstreams
        if tags is not None:
            data["tags"] = tags
            
        return self._make_request('POST', '/control/clients/add', json=data)
    
    def update_client(
        self,
        name: str,
        ids: List[str],
        use_global_settings: bool = True,
        filtering_enabled: bool = True,
        safebrowsing_enabled: bool = False,
        parental_enabled: bool = False
    ) -> Dict:
        """更新现有的AdGuardHome客户端
        
        Args:
            name: 客户端名称
            ids: 客户端标识列表（可以是IP、CIDR、MAC或客户端ID）
            use_global_settings: 是否使用全局设置
            filtering_enabled: 是否启用过滤
            safebrowsing_enabled: 是否启用安全浏览
            parental_enabled: 是否启用家长控制
            
        Returns:
            更新后的客户端信息
        """
        client_data = {
            "name": name,
            "ids": ids,
            "use_global_settings": use_global_settings,
            "filtering_enabled": filtering_enabled,
            "safebrowsing_enabled": safebrowsing_enabled,
            "parental_enabled": parental_enabled
        }
        
        request_body = {
            "name": name,
            "data": client_data
        }
        
        return self._make_request('POST', '/control/clients/update', json=request_body)
    
    def delete_client(self, name: str) -> Dict:
        """删除AdGuardHome客户端
        
        Args:
            name: 要删除的客户端名称
            
        Returns:
            删除操作的响应数据
            
        Raises:
            Exception: 当客户端不存在时抛出异常
        """
        # 先检查客户端是否存在
        client = self.find_client(name)
        if client is None:
            raise Exception(f"客户端 {name} 不存在，无法删除")
            
        data = {"name": name}
        return self._make_request('POST', '/control/clients/delete', json=data)
    
    def search_clients(
        self,
        search_criteria: Union[str, List[str]]
    ) -> Dict:
        """搜索AdGuardHome客户端
        
        Args:
            search_criteria: 搜索条件，可以是单个字符串或字符串列表
                           支持IP地址、CIDR、MAC地址或客户端ID
            
        Returns:
            匹配的客户端列表
        """
        if isinstance(search_criteria, str):
            search_criteria = [search_criteria]
            
        data = {"criteria": search_criteria}
        return self._make_request('POST', '/control/clients/find', json=data)
        
    def find_client(self, name: str) -> Optional[Dict]:
        """根据名称查找AdGuardHome客户端
        
        Args:
            name: 客户端名称
            
        Returns:
            Optional[Dict]: 客户端信息，如果未找到则返回None
        """
        try:
            # 获取所有客户端列表
            response_data = self._make_request('GET', '/control/clients')
            clients = response_data.get('clients', [])
            
            # 查找匹配名称的客户端
            for client in clients:
                if client.get('name') == name:
                    return client
                    
            return None
        except Exception:
            return None
    
    def get_status(self) -> Optional[Dict]:
        """获取AdGuardHome服务器状态和版本信息
        
        Returns:
            Optional[Dict]: 包含服务器状态和版本信息的字典，如果请求失败则返回None
        """
        try:
            return self._make_request('GET', '/status')
        except Exception:
            return None
        
    def check_connection(self) -> bool:
        """检查与AdGuardHome服务器的连接和认证状态

        Returns:
            bool: 连接和认证是否成功
        """
        try:
            # 首先验证配置
            is_valid, error_msg = self.config.validate()
            if not is_valid:
                return False
                
            # 尝试获取状态信息来验证连接和认证
            status = self.get_status()
            return status is not None
        except Exception:
            return False
                
            # 尝试获取状态信息来验证连接和认证
            self.get_status()
            return True
        except Exception:
            return False