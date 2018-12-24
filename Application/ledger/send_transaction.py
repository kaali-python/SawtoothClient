

from ledger import messaging
import coloredlogs, logging
from errors.errors import ApiBadRequest, ApiInternalError
coloredlogs.install()

from addressing import addresser
from protocompiled import payload_pb2
from transactions.extended_batch import make_header_and_batch

from asyncinit import asyncinit

class aobject(object):
    """Inheriting this class allows you to define an async __init__.

    So you can create objects by doing something like `await MyClass(params)`
    """
    async def __new__(cls, *a, **kw):
        instance = super().__new__(cls)
        await instance.__init__(*a, **kw)
        return instance

    async def __init__(self):
        pass




@asyncinit
class SendTransactions(aobject):
    async def __init__(self, rest_api_url, timeout):
        #self.val = await self.deferredFn(param)
        self.rest_api_url = rest_api_url
        self.timeout =  aiohttp.ClientTimeout(total=timeout)
        self.headers = {'Content-Type': 'application/octet-stream'}
        self.wait = timeout

    async def push_transaction(self, batch_list_bytes):
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(f"http://{rest_api_url}/batches",
                                data=batch_list_bytes,
                                headers=self.headers) as response:
                    data = await response.read()
        except Exception as e:
            logging.error("Blockchain rest-api is unreachable, Please fix it dude")
            raise ApiInternalError("Blockchain rest-api is unreachable, Please fix it dude")
        logging.info(f"Data returned after pushing the transaction on the blockchain {data}")
        return data


    async def wait_for_status(self, batch_id, rest_api_url, timeout):
        """
        Once the batch is pushed on to the rest api of blockchain, wait for
        its confirmation, If the status of block sumission is COMMITTED return True
        else
            False
        """
        waited = 0
        start_time = time.time()
        while waited < self.wait:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(f"http://{self.rest_api_url}/batch_statuses?id={batch_id}",
                        headers=self.headers) as response:
                        await asyncio.sleep(0.1)
                        data = await response.read()

            waited = time.time() - start_time
            logging.info(f"Trying again, to check block status BLOCK-STATUS {status}")

            if status != 'PENDING':
                break
        if status == "COMMITTED":
            logging.info("Transaction successfully submittted")
            return True
        else:
            logging.error("Error in the transaction {%s}"%data['data'][0]['message'])
            raise ApiBadRequest("Error in the transaction {%s}"%data['data'][0]['message'])
        return False


    async def share_mnemonic_transaction(self, txn_key=False, batch_key=False,
                                    inputs=False, outputs=False, payload=False):
        payload = payload_pb2.TransactionPayload(
            payload_type=payload_pb2.TransactionPayload.SHARE_SECRET,
            share_secret=payload)

        logging.info(payload)
        transaction_ids, batches, batch_id, batch_list_bytes =
                        make_header_and_batch(
                            payload=payload,
                            inputs=inputs,
                            outputs=outputs,
                            txn_key=txn_key,
                            batch_key=batch_key)

        transaction_id, transaction =  make_header_and_transaction(
                                                    payload=payload,
                                                    inputs=inputs,
                                                    outputs=outputs,
                                                    txn_key=txn_key,
                                                    batch_key=batch_key)

        #rest_api_response = await self.push_transaction(batch_list_bytes)
        #logging.info(f"push transaction result is {data}")
        #if not await self.wait_for_status(batch_id):
        #        raise errors.ApiInternalError("The batch couldnt be submitted")
        return transaction_id, transaction


    def multiple_transactions_batch(self, transactions, batch_key):

        batch_bytes, batch_id = transactions_batch(transactions, batch_key)
        return batch_bytes, batch_id

    async def execute_mnemonic_transaction(self, txn_key=False, batch_key=False,
                                    inputs=False, outputs=False, payload=False):
        payload = payload_pb2.TransactionPayload(
            payload_type=payload_pb2.TransactionPayload.EXECUTE_SECRET,
            execute_secret=payload)

        logging.info(payload)
        transaction_ids, batches, batch_id, batch_list_bytes =
                        make_header_and_batch(
                            payload=payload,
                            inputs=inputs,
                            outputs=outputs,
                            txn_key=txn_key,
                            batch_key=batch_key)

        transaction_id, transaction =  make_header_and_transaction(
                                                    payload=payload,
                                                    inputs=inputs,
                                                    outputs=outputs,
                                                    txn_key=txn_key,
                                                    batch_key=batch_key)

        batch_bytes, batch_id = transactions_batch([transaction], batch_key)

        rest_api_response = await self.push_transaction(batch_bytes)
        logging.info(f"push transaction result is {data}")
        if not await self.wait_for_status(batch_id):
            raise errors.ApiInternalError("The batch couldnt be submitted")
        return transaction_id, batch_id
