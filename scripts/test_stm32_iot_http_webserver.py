#!/usr/bin/env python3

# Copyright (c) 2023 Arm Ltd. All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

from websockets import client as ws
import ssl
import re
import logging

async def waitForPattern(console, pattern):
  text = ''
  match = None

  logging.info(f"Waiting for pattern: {pattern}")
  async for message in console:
    text += message.decode('utf-8')
    while '\n' in text:
      offset = text.find('\n')
      line, text = text[:offset], text[offset+1:]

      match = re.search(pattern, line)
      if (match):
        logging.info("Found")
        return match

async def run(api_instance, vm):
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
