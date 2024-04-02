import datetime

from libs.commonlib.db_insist import get_db
from libs.commonlib.pymongo_paginated_cursor import PaginatedCursor as mpcur
import requests, os

#
# Vipps stuff :
#
VIPPS_PUBLIC_KEYS_URI        = os.getenv('VIPPS_PUBLIC_KEYS_URI', '')
VIPPS_CLIENT_ID              = os.getenv('VIPPS_CLIENT_ID' , '')
VIPPS_CLIENT_SECRET          = os.getenv('VIPPS_CLIENT_SECRET' , '')
VIPPS_SUBSCRIPTION_KEY       = os.getenv('VIPPS_SUBSCRIPTION_KEY', '')
VIPPS_MERCHANT_SERIAL_NUMBER = os.getenv('VIPPS_MERCHANT_SERIAL_NUMBER', '')
VIPPS_BASE_URL               = os.getenv('VIPPS_BASE_URL', '')
VIPPS_ACCESS_TOKEN           = VIPPS_BASE_URL + 'accesstoken/get'
VIPPS_PAYMENTS               = VIPPS_BASE_URL + 'ecomm/v2/payments/'

def vippsecomkey() -> str :
    url = VIPPS_ACCESS_TOKEN
    headers = {
        'client_id'                : VIPPS_CLIENT_ID,
        'client_secret'            : VIPPS_CLIENT_SECRET,
        'Ocp-Apim-Subscription-Key': VIPPS_SUBSCRIPTION_KEY,
        'Merchant-Serial-Number'   : VIPPS_MERCHANT_SERIAL_NUMBER
    }
    response = requests.post(url, headers=headers, json=None)
    response_json = response.json()
    return response_json.get('access_token' , '')

def vipps_claim(payment : dict, db = get_db()) :

    if 'wait_until' in payment :
        if payment['wait_until'] > datetime.datetime.utcnow().timestamp() :
            return
        else:
            db.insist_on_remove_attribute(payment['_id'], 'vipps_payments_in', 'wait_until')

    orderId = payment['vipps_order_id']
    url = VIPPS_PAYMENTS + orderId + '/capture'
    token = vippsecomkey()
    headers = {
        'Authorization'             : 'Bearer ' + token,
        'X-Request-Id'              : orderId,
        'Ocp-Apim-Subscription-Key' : VIPPS_SUBSCRIPTION_KEY,
        'Merchant-Serial-Number'    : VIPPS_MERCHANT_SERIAL_NUMBER
    }
    body : dict =  {
        "merchantInfo": {
            "merchantSerialNumber": VIPPS_MERCHANT_SERIAL_NUMBER
        },
        "transaction": {
            "transactionText": "This payment was captured by Vedbjorn.no"
        }
     }
    response = requests.post(url, headers=headers, json=body)
    response_json = response.json()
    if response.status_code == 200 :
        db.insist_on_update_one(payment, 'vipps_payments_in', 'status', 'paid')
        db.insist_on_update_one(payment, 'vipps_payments_in', 'vipps_msg', response_json)
    elif response.status_code == 400 :
        if isinstance(response_json, list) and len(response_json) > 0 and 'errorCode' in response_json[0] :
            errorCode = response_json[0]['errorCode']
            if errorCode == '61' :
                # If the amount we want to claim is too high, it means it has already been claimed
                db.insist_on_update_one(payment, 'vipps_payments_in', 'status', 'paid')
                db.insist_on_update_one(payment, 'vipps_payments_in', 'vipps_msg', response_json)
                return

            #
            # TODO : Properly handle the rest of the error codes listed at :
            # TODO : https://github.com/vippsas/vipps-ecom-api/blob/master/vipps-ecom-api.md#error-codes
            #
            db.insist_on_update_one(payment, 'vipps_payments_in', 'wait_until', datetime.datetime.utcnow().timestamp() + (5 * 60))
            db.insist_on_insert_one('log_errors', {
                'time': datetime.datetime.utcnow(),
                'service': 'emailer',
                'function': 'vipps_claim',
                'description': 'Vipps API returned ' + str(response.status_code) + ' on POST ' + url,
                'details': response_json
            })

    elif response.status_code == 429 : # Too many tries, must wait longer
        db.insist_on_update_one(payment, 'vipps_payments_in', 'wait_until', datetime.datetime.utcnow().timestamp() + (5 * 60))
    else :
        db.insist_on_update_one(payment, 'vipps_payments_in', 'wait_until', datetime.datetime.utcnow().timestamp() + (5 * 60))
        db.insist_on_insert_one('log_errors' , {
            'time' : datetime.datetime.utcnow() ,
            'service' : 'emailer' ,
            'function' : 'vipps_claim' ,
            'description' : 'Vipps API returned ' + str(response.status_code) + ' on POST ' + url ,
            'details' : response_json
        })

def vipps_claim_all(db) :
    vipps_it = db.insist_on_find('vipps_payments_in' , {
        '$and' : [
            {'status' : 'unpaid'} ,
            {'vipps_order_id' : {'$exists' : True}}
        ]
    })
    for vobj in mpcur(vipps_it):
        vipps_claim(vobj, db)