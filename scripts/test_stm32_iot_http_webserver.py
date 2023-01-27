#!/usr/bin/env python3

# Copyright (c) 2023 Arm Ltd. All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

from websockets import client as ws
import ssl
import logging
from avh import waitForPattern

async def run_test(api_instance, vm):
    """Run the tests

    It'll throw an exception if the test fails or return cleanly if it passes

    Currently we only validate if the VM boots
    Parameters:
        api_instance: Connected API instance
        vm: VM instance
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    consoleEndpoint = await api_instance.v1_get_instance_console(vm.id)
    console = await ws.connect(consoleEndpoint.url, ssl=ctx)

    # waitForPattern timeouts if the pattern is not found
    try:
        result = await waitForPattern(console, "STM32U5 Webserver Demonstration")
    finally:
        await console.close()
