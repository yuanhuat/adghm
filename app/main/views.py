import logging
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.client_mapping import ClientMapping
from app.models.operation_log import OperationLog
from app.services.adguard_service import AdGuardService
from . import main

@main.route('/')
@login_required
def index():
    """用户主页
    
    显示用户的客户端列表和基本信息
    """
    return render_template('main/index.html')

@main.route('/clients')
@login_required
def clients():
    """客户端管理页面
    
    显示用户的所有客户端及其详细信息
    """
    return render_template('main/clients.html')

@main.route('/clients/<int:mapping_id>', methods=['GET', 'PUT'])
@login_required
def client_details(mapping_id):
    """获取或更新客户端配置
    
    Args:
        mapping_id: 客户端映射ID
    """
    mapping = ClientMapping.query.get_or_404(mapping_id)
    
    # 验证权限
    if mapping.user_id != current_user.id:
        return jsonify({'error': '没有权限操作此客户端'}), 403
    
    if request.method == 'GET':
        try:
            # 获取AdGuardHome客户端信息
            adguard = AdGuardService()
            client_info = adguard.find_client(mapping.client_name)
            
            if not client_info:
                return jsonify({
                    'client_ids': mapping.client_ids,
                    'use_global_settings': True,
                    'filtering_enabled': True,
                    'safebrowsing_enabled': False,
                    'parental_enabled': False
                })
            
            return jsonify({
                'client_ids': mapping.client_ids,
                'use_global_settings': client_info.get('use_global_settings', True),
                'filtering_enabled': client_info.get('filtering_enabled', True),
                'safebrowsing_enabled': client_info.get('safebrowsing_enabled', False),
                'parental_enabled': client_info.get('parental_enabled', False)
            })
            
        except Exception as e:
            return jsonify({'error': f'获取客户端信息失败：{str(e)}'}), 500
            
    elif request.method == 'PUT':
        data = request.get_json()
        use_global_settings = data.get('use_global_settings', True)
        filtering_enabled = data.get('filtering_enabled', True)
        safebrowsing_enabled = data.get('safebrowsing_enabled', False)
        parental_enabled = data.get('parental_enabled', False)
        
        # 只有管理员可以修改设备标识
        if current_user.is_admin:
            client_ids = data.get('client_ids', [])
        else:
            # 普通用户保持原有设备标识不变
            client_ids = mapping.client_ids
        
        try:
            # 更新AdGuardHome客户端
            adguard = AdGuardService()
            adguard.update_client(
                name=mapping.client_name,
                ids=client_ids,
                use_global_settings=use_global_settings,
                filtering_enabled=filtering_enabled,
                safebrowsing_enabled=safebrowsing_enabled,
                parental_enabled=parental_enabled
            )

            # 更新映射记录
            mapping.client_ids = client_ids

            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update_client',
                target_type='client',
                target_id=mapping.client_name,
                details=f'更新客户端{mapping.client_name}配置'
            )
            db.session.add(log)

            db.session.commit()
            return jsonify({'message': '客户端更新成功'})

        except Exception as e:
            db.session.rollback()
            logging.error(f'更新客户端 {mapping.client_name} 失败: {str(e)}')
            return jsonify({'error': f'更新客户端失败：{str(e)}'}), 500