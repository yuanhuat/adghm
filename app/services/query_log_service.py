import json
import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from app.services.adguard_service import AdGuardService
from app.models.query_log_analysis import QueryLogExport
from app import db

class QueryLogService:
    """查询日志服务类
    
    提供高级搜索、导出、分析等功能
    """
    
    def __init__(self):
        """初始化查询日志服务"""
        self.adguard_service = AdGuardService()
        self.logger = logging.getLogger(__name__)
    
    def advanced_search(self, filters: Dict[str, Any], 
                       page_size: int = 50, older_than: str = None) -> Dict:
        """高级搜索查询日志
        
        Args:
            filters: 搜索过滤条件
                - domain: 域名（支持通配符）
                - client: 客户端IP或名称
                - query_type: 查询类型（A, AAAA, CNAME等）
                - response_code: 响应代码
                - blocked: 是否被阻止（True/False）
                - start_time: 开始时间
                - end_time: 结束时间
                - reason: 阻止原因
            page_size: 每页记录数
            older_than: 分页参数
            
        Returns:
            搜索结果字典
        """
        try:
            # 构建API查询参数
            search_param = None
            response_status_param = None
            
            # 处理域名和客户端搜索
            if filters.get('domain') or filters.get('client'):
                search_terms = []
                if filters.get('domain'):
                    search_terms.append(filters['domain'])
                if filters.get('client'):
                    search_terms.append(filters['client'])
                search_param = ' '.join(search_terms)
            
            # 处理响应状态过滤
            if filters.get('blocked') is True:
                response_status_param = 'filtered'
            elif filters.get('blocked') is False:
                response_status_param = 'processed'
            elif filters.get('reason'):
                reason = filters['reason'].lower()
                if 'safebrowsing' in reason:
                    response_status_param = 'blocked_safebrowsing'
                elif 'parental' in reason:
                    response_status_param = 'blocked_parental'
                elif 'whitelist' in reason:
                    response_status_param = 'whitelisted'
                elif 'rewrite' in reason:
                    response_status_param = 'rewritten'
                elif 'safe_search' in reason:
                    response_status_param = 'safe_search'
                elif 'blocked' in reason:
                    response_status_param = 'blocked'
            
            # 获取原始查询日志
            log_data = self.adguard_service.get_query_log(
                limit=page_size, 
                older_than=older_than,
                search=search_param,
                response_status=response_status_param
            )
            
            if not log_data or 'data' not in log_data:
                return {'data': [], 'oldest': None, 'has_more': False}
            
            # 应用剩余的过滤条件（API不支持的）
            filtered_data = self._apply_additional_filters(log_data['data'], filters)
            
            # 计算统计信息
            stats = self._calculate_search_stats(filtered_data)
            
            return {
                'data': filtered_data,
                'oldest': log_data.get('oldest'),
                'has_more': len(log_data['data']) >= page_size,
                'total_found': len(filtered_data),
                'stats': stats
            }
            
        except Exception as e:
            self.logger.error(f"高级搜索时出错: {str(e)}")
            return {'data': [], 'oldest': None, 'has_more': False, 'error': str(e)}
    
    def export_logs(self, export_format: str, filters: Dict[str, Any] = None,
                   max_records: int = 10000, user_id: int = None) -> Optional[str]:
        """导出查询日志
        
        Args:
            export_format: 导出格式（csv, json）
            filters: 过滤条件
            max_records: 最大记录数
            user_id: 用户ID
            
        Returns:
            导出文件路径或None
        """
        try:
            # 创建导出记录
            export_record = QueryLogExport(
                export_type=export_format,
                filters=json.dumps(filters) if filters else None,
                max_records=max_records,
                requested_by=user_id,
                status='processing'
            )
            db.session.add(export_record)
            db.session.commit()
            
            # 收集所有匹配的日志
            all_logs = []
            older_than = None
            page_size = 1000
            
            while len(all_logs) < max_records:
                # 获取一页数据
                search_result = self.advanced_search(
                    filters or {}, 
                    page_size=min(page_size, max_records - len(all_logs)),
                    older_than=older_than
                )
                
                if not search_result['data']:
                    break
                
                all_logs.extend(search_result['data'])
                
                if not search_result['has_more']:
                    break
                
                older_than = search_result['oldest']
            
            # 生成导出文件
            if export_format.lower() == 'csv':
                file_path = self._export_to_csv(all_logs, export_record.id)
            elif export_format.lower() == 'json':
                file_path = self._export_to_json(all_logs, export_record.id)
            else:
                raise ValueError(f"不支持的导出格式: {export_format}")
            
            # 更新导出记录
            export_record.status = 'completed'
            export_record.file_path = file_path
            export_record.record_count = len(all_logs)
            export_record.completed_at = datetime.utcnow()
            db.session.commit()
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"导出日志时出错: {str(e)}")
            if 'export_record' in locals():
                export_record.status = 'failed'
                export_record.error_message = str(e)
                db.session.commit()
            return None
    
    def generate_analysis_report(self, time_range: str = '24h') -> Dict:
        """生成DNS查询趋势分析报告
        
        Args:
            time_range: 时间范围（1h, 6h, 24h, 7d, 30d）
            
        Returns:
            分析报告字典
        """
        try:
            # 计算时间范围
            end_time = datetime.utcnow()
            if time_range == '1h':
                start_time = end_time - timedelta(hours=1)
                interval_minutes = 5
            elif time_range == '6h':
                start_time = end_time - timedelta(hours=6)
                interval_minutes = 30
            elif time_range == '24h':
                start_time = end_time - timedelta(days=1)
                interval_minutes = 60
            elif time_range == '7d':
                start_time = end_time - timedelta(days=7)
                interval_minutes = 360  # 6小时
            elif time_range == '30d':
                start_time = end_time - timedelta(days=30)
                interval_minutes = 1440  # 24小时
            else:
                raise ValueError(f"不支持的时间范围: {time_range}")
            
            # 收集指定时间范围内的所有日志
            filters = {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
            all_logs = []
            older_than = None
            
            while True:
                search_result = self.advanced_search(
                    filters, 
                    page_size=1000,
                    older_than=older_than
                )
                
                if not search_result['data']:
                    break
                
                all_logs.extend(search_result['data'])
                
                if not search_result['has_more']:
                    break
                
                older_than = search_result['oldest']
            
            # 生成分析报告
            report = self._analyze_logs(all_logs, start_time, end_time, interval_minutes)
            
            return report
            
        except Exception as e:
            self.logger.error(f"生成分析报告时出错: {str(e)}")
            return {'error': str(e)}
    
    def _apply_additional_filters(self, logs: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """应用API不支持的额外过滤条件
        
        Args:
            logs: 原始日志列表
            filters: 过滤条件
            
        Returns:
            过滤后的日志列表
        """
        filtered_logs = []
        
        for log in logs:
            if self._matches_additional_filters(log, filters):
                filtered_logs.append(log)
        
        return filtered_logs
    
    def _matches_additional_filters(self, log: Dict, filters: Dict[str, Any]) -> bool:
        """检查日志是否匹配额外的过滤条件（API不支持的）
        
        Args:
            log: 单条日志
            filters: 过滤条件
            
        Returns:
            是否匹配
        """
        try:
            # 查询类型过滤（API不支持特定类型过滤）
            if 'query_type' in filters and filters['query_type']:
                question = log.get('question', {})
                if question.get('type') != filters['query_type']:
                    return False
            
            # 响应代码过滤
            if 'response_code' in filters and filters['response_code']:
                if log.get('status') != filters['response_code']:
                    return False
            
            # 时间范围过滤
            if 'start_time' in filters or 'end_time' in filters:
                log_time_str = log.get('time', '')
                if log_time_str:
                    try:
                        log_time = datetime.fromisoformat(log_time_str.replace('Z', '+00:00'))
                        
                        if 'start_time' in filters:
                            start_time = datetime.fromisoformat(filters['start_time'])
                            if log_time < start_time:
                                return False
                        
                        if 'end_time' in filters:
                            end_time = datetime.fromisoformat(filters['end_time'])
                            if log_time > end_time:
                                return False
                    except ValueError:
                        # 时间格式错误，跳过时间过滤
                        pass
            
            return True
            
        except Exception as e:
            self.logger.error(f"过滤条件匹配时出错: {str(e)}")
            return False
    
    def _calculate_search_stats(self, logs: List[Dict]) -> Dict:
        """计算搜索统计信息

        Args:
            logs: 日志列表

        Returns:
            统计信息字典
        """
        import ipaddress

        # 获取客户端映射
        adguard_service = AdGuardService()
        clients = adguard_service.get_all_clients()
        client_ip_map = {}
        client_cidr_map = {}
        for client in clients:
            name = client.get('name')
            if not name or not client.get('ids'):
                continue
            for an_id in client['ids']:
                try:
                    net = ipaddress.ip_network(an_id, strict=False)
                    if '/' in an_id:
                        client_cidr_map[net] = name
                    else:
                        client_ip_map[an_id] = name
                except ValueError:
                    client_ip_map[an_id] = name

        stats = {
            'total_queries': len(logs),
            'blocked_queries': 0,
            'allowed_queries': 0,
            'unique_domains': set(),
            'unique_clients': set(),
            'top_domains': {},
            'top_clients': {},
            'query_types': {},
            'block_reasons': {}
        }

        for log in logs:
            is_blocked = 'reason' in log and log['reason'] != "NotFiltered"
            if is_blocked:
                stats['blocked_queries'] += 1
            else:
                stats['allowed_queries'] += 1

            domain = log.get('question', {}).get('name', '')
            if domain:
                stats['top_domains'][domain] = stats['top_domains'].get(domain, 0) + 1
                stats['unique_domains'].add(domain)

            # 解析客户端名称
            client_ip_str = log.get('client')
            client_name = client_ip_str
            if client_ip_str:
                if client_ip_str in client_ip_map:
                    client_name = client_ip_map[client_ip_str]
                else:
                    try:
                        client_addr = ipaddress.ip_address(client_ip_str)
                        for network, name in client_cidr_map.items():
                            if client_addr in network:
                                client_name = name
                                break
                    except ValueError:
                        pass
            
            if client_name:
                stats['top_clients'][client_name] = stats['top_clients'].get(client_name, 0) + 1
                stats['unique_clients'].add(client_name)

            query_type = log.get('question', {}).get('type', '')
            if query_type:
                stats['query_types'][query_type] = stats['query_types'].get(query_type, 0) + 1

            if is_blocked:
                reason = log.get('reason', 'Unknown')
                stats['block_reasons'][reason] = stats['block_reasons'].get(reason, 0) + 1

        stats['unique_domains_count'] = len(stats['unique_domains'])
        stats['unique_clients_count'] = len(stats['unique_clients'])
        del stats['unique_domains']
        del stats['unique_clients']
        
        stats['top_domains'] = dict(sorted(stats['top_domains'].items(), key=lambda x: x[1], reverse=True)[:10])
        stats['top_clients'] = dict(sorted(stats['top_clients'].items(), key=lambda x: x[1], reverse=True)[:10])
        
        return stats
    
    def _export_to_csv(self, logs: List[Dict], export_id: int) -> str:
        """导出为CSV格式
        
        Args:
            logs: 日志列表
            export_id: 导出ID
            
        Returns:
            文件路径
        """
        import os
        
        # 创建导出目录
        export_dir = 'exports'
        os.makedirs(export_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'query_log_export_{export_id}_{timestamp}.csv'
        file_path = os.path.join(export_dir, filename)
        
        # 写入CSV文件
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'timestamp', 'domain', 'query_type', 'client_ip', 'client_name',
                'response_code', 'is_blocked', 'block_reason', 'upstream', 'elapsed_ms'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for log in logs:
                result = log.get('Result', {})
                writer.writerow({
                    'timestamp': log.get('T', ''),
                    'domain': log.get('QH', ''),
                    'query_type': log.get('QT', ''),
                    'client_ip': log.get('IP', ''),
                    'client_name': log.get('CN', ''),
                    'response_code': result.get('RCode', ''),
                    'is_blocked': result.get('IsFiltered', False),
                    'block_reason': result.get('Reason', ''),
                    'upstream': log.get('Upstream', ''),
                    'elapsed_ms': log.get('Elapsed', '')
                })
        
        return file_path
    
    def _export_to_json(self, logs: List[Dict], export_id: int) -> str:
        """导出为JSON格式
        
        Args:
            logs: 日志列表
            export_id: 导出ID
            
        Returns:
            文件路径
        """
        import os
        
        # 创建导出目录
        export_dir = 'exports'
        os.makedirs(export_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'query_log_export_{export_id}_{timestamp}.json'
        file_path = os.path.join(export_dir, filename)
        
        # 写入JSON文件
        export_data = {
            'export_info': {
                'export_id': export_id,
                'timestamp': datetime.utcnow().isoformat(),
                'record_count': len(logs)
            },
            'logs': logs
        }
        
        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
        
        return file_path
    
    def _analyze_logs(self, logs: List[Dict], start_time: datetime, 
                     end_time: datetime, interval_minutes: int) -> Dict:
        """分析日志数据
        
        Args:
            logs: 日志列表
            start_time: 开始时间
            end_time: 结束时间
            interval_minutes: 时间间隔（分钟）
            
        Returns:
            分析报告
        """
        # 初始化时间序列数据
        time_series = []
        current_time = start_time
        
        while current_time < end_time:
            time_series.append({
                'timestamp': current_time.isoformat(),
                'total_queries': 0,
                'blocked_queries': 0,
                'allowed_queries': 0
            })
            current_time += timedelta(minutes=interval_minutes)
        
        # 统计数据
        total_stats = {
            'total_queries': len(logs),
            'blocked_queries': 0,
            'allowed_queries': 0,
            'unique_domains': set(),
            'unique_clients': set(),
            'top_domains': {},
            'top_blocked_domains': {},
            'top_clients': {},
            'query_types': {},
            'block_reasons': {}
        }
        
        # 处理每条日志
        for log in logs:
            # 解析时间
            log_time_str = log.get('T', '')
            if not log_time_str:
                continue
            
            try:
                log_time = datetime.fromisoformat(log_time_str.replace('Z', '+00:00'))
            except ValueError:
                continue
            
            # 找到对应的时间间隔
            interval_index = int((log_time - start_time).total_seconds() / (interval_minutes * 60))
            if 0 <= interval_index < len(time_series):
                time_series[interval_index]['total_queries'] += 1
                
                is_blocked = log.get('Result', {}).get('IsFiltered', False)
                if is_blocked:
                    time_series[interval_index]['blocked_queries'] += 1
                    total_stats['blocked_queries'] += 1
                else:
                    time_series[interval_index]['allowed_queries'] += 1
                    total_stats['allowed_queries'] += 1
            
            # 统计域名
            domain = log.get('QH', '')
            if domain:
                total_stats['unique_domains'].add(domain)
                total_stats['top_domains'][domain] = total_stats['top_domains'].get(domain, 0) + 1
                
                if log.get('Result', {}).get('IsFiltered', False):
                    total_stats['top_blocked_domains'][domain] = total_stats['top_blocked_domains'].get(domain, 0) + 1
            
            # 统计客户端
            client = log.get('IP', '')
            if client:
                total_stats['unique_clients'].add(client)
                total_stats['top_clients'][client] = total_stats['top_clients'].get(client, 0) + 1
            
            # 统计查询类型
            query_type = log.get('QT', '')
            if query_type:
                total_stats['query_types'][query_type] = total_stats['query_types'].get(query_type, 0) + 1
            
            # 统计阻止原因
            if log.get('Result', {}).get('IsFiltered', False):
                reason = log.get('Result', {}).get('Reason', 'Unknown')
                total_stats['block_reasons'][reason] = total_stats['block_reasons'].get(reason, 0) + 1
        
        # 转换集合为数量
        total_stats['unique_domains'] = len(total_stats['unique_domains'])
        total_stats['unique_clients'] = len(total_stats['unique_clients'])
        
        # 排序热门项目
        total_stats['top_domains'] = dict(sorted(total_stats['top_domains'].items(), 
                                               key=lambda x: x[1], reverse=True)[:20])
        total_stats['top_blocked_domains'] = dict(sorted(total_stats['top_blocked_domains'].items(), 
                                                       key=lambda x: x[1], reverse=True)[:20])
        total_stats['top_clients'] = dict(sorted(total_stats['top_clients'].items(), 
                                               key=lambda x: x[1], reverse=True)[:10])
        
        # 计算阻止率
        block_rate = (total_stats['blocked_queries'] / total_stats['total_queries'] * 100) if total_stats['total_queries'] > 0 else 0
        
        return {
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'interval_minutes': interval_minutes
            },
            'time_series': time_series,
            'summary': {
                'total_queries': total_stats['total_queries'],
                'blocked_queries': total_stats['blocked_queries'],
                'allowed_queries': total_stats['allowed_queries'],
                'block_rate': round(block_rate, 2),
                'unique_domains': total_stats['unique_domains'],
                'unique_clients': total_stats['unique_clients']
            },
            'top_domains': total_stats['top_domains'],
            'top_blocked_domains': total_stats['top_blocked_domains'],
            'top_clients': total_stats['top_clients'],
            'query_types': total_stats['query_types'],
            'block_reasons': total_stats['block_reasons']
        }