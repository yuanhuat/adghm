import hashlib
import requests
import json
from urllib.parse import urlencode
from decimal import Decimal
from app.models.payment_config import PaymentConfig
from app.models.donation_order import DonationOrder, PaymentType
from app.models.payment_log import PaymentLog, PaymentLogType
from app import db
from flask import current_app

class PaymentService:
    """支付服务类"""
    
    def __init__(self, require_config=True):
        self.config = PaymentConfig.get_active_config()
        if require_config and not self.config:
            raise ValueError('支付配置未设置')
    
    def create_payment(self, order: DonationOrder):
        """创建支付订单"""
        try:
            # 构建支付参数
            params = self._build_payment_params(order)
            
            # 生成签名
            sign = self._generate_sign(params)
            params['sign'] = sign
            params['sign_type'] = 'MD5'
            
            # 记录请求数据
            request_data = params.copy()
            
            # 发起支付请求
            if order.payment_type == PaymentType.ALIPAY:
                # 支付宝支付 - 页面跳转
                payurl = f"{self.config.submit_url}?{urlencode(params)}"
                return {
                    'success': True,
                    'payurl': payurl,
                    'request_data': request_data
                }
            elif order.payment_type == PaymentType.WXPAY:
                # 微信支付 - API接口
                response = requests.post(self.config.api_url, data=params, timeout=30)
                response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {'raw': response.text}
                
                if response.status_code == 200 and response_data.get('code') == 1:
                    return {
                        'success': True,
                        'qrcode': response_data.get('qrcode'),
                        'payurl': response_data.get('payurl'),
                        'request_data': request_data,
                        'response_data': response_data
                    }
                else:
                    return {
                        'success': False,
                        'message': response_data.get('msg', '支付接口返回异常'),
                        'request_data': request_data,
                        'response_data': response_data
                    }
            else:
                return {
                    'success': False,
                    'message': '不支持的支付方式'
                }
                
        except requests.RequestException as e:
            PaymentLog.create_log(
                log_type=PaymentLogType.ERROR,
                title=f'支付请求网络异常 {order.order_no}',
                order_no=order.order_no,
                content=str(e),
                is_success=False,
                error_message=str(e)
            )
            return {
                'success': False,
                'message': '网络异常，请重试'
            }
        except Exception as e:
            PaymentLog.create_log(
                log_type=PaymentLogType.ERROR,
                title=f'支付请求异常 {order.order_no}',
                order_no=order.order_no,
                content=str(e),
                is_success=False,
                error_message=str(e)
            )
            return {
                'success': False,
                'message': '支付系统异常'
            }
    
    def _build_payment_params(self, order: DonationOrder):
        """构建支付参数"""
        # 根据支付方式设置type参数
        if order.payment_type == PaymentType.ALIPAY:
            pay_type = 'alipay'
        elif order.payment_type == PaymentType.WXPAY:
            pay_type = 'wxpay'
        else:
            raise ValueError('不支持的支付方式')
        
        params = {
            'pid': self.config.merchant_id,
            'type': pay_type,
            'out_trade_no': order.order_no,
            'notify_url': self.config.notify_url,
            'return_url': self.config.return_url,
            'name': f'爱心捐赠 - {order.donor_name or "匿名"}',
            'money': str(order.amount),
            'sitename': '爱心捐赠平台',
            'clientip': order.client_ip or '127.0.0.1',  # 添加客户端IP地址
            'device': 'pc'  # 设备类型，默认为pc
        }
        
        return params
    
    def _generate_sign(self, params):
        """生成MD5签名"""
        # 过滤空值和sign参数
        filtered_params = {k: v for k, v in params.items() 
                          if v is not None and v != '' and k != 'sign' and k != 'sign_type'}
        
        # 按key排序
        sorted_params = sorted(filtered_params.items())
        
        # 构建签名字符串
        sign_str = '&'.join([f'{k}={v}' for k, v in sorted_params])
        sign_str += self.config.merchant_key
        
        # 生成MD5签名
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    def verify_notify(self, data):
        """验证异步通知签名"""
        try:
            if 'sign' not in data:
                return False
            
            received_sign = data['sign']
            calculated_sign = self._generate_sign(data)
            
            return received_sign.lower() == calculated_sign.lower()
            
        except Exception as e:
            PaymentLog.create_log(
                log_type=PaymentLogType.ERROR,
                title='验证通知签名异常',
                content=str(e),
                is_success=False,
                error_message=str(e)
            )
            return False
    
    def query_order(self, order_no):
        """查询订单状态"""
        try:
            params = {
                'pid': self.config.merchant_id,
                'out_trade_no': order_no
            }
            
            # 生成签名
            sign = self._generate_sign(params)
            params['sign'] = sign
            params['sign_type'] = 'MD5'
            
            # 发起查询请求
            response = requests.post(f"{self.config.api_url}?act=order", data=params, timeout=30)
            response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {'raw': response.text}
            
            if response.status_code == 200 and response_data.get('code') == 1:
                return {
                    'success': True,
                    'data': response_data.get('data', {})
                }
            else:
                return {
                    'success': False,
                    'message': response_data.get('msg', '查询失败')
                }
                
        except requests.RequestException as e:
            PaymentLog.create_log(
                log_type=PaymentLogType.ERROR,
                title=f'查询订单网络异常 {order_no}',
                content=str(e),
                is_success=False,
                error_message=str(e)
            )
            return {
                'success': False,
                'message': '网络异常，请重试'
            }
        except Exception as e:
            PaymentLog.create_log(
                log_type=PaymentLogType.ERROR,
                title=f'查询订单异常 {order_no}',
                content=str(e),
                is_success=False,
                error_message=str(e)
            )
            return {
                'success': False,
                'message': '查询系统异常'
            }
    
    def test_config(self, test_config=None):
        """测试支付配置"""
        try:
            # 使用传入的配置或实例配置
            config = test_config if test_config else {
                'merchant_id': self.config.merchant_id,
                'merchant_key': self.config.merchant_key,
                'api_url': self.config.api_url,
                'submit_url': self.config.submit_url
            }
            
            # 构建测试参数
            test_params = {
                'pid': config['merchant_id'],
                'type': 'alipay',
                'out_trade_no': 'TEST_' + str(int(time.time())),
                'notify_url': 'http://test.com/notify',
                'return_url': 'http://test.com/return',
                'name': '配置测试',
                'money': '0.01',
                'sitename': '测试',
                'clientip': '127.0.0.1'  # 添加客户端IP地址
            }
            
            # 生成签名（使用测试配置的密钥）
            sign = self._generate_test_sign(test_params, config['merchant_key'])
            test_params['sign'] = sign
            test_params['sign_type'] = 'MD5'
            
            # 发起测试请求（不实际支付）
            response = requests.post(config['api_url'], data=test_params, timeout=10)
            
            if response.status_code == 200:
                # 尝试解析响应
                try:
                    response_data = response.json()
                    if response_data.get('code') == 1:
                        return {
                            'success': True,
                            'message': '配置测试通过，API连接正常'
                        }
                    else:
                        return {
                            'success': True,
                            'message': f'API连接正常，返回: {response_data.get("msg", "未知响应")}'
                        }
                except:
                    # 如果不是JSON响应，检查是否包含错误信息
                    response_text = response.text
                    if 'error' in response_text.lower() or 'fail' in response_text.lower():
                        return {
                            'success': False,
                            'message': f'API返回错误: {response_text[:100]}'
                        }
                    else:
                        return {
                            'success': True,
                            'message': 'API连接正常，配置有效'
                        }
            else:
                return {
                    'success': False,
                    'message': f'测试失败，HTTP状态码: {response.status_code}'
                }
                
        except requests.RequestException as e:
            return {
                'success': False,
                'message': f'网络连接失败: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'测试异常: {str(e)}'
            }
    
    def _generate_test_sign(self, params, merchant_key):
        """生成测试签名"""
        # 过滤空值和sign参数
        filtered_params = {k: v for k, v in params.items() if v and k not in ['sign', 'sign_type']}
        
        # 按键名排序
        sorted_params = sorted(filtered_params.items())
        
        # 构建签名字符串
        sign_str = '&'.join([f'{k}={v}' for k, v in sorted_params])
        sign_str += merchant_key
        
        # MD5加密
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    @staticmethod
    def validate_config(config_data):
        """验证支付配置"""
        errors = []
        
        # 验证必要字段
        required_fields = {
            'merchant_id': '商户ID',
            'merchant_key': '商户密钥',
            'notify_url': '异步通知地址',
            'return_url': '同步返回地址'
        }
        
        for field, name in required_fields.items():
            if not config_data.get(field):
                errors.append(f'{name}不能为空')
        
        # 验证URL格式
        url_fields = ['notify_url', 'return_url', 'api_url', 'submit_url']
        for field in url_fields:
            url = config_data.get(field)
            if url and not (url.startswith('http://') or url.startswith('https://')):
                errors.append(f'{field}必须是有效的HTTP(S)地址')
        
        # 验证金额范围
        try:
            min_amount = Decimal(str(config_data.get('min_amount', 1.00)))
            max_amount = Decimal(str(config_data.get('max_amount', 10000.00)))
            
            if min_amount <= 0:
                errors.append('最小金额必须大于0')
            if max_amount <= min_amount:
                errors.append('最大金额必须大于最小金额')
            if max_amount > 50000:
                errors.append('最大金额不能超过50000元')
                
        except (ValueError, TypeError):
            errors.append('金额格式错误')
        
        # 验证支付方式
        if not config_data.get('enable_alipay') and not config_data.get('enable_wxpay'):
            errors.append('至少需要启用一种支付方式')
        
        return errors

import time  # 添加time模块导入