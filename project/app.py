from flask import Flask, render_template, request, jsonify
import pymysql
import os

app = Flask(__name__)
app.secret_key = 'internet_cafe_2025'  # 用于会话和消息提示

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'kkcjy6033',
    'database': 'InternetCafe',
    'charset': 'utf8mb4'
}

# 读取SQL文件并初始化数据库
def init_db_from_sql_file():
    # 读取SQL脚本
    sql_file_path = 'InternetCafe.sql'
    if not os.path.exists(sql_file_path):
        print(f"错误：未找到SQL文件 {sql_file_path}")
        return
    
    with open(sql_file_path, 'r', encoding='utf8') as f:
        sql_scripts = f.read()
    
    # 连接数据库（先不指定库，因为需要创建）
    conn = pymysql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        charset=DB_CONFIG['charset']
    )
    cursor = conn.cursor()
    
    try:
        # 拆分SQL执行（解决DELIMITER问题，简化处理）
        # 先执行创建数据库和表的基础语句
        cursor.execute("CREATE DATABASE IF NOT EXISTS InternetCafe;")
        cursor.execute("USE InternetCafe;")

        # cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        # cursor.execute("TRUNCATE TABLE Consumption;")
        # cursor.execute("TRUNCATE TABLE Recharge;")
        # cursor.execute("TRUNCATE TABLE User;")
        # cursor.execute("TRUNCATE TABLE Seat;")
        # cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        
        # 手动执行表创建（避免DELIMITER解析问题）
        # 清空原有存储过程（防止冲突）
        cursor.execute("DROP PROCEDURE IF EXISTS AddUser;")
        cursor.execute("DROP PROCEDURE IF EXISTS RechargeAccount;")
        cursor.execute("DROP PROCEDURE IF EXISTS RecordConsumption;")
        cursor.execute("DROP PROCEDURE IF EXISTS SettleConsumption;")
        cursor.execute("DROP PROCEDURE IF EXISTS QueryUserInfo;")
        cursor.execute("DROP PROCEDURE IF EXISTS UpdateSeatStatus;")
        cursor.execute("DROP PROCEDURE IF EXISTS AdminQuerySummary;")

        # 重新创建表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS User (
            user_id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(50) NOT NULL,
            membership_card VARCHAR(20) UNIQUE NOT NULL,
            phone VARCHAR(15),
            balance DECIMAL(8,2) DEFAULT 0.00
        );
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Seat (
            seat_id INT PRIMARY KEY AUTO_INCREMENT,
            location VARCHAR(50) NOT NULL,
            status VARCHAR(10) NOT NULL DEFAULT '空闲'
        );
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Recharge (
            recharge_id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            amount DECIMAL(8,2) NOT NULL,
            recharge_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES User(user_id)
        );
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Consumption (
            consumption_id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            seat_id INT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NULL,
            fee DECIMAL(8,2) NULL,
            FOREIGN KEY (user_id) REFERENCES User(user_id),
            FOREIGN KEY (seat_id) REFERENCES Seat(seat_id)
        );
        """)
        
        # 创建存储过程（适配pymysql的执行方式）
        # 1. AddUser
        cursor.execute("""
        CREATE PROCEDURE AddUser(
            IN p_name VARCHAR(50),
            IN p_membership_card VARCHAR(20),
            IN p_phone VARCHAR(15)
        )
        BEGIN
            DECLARE v_count INT;
            SELECT COUNT(*) INTO v_count FROM User WHERE membership_card = p_membership_card;
            IF v_count > 0 THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '该会员卡号已存在';
            ELSE
                INSERT INTO User(name, membership_card, phone, balance) VALUES (p_name, p_membership_card, p_phone, 0.00);
            END IF;
        END
        """)
        
        # 2. RechargeAccount
        cursor.execute("""
        CREATE PROCEDURE RechargeAccount(
            IN p_name VARCHAR(50),
            IN p_amount DECIMAL(8,2)
        )
        BEGIN
            UPDATE User SET balance = balance + p_amount WHERE name = p_name;
            INSERT INTO Recharge(user_id, amount) SELECT user_id, p_amount FROM User WHERE name = p_name;
        END
        """)
        
        # 3. RecordConsumption
        cursor.execute("""
        CREATE PROCEDURE RecordConsumption(
            IN p_name VARCHAR(50),
            IN p_seat_id INT,
            IN p_start DATETIME
        )
        BEGIN
            DECLARE v_user_id INT;
            DECLARE v_seat_status VARCHAR(10);
            -- 获取用户ID
            SELECT user_id INTO v_user_id FROM User WHERE name = p_name;
            -- 获取座位状态
            SELECT status INTO v_seat_status FROM Seat WHERE seat_id = p_seat_id;
            -- 判断座位是否空闲
            IF v_seat_status <> '空闲' THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '该座位当前不可用';
            ELSE
                -- 插入消费记录
                INSERT INTO Consumption(user_id, seat_id, start_time, end_time, fee)
                VALUES (v_user_id, p_seat_id, p_start, NULL, NULL);
                -- 更新座位状态为使用中
                UPDATE Seat SET status = '使用中' WHERE seat_id = p_seat_id;
            END IF;
        END;
        """)
        
        # 4. SettleConsumption
        cursor.execute("""
        CREATE PROCEDURE SettleConsumption(
            IN p_name VARCHAR(50),
            IN p_seat_id INT,
            IN p_end DATETIME,
            IN p_fee DECIMAL(8,2)
        )
        BEGIN
            DECLARE v_user_id INT;
            -- 获取用户ID
            SELECT user_id INTO v_user_id FROM User WHERE name = p_name;
            -- 更新消费记录的 end_time 和 fee
            UPDATE Consumption
            SET end_time = p_end, fee = p_fee
            WHERE user_id = v_user_id AND seat_id = p_seat_id AND end_time IS NULL;
            -- 扣除用户余额
            UPDATE User SET balance = balance - p_fee WHERE user_id = v_user_id;
            -- 更新座位状态为空闲
            UPDATE Seat SET status = '空闲' WHERE seat_id = p_seat_id;
        END;
        """)
        
        # 5. QueryUserInfo
        cursor.execute("""
        CREATE PROCEDURE QueryUserInfo(
            IN p_name VARCHAR(50)
        )
        BEGIN
            DECLARE v_user_id INT;
            SELECT user_id INTO v_user_id FROM User WHERE name = p_name;
            SELECT name, membership_card, phone, balance FROM User WHERE user_id = v_user_id;
            SELECT COALESCE(SUM(amount),0) AS total_recharge FROM Recharge WHERE user_id = v_user_id;
            SELECT COALESCE(SUM(fee),0) AS total_fee FROM Consumption WHERE user_id = v_user_id;
        END
        """)
        
        # 6. UpdateSeatStatus
        cursor.execute("""
        CREATE PROCEDURE UpdateSeatStatus(
            IN p_location VARCHAR(50),
            IN p_status VARCHAR(10)
        )
        BEGIN
            UPDATE Seat SET status = p_status WHERE location = p_location;
        END
        """)
        
        # 7. AdminQuerySummary
        cursor.execute("""
        CREATE PROCEDURE AdminQuerySummary()
        BEGIN
            SELECT u.name, COALESCE(SUM(r.amount),0) AS total_recharge, COALESCE(SUM(c.fee),0) AS total_consumption, u.balance 
            FROM User u LEFT JOIN Recharge r ON u.user_id = r.user_id LEFT JOIN Consumption c ON u.user_id = c.user_id 
            GROUP BY u.user_id, u.name, u.balance;
            SELECT seat_id, location, status FROM Seat;
        END
        """)
        
        # cursor.execute("DELETE FROM Consumption;")
        # cursor.execute("DELETE FROM Recharge;")
        # cursor.execute("DELETE FROM User;")
        # cursor.execute("DELETE FROM Seat;") 
        # cursor.execute("""
        # INSERT INTO Seat (location, status) VALUES
        # ('A1','空闲'),('A2','空闲'),('A3','空闲'),('A4','空闲'),('A5','空闲'),
        # ('B1','空闲'),('B2','空闲'),('B3','空闲'),('B4','空闲'),('B5','空闲'),
        # ('C1','空闲'),('C2','空闲'),('C3','空闲'),('C4','空闲'),('C5','空闲')
        # """)

        conn.commit()
        print("数据库初始化成功！")
    except Exception as e:
        print(f"数据库初始化失败：{e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# 数据库连接函数
def get_db_connection():
    conn = pymysql.connect(**DB_CONFIG)
    return conn

# 首页（选择模式）
@app.route('/')
def index():
    return render_template('index.html')

# 用户界面
@app.route('/user')
def user():
    return render_template('user.html')

# 管理员界面
@app.route('/admin')
def admin():
    return render_template('admin.html')

# ---------------------- 用户功能接口 ----------------------
# 1. 会员办理
@app.route('/api/add_user', methods=['POST'])
def add_user():
    try:
        data = request.form
        name = data.get('name')
        membership_card = data.get('membership_card')
        phone = data.get('phone', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.callproc('AddUser', [name, membership_card, phone])
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': '会员办理成功！'})
    except pymysql.MySQLError as e:
        return jsonify({'status': 'error', 'message': f'操作失败：{e.args[1]}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'系统错误：{str(e)}'})

# 2. 账户充值
@app.route('/api/recharge', methods=['POST'])
def recharge():
    try:
        data = request.form
        name = data.get('name')
        amount = float(data.get('amount'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.callproc('RechargeAccount', [name, amount])
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': '充值成功！'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'充值失败：{str(e)}'})

# 3. 上机消费记录
@app.route('/api/record_consumption', methods=['POST'])
def record_consumption():
    try:
        data = request.form
        name = data.get('name')
        location = data.get('location')
        start_time = data.get('start_time')
        conn = get_db_connection()
        cursor = conn.cursor()
        # 获取 seat_id
        cursor.execute("SELECT seat_id, status FROM Seat WHERE location = %s", (location,))
        seat = cursor.fetchone()
        if not seat:
            return jsonify({'status': 'error', 'message': '座位不存在！'})
        seat_id, seat_status = seat
        if seat_status != '空闲':
            return jsonify({'status': 'error', 'message': f'该座位当前不可用（{seat_status}）！'})

        # 调用存储过程
        cursor.callproc('RecordConsumption', [name, seat_id, start_time])
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': '上机记录添加成功！'})
    except pymysql.MySQLError as e:
        return jsonify({'status': 'error', 'message': f'操作失败：{e.args[1]}'} )
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'系统错误：{str(e)}'})

# 4. 结算消费
@app.route('/api/settle_consumption', methods=['POST'])
def settle_consumption():
    try:
        data = request.form
        name = data.get('name')
        location = data.get('location')
        end_time = data.get('end_time')
        fee = float(data.get('fee'))
        conn = get_db_connection()
        cursor = conn.cursor()
        # 获取 seat_id
        cursor.execute("SELECT seat_id, status FROM Seat WHERE location = %s", (location,))
        seat = cursor.fetchone()
        if not seat:
            return jsonify({'status': 'error', 'message': '座位不存在！'})
        seat_id, seat_status = seat
        # 调用存储过程
        cursor.callproc('SettleConsumption', [name, seat_id, end_time, fee])
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': '消费结算成功！'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'结算失败：{str(e)}'})


# ---------------------- 管理员功能接口 ----------------------
# 1. 查询用户信息
@app.route('/api/query_user', methods=['POST'])
def query_user():
    try:
        data = request.form
        name = data.get('name')
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.callproc('QueryUserInfo', [name])
        
        # 获取存储过程返回的结果集
        user_info = cursor.fetchone()
        cursor.nextset()
        total_recharge = cursor.fetchone()
        cursor.nextset()
        total_fee = cursor.fetchone()
        
        result = {
            'user_info': user_info,
            'total_recharge': total_recharge['total_recharge'],
            'total_fee': total_fee['total_fee']
        }
        
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'data': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'查询失败：{str(e)}'})

# 2. 管理员总览
@app.route('/api/admin_summary', methods=['GET'])
def admin_summary():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.callproc('AdminQuerySummary')
        
        # 获取用户汇总
        user_summary = cursor.fetchall()
        cursor.nextset()
        # 获取座位状态
        seat_status = cursor.fetchall()
        
        result = {
            'user_summary': user_summary,
            'seat_status': seat_status
        }
        
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'data': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'查询失败：{str(e)}'})

# 3. 更新座位状态
@app.route('/api/update_seat', methods=['POST'])
def update_seat():
    try:
        data = request.form
        location = data.get('location')
        status = data.get('status')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.callproc('UpdateSeatStatus', [location, status])
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'message': '座位状态更新成功！'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'更新失败：{str(e)}'})

if __name__ == '__main__':
    init_db_from_sql_file()  # 从SQL文件初始化数据库
    app.run(debug=True, host='0.0.0.0', port=5000)