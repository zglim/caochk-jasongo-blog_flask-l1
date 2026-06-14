'''
controller.user控制器
该控制器专门用于处理用户管理相关操作
包括注册功能、注册要用到的邮箱验证码功能、登录功能、登录所需的图形验证码功能、登出功能
'''
import re
from datetime import datetime, timedelta

from flask import Blueprint, make_response, session, request, url_for, jsonify

from common.utility import ImageCode
from common.utility import send_email, gen_email_code

import hashlib
from model.users import Users
from model.credit import Credit

user = Blueprint('user', __name__)

# 常量配置
ECODE_EXPIRE_MINUTES = 5        # 邮箱验证码过期时间（分钟）
VCODE_EXPIRE_MINUTES = 5        # 图形验证码过期时间（分钟）
ECODE_MAX_RETRIES = 5           # 邮箱验证码最大尝试次数
VCODE_MAX_RETRIES = 5           # 图形验证码最大尝试次数

# ====图片验证码视图函数====
@user.route('/vcode')
def vcode():
    imgCode = ImageCode()
    code, bstring = imgCode.get_code()
    response = make_response(bstring)  # 将响应的内容设置为验证码的字节码内容
    response.headers['Content-Type'] = 'image/jpeg'  # 查阅李辉老师书籍后发现更推荐使用response.mimetype = 'image/jpeg'的方式来修改返回数据格式【在之后的版本中进行改进】
    session['vcode'] = code.lower()  # 将验证码字符串转换为小写字母保存到session变量中
    # 设置图形验证码过期时间和尝试次数限制
    session['vcode_expire'] = (datetime.now() + timedelta(minutes=VCODE_EXPIRE_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
    session['vcode_retries'] = 0  # 初始化尝试次数为0
    return response


# ====邮箱验证码视图函数====
@user.route('/ecode', methods=['POST'])
def ecode():
    email = request.form.get('email')
    print(email)

    # 后端校验邮箱地址合法性
    if not re.match('.+@.+\..+', email):
        return 'email-invalid'

    #校验通过，然后发送
    code = gen_email_code()
    try:
        send_email(email, code)
        print('已发送')
        session['ecode'] = code.lower()  # 记录到session中，之后用户输入的邮箱验证码需要和这里存的对比来看看用户输的对不对
        # 设置邮箱验证码过期时间和尝试次数限制
        session['ecode_expire'] = (datetime.now() + timedelta(minutes=ECODE_EXPIRE_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
        session['ecode_retries'] = 0  # 初始化尝试次数为0
        print(session.get('ecode'))
        return 'send-pass'
    except:
        return 'send-fail'


# ====用户注册视图函数====
@user.route('/user', methods=['POST'])
def register():
    username = request.form.get('username').strip()  # 从前端表单获取用户输入的用户名
    password = request.form.get('password').strip()  # 从前端获取用户输入的密码
    ecode = request.form.get('ecode').lower().strip()  # 从前端获取用户输入的邮箱验证码（对用户输入的大小写不敏感，统一转换为小写处理）
    user = Users()

    # 检查邮箱验证码是否存在
    if session.get('ecode') is None:
        return 'ecode-expired'

    # 检查邮箱验证码是否过期
    expire_time = session.get('ecode_expire')
    if expire_time and datetime.now() > datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S'):
        session.pop('ecode', None)
        session.pop('ecode_expire', None)
        session.pop('ecode_retries', None)
        return 'ecode-expired'

    # 检查验证码尝试次数是否超过限制
    retries = session.get('ecode_retries', 0)
    if retries >= ECODE_MAX_RETRIES:
        session.pop('ecode', None)
        session.pop('ecode_expire', None)
        session.pop('ecode_retries', None)
        return 'ecode-expired'

    # 验证用户输入的邮箱验证码是否正确（用户前端输入的与保存在session中的进行对比）
    print(session.get('ecode'))
    if ecode != session.get('ecode'):
        # 验证码错误，增加尝试次数
        session['ecode_retries'] = retries + 1
        return 'ecode-error'

    # 验证码正确，清除验证码相关session
    session.pop('ecode', None)
    session.pop('ecode_expire', None)
    session.pop('ecode_retries', None)

    # 真正开始注册时还需后端校验用户输入邮箱地址的合法性 及 密码长度不可<5
    if not re.match('.+@.+\..+', username) or len(password) < 5:
        return 'up-invalid'
    elif len(user.find_by_username(username)) > 0:
        return 'user-repeated'
    else:
        # 对密码进行MD5加密后保存
        password = hashlib.md5(password.encode()).hexdigest()
        # 开始注册，返回的结果还有用
        result = user.do_register(username, password)
        # 尝试注册后，利用返回结果的后续准备工作
        try:
            # 在session中保存当前注册用户的一系列信息，只要session在有效期内，这些信息可跨路由调用
            session['islogin'] = 'true'
            session['userid'] = result.userid  # [?]
            session['username'] = username
            session['nickname'] = result.nickname
            session['role'] = result.role
            # 默认注册就送新用户50积分
            Credit().insert_detail('用户注册', '0', 50)
            return 'reg-pass'
        except:
            return 'reg-fail'


# ====用户登录视图函数====
@user.route('/login', methods=['POST'])
def login():
    user = Users()
    username = request.form.get('username').strip()
    password = request.form.get('password').strip()
    vcode = request.form.get('vcode').lower().strip()

    # 检查图形验证码是否存在
    if session.get('vcode') is None:
        return 'vcode-expired'

    # 检查图形验证码是否过期
    expire_time = session.get('vcode_expire')
    if expire_time and datetime.now() > datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S'):
        session.pop('vcode', None)
        session.pop('vcode_expire', None)
        session.pop('vcode_retries', None)
        return 'vcode-expired'

    # 检查验证码尝试次数是否超过限制
    retries = session.get('vcode_retries', 0)
    if retries >= VCODE_MAX_RETRIES:
        session.pop('vcode', None)
        session.pop('vcode_expire', None)
        session.pop('vcode_retries', None)
        return 'vcode-expired'

    # 校验图形验证码是否正确
    if vcode != session.get('vcode'):
        # 验证码错误，增加尝试次数
        session['vcode_retries'] = retries + 1
        return 'vcode-error'

    # 验证码正确，清除验证码相关session
    session.pop('vcode', None)
    session.pop('vcode_expire', None)
    session.pop('vcode_retries', None)

    # 实现登录功能
    password = hashlib.md5(password.encode()).hexdigest()
    result = user.find_by_username(username)  # 查询的结果各有用途
    # 拿着用户输入的用户查询数据库查询到了结果且确实只为一条结果，再是密码验证通过，那么就可以登录了
    if len(result) == 1 and result[0].password == password:
        # 在session中保存当前登录用户的一系列信息，只要session在有效期内，这些信息可跨路由调用
        session['islogin'] = 'true'
        session['userid'] = result[0].userid
        session['username'] = username
        session['nickname'] = result[0].nickname
        session['role'] = result[0].role

        # 积分更新模块，每次登录可获得1积分
        Credit().insert_detail(type='正常登录', target='0', credit=1)
        user.update_credit(1)

        # 以下为实现自动登录功能的组成部分：用户登录后，服务器返回响应要求客户端持久化保存cookie信息，并在cookie信息中携带用户会话管理信息
        # 要求客户端设置cookie来实现自动登录功能
        response = make_response('login-pass')  # 实例化一个response对象，并传入响应主体作为参数
        # 调用Response的set_cookie()方法，并设置key、value、max_age参数
        response.set_cookie('username', username, max_age=30*24*3600)
        response.set_cookie('password', password, max_age=30*24*3600)
        # 在最大保存周期内，客户端再次访问相同站点时会自动携带该cookie信息，服务器一提取就直接免输入自动登录了

        return response
    else:
        return 'login-fail'


# ====用户退出登录视图函数====
@user.route('/logout')
# 退出登录主要就是两件事：1.清空session，2.让客户端清空cookie并重定向至根页面
def logout():
    # 1.清空Session，页面跳转
    session.clear()

    # 2.让客户端清空cookie并重定向至根页面
    response = make_response('注销并进行重定向', 302)
    response.headers['Location'] = url_for('home')
    response.delete_cookie('username')  # delete与下面的将有效期设为0，这两种方法都可用于清理cookie
    response.set_cookie('password', '', max_age=0)

    return response



@user.route('/loginfo')
def loginfo():
    # 没有登录，则直接响应一个空JSON给前端，用于前端判断
    if session.get('islogin') is None:
        return jsonify(None)
    else:
        dict = {}
        dict['islogin'] = session.get('islogin')
        dict['userid'] = session.get('userid')
        dict['username'] = session.get('username')
        dict['nickname'] = session.get('nickname')
        dict['role'] = session.get('role')
        return jsonify(dict)


from common.redisdb import redis_connect


@user.route('/redis/code', methods=['POST'])
# 用户注册的邮箱验证码保存到缓存中而非session中
def redis_code():
    username = request.form.get('username').strip()  # 修正括号位置：strip()作用于用户输入值而非字符串字面量
    code = gen_email_code()
    red = redis_connect()  # redis连接实例
    red.set(username, code)  # 在redis中创建一个字符串
    red.expire(username, 300)  # 设置username变量的有效期为300s（5分钟）
    # 设置好缓存变量的过期时间后，发送邮件完成处理
    try:
        send_email(username, code)
        print('已发送')
        # 初始化验证尝试次数
        red.set(username + '_retries', '0')
        red.expire(username + '_retries', 300)
        return 'done'
    except:
        return 'send-fail'


@user.route('/redis/reg', methods=['POST'])
# 根据用户注册的邮箱到缓存中查找验证码进行验证
def redis_reg():
    username = request.form.get('username').strip()
    password = request.form.get('password').strip()
    ecode = request.form.get('ecode').lower().strip()  # 无所谓用户输入的验证码的大小写
    try:
        red = redis_connect()  # 连接到Redis服务器
        code = red.get(username)
        # 检查验证码是否存在（已过期或从未设置）
        if code is None:
            return '验证码已经失效.'

        code = code.lower() if isinstance(code, str) else code.decode('utf-8').lower()

        # 检查验证尝试次数是否超过限制
        retries_key = username + '_retries'
        retries = int(red.get(retries_key) or 0)
        if retries >= ECODE_MAX_RETRIES:
            red.delete(username)
            red.delete(retries_key)
            return '验证码尝试次数过多，请重新获取.'

        if code == ecode:
            # 验证码正确，清除验证码相关缓存
            red.delete(username)
            red.delete(retries_key)

            # 开始进行注册流程
            user_obj = Users()
            # 后端校验邮箱地址合法性和密码长度
            if not re.match('.+@.+\..+', username) or len(password) < 5:
                return 'up-invalid'
            elif len(user_obj.find_by_username(username)) > 0:
                return 'user-repeated'
            else:
                # 对密码进行MD5加密后保存
                encrypted_password = hashlib.md5(password.encode()).hexdigest()
                # 开始注册
                result = user_obj.do_register(username, encrypted_password)
                try:
                    # 在session中保存当前注册用户的一系列信息
                    session['islogin'] = 'true'
                    session['userid'] = result.userid
                    session['username'] = username
                    session['nickname'] = result.nickname
                    session['role'] = result.role
                    # 默认注册就送新用户50积分
                    Credit().insert_detail('用户注册', '0', 50)
                    return 'reg-pass'
                except:
                    return 'reg-fail'
        else:
            # 验证码错误，增加尝试次数
            red.incr(retries_key)
            return '验证码错误.'
    except Exception as e:
        print(f'注册异常: {e}')
        return '验证码已经失效.'