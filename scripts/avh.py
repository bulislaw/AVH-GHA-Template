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
  instanceState = await api_instance.v1_get_instance_state(instance.id)
  while (instanceState != state):
    if (instanceState == "error"):
      raise Exception("VM entered error state")
    await asyncio.sleep(1)
    instanceState = await api_instance.v1_get_instance_state(instance.id)

async def main(args):
    configuration = AvhAPI.Configuration(host = args.endpoint)
    async with AvhAPI.ApiClient(configuration=configuration) as api_client:
        api_instance = AvhAPI.ArmApi(api_client)
        token_response = await api_instance.v1_auth_login({
            "apiToken": args.token,
        })

        logging.info("Logged in to AVH")
        configuration.access_token = token_response.token

        logging.info("Finding a project...")
        api_response = await api_instance.v1_get_projects()
        projectId = api_response[0].id
        logging.info(f"Done... project ID: {projectId}")

        logging.info(f"Pick a board...")
        api_response = await api_instance.v1_get_models()
        chosenModel = None
        for model in api_response:
            if model.flavor.startswith(args.board):
                chosenModel = model
                break

        if chosenModel is None:
            raise Exception(f"Board not found: {args.board}")

        logging.info(f"Chosen board: {chosenModel.name}")

        logging.info(f"Pick a base firmware...")
        api_response = await api_instance.v1_get_model_software(chosenModel.model)
        chosenSoftware = api_response[0]
        logging.info(f"Chosen base firmware: {chosenSoftware.filename}")

        logging.info(f"Creating a new instance of the board...")
        instance = await api_instance.v1_create_instance({
            "name": f"{chosenModel.name}-{time.time()}",
            "project": projectId,
            "flavor": chosenModel.flavor,
            "os": chosenSoftware.version,
            "osbuild": chosenSoftware.buildid
        })
        logging.info(f"Done... instance ID: {instance.id}")

        logging.info("Waiting for VM to boot...")
        await waitForState(api_instance, instance, "on")
        logging.info("Done... VM is running")

        logging.info(f"Setting the VM to use the test image: {args.firmware}")
        api_response = await api_instance.v1_create_image("fwbinary", "plain",
            name=os.path.basename(args.firmware),
            instance=instance.id,
            file=args.firmware
        )

        logging.info("Resetting VM to use the new software")
        api_response = await api_instance.v1_reboot_instance(instance.id)
        await waitForState(api_instance, instance, "on")
        logging.info("Done... VM is running")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                prog = "Experimental client for Arm Virtual Hardware",
                description="It allows you to run basic tests on Arm Virtual Hardware using the REST API")

    parser.add_argument("-t", "--token", help="Authentication token for AVH", type=str, required=True)
    parser.add_argument("-b", "--board", help="A board type to run tests on", type=str, required=True)
    parser.add_argument("-f", "--firmware", help="Path to a firmware binary to use", type=Path, required=True)
    parser.add_argument("-s", "--script", help="[Optional] Path to a test script", type=Path, required=False)
    parser.add_argument("-e", "--endpoint", help="[Optional] API endpoint to use (default: https://app.avh.arm.com/api)",
                        type=str, required=False, default="https://app.avh.arm.com/api")
    parser.add_argument('-v', '--verbose', action='store_true')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.ERROR)

    asyncio.run(asyncio.wait_for(main(args), 120))
    exit(0)


