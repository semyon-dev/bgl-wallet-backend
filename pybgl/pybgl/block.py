from struct import unpack, pack
from io import BytesIO
from pybgl.functions.block import bits_to_target, target_to_difficulty, merkle_root_double_sha256
from pybgl.functions.block import merkle_root, merkle_branches, merkle_root_from_branches
from pybgl.functions.hash import sha3_256, double_sha256
from pybgl.functions.tools import var_int_to_int, read_var_int, var_int_len, rh2s, reverse_hash, s2rh, s2rh_step4
from pybgl.functions.tools import bytes_from_hex, int_to_var_int
from pybgl.transaction import Transaction
import math

class Block(dict):
    def __init__(self, raw_block=None, format="decoded", version=536870912, testnet=False, keep_raw_tx=False):
        if format not in ("decoded", "raw"):
            raise ValueError("tx_format error, raw or decoded allowed")
        self["format"] = format
        self["testnet"] = testnet
        self["header"] = None
        self["hash"] = None
        self["version"] = version
        self["versionHex"] = pack(">L", version).hex()
        self["previousBlockHash"] = None
        self["merkleRoot"] = None
        self["tx"] = dict()
        self["time"] = None
        self["bits"] = None
        self["nonce"] = None
        self["weight"] = 0
        self["size"] = 80
        self["strippedSize"] = 80
        self["amount"] = 0
        self["height"] = None
        self["difficulty"] = None
        self["targetDifficulty"] = None
        self["target"] = None
        if raw_block is None:
            return
        self["size"] = len(raw_block) if isinstance(raw_block, bytes) else int(len(raw_block)/2)
        s = self.get_stream(raw_block)
        self["format"] = "raw"
        self["version"] = unpack("<L", s.read(4))[0]
        self["versionHex"] = pack(">L", self["version"]).hex()
        self["previousBlockHash"] = s.read(32)
        self["merkleRoot"] = s.read(32)
        self["time"] = unpack("<L", s.read(4))[0]
        self["bits"] = s.read(4)

        self["target"] = bits_to_target(unpack("<L", self["bits"])[0])
        self["targetDifficulty"] = target_to_difficulty(self["target"])
        self["target"] = self["target"].to_bytes(32, byteorder="little")
        self["nonce"] = unpack("<L", s.read(4))[0]
        s.seek(-80, 1)
        self["header"] = s.read(80)
        self["hash"] = sha3_256(self["header"])
        block_target = int.from_bytes(self["hash"], byteorder="little")
        self["difficulty"] = target_to_difficulty(block_target)
        tx_count = var_int_to_int(read_var_int(s))
        self["tx"] = dict()
        for i in range(tx_count):
            self["tx"][i] = Transaction(s, format="raw", keep_raw_tx=keep_raw_tx)
            self["amount"] += self["tx"][i]["amount"]
            self["strippedSize"] += self["tx"][i]["bSize"]
        self["strippedSize"] += var_int_len(tx_count)
        self["weight"] = self["strippedSize"] * 3 + self["size"]
        if format == "decoded":
            self.decode(testnet=testnet)

    def decode(self, testnet=None):
        self["format"] = "decoded"
        if testnet is not None:
            self["testnet"] = testnet
        if isinstance(self["hash"], bytes):
            self["hash"] = rh2s(self["hash"])
        if isinstance(self["target"], bytes):
            self["target"] = rh2s(self["target"])
        if isinstance(self["previousBlockHash"], bytes):
            self["previousBlockHash"] = rh2s(self["previousBlockHash"])
        if "nextBlockHash" in self:
            if isinstance(self["nextBlockHash"], bytes):
                self["nextBlockHash"] = rh2s(self["nextBlockHash"])
        if isinstance(self["merkleRoot"], bytes):
            self["merkleRoot"] = rh2s(self["merkleRoot"])
        if isinstance(self["header"], bytes):
            self["header"] = self["header"].hex()
        if isinstance(self["bits"], bytes):
            self["bits"] = rh2s(self["bits"])
        for i in self["tx"]:
            self["tx"][i].decode(testnet=testnet)

    @staticmethod
    def get_stream(stream):
        if type(stream) != BytesIO:
            if type(stream) == str:
                stream = bytes.fromhex(stream)
            if type(stream) == bytes:
                stream = BytesIO(stream)
            else:
                raise TypeError
        return stream

class BlockTemplate():
    def __init__(self, data, coinbase_output_address, testnet = False, coinbase_message = "",
                 extranonce1 = "00000000",
                 extranonce1_size = 4,
                 extranonce2_size = 4):
        self.testnet = testnet
        self.version = data["version"].to_bytes(4, "big").hex()
        self.previous_block_hash = reverse_hash(s2rh(data["previousblockhash"])).hex()
        self.time = data["curtime"].to_bytes(4, "big").hex()
        self.bits = data["bits"]
        self.height = data["height"]
        self.block_reward = 200 * 100000000 >> data["height"] // 210000
        self.coinbasevalue = self.block_reward
        self.extranonce1 = extranonce1
        self.extranonce1_size = extranonce1_size
        self.extranonce2 = "00000000"
        self.extranonce2_size = extranonce2_size
        self.coinbase_output_address = coinbase_output_address
        self.sigoplimit = data["sigoplimit"]
        self.weightlimit = data["weightlimit"]
        self.sigop= 0
        self.weight = 0
        # if type(coinbase_message) == bytes:
        #     coinbase_message = coinbase_message.hex()
        self.coinbase_message = coinbase_message

        self.transactions = list(data["transactions"])
        self.txid_list = list()
        self.scan_tx_list()
        self.coinbase_tx = self.create_coinbase_transaction()
        self.coinb1, self.coinb2 = self.split_coinbase()
        self.target = bits_to_target(self.bits)
        self.difficulty = target_to_difficulty(self.target)
        # print("<>>>>>>",self.coinbase_tx["txId"])
        self.merkle_branches = [i for i in merkle_branches([self.coinbase_tx["txId"],] + self.txid_list)]


    def scan_tx_list(self):
        self.coinbasevalue = self.block_reward
        self.sigop = 0
        self.weight = 0
        self.txid_list = list()
        tx_fee = 0
        for tx in self.transactions:
            txid = s2rh(tx["txid"])
            tx_fee += tx["fee"]
            self.weight += tx["weight"]
            self.sigop += tx["sigops"]
            self.txid_list.append(txid)
        self.coinbasevalue  += math.floor(tx_fee / 10)

    def calculate_commitment(self, witness_reserved_value):
        # print("calculate_commitment")
        wtxid_list = [b"\x00" * 32,]
        if self.transactions:
            for tx in self.transactions:
                wtxid_list.append(s2rh(tx["hash"]))
        # print("wtxid_list", wtxid_list)
        # print("wtxid_list", wtxid_list)
        # print("commitment ", double_sha256(merkle_root_double_sha256(wtxid_list, return_hex=0) + witness_reserved_value))
        return double_sha256(merkle_root_double_sha256(wtxid_list, return_hex=0) + witness_reserved_value)

    def split_coinbase(self):
        tx = self.coinbase_tx.serialize(segwit=0, hex= 0)
        len_coinbase = int(len(self.coinbase_tx["vIn"][0]["scriptSig"])/2)
        extranonce_len = self.extranonce1_size + self.extranonce2_size
        return tx[:42 + len_coinbase - extranonce_len].hex(),\
               tx[42 + len_coinbase:].hex()


    def create_coinbase_transaction(self):
        tx = Transaction()
        coinbase = b'\x02' + self.height.to_bytes(2,'little') + self.coinbase_message
        coinbase += b"\x00" * (self.extranonce1_size + self.extranonce2_size)
        assert len(coinbase) <= 100
        tx.add_input(script_sig=coinbase)
        commitment = self.calculate_commitment(b'\x00'*32)
        tx.add_output(self.coinbasevalue, address = self.coinbase_output_address)
        tx.add_output(0, script_pub_key = b'j$\xaa!\xa9\xed' + commitment)
        # tx.add_output(0, script_pub_key = bytes_from_hex("6a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf9"))
        tx.coinbase = True
        tx.commit()
        # print("coinbase tx", tx["txId"])
        # print("coinbase tx >>>>", tx)
        return tx

    def get_job(self, job_id, clean_jobs = True):
        """
        job_id - ID of the job. Use this ID while submitting share generated from this job.
        prevhash - Hash of previous block.
        coinb1 - Initial part of coinbase transaction.
        coinb2 - Final part of coinbase transaction.
        merkle_branch - List of hashes, will be used for calculation of merkle root. This is not a list of all
        transactions, it only contains prepared hashes of steps of merkle tree algorithm. Please read some
        materials for understanding how merkle trees calculation works.
        version - Bitcoin block version.
        nbits - Encoded current network difficulty
        ntime - Current ntime/
        clean_jobs - When true, server indicates that submitting shares from previous jobs don't have a
        sense and such shares will be rejected. When this flag is set, miner should also drop all previous
         jobs, so job_ids can be eventually rotated.

        """
        return [job_id,
                self.previous_block_hash,
                self.coinb1,
                self.coinb2,
                self.merkle_branches,
                self.version,
                self.bits,
                self.time,
                clean_jobs]

    def submit_job(self, extra_nonce_1, extra_nonce_2, nonce, time):
        version = s2rh(self.version)
        prev_hash = s2rh_step4(self.previous_block_hash)
        cb = self.coinb1 + extra_nonce_1 + extra_nonce_2 + self.coinb2
        # print("ccoinbase", cb)
        time = s2rh(time)
        bits = s2rh(self.bits)
        nonce = s2rh(nonce)
        c = Transaction(cb)
        cbh =  s2rh(c["txId"])
        merkle_root = merkle_root_from_branches(self.merkle_branches, cbh)
        # print("version ", version.hex())
        # print("prev_hash ", self.previous_block_hash)
        # print("cbh ", cbh.hex())
        # print("cbh2 ", s2rh(c["txId"]))
        # merkle_root = bytes_from_hex("6a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf9")
        # merkle_root = s2rh(c["txId"])
        # print("merkle_root ", merkle_root.hex())
        # print("merkle_root ", s2rh(c["txId"]))
        # print("branches ", self.merkle_branches)
        header = version + prev_hash + merkle_root + time + bits + nonce
        # print("header", header.hex())
        block = header.hex()
        block +=int_to_var_int(len (self.transactions) + 1).hex()
        block += cb
        for t in self.transactions:
            block += t["data"]
        return sha3_256(header,1), block


    def mn(self,  nonce):

        header = self.h1 +  s2rh(nonce) + self.h1
        return sha3_256(header, 1)
        cb = self.coinb1 + extra_nonce_1 + extra_nonce_2 + self.coinb2
        time = s2rh(time)
        bits = s2rh(self.bits)
        nonce = s2rh(nonce)
        cbh = sha3_256(bytes_from_hex(cb))
        c = Transaction(cb)
        # cbh = sha3_256(c["txId"])
        merkle_root = merkle_root_from_branches(self.merkle_branches, cbh)
        # print("cbh ", cbh.hex())
        # print("cbh2 ", s2rh(c["txId"]))
        #
        # print("merkle_root ", merkle_root.hex())
        # print("branches ", self.merkle_branches)
        header = version + prev_hash + merkle_root + time + bits + nonce
        block = header.hex()
        block +=int_to_var_int(len (self.transactions) + 1).hex()
        block += cb
        for t in self.transactions:
            block += t["data"]
        return sha3_256(header,1), block
    # def build_orphan(self, hash, ntime):
    #     self.previous_block_hash =  reverse_hash(s2rh(hash)).decode()
    #     self.time = hexlify(ntime.to_bytes(4, "big")).decode()
    #     self.height += 1
    #     self.transactions = list()
    #     self.txid_list = list()
    #     self.scan_tx_list()
    #     self.coinbase_tx = self.create_coinbase_transaction()
    #     self.coinb1, self.coinb2 = self.split_coinbase()
    #     self.target = bits2target(self.bits)
    #     self.difficulty = target2difficulty(self.target)
    #     self.merkle_branches = [hexlify(i).decode() for i in merkle_branches([self.coinbase_tx.hash, ] + self.txid_list)]