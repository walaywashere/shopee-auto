"""
Shopee.ph Automation Script using Nodriver (async-first successor to undetected-chromedriver)
Headed mode for visual observation and debugging
"""

import nodriver
from nodriver import cdp
import asyncio
import time
import os
import base64


async def initialize_browser():
    """Initialize nodriver browser in headed mode"""
    print("[*] Launching nodriver browser in headed mode...")
    
    browser = await nodriver.start(
        headless=False,  # Headed mode (visible browser window)
        browser_args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-notifications',
        ],
        lang="en-US"
    )
    
    print("[+] Browser initialized successfully")
    return browser


async def load_cookies_from_file(tab, filename="cookies.txt"):
    """Load cookies from header string format"""
    if not os.path.exists(filename):
        print(f"[!] Cookie file not found: {filename}")
        return False
    
    try:
        with open(filename, 'r') as f:
            cookie_string = f.read().strip()
        
        # Parse header format cookies: "name1=value1; name2=value2; ..."
        cookies_list = cookie_string.split(";")
        
        print(f"[*] Loading cookies from {filename}...")

        try:
            await tab.send(cdp.network.enable())
        except Exception as e:
            print(f"[!] Could not enable network domain: {str(e)}")

        cookie_count = 0
        
        for cookie_pair in cookies_list:
            try:
                cookie_pair = cookie_pair.strip()
                if not cookie_pair:
                    continue
                if "=" not in cookie_pair:
                    continue
                name, value = cookie_pair.split("=", 1)
                await tab.send(
                    cdp.network.set_cookie(
                        name=name.strip(),
                        value=value.strip(),
                        domain=".shopee.ph",
                        path="/",
                        secure=True,
                        http_only=False,
                        url="https://shopee.ph/"
                    )
                )
                cookie_count += 1
            except Exception as e:
                print(f"[!] Could not add cookie {cookie_pair}: {str(e)}")
        
        print(f"[+] {cookie_count} cookies loaded successfully")
        return True
    
    except Exception as e:
        print(f"[!] Error loading cookies: {str(e)}")
        return False


async def intercept_network_events(tab):
    """Setup network interception for API responses"""
    print("[*] Setting up network interception...")

    try:
        await tab.send(cdp.network.enable())
    except Exception as e:
        print(f"[!] Failed to enable network tracking: {str(e)}")

    target_endpoint = "https://api.airpayservice.com/v1/cc/txn/channels/cybs/enroll_check"
    pending_bodies = set()

    async def on_request(event, tab_ref=None):
        try:
            request_url = event.request.url
            if "airpayservice.com" in request_url:
                print(f"\n[>] Request: {request_url}")
                print(f"    Method: {event.request.method}")
        except Exception as err:
            print(f"[!] Request handler error: {err}")

    async def on_response(event, tab_ref=None):
        try:
            response_url = event.response.url
            if "airpayservice.com" in response_url:
                print(f"\n[<] Response: {response_url}")
                print(f"    Status: {event.response.status}")
                print(f"    Status Text: {event.response.status_text}")
                if target_endpoint in response_url:
                    pending_bodies.add(event.request_id)
        except Exception as err:
            print(f"[!] Response handler error: {err}")

    async def on_loading_finished(event, tab_ref=None):
        try:
            if event.request_id in pending_bodies:
                pending_bodies.remove(event.request_id)
                try:
                    body, is_base64 = await tab.send(
                        cdp.network.get_response_body(event.request_id)
                    )
                    if is_base64:
                        try:
                            body = base64.b64decode(body).decode("utf-8", errors="replace")
                        except Exception:
                            body = "<binary body>"
                    print(f"    Body: {body}")
                except Exception as body_err:
                    print(f"    [!] Could not fetch response body: {body_err}")
        except Exception as err:
            print(f"[!] LoadingFinished handler error: {err}")

    tab.add_handler(cdp.network.RequestWillBeSent, on_request)
    tab.add_handler(cdp.network.ResponseReceived, on_response)
    tab.add_handler(cdp.network.LoadingFinished, on_loading_finished)
    print("[+] Network interception ready - listening for airpayservice responses")


async def fill_payment_form(tab, card_data):
    """Fill the payment form with card details"""
    
    # Card Number
    print(f"\n[*] Step 1: Filling card number...")
    card_xpath = '//*[@id="root"]/div[2]/div[1]/div[4]/div[2]/div[1]/div/div/input'
    try:
        card_elements = await tab.xpath(card_xpath, timeout=10)
        if card_elements:
            card_element = card_elements[0]
            await card_element.scroll_into_view()
            await card_element.focus()
            await card_element.clear_input()
            await card_element.send_keys(card_data['card_number'])
            print("[+] Card number filled")
        else:
            print("[!] Card number field not found")
    except Exception as e:
        print(f"[!] Error filling card number: {str(e)}")
    
    # MM/YY
    print(f"\n[*] Step 2: Filling MM/YY...")
    mmyy_xpath = '//*[@id="root"]/div[2]/div[1]/div[4]/div[3]/div[1]/div/div[1]/div/div/input'
    try:
        mmyy_elements = await tab.xpath(mmyy_xpath, timeout=10)
        if mmyy_elements:
            mmyy_element = mmyy_elements[0]
            await mmyy_element.scroll_into_view()
            await mmyy_element.focus()
            await mmyy_element.clear_input()
            await mmyy_element.send_keys(card_data['mmyy'])
            print("[+] MM/YY filled")
        else:
            print("[!] MM/YY field not found")
    except Exception as e:
        print(f"[!] Error filling MM/YY: {str(e)}")
    
    # CVV
    print(f"\n[*] Step 3: Filling CVV...")
    cvv_xpath = '//*[@id="root"]/div[2]/div[1]/div[4]/div[3]/div[2]/div/div[1]/div/div[1]/input'
    try:
        cvv_elements = await tab.xpath(cvv_xpath, timeout=10)
        if cvv_elements:
            cvv_element = cvv_elements[0]
            await cvv_element.scroll_into_view()
            await cvv_element.focus()
            await cvv_element.clear_input()
            await cvv_element.send_keys(card_data['cvv'])
            print("[+] CVV filled")
        else:
            print("[!] CVV field not found")
    except Exception as e:
        print(f"[!] Error filling CVV: {str(e)}")
    
    # Name
    print(f"\n[*] Step 4: Filling cardholder name...")
    name_xpath = '//*[@id="root"]/div[2]/div[1]/div[4]/div[4]/div[1]/div/div/input'
    try:
        name_elements = await tab.xpath(name_xpath, timeout=10)
        if name_elements:
            name_element = name_elements[0]
            print("[*] Name input located")
            await name_element.scroll_into_view()
            await name_element.focus()
            await name_element.clear_input()
            await name_element.send_keys(card_data['name'])
            print("[+] Name filled")
        else:
            print("[!] Name field not found")
    except Exception as e:
        print(f"[!] Error filling name: {str(e)}")
    
    # Submit Button
    print(f"\n[*] Step 5: Clicking submit button...")
    submit_xpath = '//*[@id="root"]/div[2]/div[2]/div/button[2]'
    try:
        submit_buttons = await tab.xpath(submit_xpath, timeout=10)
        if submit_buttons:
            submit_button = submit_buttons[0]
            print(f"[+] Submit button found and clickable")
            print(f"[*] Submitting form...")
            await submit_button.click()
            try:
                await asyncio.sleep(3)
            except asyncio.CancelledError:
                print("[!] Submit wait interrupted, continuing...")
            print(f"[+] Form submitted!")
            print(f"[*] Current URL: {tab.url}")
        else:
            print("[!] Submit button not found")
    except Exception as e:
        print(f"[!] Error clicking submit button: {str(e)}")


async def main():
    """Main execution function"""
    browser = None
    
    try:
        # Initialize browser
        browser = await initialize_browser()
        
        # Create a new tab
        tab = await browser.get('about:blank')
        
        # Setup network interception
        await intercept_network_events(tab)

        # Load cookies before navigating to the target page
        cookies_loaded = await load_cookies_from_file(tab)
        if cookies_loaded:
            print("[+] Cookies loaded. Verifying session on shopee.ph...")
            await tab.get("https://shopee.ph/")
            await asyncio.sleep(3)
        else:
            print("[!] Proceeding without cookies (login may be required)")

        # Navigate to payment page
        payment_url = "https://pay.shopee.ph/payment-v2/add-card?add_card_scene=0&block_cc=False&client_id=40024&is_mepage=1&page_type=2&payment_channel_id=4004000&post_to_tpp=True&to_local_spm=0&callback_url=https%3A%2F%2Fshopee.ph%2Fuser%2Faccount%2Fpayment"
        
        print(f"\n[*] Navigating to payment page...")
        for attempt in range(3):
            try:
                await tab.get(payment_url)
                print("[+] Payment page loaded successfully")
                break
            except Exception as e:
                print(f"[!] Payment page load attempt {attempt + 1} failed: {str(e)[:80]}")
                if attempt < 2:
                    print(f"[*] Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    print(f"[!] Failed to load payment page after 3 attempts")
                    raise
        
        try:
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            print("[!] Navigation wait interrupted, continuing...")
        
        print(f"[+] Payment page loaded successfully")
        print(f"[*] Current URL: {tab.url}")
        
        # Prepare card data
        card_data = {
            'card_number': '4162950195300712',
            'mmyy': '03/27',
            'cvv': '017',
            'name': 'roja kun'
        }
        
        print(f"\n[*] Starting form filling process...")
        # Fill and submit form
        try:
            await fill_payment_form(tab, card_data)
            
            # Wait for API response
            print(f"\n[*] Waiting for API response from airpayservice...")
            try:
                await asyncio.wait_for(asyncio.sleep(3), timeout=3)
            except asyncio.TimeoutError:
                pass
            
        except Exception as e:
            print(f"[!] Error during form filling: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Keep browser open for observation
        print(f"\n[*] Keeping browser open for 60 seconds for observation...")
        print("[*] You can now interact with the page manually.")
        try:
            await asyncio.wait_for(asyncio.sleep(60), timeout=60)
        except asyncio.TimeoutError:
            pass
        print("[+] Duration complete")
        
        print("\n[+] Script completed successfully")
        
    except asyncio.CancelledError:
        print("[!] Operation cancelled by nodriver")
    except Exception as e:
        print(f"[!] Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        if browser:
            print("\n[*] Closing browser...")
            try:
                await browser.quit()
            except:
                pass
            print("[+] Browser closed")


if __name__ == "__main__":
    asyncio.run(main())
