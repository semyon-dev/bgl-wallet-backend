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
    print(frontend)

    try:
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

        # print("sum_amount: ", sum_amount)
        # print("sum_amount - frontend[amount]: ", sum_amount - frontend["amount"])
        # print("sum_amount - frontend[amount]: ", sum_amount - frontend["amount"])
        # print("sum_amount - frontend[amount] - 0.014: ", sum_amount - frontend["amount"] - 0.014)
        # print("-----------")
        back_output = {frontend["address"]: float(format(sum_amount - frontend["amount"] - 0.014, '.8f'))}
        to_output = {frontend["to_address"]: frontend["amount"]}

        outputs.append(back_output)
        outputs.append(to_output)

        payload = {
            "method": "createrawtransaction",
            "params": [inputs, outputs],
            "jsonrpc": "2.0",
            "id": "backend",
        }
        print(payload)
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
    except:
        return jsonify({"message": "error"}), 400

    response["message"] = "ok"
    return jsonify(response), 201


if __name__ == "__main__":
    app.run()
