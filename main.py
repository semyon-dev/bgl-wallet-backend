import os

import pybgl
import requests

from flask import Flask, jsonify, request

app = Flask(__name__)
URL = 'http://bgl_user:12345678@161.35.123.34:8332'


@app.route("/wallet", methods=['POST'])
def create_wallet():
    a = pybgl.Address()

    # Create wallet request

    payload = {
        "method": "createwallet",
        "params": [a.address, True],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(URL, json=payload)
    print(response.text)

    # Import public key to node
    url_request = URL + '/wallet/' + a.address
    payload = {
        "method": "importpubkey",
        "params": [a.public_key.hex, a.address, True],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(url_request, json=payload)
    print(response.text)

    reply = {'address': a.address, 'private_key': a.private_key.wif, "public_key": a.public_key.hex}
    return jsonify(reply)


@app.route("/balance/<address>", methods=['GET'])
def get_balance(address):
    assert address == request.view_args['address']

    payload = {
        "method": "getbalance",
        "params": ["*", 0, True],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(URL + '/wallet/' + address, json=payload).json()
    print(response)

    reply = {'amount': response["result"]}
    return jsonify(reply)


@app.route("/history", methods=['GET'])
def get_history():
    page = request.args.get('page')
    address = request.args.get('address')

    skip = int(page) * 25

    payload = {
        "method": "listtransactions",
        "params": ["*", 25, skip, True],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(URL + '/wallet/' + address, json=payload).json()

    for i in response["result"]:
        i["amount"] = str(i["amount"])
        i.pop("bip125-replaceable")
        i.pop("blockhash")
        i.pop("blockheight")
        i.pop("blocktime")
        i.pop("blockindex")
        i.pop("walletconflicts")
        i.pop("involvesWatchonly")
        i.pop("vout")

    return jsonify(response["result"])


@app.route("/transaction", methods=['POST'])
def create_transaction():
    # Create transaction
    frontend = request.json

    # Get list of unspent
    addresses = [frontend["address"]]
    payload = {
        "method": "listunspent",
        "params": [0, 999999999, addresses],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(URL + '/wallet/' + frontend["address"], json=payload).json()
    print(response)

    sum_amount = 0

    t = pybgl.Transaction()
    count = 0
    for i in response["result"]:
        sum_amount += i["amount"]
        t.add_input(i["txid"], i["vout"])
        t.sign_input(count, frontend["private_key"], i["scriptPubKey"], None, pybgl.SIGHASH_ALL, i["address"],
                     i["amount"])
        count += 1
        if sum_amount >= frontend["amount"]:
            break

    t.add_output(sum_amount - frontend["amount"], frontend["address"])
    t.add_output(sum_amount, frontend["to_address"])

    t.values()
    print(t["txid"])

    return jsonify(t)


if __name__ == "__main__":
    app.run()
