import json
import os
import dateutil.parser
from datetime import datetime
from flask import current_app, Blueprint, request, jsonify
from flask_login import current_user
from .utils.flaskcache import cache, dep_zone
from idms.common.irods.irods_sessions import irods_manager
from idms.common.filesys.fs_irods import fs_irods

bp = Blueprint('messages', __name__, url_prefix='/messages')

def get_my_login_messages():
    login_messages = load_messages(category='login', only_current=True)
    max_id = current_user.settings.setdefault('maxmsgid', 0)
    if login_messages:
        messagelist = sorted(login_messages, key=lambda x: x['key'])
        return [ message.get('msg') for message in messagelist if int(message.get('key', 0)) > max_id ]
    else:
        return []


def confirm():
    login_messages = load_messages()
    max_id = max([ m.get('key', 0) for m in login_messages.get('messages') ])
    current_user.settings[maxid_key()] =  max_id


@bp.route('/api', methods=['GET', 'POST'])
def message_api():
    if request.method == 'GET':
        msgs = load_messages()
        return jsonify(msgs)
    elif request.method == 'POST':
        requestdata = request.form.to_dict()
        messages = {}
        for k, v in requestdata.items():
            i, tag = k.split('_')
            if tag == 'time':
                times = v.split(' - ')
                if len(times) == 2:
                    start, end = times
                    messages.setdefault(i, {})['start'] = start
                    messages.setdefault(i, {})['end'] = end
            else:
                messages.setdefault(i, {})[tag] = v
        messagelist = list(messages.values())
        write_messages(messagelist)
    return messagelist

@cache.memoize(timeout=600, make_name=dep_zone)
def load_messages(category=None, only_current=False):
    if not hasattr(current_user, 'irods_zone'):
        return []
    all_messages = []
    messageobject = os.path.join('/', current_user.irods_zone, current_app.config.get("MESSAGES_OBJECT","none"))
    with irods_manager.session(current_user) as session:
        try:
            ifs = fs_irods(session=session)
            if ifs.fileexists(messageobject):
                obj = ifs.getfile(messageobject)
                messages_json = obj.open('r').read().decode('utf-8')
                all_messages = json.loads(messages_json).get('messages', [])
        except Exception as ex:
            # Do not break the website if the message file has an invalid format
            pass
    if category is None:
        category_messages = all_messages
    else:
        category_messages = [ msg for msg in all_messages if msg.get('category', 'NOT_SET') == category ]
    if only_current:
        messages = []
        for msg in category_messages:
            valid_msg = True
            try:
                if (ts := msg.get("start")):
                    if dateutil.parser.parse(ts) > datetime.now():
                        continue
                if (ts := msg.get("end")):
                    if dateutil.parser.parse(ts) < datetime.now():
                        continue
                messages.append(msg)
            except:
                # skip message with invalid time fields
                pass
    else:
        messages = category_messages
    return messages        


def write_messages(all_messages):
    if not hasattr(current_user, 'irods_zone'):
        return []
    messageobject = os.path.join('/', current_user.irods_zone, current_app.config.get("MESSAGES_OBJECT","none"))
    with irods_manager.session(current_user) as session:
        try:
            if fs_irods(session=session).fileexists(messageobject):
                messagestring = json.dumps({ 'messages' : all_messages}, indent=4)
                obj = fs_irods(session=session).getfile(messageobject)
                messages_json = obj.open('w').write(messagestring.encode())
        except Exception as ex:
            # Do not break the website if the message file has an invalid format
            pass
        cache.delete_memoized(load_messages)
    return all_messages    