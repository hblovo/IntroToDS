from crawlbase import CrawlingAPI
import json
from bs4 import BeautifulSoup

# 初始化 Crawlbase API
crawling_api = CrawlingAPI({'token': 'RGGrkIvA0Se0dajCAU2iQw'})

# 解析书籍和评论详情
def extract_book_details(html):
    soup = BeautifulSoup(html, 'html.parser')
    title_elem = soup.select_one('h1.H1Title a[data-testid="title"]')
    title = title_elem.text.strip() if title_elem else None

    rating_elem = soup.select_one('div.RatingStatistics span.RatingStars')
    rating = rating_elem['aria-label'] if rating_elem and 'aria-label' in rating_elem.attrs else None

    reviews = []
    for review_div in soup.select('article.ReviewCard'):
        # 用户名 & 用户ID
        user_elem = review_div.select_one('.ReviewerProfile__name a')
        user = user_elem.text.strip() if user_elem else None
        user_id = None
        if user_elem and 'href' in user_elem.attrs:
            href = user_elem['href']
            if "/user/show/" in href:
                user_id = href.split("/user/show/")[-1].split("-")[0]

        # 用户评分
        rating_elem = review_div.select_one('.ShelfStatus span[aria-label*="out of 5"]')
        user_rating = rating_elem['aria-label'] if rating_elem and 'aria-label' in rating_elem.attrs else None

        # 评论时间
        date_elem = review_div.select_one('.ReviewCard__row span.Text a')
        review_date = date_elem.text.strip() if date_elem else None

        # 评论内容
        review_text_elem = review_div.select_one('.ReviewText__content span.Formatted')
        review_text = review_text_elem.get_text(" ", strip=True) if review_text_elem else None

        # 点赞数
        likes_elem = review_div.select_one('footer.SocialFooter button span:contains("likes")')
        likes = likes_elem.text.strip() if likes_elem else None

        # 评论数
        comments_elem = review_div.select_one('footer.SocialFooter button span:contains("comments")')
        comments = comments_elem.text.strip() if comments_elem else None

        reviews.append({
            'user': user,
            'user_id': user_id,
            'user_rating': user_rating,
            'review_date': review_date,
            'review': review_text,
            'likes': likes,
            'comments': comments
        })

    return {'title': title, 'rating': rating, 'reviews': reviews}

# 爬取 Goodreads 首页评论
def scrape_goodreads_first_page(base_url):
    response = crawling_api.get(base_url, {
        'ajax_wait': 'true',
        'page_wait': '5000',
    })

    if response['headers']['pc_status'] == '200':
        html_content = response['body'].decode('utf-8')
        return extract_book_details(html_content)
    else:
        print("Request failed:", response['headers']['pc_status'])
        return None

# 保存 JSON 文件
def save_reviews_to_json(data, filename='goodreads_reviews.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 示例用法
if __name__ == "__main__":
    book_reviews = scrape_goodreads_first_page(
        #Here you can alter the URL to get some reviews of different books
        'https://www.goodreads.com/book/show/4671.The_Great_Gatsby/reviews'
    )
    if book_reviews:
        save_reviews_to_json(book_reviews)
        print("保存完成: goodreads_reviews.json")
