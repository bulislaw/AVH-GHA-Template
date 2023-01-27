#!/usr/bin/env python3

# Copyright (c) 2023 Arm Ltd. All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

import argparse
from pathlib import Path
import asyncio
import avh_api_async as AvhAPI
import time
import logging
import os

async def waitForState(api_instance, instance, state):
    """Wait for the VM to enter the given state

    Warning/TODO: There's no timeout so this function can block forever

    Parameters:
        api_instance: Connected API instance
        instance: VM instance
        state: State to wait for
    """
    instanceState = await api_instance.v1_get_instance_state(instance.id)
    while (instanceState != state):
        if (instanceState == "error"):
            raise Exception("VM entered error state")
        await asyncio.sleep(1)
        instanceState = await api_instance.v1_get_instance_state(instance.id)

async def setupModel(api_instance, board, firmware):
    """Create a new VM instance of the board and flash the firmware to it

    Parameters:
        api_instance: Connected API instance
        board: Board name
        firmware: Path to the firmware file

    Returns:
        The VM instance
    """
    logging.info("Finding a project...")
    api_response = await api_instance.v1_get_projects()
    projectId = api_response[0].id
    logging.info(f"Done... project ID: {projectId}")

    logging.info(f"Pick a board...")
    api_response = await api_instance.v1_get_models()
    chosenModel = None
    for model in api_response:
        if model.flavor.startswith(board):
            chosenModel = model
            break

    if chosenModel is None:
        raise Exception(f"Board not found: {board}")

    logging.info(f"Chosen board: {chosenModel.name}")

    logging.info(f"Pick a base firmware...")
    api_response = await api_instance.v1_get_model_software(chosenModel.model)
    chosenSoftware = api_response[0]
    logging.info(f"Chosen base firmware: {chosenSoftware.filename}")

    logging.info(f"Creating a new instance of the board...")
    vm = await api_instance.v1_create_instance({
        "name": f"GHA-{chosenModel.name}-{time.time()}",
        "project": projectId,
        "flavor": chosenModel.flavor,
        "os": chosenSoftware.version,
        "osbuild": chosenSoftware.buildid
    })
    logging.info(f"Done... instance ID: {vm.id}")

    logging.info("Waiting for VM to boot...")
    await waitForState(api_instance, vm, "on")
    logging.info("Done... VM is running")

    logging.info(f"Setting the VM to use the test image: {firmware}")
    api_response = await api_instance.v1_create_image("fwbinary", "plain",
        name=os.path.basename(firmware),
        instance=vm.id,
        file=firmware
    )

    logging.info("Resetting VM to use the new firmware...")
    api_response = await api_instance.v1_reboot_instance(vm.id)
    await waitForState(api_instance, vm, "on")
    logging.info("Done... VM is running")

    return vm

async def runTests(api_instance, vm, script, timeout):
    """Run the test script on the VM

    This function will import the test script and run the run_test() function from it
    run_test() function takes two parameters:
        api_instance: Connected API instance
        vm: VM instance

    It's expected to throw an exception if the test fails and return cleanly if it passes

    Parameters:
        api_instance: Connected API instance
        vm: VM instance
        script: Path to the test script
        timeout: Timeout for the test script
    """
    logging.info(f"Running test file: {script}")
    from importlib.machinery import SourceFileLoader
    test = SourceFileLoader("test", script).load_module()
    try:
        await asyncio.wait_for(test.run_test(api_instance, vm), timeout)
    except Exception as e:
        print(f"Test failed: {e}")
        raise Exception("Test failed")
    finally:
        logging.info("Test file finished.")

    print("Test passed")

async def main(args):
    """ Connect to AVH, create a VM, run the tests and clean up the AVH instance
    """
    vm = None
    configuration = AvhAPI.Configuration(host = args.endpoint)
    async with AvhAPI.ApiClient(configuration=configuration) as api_client:
        api_instance = AvhAPI.ArmApi(api_client)
        token_response = await api_instance.v1_auth_login({
            "apiToken": args.token,
        })

        logging.info("Logged in to AVH")
        configuration.access_token = token_response.token

        try:
            vm = await setupModel(api_instance, args.board, args.firmware)

            if args.script is not None:
                await runTests(api_instance, vm, args.script, args.timeout)

        finally:
            if vm is not None:
                logging.info("Cleaning up...")
                await api_instance.v1_delete_instance(vm.id)
                logging.info("Done... vm deleted")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog = "Experimental client for Arm Virtual Hardware",
        description="It allows you to run basic tests on Arm Virtual Hardware using the REST API"
    )

    parser.add_argument("-t", "--token", help="Authentication token for AVH", type=str, required=True)
    parser.add_argument("-b", "--board", help="A board type to run tests on", type=str, required=True)
    parser.add_argument("-f", "--firmware", help="Path to a firmware binary to use", type=str, required=True)
    parser.add_argument("-s", "--script", help="[Optional] Path to a test script", type=str, required=False)
    parser.add_argument("-e", "--endpoint", help="[Optional] API endpoint to use (default: https://app.avh.arm.com/api)", type=str,
            required=False, default="https://app.avh.arm.com/api")
    parser.add_argument("--timeout", help="[Optional] Timeout for the test script (default: 30s)", type=int, required=False, default=30)
    parser.add_argument('-v', '--verbose', action='store_true')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.ERROR)

    logging.info(f"Run with args: {args}")

    asyncio.run(asyncio.wait_for(main(args), 120))
    exit(0)


