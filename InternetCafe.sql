CREATE DATABASE IF NOT EXISTS InternetCafe;
USE InternetCafe;

-- === Table Definitions ===
-- User
CREATE TABLE IF NOT EXISTS User (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    membership_card VARCHAR(20) UNIQUE NOT NULL,
    phone VARCHAR(15),
    balance DECIMAL(8,2) DEFAULT 0.00
);

-- Seat
CREATE TABLE IF NOT EXISTS Seat (
    seat_id INT PRIMARY KEY AUTO_INCREMENT,
    location VARCHAR(50) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT '空闲'
);

-- Recharge
CREATE TABLE IF NOT EXISTS Recharge (
    recharge_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    amount DECIMAL(8,2) NOT NULL,
    recharge_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(user_id)
);

-- Consumption
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

-- === Stored Procedures ===
-- func: 会员办理 ———— 进行会员注册，初始余额为0，进行会员卡号查重
DROP PROCEDURE IF EXISTS AddUser;
DELIMITER //
CREATE PROCEDURE AddUser(
    IN p_name VARCHAR(50),
    IN p_membership_card VARCHAR(20),
    IN p_phone VARCHAR(15)
)
BEGIN
    DECLARE v_count INT;
    -- 检查是否已有相同会员卡号
    SELECT COUNT(*) INTO v_count
    FROM User
    WHERE membership_card = p_membership_card;

    IF v_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = '该会员卡号已存在';
    ELSE
        INSERT INTO User(name, membership_card, phone, balance)
        VALUES (p_name, p_membership_card, p_phone, 0.00);
    END IF;
END;
//
DELIMITER ;

-- func: 账户充值 ———— 依据姓名为用户充值，并记录充值流水
DROP PROCEDURE IF EXISTS RechargeAccount;
DELIMITER //
CREATE PROCEDURE RechargeAccount(
    IN p_name VARCHAR(50),
    IN p_amount DECIMAL(8,2)
)
BEGIN
    -- 更新用户余额
    UPDATE User
    SET balance = balance + p_amount
    WHERE name = p_name;
    -- 插入充值记录
    INSERT INTO Recharge(user_id, amount)
    SELECT user_id, p_amount
    FROM User
    WHERE name = p_name;
END;
//
DELIMITER ;

-- func: 上机消费记录 ———— 依据姓名记录用户上机消费信息，并更新座位状态为使用中
DROP PROCEDURE IF EXISTS RecordConsumption;
DELIMITER //
CREATE PROCEDURE RecordConsumption(
    IN p_name VARCHAR(50),
    IN p_seat_id INT,
    IN p_start DATETIME
)
BEGIN
    DECLARE v_user_id INT;
    DECLARE v_seat_status VARCHAR(10);
    -- 获取用户ID
    SELECT user_id INTO v_user_id
    FROM User
    WHERE name = p_name;
    -- 获取座位状态
    SELECT status INTO v_seat_status
    FROM Seat
    WHERE seat_id = p_seat_id;

    -- 判断座位是否空闲
    IF v_seat_status <> '空闲' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = '该座位当前不可用';
    ELSE
        -- 插入消费记录
        INSERT INTO Consumption(user_id, seat_id, start_time, end_time, fee)
        VALUES (v_user_id, p_seat_id, p_start, NULL, NULL);
        -- 更新座位状态为使用中
        UPDATE Seat
        SET status = '使用中'
        WHERE seat_id = p_seat_id;
    END IF;
END;
//
DELIMITER ;

-- func: 结算消费 ———— 依据姓名结算用户消费信息，并更新座位状态为空闲
DROP PROCEDURE IF EXISTS SettleConsumption;
DELIMITER //
CREATE PROCEDURE SettleConsumption(
    IN p_name VARCHAR(50),
    IN p_seat_id INT,
    IN p_end DATETIME,
    IN p_fee DECIMAL(8,2)
)
BEGIN
    DECLARE v_user_id INT;
    -- 获取用户ID
    SELECT user_id INTO v_user_id
    FROM User
    WHERE name = p_name;
    -- 更新消费记录：结束时间和费用
    UPDATE Consumption
    SET end_time = p_end,
        fee = p_fee
    WHERE user_id = v_user_id
      AND seat_id = p_seat_id
      AND end_time IS NULL;
    -- 更新座位状态为空闲
    UPDATE Seat
    SET status = '空闲'
    WHERE seat_id = p_seat_id;
END;
//
DELIMITER ;


-- func: 查询用户信息 ———— 依据姓名查询用户基本信息、总充值和总消费
DROP PROCEDURE IF EXISTS QueryUserInfo;
DELIMITER //
CREATE PROCEDURE QueryUserInfo(
    IN p_name VARCHAR(50)
)
BEGIN
    DECLARE v_user_id INT;
    -- 获取用户ID
    SELECT user_id INTO v_user_id
    FROM User
    WHERE name = p_name;
    -- 查询用户基本信息
    SELECT name, membership_card, phone, balance
    FROM User
    WHERE user_id = v_user_id;
    -- 查询总充值
    SELECT SUM(amount) AS total_recharge
    FROM Recharge
    WHERE user_id = v_user_id;
    -- 查询总消费
    SELECT SUM(fee) AS total_fee
    FROM Consumption
    WHERE user_id = v_user_id;
END;
//
DELIMITER ;

-- func: 更新座位状态 ———— 依据座位位置更新座位状态
DROP PROCEDURE IF EXISTS UpdateSeatStatus;
DELIMITER //
CREATE PROCEDURE UpdateSeatStatus(
    IN p_location VARCHAR(50),
    IN p_status VARCHAR(10)
)
BEGIN
    UPDATE Seat
    SET status = p_status
    WHERE location = p_location;
END;
//
DELIMITER ;

-- func: 管理员查询所有信息 ———— 查询所有用户的总充值、总消费、当前余额及所有座位状态
DROP PROCEDURE IF EXISTS AdminQuerySummary;
DELIMITER //
CREATE PROCEDURE AdminQuerySummary()
BEGIN
    -- 查询所有用户的总充值、总消费、当前余额
    SELECT 
        u.name,
        COALESCE(SUM(r.amount), 0) AS total_recharge,
        COALESCE(SUM(c.fee), 0) AS total_consumption,
        u.balance
    FROM User u
    LEFT JOIN Recharge r ON u.user_id = r.user_id
    LEFT JOIN Consumption c ON u.user_id = c.user_id
    GROUP BY u.user_id, u.name, u.balance;
    -- 查询所有座位状态
    SELECT seat_id, location, status
    FROM Seat;
END;
//
DELIMITER ;

-- === Test DataBase ===
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE Consumption;
TRUNCATE TABLE Recharge;
TRUNCATE TABLE User;
TRUNCATE TABLE Seat;
SET FOREIGN_KEY_CHECKS = 1;

-- 初始化座位，将 B2 设置为维修状态
INSERT INTO Seat(location, status) VALUES
('A1', '空闲'),
('A2', '空闲'),
('B1', '空闲'),
('B2', '空闲');
CALL UpdateSeatStatus('B2', '维修');
SELECT '座位初始化完成，A1、A2、B1 为空闲状态，B2 为维修状态' AS info;

-- 会员注册 
CALL AddUser('张三', 'M001', '13800000001');
CALL AddUser('李四', 'M002', '13800000002');
CALL AddUser('王五', 'M003', '13800000003');

-- （异常测试：会员卡号重复）
-- CALL AddUser('赵六', 'M001', '13800000004');

-- 账户充值 
CALL RechargeAccount('张三', 100.00);
CALL RechargeAccount('李四', 50.00);
CALL RechargeAccount('王五', 200.00);

-- 上机消费
CALL RecordConsumption('张三', 1, '2025-12-23 10:00:00', '2025-12-23 12:00:00', 20.00);
CALL RecordConsumption('李四', 2, '2025-12-23 11:00:00', '2025-12-23 13:30:00', 35.00);
CALL RecordConsumption('王五', 3, '2025-12-23 14:00:00', '2025-12-23 16:00:00', 25.00);

-- （异常测试：维修座位不可用）
-- CALL RecordConsumption('张三', 4, '2025-12-23 09:00:00', '2025-12-23 10:00:00', 10.00);
-- （异常测试：使用中座位不可用）
CALL RecordConsumption('赵六', 2, '2025-12-23 10:30:00', '2025-12-23 11:30:00', 10.00);

-- 消费结算 
CALL SettleConsumption('张三', 1, 20.00);
CALL SettleConsumption('李四', 2, 35.00);
CALL SettleConsumption('王五', 3, 25.00);

-- 用户信息查询 
CALL QueryUserInfo('张三');
CALL QueryUserInfo('李四');
CALL QueryUserInfo('王五');

-- 管理员汇总查询 
CALL AdminQuerySummary();

SELECT '=== InternetCafe 功能测试结束 ===' AS info;