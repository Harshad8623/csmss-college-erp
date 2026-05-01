from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from app.models import Notification, PushSubscription
from app.extensions import db

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('/')
@login_required
def index():
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).limit(50).all()
    shown_ids = [n.id for n in notifications if not n.is_read]
    if shown_ids:
        Notification.query.filter(Notification.id.in_(shown_ids))\
            .update({'is_read': True}, synchronize_session=False)
        db.session.commit()
    return render_template('notifications/index.html', notifications=notifications)

@notifications_bp.route('/mark-read/<int:id>', methods=['POST'])
@login_required
def mark_read(id):
    n = Notification.query.get_or_404(id)
    if n.user_id == current_user.id:
        n.is_read = True
        db.session.commit()
    target = n.link or url_for('dashboard.index')
    if target.startswith('http') or target.startswith('//'):
        target = url_for('dashboard.index')
    return redirect(target)

@notifications_bp.route('/api/unread')
@login_required
def unread_api():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    recent = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).limit(5).all()
    return jsonify({
        'count': count,
        'notifications': [{'id': n.id, 'message': n.message, 'type': n.type,
                           'link': n.link, 'is_read': n.is_read} for n in recent]
    })

@notifications_bp.route('/api/subscribe', methods=['POST'])
@login_required
def subscribe():
    """Save a browser's push subscription to the database."""
    data = request.get_json(silent=True)
    if not data or 'endpoint' not in data:
        return jsonify({'error': 'Invalid subscription'}), 400

    endpoint = data.get('endpoint')
    keys     = data.get('keys', {})
    p256dh   = keys.get('p256dh', '')
    auth     = keys.get('auth', '')

    if not p256dh or not auth:
        return jsonify({'error': 'Missing keys'}), 400

    # Upsert: if this endpoint already exists, update it
    sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if sub:
        sub.user_id    = current_user.id
        sub.p256dh     = p256dh
        sub.auth       = auth
        sub.user_agent = request.headers.get('User-Agent', '')[:300]
    else:
        sub = PushSubscription(
            user_id    = current_user.id,
            endpoint   = endpoint,
            p256dh     = p256dh,
            auth       = auth,
            user_agent = request.headers.get('User-Agent', '')[:300]
        )
        db.session.add(sub)

    db.session.commit()
    return jsonify({'status': 'subscribed'}), 201

@notifications_bp.route('/api/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    """Remove a browser's push subscription."""
    data = request.get_json(silent=True)
    if data and 'endpoint' in data:
        PushSubscription.query.filter_by(
            endpoint=data['endpoint'],
            user_id=current_user.id
        ).delete()
        db.session.commit()
    return jsonify({'status': 'unsubscribed'})


@notifications_bp.route('/api/push-status')
@login_required
def push_status():
    """Returns how many push subscriptions this user has saved in DB."""
    count = PushSubscription.query.filter_by(user_id=current_user.id).count()
    return jsonify({'subscriptions_in_db': count, 'user_id': current_user.id})


@notifications_bp.route('/api/push-test', methods=['GET', 'POST'])
@login_required
def push_test():
    """Synchronous test push — returns exact error per device for debugging."""
    from flask import current_app
    from app.models import PushSubscription
    import json

    subs = PushSubscription.query.filter_by(user_id=current_user.id).all()
    if not subs:
        return jsonify({'status': 'no_subscription',
                        'message': 'No subscriptions in DB. Grant Chrome notification permission first.'}), 400

    pub_key      = current_app.config.get('VAPID_PUBLIC_KEY', '')
    priv_key     = current_app.config.get('VAPID_PRIVATE_KEY', '')
    claims_email = current_app.config.get('VAPID_CLAIMS_EMAIL', '')

    results = []
    for sub in subs:
        entry = {'endpoint_tail': sub.endpoint[-40:], 'result': None, 'error': None}
        try:
            from pywebpush import webpush, WebPushException
            payload = json.dumps({
                'title': 'CSMSS ERP — Push Test',
                'body':  '🔔 Background push working! You received this with Chrome closed.',
                'type':  'success',
                'url':   '/notifications/',
                'icon':  '/static/img/college_logo.png',
            })
            resp = webpush(
                subscription_info={'endpoint': sub.endpoint,
                                   'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}},
                data=payload,
                vapid_private_key=priv_key,
                vapid_claims={'sub': f'mailto:{claims_email}'},
            )
            entry['result'] = f'HTTP {resp.status_code}'
        except Exception as e:
            entry['error'] = str(e)[:300]
        results.append(entry)

    return jsonify({
        'vapid_public_key_set':  bool(pub_key),
        'vapid_private_key_set': bool(priv_key),
        'claims_email':          claims_email,
        'devices_attempted':     len(subs),
        'results':               results,
    })
