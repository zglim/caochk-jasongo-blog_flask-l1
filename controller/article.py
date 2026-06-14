"""
controller.article控制器代码
该控制器主要实现文章详情页展示功能
"""
from flask import render_template, abort, Blueprint

from model.article import Article

article = Blueprint("article", __name__)


@article.route('/article/<int:articleid>')
def read(articleid):
    try:
        result = Article().find_by_id(articleid)
        if result is None:
            abort(404)  # 如果文章id不正确导致未能搜到任何结果，就返回404页面
    except:
        abort(500)  # 出现了异常则返回500页面

    # 增加1次阅读次数
    Article().update_read_count(articleid)
    return render_template('article-user.html', result=result)