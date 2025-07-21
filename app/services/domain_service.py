import requests
import json
import logging
from typing import Dict, List, Optional, Union
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkalidns.request.v20150109.AddDomainRecordRequest import AddDomainRecordRequest
from aliyunsdkalidns.request.v20150109.UpdateDomainRecordRequest import UpdateDomainRecordRequest
from aliyunsdkalidns.request.v20150109.DescribeDomainRecordsRequest import DescribeDomainRecordsRequest
from app import db
from app.models.operation_log import OperationLog

class DomainService:
    """
    阿里云域名解析服务类
    
    用于处理IP地址获取和阿里云域名解析相关操作
    """
    
    def __init__(self, access_key_id=None, access_key_secret=None, domain_name=None):
        """
        初始化域名服务实例
        
        Args:
            access_key_id: 阿里云AccessKey ID
            access_key_secret: 阿里云AccessKey Secret
            domain_name: 主域名
        """
        from app.models.domain_config import DomainConfig
        
        # 如果没有提供参数，则从数据库获取配置
        if not all([access_key_id, access_key_secret, domain_name]):
            config = DomainConfig.get_config()
            self.access_key_id = config.access_key_id
            self.access_key_secret = config.access_key_secret
            self.domain_name = config.domain_name
        else:
            self.access_key_id = access_key_id
            self.access_key_secret = access_key_secret
            self.domain_name = domain_name
        
        # 初始化阿里云客户端
        self.client = AcsClient(self.access_key_id, self.access_key_secret, 'cn-hangzhou')
    
    def get_local_ip(self) -> str:
        """
        获取本地公网IP地址
        
        使用多个公共API获取当前公网IP地址，按优先级尝试不同的API
        
        Returns:
            str: IP地址，如果获取失败则返回默认IP
        """
        # 定义多个可用的IP获取API，按可靠性排序
        ip_apis = [
            # 国内可靠的API
            {'url': 'https://myip.ipip.net', 'type': 'text', 'parser': lambda r: r.text.split('：')[1].split(' ')[0] if '：' in r.text else None},
            
            # 国际通用API
            {'url': 'https://api.ipify.org', 'type': 'text', 'parser': lambda r: r.text},
            {'url': 'https://ifconfig.me/ip', 'type': 'text', 'parser': lambda r: r.text},
            {'url': 'https://icanhazip.com', 'type': 'text', 'parser': lambda r: r.text.strip()},
            
            # JSON格式API
            {'url': 'https://api.ipify.org?format=json', 'type': 'json', 'parser': lambda r: r.json().get('ip')},
            {'url': 'https://httpbin.org/ip', 'type': 'json', 'parser': lambda r: r.json().get('origin')}
        ]
        
        # 尝试所有API
        success_count = 0
        for api in ip_apis:
            try:
                response = requests.get(api['url'], timeout=3)
                if response.status_code == 200:
                    if api['type'] == 'json':
                        ip = api['parser'](response)
                    else:
                        ip = api['parser'](response)
                    
                    # 验证IP地址格式
                    if ip and self._is_valid_ip(ip):
                        print(f"通过API {api['url']} 获取到IP地址: {ip}")
                        return ip
                    else:
                        print(f"API {api['url']} 返回的IP格式无效: {ip}")
                else:
                    print(f"API {api['url']} 请求失败，状态码: {response.status_code}")
            except Exception as e:
                print(f"API {api['url']} 请求异常: {str(e)}")
                success_count += 1
        
        # 如果所有API都失败，返回本地IP地址
        print(f"获取IP地址失败: {success_count}，使用默认本地IP地址")
        return "127.0.0.1"
    
    def _is_valid_ip(self, ip: str) -> bool:
        """
        验证IP地址格式是否有效
        
        Args:
            ip: 要验证的IP地址
            
        Returns:
            bool: 是否是有效的IP地址
        """
        import re
        # 简单的IPv4地址格式验证
        pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        return bool(re.match(pattern, ip.strip()))
            
    def get_ip_address(self) -> str:
        """
        获取当前IP地址
        
        此方法是get_local_ip的别名，用于保持代码兼容性
        
        Returns:
            str: IP地址
        
        Raises:
            Exception: 当获取IP地址失败时抛出异常
        """
        return self.get_local_ip()
        
    def get_current_ip(self) -> str:
        """
        获取当前IP地址
        
        此方法是get_local_ip的别名，用于保持代码兼容性
        
        Returns:
            str: IP地址
        
        Raises:
            Exception: 当获取IP地址失败时抛出异常
        """
        return self.get_local_ip()
    
    def create_subdomain(self, username: str, ip: Optional[str] = None) -> Dict:
        """
        创建子域名解析
        
        Args:
            username: 用户名，用于创建子域名
            ip: IP地址，如果不提供则自动获取
            
        Returns:
            Dict: 创建结果
            
        Raises:
            Exception: 当创建子域名解析失败时抛出异常
        """
        try:
            # 如果没有提供IP地址，则自动获取
            if not ip:
                ip = self.get_local_ip()
            
            # 检查域名解析是否已存在
            existing_record = self.find_subdomain_record(username)
            
            if existing_record:
                # 如果已存在，则更新解析记录
                return self.update_subdomain(username, ip, existing_record['RecordId'])
            else:
                # 如果不存在，则创建新的解析记录
                request = AddDomainRecordRequest()
                request.set_accept_format('json')
                
                # 设置域名解析参数
                request.set_DomainName(self.domain_name)
                request.set_RR(username)  # 子域名前缀
                request.set_Type("A")     # A记录，将域名解析到IPv4地址
                request.set_Value(ip)      # 解析到的IP地址
                request.set_TTL(600)       # 生存时间，单位秒
                
                # 发送请求
                response = self.client.do_action_with_exception(request)
                result = json.loads(response.decode('utf-8'))
                
                print(f"创建子域名解析成功: {username}.{self.domain_name} -> {ip}")
                return result
        except Exception as e:
            print(f"创建子域名解析失败: {str(e)}")
            raise Exception(f"创建子域名解析失败: {str(e)}")
                
    def add_domain_record(self, subdomain: str, ip: str) -> str:
        """
        添加域名解析记录
        
        Args:
            subdomain: 子域名
            ip: IP地址
            
        Returns:
            str: 记录ID
            
        Raises:
            Exception: 当添加域名解析记录失败时抛出异常
        """
        try:
            # 检查域名解析是否已存在
            existing_record = self.find_subdomain_record(subdomain)
            
            if existing_record:
                # 如果已存在，则更新解析记录
                try:
                    result = self.update_subdomain(subdomain, ip, existing_record['RecordId'])
                    return existing_record['RecordId']
                except Exception as update_error:
                    # 如果更新失败，检查是否是DomainRecordDuplicate错误
                    error_str = str(update_error)
                    if "DomainRecordDuplicate" in error_str:
                        logging.warning(f"域名记录已存在，但IP地址相同，无需更新: {subdomain}.{self.domain_name} -> {ip}")
                        return existing_record['RecordId']
                    else:
                        # 其他错误则继续抛出
                        raise update_error
            else:
                # 如果不存在，则创建新的解析记录
                try:
                    request = AddDomainRecordRequest()
                    request.set_accept_format('json')
                    
                    # 设置域名解析参数
                    request.set_DomainName(self.domain_name)
                    request.set_RR(subdomain)  # 子域名前缀
                    request.set_Type("A")     # A记录，将域名解析到IPv4地址
                    request.set_Value(ip)      # 解析到的IP地址
                    request.set_TTL(600)       # 生存时间，单位秒
                    
                    # 发送请求
                    response = self.client.do_action_with_exception(request)
                    result = json.loads(response.decode('utf-8'))
                    
                    print(f"创建子域名解析成功: {subdomain}.{self.domain_name} -> {ip}")
                    return result.get('RecordId', '')
                except Exception as add_error:
                    # 检查是否是DomainRecordDuplicate错误
                    error_str = str(add_error)
                    if "DomainRecordDuplicate" in error_str:
                        # 如果是重复记录错误，尝试再次查找记录并返回
                        retry_record = self.find_subdomain_record(subdomain)
                        if retry_record:
                            logging.warning(f"域名记录已存在，使用现有记录: {subdomain}.{self.domain_name}")
                            return retry_record['RecordId']
                    # 其他错误或找不到重复记录，则继续抛出
                    raise add_error
        except Exception as e:
            logging.error(f"添加域名解析记录失败: {str(e)}")
            raise e
    
    def update_subdomain(self, username: str, ip: str, record_id: str) -> Dict:
        """
        更新子域名解析
        
        Args:
            username: 用户名，用于标识子域名
            ip: 新的IP地址
            record_id: 解析记录ID
            
        Returns:
            Dict: 更新结果
            
        Raises:
            Exception: 当更新子域名解析失败时抛出异常
        """
        try:
            request = UpdateDomainRecordRequest()
            request.set_accept_format('json')
            
            # 设置域名解析参数
            request.set_RecordId(record_id)
            request.set_RR(username)  # 子域名前缀
            request.set_Type("A")     # A记录，将域名解析到IPv4地址
            request.set_Value(ip)      # 解析到的IP地址
            request.set_TTL(600)       # 生存时间，单位秒
            
            # 发送请求
            response = self.client.do_action_with_exception(request)
            result = json.loads(response.decode('utf-8'))
            
            print(f"更新子域名解析成功: {username}.{self.domain_name} -> {ip}")
            return result
        except Exception as e:
            print(f"更新子域名解析失败: {str(e)}")
            raise Exception(f"更新子域名解析失败: {str(e)}")
    
    def find_subdomain_record(self, username: str) -> Optional[Dict]:
        """
        查找子域名解析记录
        
        Args:
            username: 用户名，用于标识子域名
            
        Returns:
            Optional[Dict]: 解析记录信息，如果不存在则返回None
            
        Raises:
            Exception: 当查询子域名解析记录失败时抛出异常
        """
        try:
            request = DescribeDomainRecordsRequest()
            request.set_accept_format('json')
            
            # 设置查询参数
            request.set_DomainName(self.domain_name)
            request.set_RRKeyWord(username)  # 按照子域名前缀关键词查询
            request.set_Type("A")           # 只查询A记录
            
            # 发送请求
            response = self.client.do_action_with_exception(request)
            result = json.loads(response.decode('utf-8'))
            
            # 检查是否有匹配的记录
            if result.get('TotalCount', 0) > 0:
                records = result.get('DomainRecords', {}).get('Record', [])
                for record in records:
                    if record.get('RR') == username:
                        return record
            
            return None
        except Exception as e:
            print(f"查询子域名解析记录失败: {str(e)}")
            raise Exception(f"查询子域名解析记录失败: {str(e)}")
    
    def log_operation(self, user_id: int, operation_type: str, target_id: str, details: str) -> None:
        """
        记录域名操作日志
        
        Args:
            user_id: 用户ID
            operation_type: 操作类型（CREATE/UPDATE）
            target_id: 目标ID（域名或记录ID）
            details: 操作详情
        """
        try:
            log = OperationLog(
                user_id=user_id,
                operation_type=operation_type,
                target_type="DOMAIN",
                target_id=target_id,
                details=details
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"记录域名操作日志失败: {str(e)}")
            # 日志记录失败不影响主流程，只打印错误信息
            
    def check_connection(self) -> bool:
        """
        检查与阿里云API的连接是否正常
        
        通过尝试获取域名记录列表来验证连接和凭证是否有效
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 创建请求对象
            request = DescribeDomainRecordsRequest()
            request.set_accept_format('json')
            
            # 设置查询参数
            request.set_DomainName(self.domain_name)
            request.set_PageSize(1)  # 只获取一条记录即可验证连接
            
            # 发送请求
            response = self.client.do_action_with_exception(request)
            result = json.loads(response.decode('utf-8'))
            
            # 如果能获取到结果，说明连接正常
            if 'DomainRecords' in result:
                return True
                
            return False
        except Exception as e:
            print(f"检查阿里云API连接失败: {str(e)}")
            return False
            
    def delete_domain_record(self, record_id: str) -> Dict:
        """
        删除域名解析记录
        
        Args:
            record_id: 解析记录ID
            
        Returns:
            Dict: 删除结果
            
        Raises:
            Exception: 当删除域名解析记录失败时抛出异常
        """
        try:
            from aliyunsdkalidns.request.v20150109.DeleteDomainRecordRequest import DeleteDomainRecordRequest
            
            request = DeleteDomainRecordRequest()
            request.set_accept_format('json')
            
            # 设置记录ID
            request.set_RecordId(record_id)
            
            # 发送请求
            response = self.client.do_action_with_exception(request)
            result = json.loads(response.decode('utf-8'))
            
            print(f"删除域名解析记录成功: {record_id}")
            return result
        except Exception as e:
            logging.error(f"删除域名解析记录失败: {str(e)}")
            raise Exception(f"删除域名解析记录失败: {str(e)}")
            
    def update_domain_record(self, record_id: str, subdomain: str, ip: str) -> Dict:
        """
        更新域名解析记录
        
        Args:
            record_id: 解析记录ID
            subdomain: 子域名
            ip: IP地址
            
        Returns:
            Dict: 更新结果
            
        Raises:
            Exception: 当更新域名解析记录失败时抛出异常
        """
        try:
            # 先检查当前记录的IP是否与要更新的IP相同
            existing_record = self.find_subdomain_record(subdomain)
            if existing_record and existing_record.get('Value') == ip:
                logging.info(f"域名记录IP地址未变化，无需更新: {subdomain}.{self.domain_name} -> {ip}")
                return {"RecordId": record_id, "Status": "Unchanged"}
                
            request = UpdateDomainRecordRequest()
            request.set_accept_format('json')
            
            # 设置域名解析参数
            request.set_RecordId(record_id)
            request.set_RR(subdomain)  # 子域名前缀
            request.set_Type("A")     # A记录，将域名解析到IPv4地址
            request.set_Value(ip)      # 解析到的IP地址
            request.set_TTL(600)       # 生存时间，单位秒
            
            # 发送请求
            response = self.client.do_action_with_exception(request)
            result = json.loads(response.decode('utf-8'))
            
            print(f"更新域名解析记录成功: {subdomain}.{self.domain_name} -> {ip}")
            return result
        except Exception as e:
            error_str = str(e)
            # 检查是否是DomainRecordDuplicate错误
            if "DomainRecordDuplicate" in error_str:
                logging.warning(f"域名记录已存在，可能IP地址相同: {subdomain}.{self.domain_name} -> {ip}")
                # 返回一个成功的结果，但标记为重复
                return {"RecordId": record_id, "Status": "Duplicate"}
            else:
                logging.error(f"更新域名解析记录失败: {str(e)}")
                raise Exception(f"更新域名解析记录失败: {str(e)}")
                
    def create_or_update_subdomain(self, subdomain: str, ip_address: str) -> tuple:
        """
        创建或更新子域名解析记录
        
        Args:
            subdomain: 子域名前缀
            ip_address: IP地址
            
        Returns:
            tuple: (成功标志, 记录ID, 完整域名)
            
        Raises:
            Exception: 当创建或更新子域名解析记录失败时抛出异常
        """
        try:
            # 检查域名解析是否已存在
            existing_record = self.find_subdomain_record(subdomain)
            
            if existing_record:
                # 如果已存在，则更新解析记录
                try:
                    result = self.update_subdomain(subdomain, ip_address, existing_record['RecordId'])
                    return True, existing_record['RecordId'], f"{subdomain}.{self.domain_name}"
                except Exception as update_error:
                    # 如果更新失败，检查是否是DomainRecordDuplicate错误
                    error_str = str(update_error)
                    if "DomainRecordDuplicate" in error_str:
                        logging.warning(f"域名记录已存在，但IP地址相同，无需更新: {subdomain}.{self.domain_name} -> {ip_address}")
                        return True, existing_record['RecordId'], f"{subdomain}.{self.domain_name}"
                    else:
                        # 其他错误则继续抛出
                        raise update_error
            else:
                # 如果不存在，则创建新的解析记录
                try:
                    record_id = self.add_domain_record(subdomain, ip_address)
                    return True, record_id, f"{subdomain}.{self.domain_name}"
                except Exception as add_error:
                    # 检查是否是DomainRecordDuplicate错误
                    error_str = str(add_error)
                    if "DomainRecordDuplicate" in error_str:
                        # 如果是重复记录错误，尝试再次查找记录并返回
                        retry_record = self.find_subdomain_record(subdomain)
                        if retry_record:
                            logging.warning(f"域名记录已存在，使用现有记录: {subdomain}.{self.domain_name}")
                            return True, retry_record['RecordId'], f"{subdomain}.{self.domain_name}"
                    # 其他错误或找不到重复记录，则继续抛出
                    raise add_error
        except Exception as e:
            logging.error(f"创建或更新子域名解析记录失败: {str(e)}")
            raise e