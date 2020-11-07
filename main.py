import pybgl

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/wallet", methods=['POST'])
def create_wallet():
    a = pybgl.Address()
    # TODO делаем запрос на ноду - createwallet, затем importaddress
    reply = {'address': a.address, 'private_key': a.private_key.wif, "public_key": a.public_key}
    return jsonify(reply)


if __name__ == "__main__":
    app.run()
