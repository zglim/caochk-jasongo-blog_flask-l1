"""
controller.index控制器代码
该控制器主要用于实现
首页文章列表展示功能、第二页等页面文章列表展示功能、按类型区分的文章列表展示功能、
显示用户搜索结果的文章列表展示功能、使用Redis缓存文章后展示文章列表功能
"""
import ast
from math import ceil

from flask import Blueprint, render_template, request, abort
from model.article import Article

index = Blueprint("index", __name__)



# ====展示首页文章列表、实现自动登录 视图函数====
"""
以后当浏览器（客户端）访问主页时，
服务器先默认看看其请求中的cookie信息中是否携带了用户会话管理信息
（此处我采用的不是存储会话ID即用户会话管理的自动登录方案，而是采取直接存储用户名、加密密码来实现验证客户端身份的自动登录方案），
若cookie中携带了相应信息且匹配上了，那就直接帮助用户登录了，省得用户再去输用户名、密码
"""
@index.route('/')
def home():  # 不可同蓝本模块名一样
    # 因为利用before_request钩子实现了全局的自动登录，所以此处根页面的自动登录不需要了，已经在全局自动登录中覆盖实现了
    # *以下为实现自动登录功能的组成部分：客户端访问时，服务器检查其cookie信息中是否携带有效用户会话管理信息*
    # 只有当 当前处于非登录状态时才有必要去尝试帮用户自动登录
    # if session.get('islogin') is None:
    #     print('尝试了用cookie实现自动登录1！！！！！！！')
    #     # 从用户请求的cookie值中获取信息，然后去尝试自动登录
    #     username = request.cookies.get('username')
    #     password = request.cookies.get('password')
    #     if username and password:  # 如果cookie中确实存在用于自动登录用的信息，才往下走
    #         user = Users()
    #         result = user.find_by_username(username)
    #         # 拿着用户输入的用户查询数据库查询到了结果且确实只为一条结果，再是密码验证通过，那么就可以登录了
    #         if len(result) == 1 and result[0].password == password:
    #             session['islogin'] = 'true'
    #             session['userid'] = result[0].userid
    #             session['username'] = username
    #             session['nickname'] = result[0].nickname
    #             session['role'] = result[0].role
    #         else:
    #             pass

    # *以下为展示首页文章功能*
    article = Article()
    result = article.find_limit_with_users(0, 10)  # 首页展示的是article表中从第0行开始的前10行数据

    # 根据文章总数与每页文章数目计算总页数（为了在访问根页面时不会由于缺失page、total_page_num参数而导致报错，所以在根页面对应视图函数中也需加上）
    page_size = 10
    total_count = article.get_total_count()
    total_page_num = max(1, ceil(total_count / page_size))

    # 首页，所以page=1，total还是根据查询到的页面总数即可
    return render_template('index.html', result=result, page=1, total_page_num=total_page_num)


# 用于展示首页之后的页面中文章列表（第二页、第三页等）
@index.route('/page/<int:page>')
def paginate(page):
    page_size = 10
    start = (page - 1) * page_size  # 根据页码换算出 在数据库中所取数据的开始位置
    article = Article()
    result = article.find_limit_with_users(start, page_size)  # 从数据库中取出相应位置的数据

    # 根据文章总数与每页文章数目计算总页数
    total_count = article.get_total_count()
    total_page_num = max(1, ceil(total_count / page_size))

    return render_template('index.html', result=result, page=page, total_page_num=total_page_num)


@index.route('/type/<string:type_str>')
def classify(type_str):
    # 前端传过来的参数的格式是类似'2-1'这种，所以需要处理
    type = int(type_str.split('-')[0])
    page = int(type_str.split('-')[1])

    page_size = 10
    start = (page - 1) * page_size  # 根据页码换算出 在数据库中所取数据的开始位置
    article = Article()
    result = article.find_by_type(type, start, page_size)  # 从数据库中取出相应类别、相应位置的数据

    # 根据文章总数与每页文章数目计算总页数
    total_count = article.get_total_count_by_type(type)
    total_page_num = max(1, ceil(total_count / page_size))

    return render_template('type.html', result=result, page=page, total_page_num=total_page_num, type=type)


# 不用像主页（home）那样分成两个路由端点来写，因为如下一个就能完成
@index.route('/search/<int:page>-<keyword>')
def search(page, keyword):
    # 后端校验过滤非法用户搜索内容
    keyword = keyword.strip()
    if not keyword or len(keyword) > 50:
        abort(404)


    page_size = 10
    start = (page - 1) * page_size  # 根据页码换算出 在数据库中所取数据的开始位置（用于展示一页）
    article = Article()
    result = article.find_by_headline(keyword, start, page_size)  # 从数据库中取出标题中带相应关键字的、相应位置的文章（用于展示一页）

    # 根据按关键字搜得的文章总数与每页文章数目计算总页数（用于分页）
    total_count = article.get_total_count_by_headline(keyword)
    total_page_num = max(1, ceil(total_count / page_size))

    return render_template('search.html', result=result, page=page, total_page_num=total_page_num, keyword=keyword)


# 用于展示首页文章列表（从Redis中获取以分散数据库压力）
from common.redisdb import redis_connect
@index.route('/redis')
def home_redis():
    red = redis_connect()
    # 利用zrevrange从有序集合中倒序取0-9共10条数据，即最新文章
    result = red.zrevrange('article', 0, 9)

    # 由于加载进来的每一条数据是一个字符串，使用ast.literal_eval安全地将其转换为字典
    article_list = []
    for article in result:
        article_list.append(ast.literal_eval(article))

    page_size = 10
    total_count = red.zcard('article')  # 获取有序集合article的总数量
    total_page_num = max(1, ceil(total_count / page_size))  # 计算得到页面总数

    return render_template('index-redis.html', article_list=article_list, page=1, total_page_num=total_page_num)


# 用于展示首页之后的页面中文章列表（从Redis中获取）
@index.route('/redis/page/<int:page>')
def paginate_redis(page):
    # 利用zrevrange从有序集合中倒序取start ~ start+9共10条数据
    page_size = 10
    start = (page - 1) * page_size
    red = redis_connect()
    result = red.zrevrange('article', start, start + page_size - 1)

    # 由于加载进来的每一条数据是一个字符串，使用ast.literal_eval安全地将其转换为字典
    article_list = []
    for article in result:
        article_list.append(ast.literal_eval(article))

    total_count = red.zcard('article')  # 获取有序集合article的总数量
    total_page_num = max(1, ceil(total_count / page_size))  # 计算得到页面总数

    return render_template('index-redis.html', article_list=article_list, page=page, total_page_num=total_page_num)