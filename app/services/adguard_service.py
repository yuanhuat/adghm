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
                timeout=5  # 减少超时时间，避免批量操作时长时间等待
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

    def get_query_log(self, older_than: Optional[str] = None, limit: int = 100, 
                     offset: Optional[int] = None, search: Optional[str] = None,
                     response_status: Optional[str] = None) -> Dict:
        """获取查询日志

        Args:
            older_than: 用于分页，获取比指定时间更早的日志
            limit: 返回的日志条目数
            offset: 指定页面上第一项的排名编号
            search: 按域名或客户端IP过滤
            response_status: 按响应状态过滤（all, filtered, blocked, blocked_safebrowsing, 
                           blocked_parental, whitelisted, rewritten, safe_search, processed）

        Returns:
            查询日志数据
        """
        params = {'limit': limit}
        if older_than:
            params['older_than'] = older_than
        if offset is not None:
            params['offset'] = offset
        if search:
            params['search'] = search
        if response_status:
            params['response_status'] = response_status
        return self._make_request('GET', '/querylog', params=params)

    def get_query_log_advanced(self, filters: Dict, limit: int = 50, older_than: Optional[str] = None) -> Dict:
        """高级搜索查询日志

        Args:
            filters: 包含所有过滤条件的字典
            limit: 返回的日志条目数
            older_than: 用于分页

        Returns:
            处理后的日志数据和统计信息
        """
        # 构建基础参数
        params = {
            'limit': limit,
            'older_than': older_than if older_than else '',
            'response_status': 'all' # 默认获取所有状态
        }

        # 处理搜索词（域名或客户端）
        search_terms = []
        if filters.get('domain'):
            search_terms.append(filters['domain'])
        if filters.get('client'):
            search_terms.append(filters['client'])
        if search_terms:
            params['search'] = ' '.join(search_terms)

        # 直接调用 /querylog 端点
        raw_logs = self._make_request('GET', '/querylog', params=params)
        
        # 在Python端进行过滤
        filtered_data = self._filter_logs(raw_logs.get('data', []), filters)

        # 计算统计信息
        stats = self._calculate_stats(filtered_data)

        # 获取下一页的 oldest 时间戳
        oldest_timestamp = None
        if filtered_data:
            oldest_timestamp = filtered_data[-1]['time']

        return {
            'data': filtered_data,
            'stats': stats,
            'oldest': oldest_timestamp,
            'has_more': len(raw_logs.get('data', [])) == limit
        }

    def _filter_logs(self, logs: List[Dict], filters: Dict) -> List[Dict]:
        """在Python端根据提供的过滤器过滤日志
        
        Args:
            logs: 从AdGuardHome获取的原始日志列表
            filters: 包含所有过滤条件的字典

        Returns:
            过滤后的日志列表
        """
        if not filters:
            return logs

        from dateutil import parser

        filtered_logs = []
        for log in logs:
            match = True
            
            # 时间范围过滤
            log_time = parser.isoparse(log['time'])
            if filters.get('start_time'):
                start_time = parser.isoparse(filters['start_time'])
                if log_time < start_time:
                    match = False
            if filters.get('end_time'):
                end_time = parser.isoparse(filters['end_time'])
                if log_time > end_time:
                    match = False

            # 查询类型过滤
            if filters.get('query_type') and log['question']['type'] != filters['query_type']:
                match = False
            
            # 阻止状态过滤
            if filters.get('blocked') is not None:
                is_blocked = 'reason' in log and log['reason'] != 'NotFilteredWhiteList'
                if is_blocked != filters['blocked']:
                    match = False
            
            # 阻止原因过滤
            if filters.get('reason') and (not log.get('reason') or filters['reason'].lower() not in log['reason'].lower()):
                match = False

            if match:
                filtered_logs.append(log)
        
        return filtered_logs

    def _calculate_stats(self, logs: List[Dict]) -> Dict:
        """计算过滤后日志的统计信息"""
        total_queries = len(logs)
        blocked_queries = sum(1 for log in logs if 'reason' in log and log['reason'] != 'NotFilteredWhiteList')
        allowed_queries = total_queries - blocked_queries
        block_rate = (blocked_queries / total_queries * 100) if total_queries > 0 else 0
        unique_domains = len(set(log['question']['name'] for log in logs))
        unique_clients = len(set(log['client'] for log in logs))

        # 新增：计算top域名和客户端
        from collections import Counter
        top_domains = dict(Counter(log['question']['name'] for log in logs).most_common(10))
        top_clients = dict(Counter(log['client'] for log in logs).most_common(10))

        return {
            'total_queries': total_queries,
            'blocked_queries': blocked_queries,
            'allowed_queries': allowed_queries,
            'block_rate': round(block_rate, 2),
            'unique_domains': unique_domains,
            'unique_clients': unique_clients,
            'top_domains': top_domains,
            'top_clients': top_clients
        }
    
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
            result = self._make_request('POST', '/clients/add', json=data)
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
        
        return self._make_request('POST', '/clients/update', json=request_body)

    def add_client_to_allowlist_with_retry(self, client_id: str, max_retries: int = 3, retry_delay: int = 2) -> bool:
        """添加客户端到允许列表，支持重试机制
        
        Args:
            client_id: 客户端ID
            max_retries: 最大重试次数，默认3次
            retry_delay: 重试间隔（秒），默认2秒
        
        Returns:
            bool: 是否成功添加到允许列表
        """
        import time
        
        for attempt in range(max_retries + 1):
            try:
                # 获取当前的访问控制列表
                access_list = self._make_request('GET', '/access/list')
                allowed_clients = access_list.get('allowed_clients', [])
                
                # 检查客户端是否已在允许列表中
                if client_id in allowed_clients:
                    print(f"客户端 {client_id} 已在允许列表中")
                    return True
                
                # 将新客户端ID添加到允许列表
                allowed_clients.append(client_id)
                
                # 更新访问控制列表
                access_data = {
                    'allowed_clients': allowed_clients,
                    'disallowed_clients': access_list.get('disallowed_clients', []),
                    'blocked_hosts': access_list.get('blocked_hosts', [])
                }
                self._make_request('POST', '/access/set', json=access_data)
                print(f"已将客户端 {client_id} 添加到允许列表")
                return True
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries:
                    print(f"将客户端添加到允许列表失败（第{attempt + 1}次尝试）: {error_msg}，{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                else:
                    print(f"将客户端添加到允许列表失败（已重试{max_retries}次）: {error_msg}")
                    return False
        
        return False

    def create_client_with_retry(
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
        ignore_statistics: bool = False,
        max_retries: int = 3,
        retry_delay: int = 2
    ) -> Dict:
        """带重试机制的创建AdGuardHome客户端方法
        
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
            max_retries: 最大重试次数，默认3次
            retry_delay: 重试间隔（秒），默认2秒
            
        Returns:
            创建成功的客户端信息
            
        Raises:
            Exception: 当重试次数用尽仍然失败时抛出异常
        """
        import time
        
        for attempt in range(max_retries + 1):
            try:
                result = self.create_client(
                    name=name,
                    ids=ids,
                    use_global_settings=use_global_settings,
                    filtering_enabled=filtering_enabled,
                    safebrowsing_enabled=safebrowsing_enabled,
                    parental_enabled=parental_enabled,
                    safe_search=safe_search,
                    use_global_blocked_services=use_global_blocked_services,
                    blocked_services=blocked_services,
                    upstreams=upstreams,
                    tags=tags,
                    ignore_querylog=ignore_querylog,
                    ignore_statistics=ignore_statistics
                )
                print(f"成功创建AdGuardHome客户端: {name}")
                return result
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries:
                    print(f"创建AdGuardHome客户端失败（第{attempt + 1}次尝试）: {error_msg}，{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                else:
                    print(f"创建AdGuardHome客户端最终失败（已重试{max_retries}次）: {error_msg}")
                    raise Exception(f"创建客户端失败，已重试 {max_retries} 次: {error_msg}")
        
        raise Exception(f"创建客户端失败，已重试 {max_retries} 次")

    def delete_client(self, name: str, check_exists: bool = True) -> Dict:
        """删除AdGuardHome客户端
        
        Args:
            name: 要删除的客户端名称
            check_exists: 是否检查客户端是否存在，默认为True
            
        Returns:
            删除操作的响应数据
            
        Raises:
            Exception: 当客户端不存在时抛出异常
        """
        # 可选择性检查客户端是否存在（批量删除时可跳过以提高性能）
        if check_exists:
            client = self.find_client(name)
            if client is None:
                raise Exception(f"客户端 {name} 不存在，无法删除")
            
        data = {"name": name}
        return self._make_request('POST', '/clients/delete', json=data)
    
    def batch_delete_clients(self, names: List[str], skip_missing: bool = True) -> Dict:
        """批量删除AdGuardHome客户端
        
        Args:
            names: 要删除的客户端名称列表
            skip_missing: 是否跳过不存在的客户端，默认为True
            
        Returns:
            批量删除操作的结果统计
        """
        results = {
            'success_count': 0,
            'failed_count': 0,
            'errors': [],
            'details': []
        }
        
        for name in names:
            try:
                # 批量删除时跳过存在性检查以提高性能
                self.delete_client(name, check_exists=False)
                results['success_count'] += 1
                results['details'].append({
                    'name': name,
                    'status': 'success'
                })
            except Exception as e:
                error_msg = str(e)
                # 如果跳过缺失的客户端且错误是客户端不存在
                if skip_missing and ('not found' in error_msg.lower() or '不存在' in error_msg):
                    results['success_count'] += 1
                    results['details'].append({
                        'name': name,
                        'status': 'skipped',
                        'reason': 'client_not_found'
                    })
                else:
                    results['failed_count'] += 1
                    results['errors'].append(f"客户端 {name}: {error_msg}")
                    results['details'].append({
                        'name': name,
                        'status': 'failed',
                        'error': error_msg
                    })
        
        return results
    
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
        return self._make_request('POST', '/clients/find', json=data)
        
    def find_client(self, name: str) -> Optional[Dict]:
        """根据名称查找AdGuardHome客户端
        
        Args:
            name: 客户端名称
            
        Returns:
            Optional[Dict]: 客户端信息，如果未找到则返回None
        """
        try:
            # 获取所有客户端列表
            response_data = self._make_request('GET', '/clients')
            clients = response_data.get('clients', [])
            
            # 查找匹配名称的客户端
            for client in clients:
                if client.get('name') == name:
                    return client
                    
            return None
        except Exception:
            return None
    
    def find_client_name_by_id(self, client_id: str) -> Optional[str]:
        """根据客户端ID查找客户端名称
        
        Args:
            client_id: 客户端ID
            
        Returns:
            Optional[str]: 客户端名称，如果未找到则返回None
        """
        try:
            # 获取所有客户端列表
            response_data = self._make_request('GET', '/clients')
            clients = response_data.get('clients', [])
            
            # 查找包含指定ID的客户端
            for client in clients:
                client_ids = client.get('ids', [])
                if client_id in client_ids:
                    return client.get('name')
                    
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
             
    
    
    def get_all_clients(self) -> List[Dict]:
        """获取所有已配置的AdGuardHome客户端

        Returns:
            List[Dict]: 包含所有客户端信息的列表
        """
        try:
            response = self._make_request('GET', '/clients')
            return response.get('clients', [])
        except Exception as e:
            print(f"获取所有客户端失败: {str(e)}")
            return []

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
    
    # DNS重写相关方法
    def get_rewrite_list(self) -> List[Dict]:
        """获取所有DNS重写规则
        
        Returns:
            List[Dict]: DNS重写规则列表，每个规则包含domain和answer字段
        """
        try:
            result = self._make_request('GET', '/rewrite/list')
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"获取DNS重写规则失败: {str(e)}")
            return []
    
    def add_rewrite_rule(self, domain: str, answer: str) -> Dict:
        """添加DNS重写规则
        
        Args:
            domain: 要重写的域名
            answer: 重写后的地址（IP地址或域名）
            
        Returns:
            Dict: 操作结果
        """
        data = {
            "domain": domain,
            "answer": answer
        }
        try:
            return self._make_request('POST', '/rewrite/add', json=data)
        except Exception as e:
            print(f"添加DNS重写规则失败: {str(e)}")
            raise
    
    def delete_rewrite_rule(self, domain: str, answer: str) -> Dict:
        """删除DNS重写规则
        
        Args:
            domain: 要删除的域名
            answer: 要删除的重写地址
            
        Returns:
            Dict: 操作结果
        """
        data = {
            "domain": domain,
            "answer": answer
        }
        try:
            return self._make_request('POST', '/rewrite/delete', json=data)
        except Exception as e:
            print(f"删除DNS重写规则失败: {str(e)}")
            raise
    
    def update_rewrite_rule(self, target_domain: str, target_answer: str, 
                           new_domain: str, new_answer: str) -> Dict:
        """更新DNS重写规则
        
        Args:
            target_domain: 要更新的原域名
            target_answer: 要更新的原地址
            new_domain: 新的域名
            new_answer: 新的地址
            
        Returns:
            Dict: 操作结果
        """
        data = {
            "target": {
                "domain": target_domain,
                "answer": target_answer
            },
            "update": {
                "domain": new_domain,
                "answer": new_answer
            }
        }
        try:
            return self._make_request('PUT', '/rewrite/update', json=data)
        except Exception as e:
            print(f"更新DNS重写规则失败: {str(e)}")
            raise
    
    def batch_add_rewrite_rules(self, rules: List[Dict]) -> Dict:
        """批量添加DNS重写规则
        
        Args:
            rules: 重写规则列表，每个规则包含domain和answer字段
            
        Returns:
            Dict: 操作结果，包含成功和失败的统计信息
        """
        results = {
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        for rule in rules:
            try:
                domain = rule.get('domain', '').strip()
                answer = rule.get('answer', '').strip()
                
                if not domain or not answer:
                    results["failed"] += 1
                    results["errors"].append(f"无效规则：域名和地址不能为空")
                    continue
                
                self.add_rewrite_rule(domain, answer)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"添加规则 {rule.get('domain', 'unknown')} -> {rule.get('answer', 'unknown')} 失败: {str(e)}")
        
        return results
    
    def batch_delete_rewrite_rules(self, rules: List[Dict]) -> Dict:
        """批量删除DNS重写规则
        
        Args:
            rules: 要删除的重写规则列表，每个规则包含domain和answer字段
            
        Returns:
            Dict: 操作结果，包含成功和失败的统计信息
        """
        results = {
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        for rule in rules:
            try:
                domain = rule.get('domain', '').strip()
                answer = rule.get('answer', '').strip()
                
                if not domain or not answer:
                    results["failed"] += 1
                    results["errors"].append(f"无效规则：域名和地址不能为空")
                    continue
                
                self.delete_rewrite_rule(domain, answer)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"删除规则 {rule.get('domain', 'unknown')} -> {rule.get('answer', 'unknown')} 失败: {str(e)}")
        
        return results
    
    def import_rewrite_rules_from_url(self, url: str) -> Dict:
        """从外部URL导入DNS重写规则
        
        Args:
            url: 规则文件的URL地址
            
        Returns:
            Dict: 导入结果，包含解析的规则数量和导入结果
        """
        try:
            import requests
            from app.models.dns_import_source import DnsImportSource
            from app import db
            
            # 获取远程文件内容
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            content = response.text
            
            # 解析规则
            rules = self._parse_rewrite_rules_from_text(content)
            
            if not rules:
                return {
                    "success": False,
                    "message": "未能从URL中解析出有效的DNS重写规则",
                    "rules_parsed": 0,
                    "import_result": None
                }
            
            # 获取现有规则进行重复检查
            existing_rules = self.get_rewrite_list()
            existing_rules_set = set()
            existing_domain_to_answers = {}
            
            for existing_rule in existing_rules:
                domain = existing_rule.get('domain', '').strip().lower()
                answer = existing_rule.get('answer', '').strip()
                rule_key = f"{domain}:{answer}"
                existing_rules_set.add(rule_key)
                
                # 记录域名对应的所有答案
                if domain not in existing_domain_to_answers:
                    existing_domain_to_answers[domain] = set()
                existing_domain_to_answers[domain].add(answer)
            
            # 过滤重复规则并处理域名重复但IP不同的情况
            filtered_rules = []
            rules_to_delete = []  # 需要删除的旧规则
            skipped_duplicate = 0
            replaced_rules = 0
            
            for rule in rules:
                domain = rule.get('domain', '').strip().lower()
                answer = rule.get('answer', '').strip()
                rule_key = f"{domain}:{answer}"
                
                # 检查完全重复的规则（域名和IP都相同）
                if rule_key in existing_rules_set:
                    skipped_duplicate += 1
                    continue
                
                # 检查域名重复但IP不同的情况
                if domain in existing_domain_to_answers:
                    if answer not in existing_domain_to_answers[domain]:
                        # 域名重复但IP不重复，删除旧规则，导入新规则
                        for old_answer in existing_domain_to_answers[domain]:
                            rules_to_delete.append({
                                'domain': domain,
                                'answer': old_answer
                            })
                        filtered_rules.append(rule)
                        replaced_rules += 1
                    else:
                        # 域名和IP都重复，跳过
                        skipped_duplicate += 1
                else:
                    # 新域名，允许导入
                    filtered_rules.append(rule)
             
            # 先删除需要替换的旧规则
            if rules_to_delete:
                delete_result = self.batch_delete_rewrite_rules(rules_to_delete)
                print(f"删除旧规则结果：成功 {delete_result.get('success', 0)} 条，失败 {delete_result.get('failed', 0)} 条")
            
            # 如果没有需要导入的规则
            if not filtered_rules:
                return {
                    "success": True,
                    "message": f"从URL解析出 {len(rules)} 条规则，但全部为重复规则，跳过导入",
                    "rules_parsed": len(rules),
                    "import_result": {
                        "success": 0,
                        "failed": 0,
                        "skipped_duplicate": skipped_duplicate,
                        "replaced_rules": replaced_rules,
                        "errors": []
                    }
                }
            
            # 批量导入过滤后的规则
            import_result = self.batch_add_rewrite_rules(filtered_rules)
            import_result['skipped_duplicate'] = skipped_duplicate
            import_result['replaced_rules'] = replaced_rules
            
            # 记录导入源信息
            try:
                # 查找或创建导入源记录
                import_source = DnsImportSource.find_by_url(url)
                if not import_source:
                    import_source = DnsImportSource(source_url=url)
                    db.session.add(import_source)
                
                # 更新导入统计（只记录实际导入的规则）
                success_count = import_result.get('success', 0)
                failed_count = import_result.get('failed', 0)
                import_source.update_import_stats(
                    total=len(filtered_rules),
                    success=success_count,
                    failed=failed_count,
                    rules_data=filtered_rules
                )
                
                db.session.commit()
                
            except Exception as db_error:
                # 数据库操作失败不影响主要功能
                print(f"记录导入源失败: {str(db_error)}")
            
            message_parts = [f"成功从URL解析出 {len(rules)} 条规则"]
            if skipped_duplicate > 0:
                message_parts.append(f"跳过 {skipped_duplicate} 条重复规则")
            if len(filtered_rules) > 0:
                message_parts.append(f"实际导入 {len(filtered_rules)} 条新规则")
            
            return {
                "success": True,
                "message": "，".join(message_parts),
                "rules_parsed": len(rules),
                "import_result": import_result
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"从URL导入规则失败: {str(e)}",
                "rules_parsed": 0,
                "import_result": None
            }
    
    def _parse_rewrite_rules_from_text(self, content: str) -> List[Dict]:
        """从文本内容中解析DNS重写规则
        
        支持多种格式：
        - domain.com 192.168.1.1
        - domain.com=192.168.1.1
        - domain.com -> 192.168.1.1
        - AdGuard Home格式的hosts文件
        
        Args:
            content: 文本内容
            
        Returns:
            List[Dict]: 解析出的规则列表
        """
        rules = []
        lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # 跳过注释和空行
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            
            # 尝试不同的格式解析
            domain = None
            answer = None
            
            # 格式1: domain.com 192.168.1.1 或 格式4: hosts文件格式 (IP domain)
            # 使用split()处理空格、制表符等所有空白字符
            parts = line.split()
            if len(parts) >= 2:
                # 判断第一个部分是否为IP地址
                if self._is_valid_ip(parts[0]):
                    # hosts格式：IP domain
                    answer = parts[0]
                    domain = parts[1]
                else:
                    # 普通格式：domain IP
                    domain = parts[0]
                    answer = parts[1]
            
            # 格式2: domain.com=192.168.1.1
            elif '=' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    domain = parts[0].strip()
                    answer = parts[1].strip()
            
            # 格式3: domain.com -> 192.168.1.1
            elif '->' in line:
                parts = line.split('->', 1)
                if len(parts) == 2:
                    domain = parts[0].strip()
                    answer = parts[1].strip()
            

            
            # 验证解析结果
            if domain and answer:
                # 基本验证
                if '.' in domain and (self._is_valid_ip(answer) or '.' in answer):
                    rules.append({
                        "domain": domain,
                        "answer": answer
                    })
        
        return rules
    
    def _is_valid_ip(self, ip: str) -> bool:
        """验证IP地址格式
        
        Args:
            ip: IP地址字符串
            
        Returns:
            bool: 是否为有效的IP地址
        """
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def get_filtering_status(self) -> Dict:
        """获取过滤状态和规则
        
        Returns:
            Dict: 包含过滤状态和用户自定义规则的信息
        """
        return self._make_request('GET', '/filtering/status')
    
    def set_filtering_rules(self, rules: List[str]) -> Dict:
        """设置用户自定义过滤规则
        
        Args:
            rules: 过滤规则列表
            
        Returns:
            Dict: 操作结果
        """
        data = {"rules": rules}
        return self._make_request('POST', '/filtering/set_rules', json=data)
    
    def get_client_custom_rules(self, client_id: str) -> List[str]:
        """获取指定客户端的自定义规则
        
        Args:
            client_id: 客户端ID
            
        Returns:
            List[str]: 该客户端的自定义规则列表
        """
        try:
            # 根据客户端ID查找客户端名称
            client_name = self.find_client_name_by_id(client_id)
            if not client_name:
                print(f"未找到客户端ID {client_id} 对应的客户端名称")
                return []
            
            status = self.get_filtering_status()
            user_rules = status.get('user_rules', [])
            
            # 查找带有客户端标签的规则
            client_rules = []
            client_tag = f"$client={client_name}"
            
            for rule in user_rules:
                if client_tag in rule:
                    # 移除标签，只返回规则内容
                    clean_rule = rule.replace(f" {client_tag}", "").replace(f"{client_tag} ", "").replace(client_tag, "")
                    if clean_rule.strip():
                        client_rules.append(clean_rule.strip())
            
            return client_rules
        except Exception as e:
            print(f"获取客户端自定义规则失败: {str(e)}")
            return []
    
    def add_client_custom_rule(self, client_id: str, rule: str) -> Dict:
        """为指定客户端添加自定义规则
        
        Args:
            client_id: 客户端ID
            rule: 要添加的规则
            
        Returns:
            Dict: 操作结果
        """
        try:
            # 根据客户端ID查找客户端名称
            client_name = self.find_client_name_by_id(client_id)
            if not client_name:
                return {"success": False, "error": f"未找到客户端ID {client_id} 对应的客户端名称"}
            
            # 获取当前所有规则
            status = self.get_filtering_status()
            current_rules = status.get('user_rules', [])
            
            # 添加客户端标签
            client_tag = f"$client={client_name}"
            tagged_rule = f"{rule}{client_tag}"
            
            # 检查规则是否已存在
            if tagged_rule not in current_rules:
                current_rules.append(tagged_rule)
                return self.set_filtering_rules(current_rules)
            else:
                return {"success": True, "message": "规则已存在"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def remove_client_custom_rule(self, client_id: str, rule: str) -> Dict:
        """删除指定客户端的自定义规则
        
        Args:
            client_id: 客户端ID
            rule: 要删除的规则
            
        Returns:
            Dict: 操作结果
        """
        try:
            # 根据客户端ID查找客户端名称
            client_name = self.find_client_name_by_id(client_id)
            if not client_name:
                return {"success": False, "error": f"未找到客户端ID {client_id} 对应的客户端名称"}
            
            # 获取当前所有规则
            status = self.get_filtering_status()
            current_rules = status.get('user_rules', [])
            
            # 构建要删除的规则（带标签）
            client_tag = f"$client={client_name}"
            tagged_rule = f"{rule}{client_tag}"
            
            # 删除规则
            if tagged_rule in current_rules:
                current_rules.remove(tagged_rule)
                return self.set_filtering_rules(current_rules)
            else:
                return {"success": True, "message": "规则不存在"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def remove_all_client_custom_rules(self, client_id: str) -> Dict:
        """删除指定客户端的所有自定义规则
        
        Args:
            client_id: 客户端ID
            
        Returns:
            Dict: 操作结果，包含删除的规则数量
        """
        try:
            # 根据客户端ID查找客户端名称
            client_name = self.find_client_name_by_id(client_id)
            if not client_name:
                return {"success": False, "error": f"未找到客户端ID {client_id} 对应的客户端名称"}
            
            # 获取当前所有规则
            status = self.get_filtering_status()
            current_rules = status.get('user_rules', [])
            
            # 查找并删除该客户端的所有规则
            client_tag = f"$client={client_name}"
            rules_to_remove = [rule for rule in current_rules if client_tag in rule]
            
            if rules_to_remove:
                # 删除规则
                for rule in rules_to_remove:
                    current_rules.remove(rule)
                
                result = self.set_filtering_rules(current_rules)
                result["removed_count"] = len(rules_to_remove)
                return result
            else:
                return {"success": True, "message": "没有找到该客户端的规则", "removed_count": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "removed_count": 0}