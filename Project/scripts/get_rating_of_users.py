import json
import time
from urllib.parse import urljoin, urlparse, parse_qs
import re
import requests
from bs4 import BeautifulSoup

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
    if not href:
        return None
    m = re.search(r"/book/show/(\d+)", href)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
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
    if not td_rating:
        return None, None
    stars = td_rating.select_one("span.staticStars[title]")
    if stars and stars.has_attr("title"):
        title = stars["title"].strip().lower()
        return title, rating_map.get(title)
    inner = td_rating.select_one("span.staticStars span[title]")
    if inner and inner.has_attr("title"):
        title = inner["title"].strip().lower()
        return title, rating_map.get(title)
    return None, None

def extract_my_rating_fallback(td_shelves):
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
                for k, v in rating_map.items():
                    if v == iv:
                        return k, iv
            except Exception:
                pass
    return None, None

def parse_list_page(html, base_url):
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("tr.bookalike.review")
    if not rows:
        rows = soup.select("table#books tr") or []

    items = []
    for tr in rows:
        book_title, book_href, book_url, book_id = None, None, None, None

        td_title = tr.select_one("td.field.title, td.title")
        if td_title:
            a_book = td_title.select_one("a.bookTitle, a[href*='/book/show/']")
            if a_book:
                book_title = get_text(a_book) or None
                book_href = a_book.get("href")
                if book_href:
                    book_url = urljoin(base_url, book_href)
                    book_id = extract_book_id_from_href(book_href)

        if not (book_id and book_title and book_url):
            td_cover = tr.select_one("td.field.cover")
            if td_cover:
                a_cover = td_cover.select_one("a[href*='/book/show/']")
                if a_cover:
                    href2 = a_cover.get("href")
                    if href2:
                        if not book_href:
                            book_href = href2
                        if not book_url:
                            book_url = urljoin(base_url, href2)
                        res_div = td_cover.select_one("[data-resource-id]")
                        if res_div and res_div.has_attr("data-resource-id"):
                            try:
                                book_id = int(res_div["data-resource-id"])
                            except Exception:
                                pass
                        if not book_id:
                            book_id = extract_book_id_from_href(href2)
                if not book_title:
                    img = td_cover.select_one("img[alt]")
                    if img:
                        book_title = (img.get("alt") or "").strip() or None

        td_author = tr.select_one("td.field.author, td.author")
        a_author = td_author.select_one("a") if td_author else None
        author_name = get_text(a_author) or get_text(td_author)

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

        review_link = tr.select_one("a[href*='/review/show/']")
        review_url = urljoin(base_url, review_link["href"]) if review_link and review_link.has_attr("href") else None

        if book_id and book_title and book_url:
            items.append({
                "book_id": book_id,
                "book_title": book_title,
                "book_url": book_url,
                "author": author_name,
                "user_rating_text": rating_text,
                "user_rating": rating_value,
                "date_read": date_read,
                "date_added": date_added,
                "shelves": shelves,
                "review_url": review_url,
            })

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
    USER_ID = "27788046"
    MAX_PAGES = 15

    url = f"https://www.goodreads.com/review/list/{USER_ID}?sort=rating&view=reviews"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
    }
    cookies = {
        # 这里可以放必要的 cookie，如果页面有权限要求
    }

    data = crawl_goodreads_list(url, headers, cookies, max_pages=MAX_PAGES)

    out_path = f"./goodreads_ratings_{USER_ID}.json"
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
