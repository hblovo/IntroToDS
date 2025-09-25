import requests
from bs4 import BeautifulSoup
import json
import re
import time

# 构建请求头，模拟浏览器
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

# 解析书籍和评论详情（单页）
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

    return title, rating, reviews

# 爬取 Goodreads 所有评论
def scrape_goodreads_all_reviews(base_url):
    all_reviews = []
    page = 1
    title, rating = None, None

    while True:
        if page > 10:
            break
        url = f"{base_url}?page={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"请求失败: {response.status_code}")
            break

        t, r, reviews = extract_book_details(response.text)
        if not reviews:  # 没有更多评论了
            break

        if not title:
            title, rating = t, r

        all_reviews.extend(reviews)
        print(f"✅ 已抓取第 {page} 页, 共 {len(all_reviews)} 条评论")
        page += 1
        time.sleep(2)  # 防止过快请求被封

    return {'title': title, 'rating': rating, 'reviews': all_reviews}

# 保存 JSON 文件
def save_reviews_to_json(data, book_id):
    filename = f"goodreads_reviews_{book_id}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"💾 已保存到 {filename}")

# 主程序
if __name__ == "__main__":
    base_url = "https://www.goodreads.com/book/show/4671.The_Great_Gatsby/reviews"

    # 提取 book_id (4671)
    match = re.search(r'/book/show/(\d+)', base_url)
    book_id = match.group(1) if match else "unknown"

    book_reviews = scrape_goodreads_all_reviews(base_url)
    if book_reviews:
        save_reviews_to_json(book_reviews, book_id)
