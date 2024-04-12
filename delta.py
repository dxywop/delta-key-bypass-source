# Made by de20kw

from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions
from lxml import html
import json
import base64
import re
from urllib.parse import unquote
import threading
import time
from requests_html import HTMLSession
import os


app = Flask(__name__)

session = HTMLSession()
cookies = session.cookies  # Access the cookies

def pass_cycle(_driver) -> str:
    """Pass"""
    counter = 0  # Initialize counter

    while counter < 30:  # Check if counter has reached 6
        try:
            if _driver('xpath://div/iframe').s_ele(".ctp-checkbox-label") is not None:
                _driver('xpath://div/iframe').ele(".ctp-checkbox-label", timeout=0.1).click()
                break  # If click is successful, break the loop
        except Exception as e:
            print(f"Error: {e}".encode('cp1252', errors='replace').decode('cp1252'))
            counter += 1  # Increment counter if click fails
            pass

def process_hwid(user_hwid):
    # Check if a key already exists for this user_hwid
    check_url = f"https://api-gateway.platoboost.com/v1/authenticators/8/{user_hwid}"
    check_response = session.get(check_url, cookies=cookies)  # Pass the cookies to the request

    try:
        response_json = json.loads(check_response.text)
        existing_key = response_json.get('key')
        if existing_key:
            return f"key: {existing_key}"
    except json.JSONDecodeError:
        print('Response is not in JSON format')
    page = ChromiumPage()

    new_tab = page.new_tab()
    tab = page.get_tab(new_tab)

    options = ChromiumOptions()
    arguments = [
        "-no-first-run",
        "-force-color-profile=srgb",
        "-metrics-recording-only",
        "-password-store=basic",
        "-use-mock-keychain",
        "-export-tagged-pdf",
        "-no-default-browser-check",
        "-disable-background-mode",
        "-enable-features=NetworkService,NetworkServiceInProcess,LoadCryptoTokenExtension,PermuteTLSExtensions",
        "-disable-features=FlashDeprecationWarning,EnablePasswordsAccountStorage",
        "-deny-permission-prompts",
        "-disable-gpu"
    ]

    for argument in arguments:
        options.set_argument(argument)

    tab.get(f"https://gateway.platoboost.com/a/8?id={user_hwid}")

    pass_cycle(tab)

    token_value = None
    timeout = time.time() + 30
    while time.time() < timeout:
        html_content = tab.html
        tree = html.fromstring(html_content)
        cf_response_values = tree.xpath('//input[@name="cf-turnstile-response"]/@value')
        if cf_response_values:
            token_value = cf_response_values[0]
            break
        else:
            time.sleep(0.1)

    if token_value is None:
        return "solve the captcha"    
    tab.close()


    payload = {
        "captcha": token_value,
        "type": "Turnstile"
    }

    auth_url = f"https://api-gateway.platoboost.com/v1/sessions/auth/8/{user_hwid}"
    response = session.post(auth_url, json=payload, cookies=cookies)
    response.raise_for_status()

    response_json = json.loads(response.text)
    encoded_redirect_url = response_json.get('redirect')
    unquoted_url = unquote(encoded_redirect_url)

    pattern = r"r=([^&]+)"
    match = re.search(pattern, unquoted_url)
    if match:
        encoded_url = match.group(1)
        encoded_url = encoded_url.rstrip("=")
        padding = '=' * ((4 - len(encoded_url) % 4) % 4)
        encoded_url += padding

        decoded_bytes = base64.urlsafe_b64decode(encoded_url)
        decoded_url = decoded_bytes.decode("utf-8") 

    token_pattern = r"&tk=(\w{4})"
    token_match = re.search(token_pattern, decoded_url)
    if token_match:
        api_token = token_match.group(1)
        time.sleep(5)
        put_url = f"https://api-gateway.platoboost.com/v1/sessions/auth/8/{user_hwid}/{api_token}"
        put_response = session.put(put_url, cookies=cookies)
        put_response.raise_for_status()
        get_url = f"https://api-gateway.platoboost.com/v1/authenticators/8/{user_hwid}"
        get_response = session.get(get_url, cookies=cookies)
        get_response.raise_for_status()

    get_response = session.get(get_url)
    if get_response.text:
        try:
            response_json = json.loads(get_response.text)
            key_value = response_json.get('key', 'No key found in response')
        except json.JSONDecodeError:
            key_value = 'Response is not in JSON format'
    else:
        key_value = 'No response received'

    return f"key: {key_value}"

@app.route('/velxapi/delta/', methods=['GET'])
def delta():
    user_hwid = request.args.get('userid')
    if not user_hwid or not user_hwid.isalnum():  # Check if `userid` is present and alphanumeric
        return jsonify({"error": "Invalid or missing 'userid' parameter."}), 400

    # If `userid` is valid, proceed with the rest of the function
    key_value = process_hwid(user_hwid)
    return jsonify({"key": key_value})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 80))  # Get port from environment variable or choose 80 as default
    app.run(host='0.0.0.0', port=port, debug=True)
