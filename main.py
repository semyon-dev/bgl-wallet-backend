import os

import pybgl
import requests

from flask import Flask, jsonify, request

app = Flask(__name__)
URL = 'http://bgl_user:12345678@161.35.123.34:8332'


@app.route("/wallet", methods=['POST'])
def create_wallet():
    entropy = pybgl.generate_entropy()
    mnemonic = pybgl.entropy_to_mnemonic(entropy)
    seed = pybgl.mnemonic_to_seed(mnemonic)

    print("mnemonic before wallet: ", mnemonic)

    a = pybgl.Wallet()

    a.account_private_xkey = pybgl.create_master_xprivate_key(seed)
    a.account_public_xkey = pybgl.xprivate_to_xpublic_key(a.account_private_xkey)
    a.mnemonic = mnemonic
    print(a.__dict__)

    print("mnemonic AFTER wallet: ", mnemonic)

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

    back_txid = "tx"

    for i in response["result"]:

        if i["address"] == address and i["category"] == "send":
            back_txid = i["txid"]
            response["result"].remove(i)

        i["amount"] = str(i["amount"])
        i.pop("bip125-replaceable")
        i.pop("blockhash")
        i.pop("blockheight")
        i.pop("blocktime")
        i.pop("blockindex")
        i.pop("walletconflicts")
        i.pop("involvesWatchonly")
        i.pop("vout")

    for i in response["result"]:
        if i["address"] == address and i["category"] == "receive" and i["txid"] == back_txid:
            response["result"].remove(i)

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

    inputs = []
    outputs = []

    sum_amount = 0
    for i in response["result"]:
        sum_amount += i["amount"]
        i_append = {"txid": i["txid"],
                    "vout": i["vout"]}
        inputs.append(i_append)
        if sum_amount >= frontend["amount"]:
            break

    back_output = {frontend["address"]: sum_amount - frontend["amount"] - 0.014}
    to_output = {frontend["to_address"]: frontend["amount"]}

    outputs.append(back_output)
    outputs.append(to_output)

    payload = {
        "method": "createrawtransaction",
        "params": [inputs, outputs],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(URL, json=payload).json()
    print(response)

    hexstring = response["result"]
    print("hexstring == ", hexstring)
    private_key = [frontend["private_key"]]

    payload = {
        "method": "signrawtransactionwithkey",
        "params": [hexstring, private_key],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(URL, json=payload).json()
    print(response)

    hexstring = response["result"]["hex"]

    payload = {
        "method": "sendrawtransaction",
        "params": [hexstring],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(URL, json=payload).json()
    print(response)

    # t = pybgl.Transaction()
    # t["testnet"] = False
    # t["segwit"] = True
    #
    # count = 0
    # for i in response["result"]:
    #     sum_amount += i["amount"]
    #     t.add_input(i["txid"], i["vout"], 0xffffffff, b"", None, int(10 ** 8 * i["amount"]), i["scriptPubKey"],
    #                 i["address"])
    #     t.sign_input(count, frontend["private_key"], i["scriptPubKey"], None, pybgl.SIGHASH_ALL, i["address"],
    #                  int(10 ** 8 * i["amount"]))
    #     count += 1
    #     if sum_amount >= frontend["amount"]:
    #         break
    #
    # t.add_output(int(10 ** 8 * (sum_amount - frontend["amount"])) - 1000, frontend["address"])
    # t.add_output(int(10 ** 8 * frontend["amount"]), frontend["to_address"])
    #
    # payload = {
    #     "method": "signrawtransactionwithkey",
    #     "params": [t["rawTx"], frontend["private_key"]],
    #     "jsonrpc": "2.0",
    #     "id": "backend",
    # }
    #
    # response = requests.post(URL, json=payload).json()
    # print(response)
    #
    # # enc = t.encode()
    # print(t["txId"])
    # print(t["rawTx"])
    # print(t["hash"])
    #
    # payload = {
    #     "method": "sendrawtransaction",
    #     "params": [t["rawTx"]],
    #     "jsonrpc": "2.0",
    #     "id": "backend",
    # }
    # response = requests.post(URL, json=payload)
    # print("respones text: ", response.text)

    return jsonify(response)


if __name__ == "__main__":
    app.run()
