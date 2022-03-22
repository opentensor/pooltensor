# The MIT License (MIT)
# Copyright © 2021 Yuma Rao

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, 
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of 
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION 
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
# DEALINGS IN THE SOFTWARE.

import bittensor
import random
import time
import torch
from rich import print

def run ():

    # Make a subtensor connection to the pool chain.
    # This is local because we are assuming you ran the chain locally.
    # In practice you want to run about 10 validators for your pool on pretty beefy machines.
    print ('Connecting to pool chain...')
    pool_chain = bittensor.subtensor( chain_endpoint = '127.0.0.1:9944')
    print ('Done.')

    # Load all the nodes from the pool. Members of this pool will register themselves
    # onto the pool chain and be discovered by by this endpoint.
    # bellow we sync with the pool chain.
    print ('Synchain pool chain graph...')
    pool_graph = bittensor.metagraph( subtensor = pool_chain  ).sync()
    print ('Done.')

    # Make a subtensor connection to the parent chain, this is the one we are being validated by.
    # We are using nobunaga for testing.
    print ('Connecting to parent chain...')
    parent_chain = bittensor.subtensor( network = 'nobunaga' )
    print ('Done.')

    print ('Synchain parent chain graph...')
    parent_graph = bittensor.metagraph( subtensor = parent_chain ).sync()
    print ('Done.')

    # Fisrt create the wallet key using the cli
    # btcli new_coldkey --wallet.name poolcoldkey
    # btcli new_hotkey --wallet.name poolhotkey
    print ('Loading pool chain wallet...')
    pool_wallet = bittensor.wallet( name = 'poolwallet', hotkey = 'poolhotkey' )
    print ('Done.')

    # Register the pool wallet to nobunaga
    print ('Registering pool chain wallet to parent chain ...')
    pool_wallet.register( subtensor = parent_chain )
    print ('Done.')

    # Register the pool wallet on the poolchain
    # This does not link these accounts, but it would be great if we could create a bridge programatically
    # something like wallet.bridge( nobunaga, poolchain )
    print ('Registering pool chain wallet to pool chain ...')
    pool_wallet.register( subtensor = pool_chain )
    print ('Done.')

    # We need an RPC client to forward requests onward. 
    print ('Creating dendrite ...')
    dendrite = bittensor.dendrite( wallet = pool_wallet )
    print ('Done.')

    # We are updating weights for each miner, this is nothing crazy, 
    # we are just going to use a code base scoring.
    moving_average_delta = 0.9
    poolscores = torch.zeros_like( pool_graph.stake )

    # Forward is the function that recieves calls from peers on nobunaga
    def forward_text ( inputs_x ):
        # Randomly select a peer from the poolgraph.
        # Note that this not weighted, it is purely random.
        endpoint = random.choice( pool_graph.endpoints )
        
        # Query the pool
        response, time, code = dendrite.forward_text( inputs = inputs_x, endpoints = endpoint )

        # Check code.
        # Note that this is purely code based, not time based.
        if code.item() == 1: # Success
            poolscores[endpoint.uid] = moving_average_delta * poolscores[endpoint.uid] + (1 - moving_average_delta) * 1 # Converges towards 1
        else: # Failure
            poolscores[endpoint.uid] = moving_average_delta * poolscores[endpoint.uid] + (1 - moving_average_delta) * 0 # Converging towards 0
        
        # Return the responses
        return response

    # Create the axon RPC endpoint
    print ('Creating axon ...')
    axon = bittensor.axon( 
        wallet = pool_wallet,
        forward_text = forward_text
    )
    print ('Done.')

    # Start the axon RPC endpoint serving the forward function.
    print ('Starting axon ...')
    axon.start()
    print ('Done.')

    # Tell nobubaga that we exist and can start recieving messages.
    print ('Serving axon on pool chain...')
    axon.serve( subtensor = parent_chain )
    print ('Done.')

    # Main loop.
    sync_every_n_blocks = 10
    print ('Starting main loop ...')
    while True:

        # Make an update every few blocks
        if pool_chain.block % sync_every_n_blocks:
            print ('Setting validator weights on pool chain ...')

            # Set your weights onto the pool chain.
            pool_chain.set_weights(
                wallet = pool_wallet,
                uids = pool_graph.uids,
                weights = poolscores,
                wait_for_finalization = True 
            )
            print ('Done.')

            # Get the latest nodes from your pool
            print ('Syncing the pool graph ...')
            pool_graph.sync( subtensor = pool_chain )
            print ('Done.')

        else:
            print ('...')
            time.sleep( 12 )



if __name__ == "__main__":
    run()




