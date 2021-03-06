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
# ------------------------------------------------------------------------------

import argparse
import asyncio
import hashlib
import os
from signal import signal, SIGINT
import sys
import json
import rethinkdb as r
import functools
from db.accounts_query import insert_account, find_on_key
from sanic import Sanic
from sawtooth_signing import create_context
from sawtooth_signing import ParseError
from sawtooth_signing.secp256k1 import Secp256k1PrivateKey
from sawtooth_signing import CryptoFactory
from zmq.asyncio import ZMQEventLoop
from remotecalls.remote_calls import  from_mnemonic
#from users.login import USERS_BP
from errors.errors import ERRORS_BP
#from users.userapi import USER_ACCOUNTS_BP
from ledger.accounts.organization_account.submit_organization_account import submit_admin_account

from routes.r_accounts import ACCOUNTS_BP
from routes.r_assets import ASSETS_BP
from routes.route_utils import set_password, new_account

#from sanic_session import Session
from sanic_jinja2 import SanicJinja2
from sanic_session import Session



app = Sanic(__name__)
Session(app)  # because InMemorySessionInterface used by default

import coloredlogs, logging
coloredlogs.install()

from sanic_jinja2 import SanicJinja2

#Session(app)

jinja = SanicJinja2(app)



def close_connections(app):

    logging.warning('closing database connection')
    app.config.DB.close()

    #app.config.VAL_CON.close()


def parse_args(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--secret_key',
                        help='The API secret key')


    parser.add_argument('--aws_secret_key',
                    help='The AWS  secret key')

    parser.add_argument('--aws_access_key',
                        help='The AWS access key')
    parser.add_argument('--admin_mnemonic',
                        help='The Mnemonic for ADMIN account')

    parser.add_argument('--admin_password',
                        help='The Password for ADMIN account')

    parser.add_argument('--env',
                        help='The Environment for running the application')
    return parser.parse_args(args)


def load_config(app):  # pylint: disable=too-many-branches
    #app.config.update(DEFAULT_CONFIG)

    with open('config.json', 'r') as f:
        config = json.load(f)

    try:
        app.config.update(config)
    except Exception as e:
        print (e)
        raise Exception("Config object couldnt be loaded")
    # CLI Options will override config file options

    opts = parse_args(sys.argv[1:])
    if opts.secret_key is not None:
        app.config.secret_key = opts.secret_key
    else:
        logging.error("secret key was not provided")
        sys.exit(1)

    if opts.admin_mnemonic is not None:
        if len(opts.admin_mnemonic.split(" ")) != 24:
            logging.error("Invalid Menmonic length")
            sys.exit()
        app.config.ADMIN_MNEMONIC = opts.admin_mnemonic

    if opts.admin_password is not None:
        if hashlib.sha512(opts.admin_password.encode()).hexdigest() !=\
            app.config.ADMIN_HASH_PASSWORD:
            logging.error("Invalid admin password")
            sys.exit(1)
        else:
            logging.info("Admin password Macthed")
            app.config.ADMIN_PASSWORD = opts.admin_password

    else:
        logging.error("admin_password was not provided")
        sys.exit(1)


    if app.config.SECRET_KEY is None:
        logging.error("API secret key was not provided")
        sys.exit(1)
    else:
        app.config.SECRET_KEY = opts.secret_key


    if opts.env is None:
        logging.error("ENV must be specified")
        sys.exit(1)
    else:
        if opts.env =="PRODUCTION":
            app.config.REST_API_URL = app.config.ENV["PRODUCTION"]["REST_API_URL"]
            app.config.GOAPI_URL =app.config.ENV["PRODUCTION"]["GOAPI_URL"]
            app.config.DATABASE["ip"] =app.config.ENV["PRODUCTION"]["RETHINKDB_URL"]

        elif opts.env =="STAGING":
            app.config.REST_API_URL = app.config.ENV["STAGING"]["REST_API_URL"]
            app.config.GOAPI_URL =app.config.ENV["STAGING"]["GOAPI_URL"]
            app.config.DATABASE["ip"] =app.config.ENV["STAGING"]["RETHINKDB_URL"]

        else:
            logging.error(f"Not a valid environment {opts.env}")
            sys.exit(1)

    logging.info(app.config.REST_API_URL)
    logging.info(app.config.GOAPI_URL)
    logging.info(app.config.DATABASE)
    if not app.config.ADMIN_MNEMONIC:
        logging.error("ADMIN 12 word mnemonics was not provided")
        sys.exit(1)



    app.config.STORAGE["AWS_SECRET_KEY"] = opts.aws_secret_key
    app.config.STORAGE["AWS_ACCESS_KEY"] = opts.aws_access_key

    if app.config.STORAGE["AWS_SECRET_KEY"] is None:
        logging.error("aws secret key was not provided")
        sys.exit(1)

    if app.config.STORAGE["AWS_ACCESS_KEY"] is None:
        logging.error("aws access key was not provided")
        sys.exit(1)
    app.config.jinja = jinja

async def master_mnemonic(app):
    """
    This will check if the zeroth key generated from the ADMIN mnemonic is valid or Invalid
    If it is invalid, it will stop the application

    """
    master_pub, master_priv, zero_pub, zero_priv = await from_mnemonic(app.config.GOAPI_URL,
                                            app.config.ADMIN_MNEMONIC)
    if zero_pub != app.config.ADMIN_ZERO_PUB:
        logging.error("Wrong mnemonic provided")
        sys.exit(1)
    else:
        logging.info("ADMIN ZERO_PUB matched")

    app.config.BATCHER_PRIVATE_KEY = zero_priv
    app.config.ADMIN_ZERO_PRIV = zero_priv
    app.config.ADMIN_MSTR_PUB = master_pub
    app.config.ADMIN_MSTR_PRIV = master_priv


    try:
        private_key = Secp256k1PrivateKey.from_hex(
            app.config.BATCHER_PRIVATE_KEY)
        app.config.CONTEXT = create_context('secp256k1')
        app.config.SIGNER = CryptoFactory(app.config.CONTEXT).new_signer(private_key)
        logging.info("app.config.CONTEXT and app.config.SIGNER has been set up")
    except Exception as e:
        logging.error(f"from {__file__} error occurred {e}")
        sys.exit(1)
    return



async def open_connections(app):
    logging.debug("Tryng to initialise db")
    r.set_loop_type('asyncio')
    result = await r.connect(
        port=app.config.DATABASE["port"],
        host=app.config.DATABASE["ip"],
        db=app.config.DATABASE["dbname"],
        user=app.config.DATABASE["user"],
        password=app.config.DATABASE["password"])
    #app.config.VAL_CONN = Connection(app.config.VALIDATOR_URL)
    #app.config.VAL_CONN.open()
    logging.debug("Rethinkdb connection made")
    return result


def main():
    #app.blueprint(ACCOUNTS_BP)
    #app.blueprint(ERRORS_BP)
    #app.blueprint(ASSETS_BP)
    load_config(app)
    app.blueprint(ACCOUNTS_BP)
    app.blueprint(ERRORS_BP)
    app.blueprint(ASSETS_BP)
    #app.blueprint(USER_ACCOUNTS_BP)
    for handler, (rule, router) in app.router.routes_names.items():
        print(rule)

    zmq = ZMQEventLoop()
    asyncio.set_event_loop(zmq)
    server = app.create_server(
                host=app.config.HOST, port=app.config.PORT,
                debug=app.config.DEBUG, access_log=True)
    loop = asyncio.get_event_loop()

    ##not wait for the server to strat, this will return a future object
    asyncio.ensure_future(server)
    app.config.DB = loop.run_until_complete(open_connections(app))
    ##future.add_done_callback(functools.partial(db_callback, app))


    #task = asyncio.ensure_future(from_mnemonic(app.config.GOAPI_URL,
                                            #app.config.ADMIN_MNEMONIC))
    #task.add_done_callback(functools.partial(mstr_mnemic_chk_calbck, app))

    loop.run_until_complete(master_mnemonic(app))
    admin = loop.run_until_complete(find_on_key(app, "email", app.config.ADMIN_EMAIL,
                                            ))

    ##if ADMIN data is not present in the users_table then insert
    if not admin:
        admin = loop.run_until_complete(new_account(app, \
                        pancard=app.config.ADMIN_PANCARD,
                        phone_number=app.config.ADMIN_PHONE_NUMBER,
                        email=app.config.ADMIN_EMAIL, \
                        role="ADMIN",
                        gst_number=app.config.ADMIN_GST_NUMBER,
                        tan_number=app.config.ADMIN_TAN_NUMBER,
                        org_name=app.config.ADMIN_ORG_NAME))

        mnemonic ,admin = loop.run_until_complete(set_password(
                    app, account=admin,
                        password=app.config.ADMIN_PASSWORD))


        ##since ADMIN not going to have a create_account transaction on
        ##blockchain, its fine to set its claimed to True
        admin.update({"claimed": True})
        admin.update({"parent_pub": None, "parent_idx": 0})
        logging.info(app.config)

        loop.run_until_complete(submit_admin_account(app, admin))




    else:
        logging.info("Admin found in the Database")
    signal(SIGINT, lambda s, f: loop.close())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        close_connections(app)
        loop.stop()



if __name__ == "__main__":
    # ret.connect('13.233.46.185', 28015, password="32d10aa2-13d9-593d-9f4b-ccc871d493b5").repl()
    #ret.db("remediumdb").table("otp_email").index_create("email").run()
    #ret.db("remediumdb").table("otp_mobile").index_create("phone_number").run()

    main()
