from typing import Any, Dict, List, Union, cast, MutableSequence

from boa3.builtin import CreateNewEvent, NeoMetadata, metadata, public
from boa3.builtin.contract import Nep17TransferEvent, abort
from boa3.builtin.interop.blockchain import get_contract, Transaction
from boa3.builtin.interop.contract import NEO, GAS, call_contract, destroy_contract, update_contract
from boa3.builtin.interop.runtime import notify, log, calling_script_hash, executing_script_hash, check_witness, script_container
from boa3.builtin.interop.binary import serialize, deserialize, base58_encode
from boa3.builtin.interop.storage import delete, get, put, find, get_context
from boa3.builtin.interop.iterator import Iterator
from boa3.builtin.interop.crypto import ripemd160, sha256
from boa3.builtin.type import UInt160, UInt256
from boa3.builtin.interop.storage.storagecontext import StorageContext
from boa3.builtin.interop.contract import CallFlags
from boa3.builtin.interop.json import json_serialize, json_deserialize



# -------------------------------------------
# METADATA
# -------------------------------------------

@metadata
def manifest_metadata() -> NeoMetadata:
    """
    Defines this smart contract's metadata information
    """
    meta = NeoMetadata()
    meta.author = "Mathias Enzensberger"
    meta.description = "GhostMarket NFT"
    meta.email = "hello@ghostmarket.io"
    meta.supportedstandards = "NEP-11"
    return meta


# -------------------------------------------
# TOKEN SETTINGS
# -------------------------------------------

# Script hash of the contract owner
# OWNER = UInt160(b'@\x1fA%\x1513)\xbd^\xac\xc4!\x1c**\x0elW\x96')
OWNER = UInt160(b'\x96Wl\x0e**\x1c!\xc4\xac^\xbd)31\x15%A\x1f@')

#Fee on deploy
DEPLOY_FEE = 10000000

# Symbol of the Token
TOKEN_SYMBOL = 'GHOST'
TOKEN_SYMBOL_B = b'GHOST'

# Whether the smart contract was deployed or not
DEPLOYED = b'deployed'


# -------------------------------------------
# Prefixes
# -------------------------------------------

ACCOUNT_PREFIX = b'A'
TOKEN_PREFIX = b'T'
LOCKED_PREFIX = b'LC'
BALANCE_PREFIX = b'B'
SUPPLY_PREFIX = b'S'
META_PREFIX = b'M'
LOCKED_VIEW_COUNT = b'LVC'


# -------------------------------------------
# Keys
# -------------------------------------------

TOKEN_COUNT = b'TC'
PAUSED = b'PAUSED'
MINT_FEE = b'MINT_FEE'
AUTH_ADDRESSES = b'AUTH_ADDR'


# -------------------------------------------
# Events
# -------------------------------------------

on_transfer = CreateNewEvent(
    [
        ('from_addr', Union[UInt160, None]),
        ('to_addr', Union[UInt160, None]),
        ('amount', int),
        ('tokenId', bytes)
    ],
    'Transfer'
)

on_auth = CreateNewEvent(
    [
        ('authorized', UInt160),
        ('add', bool),
    ],
    'Auth'
)

on_mint = CreateNewEvent(
    [
        ('creator', UInt160),
        ('tokenId', bytes),
        ('tokenURI', str),
        ('externalURI', str),
        ('mint_fees', int)
    ],
    'Mint'
)

on_mint_fees_withdrawn = CreateNewEvent(
    [
        ('from_addr', int),
        ('value', int)
    ],
    'MintFeesUWithdrawn'
)

on_mint_fees_updated = CreateNewEvent(
    [
        ('value', int)
    ],
    'MintFeesUpdated'
)

on_royalties_set = CreateNewEvent(
    [
        ('tokenId', bytes),
        ('recipients', List[UInt160]),
        ('bps', List[int])
    ],
    'RoyaltiesSet'
)

on_deploy = CreateNewEvent(
    [
        ('owner', UInt160),
        ('symbol', str),
    ],
    'Deploy'
)

debug = CreateNewEvent(
    [
        ('params', list),
    ],
    'Debug'
)


# -------------------------------------------
# DEBUG
# -------------------------------------------

# def debug(data: list):
#     notify(data, "DEBUG_CONTRACT")

# -------------------------------------------
# Methods
# -------------------------------------------

@public
def symbol() -> str:
    """
    Gets the symbols of the token.

    This string must be valid ASCII, must not contain whitespace or control characters, should be limited to uppercase
    Latin alphabet (i.e. the 26 letters used in English) and should be short (3-8 characters is recommended).
    This method must always return the same value every time it is invoked.

    :return: a short string representing symbol of the token managed in this contract.
    """
    return TOKEN_SYMBOL

@public
def decimals() -> int:
    """
    Gets the amount of decimals used by the token.

    E.g. 8, means to divide the token amount by 100,000,000 (10 ^ 8) to get its user representation.
    This method must always return the same value every time it is invoked.

    :return: the number of decimals used by the token.
    """
    return 0

@public
def totalSupply() -> int:
    """
    Gets the total token supply deployed in the system.

    This number must not be in its user representation. E.g. if the total supply is 10,000,000 tokens, this method
    must return 10,000,000 * 10 ^ decimals.

    :return: the total token supply deployed in the system.
    """
    return get(SUPPLY_PREFIX).to_int()

@public
def balanceOf(owner: UInt160) -> int:
    """
    Get the current balance of an address

    The parameter account must be a 20-byte address represented by a UInt160.

    :param owner: the account address to retrieve the balance for
    :type owner: UInt160
    :return: the total amount of NFTs owned by the specified address.
    """
    assert len(owner) == 20
    return get(mk_balance_key(owner)).to_int()

@public
def tokensOf(owner: UInt160) -> Iterator:
    """
    Get all of the token ids owned by the specified address

    The parameter account must be a 20-byte address represented by a UInt160.

    :param owner: the account address to retrieve the tokens for
    :type owner: UInt160
    :return: an iterator that contains all of the token ids owned by the specified address.
    """
    assert len(owner) == 20
    ctx = get_context()

    return find(mk_account_prefix(owner), ctx)

@public
def transfer(to: UInt160, tokenId: bytes, data: Any) -> bool:
    """
    Transfers an amount of NEP17 tokens from one account to another

    If the method succeeds, it must fire the `Transfer` event and must return true, even if the amount is 0,
    or from and to are the same address.

    :param from_address: the address to transfer from
    :type from_address: UInt160
    :param to_address: the address to transfer to
    :type to_address: UInt160
    :param amount: the amount of NEP17 tokens to transfer
    :type amount: int
    :param data: whatever data is pertinent to the onPayment method
    :type data: Any

    :return: whether the transfer was successful
    :raise AssertionError: raised if `from_address` or `to_address` length is not 20 or if `amount` is less than zero.
    """
    # the parameters from and to should be 20-byte addresses. If not, this method should throw an exception.
    assert len(to) == 20

    ctx = get_context()
    token_owner = get_owner_of(ctx, tokenId)

    if (not check_witness(token_owner)):
        return False

    if (token_owner != to):
        add_to_balance(ctx, token_owner, -1)
        remove_token(ctx, token_owner, tokenId)

        add_to_balance(ctx, to, 1)
        add_token(ctx, to, tokenId)
        set_owner_of(ctx, tokenId, to)
    post_transfer(token_owner, to, tokenId, data)
    return True

@public
def ownerOf(tokenId: bytes) -> UInt160:
    """
    Get the owner of the specified token.

    The parameter tokenId SHOULD be a valid NFT. If not, this method SHOULD throw an exception.

    :param tokenId: the token for which to check the ownership
    :type tokenId: ByteString
    :return: the owner of the specified token.
    """

@public
def tokens() -> Iterator:
    """
    Get all tokens minted by the contract

    :return: an iterator that contains all of the tokens minted by the contract.
    """
    ctx = get_context()
    return find(TOKEN_PREFIX, ctx)

@public
def properties(tokenId: bytes) -> Dict[str, str]:
    """
    TODO

    """
    ctx = get_context()
    meta = get_meta(ctx, tokenId)
    deserialized = json_deserialize(meta)
    return cast(dict[str, str], deserialized)

@public
def burn(token: bytes) -> bool:
    """
    Mints new tokens. This is not a NEP-17 standard method, it's only being use to complement the onPayment method

    :param account: the address of the account that is sending cryptocurrency to this contract
    :type account: UInt160
    :param amount: the amount of gas to be refunded
    :type amount: int
    :raise AssertionError: raised if amount is less than than 0
    """
    return internal_burn(token)

@public
def multiBurn(tokens: List[bytes]) -> List[bool]:
    """
    Mints new tokens. This is not a NEP-17 standard method, it's only being use to complement the onPayment method

    :param account: the address of the account that is sending cryptocurrency to this contract
    :type account: UInt160
    :param amount: the amount of gas to be refunded
    :type amount: int
    :raise AssertionError: raised if amount is less than than 0
    """
    burned: List[bool] = []
    for i in tokens:
        burned.append(burn(i))
    return burned

@public
def mint(account: UInt160, meta: str, lockedContent: bytes, data: Any) -> bytes:
    """
    Mints new tokens. This is not a NEP-17 standard method, it's only being use to complement the onPayment method

    :param account: the address of the account that is sending cryptocurrency to this contract
    :type account: UInt160
    :param amount: the amount of gas to be refunded
    :type amount: int
    :raise AssertionError: raised if amount is less than than 0
    """

    ctx = get_context()
    fee = get_mint_fee(ctx)
    if fee < 0:
        raise Exception("Mint fee can't be < 0")

    if not cast(bool, call_contract(GAS, 'transfer', [account, executing_script_hash, fee, None])):
        raise Exception("Fee payment failed!")

    return internal_mint(account, meta, lockedContent, data)

@public
def multiMint(account: UInt160, meta: List[str], lockedContent: List[bytes], data: Any) -> List[bytes]:
    """
    Mints new tokens. This is not a NEP-17 standard method, it's only being use to complement the onPayment method

    :param account: the address of the account that is sending cryptocurrency to this contract
    :type account: UInt160
    :param amount: the amount of gas to be refunded
    :type amount: int
    :raise AssertionError: raised if amount is less than than 0
    """
    nfts: List[bytes] = []
    for i in range(0, len(meta)):
        nfts.append(mint(account, meta[i], lockedContent[i], data))
    return nfts

@public
def withdrawFee(account: UInt160) -> bool:
    """
    Mints new tokens. This is not a NEP-17 standard method, it's only being use to complement the onPayment method

    :param account: the address of the account that is sending cryptocurrency to this contract
    :type account: UInt160
    :param amount: the amount of gas to be refunded
    :type amount: int
    :raise AssertionError: raised if amount is less than than 0
    """

    assert verify()
    current_balance = cast(int, call_contract(GAS, 'balanceOf', [executing_script_hash]))
    return cast(bool, call_contract(GAS, 'transfer', [executing_script_hash, account, current_balance, None]))

@public
def getFeeBalance() -> Any:
    """
    TODO

    """

    balance = call_contract(GAS, 'balanceOf', [executing_script_hash])
    return balance

@public
def getMintFee() -> int:
    """
    TODO
    """
    ctx = get_context()
    fee = get_mint_fee(ctx)
    return fee

@public
def setMintFee(fee: int) -> int:
    """
    TODO
    """
    assert verify()
    ctx = get_context()
    return set_mint_fee(ctx, fee)

@public
def getLockedContentViewCount(token: bytes) -> int:
    """
    TODO
    """
    ctx = get_context()
    return get_locked_view_counter(ctx, token)

@public
def getLockedContent(token: bytes) -> bytes:
    """
    TODO
    """
    ctx = get_context()
    owner = get_owner_of(ctx, token)

    if not check_witness(owner):
        raise Exception("Prohibited access to locked content!")

    incr_locked_view_counter(ctx, token)
    
    return get_locked_content(ctx, token)

@public
def set_authorized_address(address: UInt160, authorized: bool) -> bool:
    """
    When this contract address is included in the transaction signature,
    this method will be triggered as a VerificationTrigger to verify that the signature is correct.
    For example, this method needs to be called when withdrawing token from the contract.

    :return: whether the transaction signature is correct
    """
    if not verify():
        return False

    serialized = get(AUTH_ADDRESSES)
    auth = cast(list[UInt160], deserialize(serialized))

    if authorized:
        found = False
        for i in auth:
            if i == address:
                found = True

        if not found:
            auth.append(address)

        put(AUTH_ADDRESSES, serialize(auth))
        on_auth(address, True)
    else:
        auth.remove(address)
        put(AUTH_ADDRESSES, serialize(auth))
        on_auth(address, False)

    return True

@public
def verify() -> bool:
    """
    When this contract address is included in the transaction signature,
    this method will be triggered as a VerificationTrigger to verify that the signature is correct.
    For example, this method needs to be called when withdrawing token from the contract.

    :return: whether the transaction signature is correct
    """

    if check_witness(OWNER):
        return True

    #auth = cast(dict[UInt160, UInt160], deserialize(serialized))
    #if auth

    return False

@public
def deploy() -> bool:
    """
    Deploys the contract.

    :return: whether the deploy was successful. This method must return True only during the smart contract's deploy.
    """
    if not check_witness(OWNER):
        return False

    if get(DEPLOYED).to_bool():
        return False

    put(DEPLOYED, True)
    put(TOKEN_COUNT, 0)
    put(MINT_FEE, DEPLOY_FEE)

    auth: List[UInt160] = []
    auth.append(OWNER)
    serialized = serialize(auth)
    put(AUTH_ADDRESSES, serialized)

    on_deploy(OWNER, symbol())
    return True

@public
def update(script: bytes, manifest: bytes):
    """
    :param script: the contract script
    :type script: bytes
    :param manifest: the contract manifest
    :type manifest: bytes
    Upgrades the contract

    """
    assert verify()
    update_contract(script, manifest) 

@public
def destroy():
    """
    Destroys the contract.

    """
    assert verify()
    destroy_contract() 

@public
def onNEP11Payment(from: UInt160, amount: int, tokenId: bytes, data: Any):
    """
    :param from: the address of the one who is trying to send cryptocurrency to this smart contract
    :type from: UInt160
    :param amount: the amount of cryptocurrency that is being sent to the this smart contract
    :type amount: int
    :param tokenId: the token hash as bytes
    :type tokenId: bytes
    :param data: any pertinent data that might validate the transaction
    :type data: Any
    """
    abort()

@public
def onNEP17Payment(from: UInt160, amount: int, data: Any):
    """
    :param from: the address of the one who is trying to send cryptocurrency to this smart contract
    :type from: UInt160
    :param amount: the amount of cryptocurrency that is being sent to the this smart contract
    :type amount: int
    :param data: any pertinent data that might validate the transaction
    :type data: Any
    """
    #Use calling_script_hash to identify if the incoming token is NEO or GAS
    if calling_script_hash != GAS:
        abort()


def post_transfer(from_address: Union[UInt160, None], to_address: Union[UInt160, None], token: bytes, data: Any):
    """
    Checks if the one receiving NEP17 tokens is a smart contract and if it's one the onPayment method will be called

    :param from_address: the address of the sender
    :type from_address: UInt160
    :param to_address: the address of the receiver
    :type to_address: UInt160
    :param amount: the amount of cryptocurrency that is being sent
    :type amount: int
    :param data: any pertinent data that might validate the transaction
    :type data: Any
    """
    on_transfer(from_address, to_address, 1, token)
    if not isinstance(to_address, None):    # TODO: change to 'is not None' when `is` semantic is implemented
        contract = get_contract(to_address)
        if not isinstance(contract, None):      # TODO: change to 'is not None' when `is` semantic is implemented
            call_contract(to_address, 'onNEP11Payment', [from_address, 1, token, data])
            pass

def internal_burn(token: bytes) -> bool:
    """
    Mints new tokens. This is not a NEP-17 standard method, it's only being use to complement the onPayment method

    :param account: the address of the account that is sending cryptocurrency to this contract
    :type account: UInt160
    :param amount: the amount of gas to be refunded
    :type amount: int
    :raise AssertionError: raised if amount is less than than 0
    """

    ctx = get_context()
    owner = get_owner_of(ctx, token)

    if not check_witness(owner):
        return False

    remove_token(ctx, owner, token)
    remove_meta(ctx, token)
    remove_owner_of(ctx, token)
    add_to_balance(ctx, owner, -1)
    add_to_supply(ctx, -1)
    
    # TODO delete view count for locked content

    post_transfer(owner, None, token, None)
    return True

def internal_mint(account: UInt160, meta: str, lockedContent: bytes, data: Any) -> bytes:
    """
    Mints new tokens. This is not a NEP-17 standard method, it's only being use to complement the onPayment method

    :param account: the address of the account that is sending cryptocurrency to this contract
    :type account: UInt160
    :param amount: the amount of gas to be refunded
    :type amount: int
    :raise AssertionError: raised if amount is less than than 0
    """

    ctx = get_context()

    total = totalSupply()
    newNFT = bytearray(TOKEN_SYMBOL_B)
    nftData = 0

    token_id = get(TOKEN_COUNT, ctx).to_int() + 1
    put(TOKEN_COUNT, token_id, ctx)
    tx = cast(Transaction, script_container)
    nftData = nftData + tx.hash.to_int() + token_id

    if not isinstance(data, None):      # TODO: change to 'is not None' when `is` semantic is implemented
        nftData = nftData + serialize(data).to_int()
    newNFT.append(nftData)

    nftmeta = json_serialize(meta)
    token = newNFT

    debug(['locked: ', lockedContent])
    add_token(ctx, account, token)
    add_locked_content(ctx, token, lockedContent)
    add_meta(ctx, token, nftmeta)
    set_owner_of(ctx, token, account)
    add_to_balance(ctx, account, 1)
    add_to_supply(ctx, 1)

    post_transfer(None, account, token, None)

    return token

def get_meta(ctx: StorageContext, token: bytes) -> bytes:
    key = mk_meta_key(token)
    val = get(key, ctx)
    return val

def remove_meta(ctx: StorageContext, token: bytes):
    key = mk_meta_key(token)
    delete(key, ctx)

def add_meta(ctx: StorageContext, token: bytes, meta: bytes):
    key = mk_meta_key(token)
    put(key, meta, ctx)

def add_token(ctx: StorageContext, owner: UInt160, token: bytes):
    key = mk_account_prefix(owner) + token
    # debug(['add token: ', key, token])
    put(key, token, ctx)

def remove_token(ctx: StorageContext, owner: UInt160, token: bytes):
    key = mk_account_prefix(owner) + token
    delete(key, ctx)

def remove_owner_of(ctx: StorageContext, token: bytes):
    key = mk_token_key(token)
    delete(key, ctx)

def set_owner_of(ctx: StorageContext, token: bytes, owner: UInt160):
    key = mk_token_key(token)
    put(key, owner, ctx)

def get_owner_of(ctx: StorageContext, token: bytes) -> UInt160:
    key = mk_token_key(token)
    owner = get(key, ctx)
    return UInt160(owner)

def add_locked_content(ctx: StorageContext, token: bytes, content: bytes):
    key = mk_locked_key(token)
    put(key, content, ctx)
    debug(['locked2: ', get(key, ctx), key])

def get_locked_content(ctx: StorageContext, token: bytes) -> bytes:
    key = mk_locked_key(token)
    val = get(key, ctx)
    debug(['locked3: ', val, key])
    return val

def remove_locked_content(ctx: StorageContext, token: bytes):
    key = mk_locked_key(token)
    delete(key, ctx)

def set_mint_fee(ctx: StorageContext, amount: int) -> int:
    put(MINT_FEE, amount, ctx)
    return get_mint_fee(ctx)

def get_mint_fee(ctx: StorageContext) -> int:
    fee = get(MINT_FEE, ctx).to_int()
    if fee is None:
        return 0
    return fee

def get_locked_view_counter(ctx: StorageContext, token: bytes) -> int:
    key = mk_lv_key(token)
    return get(key, ctx).to_int()

def incr_locked_view_counter(ctx: StorageContext, token: bytes):
    key = mk_lv_key(token)
    count = get(key, ctx).to_int() + 1
    put(key, count)

def add_to_supply(ctx: StorageContext, amount: int):
    total = totalSupply() + (amount)
    put(SUPPLY_PREFIX, total)

def add_to_balance(ctx: StorageContext, owner: UInt160, amount: int):
    old = balanceOf(owner)
    new = old + (amount)

    key = mk_balance_key(owner)
    if (new > 0):
        put(key, new, ctx)
    else:
        delete(key, ctx)


## helpers

def mk_account_prefix(address: UInt160) -> bytes:
    return ACCOUNT_PREFIX + address

def mk_balance_key(address: UInt160) -> bytes:
    return BALANCE_PREFIX + address

def mk_token_key(token: bytes) -> bytes:
    return TOKEN_PREFIX + token

def mk_locked_key(token: bytes) -> bytes:
    return LOCKED_PREFIX + token

def mk_meta_key(token: bytes) -> bytes:
    return META_PREFIX + token

def mk_lv_key(token: bytes) -> bytes:
    return LOCKED_VIEW_COUNT + token