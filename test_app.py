import os
from app import create_app
from app.extensions import db
from app.models import User, Roles

app = create_app()

with app.app_context():
    # create a dummy user
    u = User.query.filter_by(role=Roles.SUPER_ADMIN).first()
    if not u:
        u = User(name='Admin', email='admin@test.com', password_hash='x', role=Roles.SUPER_ADMIN)
        db.session.add(u)
        db.session.commit()

    with app.test_client() as client:
        # Simulate login
        with client.session_transaction() as sess:
            sess['_user_id'] = str(u.id)
            sess['_fresh'] = True
        
        response = client.get('/attendance/mark')
        print("Status code:", response.status_code)
        if response.status_code == 500:
            print(response.text)
