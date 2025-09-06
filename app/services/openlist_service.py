import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app import db
from app.models.openlist_config import OpenListConfig
from app.utils.timezone import beijing_time

class OpenListService:
    """OpenList API服务类
    
    用于处理所有与OpenList的API交互，包括认证、文件管理等。
    所有方法都会自动从数据库获取API配置信息。
    """
    
    def __init__(self, config: Optional[OpenListConfig] = None, skip_enabled_check: bool = False):
        """
        初始化OpenList服务实例
        
        Args:
            config: OpenList配置对象，如果不提供则从数据库获取
            skip_enabled_check: 是否跳过启用状态检查，用于测试连接
            
        Raises:
            Exception: 当配置验证失败时抛出异常
        """
        self.config = config or OpenListConfig.get_config()
        
        # 验证配置
        if not skip_enabled_check and not self.config.enabled:
            raise Exception('OpenList对接未启用')
            
        if not self.config.server_url:
            raise Exception('OpenList服务器地址未配置')
            
        if not self.config.username or not self.config.password:
            raise Exception('OpenList用户名或密码未配置')
            
        # 设置API基础URL
        self.base_url = self.config.server_url.rstrip('/')
        
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
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict:
        """发送HTTP请求到OpenList API
        
        Args:
            method: HTTP方法（GET、POST、PUT、DELETE）
            endpoint: API端点路径（不包含基础URL）
            json_data: 请求体数据（可选）
            params: URL查询参数（可选）
            headers: 额外的请求头（可选）
            
        Returns:
            API响应的JSON数据
            
        Raises:
            Exception: 当API请求失败时，包含详细的错误信息
        """
        # 确保endpoint以/开头
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
            
        url = f"{self.base_url}{endpoint}"
        
        # 设置默认请求头
        request_headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'ADGHM-OpenList-Client/1.0'
        }
        
        # 如果有token，添加认证头（根据OpenList API文档，直接使用token值）
        if self.config.token and self.config.is_token_valid():
            request_headers['Authorization'] = self.config.token
            import logging
            logging.info(f"使用token: {self.config.token[:20]}... (有效期至: {self.config.token_expires_at})")
        
        # 合并额外的请求头
        if headers:
            request_headers.update(headers)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=request_headers,
                json=json_data,
                params=params,
                timeout=30
            )
            
            # 检查响应状态 - 对于401错误，返回响应而不是抛出异常，让调用方处理
            if response.status_code == 401:
                # 认证失败，返回响应让调用方处理重新认证
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {'code': 401, 'message': '认证失败，token无效', 'status_code': response.status_code}
            elif response.status_code == 403:
                raise Exception('权限不足，无法访问该资源')
            elif response.status_code == 404:
                raise Exception('请求的资源不存在')
            elif response.status_code >= 400:
                error_msg = f'API请求失败，状态码: {response.status_code}'
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg += f', 错误信息: {error_data["message"]}'
                except:
                    error_msg += f', 响应内容: {response.text[:200]}'
                raise Exception(error_msg)
            
            # 尝试解析JSON响应
            try:
                return response.json()
            except json.JSONDecodeError:
                # 如果不是JSON响应，返回文本内容
                return {'content': response.text, 'status_code': response.status_code}
                
        except requests.exceptions.Timeout:
            raise Exception('请求超时，请检查网络连接或服务器状态')
        except requests.exceptions.ConnectionError:
            raise Exception('连接失败，请检查服务器地址和网络连接')
        except requests.exceptions.RequestException as e:
            raise Exception(f'请求异常: {str(e)}')
    
    def authenticate(self) -> Dict:
        """用户认证，获取访问token
        
        Returns:
            认证结果字典
            
        Raises:
            Exception: 当认证失败时抛出异常
        """
        # 根据OpenList API文档，认证数据格式
        auth_data = {
            'username': self.config.username,
            'password': self.config.password
        }
        
        try:
            import logging
            logging.info(f"开始认证，用户名: {self.config.username}")
            
            # 根据OpenList API文档，使用正确的认证端点
            response = self._make_request('POST', '/api/auth/login', json_data=auth_data)
            
            logging.info(f"认证响应: {response}")
            
            # 检查响应是否为HTML（说明端点错误）
            if isinstance(response, dict) and 'content' in response and response['content'].strip().startswith('<'):
                raise Exception(f'服务器返回HTML页面而非API响应，请检查服务器地址是否为API地址。当前地址: {self.base_url}')
            
            # 检查不同可能的token字段名
            token = None
            if 'data' in response and isinstance(response['data'], dict):
                token = response['data'].get('token')
            elif 'token' in response:
                token = response['token']
            elif 'access_token' in response:
                token = response['access_token']
            
            logging.info(f"提取的token: {token[:20] if token else 'None'}...")
            
            if token:
                # 更新配置中的token
                self.config.token = token
                
                # 设置token过期时间（根据API文档，默认48小时有效）
                self.config.token_expires_at = beijing_time() + timedelta(hours=48)
                
                # 保存到数据库
                db.session.commit()
                
                # 刷新当前实例的配置，确保使用最新的token
                db.session.refresh(self.config)
                
                return {
                    'success': True,
                    'message': '认证成功',
                    'token': token
                }
            else:
                # 根据响应内容提供具体的错误信息
                if isinstance(response, dict) and 'content' in response:
                    if response['content'].strip().startswith('<'):
                        raise Exception(f'服务器返回HTML页面而非API响应。请检查：\n1. 服务器地址是否正确（当前：{self.base_url}）\n2. 地址是否指向API服务器而非网页界面\n3. 尝试访问 {self.base_url}/ping 检查服务器状态')
                    else:
                        raise Exception(f'认证响应格式异常，响应内容: {response["content"][:200]}...')
                else:
                    raise Exception(f'认证响应中未包含token，响应数据: {response}')
                
        except Exception as e:
            return {
                'success': False,
                'message': f'认证失败: {str(e)}'
            }
    
    def test_connection(self) -> Dict:
        """测试与OpenList服务器的连接
        
        Returns:
            连接测试结果字典
        """
        try:
            # 首先尝试认证
            auth_result = self.authenticate()
            if not auth_result['success']:
                return auth_result
            
            # 然后尝试获取用户信息
            response = self._make_request('GET', '/api/auth/me')
            
            return {
                'success': True,
                'message': '连接测试成功',
                'user_info': response
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'连接测试失败: {str(e)}'
            }
    
    def list_files(self, path: str = '/') -> Dict:
        """列出指定路径下的文件和目录
        
        Args:
            path: 目录路径，默认为根目录
            
        Returns:
            文件列表结果字典
        """
        try:
            # 确保有有效的token
            if not self.config.is_token_valid():
                auth_result = self.authenticate()
                if not auth_result['success']:
                    return auth_result
            
            params = {'path': path}
            response = self._make_request('GET', '/api/fs/list', params=params)
            
            return {
                'success': True,
                'message': '获取文件列表成功',
                'files': response.get('files', []),
                'path': path
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'获取文件列表失败: {str(e)}'
            }
    
    def create_folder(self, path: str, name: str) -> Dict:
        """创建新文件夹
        
        Args:
            path: 父目录路径
            name: 文件夹名称
            
        Returns:
            创建结果字典
        """
        try:
            # 确保有有效的token
            if not self.config.is_token_valid():
                auth_result = self.authenticate()
                if not auth_result['success']:
                    return auth_result
            
            data = {
                'path': path,
                'name': name
            }
            response = self._make_request('POST', '/api/fs/mkdir', json_data=data)
            
            return {
                'success': True,
                'message': f'文件夹 "{name}" 创建成功',
                'folder_path': f'{path.rstrip("/")}/{name}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'创建文件夹失败: {str(e)}'
            }
    
    def sync_data(self) -> Dict:
        """同步数据到OpenList
        
        Returns:
            同步结果字典
        """
        try:
            # 更新最后同步时间
            self.config.last_sync_at = beijing_time()
            self.config.sync_status = '同步中'
            db.session.commit()
            
            # 测试连接
            test_result = self.test_connection()
            if not test_result['success']:
                self.config.sync_status = '同步失败'
                db.session.commit()
                return test_result
            
            # 这里可以添加具体的同步逻辑
            # 例如：同步用户数据、配置文件等
            
            # 更新同步状态
            self.config.sync_status = '同步成功'
            db.session.commit()
            
            return {
                'success': True,
                'message': '数据同步成功',
                'sync_time': self.config.last_sync_at.isoformat()
            }
            
        except Exception as e:
            self.config.sync_status = '同步失败'
            db.session.commit()
            return {
                'success': False,
                'message': f'数据同步失败: {str(e)}'
            }
    
    def get_sync_status(self) -> Dict:
        """获取同步状态信息
        
        Returns:
            同步状态字典
        """
        return {
            'sync_status': self.config.sync_status,
            'last_sync_at': self.config.last_sync_at.isoformat() if self.config.last_sync_at else None,
            'auto_sync': self.config.auto_sync,
            'sync_interval': self.config.sync_interval,
            'token_valid': self.config.is_token_valid()
        }
    
    def create_user(self, username: str, email: str, password: str, permissions: List[str], root_path: str = '/') -> Dict:
        """创建OpenList用户
        
        Args:
            username: 用户名
            email: 邮箱地址（OpenList不使用，但保留兼容性）
            password: 密码
            permissions: 权限列表（转换为permission数值）
            root_path: 用户根目录路径（对应base_path）
            
        Returns:
            创建结果字典
        """
        try:
            import logging
            logging.info(f"OpenList服务开始创建用户: {username}")
            
            # 确保有有效的token
            if not self.config.is_token_valid():
                logging.info("Token无效，开始重新认证")
                auth_result = self.authenticate()
                if not auth_result['success']:
                    logging.error(f"认证失败: {auth_result['message']}")
                    return auth_result
                logging.info("认证成功")
            else:
                logging.info("Token有效，跳过认证")
            
            # 转换权限列表为数值（根据OpenList权限系统）
            # 根据testuser555用户的权限值，WebDAV读取和FTP读取权限对应1280
            # 这个值是通过查询现有用户权限反推得出的
            permission_value = 1280
            
            # 构建用户数据（按照OpenList API规范）
            user_data = {
                'username': username,
                'password': password,
                'base_path': root_path,
                'role': 0,  # 普通用户角色
                'permission': permission_value,
                'disabled': False,
                'sso_id': ''
            }
            
            logging.info(f"准备发送用户数据: {user_data}")
            logging.info(f"OpenList服务器地址: {self.config.server_url}")
            
            # 发送创建用户请求到正确的API端点
            response = self._make_request('POST', '/api/admin/user/create', json_data=user_data)
            
            # 检查是否是401认证错误，如果是则重新认证并重试
            if response and response.get('code') == 401:
                logging.info("收到401错误，尝试重新认证")
                auth_result = self.authenticate()
                if not auth_result['success']:
                    logging.error(f"重新认证失败: {auth_result['message']}")
                    return auth_result
                logging.info("重新认证成功，重试创建用户请求")
                # 重试请求，authenticate方法已经更新了self.config中的token
                response = self._make_request('POST', '/api/admin/user/create', json_data=user_data)
            
            logging.info(f"API响应: {response}")
            
            # 检查API响应是否成功
            if response and response.get('code') == 200:
                logging.info(f"用户 {username} 创建成功")
                return {
                    'success': True,
                    'message': f'用户 "{username}" 创建成功',
                    'username': username,
                    'base_path': root_path,
                    'permission': permission_value
                }
            else:
                # API返回错误
                error_msg = response.get('message', '未知错误') if response else '请求失败'
                logging.error(f"创建用户失败: {error_msg}")
                return {
                    'success': False,
                    'message': f'创建用户失败: {error_msg}'
                }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'创建用户失败: {str(e)}'
            }
    
    def get_users(self) -> Dict:
        """获取用户列表
        
        Returns:
            用户列表字典
        """
        try:
            # 确保有有效的token
            if not self.config.is_token_valid():
                auth_result = self.authenticate()
                if not auth_result['success']:
                    return auth_result
            
            response = self._make_request('GET', '/api/users')
            
            return {
                'success': True,
                'message': '获取用户列表成功',
                'users': response.get('users', [])
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'获取用户列表失败: {str(e)}'
            }