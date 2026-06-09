import sqlite3
from datetime import datetime, time
from pathlib import Path

from flask import Flask, jsonify, render_template, request

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "consultation.db"

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

AVAILABILITY_OPTIONS = [
    ("available", "有空，可接受咨询"),
    ("busy", "忙碌中，暂不便咨询"),
    ("away", "外出/请假，不在岗"),
]

CONSULTATION_STATUS = {
    "pending": "待处理",
    "accepted": "已接受",
    "completed": "已完成",
    "cancelled": "已取消",
}

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_time(value: str) -> time:
    parts = value.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def parse_work_days(value: str) -> set[int]:
    if not value:
        return set()
    return {int(x) for x in value.split(",") if x.strip().isdigit()}


def is_within_work_hours(work_days: str, work_start: str, work_end: str, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    days = parse_work_days(work_days)
    if now.weekday() not in days:
        return False
    start = parse_time(work_start)
    end = parse_time(work_end)
    current = now.time()
    return start <= current <= end


def format_work_days(work_days: str) -> str:
    days = parse_work_days(work_days)
    if not days:
        return "未设置"
    return "、".join(WEEKDAY_LABELS[d] for d in sorted(days))


def staff_status(row, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    in_hours = is_within_work_hours(row["work_days"], row["work_start"], row["work_end"], now)
    availability = row["availability"]
    avail_label = dict(AVAILABILITY_OPTIONS).get(availability, availability)

    if not in_hours:
        consultable = False
        consult_reason = "当前不在工作时间内"
    elif availability == "available":
        consultable = True
        consult_reason = "在岗且有空，欢迎咨询"
    elif availability == "busy":
        consultable = False
        consult_reason = "在工作时间内，但当前忙碌"
    else:
        consultable = False
        consult_reason = "当前不在岗"

    return {
        "in_work_hours": in_hours,
        "work_hours_label": "工作时间内" if in_hours else "非工作时间",
        "availability": availability,
        "availability_label": avail_label,
        "consultable": consultable,
        "consult_reason": consult_reason,
        "work_schedule": f"{format_work_days(row['work_days'])} {row['work_start']}-{row['work_end']}",
    }


def department_row_to_dict(row, now: datetime | None = None) -> dict:
    data = dict(row)
    data["work_days_label"] = format_work_days(row["work_days"])
    in_hours = is_within_work_hours(row["work_days"], row["work_start"], row["work_end"], now)
    data["in_work_hours"] = in_hours
    data["work_hours_label"] = "工作时间内" if in_hours else "非工作时间"
    return data


def staff_row_to_dict(row, now: datetime | None = None) -> dict:
    data = dict(row)
    data.update(staff_status(row, now))
    return data


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                location TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                work_days TEXT NOT NULL DEFAULT '0,1,2,3,4',
                work_start TEXT NOT NULL DEFAULT '08:30',
                work_end TEXT NOT NULL DEFAULT '17:30',
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                office TEXT DEFAULT '',
                specialties TEXT DEFAULT '',
                availability TEXT NOT NULL DEFAULT 'available'
                    CHECK(availability IN ('available', 'busy', 'away')),
                availability_note TEXT DEFAULT '',
                work_days TEXT DEFAULT '',
                work_start TEXT DEFAULT '',
                work_end TEXT DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            );

            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                student_id TEXT NOT NULL,
                contact TEXT DEFAULT '',
                topic TEXT NOT NULL,
                message TEXT DEFAULT '',
                preferred_time TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'accepted', 'completed', 'cancelled')),
                created_at TEXT NOT NULL,
                FOREIGN KEY (staff_id) REFERENCES staff(id)
            );
            """
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
        if count == 0:
            seed_data(conn)


def seed_data(conn):
    departments = [
        ("学生工作处", "负责学生日常管理、奖助学金、违纪处理等", "行政楼201", "0571-88880001", "0,1,2,3,4", "08:30", "17:30", 1),
        ("教务处", "课程安排、学籍管理、考试与成绩相关事务", "行政楼105", "0571-88880002", "0,1,2,3,4", "08:30", "17:30", 2),
        ("后勤服务中心", "宿舍、食堂、报修等生活服务", "后勤楼101", "0571-88880003", "0,1,2,3,4,5,6", "07:30", "21:00", 3),
        ("就业指导中心", "实习就业、职业规划、招聘会信息", "就业楼302", "0571-88880004", "0,1,2,3,4", "09:00", "17:00", 4),
        ("心理咨询中心", "心理健康咨询与危机干预", "学生活动中心3楼", "0571-88880005", "0,1,2,3,4", "09:00", "17:00", 5),
        ("计算机学院", "本院学生事务与教学管理", "计算机楼408", "0571-88880101", "0,1,2,3,4", "08:30", "17:30", 10),
        ("经济管理学院", "本院学生事务与教学管理", "经管楼215", "0571-88880102", "0,1,2,3,4", "08:30", "17:30", 11),
    ]
    conn.executemany(
        """
        INSERT INTO departments
        (name, description, location, phone, work_days, work_start, work_end, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        departments,
    )

    staff = [
        (1, "张明", "学生科科长", "13800001001", "zhangming@school.edu.cn", "行政楼201", "奖助学金、违纪申诉", "available", "", "", "", "", 1),
        (1, "李芳", "资助专干", "13800001002", "lifang@school.edu.cn", "行政楼203", "困难认定、勤工助学", "available", "", "", "", "", 2),
        (2, "王强", "教务员", "13800002001", "wangqiang@school.edu.cn", "行政楼105", "选课、成绩、学籍", "busy", "正在处理期末考务", "", "", "", 1),
        (3, "赵敏", "宿舍管理老师", "13800003001", "zhaomin@school.edu.cn", "后勤楼101", "宿舍调换、报修", "available", "", "0,1,2,3,4,5,6", "07:30", "21:00", 1),
        (4, "陈浩", "就业指导老师", "13800004001", "chenhao@school.edu.cn", "就业楼302", "简历指导、签约咨询", "available", "", "", "", "", 1),
        (5, "刘静", "心理咨询师", "13800005001", "liujing@school.edu.cn", "活动中心301", "情绪困扰、人际关系", "available", "", "0,1,2,3,4", "09:00", "17:00", 1),
        (5, "周磊", "心理咨询师", "13800005002", "zhoulei@school.edu.cn", "活动中心302", "学业压力、适应问题", "away", "外出参加培训，6月10日返岗", "0,1,2,3,4", "09:00", "17:00", 2),
        (6, "孙辅导员", "2022级辅导员", "13800006101", "sun@cs.school.edu.cn", "计算机楼408", "班级管理、请假审批", "available", "", "0,1,2,3,4", "08:30", "17:30", 1),
        (6, "吴辅导员", "2023级辅导员", "13800006102", "wu@cs.school.edu.cn", "计算机楼410", "心理关怀、活动组织", "busy", "正在开年级大会", "0,1,2,3,4", "08:30", "17:30", 2),
        (7, "郑辅导员", "2022级辅导员", "13800007101", "zheng@em.school.edu.cn", "经管楼215", "学业指导、实习安排", "available", "", "0,1,2,3,4", "08:30", "17:30", 1),
    ]
    conn.executemany(
        """
        INSERT INTO staff
        (department_id, name, title, phone, email, office, specialties,
         availability, availability_note, work_days, work_start, work_end, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        staff,
    )
    conn.commit()


def get_staff_with_dept(conn, staff_id: int | None = None):
    query = """
        SELECT s.*,
               d.name AS department_name,
               d.location AS department_location,
               COALESCE(NULLIF(s.work_days, ''), d.work_days) AS work_days,
               COALESCE(NULLIF(s.work_start, ''), d.work_start) AS work_start,
               COALESCE(NULLIF(s.work_end, ''), d.work_end) AS work_end
        FROM staff s
        JOIN departments d ON d.id = s.department_id
    """
    params = []
    if staff_id:
        query += " WHERE s.id = ?"
        params.append(staff_id)
    query += " ORDER BY d.sort_order, d.name, s.sort_order, s.name"
    return conn.execute(query, params).fetchall()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin():
    return render_template(
        "admin.html",
        availability_options=AVAILABILITY_OPTIONS,
        status_labels=CONSULTATION_STATUS,
    )


@app.route("/api/meta", methods=["GET"])
def meta():
    now = datetime.now()
    return jsonify(
        {
            "server_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "weekday": WEEKDAY_LABELS[now.weekday()],
            "availability_options": [
                {"value": v, "label": l} for v, l in AVAILABILITY_OPTIONS
            ],
        }
    )


@app.route("/api/departments", methods=["GET"])
def list_departments():
    now = datetime.now()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM departments ORDER BY sort_order, name"
        ).fetchall()
        result = []
        for row in rows:
            dept = department_row_to_dict(row, now)
            staff_rows = get_staff_with_dept(conn)
            dept_staff = [
                staff_row_to_dict(s, now)
                for s in staff_rows
                if s["department_id"] == row["id"]
            ]
            available_count = sum(1 for s in dept_staff if s["consultable"])
            dept["staff_count"] = len(dept_staff)
            dept["available_count"] = available_count
            result.append(dept)
    return jsonify(result)


@app.route("/api/staff", methods=["GET"])
def list_staff():
    now = datetime.now()
    department_id = request.args.get("department_id", "").strip()
    consultable_only = request.args.get("consultable", "").strip() == "1"
    q = request.args.get("q", "").strip().lower()

    with get_db() as conn:
        rows = get_staff_with_dept(conn)

    staff_list = [staff_row_to_dict(row, now) for row in rows]

    if department_id.isdigit():
        staff_list = [s for s in staff_list if s["department_id"] == int(department_id)]

    if q:
        staff_list = [
            s
            for s in staff_list
            if q in s["name"].lower()
            or q in s["title"].lower()
            or q in s["department_name"].lower()
            or q in (s.get("specialties") or "").lower()
        ]

    if consultable_only:
        staff_list = [s for s in staff_list if s["consultable"]]

    return jsonify(staff_list)


@app.route("/api/staff/<int:staff_id>", methods=["GET"])
def get_staff(staff_id):
    now = datetime.now()
    with get_db() as conn:
        rows = get_staff_with_dept(conn, staff_id)
    if not rows:
        return jsonify({"error": "未找到该人员"}), 404
    return jsonify(staff_row_to_dict(rows[0], now))


@app.route("/api/staff/<int:staff_id>/availability", methods=["PATCH"])
def update_availability(staff_id):
    data = request.get_json(silent=True) or {}
    availability = str(data.get("availability", "")).strip()
    if availability not in {v for v, _ in AVAILABILITY_OPTIONS}:
        return jsonify({"error": "空闲状态无效"}), 400

    note = str(data.get("availability_note", "")).strip()

    with get_db() as conn:
        exists = conn.execute("SELECT id FROM staff WHERE id = ?", (staff_id,)).fetchone()
        if not exists:
            return jsonify({"error": "未找到该人员"}), 404
        conn.execute(
            """
            UPDATE staff SET availability = ?, availability_note = ?
            WHERE id = ?
            """,
            (availability, note, staff_id),
        )
        conn.commit()
        rows = get_staff_with_dept(conn, staff_id)

    return jsonify(
        {
            "message": "状态已更新",
            "staff": staff_row_to_dict(rows[0]),
        }
    )


@app.route("/api/consultations", methods=["POST"])
def create_consultation():
    data = request.get_json(silent=True) or {}
    required = {
        "staff_id": "咨询对象",
        "student_name": "姓名",
        "student_id": "学号",
        "topic": "咨询主题",
    }
    missing = [label for key, label in required.items() if not str(data.get(key, "")).strip()]
    if missing:
        return jsonify({"error": f"请填写：{', '.join(missing)}"}), 400

    staff_id = int(data["staff_id"])
    now = datetime.now()

    with get_db() as conn:
        rows = get_staff_with_dept(conn, staff_id)
        if not rows:
            return jsonify({"error": "咨询对象不存在"}), 404

        status_info = staff_status(rows[0], now)
        if not status_info["consultable"]:
            return jsonify(
                {
                    "error": f"当前无法提交咨询：{status_info['consult_reason']}",
                    "staff_status": status_info,
                }
            ), 400

        created_at = now.isoformat(timespec="seconds")
        cursor = conn.execute(
            """
            INSERT INTO consultations
            (staff_id, student_name, student_id, contact, topic, message, preferred_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                staff_id,
                data["student_name"].strip(),
                data["student_id"].strip(),
                str(data.get("contact", "")).strip(),
                data["topic"].strip(),
                str(data.get("message", "")).strip(),
                str(data.get("preferred_time", "")).strip(),
                created_at,
            ),
        )
        conn.commit()
        consultation_id = cursor.lastrowid

    return jsonify(
        {
            "id": consultation_id,
            "message": f"已向 {rows[0]['name']} 提交咨询申请，请等待回复",
        }
    )


@app.route("/api/consultations", methods=["GET"])
def list_consultations():
    status_filter = request.args.get("status", "").strip()
    staff_id = request.args.get("staff_id", "").strip()

    query = """
        SELECT c.*, s.name AS staff_name, s.title AS staff_title,
               d.name AS department_name
        FROM consultations c
        JOIN staff s ON s.id = c.staff_id
        JOIN departments d ON d.id = s.department_id
        WHERE 1=1
    """
    params = []

    if status_filter in CONSULTATION_STATUS:
        query += " AND c.status = ?"
        params.append(status_filter)
    if staff_id.isdigit():
        query += " AND c.staff_id = ?"
        params.append(int(staff_id))

    query += " ORDER BY c.created_at DESC, c.id DESC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["status_label"] = CONSULTATION_STATUS.get(row["status"], row["status"])
        result.append(item)
    return jsonify(result)


@app.route("/api/consultations/<int:consultation_id>/status", methods=["PATCH"])
def update_consultation_status(consultation_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).strip()
    if status not in CONSULTATION_STATUS:
        return jsonify({"error": "状态无效"}), 400

    with get_db() as conn:
        exists = conn.execute(
            "SELECT id FROM consultations WHERE id = ?", (consultation_id,)
        ).fetchone()
        if not exists:
            return jsonify({"error": "咨询记录不存在"}), 404
        conn.execute(
            "UPDATE consultations SET status = ? WHERE id = ?",
            (status, consultation_id),
        )
        conn.commit()

    return jsonify({"message": "咨询状态已更新"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
