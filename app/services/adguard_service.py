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
        # 使用配置中的认证信息
        auth_str = f"{self.config.auth_username}:{self.config.auth_password}"
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
        
        # 静默处理请求，不输出日志
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json,
                params=params,
                timeout=10  # 设置超时时间
            )

            # 静默处理响应，不输出日志
            
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
                # 对于成功的响应，即使不是JSON格式也返回空字典
                if 200 <= response.status_code < 300:
                    # 静默处理非JSON响应
                    return {}
                # 对于错误响应，提供更详细的错误信息
                error_content = response.content.decode('utf-8', errors='replace')[:200]
                raise Exception(f"无法解析服务器响应：响应不是有效的JSON格式。状态码：{response.status_code}，内容：{error_content}...")
            
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

    def get_query_log(self, older_than: Optional[str] = None, limit: int = 100) -> Dict:
        """获取查询日志

        Args:
            older_than: 用于分页，获取比指定时间更早的日志
            limit: 返回的日志条目数

        Returns:
            查询日志数据
        """
        params = {'limit': limit}
        if older_than:
            params['older_than'] = older_than
        return self._make_request('GET', '/querylog', params=params)
    
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
        # 静默处理客户端创建请求
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
        # 如果没有提供ids，使用名称作为唯一标识
        if ids is None:
            # 使用客户端名称作为ID，确保唯一性
            # 使用连字符替代下划线，因为AdGuardHome不接受下划线作为客户端ID
            ids = [f"default-{name}"]
            print(f"未提供客户端ID，使用名称生成唯一ID: {ids}")
            
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
        
        print(f"准备创建AdGuardHome客户端，数据: {data}")
        
        try:
            result = self._make_request('POST', '/control/clients/add', json=data)
            print(f"成功创建AdGuardHome客户端: {result}")
            return result
        except Exception as e:
            print(f"创建AdGuardHome客户端失败: {str(e)}")
            raise
    
    def get_blocked_services_all(self) -> Dict:
        """获取所有可用的阻止服务列表
        
        根据AdGuardHome API文档，使用/control/blocked_services/all接口获取所有可用的阻止服务及其详细信息
        
        Returns:
            包含所有可用阻止服务的信息，包括图标、ID、名称和规则
        """
        return self._make_request('GET', '/blocked_services/all')
    
    def get_blocked_services(self) -> Dict:
        """获取当前的阻止服务配置
        
        根据AdGuardHome API文档，使用/control/blocked_services/get接口获取当前的阻止服务配置
        
        Returns:
            当前的阻止服务配置，包括计划和服务ID列表
        """
        return self._make_request('GET', '/blocked_services/get')
    
    def update_blocked_services(self, schedule: Optional[Dict] = None, ids: List[str] = None) -> Dict:
        """更新阻止服务配置
        
        根据AdGuardHome API文档，使用PUT /control/blocked_services/update接口更新阻止服务配置
        
        Args:
            schedule: 阻止服务的计划配置，符合Schedule模式
            ids: 要阻止的服务ID列表
            
        Returns:
            更新操作的响应数据
        """
        data = {}
        if ids is not None:
            data['ids'] = ids
        if schedule is not None:
            data['schedule'] = schedule
            
        return self._make_request('PUT', '/blocked_services/update', json=data)
    
    def update_client(
        self,
        name: str,
        ids: List[str],
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
        """更新现有的AdGuardHome客户端
        
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
            更新后的客户端信息
        """
        client_data = {
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
        
        # 添加可选参数
        if safe_search is not None:
            client_data["safe_search"] = safe_search
        if blocked_services is not None:
            client_data["blocked_services"] = blocked_services
        if upstreams is not None:
            client_data["upstreams"] = upstreams
        if tags is not None:
            client_data["tags"] = tags
        
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
            print("尝试获取AdGuardHome服务器状态信息...")
            status = self._make_request('GET', '/status')
            print(f"成功获取AdGuardHome服务器状态信息: {status}")
            return status
        except Exception as e:
            print(f"获取AdGuardHome服务器状态信息失败: {str(e)}")
            return None
        
    def check_connection(self) -> bool:
        """检查与AdGuardHome服务器的连接和认证状态

        Returns:
            bool: 连接和认证是否成功
        """
        try:
            print("开始检查AdGuardHome连接状态...")
            # 首先验证配置
            is_valid, error_msg = self.config.validate()
            if not is_valid:
                print(f"AdGuardHome配置验证失败: {error_msg}")
                return False
                
            # 尝试获取状态信息来验证连接和认证
            print(f"尝试连接AdGuardHome服务器: {self.base_url}")
            status = self.get_status()
            if status is not None:
                print(f"成功连接到AdGuardHome服务器，版本: {status.get('version', '未知')}")
                return True
            else:
                print("连接AdGuardHome服务器失败: 获取状态信息返回None")
                return False
        except Exception as e:
             print(f"连接AdGuardHome服务器时发生异常: {str(e)}")
             return False
             
    def get_access_list(self) -> Dict:
        """获取AdGuardHome访问控制列表
        
        获取当前的访问控制列表，包括允许的客户端和拒绝的客户端
        
        Returns:
            Dict: 包含allowed_clients和disallowed_clients的字典
        """
        try:
            return self._make_request('GET', '/access/list')
        except Exception as e:
            print(f"获取访问控制列表失败: {str(e)}")
            return {"allowed_clients": [], "disallowed_clients": [], "blocked_hosts": []}
    
    def set_access_list(self, allowed_clients: List[str] = None, disallowed_clients: List[str] = None, blocked_hosts: List[str] = None) -> Dict:
        """设置AdGuardHome访问控制列表
        
        更新访问控制列表，包括允许的客户端和拒绝的客户端
        
        Args:
            allowed_clients: 允许的客户端列表（IP地址、CIDR或客户端ID）
            disallowed_clients: 拒绝的客户端列表（IP地址、CIDR或客户端ID）
            blocked_hosts: 阻止的主机列表
            
        Returns:
            Dict: API响应数据
        """
        data = {}
        if allowed_clients is not None:
            data["allowed_clients"] = allowed_clients
        if disallowed_clients is not None:
            data["disallowed_clients"] = disallowed_clients
        if blocked_hosts is not None:
            data["blocked_hosts"] = blocked_hosts
            
        # 如果没有提供任何参数，先获取当前配置
        if not data:
            current = self.get_access_list()
            data = {
                "allowed_clients": current.get("allowed_clients", []),
                "disallowed_clients": current.get("disallowed_clients", []),
                "blocked_hosts": current.get("blocked_hosts", [])
            }
            
        return self._make_request('POST', '/access/set', json=data)
    
    def get_stats(self) -> Dict:
        """获取AdGuardHome统计数据
        
        获取DNS服务器的统计信息，包括查询数量、阻止数量、客户端统计等
        
        Returns:
            Dict: 包含统计数据的字典，包括：
                - num_dns_queries: 总DNS查询数
                - num_blocked_filtering: 被过滤规则阻止的请求数
                - top_clients: 客户端请求排行
                - 其他统计信息
        """
        try:
            return self._make_request('GET', '/stats')
        except Exception as e:
            print(f"获取AdGuardHome统计数据失败: {str(e)}")
            return {}