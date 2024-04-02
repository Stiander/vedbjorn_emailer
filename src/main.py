"""
    File : main.py
    Author : Stian Broen
    Date : 25.09.2022
    Description :

File responsible for the functionality which sends emails to users of Vedbjorn.no

"""

import base64 , os , sys , datetime , time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from libs.commonlib.db_insist import get_db, all_objectids_to_str
from libs.commonlib.pymongo_paginated_cursor import PaginatedCursor as mpcur
from libs.commonlib.graph_funcs import get_sellrequests_with_email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from vipps_ecom_claimer import vipps_claim_all
from threading import Thread
import asyncio

"""
We need a tiny server, otherwise Google Cloud will complain

Tiny server begin
"""
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
HOST=os.getenv("HOST", "0.0.0.0")
PORT= int(os.getenv("PORT",1234))
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def get_index(req : Request, res : Response):
    return {'hello' : 'Im the emailer server. I have only this function.'}
"""
Tiny server end
"""

SCOPES = ['https://mail.google.com/']
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE', 'vedbjorn-bb6b49fad2e3.json')
SUBJECT              = os.getenv('SUBJECT', 'noreply@vedbjorn.no')
GMAIL_VERSION        = os.getenv('GMAIL_VERSION', 'v1')
SERVICE_NAME         = os.getenv('SERVICE_NAME', 'gmail')

credentials = service_account.Credentials.from_service_account_file(
        filename=SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
        subject=SUBJECT
    )

"""
    Function : send_email

    Description :


"""
def send_email(content : MIMEMultipart) :
    if not content :
        print('WARNING : Invalid/missing argument to send_email')
        return None

    service = build(SERVICE_NAME, GMAIL_VERSION, credentials=credentials)
    encoded_message = base64.urlsafe_b64encode(content.as_bytes()).decode()
    create_message = {'raw': encoded_message}
    send_message = service.users().messages().send(userId="me", body=create_message).execute()
    return send_message

"""
    Function : make_delivery_content

    Description :


"""
def make_delivery_content(notification : dict, db) :
    if not 'text' in notification or notification.get('text' , '') == '' :
        title = 'Vedbjørn : Ved er på vei til deg'
        text = 'En sjåfør er på vei til deg for å levere ved. Du vil få en ny epost med bilde av leveransen når den har blitt levert. '
        message = MIMEMultipart(_subtype='related')
        message["subject"] = title
        message["from"] = SUBJECT
        message["to"] = notification['email']
        try:
            name = str(notification.get('email', '')).split('@')[0]
            if not name:
                name = notification.get('email', '')
            if name:
                name = str(name[0]).upper() + name[1:len(name)]
        except Exception:
            name = ''

        html = \
            "<html>" + \
            "<head>" + \
            "   <meta charset=\"utf-8\" />" + \
            "   <style> " + \
            "       body { " + \
            "            font-family: Roboto; " + \
            "}" + \
            "       h3 { " + \
            "            color: #4d290c; " + \
            "            font-size : 30px; " + \
            "       }" + \
            "       h4 { " + \
            "            color: #6e390e; " + \
            "            font-size : 20px; " + \
            "       }" + \
            "   </style>" + \
            "</head>" + \
            "<body>" + \
                "<h3>Hei " + name + "<br></h3>" + \
                "<h4>" + text + "</h4>" + \
                "<h4>Vennligst logg inn på profilen din for nærmere informasjon.</h4>" + \
                "</br>" + \
                "</br>" + \
                "<h4>Vennlig hilsen</h4>" + \
                "<h4>Stian Broen (CEO Vedbjørn AS)</h4>" + \
                "</br>" + \
                "<img src=\"cid:myimage\" />" + \
                "</br>" + \
                "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
                "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
                "</br>" + \
                "<p>Vedbjørn AS</p>" + \
                "<p>Org. Nr. : 929350790</p>" + \
                "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
            "</body>" + \
            "</html>"
        part1 = MIMEText(html, _subtype="html")
        message.attach(part1)

        img_data = open('bear_less_padded.png', 'rb').read()
        img = MIMEImage(img_data, 'jpeg')
        img.add_header('Content-Id', '<myimage>')
        img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
        message.attach(img)
        return title, message

    else :
        title = 'Vedbjørn : Ved har blitt levert til deg'
        text = notification['text']
        message = MIMEMultipart(_subtype='related')
        message["subject"] = title
        message["from"] = SUBJECT
        message["to"] = notification['email']
        try:
            name = str(notification.get('email', '')).split('@')[0]
            if not name:
                name = notification.get('email', '')
            if name:
                name = str(name[0]).upper() + name[1:len(name)]
        except Exception:
            name = ''

        html = \
            "<html>" + \
                "<head>" + \
                "   <meta charset=\"utf-8\" />" + \
                "   <style> " + \
                "       body { " + \
                "            font-family: Roboto; " + \
                "       }" + \
                "       h3 { " + \
                "            color: #4d290c; " + \
                "            font-size : 30px; " + \
                "       }" + \
                "       h4 { " + \
                "            color: #6e390e; " + \
                "            font-size : 20px; " + \
                "       }" + \
                "   </style>" + \
                "</head>" + \
                "<body>" + \
                    "<h3>Hei " + name + "<br></h3>" + \
                    "<h4>" + text + "</h4>" + \
                    "<img src=\"cid:deliveryimage\" />" + \
                    "</br>" + \
                    "</br>" + \
                    "<h4>Vennlig hilsen</h4>" + \
                    "<h4>Stian Broen (CEO Vedbjørn AS)</h4>" + \
                    "</br>" + \
                    "<img src=\"cid:myimage\" />" + \
                    "<h4>Ser det greit ut? Logg inn på din Vedbjørn-profil for å godkjenne.</h4>" + \
                    "</br>" + \
                    "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
                    "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
                    "</br>" + \
                    "<p>Vedbjørn AS</p>" + \
                    "<p>Org. Nr. : 929350790</p>" + \
                    "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
                "</body>" + \
            "</html>"
        part1 = MIMEText(html, _subtype="html")
        message.attach(part1)

        try:
            deliveryObj = db.insist_on_find_one(notification['ref_collection'], notification['ref_id'])
            delivery_img_data = db.insist_on_get_filecontent_id(deliveryObj['meta']['file'])
            delivery_img = MIMEImage(delivery_img_data, 'jpeg')
            delivery_img.add_header('Content-Id', '<deliveryimage>')
            delivery_img.add_header("Content-Disposition", "inline", filename="bilde_av_ved")
            message.attach(delivery_img)
        except Exception as e :
            print('WARNING : Could not attach image to email : \n' , e)

        logo_img_data = open('bear_less_padded.png', 'rb').read()
        logo_img = MIMEImage(logo_img_data, 'jpeg')
        logo_img.add_header('Content-Id', '<myimage>')
        logo_img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
        message.attach(logo_img)
        return title, message

"""
    Function : make_pickup_content

    Description :


"""
def make_pickup_content(notification : dict, db) :
    ongoing_route = db.insist_on_find_one('ongoing_routes', notification.get('ongoing_routes', None))
    sellreq_graph = get_sellrequests_with_email(notification.get('email' , ''))
    sellreq = sellreq_graph[0][0]
    sellreq_name = sellreq['name']
    clients : str = ''
    for sell in ongoing_route.get('deals' , {}).get(sellreq_name, {}).get('sells' , []) :
        if clients != '' :
            clients = clients + ' , '
        clients = clients + sell['name'] + ' (' + str(sell['current_requirement']) + ' sekker) '
    driver_name = ongoing_route['driveRequestName']

    message = MIMEMultipart(_subtype='related')
    title = "Vedbjørn : Sjåfør på vei til deg for å hente ved"
    message["subject"] = title
    message["from"] = SUBJECT
    message["to"] = notification['email']
    try:
        name = str(notification.get('email', '')).split('@')[0]
        if not name:
            name = notification.get('email', '')
        if name:
            name = str(name[0]).upper() + name[1:len(name)]
    except Exception:
        name = ''

    html = \
        "<html>" + \
        "<head>" + \
        "   <meta charset=\"utf-8\" />" + \
        "   <style> " + \
        "       body { " + \
        "            font-family: Roboto; " + \
        "}" + \
        "       h3 { " + \
        "            color: #4d290c; " + \
        "            font-size : 30px; " + \
        "       }" + \
        "       h4 { " + \
        "            color: #6e390e; " + \
        "            font-size : 20px; " + \
        "       }" + \
        "   </style>" + \
        "</head>" + \
        "<body>" + \
            "<h3>Hei " + name + "<br></h3>" + \
            "<h4>" + "En sjåfør fra Vedbjørn er på vei til deg for å hente ved." + "</h4>" + \
            "<h4>" + "Sjåfør : " + driver_name + "</h4>" + \
            "<h4>" + "Antall sekker : " + str(notification['amount']) + "</h4>" + \
            "<h4>" + "Kunder : " + clients + "</h4>" + \
            "<h4>For å spare tid burde du gjøre leveransen klar for henting. Vennligst logg inn på profilen din for nærmere informasjon.</h4>" + \
            "</br>" + \
            "</br>" + \
            "<h4>Vennlig hilsen</h4>" + \
            "<h4>Stian Broen (CEO Vedbjørn AS)</h4>" + \
            "</br>" + \
            "<img src=\"cid:myimage\" />" + \
            "</br>" + \
            "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
            "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
            "</br>" + \
            "<p>Vedbjørn AS</p>" + \
            "<p>Org. Nr. : 929350790</p>" + \
            "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
        "</body>" + \
        "</html>"
    part1 = MIMEText(html, _subtype="html")
    message.attach(part1)

    img_data = open('bear_less_padded.png', 'rb').read()
    img = MIMEImage(img_data, 'jpeg')
    img.add_header('Content-Id', '<myimage>')
    img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
    message.attach(img)

    return title , message

"""
    Function : make_accepted_content

    Description :


"""
def make_accepted_content(notification : dict, db) :

    title = 'Vedbjørn : Leveranse godkjent'
    text = notification['text']

    message = MIMEMultipart(_subtype='related')
    message["subject"] = title
    message["from"] = SUBJECT
    message["to"] = notification['email']
    try:
        name = str(notification.get('email', '')).split('@')[0]
        if not name:
            name = notification.get('email', '')
        if name:
            name = str(name[0]).upper() + name[1:len(name)]
    except Exception:
        name = ''

    html = \
        "<html>" + \
        "<head>" + \
        "   <meta charset=\"utf-8\" />" + \
        "   <style> " + \
        "       body { " + \
        "            font-family: Roboto; " + \
        "}" + \
        "       h3 { " + \
        "            color: #4d290c; " + \
        "            font-size : 30px; " + \
        "       }" + \
        "       h4 { " + \
        "            color: #6e390e; " + \
        "            font-size : 20px; " + \
        "       }" + \
        "   </style>" + \
        "</head>" + \
        "<body>" + \
            "<h3>Hei " + name + "<br></h3>" + \
            "<h4>" + text + "</h4>" + \
            "<h4>Vennligst logg inn på profilen din for nærmere informasjon.</h4>" + \
            "</br>" + \
            "</br>" + \
            "<h4>Vennlig hilsen</h4>" + \
            "<h4>Stian Broen (CEO Vedbjørn AS)</h4>" + \
            "</br>" + \
            "<img src=\"cid:myimage\" />" + \
            "</br>" + \
            "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
            "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
            "</br>" + \
            "<p>Vedbjørn AS</p>" + \
            "<p>Org. Nr. : 929350790</p>" + \
            "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
        "</body>" + \
        "</html>"
    part1 = MIMEText(html, _subtype="html")
    message.attach(part1)

    img_data = open('bear_less_padded.png', 'rb').read()
    img = MIMEImage(img_data, 'jpeg')
    img.add_header('Content-Id', '<myimage>')
    img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
    message.attach(img)

    return title, message

"""
    Function : make_new_assignment_content

    Description :


"""
def make_new_assignment_content(notification : dict, db) :
    message = MIMEMultipart(_subtype='related')
    message["subject"] = "Vedbjørn : Kjøreoppdrag"
    message["from"] = SUBJECT
    message["to"] = notification['email']
    try :
        name = str(notification.get('email', '')).split('@')[0]
        if not name :
            name = notification.get('email', '')
        if name :
            name = str(name[0]).upper() + name[1:len(name)]
    except Exception:
        name = ''

    html = \
        "<html>" + \
        "<head>" + \
        "   <meta charset=\"utf-8\" />" + \
        "   <style> " + \
        "       body { " + \
        "            font-family: Roboto; " + \
                "}" + \
        "       h3 { " + \
        "            color: #4d290c; " + \
        "            font-size : 30px; " + \
        "       }" + \
        "       h4 { " + \
        "            color: #6e390e; " + \
        "            font-size : 20px; " + \
        "       }" + \
        "   </style>" + \
        "</head>" + \
            "<body>" + \
                "<h3>Hei " + name + "<br></h3>" + \
                "<h4>" + notification['text'] + "</h4>" + \
                "<h4>Vennligst logg inn på profilen din for nærmere informasjon.</h4>" + \
                "</br>" + \
                "</br>" + \
                "<h4>Vennlig hilsen</h4>" + \
                "<h4>Stian Broen (CEO Vedbjørn AS)</h4>" + \
                "</br>" + \
                "<img src=\"cid:myimage\" />" + \
                "</br>" + \
                "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
                "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
                "</br>" + \
                "<p>Vedbjørn AS</p>" + \
                "<p>Org. Nr. : 929350790</p>" + \
                "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
        "</body>" + \
        "</html>"
    part1 = MIMEText(html, _subtype = "html")
    message.attach(part1)

    img_data  = open('bear_less_padded.png', 'rb').read()
    img = MIMEImage(img_data, 'jpeg')
    img.add_header('Content-Id', '<myimage>')
    img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
    message.attach(img)

    return 'Vedbjørn : Nytt oppdrag tilgjengelig' , message


def make_email_BatchSellRequest(notification : dict, db) :
    message = MIMEMultipart(_subtype='related')
    message["subject"] = "Henvendelse angående salg av ved-lass"
    message["from"] = SUBJECT
    message["to"] = notification['email']
    try:
        name = str(notification.get('email', '')).split('@')[0]
        if not name:
            name = notification.get('email', '')
        if name:
            name = str(name[0]).upper() + name[1:len(name)]
    except Exception:
        name = ''

    html = \
        "<html>" + \
        "<head>" + \
        "   <meta charset=\"utf-8\" />" + \
        "   <style> " + \
        "       body { " + \
        "            font-family: Roboto; " + \
        "}" + \
        "       h3 { " + \
        "            color: #4d290c; " + \
        "            font-size : 30px; " + \
        "       }" + \
        "       h4 { " + \
        "            color: #6e390e; " + \
        "            font-size : 20px; " + \
        "       }" + \
        "   </style>" + \
        "</head>" + \
        "<body>" + \
        "<h3>Hei " + name + "<br></h3>" + \
        "<h4>" + notification['text'] + "</h4>" + \
        "</br>" + \
        "</br>" + \
        "<h4>Vennlig hilsen</h4>" + \
        "<h4>Stian Broen (CEO Vedbjørn AS)</h4>" + \
        "</br>" + \
        "<img src=\"cid:myimage\" />" + \
        "</br>" + \
        "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
        "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
        "</br>" + \
        "<p>Vedbjørn AS</p>" + \
        "<p>Org. Nr. : 929350790</p>" + \
        "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
        "</body>" + \
        "</html>"
    part1 = MIMEText(html, _subtype="html")
    message.attach(part1)

    img_data = open('bear_less_padded.png', 'rb').read()
    img = MIMEImage(img_data, 'jpeg')
    img.add_header('Content-Id', '<myimage>')
    img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
    message.attach(img)

    return 'Henvendelse angående salg av ved-lass', message

def make_email_IncomingInvoice(notification : dict, db, is_copy : bool = False) :

    if not is_copy :
        _subject = "Regning - betales"
        _text = 'Vedlagt er en regning som skal betales ASAP, en kunde venter.'
        _message_to = notification['email']
        try:
            name = str(notification.get('email', '')).split('@')[0]
            if not name:
                name = notification.get('email', '')
            if name:
                name = str(name[0]).upper() + name[1:len(name)]
        except Exception:
            name = ''
    else:
        _subject = "KOPI - Regning"
        _text = 'Dette er kun en kopi av regningen som ble sendt til Vedbjørn, på vegne din virksomhet. Regningen blir betalt av Vedbjørn til din konto.'
        _message_to = notification['email_copy']
        try:
            name = str(notification.get('email_copy', '')).split('@')[0]
            if not name:
                name = notification.get('email_copy', '')
            if name:
                name = str(name[0]).upper() + name[1:len(name)]
        except Exception:
            name = ''

    message = MIMEMultipart(_subtype='related')
    message["subject"] = _subject
    message["from"] = SUBJECT
    message["to"] = _message_to

    html = \
        "<html>" + \
        "<head>" + \
        "   <meta charset=\"utf-8\" />" + \
        "   <style> " + \
        "       body { " + \
        "            font-family: Roboto; " + \
        "}" + \
        "       h3 { " + \
        "            color: #4d290c; " + \
        "            font-size : 30px; " + \
        "       }" + \
        "       h4 { " + \
        "            color: #6e390e; " + \
        "            font-size : 20px; " + \
        "       }" + \
        "   </style>" + \
        "</head>" + \
        "<body>" + \
        "<h3>Hei " + name + "<br></h3>" + \
        "<h4>" + _text + "</h4>" + \
        "</br>" + \
        "</br>" + \
        "<h4>Vennlig hilsen</h4>" + \
        "<h4>Stian Broen (CEO Vedbjørn AS)</h4>" + \
        "</br>" + \
        "<img src=\"cid:myimage\" />" + \
        "</br>" + \
        "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
        "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
        "</br>" + \
        "<p>Vedbjørn AS</p>" + \
        "<p>Org. Nr. : 929350790</p>" + \
        "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
        "</body>" + \
        "</html>"
    part1 = MIMEText(html, _subtype="html")
    message.attach(part1)

    img_data = open('bear_less_padded.png', 'rb').read()
    img = MIMEImage(img_data, 'jpeg')
    img.add_header('Content-Id', '<myimage>')
    img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
    message.attach(img)

    invoice = db.insist_on_get_filecontent_id(notification['invoice_id'])
    invoice_att = MIMEApplication(invoice, _subtype="pdf")
    invoice_att.add_header('Content-Disposition', 'attachment', filename='Regning_Til_Vedbjørn.pdf')
    message.attach(invoice_att)

    return _subject, message

def make_verify_email_content(notification : dict, db) :
    message = MIMEMultipart(_subtype='related')
    message["subject"] = "Vedbjørn : Bekreft epost"
    message["from"] = SUBJECT
    message["to"] = notification['email']
    try:
        name = str(notification.get('email', '')).split('@')[0]
        if not name:
            name = notification.get('email', '')
        if name:
            name = str(name[0]).upper() + name[1:len(name)]
    except Exception:
        name = ''

    html = \
        "<html>" + \
        "<head>" + \
        "   <meta charset=\"utf-8\" />" + \
        "   <style> " + \
        "       body { " + \
        "            font-family: Roboto; " + \
        "}" + \
        "       h3 { " + \
        "            color: #4d290c; " + \
        "            font-size : 30px; " + \
        "       }" + \
        "       h4 { " + \
        "            color: #6e390e; " + \
        "            font-size : 20px; " + \
        "       }" + \
        "   </style>" + \
        "</head>" + \
        "<body>" + \
        "<h3>Hei " + name + "<br></h3>" + \
        "<h4>" + notification['text'] + "</h4>" + \
        "</br>" + \
        "</br>" + \
        "<h4>Vennlig hilsen</h4>" + \
        "<h4>Stian Broen (CEO Vedbjørn AS)</h4>" + \
        "</br>" + \
        "<img src=\"cid:myimage\" />" + \
        "</br>" + \
        "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
        "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
        "</br>" + \
        "<p>Vedbjørn AS</p>" + \
        "<p>Org. Nr. : 929350790</p>" + \
        "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
        "</body>" + \
        "</html>"
    part1 = MIMEText(html, _subtype="html")
    message.attach(part1)
    img_data = open('bear_less_padded.png', 'rb').read()
    img = MIMEImage(img_data, 'jpeg')
    img.add_header('Content-Id', '<myimage>')
    img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
    message.attach(img)
    return 'Vedbjørn : Bekreft epost', message

def make_email_verified_content(notification : dict, db) :
    message = MIMEMultipart(_subtype='related')
    message["subject"] = "Vedbjørn : Epost bekreftet!"
    message["from"] = SUBJECT
    message["to"] = notification['email']
    try:
        name = str(notification.get('email', '')).split('@')[0]
        if not name:
            name = notification.get('email', '')
        if name:
            name = str(name[0]).upper() + name[1:len(name)]
    except Exception:
        name = ''

    html = \
        "<html>" + \
        "<head>" + \
        "   <meta charset=\"utf-8\" />" + \
        "   <style> " + \
        "       body { " + \
        "            font-family: Roboto; " + \
        "}" + \
        "       h3 { " + \
        "            color: #4d290c; " + \
        "            font-size : 30px; " + \
        "       }" + \
        "       h4 { " + \
        "            color: #6e390e; " + \
        "            font-size : 20px; " + \
        "       }" + \
        "   </style>" + \
        "</head>" + \
        "<body>" + \
        "<h3>Hei " + name + "<br></h3>" + \
        "<h4>" + notification['text'] + "</h4>" + \
        "</br>" + \
        "</br>" + \
        "<h4>Vennlig hilsen</h4>" + \
        "<h4>Stian Broen (CEO Vedbjørn AS)</h4>" + \
        "</br>" + \
        "<img src=\"cid:myimage\" />" + \
        "</br>" + \
        "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
        "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
        "</br>" + \
        "<p>Vedbjørn AS</p>" + \
        "<p>Org. Nr. : 929350790</p>" + \
        "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
        "</body>" + \
        "</html>"
    part1 = MIMEText(html, _subtype="html")
    message.attach(part1)
    img_data = open('bear_less_padded.png', 'rb').read()
    img = MIMEImage(img_data, 'jpeg')
    img.add_header('Content-Id', '<myimage>')
    img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
    message.attach(img)
    return 'Vedbjørn : Epost bekreftet!', message

"""

    make_mass_content

    Description :


"""
def make_mass_content(title : str, text : str, recipient : str) :
    if not title or not text or not recipient :
        return None, None
    message = MIMEMultipart(_subtype='related')
    message["subject"] = title
    message["from"] = SUBJECT
    message["to"] = recipient

    html = \
        "<html>" + \
        "<head>" + \
        "   <meta charset=\"utf-8\" />" + \
        "   <style> " + \
        "       body { " + \
        "            font-family: Roboto; " + \
        "}" + \
        "       h3 { " + \
        "            color: #4d290c; " + \
        "            font-size : 30px; " + \
        "       }" + \
        "       h4 { " + \
        "            color: #6e390e; " + \
        "            font-size : 20px; " + \
        "       }" + \
        "   </style>" + \
        "</head>" + \
        "<body>" + \
            "<h3>Hei<br></h3>" + \
            "<h4>" + text + "</h4>" + \
            "</br>" + \
            "</br>" + \
            "<h4>Vennlig hilsen</h4>" + \
            "<h4>Oss i Vedbjørn</h4>" + \
            "</br>" + \
            "<img src=\"cid:myimage\" />" + \
            "</br>" + \
            "<p>MERK : Denne eposten er sendt ut automatisk fra et dataprogram og kan ikke besvares.</p>" + \
            "<p>Eposter fra Vedbjørn vil aldri inneholde linker eller be om personlige opplysninger fra deg.</p>" + \
            "</br>" + \
            "<p>Vedbjørn AS</p>" + \
            "<p>Org. Nr. : 929350790</p>" + \
            "<p>Forretningsadresse : Adalsveien 1B, 3185 Skoppum</p>" + \
        "</body>" + \
        "</html>"
    part1 = MIMEText(html, _subtype="html")
    message.attach(part1)
    img_data = open('bear_less_padded.png', 'rb').read()
    img = MIMEImage(img_data, 'jpeg')
    img.add_header('Content-Id', '<myimage>')
    img.add_header("Content-Disposition", "inline", filename="vedbjorn_logo")
    message.attach(img)
    return title, message

"""

    handle_mass_emails

    Description :


"""
def handle_mass_emails(db) :
    order_it = db.insist_on_find('email_orders', {
        'status' : 'ordered'
    })
    for order in mpcur(order_it):
        sent_statuses: dict = {}
        num_failed : int = 0
        num_ok : int = 0
        for recipient in order['recipients'] :
            subject, content = make_mass_content(order['title'], order['text'], recipient)
            if content:
                try:
                    if '@fake.com' in recipient:
                        sent_statuses[recipient] = 'Its a fake user! We did not actually send the email, but we pretend like we did'
                    else:
                        sent_statuses[recipient] = send_email(content)
                    num_ok = num_ok + 1
                except Exception as e:
                    sent_statuses[recipient] = str(e)
                    num_failed = num_failed + 1
        db.insist_on_update_one(order, 'email_orders', 'status', 'completed')
        db.insist_on_update_one(order, 'email_orders', 'num_ok', num_ok)
        db.insist_on_update_one(order, 'email_orders', 'num_failed', num_failed)
        db.insist_on_update_one(order, 'email_orders', 'emails_sent', sent_statuses)

"""

    handle_emails

    Description :


"""
def handle_emails(db) :
    notification_it = db.insist_on_find('notifications', {
        '$or': [
            {'status': 'new'},
            {'status': 'requested'},
            {'status': 'failed'}
        ]
    })
    for notification in mpcur(notification_it):
        contentType = notification.get('contentType', '')

        on_copy_content = None
        on_copy_subject = None
        email_copy = notification.get('email_copy', '')

        if contentType == 'delivery':
            subject, content = make_delivery_content(notification, db)
        elif contentType == 'pickup':
            subject, content = make_pickup_content(notification, db)
        elif contentType == 'accepted':
            subject, content = make_accepted_content(notification, db)
        elif contentType == 'new assignment':
            subject, content = make_new_assignment_content(notification, db)
        elif contentType == 'verify email':
            subject, content = make_verify_email_content(notification, db)
        elif contentType == 'email verified':
            subject, content = make_email_verified_content(notification, db)
        elif contentType == 'BatchSellRequest':
            subject, content = make_email_BatchSellRequest(notification, db)
        elif contentType == 'IncomingInvoice':
            subject, content = make_email_IncomingInvoice(notification, db)
            if email_copy :
                on_copy_subject , on_copy_content = make_email_IncomingInvoice(notification, db, True)
        else:
            continue

        if content:
            try:
                if '@fake.com' in notification.get('email', ''):
                    send_message = {
                        'ok': 'Its a fake user! We did not actually send the email, but we pretend like we did'
                    }
                else:
                    send_message = send_email(content)
            except Exception as e:
                send_message = None
                db.insist_on_update_one(notification, 'notifications', 'status', 'failed')
                db.insist_on_update_one(notification, 'notifications', 'handled_time', datetime.datetime.utcnow())
                db.insist_on_update_one(notification, 'notifications', 'send_return', str(e))
                print('FAILED : ' + contentType + ' email was not sent to ' + notification.get('email', '') + ', BECAUSE :\n' , e)
            if send_message:
                db.insist_on_update_one(notification, 'notifications', 'status', 'sent')
                db.insist_on_update_one(notification, 'notifications', 'handled_time', datetime.datetime.utcnow())
                db.insist_on_update_one(notification, 'notifications', 'send_return', all_objectids_to_str(send_message))
                print('SUCCESS : ' + contentType + ' email sent to ' + notification.get('email', ''))
        else:
            db.insist_on_update_one(notification, 'notifications', 'handled_time', datetime.datetime.utcnow())
            db.insist_on_update_one(notification, 'notifications', 'status', 'failed')
            db.insist_on_update_one(notification, 'notifications', 'send_return', 'no email-content was generated')

        if on_copy_content :
            try:
                if '@fake.com' in notification.get('email_copy', ''):
                    send_message = {
                        'ok': 'Its a fake user! We did not actually send the email_copy, but we pretend like we did'
                    }
                else:
                    send_message = send_email(on_copy_content)
            except Exception as e:
                send_message = None
                db.insist_on_update_one(notification, 'notifications', 'copy_status', 'failed')
                db.insist_on_update_one(notification, 'notifications', 'copy_handled_time', datetime.datetime.utcnow())
                db.insist_on_update_one(notification, 'notifications', 'copy_send_return', str(e))
                print('FAILED : ' + contentType + ' copy_email was not sent to ' + notification.get('email_copy', '') + ', BECAUSE :\n' , e)
            if send_message:
                db.insist_on_update_one(notification, 'notifications', 'copy_status', 'sent')
                db.insist_on_update_one(notification, 'notifications', 'copy_handled_time', datetime.datetime.utcnow())
                db.insist_on_update_one(notification, 'notifications', 'copy_send_return', all_objectids_to_str(send_message))
                print('SUCCESS : ' + contentType + ' copy_email sent to ' + notification.get('email_copy', ''))


def emailer_loop(asyncLoop) :
    asyncio.set_event_loop(asyncLoop)
    print('Making DB object')
    db = get_db()
    print('DB object created')
    while True :
        handle_mass_emails(db)
        vipps_claim_all(db)
        handle_emails(db)
        time.sleep(10)

if __name__ == '__main__':
    print('###############################')
    print('#')
    print('#       Service EMAILER - BEGINS')
    print('#')
    print('#\tTime : ' , datetime.datetime.utcnow())
    print('#')
    print('#')

    """
    Start the thread which actually does something
    """
    asyncLoop = asyncio.new_event_loop()
    _thread = Thread(target=emailer_loop, args=(asyncLoop,))
    _thread.start()

    """
    Start the tiny server.
    """
    uvicorn.run('main:app', host=HOST, port=PORT)



