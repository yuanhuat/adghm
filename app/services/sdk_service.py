import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from app import db
from app.models.sdk import Sdk
from app.models.user import User
from app.models.operation_log import OperationLog


class SdkService:
    """SDK服务类，处理SDK相关的业务逻辑"""
    
    @staticmethod
    def generate_sdk_code(length: int = 16) -> str:
        """生成SDK兑换码
        
        Args:
            length: SDK码长度，默认16位
            
        Returns:
            生成的SDK码
        """
        # 使用大写字母和数字，排除容易混淆的字符
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    @staticmethod
    def generate_single_sdk(days: int, admin_user_id: int) -> Dict:
        """生成单个SDK
        
        Args:
            days: VIP天数
            admin_user_id: 管理员用户ID
            
        Returns:
            包含生成结果的字典
        """
        try:
            # 生成唯一的SDK码
            max_attempts = 10
            for _ in range(max_attempts):
                code = SdkService.generate_sdk_code()
                if not Sdk.query.filter_by(code=code).first():
                    break
            else:
                return {
                    'success': False,
                    'message': '生成SDK码失败，请重试'
                }
            
            # 创建SDK记录
            sdk = Sdk(
                code=code,
                days=days,
                status='unused',
                created_by=admin_user_id
            )
            
            db.session.add(sdk)
            db.session.commit()
            
            # 记录操作日志
            operation_log = OperationLog(
                user_id=admin_user_id,
                operation_type='SDK_GENERATE',
                target_type='SDK',
                target_id=code,
                details=f'生成单个SDK: {code}，VIP天数: {days}'
            )
            db.session.add(operation_log)
            db.session.commit()
            
            logging.info(f"管理员 {admin_user_id} 生成单个SDK: {code}，VIP天数: {days}")
            
            return {
                'success': True,
                'data': {
                    'code': code,
                    'days': days,
                    'created_at': sdk.created_at.isoformat()
                }
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"生成单个SDK失败: {str(e)}")
            return {
                'success': False,
                'message': f'生成失败: {str(e)}'
            }
    
    @staticmethod
    def generate_batch_sdks(count: int, days: int, admin_user_id: int) -> Dict:
        """批量生成SDK
        
        Args:
            count: 生成数量
            days: VIP天数
            admin_user_id: 管理员用户ID
            
        Returns:
            包含生成结果的字典
        """
        try:
            if count <= 0 or count > 1000:
                return {
                    'success': False,
                    'message': '生成数量必须在1-1000之间'
                }
            
            generated_sdks = []
            failed_count = 0
            
            for i in range(count):
                # 生成唯一的SDK码
                max_attempts = 10
                code = None
                
                for _ in range(max_attempts):
                    temp_code = SdkService.generate_sdk_code()
                    if not Sdk.query.filter_by(code=temp_code).first():
                        code = temp_code
                        break
                
                if not code:
                    failed_count += 1
                    continue
                
                # 创建SDK记录
                sdk = Sdk(
                    code=code,
                    days=days,
                    status='unused',
                    created_by=admin_user_id
                )
                
                db.session.add(sdk)
                generated_sdks.append({
                    'code': code,
                    'days': days
                })
            
            # 提交所有SDK记录
            db.session.commit()
            
            # 记录操作日志
            operation_log = OperationLog(
                user_id=admin_user_id,
                operation_type='SDK_BATCH_GENERATE',
                target_type='SDK',
                target_id=f'batch_{len(generated_sdks)}',
                details=f'批量生成SDK: {len(generated_sdks)}个，VIP天数: {days}，失败: {failed_count}个'
            )
            db.session.add(operation_log)
            db.session.commit()
            
            logging.info(f"管理员 {admin_user_id} 批量生成SDK: {len(generated_sdks)}个，VIP天数: {days}，失败: {failed_count}个")
            
            return {
                'success': True,
                'data': {
                    'generated_count': len(generated_sdks),
                    'failed_count': failed_count,
                    'sdks': generated_sdks
                }
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"批量生成SDK失败: {str(e)}")
            return {
                'success': False,
                'message': f'批量生成失败: {str(e)}'
            }
    
    @staticmethod
    def validate_sdk(code: str) -> Tuple[bool, Optional[Sdk], str]:
        """验证SDK码
        
        Args:
            code: SDK码
            
        Returns:
            (是否有效, SDK对象, 错误信息)
        """
        if not code or not code.strip():
            return False, None, 'SDK码不能为空'
        
        code = code.strip().upper()
        
        # 查找SDK
        sdk = Sdk.query.filter_by(code=code).first()
        if not sdk:
            return False, None, 'SDK码不存在'
        
        # 检查是否已使用
        if sdk.status == 'used':
            return False, sdk, 'SDK码已被使用'
        
        # 检查是否有效
        if not sdk.is_valid():
            return False, sdk, 'SDK码已失效'
        
        return True, sdk, ''
    
    @staticmethod
    def redeem_sdk(code: str, user_id: int) -> Dict:
        """兑换SDK
        
        Args:
            code: SDK码
            user_id: 用户ID
            
        Returns:
            兑换结果字典
        """
        try:
            # 验证SDK
            is_valid, sdk, error_msg = SdkService.validate_sdk(code)
            if not is_valid:
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # 获取用户
            user = User.query.get(user_id)
            if not user:
                return {
                    'success': False,
                    'message': '用户不存在'
                }
            
            # 使用SDK
            result = sdk.use_sdk(user_id)
            if not result['success']:
                return result
            
            # 记录操作日志
            operation_log = OperationLog(
                user_id=user_id,
                operation_type='SDK_REDEEM',
                target_type='SDK',
                target_id=code,
                details=f'用户 {user.username} 成功兑换SDK: {code}，获得 {sdk.days} 天VIP'
            )
            db.session.add(operation_log)
            db.session.commit()
            
            logging.info(f"用户 {user.username} 成功兑换SDK: {code}，获得 {sdk.days} 天VIP")
            
            return {
                'success': True,
                'message': f'兑换成功！您获得了 {sdk.days} 天VIP时长',
                'data': {
                    'days': sdk.days,
                    'new_vip_end_time': user.vip_expire_time.isoformat() if user.vip_expire_time else None
                }
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"SDK兑换失败: {str(e)}")
            return {
                'success': False,
                'message': f'兑换失败: {str(e)}'
            }
    
    @staticmethod
    def get_sdk_statistics() -> Dict:
        """获取SDK统计信息
        
        Returns:
            统计信息字典
        """
        try:
            total_count = Sdk.query.count()
            used_count = Sdk.query.filter_by(status='used').count()
            unused_count = Sdk.query.filter_by(status='unused').count()
            
            # 计算总VIP天数
            total_days = db.session.query(db.func.sum(Sdk.days)).scalar() or 0
            used_days = db.session.query(db.func.sum(Sdk.days)).filter_by(status='used').scalar() or 0
            unused_days = db.session.query(db.func.sum(Sdk.days)).filter_by(status='unused').scalar() or 0
            
            return {
                'total': total_count,
                'used': used_count,
                'unused': unused_count,
                'total_days': total_days,
                'used_days': used_days,
                'unused_days': unused_days
            }
            
        except Exception as e:
            logging.error(f"获取SDK统计信息失败: {str(e)}")
            return {
                'total': 0,
                'used': 0,
                'unused': 0,
                'total_days': 0,
                'used_days': 0,
                'unused_days': 0
            }
    
    @staticmethod
    def delete_sdks(sdk_ids: List[int], admin_user_id: int) -> Dict:
        """删除SDK
        
        Args:
            sdk_ids: SDK ID列表
            admin_user_id: 管理员用户ID
            
        Returns:
            删除结果字典
        """
        try:
            if not sdk_ids:
                return {
                    'success': False,
                    'message': '请选择要删除的SDK'
                }
            
            # 查找要删除的SDK
            sdks = Sdk.query.filter(Sdk.id.in_(sdk_ids)).all()
            if not sdks:
                return {
                    'success': False,
                    'message': '未找到要删除的SDK'
                }
            
            deleted_codes = []
            for sdk in sdks:
                deleted_codes.append(sdk.code)
                db.session.delete(sdk)
            
            db.session.commit()
            
            # 记录操作日志
            operation_log = OperationLog(
                user_id=admin_user_id,
                operation_type='SDK_DELETE',
                target_type='SDK',
                target_id=f'batch_{len(deleted_codes)}',
                details=f'删除SDK: {len(deleted_codes)}个，SDK码: {", ".join(deleted_codes[:5])}{", ..." if len(deleted_codes) > 5 else ""}'
            )
            db.session.add(operation_log)
            db.session.commit()
            
            logging.info(f"管理员 {admin_user_id} 删除SDK: {len(deleted_codes)}个")
            
            return {
                'success': True,
                'data': {
                    'deleted_count': len(deleted_codes)
                }
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"删除SDK失败: {str(e)}")
            return {
                'success': False,
                'message': f'删除失败: {str(e)}'
            }
    
    @staticmethod
    def get_user_sdk_history(user_id: int, limit: int = 20) -> List[Dict]:
        """获取用户SDK兑换历史
        
        Args:
            user_id: 用户ID
            limit: 返回记录数限制
            
        Returns:
            历史记录列表
        """
        try:
            sdks = Sdk.query.filter_by(
                used_by=user_id,
                status='used'
            ).order_by(Sdk.used_time.desc()).limit(limit).all()
            
            history = []
            for sdk in sdks:
                history.append({
                    'sdk_code': sdk.code,
                    'days': sdk.days,
                    'used_time': sdk.used_time.isoformat() if sdk.used_time else None
                })
            
            return history
            
        except Exception as e:
            logging.error(f"获取用户SDK历史记录失败: {str(e)}")
            return []
    
    @staticmethod
    def export_sdks_to_csv(filters: Optional[Dict] = None) -> str:
        """导出SDK到CSV格式
        
        Args:
            filters: 筛选条件
            
        Returns:
            CSV格式的字符串
        """
        try:
            query = Sdk.query
            
            # 应用筛选条件
            if filters:
                if filters.get('status'):
                    query = query.filter_by(status=filters['status'])
                if filters.get('days'):
                    query = query.filter_by(days=filters['days'])
                if filters.get('search'):
                    search_term = f"%{filters['search']}%"
                    query = query.filter(
                        db.or_(
                            Sdk.code.like(search_term),
                            User.username.like(search_term)
                        )
                    ).join(User, Sdk.used_by == User.id, isouter=True)
            
            sdks = query.order_by(Sdk.created_at.desc()).all()
            
            # 生成CSV内容
            csv_lines = ['SDK码,VIP天数,状态,创建时间,使用时间,使用者']
            
            for sdk in sdks:
                used_time = sdk.used_time.strftime('%Y-%m-%d %H:%M:%S') if sdk.used_time else ''
                username = ''
                if sdk.used_by:
                    user = User.query.get(sdk.used_by)
                    username = user.username if user else ''
                
                csv_lines.append(
                    f'"{sdk.code}",{sdk.days},{sdk.status},' +
                    f'"{sdk.created_at.strftime("%Y-%m-%d %H:%M:%S")}","{used_time}","{username}"'
                )
            
            return '\n'.join(csv_lines)
            
        except Exception as e:
            logging.error(f"导出SDK到CSV失败: {str(e)}")
            return 'SDK码,VIP天数,状态,创建时间,使用时间,使用者\n导出失败'