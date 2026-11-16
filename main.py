from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from zlapi import ZaloAPI, ThreadType, Message
from zlapi.models import Mention, MultiMention, MessageStyle, MultiMsgStyle
import threading, time, random, json, os, uuid, re, base64
from datetime import datetime

API_KEY = "8820814773961806095"
SECRET_KEY = "e2d98bb618b02b0465a1b9365d6c2626"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AVATAR_DIR = os.path.join(BASE_DIR, "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

SUPER_ADMIN_PASS = "caoquockietdz29082012"
SUB_ADMIN_PASS = "gojohouseno1sanwar"

active_sessions = {}
cookie_history = {}
COLOR_LIST = ["#DB342E", "#15A85F", "#F27806", "#F7B503", "#FFFFFF", "#000000"]

USER_FILE = os.path.join(BASE_DIR, "users.json")
SESSION_FILE = os.path.join(BASE_DIR, "sessions.json")

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_profiles = load_json(USER_FILE)
active_tokens = load_json(SESSION_FILE)

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def save_cookie_history(name, ip, cookie_str, imei):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cookie_history[cookie_str] = {
        "name": name,
        "ip": ip,
        "imei": imei,
        "time": now
    }

@app.route('/avatars/<filename>')
def serve_avatar(filename):
    return send_from_directory(AVATAR_DIR, filename)

@app.route('/api/update_avatar', methods=['POST'])
def update_avatar():
    token = request.headers.get('Authorization')
    username = active_tokens.get(token)
    if not username or username not in user_profiles:
        return jsonify({"success": False, "msg": "Chưa đăng nhập!"})
    avatar_base64 = request.json.get('avatar', '')
    if not avatar_base64 or not avatar_base64.startswith('data:image'):
        return jsonify({"success": False, "msg": "Dữ liệu ảnh không hợp lệ!"})
    try:
        format, imgstr = avatar_base64.split(';base64,')
        ext = format.split('/')[-1]
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', username)
        filename = os.path.join(AVATAR_DIR, f"{safe_name}.{ext}")
        with open(filename, "wb") as fh:
            fh.write(base64.b64decode(imgstr))
        avatar_path = f"/avatars/{safe_name}.{ext}"
        user_profiles[username]["avatar"] = avatar_path
        save_json(USER_FILE, user_profiles)
        return jsonify({"success": True, "msg": "Cập nhật Avatar thành công!", "avatar": avatar_path})
    except Exception as e:
        return jsonify({"success": False, "msg": f"Lỗi lưu ảnh: {e}"})

@app.route('/api/admin/delete_user', methods=['POST'])
def delete_user():
    token = request.headers.get('Authorization')
    username = active_tokens.get(token)
    if not username or user_profiles.get(username, {}).get("role") != "King":
        return jsonify({"success": False, "msg": "Chỉ Admin chính mới có quyền xóa tài khoản!"})
    target_name = request.json.get('target_name')
    if target_name == username:
        return jsonify({"success": False, "msg": "Bạn không thể tự xóa tài khoản của chính mình!"})
    if target_name not in user_profiles:
        return jsonify({"success": False, "msg": "Không tìm thấy tài khoản này."})
    for tid in list(active_sessions.keys()):
        if active_sessions[tid]["name"] == target_name:
            try: active_sessions[tid]["tool_obj"].stop()
            except: pass
            del active_sessions[tid]
    avatar_path = user_profiles[target_name].get("avatar", "")
    if avatar_path and avatar_path.startswith("/avatars/"):
        file_path = os.path.join(AVATAR_DIR, os.path.basename(avatar_path))
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
    del user_profiles[target_name]
    save_json(USER_FILE, user_profiles)
    tokens_to_remove = [t for t, u in active_tokens.items() if u == target_name]
    for t in tokens_to_remove:
        del active_tokens[t]
    save_json(SESSION_FILE, active_tokens)
    return jsonify({"success": True, "msg": f"Đã xóa tài khoản {target_name} và dừng các dự án liên quan."})

@app.route('/api/admin/cookies', methods=['GET'])
def get_admin_cookies():
    token = request.headers.get('Authorization')
    username = active_tokens.get(token)
    if not username or user_profiles.get(username, {}).get("role") != "King":
        return jsonify({"success": False, "msg": "Chỉ Admin chính mới có quyền xem!"})
    result = []
    for c_str, data in cookie_history.items():
        result.append({
            "cookie": c_str,
            "name": data["name"],
            "ip": data["ip"],
            "imei": data["imei"],
            "time": data["time"]
        })
    result.sort(key=lambda x: x["time"], reverse=True)
    return jsonify({"success": True, "cookies": result})

@app.route('/api/admin/users_history', methods=['GET'])
def get_users_history():
    token = request.headers.get('Authorization')
    username = active_tokens.get(token)
    if not username or user_profiles.get(username, {}).get("role") != "King":
        return jsonify({"success": False, "msg": "Chỉ Admin chính mới có quyền xem!"})
    result = []
    count_king = 0
    count_linh = 0
    count_user = 0
    for u_name, data in user_profiles.items():
        if data["role"] == "King": count_king += 1
        elif data["role"] == "lính của King": count_linh += 1
        elif data["role"] == "dân thường": count_user += 1
        result.append({
            "name": u_name,
            "role": data["role"],
            "avatar": data.get("avatar", ""),
            "ip": data.get("ip", "Chưa rõ"),
            "login_time": data.get("last_seen", "Chưa rõ"),
            "last_seen": data.get("last_seen", "Chưa rõ")
        })
    result.sort(key=lambda x: x["last_seen"], reverse=True)
    stats = {"king": count_king, "linh": count_linh, "user": count_user}
    return jsonify({"success": True, "users": result, "stats": stats})

@app.route('/api/admin/sessions', methods=['GET'])
def get_admin_sessions():
    token = request.headers.get('Authorization')
    username = active_tokens.get(token)
    if not username:
        return jsonify({"success": False, "msg": "Chưa đăng nhập!"})
    my_role = user_profiles.get(username, {}).get("role", "unknown")
    result = []
    for tid, data in active_sessions.items():
        display_ip = data["ip"] if my_role == "King" else "***.***.***.***"
        result.append({
            "task_id": tid,
            "ip": display_ip,
            "name": data["name"],
            "avatar": user_profiles.get(data["name"], {}).get("avatar", ""),
            "role": data["role"],
            "time": data["time"],
            "status": data["status"],
            "mode": data["mode"],
            "box_name": data.get("box_name", data.get("box_id"))
        })
    return jsonify({"success": True, "sessions": result, "my_role": my_role, "my_name": username})

@app.route('/api/admin/kill', methods=['POST'])
def admin_kill_session():
    token = request.headers.get('Authorization')
    username = active_tokens.get(token)
    my_role = user_profiles.get(username, {}).get("role", "unknown")
    task_id = request.json.get('task_id')
    if task_id not in active_sessions:
        return jsonify({"success": False, "msg": "Không tìm thấy phiên."})
    target_name = active_sessions[task_id]["name"]
    target_role = active_sessions[task_id]["role"]
    if my_role == "King": pass 
    elif my_role == "lính của King":
        if target_role == "dân thường": pass 
        else: return jsonify({"success": False, "msg": "Bạn không đủ quyền dừng Admin khác!"})
    elif my_role == "dân thường":
        if username != target_name:
            return jsonify({"success": False, "msg": "Bạn chỉ có thể dừng dự án của chính mình!"})
    else:
        return jsonify({"success": False, "msg": "Không có quyền!"})
    try: active_sessions[task_id]["tool_obj"].stop()
    except: pass
    del active_sessions[task_id]
    return jsonify({"success": True, "msg": "Đã dừng và xóa phiên này."})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    ip = get_client_ip()
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()
    avatar_base64 = data.get('avatar', '')
    if not name or not password:
        return jsonify({"success": False, "msg": "Vui lòng nhập Tên và Key!"})
    if name in user_profiles:
        return jsonify({"success": False, "msg": "Tên tài khoản này đã có người sử dụng!"})
    role = ""
    if password == SUPER_ADMIN_PASS:
        for u_data in user_profiles.values():
            if u_data.get("role") == "King":
                return jsonify({"success": False, "msg": "Hệ thống đã có Admin chính (King). Không thể tạo thêm!"})
        role = "King"
    elif password == SUB_ADMIN_PASS:
        role = "lính của King"
    else:
        return jsonify({"success": False, "msg": "Key không hợp lệ hoặc chưa được cấp phép!"})
    avatar_path = ""
    if avatar_base64 and avatar_base64.startswith('data:image'):
        try:
            format, imgstr = avatar_base64.split(';base64,')
            ext = format.split('/')[-1]
            safe_name = re.sub(r'[^a-zA-Z0-9]', '_', name)
            filename = os.path.join(AVATAR_DIR, f"{safe_name}.{ext}")
            with open(filename, "wb") as fh:
                fh.write(base64.b64decode(imgstr))
            avatar_path = f"/avatars/{safe_name}.{ext}"
        except Exception as e:
            print("Lỗi lưu avatar:", e)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_profiles[name] = {
        "password": password,
        "role": role,
        "avatar": avatar_path,
        "ip": ip,
        "last_seen": now
    }
    save_json(USER_FILE, user_profiles)
    new_token = str(uuid.uuid4())
    active_tokens[new_token] = name
    save_json(SESSION_FILE, active_tokens)
    return jsonify({"success": True, "token": new_token, "role": role, "name": name, "avatar": avatar_path})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    ip = get_client_ip()
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()
    if name not in user_profiles:
        return jsonify({"success": False, "msg": "Tài khoản không tồn tại!"})
    user_data = user_profiles[name]
    if user_data["password"] != password:
        return jsonify({"success": False, "msg": "Sai mật khẩu (Key)!"})
    if "ip" in user_data and user_data["ip"] != ip:
         return jsonify({"success": False, "msg": "Tài khoản này đã bị khóa với một IP khác! Vui lòng dùng đúng thiết bị/Mạng đã đăng ký."})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_data["last_seen"] = now
    save_json(USER_FILE, user_profiles)
    new_token = str(uuid.uuid4())
    active_tokens[new_token] = name
    save_json(SESSION_FILE, active_tokens)
    return jsonify({
        "success": True, 
        "token": new_token, 
        "role": user_data["role"], 
        "name": name, 
        "avatar": user_data.get("avatar", "")
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization')
    if token in active_tokens:
        del active_tokens[token]
        save_json(SESSION_FILE, active_tokens)
    return jsonify({"success": True})

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    token = request.headers.get('Authorization')
    username = active_tokens.get(token)
    if username and username in user_profiles:
        role = user_profiles[username]["role"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_profiles[username]["last_seen"] = now
        save_json(USER_FILE, user_profiles)
        my_tabs = sum(1 for t in active_sessions.values() if t['name'] == username and t['status'] == 'running')
        max_tabs = "∞" if role in ["King", "lính của King"] else 10
        return jsonify({
            "authenticated": True, 
            "role": role,
            "name": username,
            "avatar": user_profiles[username].get("avatar", ""),
            "my_tabs": my_tabs,
            "max_tabs": max_tabs
        })
    return jsonify({"authenticated": False})

class ZaloSpamManager:
    def __init__(self, cookie_json, imei, box_id, message, delay, mode="text", tag_ids=None, tag_names=None, font_size=None, color=None, sticker_mode="1"):
        self.cookie = cookie_json
        self.imei = imei
        self.box_id = box_id
        if isinstance(message, str):
            self.message = message.replace('\\n', '\n')
        else:
            self.message = message
        self.delay = max(float(delay), 0.1)
        self.mode = mode
        self.tag_ids = tag_ids or []
        self.tag_names = tag_names or []
        self.is_running = True
        self.thread = None
        self.bot = None
        self.font_size = str(font_size) if font_size else None
        self.color = color if color else None
        self.sticker_mode = sticker_mode
        if self.mode == "tag" and isinstance(self.message, str):
            self.lines = [ln.strip() for ln in self.message.split('\n') if ln.strip()]
        else:
            self.lines = []
        self.stickers = [
            {"id": 25012, "cate": 10510},
            {"id": 23456, "cate": 10510} 
        ]
    def start(self):
        try:
            self.bot = ZaloAPI(API_KEY, SECRET_KEY, self.imei, self.cookie)
            self.bot.fetchAccountInfo()
        except Exception as e:
            return False
        self.is_running = True
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()
        return True
    def _get_style(self, text_length):
        styles = []
        current_color = self.color
        if current_color == "random":
            current_color = random.choice(COLOR_LIST)
        if self.font_size:
            styles.append(MessageStyle(offset=0, length=text_length, style="font", size=self.font_size, auto_format=False))
        if current_color and current_color != "":
            styles.append(MessageStyle(offset=0, length=text_length, style="color", color=current_color, auto_format=False))
        if styles:
            return MultiMsgStyle(styles)
        return None
    def worker(self):
        line_index = 0
        sticker_index = 0
        while self.is_running:
            try:
                if self.mode == "tag" and self.tag_ids and self.lines:
                    current_line = self.lines[line_index % len(self.lines)]
                    line_index += 1
                    batch_size = 5
                    for i in range(0, len(self.tag_ids), batch_size):
                        if not self.is_running: break
                        batch_ids = self.tag_ids[i:i+batch_size]
                        mentions = []
                        formatted = (current_line or "").rstrip() + " "
                        for uid, name in zip(batch_ids, self.tag_names[i:i+batch_size]):
                            tag = f"@{name}"
                            offset = len(formatted)
                            formatted += tag + " "
                            mentions.append(Mention(uid=uid, length=len(tag), offset=offset, auto_format=False))
                        multi = MultiMention(mentions)
                        style = self._get_style(len(formatted))
                        self.bot.send(Message(text=formatted, mention=multi, style=style), thread_id=self.box_id, thread_type=ThreadType.GROUP)
                        time.sleep(2)
                elif self.mode == "sticker":
                    if self.sticker_mode == "1":
                        self.bot.sendSticker(stickerType=7, stickerId=25012, cateId=10510, thread_id=self.box_id, thread_type=ThreadType.GROUP)
                    elif self.sticker_mode == "2":
                        self.bot.sendSticker(stickerType=7, stickerId=23456, cateId=10510, thread_id=self.box_id, thread_type=ThreadType.GROUP)
                    elif self.sticker_mode == "3":
                        st = self.stickers[sticker_index % 2]
                        sticker_index += 1
                        self.bot.sendSticker(stickerType=7, stickerId=st["id"], cateId=st["cate"], thread_id=self.box_id, thread_type=ThreadType.GROUP)
                else:
                    style = self._get_style(len(self.message))
                    self.bot.send(Message(text=self.message, style=style), thread_id=self.box_id, thread_type=ThreadType.GROUP)
            except Exception as e:
                time.sleep(5)
            time.sleep(self.delay * random.uniform(1.0, 1.2))
    def stop(self):
        self.is_running = False

def parse_cookie(cookie_str):
    if cookie_str.strip().startswith("{"): return json.loads(cookie_str)
    cookies = {}
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies

@app.route('/')
def index():
    return send_file(os.path.join(BASE_DIR, 'index.html'))

MUSIC_FILES = ["cyruszalo.mp3", "nhac2.mp3", "nhac3.mp3", "nhac4.mp3"]

@app.route('/api/music_list', methods=['GET'])
def music_list():
    files = []
    for f in MUSIC_FILES:
        if os.path.isfile(os.path.join(BASE_DIR, f)):
            files.append(f"/music/{f}")
    return jsonify({"success": True, "tracks": files})

@app.route('/music/<path:filename>', methods=['GET', 'HEAD'])
def serve_music(filename):
    if filename not in MUSIC_FILES:
        return jsonify({"success": False, "msg": "File không hợp lệ"}), 404
    music_file = os.path.join(BASE_DIR, filename)
    if not os.path.isfile(music_file):
        return jsonify({"success": False, "msg": f"Không tìm thấy {filename}"}), 404
    return send_from_directory(
        BASE_DIR, filename,
        mimetype='audio/mpeg', conditional=True, max_age=3600
    )

@app.route('/api/start', methods=['POST'])
def start():
    token = request.headers.get('Authorization')
    username = active_tokens.get(token)
    if not username:
        return jsonify({"success": False, "msg": "Vui lòng đăng nhập lại!"})
    my_role = user_profiles.get(username, {}).get("role", "unknown")
    my_ip = get_client_ip()
    data = request.json
    raw_cookie = data.get('cookie')
    imei = data.get('imei', '').strip()
    box_ids = data.get('box_ids', [])
    box_names = data.get('box_names', [])
    tags_data = data.get('tags_data', {})
    message = data.get('message', 'Hello')
    delay = float(data.get('delay', 10))
    mode = data.get('mode', 'text')
    font_size = data.get('font_size')
    color = data.get('color')
    sticker_mode = data.get('sticker_mode', '1')
    if not box_ids:
        return jsonify({"success": False, "msg": "Chưa chọn nhóm nào!"})
    if my_role == "dân thường":
        my_tabs = sum(1 for t in active_sessions.values() if t['name'] == username and t['status'] == 'running')
        if my_tabs + len(box_ids) > 10:
            return jsonify({"success": False, "msg": f"Bạn chọn {len(box_ids)} nhóm, nhưng chỉ còn {10 - my_tabs} tab trống."})
    if not raw_cookie or not imei: 
        return jsonify({"success": False, "msg": "Thiếu Cookie hoặc IMEI!"})
    try: 
        cookie_json = parse_cookie(raw_cookie)
    except: 
        return jsonify({"success": False, "msg": "Cookie không hợp lệ!"})
    save_cookie_history(username, my_ip, raw_cookie, imei)
    success_count = 0
    for idx, bid in enumerate(box_ids):
        bname = box_names[idx] if idx < len(box_names) else bid
        current_tags = tags_data.get(bid, {})
        t_ids = current_tags.get('ids', [])
        t_names = current_tags.get('names', [])
        task_id = str(uuid.uuid4())[:8]
        tool = ZaloSpamManager(cookie_json, imei, bid, message, delay, mode, t_ids, t_names, font_size, color, sticker_mode)
        if tool.start():
            active_sessions[task_id] = {
                "ip": my_ip,
                "name": username,
                "role": my_role,
                "time": datetime.now().strftime("%H:%M:%S"),
                "status": "running",
                "mode": mode,
                "box_id": bid,
                "box_name": bname,
                "tool_obj": tool
            }
            success_count += 1
        time.sleep(1)
    if success_count > 0:
        return jsonify({"success": True, "msg": f"Đã khởi chạy thành công {success_count}/{len(box_ids)} nhóm!"})
    return jsonify({"success": False, "msg": "Lỗi đăng nhập Zalo, không thể chạy nhóm nào!"})

@app.route('/api/stop', methods=['POST'])
def stop():
    data = request.json
    task_id = data.get('task_id')
    if task_id in active_sessions:
        try: active_sessions[task_id]["tool_obj"].stop()
        except: pass
        del active_sessions[task_id]
        return jsonify({"success": True, "msg": "Đã dừng và xóa tool."})
    return jsonify({"success": False, "msg": "Không tìm thấy tiến trình."})

@app.route('/api/get_box', methods=['POST'])
def get_box():
    data = request.json
    cookie_str = data.get('cookie', '').strip()
    imei = data.get('imei', '').strip()
    if not cookie_str or not imei: return jsonify({"success": False, "msg": "Thiếu Cookie hoặc IMEI!"})
    try: cookie_json = parse_cookie(cookie_str)
    except: return jsonify({"success": False, "msg": "Cookie sai định dạng!"})
    try:
        bot = ZaloAPI(API_KEY, SECRET_KEY, imei, cookie_json)
        data_groups = bot.fetchAllGroups()
        groups = []
        grid_map = getattr(data_groups, "gridVerMap", {}) or getattr(data_groups, "gridInfoMap", {})
        for gid in grid_map.keys():
            try:
                info = bot.fetchGroupInfo(gid)
                name = info.gridInfoMap[gid].get("name", str(gid))
            except: name = str(gid)
            groups.append({"id": gid, "name": name})
        return jsonify({"success": True, "threads": groups})
    except Exception as e:
        return jsonify({"success": False, "msg": f"Lỗi Zalo: {e}"})

@app.route('/api/get_members', methods=['POST'])
def get_members():
    data = request.json
    cookie_str = data.get('cookie', '').strip()
    imei = data.get('imei', '').strip()
    group_ids = data.get('group_ids', [])
    group_names = data.get('group_names', [])
    if not cookie_str or not group_ids or not imei: 
        return jsonify({"success": False, "msg": "Thiếu dữ liệu (Cookie, IMEI, Group ID)!"})
    try: 
        cookie_json = parse_cookie(cookie_str)
    except: 
        return jsonify({"success": False, "msg": "Cookie sai định dạng!"})
    try:
        bot = ZaloAPI(API_KEY, SECRET_KEY, imei, cookie_json)
        result_data = []
        for idx, gid in enumerate(group_ids):
            gname = group_names[idx] if idx < len(group_names) else gid
            info = bot.fetchGroupInfo(gid)
            mem_list = info.gridInfoMap.get(gid, {}).get("memVerList", [])
            members = []
            for m in mem_list:
                uid = m.split("_")[0]
                try:
                    uinfo = bot.fetchUserInfo(uid)
                    name = uinfo.changed_profiles.get(uid, {}).get('displayName', uid)
                except: name = uid
                members.append({"id": uid, "name": name})
                time.sleep(0.1)
            result_data.append({
                "group_id": gid,
                "group_name": gname,
                "members": members
            })
        return jsonify({"success": True, "groups": result_data})
    except Exception as e:
        return jsonify({"success": False, "msg": f"Lỗi lấy thành viên: {e}"})

@app.route('/api/check_cookies', methods=['POST'])
def check_cookies():
    data = request.json
    imei_list_raw = data.get('imei_list', '').strip()
    cookie_list_raw = data.get('cookie_list', '').strip()
    if not imei_list_raw or not cookie_list_raw:
        return jsonify({"success": False, "msg": "Vui lòng nhập đủ danh sách IMEI và Cookie!"})
    imeis = [line.strip() for line in imei_list_raw.split('\n') if line.strip()]
    cookies = [line.strip() for line in cookie_list_raw.split('\n') if line.strip()]
    if len(imeis) != len(cookies):
        return jsonify({"success": False, "msg": f"Số lượng không khớp! IMEI: {len(imeis)} dòng, Cookie: {len(cookies)} dòng."})
    results = []
    for imei, cookie_str in zip(imeis, cookies):
        try:
            cookie_json = parse_cookie(cookie_str)
            bot = ZaloAPI(API_KEY, SECRET_KEY, imei, cookie_json)
            profile = bot.fetchAccountInfo().profile
            name = profile.get('displayName', 'Không rõ')
            uid = profile.get('userId', 'Không rõ')
            results.append({
                "status": "live", 
                "name": name, 
                "uid": uid, 
                "raw": f"IMEI: {imei} | Cookie: {cookie_str[:30]}..."
            })
        except Exception as e:
            results.append({
                "status": "die", 
                "msg": str(e), 
                "raw": f"IMEI: {imei} | Cookie: {cookie_str[:30]}..."
            })
    return jsonify({"success": True, "results": results})