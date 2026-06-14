from sqlalchemy import Table
from common.database import dbconnect
from model.users import Users

dbsession, md, DBase = dbconnect()

# article表的关系模型
class Article(DBase):
    __table__ = Table("article", md, autoload=True)

    # 查询article表中的所有数据
    def find_all(self):
        result = dbsession.query(Article).order_by(Article.articleid.desc()).all()
        return result

    # 根据id在article表中找到唯一对应数据
    def find_by_id(self, articleid):
        result = dbsession.query(Article, Users.nickname).join(Users, Users.userid == Article.userid).filter(
            Article.hide == 0, Article.drafted == 0, Article.checked == 1, Article.articleid == articleid).order_by \
            (Article.articleid.desc()).first()
        return result

    # article表与users表进行连接查询，返回10条记录。
    # 返回10条记录的原因是博客系统首页中每页肯定只能展示一部分文章，在此定为每页10篇，然后分页。
    def find_limit_with_users(self, start, count):
        result = dbsession.query(Article, Users.nickname).join(Users, Users.userid==Article.userid).filter(Article.hide==0, \
            Article.drafted==0, Article.checked==1).order_by\
            (Article.articleid.desc()).limit(count).offset(start).all()
        # print(result)
        return result

    # 获取文章（未隐藏、非草稿、已审核）总数量
    def get_total_count(self):
        result = dbsession.query(Article).filter(Article.hide == 0, Article.drafted == 0,
                                                 Article.checked == 1).count()
        return result

    # 根据文章类型来获取文章总数量
    def get_total_count_by_type(self, type):
        count = dbsession.query(Article).filter(Article.hide == 0, Article.drafted == 0,
                                                Article.checked == 1, Article.category == type).count()
        return count

    # 按照文章类型获取文章
    def find_by_type(self, type, start, count):
        result = dbsession.query(Article, Users.nickname).join(Users, Users.userid == Article.userid).filter(
            Article.hide == 0, Article.drafted == 0, Article.checked == 1, Article.category == type).order_by \
            (Article.articleid.desc()).limit(count).offset(start).all()
        return result

    # 转义LIKE查询中的特殊字符，防止用户输入的 %、_、\ 产生非预期匹配
    @staticmethod
    def _escape_like(keyword):
        keyword = keyword.replace('\\', '\\\\')
        keyword = keyword.replace('%', '\\%')
        keyword = keyword.replace('_', '\\_')
        return keyword

    # 用户通过搜索框进行搜索，拿着用户输入关键词检索数据库article表中的标题字段（暂未实现全文搜索）
    def find_by_headline(self, headline, start, count):
        safe_headline = self._escape_like(headline)
        result = dbsession.query(Article, Users.nickname).join(Users, Users.userid == Article.userid).filter(
            Article.hide == 0, Article.drafted == 0, Article.checked == 1,
            Article.headline.like('%' + safe_headline + '%', escape='\\')).order_by \
            (Article.articleid.desc()).limit(count).offset(start).all()
        return result

    # 按搜索关键字获取文章（未隐藏、非草稿、已审核）总数量
    def get_total_count_by_headline(self, headline):
        safe_headline = self._escape_like(headline)
        result = dbsession.query(Article).filter(Article.hide == 0, Article.drafted == 0, Article.checked == 1,
                                                 Article.headline.like('%' + safe_headline + '%', escape='\\')).count()
        return result

    # 每阅读一次文章，阅读次数+1
    def update_read_count(self, articleid):
        article = dbsession.query(Article).filter_by(articleid=articleid).first()
        article.readcount += 1
        dbsession.commit()

    # 根据文章编号查询文章标题
    def find_headline_by_id(self, articleid):
        row = dbsession.query(Article.headline).filter_by(articleid=articleid).first()
        return row.headline