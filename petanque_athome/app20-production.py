from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np
import base64
import os
from datetime import datetime, timedelta
from ultralytics import YOLO
from supabase import create_client, Client
from datetime import timezone, timedelta

app = Flask(__name__)
# อนุญาตให้หน้าเว็บ (Frontend) ทุกที่สามารถเรียกใช้งาน API นี้ได้
CORS(app, resources={r"/*": {"origins": "*"}})

# ═════════════════════════════════════════════════════════════════════
# 1. ตั้งค่า Supabase (ระบบฐานข้อมูล Cloud)
# ═════════════════════════════════════════════════════════════════════
SUPABASE_URL = "https://gxevbufcksazoqvhvfji.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd4ZXZidWZja3Nhem9xdmh2ZmppIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk1MjE2NjIsImV4cCI6MjA5NTA5NzY2Mn0.4GOpkp79uP_NSwtzqDFECWKIVeLWW921jfXMMX3MwUo"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ เชื่อมต่อ Supabase สำเร็จ! พร้อมใช้งาน")
except Exception as e:
    print(f"❌ เชื่อมต่อ Supabase ไม่สำเร็จ: {e}")
    supabase = None

# ═════════════════════════════════════════════════════════════════════
# 2. ตั้งค่า AI โมเดล (YOLO) และค่ากล้อง (Camera Calibration)
# ═════════════════════════════════════════════════════════════════════
MODEL_FILE = "best3-perfect.pt"
if os.path.exists(MODEL_FILE):
    _yolo_model = YOLO(MODEL_FILE)
    print("✅ โหลดโมเดล YOLO (best.pt) สำเร็จ!")
else:
    _yolo_model = None
    print("⚠️ ไม่พบไฟล์ best.pt (ระบบจับภาพอัตโนมัติจะไม่ทำงาน)")

_cam_mtx = None
_cam_dist = None
PARAMS_FILE = "camera_params.npz"

def _load_params():
    global _cam_mtx, _cam_dist
    if os.path.exists(PARAMS_FILE):
        d = np.load(PARAMS_FILE)
        _cam_mtx = d["camera_matrix"]
        _cam_dist = d["dist_coeffs"]
        print("✅ โหลดไฟล์ camera_params.npz สำเร็จ")
    else:
        _cam_mtx = _cam_dist = None
        print("⚠️ ไม่พบไฟล์ camera_params.npz (ระบบแก้ภาพเบี้ยวจะไม่ทำงาน)")

_load_params()

def undistort(img):
    if _cam_mtx is None:
        return img
    h, w = img.shape[:2]
    new_mtx, roi = cv2.getOptimalNewCameraMatrix(_cam_mtx, _cam_dist, (w,h), 1, (w,h))
    out = cv2.undistort(img, _cam_mtx, _cam_dist, None, new_mtx)
    x, y, nw, nh = roi
    return out[y:y+nh, x:x+nw]

def decode_image(b64_str):
    if "," in b64_str:
        b64_str = b64_str.split(",")[1]
    img_data = base64.b64decode(b64_str)
    np_arr = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

# ═════════════════════════════════════════════════════════════════════
# 3. API สำหรับระบบล็อกอิน / สมัครสมาชิก (เชื่อมตาราง user)
# ═════════════════════════════════════════════════════════════════════
@app.route('/api/auth/signup', methods=['POST', 'OPTIONS'])
def auth_signup():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not supabase: return jsonify({"status": "error", "message": "ไม่ได้เชื่อมต่อฐานข้อมูล"}), 500
       
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role')
   
    try:
        # ตรวจสอบว่าชื่อซ้ำไหมในตาราง user
        existing = supabase.table("users").select("*").eq("username", username).execute()
        if existing.data:
            return jsonify({"status": "error", "message": "ชื่อผู้ใช้งานนี้ถูกใช้ไปแล้ว"}), 400
           
        # บันทึกข้อมูลลงตาราง user
        user_data = {"username": username, "password": password, "role": role}
        supabase.table("users").insert(user_data).execute()
       
        return jsonify({"status": "success", "message": "ลงทะเบียนสำเร็จ"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/auth/signin', methods=['POST', 'OPTIONS'])
def auth_signin():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not supabase: return jsonify({"status": "error", "message": "ไม่ได้เชื่อมต่อฐานข้อมูล"}), 500
       
    data = request.json
    username = data.get('username')
    password = data.get('password')
   
    try:
        # เช็คชื่อและรหัสจากตาราง user
        res = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
        if not res.data:
            return jsonify({"status": "error", "message": "ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง"}), 401
           
        user_info = res.data[0]
        return jsonify({
            "status": "success",
            "username": user_info["username"],
            "role": user_info["role"]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ═════════════════════════════════════════════════════════════════════
# 4. API สำหรับบันทึกและดึงข้อมูลสถิติ (เชื่อมตาราง training_sessions)
# ═════════════════════════════════════════════════════════════════════
@app.route('/api/save_session', methods=['POST', 'OPTIONS'])
def save_session():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not supabase: return jsonify({"status": "error", "message": "ไม่ได้เชื่อมต่อฐานข้อมูล"}), 500

    data = request.json
    try:
        # เตรียมข้อมูลเพื่อบันทึกลง Supabase
        insert_data = {
            "username": data.get("username"),
            "total_balls": data.get("total_balls"),
            "accuracy_percent": data.get("accuracy_percent"),
            "total_score": data.get("total_score")
            # ถ้ามีคอลัมน์ created_at แบบ Timestamp ในระบบ Supabase จะใส่เวลาให้อัตโนมัติ
        }
        supabase.table("training_sessions").insert(insert_data).execute()
        return jsonify({"status": "success", "message": "บันทึกการซ้อมลงฐานข้อมูลสำเร็จ"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/get_supabase_sessions', methods=['POST', 'OPTIONS'])
def get_supabase_sessions():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not supabase: return jsonify({"status": "error", "message": "ไม่ได้เชื่อมต่อฐานข้อมูล"}), 500

    data = request.json
    username = data.get('username')
    role = data.get('role')
    time_range = data.get('time_range', '90_days')

    try:
        # ดึงจาก training_sessions (สรุปต่อ session)
        query = supabase.table("training_sessions").select("*")

        if role != 'admin':
            query = query.eq("username", username)

        if time_range == '90_days':
            ninety_days_ago = (datetime.now() - timedelta(days=90)).isoformat()
            query = query.gte("created_at", ninety_days_ago)

        res = query.order("created_at", desc=True).execute()
        return jsonify({"status": "success", "data": res.data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/get_throws_by_session', methods=['POST', 'OPTIONS'])
def get_throws_by_session():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not supabase: return jsonify({"status": "error", "message": "ไม่ได้เชื่อมต่อฐานข้อมูล"}), 500

    data = request.json
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"status": "error", "message": "ไม่มี session_id"}), 400

    try:
        res = supabase.table("accuracy").select("*").eq("session_id", session_id).order("created_at").execute()
        return jsonify({"status": "success", "data": res.data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ═════════════════════════════════════════════════════════════════════
# 5. API สำหรับ Computer Vision (ดัดภาพ วัดระยะ)
# ═════════════════════════════════════════════════════════════════════
@app.route('/api/warp_image', methods=['POST', 'OPTIONS'])
def warp_image():
    if request.method == 'OPTIONS': return jsonify({}), 200

    data = request.json
    calib_pts = data.get('calibration_points')
    ref_w = float(data.get('ref_width_cm', 100))
    ref_h = float(data.get('ref_height_cm', 100))

    if not data.get('image') or not calib_pts or len(calib_pts) != 4:
        return jsonify({"error": "ข้อมูลไม่ครบ"}), 400

    img = decode_image(data['image'])
    img = undistort(img)
   
    rw, rh = int(ref_w * 5), int(ref_h * 5)
    src = np.array([[p['x'], p['y']] for p in calib_pts], dtype=np.float32)
    dst = np.array([[0,0], [rw-1,0], [rw-1,rh-1], [0,rh-1]], dtype=np.float32)
   
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (rw, rh))
   
    _, buf = cv2.imencode('.jpg', warped, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return jsonify({"status": "success", "image": "data:image/jpeg;base64," + base64.b64encode(buf).decode()})

@app.route('/api/measure_line', methods=['POST', 'OPTIONS'])
def measure_line():
    if request.method == 'OPTIONS': return jsonify({}), 200
   
    data = request.json
    calib_pts = data.get('calibration_points')
    p1, p2 = data.get('p1'), data.get('p2')
    ref_w = float(data.get('ref_width_cm', 100)) * 5
    ref_h = float(data.get('ref_height_cm', 100)) * 5
   
    if not calib_pts or len(calib_pts) != 4 or not p1 or not p2:
        return jsonify({"error": "ข้อมูลไม่ครบ"}), 400
       
    src = np.array([[p['x'], p['y']] for p in calib_pts], dtype=np.float32)
    dst = np.array([[0,0], [ref_w-1,0], [ref_w-1,ref_h-1], [0,ref_h-1]], dtype=np.float32)
   
    M = cv2.getPerspectiveTransform(src, dst)
    t1 = cv2.perspectiveTransform(np.array([[[p1['x'], p1['y']]]], np.float32), M)[0][0]
    t2 = cv2.perspectiveTransform(np.array([[[p2['x'], p2['y']]]], np.float32), M)[0][0]
   
    px_dist = np.linalg.norm(t1 - t2)
    dist_cm = px_dist / 5  # แปลงพิกเซลกลับเป็นเซนติเมตร
   
    return jsonify({"status": "success", "distance_cm": round(float(dist_cm), 2)})

# ═════════════════════════════════════════════════════════════════════
# 6. API จาก app11 (กล้อง + YOLO + คำนวณระยะ)
# ═════════════════════════════════════════════════════════════════════
def radius_px_to_cm(cx, cy, r_px, mat):
    if r_px <= 0:
        return 0.0
    c = np.array([[[cx,      cy]]], dtype=np.float32)
    e = np.array([[[cx+r_px, cy]]], dtype=np.float32)
    ct = cv2.perspectiveTransform(c, mat)[0][0]
    et = cv2.perspectiveTransform(e, mat)[0][0]
    return float(np.linalg.norm(et - ct)) / 10.0

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not supabase: return jsonify({"status": "error", "message": "ไม่ได้เชื่อมต่อฐานข้อมูล"}), 500
    data = request.json
    username = data.get('username')
    password = data.get('password')
    try:
        res = supabase.table('users').select('*').eq('username', username).eq('password', password).execute()
        if len(res.data) > 0:
            session_res = supabase.table('sessions').insert({"username": username}).execute()
            session_id = session_res.data[0]['id']
            return jsonify({"status": "success", "username": username, "session_id": session_id})
        else:
            return jsonify({"status": "error", "message": "Username หรือ Password ไม่ถูกต้อง!"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/logout', methods=['POST', 'OPTIONS'])
def logout():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.json
    session_id = data.get('session_id')
    if not supabase or not session_id:
        return jsonify({"status": "success"})

    # ขั้น 1: อัปเดต logout_time ใน sessions
    try:
        TH_TZ = timezone(timedelta(hours=7))
        now = datetime.now(TH_TZ).isoformat()
        supabase.table('sessions').update({"logout_time": now}).eq('id', session_id).execute()
        print(f"✅ logout_time updated for session {session_id}")
    except Exception as e:
        print(f"⚠️ update sessions failed: {e}")

    # ขั้น 2: สรุปผลสุดท้ายลง training_sessions (update ถ้ามีอยู่แล้ว, insert ถ้ายังไม่มี)
    try:
        throws = supabase.table('accuracy').select('accuracy_percent,points,username').eq('session_id', str(session_id)).execute().data
        print(f"📊 throws in session {session_id}: {len(throws)} balls")
        if throws:
            total_balls = len(throws)
            avg_acc = sum(float(t.get('accuracy_percent', 0)) for t in throws) / total_balls
            total_score = sum(int(t.get('points', 0)) for t in throws)
            username = throws[0].get('username', 'unknown')
            existing = supabase.table('training_sessions').select('id').eq('session_id', str(session_id)).execute().data
            if existing:
                supabase.table('training_sessions').update({
                    "total_balls": total_balls,
                    "accuracy_percent": round(avg_acc, 2),
                    "total_score": total_score
                }).eq('session_id', str(session_id)).execute()
                print(f"✅ training_session updated on logout: {username}, {total_balls} balls")
            else:
                supabase.table('training_sessions').insert({
                    "username": username,
                    "session_id": session_id,
                    "total_balls": total_balls,
                    "accuracy_percent": round(avg_acc, 2),
                    "total_score": total_score
                }).execute()
                print(f"✅ training_session inserted on logout: {username}, {total_balls} balls")
        else:
            print(f"⚠️ ไม่มี throws ใน session {session_id} — ไม่บันทึก training_session")
    except Exception as e:
        print(f"⚠️ save training_session failed: {e}")

    return jsonify({"status": "success"})

@app.route('/api/detect_court', methods=['POST', 'OPTIONS'])
def detect_court():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.json
    if not data.get('image'): return jsonify({"error": "ไม่พบรูป"}), 400
    img = decode_image(data['image'])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 50, 150)
    cnts, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
    court_pts = None
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            court_pts = approx
            break
    if court_pts is not None:
        pts = court_pts.reshape(4, 2)
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return jsonify({"status": "success", "points": [{"x": float(p[0]), "y": float(p[1])} for p in rect]})
    return jsonify({"status": "not_found", "message": "ไม่พบขอบสนามอัตโนมัติ"}), 404

@app.route('/api/detect_red_ball', methods=['POST', 'OPTIONS'])
def detect_red_ball():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.json
    if not data.get('image'): return jsonify({"error": "ไม่พบรูป"}), 400
    if _yolo_model is None: return jsonify({"error": "โมเดล AI ยังไม่ได้ติดตั้ง"}), 500
    
    img = decode_image(data['image'])
    # ใช้ conf=0.55 ซึ่งเหมาะสมแล้วสำหรับการนำไปใช้งานจริง (ลดขยะ False Positive)
    results = _yolo_model(img, conf=0.55, verbose=False)
    
    balls = []
    if len(results) > 0:
        for box in results[0].boxes:
            xyxy = box.xyxy[0].tolist()
            xmin, ymin, xmax, ymax = xyxy
            cx = (xmin + xmax) / 2.0
            cy = (ymin + ymax) / 2.0
            r = ((xmax - xmin) + (ymax - ymin)) / 4.0
            
            # 🚀 FIX 1: กรองขนาด Bounding Box (กรองขยะ)
            # รับเฉพาะลูกเปตองที่มีรัศมีระหว่าง 5 ถึง 80 พิกเซลเท่านั้น
            if 5 <= r <= 80:
                balls.append({"x": float(cx), "y": float(cy), "radius": float(r), "area": float((xmax-xmin)*(ymax-ymin))})
                
        if balls:
            balls.sort(key=lambda b: b['area'], reverse=True)
            return jsonify({"status": "success", "balls": balls})
            
    return jsonify({"status": "not_found"}), 404

@app.route('/api/calculate_distance', methods=['POST', 'OPTIONS'])
def calculate_distance():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.json
    calib_pts, jack, red_ball = data.get('calibration_points'), data.get('jack'), data.get('red_ball')
    current_username = data.get('username', 'guest')
    if not calib_pts or len(calib_pts) != 4 or not jack or not red_ball:
        return jsonify({"error": "ข้อมูลไม่ครบ"}), 400
    ref_w = float(data.get('ref_width_cm', 100)) * 10
    ref_h = float(data.get('ref_height_cm', 100)) * 10
    r_red  = float(data.get('red_ball_radius_px', 0))
    r_jack = float(data.get('jack_radius_px', 0))
    src = np.array([[p['x'],p['y']] for p in calib_pts], dtype=np.float32)
    dst = np.array([[0,0],[ref_w-1,0],[ref_w-1,ref_h-1],[0,ref_h-1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    jt = cv2.perspectiveTransform(np.array([[[jack['x'], jack['y']]]], np.float32), M)[0][0]
    rt = cv2.perspectiveTransform(np.array([[[red_ball['x'], red_ball['y']]]], np.float32), M)[0][0]
    center_cm = float(np.linalg.norm(rt - jt)) / 10.0
    red_r_cm  = radius_px_to_cm(red_ball['x'], red_ball['y'], r_red,  M)
    jack_r_cm = radius_px_to_cm(jack['x'],     jack['y'],     r_jack, M)
    edge_cm   = max(center_cm - red_r_cm - jack_r_cm, 0.0)
    if edge_cm <= 20: points = 5
    elif edge_cm <= 30: points = 4
    elif edge_cm <= 40: points = 3
    elif edge_cm <= 50: points = 1
    else: points = 0
    if edge_cm <= 20: accuracy_pct = 100.0
    elif edge_cm <= 50: accuracy_pct = 100.0 - ((edge_cm - 20.0) * (100.0 / 30.0))
    else: accuracy_pct = 0.0
    session_id = data.get('session_id')
    if supabase and current_username != 'guest':
        try:
            # 1) บันทึกรายลูกลง accuracy เหมือนเดิม
            row = {
                "username": current_username,
                "distance_cm": round(edge_cm, 2),
                "accuracy_percent": round(accuracy_pct, 2),
                "points": points
            }
            if session_id:
                row["session_id"] = session_id
            supabase.table("accuracy").insert(row).execute()
        except Exception as e:
            print(f"⚠️ บันทึก accuracy ไม่สำเร็จ: {e}")

        # 2) Upsert training_sessions ทันที (ไม่ต้อง logout ก่อน)
        if session_id:
            try:
                throws = supabase.table("accuracy").select("accuracy_percent,points").eq("session_id", str(session_id)).execute().data
                if throws:
                    total_balls  = len(throws)
                    avg_acc      = sum(float(t.get("accuracy_percent", 0)) for t in throws) / total_balls
                    total_score  = sum(int(t.get("points", 0)) for t in throws)

                    # ตรวจว่ามี row นี้ใน training_sessions แล้วหรือยัง
                    existing = supabase.table("training_sessions").select("id").eq("session_id", str(session_id)).execute().data
                    if existing:
                        supabase.table("training_sessions").update({
                            "total_balls":      total_balls,
                            "accuracy_percent": round(avg_acc, 2),
                            "total_score":      total_score
                        }).eq("session_id", str(session_id)).execute()
                    else:
                        supabase.table("training_sessions").insert({
                            "username":         current_username,
                            "session_id":       session_id,
                            "total_balls":      total_balls,
                            "accuracy_percent": round(avg_acc, 2),
                            "total_score":      total_score
                        }).execute()
                    print(f"✅ training_sessions updated live: {current_username}, {total_balls} balls, {round(avg_acc,2)}%")
            except Exception as e:
                print(f"⚠️ upsert training_sessions ไม่สำเร็จ: {e}")
    return jsonify({
        "status": "success",
        "distance_cm": round(edge_cm, 2),
        "center_distance_cm": round(center_cm, 2),
        "red_radius_cm": round(red_r_cm, 2),
        "jack_radius_cm": round(jack_r_cm, 2),
        "points": points,
        "accuracy_pct": round(accuracy_pct, 2)
    })

@app.route('/api/calibration_status', methods=['GET'])
def calibration_status():
    return jsonify({"active": _cam_mtx is not None, "file_exists": os.path.exists(PARAMS_FILE)})

@app.route('/api/reload_params', methods=['POST'])
def reload_params():
    _load_params()
    return jsonify({"status": "success", "undistortion_active": _cam_mtx is not None})

@app.route('/api/test_upload', methods=['POST'])
def test_upload():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'ไม่พบไฟล์รูปภาพ'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'ไม่ได้เลือกไฟล์'}), 400

    try:
        # 1. อ่านไฟล์รูปภาพที่อัปโหลดเข้ามา
        filestr = file.read()
        npimg = np.frombuffer(filestr, np.uint8)
        img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

        # 2. ให้โมเดล YOLO ตรวจจับ
        # (สมมติว่าคุณโหลดโมเดลไว้ในตัวแปร _yolo_model แล้ว)
        results = _yolo_model.predict(img, conf=0.40, verbose=False)
        
        # 3. ให้ YOLO วาดกรอบสี่เหลี่ยมลงบนรูป
        res_img = results[0].plot()

        # 4. แปลงรูปกลับเป็น Base64 เพื่อส่งกลับไปโชว์ที่หน้าเว็บ
        _, buffer = cv2.imencode('.jpg', res_img)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        img_data_url = 'data:image/jpeg;base64,' + img_b64

        return jsonify({'status': 'success', 'image': img_data_url, 'filename': file.filename})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    # ═════════════════════════════════════════════════════════════════════
# API สำหรับ Live Camera Test (ส่งคืนแค่พิกัด Bounding Box เพื่อความรวดเร็ว)
# ═════════════════════════════════════════════════════════════════════
@app.route('/api/detect_live', methods=['POST', 'OPTIONS'])
def detect_live():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.json
    if not data or not data.get('image'):
        return jsonify({"error": "ไม่พบรูปภาพ"}), 400
    if _yolo_model is None:
        return jsonify({"error": "โมเดล AI ยังไม่ได้ติดตั้ง"}), 500

    try:
        # ถอดรหัสรูปภาพ
        img = decode_image(data['image'])
        
        # ตรวจจับด้วย YOLO (ใช้ conf=0.40 สำหรับหน้า Test เพื่อให้เห็นกล่องง่ายขึ้น)
        results = _yolo_model.predict(img, conf=0.40, verbose=False)
        
        boxes_data = []
        if len(results) > 0:
            for box in results[0].boxes:
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                name = results[0].names[cls_id]
                
                boxes_data.append({
                    "xmin": xyxy[0], 
                    "ymin": xyxy[1],
                    "xmax": xyxy[2], 
                    "ymax": xyxy[3],
                    "conf": conf, 
                    "class": name
                })

        return jsonify({"status": "success", "boxes": boxes_data})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)