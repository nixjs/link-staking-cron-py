import os
import time
import logging
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv
from threading import Thread
from typing import Dict, Tuple
import signal

# Load environment variables
load_dotenv()

# ABI contract staking
STAKING_ABI = [
    {
        "inputs": [],
        "name": "getMaxPoolSize",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getTotalPrincipal",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getChainlinkToken",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "isOpen",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "isActive",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# ABI erc20
LINK_TOKEN_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
            {"name": "_data", "type": "bytes"},
        ],
        "name": "transferAndCall",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Constants
INTERVAL_MS = int(os.getenv('INTERVAL_MS'))
HEX_REGEX = r'^0x[0-9a-fA-F]{64}$'

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Validate environment variables
def validate_env() -> Tuple[str, str]:
    private_key = os.getenv('PRIVATE_KEY')
    staking_contract = os.getenv('STAKING_CONTRACT_ADDRESS')

    if not private_key or not staking_contract:
        raise ValueError('Missing PRIVATE_KEY or STAKING_CONTRACT_ADDRESS in .env')

    if not private_key.startswith('0x'):
        private_key = f'0x{private_key}'
    if not staking_contract.startswith('0x'):
        staking_contract = f'0x{staking_contract}'
        
    return private_key, staking_contract

# Initialize Web3
private_key, staking_contract = validate_env()
w3 = Web3(HTTPProvider(os.getenv('ETHEREUM_RPC')))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
account = w3.eth.account.from_key(private_key)

# Contract instances
staking_contract_instance = w3.eth.contract(address=staking_contract, abi=STAKING_ABI)
link_token_address = None

# Cache linkTokenAddress
def get_link_token_address() -> str:
    global link_token_address
    if not link_token_address:
        link_token_address = staking_contract_instance.functions.getChainlinkToken().call()
    return link_token_address

def get_essential_data(link_token_address: str) -> Dict:
    is_open = staking_contract_instance.functions.isOpen().call()
    is_active = staking_contract_instance.functions.isActive().call()
    max_pool_size = staking_contract_instance.functions.getMaxPoolSize().call()
    total_principal = staking_contract_instance.functions.getTotalPrincipal().call()
    link_token_instance = w3.eth.contract(address=link_token_address, abi=LINK_TOKEN_ABI)
    link_balance = link_token_instance.functions.balanceOf(account.address).call()

    return {
        'is_open': is_open,
        'is_active': is_active,
        'max_pool_size': max_pool_size,
        'total_principal': total_principal,
        'link_balance': link_balance
    }

# Format pool info
def format_pool_info(max_pool_size: int, total_staked: int, available_space: float) -> str:
    return f"Pool: {w3.from_wei(total_staked, 'ether')}/{w3.from_wei(max_pool_size, 'ether')}, Available: {available_space} LINK"

def check_and_stake():
    try:
        link_token_address = get_link_token_address()
        data = get_essential_data(link_token_address)

        if not data['is_open'] or not data['is_active']:
            return

        available_space = data['max_pool_size'] - data['total_principal']
        available_space_in_link = w3.from_wei(available_space, 'ether')
        link_balance_in_link = w3.from_wei(data['link_balance'], 'ether')
        amount_to_stake = min(available_space_in_link, link_balance_in_link)

        logger.info(f"Pool: {w3.from_wei(data['total_principal'], 'ether')}/{w3.from_wei(data['max_pool_size'], 'ether')} LINK, Av.: {available_space_in_link} LINK")
        
        if available_space <= 0 or link_balance_in_link <= 0 or amount_to_stake <= 0:
            return 
        
        logger.info(f"Staking {amount_to_stake} LINK")

        amount_in_wei = w3.toWei(amount_to_stake, 'ether')
        link_token_instance = w3.eth.contract(address=link_token_address, abi=LINK_TOKEN_ABI)

        # Build transaction
        txn = link_token_instance.functions.transferAndCall(
            staking_contract, 
            amount_in_wei, 
            '0x'
        ).buildTransaction({
            'from': account.address,
            'nonce': w3.eth.getTransactionCount(account.address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })

        signed_txn = w3.eth.account.sign_transaction(txn, private_key)
        tx_hash = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        logger.info(f'Tx Hash: {w3.toHex(tx_hash)}')

        def check_receipt():
            try:
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
                logger.info(f'Tx Confirmed: {receipt.status}')
            except Exception as e:
                logger.error(f'Receipt Error: {str(e)}')

        Thread(target=check_receipt).start()

    except Exception as e:
        logger.error(f'Error: {str(e)}')

# Start cron job
def start_cron():
    logger.info(f'Cronjob started. Checking every {INTERVAL_MS}ms...')
    
    def run_loop():
        while True:
            check_and_stake()
            time.sleep(INTERVAL_MS / 1000) 

    thread = Thread(target=run_loop)
    thread.daemon = True 
    thread.start()

    def signal_handler(sig, frame):
        logger.info('Cronjob stopped.')
        os._exit(0)

    signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    start_cron()
    while True:
        time.sleep(1)