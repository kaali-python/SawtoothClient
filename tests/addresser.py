# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# -----------------------------------------------------------------------------

import enum
import hashlib
import binascii
import coloredlogs, logging
coloredlogs.install()

FAMILY_NAME = 'accredit_users'


NS = hashlib.sha512(FAMILY_NAME.encode()).hexdigest()[:6]


class CreateAssetSpace(enum.IntEnum):
    START = 1
    STOP =  64


class ShareAssetSpace(enum.IntEnum):
    START = 65
    STOP =  128


class ReceiveAssetSpace(enum.IntEnum):
    START =  129
    STOP =  192


class TransferAssetSpace(enum.IntEnum):
    START =  193
    STOP =  256


class FloatAccountSpace(enum.IntEnum):
    START = 256
    STOP = 320

class CreateUserAccountSpace(enum.IntEnum):
    START = 321
    STOP = 384


class CreateOrganizationAccountSpace(enum.IntEnum):
    START = 385
    STOP = 448

class CreateChildAccountSpace(enum.IntEnum):
    START = 449
    STOP = 512





@enum.unique
class AddressSpace(enum.IntEnum):
    CREATE_ASSET = 0
    SHARE_ASSET = 1
    RECEIVE_ASSET = 2
    TRANSFER_ASSET = 3
    FLOAT_ACCOUNT = 4
    USER_ACCOUNT = 5
    ORGANIZATION_ACCOUNT=6
    CHILD_ACCOUNT=7
    OTHER_FAMILY = 100




def float_account_address(account_id, index):

    index_hex = '{:08x}'.format(index)
    full_hash = _hash(account_id)


    return NS \
            + index_hex\
            +_compress(full_hash, FloatAccountSpace.START, FloatAccountSpace.STOP)\
            + full_hash[:53]


def create_user_account_address(account_id, index):
    index_hex = '{:08x}'.format(index)
    full_hash = _hash(account_id)
    return NS \
            + index_hex\
            +_compress(full_hash, CreateUserAccountSpace.START, \
                    CreateUserAccountSpace.STOP)\
            + full_hash[:53]



def create_organization_account_address(account_id, index):
    index_hex = '{:08x}'.format(index)
    full_hash = _hash(account_id)
    return NS \
            + index_hex\
            +_compress(full_hash, CreateOrganizationAccountSpace.START, \
                        CreateOrganizationAccountSpace.STOP)\
            + full_hash[:53]


def child_account_address(account_id, index):
    index_hex = '{:08x}'.format(index)
    full_hash = _hash(account_id)
    return NS \
            + index_hex\
            +_compress(full_hash, CreateChildAccountSpace.START, \
                        CreateChildAccountSpace.STOP)\
            + full_hash[:53]

def create_asset_address(asset_id, index):
    index_hex = '{:08x}'.format(index)
    full_hash = _hash(asset_id)
    return NS \
            + index_hex\
            +_compress(full_hash, CreateAssetSpace.START, CreateAssetSpace.STOP)\
            + full_hash[:53]




def share_asset_address(asset_id,  index):
    index_hex = '{:08x}'.format(index)
    full_hash = _hash(asset_id)
    return NS \
            + index_hex\
            +_compress(full_hash, ShareAssetSpace.START, ShareAssetSpace.STOP)\
            + full_hash[:53]



def transfer_asset_address(asset_id,  index):
    index_hex = '{:08x}'.format(index)
    full_hash = _hash(asset_id)
    return NS \
            + index_hex\
            +_compress(full_hash, TransferAssetSpace.START, TransferAssetSpace.STOP)\
            + full_hash[:53]


def receive_asset_address(asset_id, index):
    index_hex = '{:08x}'.format(index)
    full_hash = _hash(asset_id)
    return NS \
            + index_hex\
            +_compress(full_hash, ReceiveAssetSpace.START, ReceiveAssetSpace.STOP)\
            + full_hash[:53]



def _hash(identifier):
    return hashlib.sha512(identifier.encode()).hexdigest()



def _compress(address, start, stop):
    ##This calculates the mod of the address with (stop-start)+start,
    ##The benefit being
    return "%.3X".lower() % (int(address, base=16) % (stop - start) + start)




def _contains(num, space):
    return space.START <= num < space.STOP

def hex_to_int(int_hex):
    return int.from_bytes(binascii.unhexlify(int_hex), byteorder='big')


def address_is(address):

    if address[:len(NS)] != NS:
        print ("THis is other family")
        return AddressSpace.OTHER_FAMILY, None

    infix = int(address[14:17], 16)
    int_hex = address[6:14]


    if _contains(infix, CreateAssetSpace):
        result = AddressSpace.CREATE_ASSET

    elif _contains(infix, ShareAssetSpace):
        result = AddressSpace.SHARE_ASSET

    elif _contains(infix, ReceiveAssetSpace):
        result = AddressSpace.RECEIVE_ASSET

    elif _contains(infix, FloatAccountSpace):
        result = AddressSpace.FLOAT_ACCOUNT

    elif _contains(infix, CreateUserAccountSpace):
        result = AddressSpace.USER_ACCOUNT


    elif _contains(infix, CreateOrganizationAccountSpace):
        result = AddressSpace.ORGANIZATION_ACCOUNT

    elif _contains(infix, CreateChildAccountSpace):
        result = AddressSpace.CHILD_ACCOUNT


    elif _contains(infix, TransferAssetSpace):
        result = AddressSpace.TRANSFER_ASSET


    else:
        result = AddressSpace.OTHER_FAMILY


    return (result.name, hex_to_int(int_hex))

def is_account_address(address):
    result = address_is(address)
    if result[0] != "CREATE_ACCOUNT":
        return False
    return True



def test_address(key):
    g = random.randint(0, 2**32-1)
    _float_account_address = float_account_address(key, g)
    _asset_address = create_asset_address(key, g)
    _share_asset_address = share_asset_address(key, g)
    _receive_asset_address = receive_asset_address(key, g)
    _transfer_asset_address = transfer_asset_address(key, g)

    user_account_address = create_user_account_address(key, g)
    organization_address = create_organization_account_address(key, g)
    child_address = child_account_address(key, g)

    print ("FLOAT", _float_account_address, address_is(_float_account_address))
    print ("USER_ACCOUNT", user_account_address, address_is(user_account_address))
    print ("Organization Address", organization_address, address_is(organization_address))
    print ("Child account Address", child_address, address_is(child_address))

    print ("Create Asset Address", _asset_address, address_is(_asset_address))
    print ("Share asset address", _share_asset_address, address_is(_share_asset_address))
    print ("Receiver asset address", _receive_asset_address, address_is(_receive_asset_address))
    print ("Transfer assset address", _transfer_asset_address, address_is(_transfer_asset_address) )
