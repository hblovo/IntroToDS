import json
import time
from urllib.parse import urljoin, urlparse, parse_qs
import re
import requests
from bs4 import BeautifulSoup

# =============== 你已有的配置 ===============
url = "https://www.goodreads.com/review/list/3672777?sort=rating&view=reviews"

cookies = {
    "ccsid": "379-0866094-5504217",
    "ubid-main": "133-4921598-2766758",
    "likely_has_account": "true",
    "csm-sid": "633-9155635-2102392",
    "allow_behavioral_targeting": "true",
    "lc-main": "en_US",
    "blocking_sign_in_interstitial": "true",
    "session-id": "143-3116519-0844337",
    "session-id-time": "2389244579l",
    "session-token": "4/2rc/eN7zn3FyZDPlk9pWea4iQQRZiwA0Z8nrvAmWvrVPmAMtDH5WQbPo0LVKMa0KJPXrW+vcPaJ+J8Pe1/4cSI9PK0R5gvROgDBG9tXOBbrrQwspXdLMrUg35XH0SJcwnB0DMPW/cH3kfi+qNCMfmrhuSEzs5fQzPHsUefAn1RcJjcdWwBOFmq+onPzYNPBdDdE8VCdz8GqdRwHcQWkc0899s1oc4O5ERpVR/rT8AJz3S9XIiSRo5d4fhV5fwWUNpLMUJV1vc7FCjyq7ke5b/Jpx1yuTa3upmIKWt+cpwPWt7p0bGQLKzBhVWgPYy/wnUoIDOfH92+xE4cCD7Eys+py0Gw4GithsYEvvPqcgAMj4RfNgHAZA==",
    "x-main": "ZgcOvBWIryMtH3oYMD6LrlWZWCi@ZcogAivSg1Bw@mZrviNUWCJ8TtbtdR650faZ",
    "at-main": "Atza|IwEBINqgfWdQKICLp8KKSbt2IwLUbjEC9bbFkt_tgb18smSJgf673E5xPsxYtbnIU313eITsTw7eJXwVw745O42G_to6JsJaVIwbog9kA7cFS3MB2gj3Vc9AHtWX5TRu8LYGmjgGA5Bl4L56nvcOwBYeEFZJ0g5efvzACAOsZ3h8deCNe7XBj-ydxSkmqdP-KO6kE3FkWW2eyzuKrqaFPgqXSBIFYp4gki--BlM3SDBN2Nj4B4jhKGESq0IxuU64-Ti4GCQ",
    "sess-at-main": "q5+uQocIxfCJ1e8KACcWRsBQPgrWWXeblTCS6Vys8P0=",
    "_session_id2": "ee4d764d32851fd7ac20d2ac07abb546",
    "locale": "en",
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "no-cache",
    "Referer": "https://www.goodreads.com/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# =============== 评分映射 ===============
rating_map = {
    "did not like it": 1,
    "it was ok": 2,
    "liked it": 3,
    "really liked it": 4,
    "it was amazing": 5
}

# =============== 抽取工具函数 ===============
def parse_int_safe(s):
    try:
        return int(s)
    except Exception:
        return None

def extract_book_id_from_href(href: str):
    """
    兼容 /book/show/233667.Firestarter、/book/show/233667-xxx、以及 ?book_id=233667
    """
    if not href:
        return None
    # /book/show/233667.Firestarter 或 /book/show/233667-xxx
    m = re.search(r"/book/show/(\d+)", href)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    # 兜底 query
    try:
        qs = parse_qs(urlparse(href).query)
        if "book_id" in qs:
            return int(qs["book_id"][0])
    except Exception:
        pass
    return None

def get_text(el):
    return el.get_text(strip=True) if el else None

def extract_rating_from_static_stars(td_rating):
    """
    从 <td class='field rating'> 里提取 staticStars 标题（it was amazing 等）
    """
    if not td_rating:
        return None, None
    stars = td_rating.select_one("span.staticStars[title]")
    if stars and stars.has_attr("title"):
        title = stars["title"].strip().lower()
        return title, rating_map.get(title)
    # 某些页面 title 在内层 span 上
    inner = td_rating.select_one("span.staticStars span[title]")
    if inner and inner.has_attr("title"):
        title = inner["title"].strip().lower()
        return title, rating_map.get(title)
    return None, None

def extract_my_rating_fallback(td_shelves):
    """
    在 “my rating” 的 div.stars 上，尝试从 data-rating / data-restore-rating 兜底
    """
    if not td_shelves:
        return None, None
    stars = td_shelves.select_one("div.stars")
    if not stars:
        return None, None
    for attr in ("data-rating", "data-restore-rating"):
        if stars.has_attr(attr):
            val = stars.get(attr)
            try:
                iv = int(val)
                # 反向映射：找第一个匹配的文字
                for k, v in rating_map.items():
                    if v == iv:
                        return k, iv
            except Exception:
                pass
    # 还可以从 a.star 的 title 判断，但通常 data-rating 已足够
    return None, None

def parse_list_page(html, base_url):
    soup = BeautifulSoup(html, "lxml")

    # 每本书的行：通常为 <tr class="bookalike review">
    rows = soup.select("tr.bookalike.review")
    if not rows:
        rows = soup.select("table#books tr") or []

    items = []
    for tr in rows:
        # ========== 书名 / 链接 / ID ==========
        book_title, book_href, book_url, book_id = None, None, None, None

        # 1) 常规标题列
        td_title = tr.select_one("td.field.title, td.title")  # 去掉 td:nth-of-type(2) 避免误取 position
        if td_title:
            a_book = td_title.select_one("a.bookTitle, a[href*='/book/show/']")
            if a_book:
                book_title = get_text(a_book) or None
                book_href = a_book.get("href")
                if book_href:
                    book_url = urljoin(base_url, book_href)
                    book_id = extract_book_id_from_href(book_href)

        # 2) 封面列兜底（你给的 HTML 结构）
        if not (book_id and book_title and book_url):
            td_cover = tr.select_one("td.field.cover")
            if td_cover:
                # 链接（/book/show/233667.Firestarter）
                a_cover = td_cover.select_one("a[href*='/book/show/']")
                if a_cover:
                    href2 = a_cover.get("href")
                    if href2:
                        if not book_href:
                            book_href = href2
                        if not book_url:
                            book_url = urljoin(base_url, href2)
                        # book_id：优先 data-resource-id，再从 href 中抠
                        res_div = td_cover.select_one("[data-resource-id]")
                        if res_div and res_div.has_attr("data-resource-id"):
                            try:
                                book_id = int(res_div["data-resource-id"])
                            except Exception:
                                pass
                        if not book_id:
                            book_id = extract_book_id_from_href(href2)
                # 书名：封面图 alt
                if not book_title:
                    img = td_cover.select_one("img[alt]")
                    if img:
                        book_title = (img.get("alt") or "").strip() or None

        # 作者
        td_author = tr.select_one("td.field.author, td.author")
        a_author = td_author.select_one("a") if td_author else None
        author_name = get_text(a_author) or get_text(td_author)

        # 用户评分（优先 '...’s rating' 的 staticStars，再 fallback 到 'my rating'）
        td_rating = None
        for td in tr.select("td.field"):
            label = td.select_one("label")
            if label and label.get_text(strip=True).lower().endswith("'s rating"):
                td_rating = td
                break
        if td_rating is None:
            td_rating = tr.select_one("td.field.rating")

        rating_text, rating_value = extract_rating_from_static_stars(td_rating)

        if rating_value is None:
            td_shelves = None
            for td in tr.select("td.field"):
                label = td.select_one("label")
                if label and label.get_text(strip=True).lower() == "my rating":
                    td_shelves = td
                    break
            if td_shelves is None:
                td_shelves = tr.select_one("td.field.shelves")
            rt2, rv2 = extract_my_rating_fallback(td_shelves)
            if rv2 is not None:
                rating_text, rating_value = rt2, rv2

        # 日期（若存在）
        date_read = None
        date_added = None
        for td in tr.select("td.field"):
            label = td.select_one("label")
            if not label:
                continue
            lab = label.get_text(strip=True).lower()
            if lab == "date read":
                date_read = get_text(td.select_one("div.value"))
            elif lab == "date added":
                date_added = get_text(td.select_one("div.value"))

        # 书架标签（可选）
        shelves = []
        td_shelves_text = None
        for td in tr.select("td.field"):
            label = td.select_one("label")
            if label and label.get_text(strip=True).lower() == "shelves":
                td_shelves_text = td
                break
        if td_shelves_text:
            for a in td_shelves_text.select("a[href*='/review/list']"):
                tag = get_text(a)
                if tag:
                    shelves.append(tag)

        # 评审页链接（如果有）
        review_link = tr.select_one("a[href*='/review/show/']")
        review_url = urljoin(base_url, review_link["href"]) if review_link and review_link.has_attr("href") else None

        # —— 只在三件套齐备时才收录，避免出现 book_title=position 或 null ——
        if book_id and book_title and book_url:
            items.append({
                "book_id": book_id,
                "book_title": book_title,
                "book_url": book_url,
                "author": author_name,
                "user_rating_text": rating_text,  # 如 "it was amazing"
                "user_rating": rating_value,      # 数值 1-5
                "date_read": date_read,
                "date_added": date_added,
                "shelves": shelves,
                "review_url": review_url,
            })

    # 下一页链接
    next_href = None
    a_next = soup.select_one("a[rel='next'], a.next_page, li.next a")
    if a_next and a_next.has_attr("href"):
        next_href = urljoin(base_url, a_next["href"])

    return items, next_href


# =============== 主流程 ===============
def crawl_goodreads_list(start_url, headers, cookies, max_pages=None, sleep_sec=1.5):
    sess = requests.Session()
    sess.headers.update(headers)
    for k, v in cookies.items():
        sess.cookies.set(k, v)

    all_items = []
    page_url = start_url
    page_count = 0

    while page_url:
        page_count += 1
        resp = sess.get(page_url, allow_redirects=True, timeout=30)
        print(f"[{resp.status_code}] GET {page_url}")
        if resp.status_code != 200:
            print("非 200 响应，中断。")
            break

        items, next_url = parse_list_page(resp.text, base_url="https://www.goodreads.com")
        print(f"  解析到 {len(items)} 条记录")
        all_items.extend(items)

        if max_pages and page_count >= max_pages:
            print(f"达到最大页数 {max_pages}，停止。")
            break

        if next_url and next_url != page_url:
            page_url = next_url
            time.sleep(sleep_sec)
        else:
            break

    return all_items

if __name__ == "__main__":
    # 设定最多抓取页数（None 表示自动翻到末页）
    MAX_PAGES = 1

    data = crawl_goodreads_list(url, headers, cookies, max_pages=MAX_PAGES)

    # 保存到 JSON 文件
    out_path = "./goodreads_ratings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "source_url": url,
                "count": len(data),
                "items": data,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"已保存：{out_path}（共 {len(data)} 条）")
