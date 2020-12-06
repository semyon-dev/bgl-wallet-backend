import os

import pybgl
import requests
from flask import Flask, jsonify, request

try:
    from dotenv import load_dotenv

    load_dotenv()
except:
    print(".env not from file")

app = Flask(__name__)
node_url = os.getenv('NODE_URL')


@app.route("/", methods=['GET'])
def welcome():
    return jsonify({"message": "ok"}), 200


@app.route("/wallet", methods=['POST'])
def create_wallet():
    entropy = pybgl.generate_entropy()
    mnemonic = pybgl.entropy_to_mnemonic(entropy)
    data = import_wallet(mnemonic)
    data["message"] = "ok"
    return jsonify(data), 201


@app.route("/wallet", methods=['PUT'])
def put_wallet():
    data = request.json
    reply = import_wallet(data["mnemonic"])
    reply["message"] = "ok"
    return jsonify(reply), 200


@app.route("/balance/<address>", methods=['GET'])
def get_balance(address):
    assert address == request.view_args['address']
    payload = {
        "method": "getbalance",
        "params": ["*", 0, True],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(node_url + '/wallet/' + address, json=payload).json()
    if response["error"]["code"] == -18:
        load_wallet(address)
    response = requests.post(node_url + '/wallet/' + address, json=payload).json()
    reply = {'amount': response["result"]}
    return jsonify(reply), 200


def load_wallet(address):
    payload = {
        "method": "loadwallet",
        "params": [address],
        "jsonrpc": "2.0",
        "id": "backend",
    }
    response = requests.post(node_url + '/wallet/' + address, json=payload).json()


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
    response = requests.post(node_url + '/wallet/' + address, json=payload).json()
    if response["error"]["code"] == -18:
        load_wallet(address)

    response = requests.post(node_url + '/wallet/' + address, json=payload).json()

    back_txid = "tx"

    for i in response["result"]:

        if i["address"] == address and i["category"] == "send":
            back_txid = i["txid"]
            response["result"].remove(i)

        i["amount"] = str(i["amount"])
        if "bip125-replaceable" in i:
            i.pop("bip125-replaceable")
        if "blockhash" in i:
            i.pop("blockhash")
        if "blockheight" in i:
            i.pop("blockheight")
        if "blocktime" in i:
            i.pop("blocktime")
        if "blockindex" in i:
            i.pop("blockindex")
        if "walletconflicts" in i:
            i.pop("walletconflicts")
        if "involvesWatchonly" in i:
            i.pop("involvesWatchonly")
        if "vout" in i:
            i.pop("vout")

    for i in response["result"]:
        if i["address"] == address and i["category"] == "receive" and i["txid"] == back_txid:
            response["result"].remove(i)

    return jsonify(list(reversed(response["result"]))), 200


@app.route("/transaction", methods=['POST'])
def create_transaction():
    is_small_utxos = request.args.get('is_small_utxos')

    # Create transaction
    frontend = request.json
    message = "unknown error"

    try:
        # Get list of unspent
        addresses = [frontend["address"]]
        payload = {
            "method": "listunspent",
            "params": [0, 999999999, addresses],
            "jsonrpc": "2.0",
            "id": "backend",
        }
        response = requests.post(node_url + '/wallet/' + frontend["address"], json=payload).json()
        if response["error"]["code"] == -18:
            load_wallet(frontend["address"])
        response = requests.post(node_url + '/wallet/' + frontend["address"], json=payload).json()
        if response["error"] is not None:
            message = response["error"]["message"]
            return jsonify({"message": message}), 400

        inputs = []
        outputs = []

        sum_amount = 0

        if is_small_utxos:
            response["result"] = sorted(response["result"], key=lambda k: k['amount'])
            # for i in response["result"]:
            #     print(i['amount'])

        for i in response["result"]:
            sum_amount += i["amount"]
            i_append = {"txid": i["txid"],
                        "vout": i["vout"]}
            inputs.append(i_append)
            if sum_amount >= float(format(frontend["amount"] + 0.01, '.8f')):
                break

        # print("sum_amount : ", sum_amount)
        # print("sum_amount - frontend amount: ", sum_amount - frontend["amount"])
        # print(sum_amount - frontend["amount"] - 0.01)
        back_output = {frontend["address"]: float(format(sum_amount - frontend["amount"] - 0.01, '.8f'))}
        to_output = {frontend["to_address"]: frontend["amount"]}

        outputs.append(back_output)
        outputs.append(to_output)

        payload = {
            "method": "createrawtransaction",
            "params": [inputs, outputs],
            "jsonrpc": "2.0",
            "id": "backend",
        }
        response = requests.post(node_url, json=payload).json()
        if response["error"] is not None:
            message = response["error"]["message"]
            return jsonify({"message": message}), 400

        hexstring = response["result"]
        private_key = [frontend["private_key"]]

        payload = {
            "method": "signrawtransactionwithkey",
            "params": [hexstring, private_key],
            "jsonrpc": "2.0",
            "id": "backend",
        }
        response = requests.post(node_url, json=payload).json()
        if response["error"] is not None:
            message = response["error"]["message"]
            return jsonify({"message": message}), 400

        hexstring = response["result"]["hex"]

        payload = {
            "method": "sendrawtransaction",
            "params": [hexstring],
            "jsonrpc": "2.0",
            "id": "backend",
        }
        response = requests.post(node_url, json=payload).json()
        if response["error"] is not None:
            message = response["error"]["message"]
            return jsonify({"message": message}), 400
    except:
        return jsonify({"message": message}), 400

    response["message"] = "transaction was sent successfully"
    return jsonify(response), 201


def import_wallet(mnemonic):
    seed = pybgl.mnemonic_to_seed(mnemonic)

    x_private_key = pybgl.create_master_xprivate_key(seed)

    private_key = pybgl.private_from_xprivate_key(x_private_key)

    public_key = pybgl.private_to_public_key(private_key)
    hex_public_key = pybgl.private_to_public_key(private_key, True, True)

    address = pybgl.public_key_to_address(public_key)

    try:
        payload = {
            "method": "createwallet",
            "params": [address, True],
            "jsonrpc": "2.0",
            "id": "backend",
        }
        response = requests.post(node_url, json=payload)
        if response.json()["error"]["code"] == -18:
            load_wallet(address)
        response = requests.post(node_url, json=payload)

        # Import public key to node
        url_request = node_url + '/wallet/' + address
        payload = {
            "method": "importpubkey",
            "params": [hex_public_key, address, True],
            "jsonrpc": "2.0",
            "id": "backend",
        }
        response = requests.post(url_request, json=payload)
        if response.json()["error"]["code"] == -18:
            load_wallet(address)
        response = requests.post(url_request, json=payload)
    except:
        pass

    load_wallet(address)

    reply = {"address": address, "private_key": private_key,
             "public_key": hex_public_key, "mnemonic": mnemonic}

    return reply


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
