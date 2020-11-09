import unittest
import os, sys
parentPath = os.path.abspath("..")
if parentPath not in sys.path:
    sys.path.insert(0, parentPath)
from pybgl import *
from binascii import unhexlify
from pybgl import address_to_hash  as address2hash160

class CreateTransactionTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\nTesting create transaction:\n")

    def test_create_tx(self):
        rtx = "0200000000010151ab0ce41d17c55597011e798f6e634704cfd22d0debf0c4e0ee9c2c9cbb5f8e0000000000ffffffff0118ddf" \
              "50500000000160014e0a5424502ad701c79ed7cb53f7ceabe9fd3b1e30247304402207b07de070579ec1c481ec858f339ea02b8" \
              "269f554e70130e6f94f0dfe84dc45402202bfab5d7877ddcf57c7afd5dead1d708940382231007c166f83c31247d71c97d01210" \
              "384fcc40094f0bdf493483dd5db6c7985d10122ef599e59be7436b59ca50de574c37e0000";

        tx = Transaction(version=2, lock_time= 32451)
        tx.add_input("8e5fbb9c2c9ceee0c4f0eb0d2dd2cf0447636e8f791e019755c5171de40cab51",
                     0, address="bgl1qrujz90dzsd5cle8yy7lm546saregcjmzt4g4kl")
        tx.add_output(99999000, "bgl1quzj5y3gz44cpc70d0j6n7l82h60a8v0rwf0pjq")
        tx.sign_input(0, private_key="KyfrGSgiv9rSiXiXBhJnDyZz8DU8VJdKYcbMGPginJUhrx7VSvAY",
                         sighash_type=SIGHASH_ALL,
                         amount=100000000)
        self.assertEqual(tx.serialize(), rtx)


