from app import create_app, db
from app.models.user import User
from app.models.donation_record import DonationRecord

app = create_app()
app.app_context().push()

user = User.query.filter_by(username='52943792').first()
if user:
    print(f'用户: {user.username}')
    print(f'用户ID: {user.id}')
    print(f'是否管理员: {user.is_admin}')
    print(f'是否VIP: {user.is_vip()}')
    
    records = DonationRecord.query.filter_by(user_id=user.id).all()
    print(f'捐赠记录数量: {len(records)}')
    for i, r in enumerate(records):
        print(f'记录{i+1}: 订单号={r.order_id}, 金额={r.amount}, 状态={r.status}')
else:
    print('未找到用户')